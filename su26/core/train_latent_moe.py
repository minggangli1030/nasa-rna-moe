#!/usr/bin/env python3
"""Frozen-trunk residual MoE feasibility trainer.

This is deliberately a bounded Stage 2 pilot.  A previously trained pooled
ExpressionPerformer is frozen; only a sample router and K small per-gene residual
heads are optimized.  The label-free mode receives no organ, study, platform, or
phenotype labels.  Organ and balanced-random modes are matched positive/null
controls using the same architecture and update budget.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import itertools
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from torch import nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader


CORE_DIR = Path(__file__).resolve().parent
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

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
from train_single import ExpressionPerformer  # noqa: E402


MODES = ("organ_supervised", "balanced_random", "label_free")


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


def _checkpoint_config(checkpoint: dict[str, Any]) -> dict[str, Any]:
    config = checkpoint.get("config")
    if not isinstance(config, dict):
        raise ValueError("pooled checkpoint is missing a config dictionary")
    required = {
        "num_genes", "hidden_dim", "ffn_dim", "num_heads", "num_layers",
        "ree_base", "feature_type", "compute_type", "mask_token",
        "normalization", "gene_list",
    }
    missing = sorted(required - set(config))
    if missing:
        raise ValueError(f"pooled checkpoint config is missing {missing}")
    if len(config["gene_list"]) != int(config["num_genes"]):
        raise ValueError("checkpoint gene list does not match num_genes")
    return config


def load_frozen_trunk(
    checkpoint_path: str | Path, device: torch.device
) -> tuple[ExpressionPerformer, dict[str, Any], dict[str, Any]]:
    checkpoint_path = Path(checkpoint_path)
    try:
        checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    except TypeError:
        checkpoint = torch.load(checkpoint_path, map_location="cpu")
    config = _checkpoint_config(checkpoint)
    trunk = ExpressionPerformer(
        num_genes=int(config["num_genes"]),
        hidden_dim=int(config["hidden_dim"]),
        n_heads=int(config["num_heads"]),
        n_layers=int(config["num_layers"]),
        ffn_dim=int(config["ffn_dim"]),
        ree_base=float(config["ree_base"]),
        mask_token_id=float(config["mask_token"]),
        feature_type=str(config["feature_type"]),
        compute_type=str(config["compute_type"]),
        gradient_checkpointing=False,
    )
    trunk.load_state_dict(checkpoint["model_state_dict"])
    trunk.requires_grad_(False)
    trunk.eval()
    trunk.to(device)
    return trunk, config, checkpoint


class ResidualExpert(nn.Module):
    def __init__(self, hidden_dim: int, adapter_dim: int):
        super().__init__()
        self.down = nn.Linear(hidden_dim, adapter_dim)
        self.up = nn.Linear(adapter_dim, 1)
        nn.init.normal_(self.up.weight, mean=0.0, std=1e-3)
        nn.init.zeros_(self.up.bias)

    def forward(self, hidden: torch.Tensor) -> torch.Tensor:
        return self.up(F.gelu(self.down(hidden))).squeeze(-1)


class FrozenTrunkResidualMoE(nn.Module):
    def __init__(
        self,
        trunk: ExpressionPerformer,
        *,
        num_experts: int,
        adapter_dim: int,
        router_hidden_dim: int,
        mask_token: float,
    ):
        super().__init__()
        if num_experts < 2:
            raise ValueError("num_experts must be at least two")
        self.trunk = trunk
        self.num_experts = int(num_experts)
        self.mask_token = float(mask_token)
        hidden_dim = int(trunk.gene_embedding.embedding_dim)
        self.router = nn.Sequential(
            nn.LayerNorm(hidden_dim),
            nn.Linear(hidden_dim, router_hidden_dim),
            nn.GELU(),
            nn.Linear(router_hidden_dim, num_experts),
        )
        self.experts = nn.ModuleList(
            ResidualExpert(hidden_dim, adapter_dim) for _ in range(num_experts)
        )

    def train(self, mode: bool = True):
        super().train(mode)
        self.trunk.eval()
        return self

    def forward(
        self, masked: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        with torch.no_grad():
            hidden = self.trunk.encode(masked)
            base = self.trunk.decode(hidden)
        observed = masked.ne(self.mask_token).to(hidden.dtype)
        denominator = observed.sum(dim=1, keepdim=True).clamp_min(1.0)
        summary = (hidden * observed.unsqueeze(-1)).sum(dim=1) / denominator
        router_logits = self.router(summary)
        residuals = torch.stack([expert(hidden) for expert in self.experts], dim=1)
        expert_predictions = base.unsqueeze(1) + residuals
        return expert_predictions, router_logits, base

    def trainable_state_dict(self) -> dict[str, torch.Tensor]:
        return {
            name: value.detach().cpu()
            for name, value in self.state_dict().items()
            if not name.startswith("trunk.")
        }


def encode_partition_labels(
    frame: pd.DataFrame,
    *,
    mode: str,
    organ_column: str,
    random_shard_column: str,
    expected_names: Sequence[str] | None = None,
) -> tuple[np.ndarray | None, list[str]]:
    if mode == "label_free":
        return None, [f"latent_{index}" for index in range(5)]
    column = organ_column if mode == "organ_supervised" else random_shard_column
    if column not in frame.columns or frame[column].isna().any():
        raise ValueError(f"{mode} requires complete manifest column {column!r}")
    values = frame[column].astype(str)
    names = sorted(values.unique()) if expected_names is None else list(expected_names)
    unknown = sorted(set(values) - set(names))
    if unknown:
        raise ValueError(f"validation contains unseen {column} values: {unknown}")
    index = {name: offset for offset, name in enumerate(names)}
    return np.asarray([index[value] for value in values], dtype=np.int64), names


def _masked_row_mse(
    prediction: torch.Tensor, truth: torch.Tensor, mask: torch.Tensor
) -> torch.Tensor:
    return (prediction.gather(1, mask) - truth.gather(1, mask)).square().mean(dim=1)


def _weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    values = np.asarray(values, dtype=np.float64)
    weights = np.asarray(weights, dtype=np.float64)
    return float(np.dot(values, weights))


def simplex_least_squares_weights(
    expert_masked: np.ndarray,
    target_masked: np.ndarray,
    sample_weights: np.ndarray | None = None,
) -> np.ndarray:
    """Fit the exact best nonnegative sum-to-one blend for a small expert set.

    The pilot fixes K=5, so enumerating the simplex faces is both deterministic
    and more reliable than an iterative generic optimizer.  On each face the
    equality-constrained least-squares solution is analytic; the best feasible
    face is the global solution of this convex problem.
    """
    predictions = np.asarray(expert_masked, dtype=np.float64)
    targets = np.asarray(target_masked, dtype=np.float64)
    if predictions.ndim != 3 or targets.shape != (predictions.shape[0], predictions.shape[2]):
        raise ValueError("expert/target masked arrays are misaligned")
    design = predictions.transpose(0, 2, 1).reshape(-1, predictions.shape[1])
    target = targets.reshape(-1)
    if sample_weights is None:
        observation_weights = np.ones(len(predictions), dtype=np.float64)
    else:
        observation_weights = np.asarray(sample_weights, dtype=np.float64)
        if observation_weights.shape != (len(predictions),):
            raise ValueError("fixed-blend sample weights do not align with predictions")
        if np.any(observation_weights < 0) or observation_weights.sum() <= 0:
            raise ValueError("fixed-blend sample weights must be nonnegative with positive sum")
    observation_weights = observation_weights / observation_weights.sum()
    flattened_weights = np.repeat(observation_weights, targets.shape[1])
    sqrt_weights = np.sqrt(flattened_weights)
    design = design * sqrt_weights[:, None]
    target = target * sqrt_weights
    gram = design.T @ design
    cross = design.T @ target

    num_experts = predictions.shape[1]
    if num_experts > 12:
        raise ValueError("exact simplex solver supports at most 12 experts")

    best_objective = np.inf
    best_weights: np.ndarray | None = None
    for size in range(1, num_experts + 1):
        for active_tuple in itertools.combinations(range(num_experts), size):
            active = np.asarray(active_tuple, dtype=np.int64)
            face_gram = gram[np.ix_(active, active)]
            kkt = np.block([
                [face_gram, np.ones((size, 1), dtype=np.float64)],
                [np.ones((1, size), dtype=np.float64), np.zeros((1, 1), dtype=np.float64)],
            ])
            rhs = np.concatenate([cross[active], np.ones(1, dtype=np.float64)])
            solution, *_ = np.linalg.lstsq(kkt, rhs, rcond=None)
            face_weights = solution[:size]
            if np.any(face_weights < -1e-10):
                continue
            candidate = np.zeros(num_experts, dtype=np.float64)
            candidate[active] = np.clip(face_weights, 0.0, None)
            candidate /= candidate.sum()
            objective = float(candidate @ gram @ candidate - 2.0 * candidate @ cross)
            if objective < best_objective:
                best_objective = objective
                best_weights = candidate

    if best_weights is None:
        raise RuntimeError("exact fixed-blend simplex optimization found no feasible face")
    return best_weights


def evaluate(
    model: FrozenTrunkResidualMoE,
    loader: DataLoader,
    *,
    device: torch.device,
    sample_weights: np.ndarray,
    temperature: float,
    true_labels: np.ndarray | None,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    model.eval()
    pooled_rows: list[np.ndarray] = []
    hard_rows: list[np.ndarray] = []
    soft_rows: list[np.ndarray] = []
    oracle_rows: list[np.ndarray] = []
    true_rows: list[np.ndarray] = []
    routes: list[np.ndarray] = []
    probabilities: list[np.ndarray] = []
    expert_masked_rows: list[np.ndarray] = []
    target_masked_rows: list[np.ndarray] = []
    with torch.no_grad():
        for masked, truth, mask in loader:
            masked = masked.to(device)
            truth = truth.to(device)
            mask = mask.to(device)
            expert_predictions, logits, base = model(masked)
            probs = torch.softmax(logits / temperature, dim=1)
            route = probs.argmax(dim=1)
            row = torch.arange(len(masked), device=device)
            hard_prediction = expert_predictions[row, route]
            soft_prediction = torch.einsum("bk,bkg->bg", probs, expert_predictions)
            expert_errors = torch.stack(
                [
                    _masked_row_mse(expert_predictions[:, index], truth, mask)
                    for index in range(model.num_experts)
                ],
                dim=1,
            )
            pooled_rows.append(_masked_row_mse(base, truth, mask).cpu().numpy())
            hard_rows.append(_masked_row_mse(hard_prediction, truth, mask).cpu().numpy())
            soft_rows.append(_masked_row_mse(soft_prediction, truth, mask).cpu().numpy())
            oracle_rows.append(expert_errors.min(dim=1).values.cpu().numpy())
            if true_labels is not None:
                start = sum(len(value) for value in routes)
                batch_labels = torch.as_tensor(
                    true_labels[start : start + len(masked)], device=device
                )
                true_prediction = expert_predictions[row, batch_labels]
                true_rows.append(
                    _masked_row_mse(true_prediction, truth, mask).cpu().numpy()
                )
            routes.append(route.cpu().numpy())
            probabilities.append(probs.cpu().numpy())
            expanded_mask = mask.unsqueeze(1).expand(-1, model.num_experts, -1)
            expert_masked_rows.append(
                expert_predictions.gather(2, expanded_mask).cpu().numpy()
            )
            target_masked_rows.append(truth.gather(1, mask).cpu().numpy())

    expert_masked = np.concatenate(expert_masked_rows).astype(np.float64)
    target_masked = np.concatenate(target_masked_rows).astype(np.float64)
    fixed_weights = simplex_least_squares_weights(
        expert_masked, target_masked, sample_weights=sample_weights
    )
    fixed_masked = np.einsum("k,nkm->nm", fixed_weights, expert_masked)
    fixed_mse = np.square(fixed_masked - target_masked).mean(axis=1)

    arrays = {
        "pooled_mse": np.concatenate(pooled_rows).astype(np.float64),
        "fixed_mse": fixed_mse,
        "router_hard_mse": np.concatenate(hard_rows).astype(np.float64),
        "router_soft_mse": np.concatenate(soft_rows).astype(np.float64),
        "oracle_mse": np.concatenate(oracle_rows).astype(np.float64),
        "routes": np.concatenate(routes).astype(np.int64),
        "probabilities": np.concatenate(probabilities).astype(np.float32),
    }
    if true_rows:
        arrays["true_partition_mse"] = np.concatenate(true_rows).astype(np.float64)
    if len(sample_weights) != len(arrays["routes"]):
        raise AssertionError("evaluation weights do not align with predictions")
    utilization = np.bincount(
        arrays["routes"], minlength=model.num_experts
    ).astype(np.float64)
    utilization /= utilization.sum()
    metrics: dict[str, Any] = {
        key: _weighted_mean(value, sample_weights)
        for key, value in arrays.items()
        if key.endswith("_mse")
    }
    pooled = metrics["pooled_mse"]
    for name in ("fixed", "router_hard", "router_soft", "oracle", "true_partition"):
        key = f"{name}_mse"
        if key in metrics:
            metrics[f"{name}_relative_mse_reduction_vs_pooled"] = (
                pooled - metrics[key]
            ) / pooled
    metrics["route_utilization"] = utilization.tolist()
    metrics["fixed_weights"] = fixed_weights.tolist()
    metrics["effective_experts"] = float(1.0 / np.square(utilization).sum())
    metrics["minimum_route_fraction"] = float(utilization.min())
    if true_labels is not None:
        metrics["router_accuracy"] = float(
            np.mean(arrays["routes"] == np.asarray(true_labels))
        )
        arrays["true_labels"] = np.asarray(true_labels, dtype=np.int64)
    return metrics, arrays


def _load_data(args: argparse.Namespace, checkpoint_config: dict[str, Any]):
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
    expression, info = load_expression_rows(
        args.expression_parquet,
        train_ids + validation_ids,
        sample_id_column=args.sample_id_column,
    )
    if list(info.gene_columns) != list(checkpoint_config["gene_list"]):
        raise ValueError("expression gene order differs from pooled checkpoint")
    validate_expression_metadata(
        args.expression_parquet,
        info.gene_columns,
        metadata_path=args.expression_metadata,
    )
    return manifest, selection, expression[: len(train_ids)], expression[len(train_ids) :], info


def run_training(args: argparse.Namespace) -> dict[str, Any]:
    if args.mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output_dir}")
    seed_everything(args.seed, deterministic=True)
    device = _resolve_device(args.device)
    trunk, checkpoint_config, checkpoint = load_frozen_trunk(
        args.pooled_checkpoint, device
    )
    if checkpoint_config["normalization"] != "log1p_tpm":
        raise ValueError("latent-axis pilot requires a log1p_tpm pooled checkpoint")
    if not np.isclose(float(checkpoint_config["mask_token"]), float(args.mask_token)):
        raise ValueError("requested mask token differs from pooled checkpoint")
    manifest, selection, train_expression, validation_expression, expression_info = _load_data(
        args, checkpoint_config
    )
    train_labels, label_names = encode_partition_labels(
        selection.train,
        mode=args.mode,
        organ_column=args.organ_column,
        random_shard_column=args.random_shard_column,
    )
    if args.mode == "label_free":
        label_names = [f"latent_{index}" for index in range(args.num_experts)]
    elif len(label_names) != args.num_experts:
        raise ValueError(
            f"mode {args.mode} has {len(label_names)} labels, expected {args.num_experts}"
        )
    validation_labels, _ = encode_partition_labels(
        selection.validation,
        mode=args.mode,
        organ_column=args.organ_column,
        random_shard_column=args.random_shard_column,
        expected_names=None if args.mode == "label_free" else label_names,
    )

    train_ids = selection.train[args.sample_id_column].astype(str).tolist()
    validation_ids = selection.validation[args.sample_id_column].astype(str).tolist()
    required_probe_columns = ("label_evidence", "single_cell_probability")
    missing_probe_columns = [
        column for column in required_probe_columns if column not in selection.validation
    ]
    if missing_probe_columns:
        raise ValueError(f"manifest is missing post-hoc probe columns {missing_probe_columns}")
    validation_probe_arrays = {
        "label_evidence": np.asarray(
            selection.validation["label_evidence"].astype(str), dtype=str
        ),
        "single_cell_probability": selection.validation[
            "single_cell_probability"
        ].astype(float).to_numpy(),
    }
    train_dataset = DeterministicMaskedExpressionDataset(
        train_expression,
        train_ids,
        normalization="log1p_tpm",
        mask_ratio=args.mask_ratio,
        mask_token=args.mask_token,
        seed=args.seed,
        phase="latent_train",
        fixed_masks=False,
    )
    validation_dataset = DeterministicMaskedExpressionDataset(
        validation_expression,
        validation_ids,
        normalization="log1p_tpm",
        mask_ratio=args.mask_ratio,
        mask_token=args.mask_token,
        seed=args.mask_seed,
        phase="latent_validation",
        fixed_masks=True,
    )
    sampler = DeterministicBudgetBatchSampler(
        train_ids,
        batch_size=args.batch_size,
        max_updates=args.max_updates,
        seed=stable_seed(args.seed, "latent_sampler"),
        sampling_mode="organ_balanced",
        organs=selection.train[args.organ_column].astype(str).tolist(),
        group_ids=selection.train[args.group_column].astype(str).tolist(),
    )
    generator = torch.Generator().manual_seed(
        stable_seed(args.seed, "latent_loader") % (2**63 - 1)
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
        num_experts=args.num_experts,
        adapter_dim=args.adapter_dim,
        router_hidden_dim=args.router_hidden_dim,
        mask_token=args.mask_token,
    ).to(device)
    trainable = [parameter for parameter in model.parameters() if parameter.requires_grad]
    optimizer = AdamW(
        trainable, lr=args.learning_rate, weight_decay=args.weight_decay
    )
    scheduler = CosineAnnealingLR(optimizer, T_max=max(1, args.max_updates))
    use_amp = bool(args.use_amp and device.type == "cuda")
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)

    metadata = {
        "schema_version": 1,
        "status": "running",
        "research_stage": "stage2_discovery",
        "experiment": "frozen_trunk_latent_axis_pilot",
        "mode": args.mode,
        "training_seed": int(args.seed),
        "label_names": label_names,
        "test_accessed": False,
        "config": {
            "num_experts": args.num_experts,
            "adapter_dim": args.adapter_dim,
            "router_hidden_dim": args.router_hidden_dim,
            "max_updates": args.max_updates,
            "validation_interval": args.validation_interval,
            "batch_size": args.batch_size,
            "validation_batch_size": args.validation_batch_size,
            "mask_ratio": args.mask_ratio,
            "mask_token": args.mask_token,
            "mask_seed": args.mask_seed,
            "repeated_mask_seeds": list(args.repeated_mask_seeds),
            "learning_rate": args.learning_rate,
            "weight_decay": args.weight_decay,
            "load_balance_weight": args.load_balance_weight,
            "entropy_weight": args.entropy_weight,
            "router_supervision_weight": args.router_supervision_weight,
            "temperature": args.temperature,
            "use_amp": use_amp,
            "trunk_frozen": True,
        },
        "counts": {
            "train": len(train_ids),
            "validation": len(validation_ids),
            "genes": len(expression_info.gene_columns),
        },
        "hashes": {
            "pooled_checkpoint_sha256": sha256_file(args.pooled_checkpoint),
            "expression_sha256": sha256_file(args.expression_parquet),
            "manifest_sha256": sha256_file(args.manifest),
            "train_sample_ids_sha256": sha256_lines(train_ids),
            "validation_sample_ids_sha256": sha256_lines(validation_ids),
            "gene_order_sha256": sha256_lines(expression_info.gene_columns),
        },
        "trainable_parameters": int(sum(parameter.numel() for parameter in trainable)),
        "total_parameters": int(sum(parameter.numel() for parameter in model.parameters())),
        "pooled_checkpoint_update": checkpoint.get("update"),
    }
    metadata["hashes"]["resolved_config_sha256"] = sha256_json(metadata["config"])
    _atomic_json(output_dir / "run_metadata.json", metadata)

    history: list[dict[str, Any]] = []
    best_metric = float("inf")
    best_update = 0
    best_state: dict[str, torch.Tensor] | None = None
    start_time = time.time()
    model.train()
    for update, batch in enumerate(train_loader, start=1):
        masked, truth, mask = (value.to(device) for value in batch)
        optimizer.zero_grad(set_to_none=True)
        autocast = torch.autocast(device_type="cuda", dtype=torch.float16, enabled=use_amp)
        with autocast:
            expert_predictions, logits, _ = model(masked)
            probabilities = torch.softmax(logits / args.temperature, dim=1)
            if train_labels is None:
                prediction = torch.einsum(
                    "bk,bkg->bg", probabilities, expert_predictions
                )
                router_loss = torch.zeros((), device=device)
            else:
                batch_indices = [int(item[0]) for item in sampler.batches[update - 1]]
                labels = torch.as_tensor(train_labels[batch_indices], device=device)
                row = torch.arange(len(labels), device=device)
                prediction = expert_predictions[row, labels]
                router_loss = F.cross_entropy(logits, labels)
            reconstruction_loss = _masked_row_mse(prediction, truth, mask).mean()
            mean_probability = probabilities.mean(dim=0)
            load_balance = args.num_experts * mean_probability.square().sum() - 1.0
            entropy = -(
                probabilities * probabilities.clamp_min(1e-8).log()
            ).sum(dim=1).mean()
            loss = (
                reconstruction_loss
                + args.router_supervision_weight * router_loss
                + args.load_balance_weight * load_balance
                + args.entropy_weight * entropy
            )
        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()
        scheduler.step()

        if update % args.validation_interval == 0 or update == args.max_updates:
            metrics, _ = evaluate(
                model,
                validation_loader,
                device=device,
                sample_weights=validation_weights,
                temperature=args.temperature,
                true_labels=validation_labels,
            )
            selection_metric = metrics["router_hard_mse"]
            row = {
                "update": update,
                "train_loss": float(loss.detach().cpu()),
                "train_reconstruction_loss": float(reconstruction_loss.detach().cpu()),
                "validation_selection_mse": float(selection_metric),
                **metrics,
            }
            history.append(row)
            _atomic_json(output_dir / "training_history.json", history)
            if selection_metric < best_metric:
                best_metric = float(selection_metric)
                best_update = update
                best_state = copy.deepcopy(model.trainable_state_dict())
            print(
                f"update={update}/{args.max_updates} mode={args.mode} "
                f"train={float(reconstruction_loss.detach().cpu()):.6f} "
                f"val={selection_metric:.6f} effective_k={metrics['effective_experts']:.3f}",
                flush=True,
            )
            model.train()

    if best_state is None:
        raise AssertionError("training completed without validation")
    current = model.state_dict()
    current.update(best_state)
    model.load_state_dict(current)
    final_metrics, arrays = evaluate(
        model,
        validation_loader,
        device=device,
        sample_weights=validation_weights,
        temperature=args.temperature,
        true_labels=validation_labels,
    )
    np.savez_compressed(
        output_dir / "routes_validation.npz",
        sample_ids=np.asarray(validation_ids, dtype=str),
        groups=np.asarray(selection.validation[args.group_column].astype(str), dtype=str),
        organs=np.asarray(selection.validation[args.organ_column].astype(str), dtype=str),
        **validation_probe_arrays,
        **arrays,
    )
    repeated_mask_metrics: dict[str, Any] = {str(args.mask_seed): final_metrics}
    repeated_mask_artifacts: dict[str, str] = {
        str(args.mask_seed): sha256_file(output_dir / "routes_validation.npz")
    }
    for repeated_seed in args.repeated_mask_seeds:
        repeated_seed = int(repeated_seed)
        if repeated_seed == int(args.mask_seed):
            continue
        repeated_dataset = DeterministicMaskedExpressionDataset(
            validation_expression,
            validation_ids,
            normalization="log1p_tpm",
            mask_ratio=args.mask_ratio,
            mask_token=args.mask_token,
            seed=repeated_seed,
            phase="latent_validation",
            fixed_masks=True,
        )
        repeated_loader = DataLoader(
            repeated_dataset,
            batch_size=args.validation_batch_size,
            shuffle=False,
            num_workers=args.num_workers,
            worker_init_fn=seed_data_worker,
            generator=generator,
        )
        repeated_metrics, repeated_arrays = evaluate(
            model,
            repeated_loader,
            device=device,
            sample_weights=validation_weights,
            temperature=args.temperature,
            true_labels=validation_labels,
        )
        repeated_path = output_dir / f"routes_validation_mask{repeated_seed}.npz"
        np.savez_compressed(
            repeated_path,
            sample_ids=np.asarray(validation_ids, dtype=str),
            groups=np.asarray(
                selection.validation[args.group_column].astype(str), dtype=str
            ),
            organs=np.asarray(
                selection.validation[args.organ_column].astype(str), dtype=str
            ),
            **validation_probe_arrays,
            **repeated_arrays,
        )
        repeated_mask_metrics[str(repeated_seed)] = repeated_metrics
        repeated_mask_artifacts[str(repeated_seed)] = sha256_file(repeated_path)
    torch.save(
        {
            "schema_version": 1,
            "mode": args.mode,
            "training_seed": int(args.seed),
            "best_update": int(best_update),
            "pooled_checkpoint_sha256": metadata["hashes"]["pooled_checkpoint_sha256"],
            "config": metadata["config"],
            "label_names": label_names,
            "adapter_router_state_dict": best_state,
        },
        output_dir / "best_adapter_router.pt",
    )
    metadata.update({
        "status": "complete",
        "best_update": int(best_update),
        "best_validation_mse": float(best_metric),
        "elapsed_seconds": float(time.time() - start_time),
        "validation_metrics": final_metrics,
        "repeated_mask_metrics": repeated_mask_metrics,
        "artifacts": {
            "adapter_router_sha256": sha256_file(output_dir / "best_adapter_router.pt"),
            "routes_validation_sha256": sha256_file(output_dir / "routes_validation.npz"),
            "repeated_mask_route_sha256": repeated_mask_artifacts,
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
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--train-split", default="train")
    parser.add_argument("--validation-split", default="calibration")
    parser.add_argument("--train-filter-column", default="balanced_train")
    parser.add_argument("--sample-id-column", default="sample_id")
    parser.add_argument("--organ-column", default="organ")
    parser.add_argument("--group-column", default="series_group_id")
    parser.add_argument("--random-shard-column", default="random_shard")
    parser.add_argument("--num-experts", type=int, default=5)
    parser.add_argument("--adapter-dim", type=int, default=64)
    parser.add_argument("--router-hidden-dim", type=int, default=128)
    parser.add_argument("--max-updates", type=int, default=1500)
    parser.add_argument("--validation-interval", type=int, default=150)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--validation-batch-size", type=int, default=8)
    parser.add_argument("--mask-ratio", type=float, default=0.30)
    parser.add_argument("--mask-token", type=float, default=-10.0)
    parser.add_argument("--mask-seed", type=int, default=271828)
    parser.add_argument(
        "--repeated-mask-seeds", type=int, nargs="+", default=[271828, 271829, 271830]
    )
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--load-balance-weight", type=float, default=0.05)
    parser.add_argument("--entropy-weight", type=float, default=0.01)
    parser.add_argument("--router-supervision-weight", type=float, default=0.1)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument(
        "--use-amp", action=argparse.BooleanOptionalAction, default=True
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = run_training(args)
    print(json.dumps({
        "status": result["status"],
        "mode": result["mode"],
        "training_seed": result["training_seed"],
        "best_update": result["best_update"],
        "validation_metrics": result["validation_metrics"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
