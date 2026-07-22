#!/usr/bin/env python3
"""Train all fixed utility-partition expert banks in one frozen-trunk pass.

The banks have disjoint trainable parameters and independent optimizers.  They
share only the frozen trunk activations and a deterministic natural sample
schedule, so summing their hard-dispatch losses preserves each bank's isolated
gradient while avoiding 21 redundant trunk-training jobs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
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
    SAMPLING_MODES,
    DeterministicBudgetBatchSampler,
    DeterministicMaskedExpressionDataset,
    balanced_validation_weights,
    build_exposure_frame,
    seed_data_worker,
    seed_everything,
    sha256_file,
    sha256_json,
    sha256_lines,
    stable_seed,
    summarize_exposures,
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
        axis_expert_keys: dict[str, list[str]] | None = None,
    ):
        super().__init__()
        self.trunk = trunk
        self.trunk.requires_grad_(False)
        hidden_dim = int(trunk.gene_embedding.embedding_dim)
        banks: dict[str, nn.ModuleList] = {}
        for axis in sorted(axis_k):
            expert_keys = None if axis_expert_keys is None else axis_expert_keys.get(axis)
            if expert_keys is None:
                bank_seed = stable_seed(seed, "fixed_expert_bank", axis) % (2**63 - 1)
                with torch.random.fork_rng(devices=[], enabled=True):
                    torch.manual_seed(bank_seed)
                    banks[axis] = nn.ModuleList(
                        ResidualExpert(hidden_dim, adapter_dim)
                        for _ in range(axis_k[axis])
                    )
                continue
            if len(expert_keys) != axis_k[axis] or len(set(expert_keys)) != len(expert_keys):
                raise ValueError(f"axis {axis!r} expert initialization keys are invalid")
            experts = nn.ModuleList()
            for expert_key in expert_keys:
                expert_seed = stable_seed(
                    seed, "fixed_semantic_expert", str(expert_key)
                ) % (2**63 - 1)
                with torch.random.fork_rng(devices=[], enabled=True):
                    torch.manual_seed(expert_seed)
                    experts.append(ResidualExpert(hidden_dim, adapter_dim))
            banks[axis] = experts
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


def _validate_axes(
    partitions: pd.DataFrame,
    axes: list[str],
    *,
    allow_fallback_label: bool = False,
) -> dict[str, np.ndarray]:
    output: dict[str, np.ndarray] = {}
    for axis in axes:
        if axis not in partitions:
            raise ValueError(f"partition manifest lacks requested axis {axis!r}")
        raw = partitions[axis].to_numpy()
        if pd.isna(raw).any():
            raise ValueError(f"axis {axis!r} contains missing labels")
        labels = np.asarray(raw, dtype=np.int64)
        unique = np.unique(labels)
        if allow_fallback_label:
            if np.any(unique < -1):
                raise ValueError(f"axis {axis!r} contains a label below fallback -1")
            active = unique[unique >= 0]
            if not len(active) or not np.array_equal(active, np.arange(len(active))):
                raise ValueError(
                    f"axis {axis!r} active labels are not contiguous: {unique}"
                )
        elif not np.array_equal(unique, np.arange(len(unique))):
            raise ValueError(f"axis {axis!r} labels are not contiguous: {unique}")
        output[axis] = labels
    return output


def _parse_axis_int_overrides(
    values: list[str] | None,
    axes: list[str],
    *,
    option_name: str,
) -> dict[str, int]:
    output: dict[str, int] = {}
    for raw in values or []:
        if "=" not in raw:
            raise ValueError(f"{option_name} must use AXIS=INTEGER")
        axis, value = raw.split("=", 1)
        if axis not in axes:
            raise ValueError(f"{option_name} names unknown axis {axis!r}")
        if axis in output:
            raise ValueError(f"{option_name} repeats axis {axis!r}")
        try:
            parsed = int(value)
        except ValueError as error:
            raise ValueError(f"{option_name} has noninteger value {raw!r}") from error
        if parsed <= 0:
            raise ValueError(f"{option_name} values must be positive")
        output[axis] = parsed
    return output


def _parse_axis_expert_keys(
    values: list[str] | None,
    axis_k: dict[str, int],
) -> dict[str, list[str]]:
    output: dict[str, list[str]] = {}
    for raw in values or []:
        if "=" not in raw:
            raise ValueError("axis-expert-key must use AXIS=KEY0,KEY1,...")
        axis, joined = raw.split("=", 1)
        if axis not in axis_k:
            raise ValueError(f"axis-expert-key names unknown axis {axis!r}")
        if axis in output:
            raise ValueError(f"axis-expert-key repeats axis {axis!r}")
        keys = [value.strip() for value in joined.split(",")]
        if (
            len(keys) != axis_k[axis]
            or any(not value for value in keys)
            or len(set(keys)) != len(keys)
        ):
            raise ValueError(f"axis-expert-key count/values are invalid for {axis!r}")
        output[axis] = keys
    return output


def _tensor_state_sha256(state: dict[str, torch.Tensor]) -> str:
    digest = hashlib.sha256()
    for name in sorted(state):
        value = state[name].detach().cpu().contiguous()
        digest.update(name.encode("utf-8"))
        digest.update(str(value.dtype).encode("utf-8"))
        digest.update(np.asarray(value.shape, dtype=np.int64).tobytes())
        digest.update(value.numpy().tobytes())
    return digest.hexdigest()


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
    allow_fallback_label = bool(getattr(args, "allow_fallback_label", False))
    final_refit = bool(getattr(args, "final_refit", False))
    sampling_mode = str(getattr(args, "sampling_mode", "natural"))
    code_commit = str(getattr(args, "code_commit", "unknown"))
    if final_refit and re.fullmatch(r"[0-9a-f]{40}", code_commit) is None:
        raise ValueError("final refit requires the full 40-character Git commit")
    if final_refit and bool(getattr(args, "require_calibration_coverage", False)):
        raise ValueError(
            "final refit merges calibration into fitting and cannot request "
            "calibration coverage evaluation"
        )
    trunk, checkpoint_config, checkpoint = load_frozen_trunk(args.pooled_checkpoint, device)
    load_args = SimpleNamespace(**vars(args))
    load_args.axis = axes[0]
    load_args.allow_fallback_label = allow_fallback_label
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
    labels_all = _validate_axes(
        partitions,
        axes,
        allow_fallback_label=allow_fallback_label,
    )
    train_count = len(selection.train)
    source_train_labels = {
        name: values[:train_count] for name, values in labels_all.items()
    }
    labels_validation = {name: values[train_count:] for name, values in labels_all.items()}
    labels_train = labels_all if final_refit else source_train_labels
    axis_k = {
        name: int(len(np.unique(labels_train[name][labels_train[name] >= 0])))
        for name in axes
    }
    for axis in axes:
        expected = np.arange(axis_k[axis])
        train_active = np.unique(labels_train[axis][labels_train[axis] >= 0])
        if not np.array_equal(train_active, expected):
            raise ValueError(f"axis {axis!r} training labels do not cover 0..K-1")
        if bool(getattr(args, "require_calibration_coverage", False)):
            validation_active = np.unique(
                labels_validation[axis][labels_validation[axis] >= 0]
            )
            if not np.array_equal(validation_active, expected):
                raise ValueError(
                    f"axis {axis!r} calibration labels do not cover 0..K-1"
                )
    update_overrides = _parse_axis_int_overrides(
        getattr(args, "axis_update_budget", None),
        axes,
        option_name="axis-update-budget",
    )
    target_overrides = _parse_axis_int_overrides(
        getattr(args, "axis_target_exposures", None),
        axes,
        option_name="axis-target-exposures",
    )
    axis_expert_keys = _parse_axis_expert_keys(
        getattr(args, "axis_expert_key", None), axis_k
    )
    budgets: dict[str, int] = {}
    for axis, k in axis_k.items():
        draws = args.exposures_per_expert * k
        if draws % args.batch_size:
            raise ValueError("per-bank exposure budget must divide by batch size")
        budgets[axis] = update_overrides.get(axis, draws // args.batch_size)
        if np.any(labels_train[axis] < 0) and axis not in update_overrides:
            raise ValueError(
                f"fallback axis {axis!r} requires an explicit axis-update-budget"
            )
    target_exposures = {
        axis: target_overrides.get(axis, int(args.exposures_per_expert))
        for axis in axes
    }
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
    if final_refit:
        training_frame = pd.concat(
            [selection.train, selection.validation], ignore_index=True
        )
        training_expression = np.concatenate(
            [train_expression, validation_expression], axis=0
        )
    else:
        training_frame = selection.train
        training_expression = train_expression
    fitting_ids = training_frame[args.sample_id_column].astype(str).tolist()
    mask_phase = (
        "packed_final_refit_banks"
        if final_refit
        else "packed_fixed_partition_banks"
    )
    train_dataset = DeterministicMaskedExpressionDataset(
        training_expression,
        fitting_ids,
        normalization="log1p_tpm",
        mask_ratio=args.mask_ratio,
        mask_token=args.mask_token,
        seed=args.seed,
        phase=mask_phase,
        fixed_masks=False,
    )
    sampler = DeterministicBudgetBatchSampler(
        fitting_ids,
        batch_size=args.batch_size,
        max_updates=max_updates,
        seed=stable_seed(args.seed, "packed_fixed_partition_sampler"),
        sampling_mode=sampling_mode,
        organs=training_frame[args.organ_column].astype(str).tolist(),
        group_ids=training_frame[args.group_column].astype(str).tolist(),
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
    validation_loader = None
    validation_weights = None
    if not final_refit:
        validation_dataset = FixedGeneMaskDataset(
            validation_expression,
            validation_ids,
            mask_indices=score_indices,
            mask_token=args.mask_token,
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
    exposure_frame = build_exposure_frame(
        training_frame,
        sampler,
        sample_id_column=args.sample_id_column,
        organ_column=args.organ_column,
        group_column=args.group_column,
    )
    exposure_summary = summarize_exposures(exposure_frame)
    if final_refit and not args.smoke_only and exposure_summary["zero_exposure_samples"]:
        raise ValueError("final refit schedule leaves one or more fitting rows unexposed")
    model = PackedExpertBanks(
        trunk,
        axis_k,
        adapter_dim=args.adapter_dim,
        seed=args.seed,
        axis_expert_keys=axis_expert_keys,
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
    exposure_counts: dict[str, list[int]] = {}
    exposure_deviations: dict[str, float] = {}
    fallback_draw_counts: dict[str, int] = {}
    for axis in axes:
        scheduled_indices = np.asarray(
            sampler.flat_indices[: budgets[axis] * args.batch_size], dtype=np.int64
        )
        scheduled_labels = labels_train[axis][scheduled_indices]
        active_labels = scheduled_labels[scheduled_labels >= 0]
        exposure_counts[axis] = np.bincount(
            active_labels, minlength=axis_k[axis]
        ).tolist()
        exposure_deviations[axis] = float(
            np.max(
                np.abs(
                    np.asarray(exposure_counts[axis], dtype=np.float64)
                    - target_exposures[axis]
                )
                / target_exposures[axis]
            )
        )
        fallback_draw_counts[axis] = int(np.sum(scheduled_labels < 0))
        for update in range(budgets[axis]):
            batch_indices = np.asarray(
                [int(item[0]) for item in sampler.batches[update]], dtype=np.int64
            )
            if not np.any(labels_train[axis][batch_indices] >= 0):
                raise ValueError(
                    f"axis {axis!r} has an all-fallback scheduled batch at update {update + 1}"
                )
    maximum_exposure_deviation = float(
        getattr(args, "maximum_exposure_fractional_deviation", 0.05)
    )
    if not 0 <= maximum_exposure_deviation < 1:
        raise ValueError("maximum exposure fractional deviation must lie in [0, 1)")
    if not args.smoke_only:
        failed_exposures = {
            axis: value
            for axis, value in exposure_deviations.items()
            if value > maximum_exposure_deviation
        }
        if failed_exposures:
            raise ValueError(
                "scheduled expert exposures exceed the frozen deviation limit: "
                f"{failed_exposures}"
            )
    exposure_path = output_dir / "fit_exposures.parquet"
    temporary_exposure_path = exposure_path.with_suffix(".parquet.tmp")
    exposure_frame.to_parquet(temporary_exposure_path, index=False)
    os.replace(temporary_exposure_path, exposure_path)
    flat_indices = np.asarray(sampler.flat_indices, dtype=np.int64)
    draw_numbers = np.arange(len(flat_indices), dtype=np.int64)
    fitting_ids_array = np.asarray(fitting_ids, dtype=str)
    schedule_frame = pd.DataFrame({
        "draw_number": draw_numbers,
        "update": draw_numbers // int(args.batch_size) + 1,
        "batch_position": draw_numbers % int(args.batch_size),
        "sample_index": flat_indices,
        "sample_id": fitting_ids_array[flat_indices],
        "organ": training_frame[args.organ_column].astype(str).to_numpy()[flat_indices],
        "series_group_id": training_frame[args.group_column]
        .astype(str)
        .to_numpy()[flat_indices],
    })
    schedule_frame["mask_seed_u64_hex"] = [
        f"{stable_seed(args.seed, 'mask', mask_phase, sample_id, int(draw)):016x}"
        for draw, sample_id in zip(
            schedule_frame["draw_number"], schedule_frame["sample_id"]
        )
    ]
    schedule_path = output_dir / "fit_schedule.parquet"
    temporary_schedule_path = schedule_path.with_suffix(".parquet.tmp")
    schedule_frame.to_parquet(temporary_schedule_path, index=False)
    os.replace(temporary_schedule_path, schedule_path)
    exposure_report = {
        "schema_version": 1,
        "status": "complete",
        "final_refit": final_refit,
        "sampling_mode": sampling_mode,
        "mask_phase": mask_phase,
        "ordered_schedule_rows": int(len(schedule_frame)),
        "training_seed": int(args.seed),
        "code_commit": code_commit,
        "test_accessed": False,
        "external_data_accessed": False,
        "internal_efficacy_scoring": False if final_refit else True,
        "summary": exposure_summary,
        "axis_exposure_counts": exposure_counts,
        "axis_exposure_fractional_deviations": exposure_deviations,
        "fallback_draw_counts": fallback_draw_counts,
        "all_fit_rows_exposed": exposure_summary["zero_exposure_samples"] == 0,
        "artifacts": {
            "fit_exposures_sha256": sha256_file(exposure_path),
            "fit_schedule_sha256": sha256_file(schedule_path),
            "ordered_schedule_rows": int(len(schedule_frame)),
        },
    }
    _atomic_json(output_dir / "fit_exposure_report.json", exposure_report)
    common_hashes = {
        "protocol_sha256": sha256_file(args.protocol),
        "pooled_checkpoint_sha256": sha256_file(args.pooled_checkpoint),
        "expression_sha256": sha256_file(args.expression_parquet),
        "expression_metadata_sha256": sha256_file(args.expression_metadata),
        "manifest_sha256": sha256_file(args.manifest),
        "partition_manifest_sha256": sha256_file(args.partition_manifest),
        "partition_report_sha256": sha256_file(args.partition_report),
        "axis_definitions_sha256": sha256_file(args.axis_definitions),
        "train_sample_ids_sha256": sha256_lines(train_ids),
        "calibration_sample_ids_sha256": sha256_lines(validation_ids),
        "fitting_sample_ids_sha256": sha256_lines(fitting_ids),
        "gene_order_sha256": sha256_lines(expression_info.gene_columns),
        "score_gene_indices_sha256": sha256_lines([str(value) for value in score_indices]),
        "fit_exposures_sha256": sha256_file(exposure_path),
        "fit_schedule_sha256": sha256_file(schedule_path),
        "fit_exposure_report_sha256": sha256_file(
            output_dir / "fit_exposure_report.json"
        ),
    }
    if common_hashes["partition_manifest_sha256"] != partition_report["hashes"]["partition_manifest_sha256"]:
        raise ValueError("partition manifest is not pinned by partition report")
    top_config = {
        "axes": axes,
        "axis_k": axis_k,
        "bank_update_budgets": budgets,
        "max_updates": max_updates,
        "target_exposures_per_expert": target_exposures,
        "fallback_label": -1 if allow_fallback_label else None,
        "fallback_draw_counts": fallback_draw_counts,
        "exposure_fractional_deviations": exposure_deviations,
        "maximum_exposure_fractional_deviation": maximum_exposure_deviation,
        "axis_expert_keys": axis_expert_keys,
        "batch_size": args.batch_size,
        "validation_batch_size": args.validation_batch_size,
        "adapter_dim": args.adapter_dim,
        "mask_ratio": args.mask_ratio,
        "mask_token": args.mask_token,
        "normalization": "log1p_tpm",
        "score_gene_count": int(len(score_indices)),
        "learning_rate": args.learning_rate,
        "weight_decay": args.weight_decay,
        "optimizer": "AdamW",
        "sampling_mode": sampling_mode,
        "mask_phase": mask_phase,
        "ordered_schedule_rows": int(len(schedule_frame)),
        "sampling": (
            "one shared deterministic organ-then-sample balanced schedule"
            if sampling_mode == "organ_sample_balanced"
            else f"one shared deterministic {sampling_mode} schedule"
        ),
        "loss_normalization": "sum active-row losses divided by common full batch size",
        "checkpoint_policy": "predetermined_final_update_per_bank",
        "scheduler": "CosineAnnealingLR",
        "final_refit": final_refit,
        "calibration_evaluation_performed": not final_refit,
        "router_present": False,
        "use_amp": use_amp,
    }
    top_metadata = {
        "schema_version": 1,
        "status": "running",
        "research_stage": getattr(
            args, "research_stage", "stage2_competitive_followup"
        ),
        "experiment": getattr(
            args, "experiment", "packed_hard_fixed_partition_expert_banks"
        ),
        "training_seed": int(args.seed),
        "code_commit": code_commit,
        "test_accessed": False,
        "external_data_accessed": False,
        "mechanical_only": bool(args.smoke_only),
        "internal_efficacy_scoring": False if final_refit else True,
        "fitting_roles": (
            [str(args.train_split), str(args.validation_split)]
            if final_refit
            else [str(args.train_split)]
        ),
        "config": top_config,
        "counts": {
            "train": len(train_ids),
            "calibration": len(validation_ids),
            "fit": len(fitting_ids),
            "genes": len(expression_info.gene_columns),
            "score_genes": len(score_indices),
        },
        "exposure_counts": exposure_counts,
        "fit_exposure_summary": exposure_summary,
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
                valid = labels >= 0
                row = torch.arange(len(labels), device=device)[valid]
                per_row = _masked_row_mse(
                    predictions[row, labels[valid]], truth[valid], mask[valid]
                )
                losses[axis] = per_row.sum() / args.batch_size
            total_loss = torch.stack(list(losses.values())).sum()
        if not all(bool(torch.isfinite(value).item()) for value in losses.values()):
            raise FloatingPointError(f"non-finite bank loss at update {update}")
        if not bool(torch.isfinite(total_loss).item()):
            raise FloatingPointError(f"non-finite total loss at update {update}")
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
        metrics = None
        if not final_refit:
            if validation_loader is None or validation_weights is None:
                raise AssertionError("calibration evaluator was not initialized")
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
                fallback_label=(-1 if allow_fallback_label else None),
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
        expert_state_hashes = [
            _tensor_state_sha256(dict(expert.state_dict()))
            for expert in model.banks[axis]
        ]
        if not all(
            bool(torch.isfinite(value).all().item())
            for value in expert_state.values()
        ):
            raise FloatingPointError(f"axis {axis!r} contains non-finite final weights")
        bank_config = {
            "axis": axis,
            "num_experts": axis_k[axis],
            "adapter_dim": args.adapter_dim,
            "router_trainable": False,
            "final_update": budgets[axis],
            "exposures_per_expert_target": target_exposures[axis],
            "realized_exposure_counts": exposure_counts[axis],
            "maximum_realized_exposure_fractional_deviation": exposure_deviations[
                axis
            ],
            "fallback_label": -1 if np.any(labels_train[axis] < 0) else None,
            "fallback_draw_count": fallback_draw_counts[axis],
            "expert_initialization_keys": axis_expert_keys.get(axis),
            "batch_size": args.batch_size,
            "mask_ratio": args.mask_ratio,
            "mask_token": args.mask_token,
            "normalization": "log1p_tpm",
            "score_gene_count": int(len(score_indices)),
            "checkpoint_policy": "predetermined_final_update",
            "scheduler": "CosineAnnealingLR",
            "packed_shared_trunk": True,
            "final_refit": final_refit,
            "calibration_evaluation_performed": not final_refit,
            "loss_normalization": "sum active-row losses divided by common full batch size",
        }
        checkpoint_path = bank_dir / "final_experts.pt"
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
            checkpoint_path,
        )
        roundtrip = torch.load(
            checkpoint_path, map_location="cpu", weights_only=False
        )
        roundtrip_state = roundtrip.get("expert_state_dict")
        if not isinstance(roundtrip_state, dict):
            raise RuntimeError(f"axis {axis!r} checkpoint round-trip lacks expert state")
        if not all(
            isinstance(value, torch.Tensor) and bool(torch.isfinite(value).all().item())
            for value in roundtrip_state.values()
        ):
            raise FloatingPointError(
                f"axis {axis!r} checkpoint round-trip contains non-finite weights"
            )
        if _tensor_state_sha256(roundtrip_state) != _tensor_state_sha256(expert_state):
            raise RuntimeError(f"axis {axis!r} checkpoint round-trip changed expert state")
        bank_metadata = {
            "schema_version": 1,
            "status": "complete",
            "research_stage": getattr(
                args, "research_stage", "stage2_competitive_followup"
            ),
            "experiment": getattr(
                args, "bank_experiment", "hard_fixed_partition_residual_experts"
            ),
            "axis": axis,
            "training_seed": int(args.seed),
            "code_commit": code_commit,
            "test_accessed": False,
            "external_data_accessed": False,
            "mechanical_only": bool(args.smoke_only),
            "internal_efficacy_scoring": False if final_refit else True,
            "config": bank_config,
            "hashes": {
                **common_hashes,
                "resolved_config_sha256": sha256_json(bank_config),
            },
            "artifacts": {
                "final_experts_sha256": sha256_file(checkpoint_path),
                "expert_state_sha256": expert_state_hashes,
                "all_final_tensors_finite": True,
                "checkpoint_roundtrip_verified": True,
            },
        }
        if metrics is not None:
            bank_metadata["calibration_metrics"] = metrics
            bank_metadata["artifacts"]["calibration_scores_sha256"] = sha256_file(
                bank_dir / "calibration_scores.npz"
            )
        _atomic_json(bank_dir / "run_metadata.json", bank_metadata)
        (bank_dir / "COMPLETE").touch()
        result = {
            "final_update": budgets[axis],
            "path": str(bank_dir),
        }
        if metrics is not None:
            result["calibration_metrics"] = metrics
        bank_results[axis] = result
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
    parser.add_argument(
        "--axis-update-budget",
        action="append",
        help="Per-axis scheduled updates as AXIS=INTEGER; required for fallback axes.",
    )
    parser.add_argument(
        "--axis-target-exposures",
        action="append",
        help="Per-axis active exposure target as AXIS=INTEGER.",
    )
    parser.add_argument(
        "--axis-expert-key",
        action="append",
        help="Semantic initialization keys as AXIS=KEY0,KEY1,...",
    )
    parser.add_argument(
        "--allow-fallback-label",
        action="store_true",
        help="Permit label -1, which receives pooled fallback and zero adapter loss.",
    )
    parser.add_argument(
        "--require-calibration-coverage",
        action="store_true",
        help="Require every active expert label to occur in calibration; K45 contract only.",
    )
    parser.add_argument(
        "--final-refit",
        action="store_true",
        help=(
            "Merge the selected train and calibration rows for fixed-protocol fitting "
            "and emit no internal efficacy scores."
        ),
    )
    parser.add_argument(
        "--sampling-mode", choices=SAMPLING_MODES, default="natural"
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--research-stage", default="stage2_competitive_followup")
    parser.add_argument(
        "--experiment", default="packed_hard_fixed_partition_expert_banks"
    )
    parser.add_argument(
        "--bank-experiment", default="hard_fixed_partition_residual_experts"
    )
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--code-commit", default="unknown")
    parser.add_argument("--train-split", default="train")
    parser.add_argument("--validation-split", default="calibration")
    parser.add_argument("--train-filter-column", default="balanced_train")
    parser.add_argument("--sample-id-column", default="sample_id")
    parser.add_argument("--organ-column", default="organ")
    parser.add_argument("--group-column", default="series_group_id")
    parser.add_argument("--adapter-dim", type=int, default=64)
    parser.add_argument("--exposures-per-expert", type=int, default=2400)
    parser.add_argument(
        "--maximum-exposure-fractional-deviation", type=float, default=0.05
    )
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
