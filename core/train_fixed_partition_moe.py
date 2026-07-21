#!/usr/bin/env python3
"""Hard-train frozen-trunk residual experts for one fixed utility partition.

Unlike the failed joint soft-mixture pilot, this trainer has no learned router
and no blended-output training loss.  Every sample updates exactly one expert
according to a partition fitted before expert initialization.  The final
predetermined update is evaluated once on calibration score genes that were
hidden while the partition was constructed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd
import torch
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader, Dataset


CORE_DIR = Path(__file__).resolve().parent
ROOT = CORE_DIR.parent
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))
if str(ROOT / "evaluation") not in sys.path:
    sys.path.insert(0, str(ROOT / "evaluation"))

from headroom_metrics import make_crossfit_folds  # noqa: E402
from train_latent_moe import (  # noqa: E402
    FrozenTrunkResidualMoE,
    _masked_row_mse,
    load_frozen_trunk,
    simplex_least_squares_weights,
)
from train_manifest import (  # noqa: E402
    DeterministicBudgetBatchSampler,
    DeterministicMaskedExpressionDataset,
    balanced_validation_weights,
    load_expression_rows,
    read_manifest,
    seed_data_worker,
    seed_everything,
    select_manifest_rows,
    sha256_file,
    sha256_json,
    sha256_lines,
    stable_seed,
    validate_expression_metadata,
)


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _resolve_device(requested: str) -> torch.device:
    if requested == "auto":
        return torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    device = torch.device(requested)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError(f"CUDA requested but unavailable: {requested}")
    return device


class FixedGeneMaskDataset(Dataset):
    """Expression rows with one frozen global score-gene mask."""

    def __init__(
        self,
        expression: np.ndarray,
        sample_ids: Sequence[str],
        *,
        mask_indices: np.ndarray,
        mask_token: float,
    ):
        values = np.asarray(expression, dtype=np.float32)
        if values.ndim != 2 or values.shape[0] != len(sample_ids):
            raise ValueError("expression must align with sample IDs")
        if np.any(values < 0):
            raise ValueError("expected nonnegative TPM expression")
        mask_indices = np.asarray(mask_indices, dtype=np.int64)
        if mask_indices.ndim != 1 or not len(mask_indices):
            raise ValueError("score mask must be a nonempty vector")
        if mask_indices.min() < 0 or mask_indices.max() >= values.shape[1]:
            raise ValueError("score mask contains an out-of-range gene")
        self.expression = np.log1p(values).astype(np.float32, copy=False)
        self.sample_ids = tuple(str(value) for value in sample_ids)
        self.mask_indices_value = np.sort(mask_indices)
        self.mask_token = float(mask_token)

    def __len__(self) -> int:
        return len(self.sample_ids)

    def __getitem__(self, index: int):
        truth = self.expression[int(index)]
        masked = truth.copy()
        masked[self.mask_indices_value] = self.mask_token
        return (
            torch.from_numpy(masked),
            torch.from_numpy(truth.copy()),
            torch.from_numpy(self.mask_indices_value.copy()),
        )


def _weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    values = np.asarray(values, dtype=np.float64)
    weights = np.asarray(weights, dtype=np.float64)
    return float(np.dot(values, weights))


def _crossfit_fixed_blend(
    expert_masked: np.ndarray,
    target_masked: np.ndarray,
    *,
    groups: np.ndarray,
    organs: np.ndarray,
    sample_weights: np.ndarray,
    seed: int,
    folds: int,
) -> tuple[np.ndarray, list[list[float]], np.ndarray]:
    fold_ids = make_crossfit_folds(
        len(target_masked),
        folds,
        seed,
        strata=organs,
        groups=groups,
    )
    prediction = np.empty_like(target_masked, dtype=np.float64)
    fold_weights: list[list[float]] = []
    for fold in sorted(np.unique(fold_ids)):
        fit = fold_ids != fold
        held = fold_ids == fold
        fit_weights = sample_weights[fit]
        fit_weights = fit_weights / fit_weights.sum()
        weights = simplex_least_squares_weights(
            expert_masked[fit],
            target_masked[fit],
            sample_weights=fit_weights,
        )
        prediction[held] = np.einsum(
            "k,nkm->nm", weights, expert_masked[held]
        )
        fold_weights.append(weights.tolist())
    mse = np.square(prediction - target_masked).mean(axis=1)
    return mse, fold_weights, fold_ids


def evaluate_fixed_partition(
    model: FrozenTrunkResidualMoE,
    loader: DataLoader,
    *,
    labels: np.ndarray,
    groups: np.ndarray,
    organs: np.ndarray,
    sample_weights: np.ndarray,
    device: torch.device,
    crossfit_seed: int,
    crossfit_folds: int,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    model.eval()
    pooled_rows: list[np.ndarray] = []
    true_rows: list[np.ndarray] = []
    oracle_rows: list[np.ndarray] = []
    expert_error_rows: list[np.ndarray] = []
    expert_masked_rows: list[np.ndarray] = []
    target_masked_rows: list[np.ndarray] = []
    offset = 0
    with torch.no_grad():
        for masked, truth, mask in loader:
            masked = masked.to(device)
            truth = truth.to(device)
            mask = mask.to(device)
            expert_predictions, _, base = model(masked)
            batch_labels = torch.as_tensor(
                labels[offset : offset + len(masked)], device=device
            )
            row = torch.arange(len(masked), device=device)
            true_prediction = expert_predictions[row, batch_labels]
            errors = torch.stack(
                [
                    _masked_row_mse(expert_predictions[:, index], truth, mask)
                    for index in range(model.num_experts)
                ],
                dim=1,
            )
            expanded_mask = mask.unsqueeze(1).expand(-1, model.num_experts, -1)
            expert_masked_rows.append(
                expert_predictions.gather(2, expanded_mask).cpu().numpy()
            )
            target_masked_rows.append(truth.gather(1, mask).cpu().numpy())
            pooled_rows.append(_masked_row_mse(base, truth, mask).cpu().numpy())
            true_rows.append(
                _masked_row_mse(true_prediction, truth, mask).cpu().numpy()
            )
            oracle_rows.append(errors.min(dim=1).values.cpu().numpy())
            expert_error_rows.append(errors.cpu().numpy())
            offset += len(masked)
    if offset != len(labels):
        raise AssertionError("validation labels do not align with loader")
    expert_masked = np.concatenate(expert_masked_rows).astype(np.float64)
    target_masked = np.concatenate(target_masked_rows).astype(np.float64)
    uniform_prediction = expert_masked.mean(axis=1)
    uniform_mse = np.square(uniform_prediction - target_masked).mean(axis=1)
    full_fixed_weights = simplex_least_squares_weights(
        expert_masked,
        target_masked,
        sample_weights=sample_weights,
    )
    full_fixed_prediction = np.einsum(
        "k,nkm->nm", full_fixed_weights, expert_masked
    )
    full_fixed_mse = np.square(full_fixed_prediction - target_masked).mean(axis=1)
    crossfit_mse, fold_weights, fold_ids = _crossfit_fixed_blend(
        expert_masked,
        target_masked,
        groups=groups,
        organs=organs,
        sample_weights=sample_weights,
        seed=crossfit_seed,
        folds=crossfit_folds,
    )
    arrays = {
        "pooled_mse": np.concatenate(pooled_rows).astype(np.float64),
        "true_partition_mse": np.concatenate(true_rows).astype(np.float64),
        "oracle_mse": np.concatenate(oracle_rows).astype(np.float64),
        "expert_mse": np.concatenate(expert_error_rows).astype(np.float64),
        "uniform_fixed_mse": uniform_mse.astype(np.float64),
        "full_calibration_fixed_mse": full_fixed_mse.astype(np.float64),
        "crossfit_fixed_mse": crossfit_mse.astype(np.float64),
        "true_labels": np.asarray(labels, dtype=np.int64),
        "crossfit_fold": fold_ids.astype(np.int64),
    }
    metrics: dict[str, Any] = {
        name: _weighted_mean(values, sample_weights)
        for name, values in arrays.items()
        if name.endswith("_mse") and values.ndim == 1
    }
    pooled = metrics["pooled_mse"]
    for name in ("true_partition", "oracle", "uniform_fixed", "crossfit_fixed"):
        metrics[f"{name}_relative_mse_reduction_vs_pooled"] = (
            pooled - metrics[f"{name}_mse"]
        ) / pooled
    metrics["oracle_relative_mse_reduction_vs_crossfit_fixed"] = (
        metrics["crossfit_fixed_mse"] - metrics["oracle_mse"]
    ) / metrics["crossfit_fixed_mse"]
    counts = np.bincount(labels, minlength=model.num_experts).astype(np.float64)
    fractions = counts / counts.sum()
    metrics["partition_utilization"] = fractions.tolist()
    metrics["effective_experts"] = float(1.0 / np.square(fractions).sum())
    metrics["minimum_partition_fraction"] = float(fractions.min())
    metrics["crossfit_fixed_weights"] = fold_weights
    metrics["full_calibration_fixed_weights"] = full_fixed_weights.tolist()

    pairwise = []
    residual = expert_masked - target_masked[:, None, :]
    gene_count = target_masked.shape[1]
    observation_weights = np.repeat(sample_weights / gene_count, gene_count)
    for left in range(model.num_experts):
        for right in range(left + 1, model.num_experts):
            left_residual = residual[:, left, :].reshape(-1)
            right_residual = residual[:, right, :].reshape(-1)
            left_mean = float(np.dot(observation_weights, left_residual))
            right_mean = float(np.dot(observation_weights, right_residual))
            left_centered = left_residual - left_mean
            right_centered = right_residual - right_mean
            covariance = float(
                np.dot(observation_weights, left_centered * right_centered)
            )
            variance_left = float(np.dot(observation_weights, left_centered**2))
            variance_right = float(np.dot(observation_weights, right_centered**2))
            denominator = np.sqrt(variance_left * variance_right)
            disagreement = np.square(
                expert_masked[:, left, :] - expert_masked[:, right, :]
            ).mean(axis=1)
            pairwise.append({
                "experts": [left, right],
                "residual_correlation": (
                    float(covariance / denominator) if denominator > 0 else 0.0
                ),
                "rms_prediction_disagreement": float(
                    np.sqrt(_weighted_mean(disagreement, sample_weights))
                ),
            })
    metrics["pairwise_functional_diversity"] = pairwise
    return metrics, arrays


def _load_inputs(args: argparse.Namespace, checkpoint_config: dict[str, Any]):
    manifest = read_manifest(args.manifest)
    selection = select_manifest_rows(
        manifest,
        role="pooled",
        train_split=args.train_split,
        validation_split=args.validation_split,
        train_filter_column=args.train_filter_column,
    )
    train_ids = selection.train[args.sample_id_column].astype(str).tolist()
    validation_ids = selection.validation[args.sample_id_column].astype(str).tolist()
    expression, expression_info = load_expression_rows(
        args.expression_parquet,
        train_ids + validation_ids,
        sample_id_column=args.sample_id_column,
    )
    if list(expression_info.gene_columns) != list(checkpoint_config["gene_list"]):
        raise ValueError("expression gene order differs from pooled checkpoint")
    validate_expression_metadata(
        args.expression_parquet,
        expression_info.gene_columns,
        metadata_path=args.expression_metadata,
    )
    partition_report = json.loads(Path(args.partition_report).read_text())
    if partition_report.get("status") != "complete" or partition_report.get("test_accessed") is not False:
        raise ValueError("partition report is incomplete or accessed test")
    partition_path = Path(args.partition_manifest)
    definitions_path = Path(args.axis_definitions)
    if sha256_file(partition_path) != partition_report["hashes"]["partition_manifest_sha256"]:
        raise ValueError("partition manifest hash differs from report")
    if sha256_file(definitions_path) != partition_report["hashes"]["axis_definitions_sha256"]:
        raise ValueError("axis definition hash differs from report")
    partitions = pd.read_parquet(partition_path)
    expected_ids = train_ids + validation_ids
    if partitions[args.sample_id_column].astype(str).tolist() != expected_ids:
        raise ValueError("partition manifest sample order differs from selected data")
    if args.axis not in partitions:
        raise ValueError(f"unknown fixed partition {args.axis!r}")
    raw_labels = partitions[args.axis].to_numpy()
    if pd.isna(raw_labels).any():
        raise ValueError("fixed partition contains missing labels")
    labels = np.asarray(raw_labels, dtype=np.int64)
    unique = np.unique(labels)
    if not np.array_equal(unique, np.arange(len(unique))):
        raise ValueError(f"fixed partition labels must be contiguous from zero: {unique}")
    with np.load(definitions_path, allow_pickle=False) as archive:
        score_indices = archive["score_gene_indices"].astype(np.int64)
        probe_indices = archive["probe_gene_indices"].astype(np.int64)
        definition_gene_names = archive["gene_names"].astype(str).tolist()
    if definition_gene_names != list(expression_info.gene_columns):
        raise ValueError("axis definition gene names differ from expression")
    if set(score_indices) & set(probe_indices):
        raise ValueError("probe and score genes overlap")
    return (
        selection,
        expression[: len(train_ids)],
        expression[len(train_ids) :],
        expression_info,
        labels[: len(train_ids)],
        labels[len(train_ids) :],
        score_indices,
        partition_report,
    )


def run_training(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output_dir}")
    seed_everything(args.seed, deterministic=True)
    device = _resolve_device(args.device)
    trunk, checkpoint_config, checkpoint = load_frozen_trunk(args.pooled_checkpoint, device)
    if checkpoint_config["normalization"] != "log1p_tpm":
        raise ValueError("fixed-partition pilot requires log1p_tpm checkpoint")
    if not np.isclose(float(checkpoint_config["mask_token"]), float(args.mask_token)):
        raise ValueError("mask token differs from pooled checkpoint")
    (
        selection,
        train_expression,
        validation_expression,
        expression_info,
        train_labels,
        validation_labels,
        score_indices,
        partition_report,
    ) = _load_inputs(args, checkpoint_config)
    num_experts = int(len(np.unique(train_labels)))
    if len(np.unique(validation_labels)) != num_experts:
        raise ValueError("calibration does not use every fixed expert")
    expected_updates = int(args.exposures_per_expert * num_experts / args.batch_size)
    if expected_updates * args.batch_size != args.exposures_per_expert * num_experts:
        raise ValueError("exposure budget must divide exactly by batch size")
    if args.max_updates is None:
        max_updates = expected_updates
    else:
        max_updates = int(args.max_updates)
        if not args.smoke_only and max_updates != expected_updates:
            raise ValueError(
                f"full run requires {expected_updates} updates for K={num_experts}, got {max_updates}"
            )
    train_ids = selection.train[args.sample_id_column].astype(str).tolist()
    validation_ids = selection.validation[args.sample_id_column].astype(str).tolist()
    train_dataset = DeterministicMaskedExpressionDataset(
        train_expression,
        train_ids,
        normalization="log1p_tpm",
        mask_ratio=args.mask_ratio,
        mask_token=args.mask_token,
        seed=args.seed,
        phase=f"fixed_partition_{args.axis}",
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
        seed=stable_seed(args.seed, "fixed_partition_sampler", args.axis),
        sampling_mode="organ_balanced",
        organs=[str(value) for value in train_labels],
        group_ids=selection.train[args.group_column].astype(str).tolist(),
    )
    generator = torch.Generator().manual_seed(
        stable_seed(args.seed, "fixed_partition_loader", args.axis) % (2**63 - 1)
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
    model = FrozenTrunkResidualMoE(
        trunk,
        num_experts=num_experts,
        adapter_dim=args.adapter_dim,
        router_hidden_dim=args.router_hidden_dim,
        mask_token=args.mask_token,
    ).to(device)
    model.router.requires_grad_(False)
    trainable = [
        parameter
        for expert in model.experts
        for parameter in expert.parameters()
        if parameter.requires_grad
    ]
    optimizer = AdamW(trainable, lr=args.learning_rate, weight_decay=args.weight_decay)
    scheduler = CosineAnnealingLR(optimizer, T_max=max(1, max_updates))
    use_amp = bool(args.use_amp and device.type == "cuda")
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    exposure_counts = np.bincount(
        train_labels[np.asarray(sampler.flat_indices, dtype=np.int64)],
        minlength=num_experts,
    )
    if exposure_counts.min() != exposure_counts.max() and not args.smoke_only:
        raise AssertionError(f"per-expert exposures are not equal: {exposure_counts}")
    config = {
        "axis": args.axis,
        "num_experts": num_experts,
        "adapter_dim": args.adapter_dim,
        "router_trainable": False,
        "max_updates": max_updates,
        "exposures_per_expert": args.exposures_per_expert,
        "batch_size": args.batch_size,
        "validation_batch_size": args.validation_batch_size,
        "mask_ratio": args.mask_ratio,
        "score_gene_count": int(len(score_indices)),
        "learning_rate": args.learning_rate,
        "weight_decay": args.weight_decay,
        "crossfit_folds": args.crossfit_folds,
        "crossfit_seed": args.crossfit_seed,
        "use_amp": use_amp,
        "checkpoint_policy": "predetermined_final_update",
    }
    metadata = {
        "schema_version": 1,
        "status": "running",
        "research_stage": "stage2_competitive_followup",
        "experiment": "hard_fixed_partition_residual_experts",
        "axis": args.axis,
        "training_seed": int(args.seed),
        "test_accessed": False,
        "mechanical_only": bool(args.smoke_only),
        "config": config,
        "counts": {
            "train": len(train_ids),
            "calibration": len(validation_ids),
            "genes": len(expression_info.gene_columns),
            "score_genes": len(score_indices),
        },
        "exposure_counts": exposure_counts.tolist(),
        "trainable_parameters": int(sum(value.numel() for value in trainable)),
        "pooled_checkpoint_update": checkpoint.get("update"),
        "hashes": {
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
        },
    }
    metadata["hashes"]["resolved_config_sha256"] = sha256_json(config)
    if metadata["hashes"]["partition_manifest_sha256"] != partition_report["hashes"]["partition_manifest_sha256"]:
        raise ValueError("partition manifest is not the report-pinned artifact")
    _atomic_json(output_dir / "run_metadata.json", metadata)

    start_time = time.time()
    training_log: list[dict[str, Any]] = []
    model.train()
    for update, batch in enumerate(train_loader, start=1):
        masked, truth, mask = (value.to(device) for value in batch)
        batch_indices = [int(item[0]) for item in sampler.batches[update - 1]]
        labels = torch.as_tensor(train_labels[batch_indices], device=device)
        optimizer.zero_grad(set_to_none=True)
        autocast = torch.autocast(device_type="cuda", dtype=torch.float16, enabled=use_amp)
        with autocast:
            expert_predictions, _, _ = model(masked)
            row = torch.arange(len(labels), device=device)
            prediction = expert_predictions[row, labels]
            reconstruction_loss = _masked_row_mse(prediction, truth, mask).mean()
        scaler.scale(reconstruction_loss).backward()
        scaler.step(optimizer)
        scaler.update()
        scheduler.step()
        if update == 1 or update % args.log_interval == 0 or update == max_updates:
            item = {
                "update": int(update),
                "train_reconstruction_loss": float(reconstruction_loss.detach().cpu()),
            }
            training_log.append(item)
            _atomic_json(output_dir / "training_history.json", training_log)
            print(
                f"update={update}/{max_updates} axis={args.axis} "
                f"train={item['train_reconstruction_loss']:.6f}",
                flush=True,
            )
    groups = selection.validation[args.group_column].astype(str).to_numpy()
    organs = selection.validation[args.organ_column].astype(str).to_numpy()
    metrics, arrays = evaluate_fixed_partition(
        model,
        validation_loader,
        labels=validation_labels,
        groups=groups,
        organs=organs,
        sample_weights=validation_weights,
        device=device,
        crossfit_seed=args.crossfit_seed,
        crossfit_folds=args.crossfit_folds,
    )
    np.savez_compressed(
        output_dir / "calibration_scores.npz",
        sample_ids=np.asarray(validation_ids, dtype=str),
        groups=np.asarray(groups, dtype=str),
        organs=np.asarray(organs, dtype=str),
        sample_weights=validation_weights.astype(np.float64),
        **arrays,
    )
    expert_state = {
        name: value.detach().cpu()
        for name, value in model.state_dict().items()
        if name.startswith("experts.")
    }
    torch.save(
        {
            "schema_version": 1,
            "axis": args.axis,
            "training_seed": int(args.seed),
            "final_update": int(max_updates),
            "config": config,
            "expert_state_dict": expert_state,
            "pooled_checkpoint_sha256": metadata["hashes"]["pooled_checkpoint_sha256"],
        },
        output_dir / "final_experts.pt",
    )
    metadata.update({
        "status": "complete",
        "final_update": int(max_updates),
        "elapsed_seconds": float(time.time() - start_time),
        "calibration_metrics": metrics,
        "artifacts": {
            "final_experts_sha256": sha256_file(output_dir / "final_experts.pt"),
            "calibration_scores_sha256": sha256_file(output_dir / "calibration_scores.npz"),
        },
    })
    _atomic_json(output_dir / "run_metadata.json", metadata)
    (output_dir / "COMPLETE").touch()
    return metadata


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
    parser.add_argument("--axis", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--train-split", default="train")
    parser.add_argument("--validation-split", default="calibration")
    parser.add_argument("--train-filter-column", default="balanced_train")
    parser.add_argument("--sample-id-column", default="sample_id")
    parser.add_argument("--organ-column", default="organ")
    parser.add_argument("--group-column", default="series_group_id")
    parser.add_argument("--adapter-dim", type=int, default=64)
    parser.add_argument("--router-hidden-dim", type=int, default=128)
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
    result = run_training(args)
    print(json.dumps({
        "status": result["status"],
        "axis": result["axis"],
        "training_seed": result["training_seed"],
        "final_update": result["final_update"],
        "calibration_metrics": result["calibration_metrics"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
