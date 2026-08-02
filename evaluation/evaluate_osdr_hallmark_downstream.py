#!/usr/bin/env python3
"""Frozen OSDR Hallmark-50 downstream feature evaluation (D2)."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from evaluation.evaluate_multiaxis_tier1_osdr_probe import (
    METADATA_COLUMNS,
    hallmark_features,
    parse_hallmark,
    study_bootstrap_delta,
)
from evaluation.evaluate_stage1_osdr_downstream import (
    _fit,
    _fit_grid_path,
    _score,
    _splits,
    sha256_file,
)


Transform = Callable[[np.ndarray, np.ndarray], tuple[np.ndarray, np.ndarray]]


def _standardized_transform(
    train: np.ndarray, test: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    scaler = StandardScaler()
    return scaler.fit_transform(train), scaler.transform(test)


def _pca_transform(
    train: np.ndarray, test: np.ndarray, *, components: int = 64
) -> tuple[np.ndarray, np.ndarray]:
    scaled_train, scaled_test = _standardized_transform(train, test)
    count = min(components, len(scaled_train) - 1, scaled_train.shape[1])
    if count < 2:
        raise ValueError("PCA fold has fewer than two available components")
    pca = PCA(n_components=count, svd_solver="randomized", random_state=1701)
    return pca.fit_transform(scaled_train), pca.transform(scaled_test)


def _hallmark_pca_transform(
    raw_train: np.ndarray,
    raw_test: np.ndarray,
    hallmark_train: np.ndarray,
    hallmark_test: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    pca_train, pca_test = _pca_transform(raw_train, raw_test)
    hallmark_train, hallmark_test = _standardized_transform(
        hallmark_train, hallmark_test
    )
    return (
        np.column_stack([pca_train, hallmark_train]),
        np.column_stack([pca_test, hallmark_test]),
    )


def nested_group_evaluate_transformed(
    x: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    *,
    outer_folds: int,
    inner_folds: int,
    grid: tuple[tuple[float, float], ...],
    transform: Transform,
) -> dict:
    folds = []
    probabilities = np.full(len(y), np.nan, dtype=np.float64)
    predictions = np.full(len(y), -1, dtype=np.int64)
    for outer_index, (train_index, test_index) in enumerate(
        _splits(groups, outer_folds)
    ):
        inner_groups = groups[train_index]
        scores = {item: [] for item in grid}
        iterations = {item: [] for item in grid}
        for inner_train, inner_test in _splits(inner_groups, inner_folds):
            a = train_index[inner_train]
            b = train_index[inner_test]
            train, test = transform(x[a], x[b])
            path = _fit_grid_path(train, y[a], test, grid)
            for item, (probability, n_iter) in path.items():
                from sklearn.metrics import roc_auc_score

                scores[item].append(float(roc_auc_score(y[b], probability)))
                iterations[item].append(n_iter)
        candidates = [
            {
                "C": c_value,
                "l1_ratio": l1_ratio,
                "mean_inner_auroc": float(np.mean(scores[(c_value, l1_ratio)])),
                "max_inner_iterations": int(max(iterations[(c_value, l1_ratio)])),
            }
            for c_value, l1_ratio in grid
        ]
        selected = sorted(
            candidates,
            key=lambda item: (-item["mean_inner_auroc"], item["C"], item["l1_ratio"]),
        )[0]
        train, test = transform(x[train_index], x[test_index])
        probability, prediction, n_iter = _fit(
            train,
            y[train_index],
            test,
            c_value=selected["C"],
            l1_ratio=selected["l1_ratio"],
        )
        probabilities[test_index] = probability
        predictions[test_index] = prediction
        folds.append(
            {
                "fold": outer_index,
                "train_studies": int(np.unique(groups[train_index]).size),
                "test_studies": int(np.unique(groups[test_index]).size),
                "test_samples": int(len(test_index)),
                "selected": selected,
                "outer_fit_iterations": n_iter,
                "metrics": _score(y[test_index], probability, prediction),
            }
        )
    if not np.isfinite(probabilities).all() or np.any(predictions < 0):
        raise RuntimeError("grouped evaluation did not score every sample")
    return {
        "pooled_out_of_fold": _score(y, probabilities, predictions),
        "folds": folds,
        "probabilities": probabilities,
        "predictions": predictions,
    }


def random_matched_sets(
    names: list[str],
    sizes: list[int],
    gene_pool: list[str],
    *,
    seed: int,
) -> dict[str, tuple[str, ...]]:
    if len(names) != len(sizes):
        raise ValueError("set names and sizes differ")
    if max(sizes) > len(gene_pool):
        raise ValueError("random gene pool is too small")
    rng = np.random.default_rng(seed)
    genes = np.asarray(sorted(gene_pool), dtype=str)
    return {
        name: tuple(rng.choice(genes, size=size, replace=False).tolist())
        for name, size in zip(names, sizes)
    }


def _reportable(result: dict) -> dict:
    return {
        key: value
        for key, value in result.items()
        if key not in {"probabilities", "predictions"}
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--cohort-root", required=True)
    parser.add_argument("--hallmark-gmt", required=True)
    parser.add_argument("--router", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()

    protocol_path = Path(args.protocol)
    if sha256_file(protocol_path) != args.expected_protocol_sha256:
        raise ValueError("D2 protocol SHA256 mismatch")
    protocol = json.loads(protocol_path.read_text())
    if protocol.get("status") != "frozen_before_d2_hallmark_outcome_access":
        raise ValueError("D2 protocol is not frozen")
    inputs = protocol["inputs"]
    checks = (
        (Path(args.hallmark_gmt), inputs["hallmark_gmt_sha256"]),
        (Path(args.router), inputs["router_sha256"]),
        (Path(args.cohort_root) / "retained_cohort.csv", inputs["retained_cohort_sha256"]),
        (Path(args.cohort_root) / "osdr_expression_v3.parquet", inputs["expression_sha256"]),
    )
    for path, expected in checks:
        if sha256_file(path) != expected:
            raise ValueError(f"input SHA256 mismatch: {path}")

    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise FileExistsError(output_dir)
    output_dir.mkdir(parents=True)
    retained = pd.read_csv(Path(args.cohort_root) / "retained_cohort.csv")
    retained = retained.loc[retained["valid_study_organ_contrast"].astype(bool)].copy()
    if len(retained) != 292 or retained["study_id"].nunique() != 18:
        raise ValueError("frozen OSDR cohort membership changed")
    expression = pd.read_parquet(Path(args.cohort_root) / "osdr_expression_v3.parquet")
    expression.index = expression.index.astype(str)
    sample_ids = retained["sample_id"].astype(str).to_numpy()
    expression = expression.reindex(sample_ids)
    if expression.isna().any().any():
        raise ValueError("expression does not cover frozen cohort")
    labels = retained["spaceflight"].astype(np.int64).to_numpy()
    groups = retained["study_id"].astype(str).to_numpy()
    genes = sorted(set(expression.columns) - METADATA_COLUMNS)
    raw = expression[genes].to_numpy(dtype=np.float64)
    if not np.isfinite(raw).all():
        raise ValueError("raw expression contains non-finite values")

    router = np.load(args.router, allow_pickle=False)
    score_genes = set(router["score_gene_names"].astype(str).tolist())
    hallmark_sets = parse_hallmark(Path(args.hallmark_gmt))
    hallmark, coverage = hallmark_features(expression, hallmark_sets, score_genes)
    names = sorted(coverage)
    sizes = [coverage[name] for name in names]
    gene_pool = sorted(set(genes) - score_genes)
    random_features = {}
    for seed in protocol["controls"]["random_draw_seeds"]:
        sets = random_matched_sets(names, sizes, gene_pool, seed=int(seed))
        random_features[f"random_50_seed{seed}"] = hallmark_features(
            expression, sets, score_genes
        )[0]
    permuted_sets = random_matched_sets(
        names,
        sizes,
        sorted(set().union(*(set(values) for values in hallmark_sets.values())) & set(gene_pool)),
        seed=int(protocol["controls"]["permuted_hallmark_seed"]),
    )
    permuted = hallmark_features(expression, permuted_sets, score_genes)[0]

    if args.smoke:
        grid = ((0.1, 0.0), (1.0, 1.0))
        bootstrap_replicates = 100
    else:
        grid = tuple(
            (float(item["C"]), float(item["l1_ratio"]))
            for item in protocol["head"]["grid"]
        )
        bootstrap_replicates = int(protocol["statistics"]["study_bootstrap_replicates"])
    outer_folds = int(protocol["cohort"]["outer_folds"])
    inner_folds = int(protocol["cohort"]["inner_folds"])

    conditions: dict[str, tuple[np.ndarray, Transform]] = {
        "raw_expression": (raw, _standardized_transform),
        "pca_64": (raw, _pca_transform),
        "hallmark_50": (hallmark, _standardized_transform),
        "hallmark_permuted": (permuted, _standardized_transform),
    }
    conditions.update(
        (name, (features, _standardized_transform))
        for name, features in random_features.items()
    )
    results = {}
    evaluated = {}
    for name, (features, transform) in conditions.items():
        evaluated[name] = nested_group_evaluate_transformed(
            features,
            labels,
            groups,
            outer_folds=outer_folds,
            inner_folds=inner_folds,
            grid=grid,
            transform=transform,
        )
        results[name] = _reportable(evaluated[name])

    combined = np.column_stack([raw, hallmark])
    raw_width = raw.shape[1]

    def combined_transform(train: np.ndarray, test: np.ndarray):
        return _hallmark_pca_transform(
            train[:, :raw_width],
            test[:, :raw_width],
            train[:, raw_width:],
            test[:, raw_width:],
        )

    evaluated["hallmark_50_plus_pca_64"] = nested_group_evaluate_transformed(
        combined,
        labels,
        groups,
        outer_folds=outer_folds,
        inner_folds=inner_folds,
        grid=grid,
        transform=combined_transform,
    )
    results["hallmark_50_plus_pca_64"] = _reportable(
        evaluated["hallmark_50_plus_pca_64"]
    )

    comparisons = {}
    for candidate in ("hallmark_50", "hallmark_50_plus_pca_64"):
        comparisons[candidate] = {}
        for baseline in ("pca_64", "raw_expression"):
            comparisons[candidate][f"minus_{baseline}"] = study_bootstrap_delta(
                labels,
                evaluated[baseline]["probabilities"],
                evaluated[candidate]["probabilities"],
                groups,
                replicates=bootstrap_replicates,
                seed=int(protocol["statistics"]["study_bootstrap_seed"]),
            )
    candidate = "hallmark_50_plus_pca_64"
    candidate_auroc = results[candidate]["pooled_out_of_fold"]["auroc"]
    control_names = ["hallmark_permuted", *sorted(random_features)]
    passes = {
        "pca_interval_above_zero": comparisons[candidate]["minus_pca_64"]["ci95"][0] > 0,
        "raw_interval_above_zero": comparisons[candidate]["minus_raw_expression"]["ci95"][0] > 0,
        "beats_every_control": all(
            candidate_auroc > results[name]["pooled_out_of_fold"]["auroc"]
            for name in control_names
        ),
    }
    verdict = "HALLMARK_FEATURES_PASS" if all(passes.values()) else "HALLMARK_FEATURES_FAIL"
    prediction_rows = []
    for name, result in evaluated.items():
        prediction_rows.extend(
            {
                "condition": name,
                "sample_id": sample_id,
                "study_id": group,
                "label": int(label),
                "probability": float(probability),
                "prediction": int(prediction),
            }
            for sample_id, group, label, probability, prediction in zip(
                sample_ids,
                groups,
                labels,
                result["probabilities"],
                result["predictions"],
            )
        )
    predictions_path = output_dir / "out_of_fold_predictions.csv"
    pd.DataFrame(prediction_rows).to_csv(predictions_path, index=False)
    report = {
        "schema_version": 1,
        "status": "complete",
        "role": protocol["role"],
        "smoke": bool(args.smoke),
        "protocol_sha256": sha256_file(protocol_path),
        "n_samples": int(len(labels)),
        "n_studies": int(np.unique(groups).size),
        "coverage": coverage,
        "results": results,
        "comparisons": comparisons,
        "frozen_gate": passes,
        "verdict": verdict,
        "predictions_sha256": sha256_file(predictions_path),
        "best_seed_or_condition_selection": False,
        "final_confirmation": False,
    }
    report_path = output_dir / "hallmark_downstream_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    checksums = {
        report_path.name: sha256_file(report_path),
        predictions_path.name: sha256_file(predictions_path),
    }
    (output_dir / "IMMUTABLE_SHA256SUMS").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in sorted(checksums.items()))
    )
    (output_dir / "COMPLETE").write_text("complete\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
