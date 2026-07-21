#!/usr/bin/env python3
"""Cache the single locked test access for fixed organ/random K5 banks.

The cache reloads five already-trained residual-expert banks (organ, legacy
row-random, and three study-preserving random controls) over one frozen pooled
trunk.  It scores only the separately sealed test assignment artifact,
masks the complete frozen score-gene panel for every forward pass, and applies
an already-frozen calibration-only K5 router to those same target-hidden
features.  No model fitting or checkpoint selection occurs here.

Array convention
----------------
Every ``*_expert_masked`` bank array has axes ``(sample, expert, score_gene)``.
Targets, the train-only organ gene-mean baseline, and pooled predictions have
axes ``(sample, score_gene)``.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch import nn


ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = ROOT / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from train_latent_moe import ResidualExpert, load_frozen_trunk  # noqa: E402
from train_manifest import (  # noqa: E402
    balanced_validation_weights,
    load_expression_rows,
    read_manifest,
    sha256_file,
    sha256_json,
    sha256_lines,
    validate_expression_metadata,
)


SCHEMA_VERSION = 1
CANONICAL_ORGANS = (
    "adipose",
    "brain",
    "liver",
    "skeletal_muscle",
    "skin",
)
CANONICAL_RANDOM_SHARDS = tuple(f"random_{index}" for index in range(5))
GROUP_RANDOM_AXES = (
    "random_group_k5_p17",
    "random_group_k5_p42",
    "random_group_k5_p101",
)
ORGAN_TO_LABEL = {name: index for index, name in enumerate(CANONICAL_ORGANS)}
RANDOM_TO_LABEL = {
    name: index for index, name in enumerate(CANONICAL_RANDOM_SHARDS)
}
REQUIRED_ASSIGNMENT_COLUMNS = (
    "sample_id",
    "utility_split",
    "split",
    "organ",
    "series_group_id",
    "random_shard",
    "organ_k5",
    "random_k5",
    *GROUP_RANDOM_AXES,
)


def _sha256_array(values: np.ndarray) -> str:
    values = np.asarray(values)
    digest = hashlib.sha256()
    digest.update(str(values.shape).encode("utf-8"))
    if values.dtype.kind in {"U", "S", "O"}:
        digest.update(b"<unicode>\0")
        for value in values.astype(str).ravel(order="C"):
            digest.update(value.encode("utf-8"))
            digest.update(b"\0")
    else:
        contiguous = np.ascontiguousarray(values)
        digest.update(contiguous.dtype.str.encode("ascii"))
        digest.update(contiguous.tobytes(order="C"))
    return digest.hexdigest()


def _assignment_hash(frame: pd.DataFrame, source_column: str) -> str:
    return sha256_lines(
        f"{row.sample_id}\t{getattr(row, source_column)}"
        for row in frame[["sample_id", source_column]].itertuples(index=False)
    )


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _parse_named_paths(values: Iterable[str]) -> dict[str, Path]:
    output: dict[str, Path] = {}
    for raw in values:
        if "=" not in raw:
            raise ValueError("group-random-bank must use AXIS=PATH syntax")
        name, path = raw.split("=", 1)
        if name in output:
            raise ValueError(f"duplicate group-random bank {name!r}")
        output[name] = Path(path)
    if set(output) != set(GROUP_RANDOM_AXES):
        raise ValueError(
            f"group-random banks must be exactly {list(GROUP_RANDOM_AXES)}"
        )
    return output


def _write_deterministic_npz(path: Path, arrays: dict[str, np.ndarray]) -> None:
    """Write an ``np.load`` archive with fixed ZIP member metadata."""
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        with zipfile.ZipFile(
            handle, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archive:
            for name in sorted(arrays):
                value = np.asarray(arrays[name])
                if value.dtype.kind == "O":
                    raise ValueError(f"cache array {name!r} may not use object dtype")
                payload = io.BytesIO()
                np.lib.format.write_array(payload, value, allow_pickle=False)
                member = zipfile.ZipInfo(
                    f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0)
                )
                member.compress_type = zipfile.ZIP_DEFLATED
                member.external_attr = 0o600 << 16
                archive.writestr(
                    member,
                    payload.getvalue(),
                    compress_type=zipfile.ZIP_DEFLATED,
                    compresslevel=9,
                )
    os.replace(temporary, path)


def _resolve_device(requested: str) -> torch.device:
    if requested == "auto":
        return torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    device = torch.device(requested)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError(f"CUDA requested but unavailable: {requested}")
    return device


def mask_score_genes(
    expression: np.ndarray, score_gene_indices: np.ndarray, mask_token: float
) -> np.ndarray:
    """Copy a log-expression batch and hide every frozen score-panel gene."""
    values = np.asarray(expression, dtype=np.float32)
    indices = np.asarray(score_gene_indices, dtype=np.int64)
    if values.ndim != 2:
        raise ValueError("expression must be rank 2")
    if indices.ndim != 1 or not len(indices):
        raise ValueError("score_gene_indices must be a nonempty rank-1 array")
    if len(np.unique(indices)) != len(indices):
        raise ValueError("score_gene_indices contains duplicates")
    if indices.min() < 0 or indices.max() >= values.shape[1]:
        raise ValueError("score_gene_indices contains an out-of-range index")
    output = values.copy()
    output[:, indices] = np.float32(mask_token)
    return output


def _truthy(values: pd.Series, *, column: str) -> np.ndarray:
    if pd.api.types.is_bool_dtype(values.dtype):
        return values.fillna(False).to_numpy(dtype=bool)
    normalized = values.fillna("false").astype(str).str.strip().str.lower()
    allowed = {"true", "false", "1", "0", "yes", "no", "y", "n"}
    invalid = sorted(set(normalized) - allowed)
    if invalid:
        raise ValueError(f"manifest column {column!r} has invalid booleans: {invalid[:3]}")
    return normalized.isin({"true", "1", "yes", "y"}).to_numpy(dtype=bool)


def _validate_source_manifest(
    frame: pd.DataFrame,
    *,
    sample_id_column: str,
    organ_column: str,
    group_column: str,
    split_column: str,
    random_shard_column: str,
    train_filter_column: str,
) -> pd.DataFrame:
    required = {
        sample_id_column,
        organ_column,
        group_column,
        split_column,
        random_shard_column,
        train_filter_column,
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"source manifest lacks required columns: {missing}")
    output = frame.copy()
    for column in (sample_id_column, organ_column, group_column, split_column):
        if output[column].isna().any():
            raise ValueError(f"source manifest column {column!r} contains missing values")
        output[column] = output[column].astype(str)
    if output[sample_id_column].duplicated().any():
        raise ValueError("source manifest contains duplicate sample IDs")
    split_counts = output.groupby(group_column)[split_column].nunique()
    leaked = split_counts[split_counts > 1]
    if not leaked.empty:
        raise ValueError(
            "connected study groups cross source splits: "
            f"{leaked.index.astype(str).tolist()[:5]}"
        )
    return output


def _validate_sealed_assignments(
    assignments_path: Path,
    report_path: Path,
    source: pd.DataFrame,
    *,
    manifest_sha256: str,
    sample_id_column: str,
    organ_column: str,
    group_column: str,
    split_column: str,
    random_shard_column: str,
    test_split: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    assignments = pd.read_parquet(assignments_path)
    missing = [name for name in REQUIRED_ASSIGNMENT_COLUMNS if name not in assignments]
    if missing:
        raise ValueError(f"sealed test assignments lack required columns: {missing}")
    assignments = assignments[list(REQUIRED_ASSIGNMENT_COLUMNS)].copy()
    for column in (
        "sample_id",
        "utility_split",
        "split",
        "organ",
        "series_group_id",
        "random_shard",
    ):
        if assignments[column].isna().any():
            raise ValueError(f"sealed test column {column!r} contains missing values")
        assignments[column] = assignments[column].astype(str)
    if assignments["sample_id"].duplicated().any():
        raise ValueError("sealed test assignments contain duplicate sample IDs")
    if set(assignments["utility_split"]) != {str(test_split)} or set(
        assignments["split"]
    ) != {str(test_split)}:
        raise ValueError("sealed test assignments contain a non-test split")
    if assignments["sample_id"].tolist() != sorted(assignments["sample_id"]):
        raise ValueError("sealed test assignments must be sample_id-sorted")

    source_test = source.loc[source[split_column].eq(str(test_split))].copy()
    source_test = source_test.sort_values(sample_id_column).reset_index(drop=True)
    expected = source_test[
        [sample_id_column, organ_column, group_column, random_shard_column]
    ].copy()
    expected.columns = ["sample_id", "organ", "series_group_id", "random_shard"]
    for column in expected:
        if expected[column].isna().any():
            raise ValueError(f"source test column {column!r} contains missing values")
        expected[column] = expected[column].astype(str)
    if not assignments[
        ["sample_id", "organ", "series_group_id", "random_shard"]
    ].equals(expected):
        raise ValueError(
            "sealed test assignments do not exactly match source-manifest test IDs, "
            "organs, groups, and frozen random shards"
        )
    expected_organ_labels = assignments["organ"].map(ORGAN_TO_LABEL)
    expected_random_labels = assignments["random_shard"].map(RANDOM_TO_LABEL)
    if expected_organ_labels.isna().any():
        unknown = sorted(set(assignments["organ"]) - set(CANONICAL_ORGANS))
        raise ValueError(f"sealed test contains noncanonical organs: {unknown}")
    if expected_random_labels.isna().any():
        unknown = sorted(
            set(assignments["random_shard"]) - set(CANONICAL_RANDOM_SHARDS)
        )
        raise ValueError(f"sealed test contains noncanonical random shards: {unknown}")
    for column, expected_labels in (
        ("organ_k5", expected_organ_labels),
        ("random_k5", expected_random_labels),
    ):
        raw = assignments[column]
        if raw.isna().any():
            raise ValueError(f"sealed test column {column!r} contains missing values")
        try:
            labels = raw.to_numpy(dtype=np.int64)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"sealed test column {column!r} must contain integers") from exc
        if not np.array_equal(labels, expected_labels.to_numpy(dtype=np.int64)):
            raise ValueError(f"sealed test {column} differs from its canonical mapping")
        if set(labels) != set(range(5)):
            raise ValueError(f"sealed test {column} does not cover all five labels")
        assignments[column] = labels
    for axis in GROUP_RANDOM_AXES:
        raw = assignments[axis]
        if raw.isna().any():
            raise ValueError(f"sealed test column {axis!r} contains missing values")
        try:
            labels = raw.to_numpy(dtype=np.int64)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"sealed test column {axis!r} must contain integers") from exc
        if np.any(labels < 0) or np.any(labels >= 5):
            raise ValueError(f"sealed test {axis} labels fall outside [0, 5)")
        assignments[axis] = labels
        group_counts = assignments.groupby("series_group_id")[axis].nunique()
        if (group_counts > 1).any():
            raise ValueError(f"sealed test {axis} splits a connected study")

    report = json.loads(report_path.read_text())
    if report.get("status") != "complete" or report.get("sealed") is not True:
        raise ValueError("sealed test report is not a complete sealed artifact")
    if report.get("test_accessed") is not False:
        raise ValueError("sealed assignment report must precede test expression access")
    if report.get("test_expression_accessed") is not False or report.get(
        "test_targets_accessed"
    ) is not False:
        raise ValueError("sealed assignment report unexpectedly accessed test expression")
    hashes = report.get("hashes")
    if not isinstance(hashes, dict):
        raise ValueError("sealed test report lacks hashes")
    required_hashes = {
        "manifest_sha256": manifest_sha256,
        "sealed_test_assignments_sha256": sha256_file(assignments_path),
        "test_sample_ids_sha256": sha256_lines(assignments["sample_id"].tolist()),
        "test_organ_assignment_sha256": _assignment_hash(assignments, "organ"),
        "test_random_shard_assignment_sha256": _assignment_hash(
            assignments, "random_shard"
        ),
        **{
            f"test_{axis}_assignment_sha256": _assignment_hash(assignments, axis)
            for axis in GROUP_RANDOM_AXES
        },
    }
    for name, expected_hash in required_hashes.items():
        if hashes.get(name) != expected_hash:
            raise ValueError(f"sealed test report hash mismatch for {name}")
    if int(report.get("counts", {}).get("test", -1)) != len(assignments):
        raise ValueError("sealed test report row count differs from assignments")
    expected_mappings = {
        "organ_k5": ORGAN_TO_LABEL,
        "random_k5": RANDOM_TO_LABEL,
        **{
            axis: {
                f"random_group_{index}": index for index in range(5)
            }
            for axis in GROUP_RANDOM_AXES
        },
    }
    if report.get("mappings") != expected_mappings:
        raise ValueError("sealed test report canonical mappings changed")
    return assignments, report


class ExpertBank(nn.Module):
    """Five residual experts with no router or trainable trunk."""

    def __init__(self, hidden_dim: int, adapter_dim: int, num_experts: int = 5):
        super().__init__()
        self.experts = nn.ModuleList(
            ResidualExpert(hidden_dim, adapter_dim) for _ in range(num_experts)
        )

    def forward(self, hidden: torch.Tensor, base: torch.Tensor) -> torch.Tensor:
        residual = torch.stack([expert(hidden) for expert in self.experts], dim=1)
        return base.unsqueeze(1) + residual


def _require_metadata_hash(
    metadata: dict[str, Any], name: str, expected: str, *, bank_name: str
) -> None:
    observed = metadata.get("hashes", {}).get(name)
    if observed != expected:
        raise ValueError(f"{bank_name} bank hash mismatch for {name}")


def load_expert_bank(
    bank_dir: str | Path,
    *,
    expected_axis: str,
    hidden_dim: int,
    score_gene_count: int,
    expected_hashes: dict[str, str],
    device: torch.device,
    expected_seed: int | None = None,
    expected_final_update: int = 1500,
) -> tuple[ExpertBank, dict[str, Any]]:
    """Strictly validate and reload one completed fixed K5 expert bank."""
    path = Path(bank_dir)
    checkpoint_path = path / "final_experts.pt"
    metadata_path = path / "run_metadata.json"
    for required in (path / "COMPLETE", checkpoint_path, metadata_path):
        if not required.is_file():
            raise FileNotFoundError(required)
    metadata = json.loads(metadata_path.read_text())
    if metadata.get("status") != "complete":
        raise ValueError(f"{expected_axis} bank is not complete")
    if metadata.get("axis") != expected_axis:
        raise ValueError(f"bank axis {metadata.get('axis')!r} != {expected_axis!r}")
    if metadata.get("test_accessed") is not False:
        raise ValueError(f"{expected_axis} bank accessed test")
    if metadata.get("mechanical_only") is not False:
        raise ValueError(f"{expected_axis} bank is mechanical-only")
    config = metadata.get("config")
    if not isinstance(config, dict):
        raise ValueError(f"{expected_axis} bank lacks config")
    expected_config = {
        "axis": expected_axis,
        "num_experts": 5,
        "router_trainable": False,
        "final_update": int(expected_final_update),
        "score_gene_count": int(score_gene_count),
        "checkpoint_policy": "predetermined_final_update",
    }
    for name, expected_value in expected_config.items():
        if config.get(name) != expected_value:
            raise ValueError(
                f"{expected_axis} bank config {name}={config.get(name)!r}, "
                f"expected {expected_value!r}"
            )
    adapter_dim = int(config.get("adapter_dim", 0))
    if adapter_dim < 1:
        raise ValueError(f"{expected_axis} bank has invalid adapter_dim")
    seed = int(metadata.get("training_seed", -1))
    if expected_seed is not None and seed != int(expected_seed):
        raise ValueError(f"{expected_axis} bank seed {seed} != {expected_seed}")
    for name, expected_hash in expected_hashes.items():
        _require_metadata_hash(
            metadata, name, expected_hash, bank_name=expected_axis
        )
    actual_checkpoint_hash = sha256_file(checkpoint_path)
    if metadata.get("artifacts", {}).get("final_experts_sha256") != actual_checkpoint_hash:
        raise ValueError(f"{expected_axis} final-expert hash differs from metadata")
    resolved_hash = metadata.get("hashes", {}).get("resolved_config_sha256")
    if resolved_hash is not None and resolved_hash != sha256_json(config):
        raise ValueError(f"{expected_axis} resolved config hash mismatch")

    try:
        checkpoint = torch.load(
            checkpoint_path, map_location="cpu", weights_only=False
        )
    except TypeError:
        checkpoint = torch.load(checkpoint_path, map_location="cpu")
    if checkpoint.get("axis") != expected_axis:
        raise ValueError(f"{expected_axis} checkpoint axis mismatch")
    if int(checkpoint.get("training_seed", -1)) != seed:
        raise ValueError(f"{expected_axis} checkpoint seed mismatch")
    if int(checkpoint.get("final_update", -1)) != int(expected_final_update):
        raise ValueError(f"{expected_axis} checkpoint final update mismatch")
    if checkpoint.get("config") != config:
        raise ValueError(f"{expected_axis} checkpoint config differs from metadata")
    if checkpoint.get("pooled_checkpoint_sha256") != expected_hashes[
        "pooled_checkpoint_sha256"
    ]:
        raise ValueError(f"{expected_axis} checkpoint pooled-trunk hash mismatch")
    state = checkpoint.get("expert_state_dict")
    if not isinstance(state, dict) or not state:
        raise ValueError(f"{expected_axis} checkpoint lacks expert_state_dict")
    model = ExpertBank(hidden_dim, adapter_dim, num_experts=5)
    model.load_state_dict(state, strict=True)
    model.requires_grad_(False)
    model.eval()
    model.to(device)
    return model, {
        "axis": expected_axis,
        "training_seed": seed,
        "config": config,
        "hashes": {
            str(name): str(value)
            for name, value in metadata.get("hashes", {}).items()
            if isinstance(value, str)
        },
        "bank_dir": str(path.resolve()),
        "run_metadata_sha256": sha256_file(metadata_path),
        "final_experts_sha256": actual_checkpoint_hash,
    }


def _load_router(
    artifact_path: Path,
    report_path: Path,
    *,
    genes: list[str],
    score_gene_indices: np.ndarray,
    mask_token: float,
    expected_hashes: dict[str, str],
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    report = json.loads(report_path.read_text())
    if report.get("status") != "complete" or report.get("test_accessed") is not False:
        raise ValueError("router report is not a pre-test complete artifact")
    if report.get("test_features_loaded") is not False:
        raise ValueError("router report already loaded test features")
    if report.get("target_hiding", {}).get(
        "score_genes_masked_for_every_sample"
    ) is not True:
        raise ValueError("router report does not assert score-gene target hiding")
    hashes = report.get("hashes", {})
    if hashes.get("router_artifact_sha256") != sha256_file(artifact_path):
        raise ValueError("router artifact hash differs from router report")
    router_hash_names = {
        "expression_parquet_sha256": "expression_sha256",
        "expression_metadata_sha256": "expression_metadata_sha256",
        "source_manifest_sha256": "manifest_sha256",
        "axis_definitions_sha256": "axis_definitions_sha256",
    }
    for report_name, expected_name in router_hash_names.items():
        if hashes.get(report_name) != expected_hashes[expected_name]:
            raise ValueError(f"router input hash mismatch for {report_name}")
    if hashes.get("gene_order_sha256") != sha256_lines(genes):
        raise ValueError("router gene-order hash differs from expression")
    config = report.get("config", {})
    if float(config.get("mask_token", np.nan)) != float(mask_token):
        raise ValueError("router mask token differs from frozen trunk")

    required = {
        "gene_names",
        "score_gene_indices",
        "mask_token",
        "k5_full_classes",
        "k5_full_scaler_mean",
        "k5_full_scaler_scale",
        "k5_full_coefficients",
        "k5_full_intercepts",
    }
    with np.load(artifact_path, allow_pickle=False) as archive:
        missing = sorted(required - set(archive.files))
        if missing:
            raise ValueError(f"router artifact lacks required arrays: {missing}")
        arrays = {name: np.asarray(archive[name]) for name in required}
    if arrays["gene_names"].astype(str).tolist() != genes:
        raise ValueError("router artifact gene order differs from expression")
    if not np.array_equal(
        arrays["score_gene_indices"].astype(np.int64), score_gene_indices
    ):
        raise ValueError("router artifact score-gene indices changed")
    if float(np.asarray(arrays["mask_token"]).item()) != float(mask_token):
        raise ValueError("router artifact mask token changed")
    classes = arrays["k5_full_classes"].astype(str)
    if not np.array_equal(classes, np.asarray(CANONICAL_ORGANS)):
        raise ValueError("router K5 classes differ from canonical organ order")
    full = report.get("full_calibration_k5", {})
    checks = {
        "scaler_mean_sha256": arrays["k5_full_scaler_mean"],
        "scaler_scale_sha256": arrays["k5_full_scaler_scale"],
        "coefficient_sha256": arrays["k5_full_coefficients"],
        "intercept_sha256": arrays["k5_full_intercepts"],
    }
    for name, values in checks.items():
        if full.get(name) != _sha256_array(values):
            raise ValueError(f"router report parameter hash mismatch for {name}")
    n_genes = len(genes)
    if arrays["k5_full_scaler_mean"].shape != (n_genes,):
        raise ValueError("router scaler mean has wrong shape")
    if arrays["k5_full_scaler_scale"].shape != (n_genes,):
        raise ValueError("router scaler scale has wrong shape")
    if arrays["k5_full_coefficients"].shape != (5, n_genes):
        raise ValueError("router K5 coefficients have wrong shape")
    if arrays["k5_full_intercepts"].shape != (5,):
        raise ValueError("router K5 intercepts have wrong shape")
    if np.any(arrays["k5_full_scaler_scale"] <= 0):
        raise ValueError("router scaler has a nonpositive scale")
    return arrays, {
        "router_artifact": str(artifact_path.resolve()),
        "router_report": str(report_path.resolve()),
        "router_artifact_sha256": sha256_file(artifact_path),
        "router_report_sha256": sha256_file(report_path),
        "router_was_prefrozen": True,
        "router_refit_during_test_cache": False,
        "target_hiding_verified": True,
    }


def _apply_router(
    masked_features: np.ndarray, router: dict[str, np.ndarray]
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    features = np.asarray(masked_features, dtype=np.float64)
    mean = router["k5_full_scaler_mean"].astype(np.float64)
    scale = router["k5_full_scaler_scale"].astype(np.float64)
    coefficients = router["k5_full_coefficients"].astype(np.float64)
    intercepts = router["k5_full_intercepts"].astype(np.float64)
    classes = router["k5_full_classes"].astype(str)
    logits = ((features - mean) / scale) @ coefficients.T + intercepts
    logits -= logits.max(axis=1, keepdims=True)
    probability = np.exp(logits)
    probability /= probability.sum(axis=1, keepdims=True)
    if not np.isfinite(probability).all() or not np.allclose(
        probability.sum(axis=1), 1.0, atol=1e-10
    ):
        raise RuntimeError("frozen K5 router produced invalid probabilities")
    predicted = classes[np.argmax(probability, axis=1)]
    return probability.astype(np.float64), predicted.astype(str), classes


def _baseline(
    source: pd.DataFrame,
    expression_path: Path,
    *,
    score_gene_indices: np.ndarray,
    test_organs: np.ndarray,
    gene_order: list[str],
    sample_id_column: str,
    organ_column: str,
    group_column: str,
    split_column: str,
    train_filter_column: str,
    train_split: str,
    test_split: str,
) -> tuple[np.ndarray, dict[str, Any]]:
    eligible = _truthy(source[train_filter_column], column=train_filter_column)
    fit = source.loc[eligible & source[split_column].eq(str(train_split))].copy()
    fit = fit.sort_values(sample_id_column).reset_index(drop=True)
    if fit.empty:
        raise ValueError("train-only baseline fit contains no rows")
    if set(fit[organ_column]) != set(CANONICAL_ORGANS):
        raise ValueError("train-only baseline fit does not cover canonical organs")
    test_groups = set(source.loc[source[split_column].eq(str(test_split)), group_column])
    if set(fit[group_column]) & test_groups:
        raise ValueError("baseline fit groups overlap test groups")
    fit_ids = fit[sample_id_column].astype(str).tolist()
    expression, info = load_expression_rows(
        expression_path, fit_ids, sample_id_column=sample_id_column
    )
    if list(info.gene_columns) != gene_order:
        raise ValueError("baseline expression gene order changed")
    if np.any(expression < 0):
        raise ValueError("baseline TPM expression contains negative values")
    score_values = np.log1p(expression[:, score_gene_indices]).astype(
        np.float32, copy=False
    )
    means: dict[str, np.ndarray] = {}
    for organ in CANONICAL_ORGANS:
        rows = fit[organ_column].astype(str).eq(organ).to_numpy()
        if not rows.any():
            raise ValueError(f"baseline has no train rows for {organ}")
        means[organ] = score_values[rows].mean(axis=0, dtype=np.float64).astype(
            np.float32
        )
    output = np.stack([means[str(organ)] for organ in test_organs]).astype(
        np.float32, copy=False
    )
    metadata = {
        "definition": "balanced-train-only organ-specific log1p gene mean",
        "fit_split": str(train_split),
        "fit_filter_column": train_filter_column,
        "n_fit_samples": len(fit_ids),
        "fit_sample_ids_sha256": sha256_lines(fit_ids),
        "fit_group_ids_sha256": sha256_lines(
            sorted(fit[group_column].astype(str).unique())
        ),
        "fit_organ_counts": {
            organ: int(fit[organ_column].astype(str).eq(organ).sum())
            for organ in CANONICAL_ORGANS
        },
        "test_targets_used_for_fit": False,
        "calibration_targets_used_for_fit": False,
        "fit_test_group_overlap": 0,
        "baseline_masked_sha256": _sha256_array(output),
    }
    return output, metadata


def build_cache(args: argparse.Namespace | SimpleNamespace) -> dict[str, Any]:
    protocol_path = Path(args.protocol)
    expression_path = Path(args.expression_parquet)
    expression_metadata_path = Path(args.expression_metadata)
    manifest_path = Path(args.manifest)
    pooled_checkpoint_path = Path(args.pooled_checkpoint)
    axis_definitions_path = Path(args.axis_definitions)
    assignments_path = Path(args.sealed_test_assignments)
    sealed_report_path = Path(args.sealed_test_report)
    router_artifact_path = Path(args.router_artifact)
    router_report_path = Path(args.router_report)
    organ_bank_dir = Path(args.organ_bank_dir)
    random_bank_dir = Path(args.random_bank_dir)
    group_random_bank_dirs = _parse_named_paths(
        getattr(args, "group_random_bank", ())
    )
    output_dir = Path(args.output_dir)
    required_files = (
        protocol_path,
        expression_path,
        expression_metadata_path,
        manifest_path,
        pooled_checkpoint_path,
        axis_definitions_path,
        assignments_path,
        sealed_report_path,
        router_artifact_path,
        router_report_path,
    )
    for path in required_files:
        if not path.is_file():
            raise FileNotFoundError(path)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "test_scores.npz"
    report_path = output_dir / "test_score_report.json"
    if output_path.exists() or report_path.exists():
        raise FileExistsError("test score cache output already exists")

    # Bind the exact frozen protocol to every bank before reading even one test
    # expression row.  A stale or edited protocol must fail at the firewall,
    # not only later when the completed caches are aggregated.
    protocol = json.loads(protocol_path.read_text())
    if (
        protocol.get("authorization", {}).get("requested_by_user") is not True
        or protocol.get("evidence_label", {}).get("internal_locked_replication")
        is not True
        or protocol.get("evidence_label", {}).get("independent_confirmation")
        is not False
    ):
        raise ValueError("protocol does not authorize the locked internal replication")
    protocol_hash = sha256_file(protocol_path)
    preflight_bank_dirs = {
        "organ_k5": organ_bank_dir,
        "random_k5": random_bank_dir,
        **group_random_bank_dirs,
    }
    for axis, bank_dir in preflight_bank_dirs.items():
        metadata_path = bank_dir / "run_metadata.json"
        if not metadata_path.is_file():
            raise FileNotFoundError(metadata_path)
        metadata = json.loads(metadata_path.read_text())
        if metadata.get("hashes", {}).get("protocol_sha256") != protocol_hash:
            raise ValueError(f"{axis} bank is not bound to the exact frozen protocol")

    sample_id_column = str(getattr(args, "sample_id_column", "sample_id"))
    organ_column = str(getattr(args, "organ_column", "organ"))
    group_column = str(getattr(args, "group_column", "series_group_id"))
    split_column = str(getattr(args, "split_column", "split"))
    random_shard_column = str(
        getattr(args, "random_shard_column", "random_shard")
    )
    train_filter_column = str(
        getattr(args, "train_filter_column", "balanced_train")
    )
    train_split = str(getattr(args, "train_split", "train"))
    test_split = str(getattr(args, "test_split", "test"))

    source = _validate_source_manifest(
        read_manifest(manifest_path),
        sample_id_column=sample_id_column,
        organ_column=organ_column,
        group_column=group_column,
        split_column=split_column,
        random_shard_column=random_shard_column,
        train_filter_column=train_filter_column,
    )
    manifest_hash = sha256_file(manifest_path)
    assignments, sealed_report = _validate_sealed_assignments(
        assignments_path,
        sealed_report_path,
        source,
        manifest_sha256=manifest_hash,
        sample_id_column=sample_id_column,
        organ_column=organ_column,
        group_column=group_column,
        split_column=split_column,
        random_shard_column=random_shard_column,
        test_split=test_split,
    )
    sample_ids = assignments["sample_id"].to_numpy(dtype=str)
    groups = assignments["series_group_id"].to_numpy(dtype=str)
    organs = assignments["organ"].to_numpy(dtype=str)
    organ_labels = assignments["organ_k5"].to_numpy(dtype=np.int64)
    random_labels = assignments["random_k5"].to_numpy(dtype=np.int64)
    sample_weights = balanced_validation_weights(
        assignments,
        organ_column="organ",
        group_column="series_group_id",
    ).astype(np.float64)

    device = _resolve_device(str(getattr(args, "device", "auto")))
    trunk, checkpoint_config, _checkpoint = load_frozen_trunk(
        pooled_checkpoint_path, device
    )
    if checkpoint_config.get("normalization") != "log1p_tpm":
        raise ValueError("confirmation requires a log1p_tpm frozen trunk")
    mask_token = float(checkpoint_config["mask_token"])
    expression, expression_info = load_expression_rows(
        expression_path, sample_ids, sample_id_column=sample_id_column
    )
    genes = list(expression_info.gene_columns)
    if genes != list(checkpoint_config["gene_list"]):
        raise ValueError("expression gene order differs from frozen trunk")
    expression_contract = validate_expression_metadata(
        expression_path,
        genes,
        metadata_path=expression_metadata_path,
    )
    with np.load(axis_definitions_path, allow_pickle=False) as definitions:
        required = {"score_gene_indices", "gene_names"}
        missing = sorted(required - set(definitions.files))
        if missing:
            raise ValueError(f"axis definitions lack required arrays: {missing}")
        score_gene_indices = np.asarray(
            definitions["score_gene_indices"], dtype=np.int64
        )
        definition_genes = definitions["gene_names"].astype(str).tolist()
    if definition_genes != genes:
        raise ValueError("axis-definition gene order differs from expression")
    # Validates rank, uniqueness, and range without retaining an extra full matrix.
    mask_score_genes(np.zeros((1, len(genes)), dtype=np.float32), score_gene_indices, mask_token)

    input_hashes = {
        "protocol_sha256": protocol_hash,
        "pooled_checkpoint_sha256": sha256_file(pooled_checkpoint_path),
        "expression_sha256": sha256_file(expression_path),
        "expression_metadata_sha256": sha256_file(expression_metadata_path),
        "manifest_sha256": manifest_hash,
        "axis_definitions_sha256": sha256_file(axis_definitions_path),
    }
    hidden_dim = int(trunk.gene_embedding.embedding_dim)
    expected_seed = getattr(args, "expected_seed", None)
    expected_seed = None if expected_seed is None else int(expected_seed)
    expected_final_update = int(getattr(args, "expected_final_update", 1500))
    bank_hashes = {
        name: input_hashes[name]
        for name in (
            "pooled_checkpoint_sha256",
            "expression_sha256",
            "manifest_sha256",
            "axis_definitions_sha256",
            "protocol_sha256",
        )
    }
    organ_bank, organ_bank_info = load_expert_bank(
        organ_bank_dir,
        expected_axis="organ_k5",
        hidden_dim=hidden_dim,
        score_gene_count=len(score_gene_indices),
        expected_hashes=bank_hashes,
        device=device,
        expected_seed=expected_seed,
        expected_final_update=expected_final_update,
    )
    random_bank, random_bank_info = load_expert_bank(
        random_bank_dir,
        expected_axis="random_k5",
        hidden_dim=hidden_dim,
        score_gene_count=len(score_gene_indices),
        expected_hashes=bank_hashes,
        device=device,
        expected_seed=expected_seed,
        expected_final_update=expected_final_update,
    )
    group_random_banks: dict[str, ExpertBank] = {}
    group_random_bank_info: dict[str, dict[str, Any]] = {}
    for axis in GROUP_RANDOM_AXES:
        bank, info = load_expert_bank(
            group_random_bank_dirs[axis],
            expected_axis=axis,
            hidden_dim=hidden_dim,
            score_gene_count=len(score_gene_indices),
            expected_hashes=bank_hashes,
            device=device,
            expected_seed=expected_seed,
            expected_final_update=expected_final_update,
        )
        group_random_banks[axis] = bank
        group_random_bank_info[axis] = info
    if organ_bank_info["training_seed"] != random_bank_info["training_seed"]:
        raise ValueError("organ and random banks use different training seeds")
    training_seed = int(organ_bank_info["training_seed"])
    if any(
        info["training_seed"] != training_seed
        for info in group_random_bank_info.values()
    ):
        raise ValueError("group-random banks use a different training seed")
    bank_common_hashes: dict[str, str] = {}
    for name in (
        "protocol_sha256",
        "partition_manifest_sha256",
        "score_gene_indices_sha256",
    ):
        organ_value = organ_bank_info["hashes"].get(name)
        random_value = random_bank_info["hashes"].get(name)
        if not organ_value or organ_value != random_value:
            raise ValueError(f"organ/random bank common hash mismatch for {name}")
        for axis, info in group_random_bank_info.items():
            if info["hashes"].get(name) != organ_value:
                raise ValueError(
                    f"organ/{axis} bank common hash mismatch for {name}"
                )
        bank_common_hashes[name] = organ_value
    expected_score_hash = sha256_lines(score_gene_indices.tolist())
    if bank_common_hashes["score_gene_indices_sha256"] != expected_score_hash:
        raise ValueError("bank score-gene hash differs from axis definitions")

    router, router_info = _load_router(
        router_artifact_path,
        router_report_path,
        genes=genes,
        score_gene_indices=score_gene_indices,
        mask_token=mask_token,
        expected_hashes=input_hashes,
    )

    if np.any(expression < 0) or not np.isfinite(expression).all():
        raise ValueError("test TPM expression contains invalid values")
    truth = np.log1p(expression).astype(np.float32, copy=False)
    masked_features = mask_score_genes(truth, score_gene_indices, mask_token)
    if not np.all(
        masked_features[:, score_gene_indices] == np.float32(mask_token)
    ):
        raise RuntimeError("test target-hiding assertion failed")
    blind_probability, blind_predicted, k5_classes = _apply_router(
        masked_features, router
    )

    baseline_masked, baseline_info = _baseline(
        source,
        expression_path,
        score_gene_indices=score_gene_indices,
        test_organs=organs,
        gene_order=genes,
        sample_id_column=sample_id_column,
        organ_column=organ_column,
        group_column=group_column,
        split_column=split_column,
        train_filter_column=train_filter_column,
        train_split=train_split,
        test_split=test_split,
    )

    n_samples = len(sample_ids)
    n_score = len(score_gene_indices)
    target_masked = truth[:, score_gene_indices].astype(np.float32, copy=True)
    pooled_masked = np.empty((n_samples, n_score), dtype=np.float32)
    organ_expert_masked = np.empty((n_samples, 5, n_score), dtype=np.float32)
    random_expert_masked = np.empty((n_samples, 5, n_score), dtype=np.float32)
    group_random_expert_masked = {
        axis: np.empty((n_samples, 5, n_score), dtype=np.float32)
        for axis in GROUP_RANDOM_AXES
    }
    batch_size = int(getattr(args, "batch_size", 8))
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    trunk.eval()
    organ_bank.eval()
    random_bank.eval()
    for bank in group_random_banks.values():
        bank.eval()
    with torch.inference_mode():
        for start in range(0, n_samples, batch_size):
            stop = min(n_samples, start + batch_size)
            batch = torch.from_numpy(masked_features[start:stop]).to(device)
            hidden = trunk.encode(batch)
            base = trunk.decode(hidden)
            organ_prediction = organ_bank(hidden, base)
            random_prediction = random_bank(hidden, base)
            group_random_predictions = {
                axis: bank(hidden, base)
                for axis, bank in group_random_banks.items()
            }
            index = torch.as_tensor(score_gene_indices, device=device)
            pooled_masked[start:stop] = base.index_select(1, index).float().cpu().numpy()
            organ_expert_masked[start:stop] = (
                organ_prediction.index_select(2, index).float().cpu().numpy()
            )
            random_expert_masked[start:stop] = (
                random_prediction.index_select(2, index).float().cpu().numpy()
            )
            for axis, prediction in group_random_predictions.items():
                group_random_expert_masked[axis][start:stop] = (
                    prediction.index_select(2, index).float().cpu().numpy()
                )
    numeric = (
        target_masked,
        baseline_masked,
        pooled_masked,
        organ_expert_masked,
        random_expert_masked,
        *group_random_expert_masked.values(),
        blind_probability,
    )
    if not all(np.isfinite(value).all() for value in numeric):
        raise RuntimeError("test score cache contains nonfinite numeric values")

    arrays: dict[str, np.ndarray] = {
        "sample_ids": sample_ids.astype(str),
        "groups": groups.astype(str),
        "organs": organs.astype(str),
        "sample_weights": sample_weights,
        "organ_labels": organ_labels,
        "random_labels": random_labels,
        "organ_label_names": np.asarray(CANONICAL_ORGANS, dtype=str),
        "random_label_names": np.asarray(CANONICAL_RANDOM_SHARDS, dtype=str),
        "score_gene_indices": score_gene_indices.astype(np.int64),
        "score_gene_names": np.asarray(genes, dtype=str)[score_gene_indices],
        "target_masked": target_masked,
        "baseline_masked": baseline_masked,
        "pooled_masked": pooled_masked,
        "organ_expert_masked": organ_expert_masked,
        "random_expert_masked": random_expert_masked,
        "blind_k5_probabilities": blind_probability,
        "blind_k5_predicted_organ": blind_predicted.astype(str),
        "k5_full_classes": k5_classes.astype(str),
    }
    for axis in GROUP_RANDOM_AXES:
        arrays[f"{axis}_labels"] = assignments[axis].to_numpy(dtype=np.int64)
        arrays[f"{axis}_expert_masked"] = group_random_expert_masked[axis]
    array_hashes = {name: _sha256_array(value) for name, value in arrays.items()}
    base_report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "complete",
        "research_stage": "stage1_organ_k_confirmation",
        "experiment": "fixed_bank_locked_test_score_cache",
        "internal_locked_replication": True,
        "independent_confirmation": False,
        "mechanical_only": False,
        "test_accessed": True,
        "test_expression_accessed": True,
        "test_targets_accessed": True,
        "model_fitting_during_test_access": False,
        "training_seed": training_seed,
        "counts": {
            "test_samples": n_samples,
            "test_groups": int(len(np.unique(groups))),
            "genes": len(genes),
            "score_genes": n_score,
            "experts_per_bank": 5,
        },
        "array_contract": {
            "row_arrays": [
                "sample_ids",
                "groups",
                "organs",
                "sample_weights",
                "organ_labels",
                "random_labels",
                "blind_k5_predicted_organ",
                *[f"{axis}_labels" for axis in GROUP_RANDOM_AXES],
            ],
            "sample_score_arrays": [
                "target_masked",
                "baseline_masked",
                "pooled_masked",
            ],
            "expert_array_axes": ["sample", "expert", "score_gene"],
            "organ_expert_masked_shape": list(organ_expert_masked.shape),
            "random_expert_masked_shape": list(random_expert_masked.shape),
            "group_random_expert_masked_shapes": {
                axis: list(group_random_expert_masked[axis].shape)
                for axis in GROUP_RANDOM_AXES
            },
            "blind_k5_probabilities_shape": list(blind_probability.shape),
        },
        "labels": {
            "organ_k5": ORGAN_TO_LABEL,
            "random_k5": RANDOM_TO_LABEL,
            **{
                axis: {f"random_group_{index}": index for index in range(5)}
                for axis in GROUP_RANDOM_AXES
            },
            "router_k5_class_order": k5_classes.tolist(),
        },
        "target_hiding": {
            "all_score_genes_replaced_by_mask_token": True,
            "mask_token": mask_token,
            "score_gene_count": n_score,
            "score_gene_indices_sha256": sha256_lines(
                score_gene_indices.tolist()
            ),
            "masked_test_feature_sha256": _sha256_array(masked_features),
            "same_masked_features_used_for_router_and_experts": True,
        },
        "baseline": baseline_info,
        "router": router_info,
        "banks": {
            "organ_k5": organ_bank_info,
            "random_k5": random_bank_info,
            **group_random_bank_info,
        },
        "source_files": {
            "expression_parquet": str(expression_path.resolve()),
            "expression_metadata": str(expression_metadata_path.resolve()),
            "manifest": str(manifest_path.resolve()),
            "pooled_checkpoint": str(pooled_checkpoint_path.resolve()),
            "axis_definitions": str(axis_definitions_path.resolve()),
            "protocol": str(protocol_path.resolve()),
            "sealed_test_assignments": str(assignments_path.resolve()),
            "sealed_test_report": str(sealed_report_path.resolve()),
        },
        "hashes": {
            **input_hashes,
            **bank_common_hashes,
            "router_artifact_sha256": router_info["router_artifact_sha256"],
            "sealed_test_assignments_sha256": sha256_file(assignments_path),
            "sealed_test_report_sha256": sha256_file(sealed_report_path),
            "test_sample_ids_sha256": sha256_lines(sample_ids.tolist()),
            "test_group_ids_sha256": sha256_lines(groups.tolist()),
            "test_organ_assignment_sha256": _assignment_hash(assignments, "organ"),
            "test_random_shard_assignment_sha256": _assignment_hash(
                assignments, "random_shard"
            ),
            **{
                f"test_{axis}_assignment_sha256": _assignment_hash(
                    assignments, axis
                )
                for axis in GROUP_RANDOM_AXES
            },
            "gene_order_sha256": sha256_lines(genes),
            "resolved_config_sha256": sha256_json(
                {
                    "batch_size": batch_size,
                    "expected_final_update": expected_final_update,
                    "mask_token": mask_token,
                    "test_split": test_split,
                    "train_split": train_split,
                    "train_filter_column": train_filter_column,
                }
            ),
        },
        "content_sha256": array_hashes,
        "expression_contract": expression_contract,
        "sealed_assignment_guardrail": sealed_report.get("guardrail"),
    }
    arrays["metadata_json"] = np.asarray(
        json.dumps(base_report, sort_keys=True), dtype=str
    )
    _write_deterministic_npz(output_path, arrays)
    report = {
        **base_report,
        "hashes": {
            **base_report["hashes"],
            "test_scores_sha256": sha256_file(output_path),
        },
        "artifacts": {
            "test_scores": str(output_path.resolve()),
            "test_scores_sha256": sha256_file(output_path),
            "test_score_report": str(report_path.resolve()),
        },
    }
    _atomic_json(report_path, report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expression-parquet", required=True)
    parser.add_argument("--expression-metadata", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--pooled-checkpoint", required=True)
    parser.add_argument("--axis-definitions", required=True)
    parser.add_argument("--sealed-test-assignments", required=True)
    parser.add_argument("--sealed-test-report", required=True)
    parser.add_argument("--organ-bank-dir", required=True)
    parser.add_argument("--random-bank-dir", required=True)
    parser.add_argument(
        "--group-random-bank",
        action="append",
        required=True,
        help="AXIS=PATH; repeat for the three study-preserving random axes",
    )
    parser.add_argument("--router-artifact", required=True)
    parser.add_argument("--router-report", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--expected-seed", type=int)
    parser.add_argument("--expected-final-update", type=int, default=1500)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--sample-id-column", default="sample_id")
    parser.add_argument("--organ-column", default="organ")
    parser.add_argument("--group-column", default="series_group_id")
    parser.add_argument("--split-column", default="split")
    parser.add_argument("--random-shard-column", default="random_shard")
    parser.add_argument("--train-filter-column", default="balanced_train")
    parser.add_argument("--train-split", default="train")
    parser.add_argument("--test-split", default="test")
    return parser


def main() -> None:
    report = build_cache(build_parser().parse_args())
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
