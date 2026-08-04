#!/usr/bin/env python3
"""Evaluate frozen K8 experts as organ-label compatibility scores.

This is a read-only GTEx calibration-development audit.  It trains no neural
weights and never selects a model seed.  Each sample is paired with its true organ
assignment and all seven deterministic wrong assignments.  The expert compatibility
margin is compared with train-only raw-centroid and PCA-centroid margins.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import rankdata
from sklearn.decomposition import PCA


ORGANS = (
    "adipose",
    "brain",
    "colon",
    "heart",
    "liver",
    "lung",
    "skeletal_muscle",
    "skin",
)
SEEDS = (17, 42, 101)


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_lines(values: list[str]) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(value.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def sha256_array(values: np.ndarray) -> str:
    values = np.asarray(values)
    digest = hashlib.sha256()
    digest.update(str(values.shape).encode("utf-8"))
    contiguous = np.ascontiguousarray(values)
    digest.update(contiguous.dtype.str.encode("utf-8"))
    digest.update(contiguous.tobytes())
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise TypeError(f"{path} is not a JSON object")
    return value


def _auc(labels: np.ndarray, scores: np.ndarray) -> float:
    labels = np.asarray(labels, dtype=np.int8)
    scores = np.asarray(scores, dtype=np.float64)
    if labels.shape != scores.shape or labels.ndim != 1:
        raise ValueError("AUC inputs must be equal one-dimensional arrays")
    if not np.isfinite(scores).all():
        raise ValueError("AUC scores contain nonfinite values")
    n1 = int(labels.sum())
    n0 = int(len(labels) - n1)
    if n0 == 0 or n1 == 0:
        raise ValueError("AUC requires both classes")
    ranks = rankdata(scores, method="average")
    return float((ranks[labels == 1].sum() - n1 * (n1 + 1) / 2.0) / (n0 * n1))


def compatibility_margin(errors: np.ndarray) -> np.ndarray:
    """Return assigned-label error minus the best label error for every assignment."""
    values = np.asarray(errors, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != len(ORGANS):
        raise ValueError("compatibility errors must have one column per organ")
    if not np.isfinite(values).all():
        raise ValueError("compatibility errors contain nonfinite values")
    return values - values.min(axis=1, keepdims=True)


def macro_organ_auc(
    margins: np.ndarray,
    true_labels: np.ndarray,
    row_indices: dict[int, np.ndarray] | None = None,
) -> float:
    assignments = np.arange(len(ORGANS), dtype=np.int64)
    aucs = []
    for organ_index in range(len(ORGANS)):
        indices = (
            np.flatnonzero(true_labels == organ_index)
            if row_indices is None
            else np.asarray(row_indices[organ_index], dtype=np.int64)
        )
        if len(indices) == 0:
            raise ValueError(f"organ {ORGANS[organ_index]} has no rows")
        labels = np.tile(assignments != organ_index, len(indices)).astype(np.int8)
        scores = margins[indices].reshape(-1)
        aucs.append(_auc(labels, scores))
    return float(np.mean(aucs))


def _centroid_errors(
    train: np.ndarray,
    train_labels: np.ndarray,
    evaluation: np.ndarray,
) -> np.ndarray:
    centroids = np.stack(
        [train[train_labels == index].mean(axis=0) for index in range(len(ORGANS))]
    )
    if not np.isfinite(centroids).all():
        raise ValueError("centroid computation failed")
    train_scale = train.std(axis=0, ddof=0)
    train_scale[train_scale < 1e-6] = 1.0
    return np.stack(
        [np.mean(np.square((evaluation - center) / train_scale), axis=1) for center in centroids],
        axis=1,
    )


def _bootstrap(
    margins: dict[str, np.ndarray],
    true_labels: np.ndarray,
    groups: np.ndarray,
    *,
    draws: int,
    seed: int,
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    values = {name: np.empty(draws, dtype=np.float64) for name in margins}
    by_organ_groups: dict[int, list[str]] = {}
    group_rows: dict[tuple[int, str], np.ndarray] = {}
    for organ_index in range(len(ORGANS)):
        organ_rows = np.flatnonzero(true_labels == organ_index)
        unique_groups = sorted(set(groups[organ_rows].astype(str)))
        if len(unique_groups) < 2:
            raise ValueError(f"organ {ORGANS[organ_index]} has fewer than two donors")
        by_organ_groups[organ_index] = unique_groups
        for group in unique_groups:
            group_rows[(organ_index, group)] = organ_rows[groups[organ_rows] == group]
    for draw in range(draws):
        rows: dict[int, np.ndarray] = {}
        for organ_index, unique_groups in by_organ_groups.items():
            selected = rng.choice(unique_groups, size=len(unique_groups), replace=True)
            rows[organ_index] = np.concatenate(
                [group_rows[(organ_index, str(group))] for group in selected]
            )
        for name, matrix in margins.items():
            values[name][draw] = macro_organ_auc(matrix, true_labels, rows)
    result: dict[str, Any] = {}
    for name, array in values.items():
        result[name] = {
            "ci95": np.quantile(array, [0.025, 0.975]).astype(float).tolist(),
            "draw_mean": float(array.mean()),
        }
    for seed_name in [name for name in margins if name.startswith("expert_seed")]:
        for baseline in ("raw_centroid", "pca64_centroid"):
            delta = values[seed_name] - values[baseline]
            result[f"{seed_name}_minus_{baseline}"] = {
                "ci95": np.quantile(delta, [0.025, 0.975]).astype(float).tolist(),
                "draw_mean": float(delta.mean()),
            }
    return result


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    protocol_path = Path(args.protocol)
    if sha256_file(protocol_path) != args.expected_protocol_sha256:
        raise ValueError("protocol SHA256 mismatch")
    protocol = _load_json(protocol_path)
    if protocol.get("status") != "frozen_gtex_k8_mislabel_development_protocol":
        raise ValueError("protocol is not frozen")
    expected_self = protocol["implementation"]["evaluator_sha256"]
    if expected_self != sha256_file(Path(__file__).resolve()):
        raise ValueError("evaluator hash differs from frozen implementation")
    inputs = protocol["inputs"]
    paths = {
        "expression": Path(args.expression_parquet),
        "manifest": Path(args.manifest),
        "router": Path(args.router_artifact),
        "candidate_ledger": Path(args.candidate_ledger),
    }
    for name, path in paths.items():
        if not path.is_file() or sha256_file(path) != inputs[f"{name}_sha256"]:
            raise ValueError(f"{name} input is absent or changed")
    ledger = _load_json(paths["candidate_ledger"])
    if ledger.get("best_seed_selection_allowed") is not False:
        raise ValueError("candidate ledger permits seed selection")
    manifest = pd.read_parquet(paths["manifest"])
    required = {"sample_id", "donor_id", "organ", "split"}
    if required - set(manifest):
        raise ValueError("manifest lacks required columns")
    if manifest["sample_id"].duplicated().any():
        raise ValueError("manifest repeats sample IDs")
    for column in required:
        manifest[column] = manifest[column].astype(str)
    if set(manifest["organ"]) != set(ORGANS):
        raise ValueError("manifest organ set changed")
    train_manifest = manifest.loc[manifest["split"].eq("train")].copy()
    calibration_manifest = manifest.loc[manifest["split"].eq("calibration")].copy()
    if sha256_lines(calibration_manifest["sample_id"].tolist()) != inputs["calibration_sample_ids_sha256"]:
        raise ValueError("calibration membership changed")

    expression = pd.read_parquet(paths["expression"])
    expression["sample_id"] = expression["sample_id"].astype(str)
    expression = expression.set_index("sample_id")
    ordered_ids = manifest["sample_id"].tolist()
    expression = expression.reindex(ordered_ids)
    if expression.isna().any().any():
        raise ValueError("expression does not cover the frozen manifest")
    genes = expression.columns.astype(str).tolist()
    if sha256_lines(genes) != inputs["gene_order_sha256"]:
        raise ValueError("gene order changed")
    with np.load(paths["router"], allow_pickle=False) as archive:
        score_indices = np.asarray(archive["score_gene_indices"], dtype=np.int64)
        router_genes = archive["gene_names"].astype(str).tolist()
    if router_genes != genes or len(score_indices) != 4634:
        raise ValueError("router score panel changed")
    if sha256_array(score_indices) != inputs["score_gene_indices_sha256"]:
        raise ValueError("score-gene index hash changed")

    values = np.log1p(expression.to_numpy(dtype=np.float32))[:, score_indices]
    if not np.isfinite(values).all():
        raise ValueError("expression contains nonfinite values")
    id_to_row = {sample_id: index for index, sample_id in enumerate(ordered_ids)}
    train_rows = np.asarray([id_to_row[value] for value in train_manifest["sample_id"]])
    calibration_rows = np.asarray(
        [id_to_row[value] for value in calibration_manifest["sample_id"]]
    )
    organ_to_index = {organ: index for index, organ in enumerate(ORGANS)}
    train_labels = train_manifest["organ"].map(organ_to_index).to_numpy(dtype=np.int64)
    true_labels = calibration_manifest["organ"].map(organ_to_index).to_numpy(dtype=np.int64)
    groups = calibration_manifest["donor_id"].to_numpy(dtype=str)

    raw_errors = _centroid_errors(values[train_rows], train_labels, values[calibration_rows])
    train_mean = values[train_rows].mean(axis=0)
    train_scale = values[train_rows].std(axis=0, ddof=0)
    train_scale[train_scale < 1e-6] = 1.0
    train_z = (values[train_rows] - train_mean) / train_scale
    calibration_z = (values[calibration_rows] - train_mean) / train_scale
    pca = PCA(
        n_components=int(protocol["baselines"]["pca_components"]),
        svd_solver="randomized",
        random_state=int(protocol["baselines"]["pca_random_state"]),
    )
    train_pca = pca.fit_transform(train_z)
    calibration_pca = pca.transform(calibration_z)
    pca_errors = _centroid_errors(train_pca, train_labels, calibration_pca)
    margins: dict[str, np.ndarray] = {
        "raw_centroid": compatibility_margin(raw_errors),
        "pca64_centroid": compatibility_margin(pca_errors),
    }

    ledger_entries = {int(item["seed"]): item for item in ledger["seed_candidates"]}
    cache_root = Path(args.training_root)
    for seed in SEEDS:
        descriptor = ledger_entries[seed]["banks"]["organ_k8"]["calibration_scores"]
        cache = cache_root / descriptor["path"]
        if not cache.is_file() or sha256_file(cache) != descriptor["sha256"]:
            raise ValueError(f"seed {seed} calibration cache changed")
        with np.load(cache, allow_pickle=False) as archive:
            sample_ids = archive["sample_ids"].astype(str)
            cache_groups = archive["groups"].astype(str)
            cache_organs = archive["organs"].astype(str)
            expert_mse = np.asarray(archive["expert_mse"], dtype=np.float64)
            cache_labels = np.asarray(archive["true_labels"], dtype=np.int64)
        if (
            sample_ids.tolist() != calibration_manifest["sample_id"].tolist()
            or not np.array_equal(cache_groups, groups)
            or not np.array_equal(cache_organs, calibration_manifest["organ"].to_numpy(dtype=str))
            or not np.array_equal(cache_labels, true_labels)
        ):
            raise ValueError(f"seed {seed} calibration cache membership changed")
        margins[f"expert_seed{seed}"] = compatibility_margin(expert_mse)

    point = {name: macro_organ_auc(value, true_labels) for name, value in margins.items()}
    bootstrap = _bootstrap(
        margins,
        true_labels,
        groups,
        draws=int(protocol["statistics"]["donor_bootstrap_draws"]),
        seed=int(protocol["statistics"]["bootstrap_seed"]),
    )
    seed_passes = {}
    for seed in SEEDS:
        name = f"expert_seed{seed}"
        seed_passes[str(seed)] = {
            "point_above_raw": point[name] > point["raw_centroid"],
            "point_above_pca64": point[name] > point["pca64_centroid"],
            "raw_delta_lower_above_zero": bootstrap[f"{name}_minus_raw_centroid"]["ci95"][0] > 0,
            "pca64_delta_lower_above_zero": bootstrap[f"{name}_minus_pca64_centroid"]["ci95"][0] > 0,
        }
    deployable = all(all(value.values()) for value in seed_passes.values())
    report = {
        "schema_version": 1,
        "status": "complete",
        "role": "gtex_calibration_development_organ_label_compatibility",
        "protocol_sha256": sha256_file(protocol_path),
        "evaluator_sha256": expected_self,
        "samples": int(len(calibration_manifest)),
        "donors": int(calibration_manifest["donor_id"].nunique()),
        "organs": list(ORGANS),
        "seeds": list(SEEDS),
        "point_macro_organ_auc": point,
        "donor_bootstrap": bootstrap,
        "seed_gates": seed_passes,
        "decision": (
            "MISLABEL_UTILITY_PASSES_ALL_SEEDS"
            if deployable
            else "MISLABEL_UTILITY_DOES_NOT_BEAT_RAW_AND_PCA_ALL_SEEDS"
        ),
        "firewalls": {
            "neural_training_performed": False,
            "checkpoint_updated": False,
            "best_seed_selected": False,
            "archs4_expression_accessed": False,
            "confirmation_claim": False,
        },
    }
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise FileExistsError(output_dir)
    output_dir.mkdir(parents=True)
    report_path = output_dir / "evaluation_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    sums = output_dir / "IMMUTABLE_SHA256SUMS"
    sums.write_text(f"{sha256_file(report_path)}  evaluation_report.json\n")
    (output_dir / "COMPLETE").write_text("COMPLETE\n")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--expression-parquet", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--router-artifact", required=True)
    parser.add_argument("--candidate-ledger", required=True)
    parser.add_argument("--training-root", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


if __name__ == "__main__":
    evaluate(parse_args())
