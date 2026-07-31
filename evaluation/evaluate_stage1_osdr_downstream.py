#!/usr/bin/env python3
"""Study-grouped downstream probes for frozen Stage 1 OSDR representations."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    f1_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler


CONDITIONS = (
    "pooled",
    "pooled_adapter",
    "pooled_plus_organ_label",
    "true_organ",
    "blind_router_hard",
    "blind_router_soft",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _splits(groups: np.ndarray, folds: int):
    unique = np.unique(groups)
    if len(unique) < folds:
        raise ValueError("insufficient groups for requested grouped folds")
    dummy = np.zeros(len(groups))
    return list(GroupKFold(n_splits=folds).split(dummy, groups=groups))


def _transform(
    x_train: np.ndarray,
    x_test: np.ndarray,
    *,
    pca_components: int | None,
) -> tuple[np.ndarray, np.ndarray]:
    scaler = StandardScaler()
    train = scaler.fit_transform(x_train)
    test = scaler.transform(x_test)
    if pca_components is not None:
        n_components = min(pca_components, len(train) - 1, train.shape[1])
        if n_components < 2:
            raise ValueError("PCA fold has fewer than two available components")
        pca = PCA(n_components=n_components, svd_solver="randomized", random_state=1701)
        train = pca.fit_transform(train)
        test = pca.transform(test)
    return train, test


def _fit(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    *,
    c_value: float,
    l1_ratio: float,
) -> tuple[np.ndarray, np.ndarray, int]:
    max_iter = 10_000
    model = LogisticRegression(
        C=c_value,
        penalty="elasticnet",
        solver="saga",
        l1_ratio=l1_ratio,
        class_weight="balanced",
        max_iter=max_iter,
        random_state=1701,
        n_jobs=1,
        tol=1e-3,
    )
    model.fit(x_train, y_train)
    n_iter = int(model.n_iter_.max())
    if n_iter >= max_iter:
        raise RuntimeError(
            f"elastic-net logistic fit did not converge in {max_iter} iterations"
        )
    return model.predict_proba(x_test)[:, 1], model.predict(x_test), n_iter


def _fit_grid_path(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    grid: tuple[tuple[float, float], ...],
) -> dict[tuple[float, float], tuple[np.ndarray, int]]:
    """Fit the frozen grid with warm starts along C for each fixed L1 ratio."""
    max_iter = 10_000
    output = {}
    ratios = sorted({l1_ratio for _, l1_ratio in grid})
    for l1_ratio in ratios:
        model = LogisticRegression(
            C=1.0,
            penalty="elasticnet",
            solver="saga",
            l1_ratio=l1_ratio,
            class_weight="balanced",
            max_iter=max_iter,
            random_state=1701,
            n_jobs=1,
            tol=1e-3,
            warm_start=True,
        )
        for c_value in sorted(c for c, ratio in grid if ratio == l1_ratio):
            model.set_params(C=c_value)
            model.fit(x_train, y_train)
            n_iter = int(model.n_iter_.max())
            if n_iter >= max_iter:
                raise RuntimeError(
                    "elastic-net logistic grid fit did not converge: "
                    f"C={c_value}, l1_ratio={l1_ratio}, max_iter={max_iter}"
                )
            output[(c_value, l1_ratio)] = (
                model.predict_proba(x_test)[:, 1],
                n_iter,
            )
    if set(output) != set(grid):
        raise RuntimeError("warm-start path did not cover the frozen grid")
    return output


def _score(y: np.ndarray, probability: np.ndarray, prediction: np.ndarray) -> dict:
    return {
        "auroc": float(roc_auc_score(y, probability)),
        "auprc": float(average_precision_score(y, probability)),
        "balanced_accuracy": float(balanced_accuracy_score(y, prediction)),
        "macro_f1": float(f1_score(y, prediction, average="macro")),
    }


def nested_group_evaluate(
    x: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    *,
    outer_folds: int,
    inner_folds: int,
    pca_components: int | None,
    grid: tuple[tuple[float, float], ...],
) -> dict:
    folds = []
    probabilities = np.full(len(y), np.nan, dtype=np.float64)
    predictions = np.full(len(y), -1, dtype=np.int64)
    for outer_index, (train_index, test_index) in enumerate(_splits(groups, outer_folds)):
        inner_groups = groups[train_index]
        candidate_scores = {item: [] for item in grid}
        candidate_iterations = {item: [] for item in grid}
        for inner_train, inner_test in _splits(inner_groups, inner_folds):
            a = train_index[inner_train]
            b = train_index[inner_test]
            train, test = _transform(
                x[a], x[b], pca_components=pca_components
            )
            path = _fit_grid_path(train, y[a], test, grid)
            for item, (probability, n_iter) in path.items():
                candidate_scores[item].append(
                    float(roc_auc_score(y[b], probability))
                )
                candidate_iterations[item].append(n_iter)
        candidates = []
        for c_value, l1_ratio in grid:
            scores = candidate_scores[(c_value, l1_ratio)]
            candidates.append(
                {
                    "C": c_value,
                    "l1_ratio": l1_ratio,
                    "mean_inner_auroc": float(np.mean(scores)),
                    "max_inner_iterations": int(
                        max(candidate_iterations[(c_value, l1_ratio)])
                    ),
                }
            )
        selected = sorted(
            candidates,
            key=lambda item: (
                -item["mean_inner_auroc"],
                item["C"],
                item["l1_ratio"],
            ),
        )[0]
        train, test = _transform(
            x[train_index], x[test_index], pca_components=pca_components
        )
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--cohort-root", required=True)
    parser.add_argument("--feature-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--outer-folds", type=int, default=5)
    parser.add_argument("--inner-folds", type=int, default=3)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()

    protocol_path = Path(args.protocol)
    if sha256_file(protocol_path) != args.expected_protocol_sha256:
        raise ValueError("downstream protocol SHA256 mismatch")
    protocol = json.loads(protocol_path.read_text())
    if protocol.get("status") != "frozen_stage1_osdr_downstream_development":
        raise ValueError("protocol is not frozen")
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise FileExistsError(output_dir)
    output_dir.mkdir(parents=True)

    expression = pd.read_parquet(Path(args.cohort_root) / "osdr_expression_v3.parquet")
    feature_paths = sorted(Path(args.feature_root).glob("seed*_features.npz"))
    if not feature_paths:
        raise FileNotFoundError("no Stage 1 OSDR feature caches")
    feature_archives = {}
    for path in feature_paths:
        archive = np.load(path, allow_pickle=False)
        metadata = json.loads(str(archive["metadata_json"].item()))
        if metadata.get("status") != "complete":
            raise ValueError(f"incomplete feature cache: {path}")
        feature_archives[int(metadata["seed"])] = archive

    reference = feature_archives[sorted(feature_archives)[0]]
    sample_ids = reference["sample_ids"].astype(str)
    groups = reference["groups"].astype(str)
    organs = reference["organs"].astype(str)
    labels = reference["labels"].astype(np.int64)
    expression.index = expression.index.astype(str)
    expression = expression.reindex(sample_ids)
    metadata_columns = {"sample_name", "condition", "spaceflight", "study_id", "species"}
    genes = [column for column in expression.columns if column not in metadata_columns]
    raw = expression[genes].to_numpy(dtype=np.float32)
    if expression.isna().any().any() or not np.isfinite(raw).all():
        raise ValueError("raw expression differs from feature-cache membership")
    for seed, archive in feature_archives.items():
        for key, expected in (
            ("sample_ids", sample_ids),
            ("groups", groups),
            ("organs", organs),
            ("labels", labels),
        ):
            actual = archive[key].astype(str) if key != "labels" else archive[key]
            comparable = expected.astype(str) if key != "labels" else expected
            if not np.array_equal(actual, comparable):
                raise ValueError(f"seed {seed} {key} differs")

    organ_order = protocol["cohort"]["organs"]
    organ_one_hot = np.eye(len(organ_order), dtype=np.float32)[
        [organ_order.index(value) for value in organs]
    ]
    if args.smoke:
        grid = ((0.1, 0.0), (0.1, 1.0), (1.0, 0.0), (1.0, 1.0))
        seeds = [sorted(feature_archives)[0]]
    else:
        grid = tuple(
            (c_value, l1_ratio)
            for c_value in (0.01, 0.1, 1.0, 10.0)
            for l1_ratio in (0.0, 0.5, 1.0)
        )
        seeds = sorted(feature_archives)
    results = {}
    prediction_rows = []

    baselines = {
        "raw_expression": (raw, None),
        "pca_64": (raw, 64),
    }
    for name, (features, components) in baselines.items():
        result = nested_group_evaluate(
            features,
            labels,
            groups,
            outer_folds=args.outer_folds,
            inner_folds=args.inner_folds,
            pca_components=components,
            grid=grid,
        )
        results[name] = {
            key: value for key, value in result.items() if key not in {"probabilities", "predictions"}
        }
        prediction_rows.extend(
            {
                "seed": -1,
                "representation": name,
                "sample_id": sample_id,
                "study_id": group,
                "organ": organ,
                "label": int(label),
                "probability": float(probability),
                "prediction": int(prediction),
            }
            for sample_id, group, organ, label, probability, prediction in zip(
                sample_ids,
                groups,
                organs,
                labels,
                result["probabilities"],
                result["predictions"],
            )
        )
    for seed in seeds:
        archive = feature_archives[seed]
        for condition in CONDITIONS:
            if condition == "pooled_plus_organ_label":
                features = np.concatenate(
                    [archive["feature__pooled"], organ_one_hot], axis=1
                )
            else:
                features = archive[f"feature__{condition}"]
            result = nested_group_evaluate(
                features,
                labels,
                groups,
                outer_folds=args.outer_folds,
                inner_folds=args.inner_folds,
                pca_components=None,
                grid=grid,
            )
            key = f"seed{seed}__{condition}"
            results[key] = {
                item: value
                for item, value in result.items()
                if item not in {"probabilities", "predictions"}
            }
            prediction_rows.extend(
                {
                    "seed": seed,
                    "representation": condition,
                    "sample_id": sample_id,
                    "study_id": group,
                    "organ": organ,
                    "label": int(label),
                    "probability": float(probability),
                    "prediction": int(prediction),
                }
                for sample_id, group, organ, label, probability, prediction in zip(
                    sample_ids,
                    groups,
                    organs,
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
        "role": "stage1_osdr_downstream_development",
        "smoke": bool(args.smoke),
        "protocol_sha256": sha256_file(protocol_path),
        "n_samples": int(len(labels)),
        "n_studies": int(np.unique(groups).size),
        "outer_folds": int(args.outer_folds),
        "inner_folds": int(args.inner_folds),
        "hyperparameter_grid": [
            {"C": c_value, "l1_ratio": l1_ratio} for c_value, l1_ratio in grid
        ],
        "best_seed_selection": False,
        "results": results,
        "predictions_sha256": sha256_file(predictions_path),
    }
    report_path = output_dir / "evaluation_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (output_dir / "COMPLETE").write_text("complete\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
