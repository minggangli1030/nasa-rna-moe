#!/usr/bin/env python3
"""Train all fixed utility-partition expert banks in one frozen-trunk pass.

The banks have disjoint trainable parameters and independent optimizers.  They
share only the frozen trunk activations and a deterministic natural sample
schedule, so summing their hard-dispatch losses preserves each bank's isolated
gradient while avoiding 21 redundant trunk-training jobs.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader

from train_fixed_partition_moe import (
    FixedGeneMaskDataset,
    _atomic_json,
    _load_inputs,
    _resolve_device,
    evaluate_fixed_partition,
)
from train_latent_moe import ResidualExpert, _masked_row_mse, load_frozen_trunk
from train_manifest import (
    DeterministicBudgetBatchSampler,
    DeterministicMaskedExpressionDataset,
    balanced_validation_weights,
    seed_data_worker,
    seed_everything,
    sha256_file,
    sha256_json,
    sha256_lines,
    stable_seed,
)


DEFAULT_AXES = (
    "head_gradient_k2",
    "head_gradient_k3",
    "residual_pca_k2",
    "residual_pca_k3",
    "random_k2",
    "random_k3",
    "organ_k5",
)


class PackedExpertBanks(nn.Module):
    def __init__(
        self,
        trunk: nn.Module,
        axis_k: dict[str, int],
        *,
        adapter_dim: int,
        seed: int,
    ):
        super().__init__()
        self.trunk = trunk
        self.trunk.requires_grad_(False)
        hidden_dim = int(trunk.gene_embedding.embedding_dim)
        banks: dict[str, nn.ModuleList] = {}
        for axis in sorted(axis_k):
            bank_seed = stable_seed(seed, "fixed_expert_bank", axis) % (2**63 - 1)
            with torch.random.fork_rng(devices=[], enabled=True):
                torch.manual_seed(bank_seed)
                banks[axis] = nn.ModuleList(
                    ResidualExpert(hidden_dim, adapter_dim)
                    for _ in range(axis_k[axis])
                )
        self.banks = nn.ModuleDict(banks)

    def train(self, mode: bool = True):
        super().train(mode)
        self.trunk.eval()
        return self

    def encode_base(self, masked: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        with torch.no_grad():
            hidden = self.trunk.encode(masked)
            base = self.trunk.decode(hidden)
        return hidden, base

    def bank_predictions(
        self, axis: str, hidden: torch.Tensor, base: torch.Tensor
    ) -> torch.Tensor:
        residuals = torch.stack(
            [expert(hidden) for expert in self.banks[axis]], dim=1
        )
        return base.unsqueeze(1) + residuals


class _BankEvaluationView(nn.Module):
    def __init__(self, packed: PackedExpertBanks, axis: str):
        super().__init__()
        self.trunk = packed.trunk
        self.experts = packed.banks[axis]
        self.num_experts = len(self.experts)

    def forward(self, masked: torch.Tensor):
        with torch.no_grad():
            hidden = self.trunk.encode(masked)
            base = self.trunk.decode(hidden)
        residuals = torch.stack([expert(hidden) for expert in self.experts], dim=1)
        predictions = base.unsqueeze(1) + residuals
        logits = torch.zeros(
            len(masked), self.num_experts, device=masked.device, dtype=base.dtype
        )
        return predictions, logits, base


def _validate_axes(partitions: pd.DataFrame, axes: list[str]) -> dict[str, np.ndarray]:
    output: dict[str, np.ndarray] = {}
    for axis in axes:
        if axis not in partitions:
            raise ValueError(f"partition manifest lacks requested axis {axis!r}")
        raw = partitions[axis].to_numpy()
        if pd.isna(raw).any():
            raise ValueError(f"axis {axis!r} contains missing labels")
        labels = np.asarray(raw, dtype=np.int64)
        unique = np.unique(labels)
        if not np.array_equal(unique, np.arange(len(unique))):
            raise ValueError(f"axis {axis!r} labels are not contiguous: {unique}")
        output[axis] = labels
    return output


def run_packed_training(args: argparse.Namespace) -> dict[str, Any]:
    axes = list(args.axis or DEFAULT_AXES)
    if len(axes) != len(set(axes)):
        raise ValueError("axis list contains duplicates")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output_dir}")
    seed_everything(args.seed, deterministic=True)
    device = _resolve_device(args.device)
    trunk, checkpoint_config, checkpoint = load_frozen_trunk(args.pooled_checkpoint, device)
    load_args = SimpleNamespace(**vars(args))
    load_args.axis = axes[0]
    (
        selection,
        train_expression,
        validation_expression,
        expression_info,
        _,
        _,
        score_indices,
        partition_report,
    ) = _load_inputs(load_args, checkpoint_config)
    partitions = pd.read_parquet(args.partition_manifest)
    labels_all = _validate_axes(partitions, axes)
    train_count = len(selection.train)
    labels_train = {name: values[:train_count] for name, values in labels_all.items()}
    labels_validation = {name: values[train_count:] for name, values in labels_all.items()}
    axis_k = {name: int(len(np.unique(labels_train[name]))) for name in axes}
    budgets: dict[str, int] = {}
    for axis, k in axis_k.items():
        draws = args.exposures_per_expert * k
        if draws % args.batch_size:
            raise ValueError("per-bank exposure budget must divide by batch size")
        budgets[axis] = draws // args.batch_size
    if args.max_updates is None:
        max_updates = max(budgets.values())
    else:
        max_updates = int(args.max_updates)
        if not args.smoke_only and max_updates != max(budgets.values()):
            raise ValueError("full packed run must continue through the largest bank budget")
        if args.smoke_only:
            budgets = {axis: min(value, max_updates) for axis, value in budgets.items()}

    train_ids = selection.train[args.sample_id_column].astype(str).tolist()
    validation_ids = selection.validation[args.sample_id_column].astype(str).tolist()
    train_dataset = DeterministicMaskedExpressionDataset(
        train_expression,
        train_ids,
        normalization="log1p_tpm",
        mask_ratio=args.mask_ratio,
        mask_token=args.mask_token,
        seed=args.seed,
        phase="packed_fixed_partition_banks",
        fixed_masks=False,
    )
    validation_dataset = FixedGeneMaskDataset(
        validation_expression,
        validation_ids,
        mask_indices=score_indices,
        mask_token=args.mask_token,
    )
    sampler = DeterministicBudgetBatchSampler(
        train_ids,
        batch_size=args.batch_size,
        max_updates=max_updates,
        seed=stable_seed(args.seed, "packed_fixed_partition_sampler"),
        sampling_mode="natural",
    )
    generator = torch.Generator().manual_seed(
        stable_seed(args.seed, "packed_fixed_partition_loader") % (2**63 - 1)
    )
    train_loader = DataLoader(
        train_dataset,
        batch_sampler=sampler,
        num_workers=args.num_workers,
        worker_init_fn=seed_data_worker,
        generator=generator,
    )
    validation_loader = DataLoader(
        validation_dataset,
        batch_size=args.validation_batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        worker_init_fn=seed_data_worker,
        generator=generator,
    )
    validation_weights = balanced_validation_weights(
        selection.validation,
        organ_column=args.organ_column,
        group_column=args.group_column,
    )
    model = PackedExpertBanks(
        trunk,
        axis_k,
        adapter_dim=args.adapter_dim,
        seed=args.seed,
    ).to(device)
    optimizers = {
        axis: AdamW(
            model.banks[axis].parameters(),
            lr=args.learning_rate,
            weight_decay=args.weight_decay,
        )
        for axis in axes
    }
    schedulers = {
        axis: CosineAnnealingLR(optimizers[axis], T_max=max(1, budgets[axis]))
        for axis in axes
    }
    use_amp = bool(args.use_amp and device.type == "cuda")
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    exposure_counts = {
        axis: np.bincount(
            labels_train[axis][
                np.asarray(sampler.flat_indices[: budgets[axis] * args.batch_size])
            ],
            minlength=axis_k[axis],
        ).tolist()
        for axis in axes
    }
    common_hashes = {
        "protocol_sha256": sha256_file(args.protocol),
        "pooled_checkpoint_sha256": sha256_file(args.pooled_checkpoint),
        "expression_sha256": sha256_file(args.expression_parquet),
        "manifest_sha256": sha256_file(args.manifest),
        "partition_manifest_sha256": sha256_file(args.partition_manifest),
        "partition_report_sha256": sha256_file(args.partition_report),
        "axis_definitions_sha256": sha256_file(args.axis_definitions),
        "train_sample_ids_sha256": sha256_lines(train_ids),
        "calibration_sample_ids_sha256": sha256_lines(validation_ids),
        "gene_order_sha256": sha256_lines(expression_info.gene_columns),
        "score_gene_indices_sha256": sha256_lines([str(value) for value in score_indices]),
    }
    if common_hashes["partition_manifest_sha256"] != partition_report["hashes"]["partition_manifest_sha256"]:
        raise ValueError("partition manifest is not pinned by partition report")
    top_config = {
        "axes": axes,
        "axis_k": axis_k,
        "bank_update_budgets": budgets,
        "max_updates": max_updates,
        "exposures_per_expert_target": args.exposures_per_expert,
        "batch_size": args.batch_size,
        "validation_batch_size": args.validation_batch_size,
        "adapter_dim": args.adapter_dim,
        "mask_ratio": args.mask_ratio,
        "score_gene_count": int(len(score_indices)),
        "learning_rate": args.learning_rate,
        "weight_decay": args.weight_decay,
        "sampling": "one shared deterministic natural schedule; no organ/study sampling labels",
        "checkpoint_policy": "predetermined_final_update_per_bank",
        "router_present": False,
        "use_amp": use_amp,
    }
    top_metadata = {
        "schema_version": 1,
        "status": "running",
        "research_stage": "stage2_competitive_followup",
        "experiment": "packed_hard_fixed_partition_expert_banks",
        "training_seed": int(args.seed),
        "test_accessed": False,
        "mechanical_only": bool(args.smoke_only),
        "config": top_config,
        "counts": {
            "train": len(train_ids),
            "calibration": len(validation_ids),
            "genes": len(expression_info.gene_columns),
            "score_genes": len(score_indices),
        },
        "exposure_counts": exposure_counts,
        "pooled_checkpoint_update": checkpoint.get("update"),
        "hashes": dict(common_hashes),
    }
    top_metadata["hashes"]["resolved_config_sha256"] = sha256_json(top_config)
    _atomic_json(output_dir / "run_metadata.json", top_metadata)

    histories = {axis: [] for axis in axes}
    start_time = time.time()
    model.train()
    for update, batch in enumerate(train_loader, start=1):
        active = [axis for axis in axes if update <= budgets[axis]]
        for axis in active:
            optimizers[axis].zero_grad(set_to_none=True)
        masked, truth, mask = (value.to(device) for value in batch)
        batch_indices = np.asarray(
            [int(item[0]) for item in sampler.batches[update - 1]], dtype=np.int64
        )
        autocast = torch.autocast(device_type="cuda", dtype=torch.float16, enabled=use_amp)
        losses: dict[str, torch.Tensor] = {}
        with autocast:
            hidden, base = model.encode_base(masked)
            for axis in active:
                predictions = model.bank_predictions(axis, hidden, base)
                labels = torch.as_tensor(labels_train[axis][batch_indices], device=device)
                row = torch.arange(len(labels), device=device)
                losses[axis] = _masked_row_mse(
                    predictions[row, labels], truth, mask
                ).mean()
            total_loss = torch.stack(list(losses.values())).sum()
        scaler.scale(total_loss).backward()
        for axis in active:
            scaler.step(optimizers[axis])
            schedulers[axis].step()
        scaler.update()
        if update == 1 or update % args.log_interval == 0 or update in set(budgets.values()):
            values = {
                axis: float(losses[axis].detach().cpu()) for axis in active
            }
            for axis, value in values.items():
                histories[axis].append({
                    "update": int(update),
                    "train_reconstruction_loss": value,
                })
            _atomic_json(output_dir / "training_history.json", histories)
            print(
                f"update={update}/{max_updates} active={','.join(active)} "
                + " ".join(f"{axis}={value:.6f}" for axis, value in values.items()),
                flush=True,
            )

    bank_results: dict[str, Any] = {}
    groups = selection.validation[args.group_column].astype(str).to_numpy()
    organs = selection.validation[args.organ_column].astype(str).to_numpy()
    for axis in axes:
        bank_dir = output_dir / "banks" / axis
        bank_dir.mkdir(parents=True, exist_ok=False)
        view = _BankEvaluationView(model, axis).to(device)
        metrics, arrays = evaluate_fixed_partition(
            view,
            validation_loader,
            labels=labels_validation[axis],
            groups=groups,
            organs=organs,
            sample_weights=validation_weights,
            device=device,
            crossfit_seed=stable_seed(args.crossfit_seed, axis) % (2**32 - 1),
            crossfit_folds=args.crossfit_folds,
        )
        np.savez_compressed(
            bank_dir / "calibration_scores.npz",
            sample_ids=np.asarray(validation_ids, dtype=str),
            groups=np.asarray(groups, dtype=str),
            organs=np.asarray(organs, dtype=str),
            sample_weights=validation_weights.astype(np.float64),
            **arrays,
        )
        expert_state = {
            f"experts.{index}.{name}": value.detach().cpu()
            for index, expert in enumerate(model.banks[axis])
            for name, value in expert.state_dict().items()
        }
        bank_config = {
            "axis": axis,
            "num_experts": axis_k[axis],
            "adapter_dim": args.adapter_dim,
            "router_trainable": False,
            "final_update": budgets[axis],
            "exposures_per_expert_target": args.exposures_per_expert,
            "realized_exposure_counts": exposure_counts[axis],
            "batch_size": args.batch_size,
            "mask_ratio": args.mask_ratio,
            "score_gene_count": int(len(score_indices)),
            "checkpoint_policy": "predetermined_final_update",
            "packed_shared_trunk": True,
        }
        torch.save(
            {
                "schema_version": 1,
                "axis": axis,
                "training_seed": int(args.seed),
                "final_update": budgets[axis],
                "config": bank_config,
                "expert_state_dict": expert_state,
                "pooled_checkpoint_sha256": common_hashes["pooled_checkpoint_sha256"],
            },
            bank_dir / "final_experts.pt",
        )
        bank_metadata = {
            "schema_version": 1,
            "status": "complete",
            "research_stage": "stage2_competitive_followup",
            "experiment": "hard_fixed_partition_residual_experts",
            "axis": axis,
            "training_seed": int(args.seed),
            "test_accessed": False,
            "mechanical_only": bool(args.smoke_only),
            "config": bank_config,
            "hashes": {
                **common_hashes,
                "resolved_config_sha256": sha256_json(bank_config),
            },
            "calibration_metrics": metrics,
            "artifacts": {
                "final_experts_sha256": sha256_file(bank_dir / "final_experts.pt"),
                "calibration_scores_sha256": sha256_file(bank_dir / "calibration_scores.npz"),
            },
        }
        _atomic_json(bank_dir / "run_metadata.json", bank_metadata)
        (bank_dir / "COMPLETE").touch()
        bank_results[axis] = {
            "final_update": budgets[axis],
            "calibration_metrics": metrics,
            "path": str(bank_dir),
        }
    top_metadata.update({
        "status": "complete",
        "elapsed_seconds": float(time.time() - start_time),
        "banks": bank_results,
    })
    _atomic_json(output_dir / "run_metadata.json", top_metadata)
    (output_dir / "COMPLETE").touch()
    return top_metadata


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expression-parquet", required=True)
    parser.add_argument("--expression-metadata", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--pooled-checkpoint", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--partition-manifest", required=True)
    parser.add_argument("--partition-report", required=True)
    parser.add_argument("--axis-definitions", required=True)
    parser.add_argument("--axis", action="append")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--train-split", default="train")
    parser.add_argument("--validation-split", default="calibration")
    parser.add_argument("--train-filter-column", default="balanced_train")
    parser.add_argument("--sample-id-column", default="sample_id")
    parser.add_argument("--organ-column", default="organ")
    parser.add_argument("--group-column", default="series_group_id")
    parser.add_argument("--adapter-dim", type=int, default=64)
    parser.add_argument("--exposures-per-expert", type=int, default=2400)
    parser.add_argument("--max-updates", type=int)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--validation-batch-size", type=int, default=8)
    parser.add_argument("--mask-ratio", type=float, default=0.30)
    parser.add_argument("--mask-token", type=float, default=-10.0)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--crossfit-folds", type=int, default=5)
    parser.add_argument("--crossfit-seed", type=int, default=8675309)
    parser.add_argument("--log-interval", type=int, default=100)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--use-amp", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--smoke-only", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = run_packed_training(args)
    print(json.dumps({
        "status": result["status"],
        "training_seed": result["training_seed"],
        "elapsed_seconds": result["elapsed_seconds"],
        "banks": result["banks"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
