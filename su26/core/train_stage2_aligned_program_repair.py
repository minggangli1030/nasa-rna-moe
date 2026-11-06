#!/usr/bin/env python3
"""Train the frozen Stage 2 coefficient-supervised aligned-program repair.

The organ-private path is trained first and frozen. Training-only residuals are
then projected into the exact fixed decoder, and the existing shared head is
supervised on standardized coefficient targets. Calibration is donor/study
disjoint and no external data are accepted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader, Dataset


CORE = Path(__file__).resolve().parent
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

from stage2_program_model import (  # noqa: E402
    AlignedProgramCondition,
    trainable_parameter_count,
)
from train_fixed_partition_moe import _resolve_device  # noqa: E402
from train_latent_moe import load_frozen_trunk  # noqa: E402
from phase_guards import PhaseGuard, tensor_state_sha256  # noqa: E402
from train_manifest import (  # noqa: E402
    DeterministicBudgetBatchSampler,
    balanced_validation_weights,
    build_exposure_frame,
    load_expression_rows,
    read_manifest,
    seed_data_worker,
    seed_everything,
    select_manifest_rows,
    sha256_file,
    sha256_json,
    sha256_lines,
    stable_seed,
    summarize_exposures,
    validate_expression_metadata,
)


SEEDS = (17, 42, 101)
CONDITIONS = (
    "organ_private_phase1",
    "organ_private_extended",
    "generic_capacity_extended",
    "coefficient_supervised_plus_frozen_private",
    "random_coefficient_supervised_plus_frozen_private",
)
COEFFICIENT_CONDITION = "coefficient_supervised_plus_frozen_private"


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


class ScoreGeneMaskDataset(Dataset):
    """Mask deterministic subsets of the frozen score genes only."""

    def __init__(
        self,
        expression: np.ndarray,
        sample_ids: Sequence[str],
        *,
        score_gene_indices: np.ndarray,
        mask_ratio: float,
        mask_token: float,
        seed: int,
        phase: str,
        fixed_all_score_genes: bool,
    ):
        values = np.asarray(expression, dtype=np.float32)
        indices = np.asarray(score_gene_indices, dtype=np.int64)
        if values.ndim != 2 or values.shape[0] != len(sample_ids):
            raise ValueError("expression must align with sample IDs")
        if np.any(values < 0):
            raise ValueError("expected nonnegative TPM expression")
        if indices.ndim != 1 or not len(indices) or len(np.unique(indices)) != len(indices):
            raise ValueError("score-gene indices must be unique and nonempty")
        if indices.min() < 0 or indices.max() >= values.shape[1]:
            raise ValueError("score-gene index is out of range")
        if not 0 < mask_ratio <= 1:
            raise ValueError("mask ratio must lie in (0, 1]")
        self.expression = np.log1p(values).astype(np.float32, copy=False)
        self.sample_ids = tuple(str(value) for value in sample_ids)
        self.score_gene_indices = indices
        self.mask_count = (
            len(indices)
            if fixed_all_score_genes
            else max(1, int(len(indices) * mask_ratio))
        )
        self.mask_token = float(mask_token)
        self.seed = int(seed)
        self.phase = str(phase)
        self.fixed_all_score_genes = bool(fixed_all_score_genes)

    def __len__(self) -> int:
        return len(self.sample_ids)

    def __getitem__(self, key):
        if isinstance(key, (tuple, list)):
            index, draw_number = int(key[0]), int(key[1])
        else:
            index, draw_number = int(key), 0
        truth = self.expression[index]
        if self.fixed_all_score_genes:
            local_mask = np.arange(len(self.score_gene_indices), dtype=np.int64)
        else:
            rng = np.random.default_rng(
                stable_seed(
                    self.seed,
                    "score_gene_mask",
                    self.phase,
                    self.sample_ids[index],
                    draw_number,
                )
            )
            local_mask = np.sort(
                rng.choice(
                    len(self.score_gene_indices),
                    self.mask_count,
                    replace=False,
                ).astype(np.int64)
            )
        global_mask = self.score_gene_indices[local_mask]
        masked = truth.copy()
        masked[global_mask] = self.mask_token
        return (
            torch.from_numpy(masked),
            torch.from_numpy(truth[self.score_gene_indices].copy()),
            torch.from_numpy(local_mask),
        )


def _masked_score_mse(
    prediction: torch.Tensor, truth: torch.Tensor, local_mask: torch.Tensor
) -> torch.Tensor:
    return (
        prediction.gather(1, local_mask) - truth.gather(1, local_mask)
    ).square().mean(dim=1)


def _load_basis(
    path: Path,
    *,
    expected_sha256: str,
    gene_names: list[str],
    score_indices: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, dict[str, str]]:
    if sha256_file(path) != expected_sha256:
        raise ValueError("program-basis bundle SHA256 mismatch")
    with np.load(path, allow_pickle=False) as archive:
        required = {
            "gene_names",
            "weighted_scale",
            "program_components",
            "random_components",
        }
        if set(archive.files) != required:
            raise ValueError("program-basis bundle fields differ from protocol")
        basis_genes = archive["gene_names"].astype(str).tolist()
        scale = archive["weighted_scale"].astype(np.float32)
        program = archive["program_components"].astype(np.float32)
        random = archive["random_components"].astype(np.float32)
    expected_genes = np.asarray(gene_names)[score_indices].astype(str).tolist()
    if basis_genes != expected_genes:
        raise ValueError("program basis gene order differs from score genes")
    if (
        program.shape != random.shape
        or program.shape[1] != len(score_indices)
        or scale.shape != (len(score_indices),)
    ):
        raise ValueError("program-basis bundle shapes are inconsistent")
    program_decoder = program * scale[None, :]
    random_decoder = random * scale[None, :]
    hashes = {
        "program_decoder_sha256": hashlib.sha256(
            np.ascontiguousarray(program_decoder).tobytes()
        ).hexdigest(),
        "random_decoder_sha256": hashlib.sha256(
            np.ascontiguousarray(random_decoder).tobytes()
        ).hexdigest(),
    }
    return program_decoder, random_decoder, hashes


def _make_condition(
    *,
    hidden_dim: int,
    score_indices: np.ndarray,
    decoder: np.ndarray | None,
    program_head_dim: int,
    private_adapter_dim: int | None,
    experts: int,
) -> AlignedProgramCondition:
    return AlignedProgramCondition(
        hidden_dim=hidden_dim,
        score_gene_indices=torch.as_tensor(score_indices),
        program_decoder=None if decoder is None else torch.as_tensor(decoder),
        program_head_dim=program_head_dim,
        private_adapter_dim=private_adapter_dim,
        num_private_experts=experts,
    )


def _labels_for_condition(name: str, organ_labels: torch.Tensor) -> torch.Tensor:
    if name == "generic_capacity_extended":
        return torch.zeros_like(organ_labels)
    if name in CONDITIONS:
        return organ_labels
    raise KeyError(name)


def _evaluate(
    *,
    trunk: nn.Module,
    conditions: nn.ModuleDict,
    loader: DataLoader,
    organ_labels: np.ndarray,
    sample_weights: np.ndarray,
    device: torch.device,
    mask_token: float,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    score_indices = conditions[CONDITIONS[0]].score_gene_indices
    rows = {name: [] for name in CONDITIONS}
    pooled_rows = []
    coefficients = []
    offset = 0
    trunk.eval()
    conditions.eval()
    with torch.no_grad():
        for masked, truth_score, local_mask in loader:
            masked = masked.to(device)
            truth_score = truth_score.to(device)
            local_mask = local_mask.to(device)
            hidden = trunk.encode(masked)
            pooled_score = trunk.decode(hidden).index_select(1, score_indices)
            pooled_rows.append(
                _masked_score_mse(pooled_score, truth_score, local_mask).cpu().numpy()
            )
            batch_organs = torch.as_tensor(
                organ_labels[offset : offset + len(masked)],
                device=device,
                dtype=torch.long,
            )
            for name in CONDITIONS:
                residual, coefficient = conditions[name](
                    hidden,
                    masked,
                    _labels_for_condition(name, batch_organs),
                )
                prediction = pooled_score + residual
                rows[name].append(
                    _masked_score_mse(
                        prediction, truth_score, local_mask
                    ).cpu().numpy()
                )
                if name == COEFFICIENT_CONDITION:
                    if coefficient is None:
                        raise AssertionError("coefficient condition returned no coefficients")
                    coefficients.append(coefficient.cpu().numpy())
            offset += len(masked)
    if offset != len(organ_labels):
        raise AssertionError("calibration labels do not align with loader")
    arrays = {
        "pooled_mse": np.concatenate(pooled_rows).astype(np.float64),
        **{
            f"{name}_mse": np.concatenate(rows[name]).astype(np.float64)
            for name in CONDITIONS
        },
        "program_coefficients": np.concatenate(coefficients).astype(np.float32),
    }
    metrics: dict[str, Any] = {
        "pooled_mse": float(np.dot(arrays["pooled_mse"], sample_weights)),
        "conditions": {},
    }
    for name in CONDITIONS:
        mse = float(np.dot(arrays[f"{name}_mse"], sample_weights))
        metrics["conditions"][name] = {
            "mse": mse,
            "relative_mse_reduction_vs_pooled": (
                metrics["pooled_mse"] - mse
            ) / metrics["pooled_mse"],
        }
    return metrics, arrays


def _hidden_summary(
    hidden: torch.Tensor, masked_expression: torch.Tensor, mask_token: float
) -> torch.Tensor:
    observed = masked_expression.ne(mask_token)
    weights = observed.to(dtype=hidden.dtype)
    return (
        (hidden * weights.unsqueeze(-1)).sum(dim=1)
        / weights.sum(dim=1, keepdim=True).clamp_min(1.0)
    )


def _coefficient_targets(
    residual: torch.Tensor,
    local_mask: torch.Tensor,
    decoder: torch.Tensor,
    *,
    ridge: float,
) -> tuple[torch.Tensor, torch.Tensor]:
    batch, masked_genes = local_mask.shape
    components = decoder.shape[0]
    selected_decoder = decoder.unsqueeze(0).expand(batch, -1, -1).gather(
        2, local_mask.unsqueeze(1).expand(-1, components, -1)
    )
    selected_residual = residual.gather(1, local_mask)
    gram = torch.bmm(selected_decoder, selected_decoder.transpose(1, 2))
    identity = torch.eye(components, device=decoder.device).unsqueeze(0)
    right = torch.bmm(
        selected_decoder, selected_residual.unsqueeze(-1)
    ).squeeze(-1)
    target = torch.linalg.solve(gram + ridge * identity, right)
    return target, gram / float(masked_genes)


def _copy_private(
    source: AlignedProgramCondition, target: AlignedProgramCondition
) -> None:
    if source.private is None or target.private is None:
        raise ValueError("private path is required")
    target.private.load_state_dict(source.private.state_dict())


def _freeze_private(condition: AlignedProgramCondition) -> None:
    if condition.private is None:
        raise ValueError("private path is required")
    for parameter in condition.private.parameters():
        parameter.requires_grad_(False)


def train(args: argparse.Namespace) -> dict[str, Any]:
    if args.seed not in SEEDS:
        raise ValueError(f"seed must be one of {SEEDS}")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    protocol_path = Path(args.protocol)
    if sha256_file(protocol_path) != args.expected_protocol_sha256:
        raise ValueError("aligned-program protocol SHA256 mismatch")
    protocol = json.loads(protocol_path.read_text())
    if protocol.get("status") != "frozen_before_repair_training":
        raise ValueError("aligned-program repair protocol is not frozen")
    if protocol.get("firewalls", {}).get("archs4_access") is not False:
        raise ValueError("protocol does not prohibit ARCHS4 access")
    seed_everything(args.seed, deterministic=True)
    device = _resolve_device(args.device)

    input_paths = {
        "expression_sha256": Path(args.expression_parquet),
        "expression_metadata_sha256": Path(args.expression_metadata),
        "manifest_sha256": Path(args.manifest),
        "axis_definitions_sha256": Path(args.axis_definitions),
        "basis_bundle_sha256": Path(args.basis_bundle),
    }
    for key, path in input_paths.items():
        if sha256_file(path) != protocol["inputs"][key]:
            raise ValueError(f"{key} differs from frozen protocol")
    expected_checkpoint = protocol["inputs"]["pooled_checkpoint_sha256"][str(args.seed)]
    if sha256_file(args.pooled_checkpoint) != expected_checkpoint:
        raise ValueError("pooled checkpoint differs from frozen seed input")

    trunk, checkpoint_config, checkpoint = load_frozen_trunk(
        args.pooled_checkpoint, device
    )
    manifest = read_manifest(args.manifest)
    selection = select_manifest_rows(
        manifest,
        role="pooled",
        train_split="train",
        validation_split="calibration",
        train_filter_column="balanced_train",
    )
    train_ids = selection.train["sample_id"].astype(str).tolist()
    validation_ids = selection.validation["sample_id"].astype(str).tolist()
    expression, expression_info = load_expression_rows(
        args.expression_parquet, train_ids + validation_ids
    )
    validate_expression_metadata(
        args.expression_parquet,
        expression_info.gene_columns,
        metadata_path=args.expression_metadata,
    )
    if list(expression_info.gene_columns) != list(checkpoint_config["gene_list"]):
        raise ValueError("expression gene order differs from pooled checkpoint")
    if not np.isclose(float(checkpoint_config["mask_token"]), args.mask_token):
        raise ValueError("mask token differs from pooled checkpoint")
    with np.load(args.axis_definitions, allow_pickle=False) as archive:
        score_indices = archive["score_gene_indices"].astype(np.int64)
        axis_genes = archive["gene_names"].astype(str).tolist()
    if axis_genes != list(expression_info.gene_columns):
        raise ValueError("axis-definition gene order differs from expression")
    partitions = pd.read_parquet(args.manifest).set_index("sample_id")
    ordered = partitions.loc[train_ids + validation_ids]
    for axis in ("organ_k8", "random_k8_p17"):
        if axis not in ordered or ordered[axis].isna().any():
            raise ValueError(f"manifest lacks complete {axis} labels")
        labels = np.unique(ordered[axis].astype(int))
        if not np.array_equal(labels, np.arange(8)):
            raise ValueError(f"{axis} labels are not contiguous K8")
    organ_all = ordered["organ_k8"].to_numpy(dtype=np.int64)
    random_all = ordered["random_k8_p17"].to_numpy(dtype=np.int64)
    train_count = len(train_ids)
    train_organ, validation_organ = organ_all[:train_count], organ_all[train_count:]
    train_random, validation_random = random_all[:train_count], random_all[train_count:]

    program_decoder, random_decoder, decoder_hashes = _load_basis(
        Path(args.basis_bundle),
        expected_sha256=protocol["inputs"]["basis_bundle_sha256"],
        gene_names=list(expression_info.gene_columns),
        score_indices=score_indices,
    )
    if decoder_hashes != protocol["inputs"]["decoder_sha256"]:
        raise ValueError("decoded program matrices differ from frozen protocol")
    config = protocol["training"]
    phase1_updates = int(
        args.smoke_updates if args.smoke_only else config["phase1_private_updates"]
    )
    phase2_updates = int(
        args.smoke_updates if args.smoke_only else config["phase2_shared_updates"]
    )
    generator = torch.Generator().manual_seed(
        stable_seed(args.seed, "stage2_aligned_program_repair_loader") % (2**63 - 1)
    )

    def make_training_loader(phase: str, updates: int):
        dataset = ScoreGeneMaskDataset(
            expression[:train_count],
            train_ids,
            score_gene_indices=score_indices,
            mask_ratio=float(config["mask_ratio"]),
            mask_token=float(config["mask_token"]),
            seed=args.seed,
            phase=phase,
            fixed_all_score_genes=False,
        )
        sampler = DeterministicBudgetBatchSampler(
            train_ids,
            batch_size=int(config["batch_size"]),
            max_updates=updates,
            seed=stable_seed(args.seed, phase, "sampler"),
            sampling_mode="organ_sample_balanced",
            organs=selection.train["organ"].astype(str).tolist(),
            group_ids=selection.train["series_group_id"].astype(str).tolist(),
        )
        loader = DataLoader(
            dataset,
            batch_sampler=sampler,
            num_workers=args.num_workers,
            worker_init_fn=seed_data_worker,
            generator=generator,
        )
        return loader, sampler

    phase1_loader, phase1_sampler = make_training_loader(
        "stage2_aligned_program_repair_private", phase1_updates
    )
    phase2_loader, phase2_sampler = make_training_loader(
        "stage2_aligned_program_repair_shared", phase2_updates
    )
    validation_dataset = ScoreGeneMaskDataset(
        expression[train_count:],
        validation_ids,
        score_gene_indices=score_indices,
        mask_ratio=1.0,
        mask_token=float(config["mask_token"]),
        seed=int(protocol["evaluation"]["mask_seed"]),
        phase="stage2_aligned_program_calibration",
        fixed_all_score_genes=True,
    )
    validation_loader = DataLoader(
        validation_dataset,
        batch_size=int(config["validation_batch_size"]),
        shuffle=False,
        num_workers=args.num_workers,
        worker_init_fn=seed_data_worker,
        generator=generator,
    )

    hidden_dim = int(trunk.gene_embedding.embedding_dim)
    make = lambda decoder, private_dim, experts: _make_condition(
        hidden_dim=hidden_dim,
        score_indices=score_indices,
        decoder=decoder,
        program_head_dim=int(config["program_head_dim"]),
        private_adapter_dim=private_dim,
        experts=experts,
    )
    with torch.random.fork_rng(devices=[], enabled=True):
        torch.manual_seed(
            stable_seed(args.seed, "aligned_program_repair_conditions") % (2**63 - 1)
        )
        conditions = nn.ModuleDict({
            "organ_private_phase1": make(
                None, int(config["private_adapter_dim"]), 8
            ),
            "organ_private_extended": make(
                None, int(config["private_adapter_dim"]), 8
            ),
            "generic_capacity_extended": make(
                None, int(config["generic_adapter_dim"]), 1
            ),
            "coefficient_supervised_plus_frozen_private": make(
                program_decoder, int(config["private_adapter_dim"]), 8
            ),
            "random_coefficient_supervised_plus_frozen_private": make(
                random_decoder, int(config["private_adapter_dim"]), 8
            ),
        }).to(device)
    conditions[
        "random_coefficient_supervised_plus_frozen_private"
    ].program.coefficient_head.load_state_dict(
        conditions[
            "coefficient_supervised_plus_frozen_private"
        ].program.coefficient_head.state_dict()
    )
    parameter_counts = {
        name: trainable_parameter_count(conditions[name]) for name in CONDITIONS
    }
    matched = (
        parameter_counts["generic_capacity_extended"]
        / parameter_counts["coefficient_supervised_plus_frozen_private"]
    )
    if not 0.98 <= matched <= 1.02:
        raise ValueError("generic capacity control is not within 2% of shared+private")
    phase1_names = ("organ_private_extended", "generic_capacity_extended")
    optimizers = {
        name: AdamW(
            conditions[name].parameters(),
            lr=float(config["learning_rate"]),
            weight_decay=float(config["weight_decay"]),
        )
        for name in phase1_names
    }
    phase1_modules = {name: conditions[name] for name in phase1_names}
    phase1_guard = PhaseGuard(
        "phase1_private",
        phase1_modules,
        optimizers,
    )
    schedulers = {
        name: CosineAnnealingLR(optimizers[name], T_max=phase1_updates)
        for name in phase1_names
    }
    use_amp = bool(args.use_amp and device.type == "cuda")
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    phase1_exposure = build_exposure_frame(selection.train, phase1_sampler)
    phase2_exposure = build_exposure_frame(selection.train, phase2_sampler)
    phase1_exposure_path = output_dir / "phase1_fit_exposures.parquet"
    phase2_exposure_path = output_dir / "phase2_fit_exposures.parquet"
    phase1_exposure.to_parquet(phase1_exposure_path, index=False)
    phase2_exposure.to_parquet(phase2_exposure_path, index=False)
    metadata: dict[str, Any] = {
        "schema_version": 2,
        "status": "running",
        "research_stage": "stage2_aligned_program_coefficient_supervision_repair",
        "seed": args.seed,
        "code_commit": args.code_commit,
        "mechanical_only": bool(args.smoke_only),
        "development_only": True,
        "external_data_accessed": False,
        "archs4_accessed": False,
        "best_seed_selection_allowed": False,
        "counts": {
            "train_samples": train_count,
            "calibration_samples": len(validation_ids),
            "genes": len(expression_info.gene_columns),
            "score_genes": len(score_indices),
            "components": int(program_decoder.shape[0]),
            "conditions": len(CONDITIONS),
            "phase1_updates": phase1_updates,
            "phase2_updates": phase2_updates,
            "total_updates_per_extended_control": phase1_updates + phase2_updates,
        },
        "parameter_counts": parameter_counts,
        "hashes": {
            "protocol_sha256": sha256_file(protocol_path),
            **{key: sha256_file(path) for key, path in input_paths.items()},
            "pooled_checkpoint_sha256": expected_checkpoint,
            "train_sample_ids_sha256": sha256_lines(train_ids),
            "calibration_sample_ids_sha256": sha256_lines(validation_ids),
            "phase1_fit_exposures_sha256": sha256_file(phase1_exposure_path),
            "phase2_fit_exposures_sha256": sha256_file(phase2_exposure_path),
            **decoder_hashes,
        },
        "config": {**config, "use_amp": use_amp},
        "phase1_exposure_summary": summarize_exposures(phase1_exposure),
        "phase2_exposure_summary": summarize_exposures(phase2_exposure),
    }
    metadata["hashes"]["resolved_config_sha256"] = sha256_json(metadata["config"])
    _atomic_json(output_dir / "run_metadata.json", metadata)

    histories = {"phase1": [], "phase2": []}
    start = time.time()
    trunk.eval()
    conditions.train()
    score_tensor = conditions[CONDITIONS[0]].score_gene_indices
    phase1_guard_update = min(5, phase1_updates)
    phase1_early_audit = None
    for update, (masked, truth_score, local_mask) in enumerate(phase1_loader, start=1):
        for optimizer in optimizers.values():
            optimizer.zero_grad(set_to_none=True)
        masked = masked.to(device)
        truth_score = truth_score.to(device)
        local_mask = local_mask.to(device)
        batch_indices = np.asarray(
            [int(item[0]) for item in phase1_sampler.batches[update - 1]],
            dtype=np.int64,
        )
        batch_organs = torch.as_tensor(
            train_organ[batch_indices], device=device, dtype=torch.long
        )
        with torch.autocast(
            device_type="cuda", dtype=torch.float16, enabled=use_amp
        ):
            with torch.no_grad():
                hidden = trunk.encode(masked)
                pooled_score = trunk.decode(hidden).index_select(1, score_tensor)
            losses = {}
            for name in phase1_names:
                residual, _ = conditions[name](
                    hidden,
                    masked,
                    _labels_for_condition(name, batch_organs),
                )
                losses[name] = _masked_score_mse(
                    pooled_score + residual, truth_score, local_mask
                ).mean()
            total_loss = torch.stack(list(losses.values())).sum()
        if not bool(torch.isfinite(total_loss).item()):
            raise FloatingPointError(f"nonfinite training loss at update {update}")
        scaler.scale(total_loss).backward()
        for name in phase1_names:
            scaler.step(optimizers[name])
            schedulers[name].step()
        scaler.update()
        if update == phase1_guard_update:
            phase1_early_audit = phase1_guard.movement(
                checkpoint=f"update_{update}"
            )
        if (
            update == 1
            or update % int(config["log_interval"]) == 0
            or update == phase1_updates
        ):
            summary = []
            row = {"update": update}
            for name, loss in losses.items():
                value = float(loss.detach().cpu())
                row[name] = value
                summary.append(f"{name}={value:.6f}")
            histories["phase1"].append(row)
            _atomic_json(output_dir / "training_history.json", histories)
            print(
                f"seed={args.seed} phase=private update={update}/{phase1_updates} "
                + " ".join(summary),
                flush=True,
            )
    if phase1_early_audit is None:
        raise AssertionError("phase-1 movement guard was not reached")
    phase1_final_audit = phase1_guard.movement(checkpoint="phase_end")

    _copy_private(
        conditions["organ_private_extended"], conditions["organ_private_phase1"]
    )
    _copy_private(
        conditions["organ_private_extended"],
        conditions["coefficient_supervised_plus_frozen_private"],
    )
    _copy_private(
        conditions["organ_private_extended"],
        conditions["random_coefficient_supervised_plus_frozen_private"],
    )
    _freeze_private(conditions["organ_private_phase1"])
    _freeze_private(conditions["coefficient_supervised_plus_frozen_private"])
    _freeze_private(
        conditions["random_coefficient_supervised_plus_frozen_private"]
    )

    cache = {
        "summary": [],
        "program_target": [],
        "program_gram": [],
        "random_target": [],
        "random_gram": [],
    }
    conditions.eval()
    offset = 0
    with torch.no_grad():
        for update, (masked, truth_score, local_mask) in enumerate(
            phase2_loader, start=1
        ):
            masked = masked.to(device)
            truth_score = truth_score.to(device)
            local_mask = local_mask.to(device)
            batch_indices = np.asarray(
                [int(item[0]) for item in phase2_sampler.batches[update - 1]],
                dtype=np.int64,
            )
            batch_organs = torch.as_tensor(
                train_organ[batch_indices], device=device, dtype=torch.long
            )
            hidden = trunk.encode(masked)
            pooled_score = trunk.decode(hidden).index_select(1, score_tensor)
            frozen_private, _ = conditions["organ_private_phase1"](
                hidden, masked, batch_organs
            )
            residual = truth_score - pooled_score - frozen_private
            program_target, program_gram = _coefficient_targets(
                residual,
                local_mask,
                conditions[COEFFICIENT_CONDITION].program.decoder,
                ridge=float(config["projection_ridge"]),
            )
            random_target, random_gram = _coefficient_targets(
                residual,
                local_mask,
                conditions[
                    "random_coefficient_supervised_plus_frozen_private"
                ].program.decoder,
                ridge=float(config["projection_ridge"]),
            )
            cache["summary"].append(
                _hidden_summary(hidden, masked, float(config["mask_token"])).cpu()
            )
            cache["program_target"].append(program_target.cpu())
            cache["program_gram"].append(program_gram.cpu())
            cache["random_target"].append(random_target.cpu())
            cache["random_gram"].append(random_gram.cpu())
            offset += len(masked)
    cached = {name: torch.cat(values) for name, values in cache.items()}
    target_stats = {}
    for prefix in ("program", "random"):
        target = cached[f"{prefix}_target"]
        mean = target.mean(dim=0)
        scale = target.std(dim=0).clamp_min(float(config["target_scale_floor"]))
        gram = cached[f"{prefix}_gram"]
        energy = torch.bmm(
            target.unsqueeze(1), gram
        ).bmm(target.unsqueeze(-1)).mean().clamp_min(1e-8)
        target_stats[prefix] = {"mean": mean, "scale": scale, "energy": energy}
    target_stats_path = output_dir / "coefficient_target_stats.npz"
    np.savez_compressed(
        target_stats_path,
        program_mean=target_stats["program"]["mean"].numpy(),
        program_scale=target_stats["program"]["scale"].numpy(),
        program_energy=np.asarray(target_stats["program"]["energy"].item()),
        random_mean=target_stats["random"]["mean"].numpy(),
        random_scale=target_stats["random"]["scale"].numpy(),
        random_energy=np.asarray(target_stats["random"]["energy"].item()),
    )

    phase2_names = (
        "organ_private_extended",
        "generic_capacity_extended",
        "coefficient_supervised_plus_frozen_private",
        "random_coefficient_supervised_plus_frozen_private",
    )
    optimizers = {
        "organ_private_extended": AdamW(
            conditions["organ_private_extended"].parameters(),
            lr=float(config["learning_rate"]),
            weight_decay=float(config["weight_decay"]),
        ),
        "generic_capacity_extended": AdamW(
            conditions["generic_capacity_extended"].parameters(),
            lr=float(config["learning_rate"]),
            weight_decay=float(config["weight_decay"]),
        ),
        "coefficient_supervised_plus_frozen_private": AdamW(
            conditions[
                "coefficient_supervised_plus_frozen_private"
            ].program.coefficient_head.parameters(),
            lr=float(config["learning_rate"]),
            weight_decay=float(config["weight_decay"]),
        ),
        "random_coefficient_supervised_plus_frozen_private": AdamW(
            conditions[
                "random_coefficient_supervised_plus_frozen_private"
            ].program.coefficient_head.parameters(),
            lr=float(config["learning_rate"]),
            weight_decay=float(config["weight_decay"]),
        ),
    }
    phase2_modules = {
        "organ_private_extended": conditions["organ_private_extended"],
        "generic_capacity_extended": conditions["generic_capacity_extended"],
        "coefficient_supervised_plus_frozen_private": conditions[
            "coefficient_supervised_plus_frozen_private"
        ].program.coefficient_head,
        "random_coefficient_supervised_plus_frozen_private": conditions[
            "random_coefficient_supervised_plus_frozen_private"
        ].program.coefficient_head,
    }
    phase2_guard = PhaseGuard(
        "phase2_coefficient",
        phase2_modules,
        optimizers,
    )
    schedulers = {
        name: CosineAnnealingLR(optimizers[name], T_max=phase2_updates)
        for name in phase2_names
    }
    conditions.train()
    cursor = 0
    phase2_guard_update = min(5, phase2_updates)
    phase2_early_audit = None
    for update, (masked, truth_score, local_mask) in enumerate(phase2_loader, start=1):
        for optimizer in optimizers.values():
            optimizer.zero_grad(set_to_none=True)
        masked = masked.to(device)
        truth_score = truth_score.to(device)
        local_mask = local_mask.to(device)
        batch = len(masked)
        batch_indices = np.asarray(
            [int(item[0]) for item in phase2_sampler.batches[update - 1]],
            dtype=np.int64,
        )
        batch_organs = torch.as_tensor(
            train_organ[batch_indices], device=device, dtype=torch.long
        )
        with torch.autocast(
            device_type="cuda", dtype=torch.float16, enabled=use_amp
        ):
            with torch.no_grad():
                hidden = trunk.encode(masked)
                pooled_score = trunk.decode(hidden).index_select(1, score_tensor)
            losses = {}
            for name in ("organ_private_extended", "generic_capacity_extended"):
                residual, _ = conditions[name](
                    hidden, masked, _labels_for_condition(name, batch_organs)
                )
                losses[name] = _masked_score_mse(
                    pooled_score + residual, truth_score, local_mask
                ).mean()
            for name, prefix in (
                ("coefficient_supervised_plus_frozen_private", "program"),
                (
                    "random_coefficient_supervised_plus_frozen_private",
                    "random",
                ),
            ):
                summary = cached["summary"][cursor : cursor + batch].to(device)
                target = cached[f"{prefix}_target"][cursor : cursor + batch].to(device)
                gram = cached[f"{prefix}_gram"][cursor : cursor + batch].to(device)
                mean = target_stats[prefix]["mean"].to(device)
                scale = target_stats[prefix]["scale"].to(device)
                prediction = conditions[name].program.coefficient_head.network(summary)
                coefficient_loss = (((prediction - target) / scale).square()).mean()
                difference = prediction - target
                decoded_loss = torch.bmm(
                    difference.unsqueeze(1), gram
                ).bmm(difference.unsqueeze(-1)).mean()
                decoded_loss = decoded_loss / target_stats[prefix]["energy"].to(device)
                losses[name] = (
                    float(config["coefficient_loss_weight"]) * coefficient_loss
                    + float(config["decoded_auxiliary_weight"]) * decoded_loss
                )
            total_loss = torch.stack(list(losses.values())).sum()
        if not bool(torch.isfinite(total_loss).item()):
            raise FloatingPointError(f"nonfinite phase-2 loss at update {update}")
        scaler.scale(total_loss).backward()
        for name in phase2_names:
            scaler.step(optimizers[name])
            schedulers[name].step()
        scaler.update()
        if update == phase2_guard_update:
            phase2_early_audit = phase2_guard.movement(
                checkpoint=f"update_{update}"
            )
        cursor += batch
        if update == 1 or update % int(config["log_interval"]) == 0 or update == phase2_updates:
            row = {"update": update}
            summary = []
            for name, loss in losses.items():
                value = float(loss.detach().cpu())
                row[name] = value
                summary.append(f"{name}={value:.6f}")
            histories["phase2"].append(row)
            _atomic_json(output_dir / "training_history.json", histories)
            print(
                f"seed={args.seed} phase=coefficient update={update}/{phase2_updates} "
                + " ".join(summary),
                flush=True,
            )
    if phase2_early_audit is None:
        raise AssertionError("phase-2 movement guard was not reached")
    phase2_final_audit = phase2_guard.movement(checkpoint="phase_end")
    if cursor != len(cached["summary"]):
        raise AssertionError("phase-2 cache does not align with fitting schedule")

    weights = balanced_validation_weights(selection.validation)
    metrics, arrays = _evaluate(
        trunk=trunk,
        conditions=conditions,
        loader=validation_loader,
        organ_labels=validation_organ,
        sample_weights=weights,
        device=device,
        mask_token=float(config["mask_token"]),
    )
    score_path = output_dir / "calibration_scores.npz"
    np.savez_compressed(
        score_path,
        sample_ids=np.asarray(validation_ids, dtype=str),
        donors=selection.validation["series_group_id"].astype(str).to_numpy(dtype=str),
        organs=selection.validation["organ"].astype(str).to_numpy(dtype=str),
        organ_labels=validation_organ,
        random_labels=validation_random,
        sample_weights=weights,
        **arrays,
    )
    checkpoint_path = output_dir / "final_heads.pt"
    state = {
        name: value.detach().cpu()
        for name, value in conditions.state_dict().items()
    }
    torch.save(
        {
            "schema_version": 2,
            "seed": args.seed,
            "code_commit": args.code_commit,
            "conditions": list(CONDITIONS),
            "state_dict": state,
            "parameter_counts": parameter_counts,
        },
        checkpoint_path,
    )
    metadata.update({
        "status": "complete",
        "elapsed_seconds": float(time.time() - start),
        "completed_phase1_updates": phase1_updates,
        "completed_phase2_updates": phase2_updates,
        "completed_updates": phase1_updates + phase2_updates,
        "metrics": metrics,
        "phase_guards": {
            "phase1_early": phase1_early_audit,
            "phase1_final": phase1_final_audit,
            "phase2_early": phase2_early_audit,
            "phase2_final": phase2_final_audit,
        },
    })
    metadata["hashes"].update({
        "calibration_scores_sha256": sha256_file(score_path),
        "checkpoint_sha256": sha256_file(checkpoint_path),
        "final_state_sha256": tensor_state_sha256(state),
        "coefficient_target_stats_sha256": sha256_file(target_stats_path),
    })
    _atomic_json(output_dir / "run_metadata.json", metadata)
    (output_dir / "COMPLETE").touch()
    return metadata


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--basis-bundle", required=True)
    parser.add_argument("--expression-parquet", required=True)
    parser.add_argument("--expression-metadata", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--axis-definitions", required=True)
    parser.add_argument("--pooled-checkpoint", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--mask-token", type=float, default=-10.0)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--use-amp", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--smoke-only", action="store_true")
    parser.add_argument("--smoke-updates", type=int, default=2)
    return parser


def main() -> None:
    result = train(build_parser().parse_args())
    print(json.dumps({
        "status": result["status"],
        "seed": result["seed"],
        "completed_updates": result["completed_updates"],
        "elapsed_seconds": result["elapsed_seconds"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
