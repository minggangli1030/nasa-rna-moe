#!/usr/bin/env python3
"""Evaluate an expression-only species gate on frozen expert predictions."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, log_loss, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from headroom_metrics import (
    apply_sample_weights,
    balanced_group_mean,
    masked_values,
    mse_rows,
    paired_bootstrap_ci,
    pearson_rows,
    simplex_least_squares,
    soft_oracle_mse_weights,
)


EXPERTS = ("human", "mouse", "mixed")
SPECIES = ("human", "mouse")


def masked_gate_features(values: np.ndarray, mask_idx: np.ndarray, mask_token: float) -> np.ndarray:
    """Return the exact masked expression available to a blind gate."""
    features = np.asarray(values, dtype=np.float32).copy()
    mask_idx = np.asarray(mask_idx, dtype=np.int64)
    if features.ndim != 2 or mask_idx.ndim != 2 or features.shape[0] != mask_idx.shape[0]:
        raise ValueError("values and mask_idx must be compatible rank-2 arrays")
    features[np.arange(len(features))[:, None], mask_idx] = mask_token
    return features


def _sha256_lines(values: np.ndarray) -> str:
    payload = "\n".join(np.asarray(values).astype(str)) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _fit_classifier(
    features: np.ndarray,
    labels: np.ndarray,
    groups: np.ndarray,
    seed: int,
) -> tuple[object, dict]:
    y = (np.asarray(labels).astype(str) == "mouse").astype(np.int64)
    cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)

    def pipeline():
        return make_pipeline(
            StandardScaler(),
            LogisticRegression(
                C=1.0,
                solver="liblinear",
                class_weight="balanced",
                max_iter=2000,
                random_state=seed,
            ),
        )

    oof_prob = cross_val_predict(
        pipeline(), features, y, groups=groups, cv=cv, method="predict_proba", n_jobs=1
    )[:, 1]
    model = pipeline().fit(features, y)
    return model, {
        "n_samples": int(len(y)),
        "n_groups": int(len(np.unique(groups))),
        "oof_accuracy": float(accuracy_score(y, oof_prob >= 0.5)),
        "oof_balanced_accuracy": float(balanced_accuracy_score(y, oof_prob >= 0.5)),
        "oof_roc_auc": float(roc_auc_score(y, oof_prob)),
        "oof_log_loss": float(log_loss(y, np.column_stack([1.0 - oof_prob, oof_prob]))),
    }


def _fit_router(
    pred_masked: np.ndarray,
    true_masked: np.ndarray,
    labels: np.ndarray,
) -> dict:
    design = pred_masked.transpose(1, 2, 0).reshape(-1, len(EXPERTS))
    fixed = simplex_least_squares(design, true_masked.reshape(-1))
    hard: dict[str, int] = {}
    soft: dict[str, np.ndarray] = {}
    for label in SPECIES:
        keep = labels == label
        if not np.any(keep):
            raise ValueError(f"calibration set lacks species {label!r}")
        losses = np.mean(
            (pred_masked[:, keep, :] - true_masked[None, keep, :]) ** 2,
            axis=(1, 2),
        )
        hard[label] = int(np.argmin(losses))
        species_design = pred_masked[:, keep, :].transpose(1, 2, 0).reshape(-1, len(EXPERTS))
        soft[label] = simplex_least_squares(species_design, true_masked[keep].reshape(-1))
    return {"fixed": fixed, "hard": hard, "soft": soft}


def _condition_arrays(
    prediction: np.ndarray,
    target: np.ndarray,
    baseline: np.ndarray,
) -> dict[str, np.ndarray]:
    return {
        "pearson": pearson_rows(prediction, target),
        "residual_pearson": pearson_rows(prediction - baseline, target - baseline),
        "mse": mse_rows(prediction, target),
    }


def _summarize(arrays: dict[str, np.ndarray], groups: np.ndarray, species: np.ndarray) -> dict:
    return {
        "primary_pearson_study_macro": balanced_group_mean(arrays["pearson"], groups, species),
        "primary_residual_pearson_study_macro": balanced_group_mean(
            arrays["residual_pearson"], groups, species
        ),
        "primary_mse_study_macro": balanced_group_mean(arrays["mse"], groups, species),
    }


def _compare(
    name: str,
    candidate: dict[str, np.ndarray],
    reference: dict[str, np.ndarray],
    groups: np.ndarray,
    species: np.ndarray,
    seed: int,
    bootstrap_reps: int,
) -> dict:
    pearson_gain = candidate["pearson"] - reference["pearson"]
    residual_gain = candidate["residual_pearson"] - reference["residual_pearson"]
    mse_improvement = reference["mse"] - candidate["mse"]
    candidate_mse = balanced_group_mean(candidate["mse"], groups, species)
    reference_mse = balanced_group_mean(reference["mse"], groups, species)
    return {
        "name": name,
        "pearson_gain_mean": balanced_group_mean(pearson_gain, groups, species),
        "pearson_gain_ci95": paired_bootstrap_ci(
            pearson_gain, seed, bootstrap_reps, groups=groups, strata=species
        ),
        "residual_pearson_gain_mean": balanced_group_mean(residual_gain, groups, species),
        "residual_pearson_gain_ci95": paired_bootstrap_ci(
            residual_gain, seed + 1, bootstrap_reps, groups=groups, strata=species
        ),
        "mse_improvement_mean": balanced_group_mean(mse_improvement, groups, species),
        "mse_improvement_ci95": paired_bootstrap_ci(
            mse_improvement, seed + 2, bootstrap_reps, groups=groups, strata=species
        ),
        "candidate_mse_mean": candidate_mse,
        "reference_mse_mean": reference_mse,
        "relative_mse_reduction": (reference_mse - candidate_mse) / reference_mse,
    }


def evaluate(args) -> dict:
    cache_path = Path(args.cache)
    z = np.load(cache_path, allow_pickle=False)
    required = {
        "gt_common", "mask_idx_common", "sample_ids", "species", "series_group_id",
        "common_genes", "pred_human", "pred_mouse", "pred_mixed",
    }
    missing = required - set(z.files)
    if missing:
        raise ValueError(f"prediction cache lacks required fields: {sorted(missing)}")

    sample_ids = z["sample_ids"].astype(str)
    species = z["species"].astype(str)
    groups = z["series_group_id"].astype(str)
    strict_ids = {
        line.strip() for line in Path(args.strict_ids).read_text().splitlines() if line.strip()
    }
    test = np.asarray([sample_id in strict_ids for sample_id in sample_ids])
    calibration = ~test
    if int(test.sum()) != len(strict_ids):
        raise ValueError("strict IDs are not an exact subset of the prediction cache")
    overlap = set(groups[calibration]) & set(groups[test])
    if overlap:
        raise ValueError(f"calibration and strict groups overlap: {sorted(overlap)[:5]}")

    true_full = np.asarray(z["gt_common"], dtype=np.float32)
    mask_idx = np.asarray(z["mask_idx_common"], dtype=np.int64)
    gate_features = masked_gate_features(true_full, mask_idx, args.mask_token)
    classifier, calibration_classifier = _fit_classifier(
        gate_features[calibration], species[calibration], groups[calibration], args.seed
    )
    strict_mouse_probability = classifier.predict_proba(gate_features[test])[:, 1]
    strict_predicted_species = np.where(strict_mouse_probability >= 0.5, "mouse", "human")
    strict_true_species = species[test]
    strict_y = (strict_true_species == "mouse").astype(np.int64)

    pred_full = np.stack(
        [np.asarray(z[f"pred_{expert}"], dtype=np.float32) for expert in EXPERTS]
    )
    pred_masked = np.stack(
        [masked_values(pred_full[index], mask_idx) for index in range(len(EXPERTS))]
    )
    true_masked = masked_values(true_full, mask_idx)
    router = _fit_router(
        pred_masked[:, calibration], true_masked[calibration], species[calibration]
    )

    test_pred = pred_masked[:, test, :]
    test_true = true_masked[test]
    fixed_weights = np.repeat(router["fixed"][None, :], int(test.sum()), axis=0)
    metadata_hard_weights = np.zeros((int(test.sum()), len(EXPERTS)), dtype=np.float64)
    blind_hard_weights = np.zeros_like(metadata_hard_weights)
    metadata_soft_weights = np.empty_like(metadata_hard_weights)
    blind_soft_weights = np.empty_like(metadata_hard_weights)
    for row, (truth, predicted, p_mouse) in enumerate(
        zip(strict_true_species, strict_predicted_species, strict_mouse_probability)
    ):
        metadata_hard_weights[row, router["hard"][truth]] = 1.0
        blind_hard_weights[row, router["hard"][predicted]] = 1.0
        metadata_soft_weights[row] = router["soft"][truth]
        blind_soft_weights[row] = (
            (1.0 - p_mouse) * router["soft"]["human"]
            + p_mouse * router["soft"]["mouse"]
        )

    oracle_weights = soft_oracle_mse_weights(test_pred, test_true)
    predictions = {
        "human": test_pred[0],
        "mouse": test_pred[1],
        "mixed": test_pred[2],
        "fixed_calibration": apply_sample_weights(test_pred, fixed_weights),
        "metadata_species_hard_calibration": apply_sample_weights(
            test_pred, metadata_hard_weights
        ),
        "metadata_species_soft_calibration": apply_sample_weights(
            test_pred, metadata_soft_weights
        ),
        "blind_species_hard": apply_sample_weights(test_pred, blind_hard_weights),
        "blind_species_soft": apply_sample_weights(test_pred, blind_soft_weights),
        "soft_oracle": apply_sample_weights(test_pred, oracle_weights),
    }

    mean_artifact = np.load(args.baseline_mean, allow_pickle=False)
    if not np.array_equal(mean_artifact["genes"].astype(str), z["common_genes"].astype(str)):
        raise ValueError("baseline gene order differs from prediction cache")
    baseline_full = np.stack(
        [mean_artifact[f"mean_{label}"] for label in strict_true_species]
    )
    baseline_masked = masked_values(baseline_full, mask_idx[test])
    test_groups = groups[test]
    arrays = {
        name: _condition_arrays(prediction, test_true, baseline_masked)
        for name, prediction in predictions.items()
    }
    conditions = {
        name: _summarize(values, test_groups, strict_true_species)
        for name, values in arrays.items()
    }
    pairs = (
        ("blind_hard_vs_mixed", "blind_species_hard", "mixed"),
        ("blind_hard_vs_fixed", "blind_species_hard", "fixed_calibration"),
        ("blind_soft_vs_mixed", "blind_species_soft", "mixed"),
        ("blind_soft_vs_fixed", "blind_species_soft", "fixed_calibration"),
        ("blind_soft_vs_metadata_soft", "blind_species_soft", "metadata_species_soft_calibration"),
        ("metadata_soft_vs_fixed", "metadata_species_soft_calibration", "fixed_calibration"),
        ("soft_oracle_vs_fixed", "soft_oracle", "fixed_calibration"),
    )
    comparisons = [
        _compare(
            name, arrays[candidate], arrays[reference], test_groups, strict_true_species,
            args.seed + 10 * index, args.bootstrap_reps,
        )
        for index, (name, candidate, reference) in enumerate(pairs)
    ]

    frame = pd.DataFrame({
        "sample_id": sample_ids[test],
        "species": strict_true_species,
        "series_group_id": test_groups,
        "predicted_species": strict_predicted_species,
        "mouse_probability": strict_mouse_probability,
    })
    for name, values in arrays.items():
        for metric, metric_values in values.items():
            frame[f"{name}__{metric}"] = metric_values

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output_dir / "per_sample_metrics.parquet", index=False)
    report = {
        "schema_version": 1,
        "claim": "expression-only blind species gate on frozen 20k experts",
        "cache": str(cache_path.resolve()),
        "mask_token": args.mask_token,
        "calibration": {
            **calibration_classifier,
            "sample_id_sha256": _sha256_lines(sample_ids[calibration]),
        },
        "strict_test": {
            "n_samples": int(test.sum()),
            "n_groups": int(len(np.unique(test_groups))),
            "sample_id_sha256": _sha256_lines(sample_ids[test]),
            "accuracy": float(accuracy_score(strict_y, strict_predicted_species == "mouse")),
            "balanced_accuracy": float(
                balanced_accuracy_score(strict_y, strict_predicted_species == "mouse")
            ),
            "roc_auc": float(roc_auc_score(strict_y, strict_mouse_probability)),
            "log_loss": float(
                log_loss(
                    strict_y,
                    np.column_stack([1.0 - strict_mouse_probability, strict_mouse_probability]),
                )
            ),
            "confusion_matrix_human_mouse": confusion_matrix(
                strict_y, strict_predicted_species == "mouse", labels=[0, 1]
            ).tolist(),
        },
        "router": {
            "expert_order": EXPERTS,
            "fixed_weights": router["fixed"].tolist(),
            "hard_expert_by_species": {
                label: EXPERTS[index] for label, index in router["hard"].items()
            },
            "soft_weights_by_species": {
                label: weights.tolist() for label, weights in router["soft"].items()
            },
        },
        "conditions": conditions,
        "comparisons": comparisons,
    }
    (output_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", required=True)
    parser.add_argument("--strict-ids", required=True)
    parser.add_argument("--baseline-mean", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--mask-token", type=float, default=-10.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--bootstrap-reps", type=int, default=2000)
    args = parser.parse_args()
    report = evaluate(args)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
