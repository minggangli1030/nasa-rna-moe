#!/usr/bin/env python3
"""Build target-hidden, train-fitted utility-axis partitions.

This is the axis-discovery half of the competitive Stage 2 follow-up.  It
never loads the sealed test split.  A fixed probe-gene panel is reconstructed
from a frozen pooled trunk while the independent score-gene panel is hidden.
Train-only residual and output-head-gradient fingerprints are reduced and
capacity-balanced into K=2/K=3 partitions; calibration samples are assigned by
the frozen train centroids without calibration fitting.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import sys
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd
import torch
from scipy.optimize import linear_sum_assignment
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_mutual_info_score


ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = ROOT / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from train_latent_moe import load_frozen_trunk  # noqa: E402
from train_manifest import (  # noqa: E402
    load_expression_rows,
    read_manifest,
    select_manifest_rows,
    sha256_file,
    sha256_json,
    sha256_lines,
    stable_seed,
    validate_expression_metadata,
)


CANDIDATE_KINDS = ("head_gradient", "residual_pca")


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


def build_gene_partition(
    num_genes: int,
    *,
    seed: int,
    probe_fraction: float,
    score_fraction: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return fixed disjoint probe, score, and context gene indices."""
    if num_genes < 6:
        raise ValueError("utility-axis discovery requires at least six genes")
    if not 0 < probe_fraction < 1 or not 0 < score_fraction < 1:
        raise ValueError("probe/score fractions must be in (0, 1)")
    if probe_fraction + score_fraction >= 1:
        raise ValueError("probe and score panels must leave nonempty context")
    num_probe = max(2, int(num_genes * probe_fraction))
    num_score = max(2, int(num_genes * score_fraction))
    if num_probe + num_score >= num_genes:
        raise ValueError("probe and score panels leave no context genes")
    rng = np.random.default_rng(stable_seed(seed, "utility_axis_gene_partition"))
    order = rng.permutation(num_genes)
    probe = np.sort(order[:num_probe].astype(np.int64))
    score = np.sort(order[num_probe : num_probe + num_score].astype(np.int64))
    context = np.sort(order[num_probe + num_score :].astype(np.int64))
    if set(probe) & set(score) or set(probe) & set(context) or set(score) & set(context):
        raise AssertionError("gene partition is not disjoint")
    return probe, score, context


def compute_fingerprints(
    trunk: torch.nn.Module,
    expression: np.ndarray,
    *,
    probe_indices: np.ndarray,
    score_indices: np.ndarray,
    mask_token: float,
    batch_size: int,
    device: torch.device,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute signed probe residuals and exact linear-head gradients.

    Score genes are masked during this pass.  Therefore a calibration route
    assignment cannot encode any target later used for the primary score.
    """
    values = np.asarray(expression, dtype=np.float32)
    if values.ndim != 2:
        raise ValueError("expression must be rank two")
    if np.any(values < 0):
        raise ValueError("expected nonnegative TPM expression")
    values = np.log1p(values).astype(np.float32, copy=False)
    blocked = np.sort(np.concatenate([probe_indices, score_indices])).astype(np.int64)
    residual_rows: list[np.ndarray] = []
    gradient_rows: list[np.ndarray] = []
    trunk.eval()
    with torch.no_grad():
        for start in range(0, len(values), batch_size):
            truth = torch.from_numpy(values[start : start + batch_size]).to(device)
            masked = truth.clone()
            masked[:, blocked] = float(mask_token)
            hidden = trunk.encode(masked)
            base = trunk.decode(hidden)
            probe_truth = truth[:, probe_indices]
            probe_base = base[:, probe_indices]
            signed_residual = probe_truth - probe_base
            # Gradient of mean squared error with respect to a zero-initialized
            # shared linear residual head.  Direction, not magnitude, is used
            # downstream to identify samples requesting compatible updates.
            error = probe_base - probe_truth
            gradient_weight = (2.0 / len(probe_indices)) * torch.einsum(
                "bp,bph->bh", error, hidden[:, probe_indices, :]
            )
            gradient_bias = 2.0 * error.mean(dim=1, keepdim=True)
            residual_rows.append(signed_residual.cpu().numpy().astype(np.float32))
            gradient_rows.append(
                torch.cat([gradient_weight, gradient_bias], dim=1)
                .cpu()
                .numpy()
                .astype(np.float32)
            )
    return np.concatenate(residual_rows), np.concatenate(gradient_rows)


def _fit_embedding(
    train: np.ndarray,
    calibration: np.ndarray,
    *,
    components: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, dict[str, np.ndarray]]:
    train = np.asarray(train, dtype=np.float64)
    calibration = np.asarray(calibration, dtype=np.float64)
    if train.ndim != 2 or calibration.ndim != 2 or train.shape[1] != calibration.shape[1]:
        raise ValueError("train/calibration fingerprints are incompatible")
    mean = train.mean(axis=0)
    scale = train.std(axis=0)
    scale[scale < 1e-8] = 1.0
    train_scaled = (train - mean) / scale
    calibration_scaled = (calibration - mean) / scale
    n_components = min(int(components), train.shape[0] - 1, train.shape[1])
    if n_components < 1:
        raise ValueError("not enough rows/features for PCA")
    pca = PCA(n_components=n_components, svd_solver="randomized", random_state=seed)
    train_embedding = pca.fit_transform(train_scaled)
    calibration_embedding = pca.transform(calibration_scaled)

    def normalize(rows: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(rows, axis=1, keepdims=True)
        norms[norms < 1e-12] = 1.0
        return rows / norms

    return normalize(train_embedding), normalize(calibration_embedding), {
        "standard_mean": mean.astype(np.float32),
        "standard_scale": scale.astype(np.float32),
        "pca_mean": pca.mean_.astype(np.float32),
        "pca_components": pca.components_.astype(np.float32),
        "pca_explained_variance_ratio": pca.explained_variance_ratio_.astype(np.float32),
    }


def _balanced_assignment(embedding: np.ndarray, centers: np.ndarray) -> np.ndarray:
    """Minimum-cost assignment to deterministic near-equal centroid slots."""
    embedding = np.asarray(embedding, dtype=np.float64)
    centers = np.asarray(centers, dtype=np.float64)
    n_samples = len(embedding)
    k = len(centers)
    capacities = np.full(k, n_samples // k, dtype=np.int64)
    capacities[: n_samples % k] += 1
    slots = np.repeat(np.arange(k, dtype=np.int64), capacities)
    slot_centers = centers[slots]
    cost = (
        np.square(embedding).sum(axis=1, keepdims=True)
        + np.square(slot_centers).sum(axis=1)[None, :]
        - 2.0 * embedding @ slot_centers.T
    )
    row, column = linear_sum_assignment(cost)
    labels = np.empty(n_samples, dtype=np.int64)
    labels[row] = slots[column]
    return labels


def _canonicalize(labels: np.ndarray, centers: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    keys = tuple(centers[:, index] for index in reversed(range(min(3, centers.shape[1]))))
    order = np.lexsort(keys)
    remap = np.empty(len(order), dtype=np.int64)
    remap[order] = np.arange(len(order), dtype=np.int64)
    return remap[labels], centers[order]


def fit_balanced_consensus_partition(
    train_embedding: np.ndarray,
    calibration_embedding: np.ndarray,
    *,
    k: int,
    seed: int,
    restarts: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    """Fit repeated train-only balanced partitions and choose their AMI medoid."""
    if k < 2 or k >= len(train_embedding):
        raise ValueError("invalid partition size")
    candidates: list[tuple[np.ndarray, np.ndarray]] = []
    for restart in range(restarts):
        restart_seed = stable_seed(seed, "balanced_kmeans", k, restart) % (2**32 - 1)
        initial = KMeans(
            n_clusters=k,
            n_init=1,
            max_iter=200,
            random_state=int(restart_seed),
        ).fit(train_embedding)
        labels = _balanced_assignment(train_embedding, initial.cluster_centers_)
        centers = np.stack(
            [train_embedding[labels == index].mean(axis=0) for index in range(k)]
        )
        labels = _balanced_assignment(train_embedding, centers)
        centers = np.stack(
            [train_embedding[labels == index].mean(axis=0) for index in range(k)]
        )
        labels, centers = _canonicalize(labels, centers)
        candidates.append((labels, centers))
    pairwise = np.eye(restarts, dtype=np.float64)
    for left, right in itertools.combinations(range(restarts), 2):
        value = adjusted_mutual_info_score(candidates[left][0], candidates[right][0])
        pairwise[left, right] = pairwise[right, left] = value
    mean_ami = pairwise.mean(axis=1)
    selected = int(np.argmax(mean_ami))
    train_labels, centers = candidates[selected]
    distances = (
        np.square(calibration_embedding).sum(axis=1, keepdims=True)
        + np.square(centers).sum(axis=1)[None, :]
        - 2.0 * calibration_embedding @ centers.T
    )
    calibration_labels = distances.argmin(axis=1).astype(np.int64)
    stability_values = pairwise[np.triu_indices(restarts, k=1)]
    report = {
        "restarts": int(restarts),
        "selected_restart": selected,
        "mean_ami_by_restart": mean_ami.tolist(),
        "minimum_pairwise_ami": (
            float(stability_values.min()) if len(stability_values) else 1.0
        ),
        "mean_pairwise_ami": (
            float(stability_values.mean()) if len(stability_values) else 1.0
        ),
    }
    return train_labels, calibration_labels, centers.astype(np.float32), report


def stratified_random_labels(frame: pd.DataFrame, *, k: int, seed: int) -> np.ndarray:
    """Deterministic organ-stratified random labels with near-equal exposure."""
    labels = np.full(len(frame), -1, dtype=np.int64)
    rng = np.random.default_rng(seed)
    offset = 0
    for organ in sorted(frame["organ"].astype(str).unique()):
        rows = np.flatnonzero(frame["organ"].astype(str).to_numpy() == organ)
        rng.shuffle(rows)
        assigned = (np.arange(len(rows), dtype=np.int64) + offset) % k
        labels[rows] = assigned
        offset = int((offset + len(rows)) % k)
    if np.any(labels < 0):
        raise AssertionError("random partition left rows unassigned")
    return labels


def _partition_summary(labels: np.ndarray, frame: pd.DataFrame, k: int) -> dict[str, Any]:
    labels = np.asarray(labels, dtype=np.int64)
    counts = np.bincount(labels, minlength=k)
    fractions = counts / counts.sum()
    groups = frame["series_group_id"].astype(str).to_numpy()
    organs = frame["organ"].astype(str).to_numpy()
    dominance = []
    study_counts = []
    for label in range(k):
        route_groups = groups[labels == label]
        unique, group_count = np.unique(route_groups, return_counts=True)
        dominance.append(float(group_count.max() / group_count.sum()) if len(unique) else 1.0)
        study_counts.append(int(len(unique)))
    return {
        "counts": counts.tolist(),
        "fractions": fractions.tolist(),
        "effective_k": float(1.0 / np.square(fractions).sum()),
        "minimum_fraction": float(fractions.min()),
        "connected_studies_per_partition": study_counts,
        "maximum_single_study_fraction": float(max(dominance)),
        "organ_ami": float(adjusted_mutual_info_score(organs, labels)),
        "study_ami": float(adjusted_mutual_info_score(groups, labels)),
    }


def build(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output_dir}")
    device = _resolve_device(args.device)
    trunk, checkpoint_config, checkpoint = load_frozen_trunk(args.pooled_checkpoint, device)
    if checkpoint_config["normalization"] != "log1p_tpm":
        raise ValueError("utility-axis pilot requires log1p_tpm pooled checkpoint")
    if not np.isclose(float(checkpoint_config["mask_token"]), float(args.mask_token)):
        raise ValueError("mask token differs from pooled checkpoint")
    manifest = read_manifest(args.manifest)
    selection = select_manifest_rows(
        manifest,
        role="pooled",
        train_split=args.train_split,
        validation_split=args.validation_split,
        train_filter_column=args.train_filter_column,
    )
    train_ids = selection.train[args.sample_id_column].astype(str).tolist()
    calibration_ids = selection.validation[args.sample_id_column].astype(str).tolist()
    expression, expression_info = load_expression_rows(
        args.expression_parquet,
        train_ids + calibration_ids,
        sample_id_column=args.sample_id_column,
    )
    if list(expression_info.gene_columns) != list(checkpoint_config["gene_list"]):
        raise ValueError("expression gene order differs from pooled checkpoint")
    validate_expression_metadata(
        args.expression_parquet,
        expression_info.gene_columns,
        metadata_path=args.expression_metadata,
    )
    train_expression = expression[: len(train_ids)]
    calibration_expression = expression[len(train_ids) :]
    probe, score, context = build_gene_partition(
        len(expression_info.gene_columns),
        seed=args.axis_seed,
        probe_fraction=args.probe_fraction,
        score_fraction=args.score_fraction,
    )
    train_residual, train_gradient = compute_fingerprints(
        trunk,
        train_expression,
        probe_indices=probe,
        score_indices=score,
        mask_token=args.mask_token,
        batch_size=args.batch_size,
        device=device,
    )
    calibration_residual, calibration_gradient = compute_fingerprints(
        trunk,
        calibration_expression,
        probe_indices=probe,
        score_indices=score,
        mask_token=args.mask_token,
        batch_size=args.batch_size,
        device=device,
    )
    raw_by_kind = {
        "head_gradient": (train_gradient, calibration_gradient),
        "residual_pca": (train_residual, calibration_residual),
    }
    embeddings: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    definition_arrays: dict[str, np.ndarray] = {
        "probe_gene_indices": probe,
        "score_gene_indices": score,
        "context_gene_indices": context,
        "gene_names": np.asarray(expression_info.gene_columns, dtype=str),
    }
    for kind, (train_raw, calibration_raw) in raw_by_kind.items():
        train_embedding, calibration_embedding, transform = _fit_embedding(
            train_raw,
            calibration_raw,
            components=args.pca_components,
            seed=stable_seed(args.axis_seed, kind) % (2**32 - 1),
        )
        embeddings[kind] = (train_embedding, calibration_embedding)
        for name, value in transform.items():
            definition_arrays[f"{kind}_{name}"] = value

    combined = pd.concat(
        [
            selection.train.assign(_utility_split="train"),
            selection.validation.assign(_utility_split="calibration"),
        ],
        ignore_index=True,
    )
    keep = [
        args.sample_id_column,
        "_utility_split",
        args.organ_column,
        args.group_column,
    ]
    assignments = combined[keep].rename(columns={"_utility_split": "utility_split"}).copy()
    reports: dict[str, Any] = {}
    for kind in CANDIDATE_KINDS:
        train_embedding, calibration_embedding = embeddings[kind]
        for k in args.k_values:
            name = f"{kind}_k{k}"
            train_labels, calibration_labels, centers, stability = (
                fit_balanced_consensus_partition(
                    train_embedding,
                    calibration_embedding,
                    k=k,
                    seed=stable_seed(args.axis_seed, kind, k),
                    restarts=args.cluster_restarts,
                )
            )
            assignments[name] = np.concatenate([train_labels, calibration_labels])
            definition_arrays[f"{name}_centroids"] = centers
            reports[name] = {
                "kind": kind,
                "k": int(k),
                "primary": name == args.primary_candidate,
                "clustering_stability": stability,
                "train": _partition_summary(train_labels, selection.train, k),
                "calibration": _partition_summary(
                    calibration_labels, selection.validation, k
                ),
            }
    for k in args.k_values:
        name = f"random_k{k}"
        train_labels = stratified_random_labels(
            selection.train,
            k=k,
            seed=stable_seed(args.axis_seed, "random", k, "train"),
        )
        calibration_labels = stratified_random_labels(
            selection.validation,
            k=k,
            seed=stable_seed(args.axis_seed, "random", k, "calibration"),
        )
        assignments[name] = np.concatenate([train_labels, calibration_labels])
        reports[name] = {
            "kind": "matched_random",
            "k": int(k),
            "primary": False,
            "train": _partition_summary(train_labels, selection.train, k),
            "calibration": _partition_summary(calibration_labels, selection.validation, k),
        }
    organ_names = sorted(selection.train[args.organ_column].astype(str).unique())
    if set(selection.validation[args.organ_column].astype(str)) - set(organ_names):
        raise ValueError("calibration contains an organ absent from training")
    organ_index = {name: index for index, name in enumerate(organ_names)}
    organ_labels = np.asarray(
        [organ_index[value] for value in combined[args.organ_column].astype(str)],
        dtype=np.int64,
    )
    assignments["organ_k5"] = organ_labels
    reports["organ_k5"] = {
        "kind": "organ_anchor",
        "k": len(organ_names),
        "label_names": organ_names,
        "primary": False,
        "train": _partition_summary(organ_labels[: len(train_ids)], selection.train, len(organ_names)),
        "calibration": _partition_summary(
            organ_labels[len(train_ids) :], selection.validation, len(organ_names)
        ),
    }
    if len(organ_names) != 5:
        raise ValueError(f"organ anchor expected five organs, found {organ_names}")

    assignments_path = output_dir / "partition_manifest.parquet"
    assignments.to_parquet(assignments_path, index=False)
    definitions_path = output_dir / "axis_definitions.npz"
    np.savez_compressed(definitions_path, **definition_arrays)
    metadata = {
        "schema_version": 1,
        "status": "complete",
        "research_stage": "stage2_competitive_followup",
        "experiment": "target_hidden_utility_axis_partitions",
        "test_accessed": False,
        "axis_seed": int(args.axis_seed),
        "primary_candidate": args.primary_candidate,
        "candidate_family": [
            f"{kind}_k{k}" for kind in CANDIDATE_KINDS for k in args.k_values
        ],
        "controls": [f"random_k{k}" for k in args.k_values] + ["organ_k5"],
        "gene_partition": {
            "probe_fraction": args.probe_fraction,
            "score_fraction": args.score_fraction,
            "probe_genes": int(len(probe)),
            "score_genes": int(len(score)),
            "context_genes": int(len(context)),
            "target_hidden_guard": (
                "axis fingerprints mask both probe and score genes; only probe truth "
                "forms the fingerprint; score truth is never consumed"
            ),
        },
        "counts": {
            "train": len(train_ids),
            "calibration": len(calibration_ids),
            "genes": len(expression_info.gene_columns),
        },
        "checkpoint_update": checkpoint.get("update"),
        "partitions": reports,
        "hashes": {
            "protocol_sha256": sha256_file(args.protocol),
            "pooled_checkpoint_sha256": sha256_file(args.pooled_checkpoint),
            "expression_sha256": sha256_file(args.expression_parquet),
            "manifest_sha256": sha256_file(args.manifest),
            "gene_order_sha256": sha256_lines(expression_info.gene_columns),
            "train_sample_ids_sha256": sha256_lines(train_ids),
            "calibration_sample_ids_sha256": sha256_lines(calibration_ids),
            "partition_manifest_sha256": sha256_file(assignments_path),
            "axis_definitions_sha256": sha256_file(definitions_path),
        },
        "config": {
            "pca_components": args.pca_components,
            "cluster_restarts": args.cluster_restarts,
            "k_values": list(args.k_values),
            "batch_size": args.batch_size,
            "mask_token": args.mask_token,
        },
    }
    metadata["hashes"]["resolved_config_sha256"] = sha256_json(metadata["config"])
    _atomic_json(output_dir / "partition_report.json", metadata)
    (output_dir / "COMPLETE").touch()
    return metadata


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expression-parquet", required=True)
    parser.add_argument("--expression-metadata", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--pooled-checkpoint", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--axis-seed", type=int, default=314159)
    parser.add_argument("--primary-candidate", default="head_gradient_k2")
    parser.add_argument("--k-values", type=int, nargs="+", default=[2, 3])
    parser.add_argument("--probe-fraction", type=float, default=0.10)
    parser.add_argument("--score-fraction", type=float, default=0.30)
    parser.add_argument("--pca-components", type=int, default=32)
    parser.add_argument("--cluster-restarts", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--mask-token", type=float, default=-10.0)
    parser.add_argument("--train-split", default="train")
    parser.add_argument("--validation-split", default="calibration")
    parser.add_argument("--train-filter-column", default="balanced_train")
    parser.add_argument("--sample-id-column", default="sample_id")
    parser.add_argument("--organ-column", default="organ")
    parser.add_argument("--group-column", default="series_group_id")
    parser.add_argument("--device", default="auto")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.primary_candidate not in {
        f"{kind}_k{k}" for kind in CANDIDATE_KINDS for k in args.k_values
    }:
        raise ValueError("primary candidate is outside the frozen candidate family")
    result = build(args)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
