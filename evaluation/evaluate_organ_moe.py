#!/usr/bin/env python3
"""Evaluate a K-organ routed ensemble from a generic prediction cache.

The final-test labels and reconstruction targets are used only after all fixed,
metadata-conditioned, and blind routing rules have been fit on the calibration
split.  Primary estimates give every organ equal weight and every connected study
equal weight within organ; sample-weighted natural-distribution estimates are
reported as secondary diagnostics.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, log_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    from .cache_organ_predictions import _sha256_array
    from .headroom_metrics import (
        balanced_group_mean,
        mse_rows,
        paired_bootstrap_ci,
        pearson_rows,
    )
except ImportError:  # Direct execution: python evaluation/evaluate_organ_moe.py
    from cache_organ_predictions import _sha256_array
    from headroom_metrics import balanced_group_mean, mse_rows, paired_bootstrap_ci, pearson_rows


SCHEMA_VERSION = 2
EPS = 1e-12


def masked_gate_features(values: np.ndarray, mask_idx: np.ndarray, mask_token: float) -> np.ndarray:
    """Return observed expression with every reconstruction target hidden."""
    features = np.asarray(values, dtype=np.float32).copy()
    mask_idx = np.asarray(mask_idx, dtype=np.int64)
    if features.ndim != 2 or mask_idx.ndim != 2 or features.shape[0] != mask_idx.shape[0]:
        raise ValueError("values and mask_idx must be compatible rank-2 arrays")
    features[np.arange(len(features))[:, None], mask_idx] = float(mask_token)
    return features


def _project_simplex_rows(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    one_dimensional = values.ndim == 1
    if one_dimensional:
        values = values[None, :]
    if values.ndim != 2 or values.shape[1] < 1:
        raise ValueError("simplex projection expects a nonempty vector or matrix")
    ordered = np.sort(values, axis=1)[:, ::-1]
    cssv = np.cumsum(ordered, axis=1) - 1.0
    divisors = np.arange(1, values.shape[1] + 1, dtype=np.float64)
    active = ordered - cssv / divisors > 0.0
    rho = active.sum(axis=1) - 1
    theta = cssv[np.arange(len(values)), rho] / (rho + 1.0)
    projected = np.maximum(values - theta[:, None], 0.0)
    return projected[0] if one_dimensional else projected


def _solve_simplex_quadratic(gram: np.ndarray, rhs: np.ndarray) -> np.ndarray:
    """Solve a small convex simplex quadratic by enumerating every active face."""
    gram = np.asarray(gram, dtype=np.float64)
    rhs = np.asarray(rhs, dtype=np.float64)
    k = len(rhs)
    if gram.shape != (k, k) or k < 1:
        raise ValueError("simplex quadratic dimensions are invalid")
    if k > 10:
        raise ValueError(
            "exact Stage 1 simplex solver supports at most 10 experts; "
            "add a verified large-K solver before scaling"
        )
    best_weights = None
    best_objective = float("inf")
    for bits in range(1, 1 << k):
        active = np.asarray([index for index in range(k) if bits & (1 << index)])
        subgram = gram[np.ix_(active, active)]
        system = np.block([
            [subgram, np.ones((len(active), 1), dtype=np.float64)],
            [np.ones((1, len(active)), dtype=np.float64), np.zeros((1, 1))],
        ])
        target = np.r_[rhs[active], 1.0]
        solution = np.linalg.lstsq(system, target, rcond=None)[0][:-1]
        if np.any(solution < -1e-9):
            continue
        solution = np.maximum(solution, 0.0)
        if solution.sum() <= 0:
            continue
        solution /= solution.sum()
        weights = np.zeros(k, dtype=np.float64)
        weights[active] = solution
        objective = float(weights @ gram @ weights - 2.0 * rhs @ weights)
        if objective < best_objective:
            best_objective = objective
            best_weights = weights
    if best_weights is None:
        raise RuntimeError("simplex solver found no feasible active face")
    vertex_objectives = np.diag(gram) - 2.0 * rhs
    if best_objective > float(vertex_objectives.min()) + 1e-8:
        raise RuntimeError("simplex solution is worse than the best single expert")
    if np.any(best_weights < -1e-10) or not np.isclose(best_weights.sum(), 1.0):
        raise RuntimeError("simplex solver returned infeasible weights")
    return best_weights


def fit_simplex_weights(
    pred_masked: np.ndarray,
    true_masked: np.ndarray,
    sample_weight: np.ndarray | None = None,
    max_iter: int = 2000,
    tolerance: float = 1e-11,
) -> np.ndarray:
    """Fit arbitrary-K convex MSE weights with deterministic projected FISTA."""
    pred = np.asarray(pred_masked, dtype=np.float64)
    true = np.asarray(true_masked, dtype=np.float64)
    if pred.ndim != 3 or true.shape != pred.shape[1:]:
        raise ValueError("pred_masked must be (experts, samples, genes) matching true_masked")
    n_experts, n_samples, n_positions = pred.shape
    if sample_weight is None:
        weight = np.ones(n_samples, dtype=np.float64)
    else:
        weight = np.asarray(sample_weight, dtype=np.float64)
        if weight.shape != (n_samples,) or np.any(weight < 0) or not np.any(weight > 0):
            raise ValueError("sample_weight must be nonnegative with one positive value per sample")
    weight = weight / weight.sum()
    gram = np.einsum("n,enp,fnp->ef", weight, pred, pred) / n_positions
    rhs = np.einsum("n,enp,np->e", weight, pred, true) / n_positions
    return _solve_simplex_quadratic(gram, rhs)


def per_sample_simplex_weights(
    pred_masked: np.ndarray,
    true_masked: np.ndarray,
    max_iter: int = 500,
    tolerance: float = 1e-9,
) -> np.ndarray:
    """Vectorized arbitrary-K per-sample convex MSE oracle."""
    pred = np.asarray(pred_masked, dtype=np.float64)
    true = np.asarray(true_masked, dtype=np.float64)
    if pred.ndim != 3 or true.shape != pred.shape[1:]:
        raise ValueError("pred_masked must be (experts, samples, genes) matching true_masked")
    n_experts, n_samples, n_positions = pred.shape
    gram = np.einsum("enp,fnp->nef", pred, pred) / n_positions
    rhs = np.einsum("enp,np->ne", pred, true) / n_positions
    return np.stack(
        [_solve_simplex_quadratic(gram[row], rhs[row]) for row in range(n_samples)]
    )


def apply_sample_weights(pred_masked: np.ndarray, weights: np.ndarray) -> np.ndarray:
    pred = np.asarray(pred_masked, dtype=np.float64)
    weights = np.asarray(weights, dtype=np.float64)
    if pred.ndim != 3 or weights.shape != (pred.shape[1], pred.shape[0]):
        raise ValueError("weights must have shape (samples, experts)")
    return np.einsum("ne,enp->np", weights, pred)


def _balanced_metric_weights(organs: np.ndarray, groups: np.ndarray) -> np.ndarray:
    """Give each organ equal total mass and each study equal mass within organ."""
    organs = np.asarray(organs).astype(str)
    groups = np.asarray(groups).astype(str)
    weights = np.zeros(len(organs), dtype=np.float64)
    labels = np.unique(organs)
    for organ in labels:
        organ_rows = organs == organ
        organ_groups = np.unique(groups[organ_rows])
        for group in organ_groups:
            rows = organ_rows & (groups == group)
            weights[rows] = 1.0 / (len(labels) * len(organ_groups) * rows.sum())
    return weights / weights.sum()


def _classifier_sample_weights(organs: np.ndarray, groups: np.ndarray) -> np.ndarray:
    """Equalize studies inside class while leaving class balancing to sklearn."""
    organs = np.asarray(organs).astype(str)
    groups = np.asarray(groups).astype(str)
    weights = np.zeros(len(organs), dtype=np.float64)
    for organ in np.unique(organs):
        organ_rows = organs == organ
        n_organ = int(organ_rows.sum())
        organ_groups = np.unique(groups[organ_rows])
        for group in organ_groups:
            rows = organ_rows & (groups == group)
            weights[rows] = n_organ / (len(organ_groups) * rows.sum())
    return weights / weights.mean()


def fit_blind_router(
    calibration_features: np.ndarray,
    calibration_organs: np.ndarray,
    calibration_groups: np.ndarray,
    seed: int,
    max_iter: int = 2000,
):
    """Fit a balanced K-class router using calibration inputs and labels only."""
    labels = np.asarray(calibration_organs).astype(str)
    if len(np.unique(labels)) < 2:
        raise ValueError("blind router requires at least two calibration organs")
    weights = _classifier_sample_weights(labels, calibration_groups)
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(
            C=1.0,
            solver="lbfgs",
            class_weight="balanced",
            max_iter=max_iter,
            random_state=seed,
        ),
    )
    model.fit(
        np.asarray(calibration_features, dtype=np.float32),
        labels,
        logisticregression__sample_weight=weights,
    )
    return model, weights


def _masked_values(values: np.ndarray, mask_idx: np.ndarray) -> np.ndarray:
    values = np.asarray(values)
    mask_idx = np.asarray(mask_idx, dtype=np.int64)
    if values.ndim != 2 or mask_idx.shape[0] != values.shape[0]:
        raise ValueError("values and masks must have matching sample axes")
    return values[np.arange(len(values))[:, None], mask_idx]


def _masked_predictions(predictions: np.ndarray, mask_idx: np.ndarray) -> np.ndarray:
    predictions = np.asarray(predictions)
    if predictions.ndim != 3 or predictions.shape[1] != mask_idx.shape[0]:
        raise ValueError("predictions and masks must have matching sample axes")
    return np.take_along_axis(predictions, mask_idx[None, :, :], axis=2)


def _condition_arrays(
    prediction: np.ndarray,
    target: np.ndarray,
    baseline: np.ndarray,
) -> dict[str, np.ndarray]:
    return {
        "mse": mse_rows(prediction, target),
        "pearson": pearson_rows(prediction, target),
        "residual_pearson": pearson_rows(prediction - baseline, target - baseline),
    }


def _summarize_condition(
    arrays: dict[str, np.ndarray], groups: np.ndarray, organs: np.ndarray
) -> dict:
    summary: dict[str, object] = {
        "primary_balanced_organ_study_macro": {},
        "secondary_natural_sample_mean": {},
        "secondary_natural_study_macro": {},
        "by_organ_study_macro": {},
    }
    for metric, values in arrays.items():
        summary["primary_balanced_organ_study_macro"][metric] = balanced_group_mean(
            values, groups=groups, strata=organs
        )
        summary["secondary_natural_sample_mean"][metric] = float(np.nanmean(values))
        summary["secondary_natural_study_macro"][metric] = balanced_group_mean(
            values, groups=groups
        )
    for organ in np.unique(organs):
        keep = organs == organ
        summary["by_organ_study_macro"][organ] = {
            metric: balanced_group_mean(values[keep], groups=groups[keep])
            for metric, values in arrays.items()
        }
    return summary


def _comparison(
    name: str,
    candidate: dict[str, np.ndarray],
    reference: dict[str, np.ndarray],
    groups: np.ndarray,
    organs: np.ndarray,
    seed: int,
    bootstrap_reps: int,
) -> dict:
    mse_gain = reference["mse"] - candidate["mse"]
    pearson_gain = candidate["pearson"] - reference["pearson"]
    residual_gain = candidate["residual_pearson"] - reference["residual_pearson"]
    candidate_mse = balanced_group_mean(candidate["mse"], groups=groups, strata=organs)
    reference_mse = balanced_group_mean(reference["mse"], groups=groups, strata=organs)
    natural_candidate_mse = float(np.nanmean(candidate["mse"]))
    natural_reference_mse = float(np.nanmean(reference["mse"]))

    def ci(values: np.ndarray, offset: int) -> list[float]:
        return list(
            paired_bootstrap_ci(
                values,
                seed=seed + offset,
                n_bootstrap=bootstrap_reps,
                groups=groups,
                strata=organs,
            )
        )

    return {
        "name": name,
        "primary": {
            "mse_improvement_mean": balanced_group_mean(mse_gain, groups, organs),
            "mse_improvement_ci95": ci(mse_gain, 0),
            "relative_mse_reduction": (
                (reference_mse - candidate_mse) / reference_mse
                if abs(reference_mse) > EPS else float("nan")
            ),
            "pearson_gain_mean": balanced_group_mean(pearson_gain, groups, organs),
            "pearson_gain_ci95": ci(pearson_gain, 1),
            "residual_pearson_gain_mean": balanced_group_mean(
                residual_gain, groups, organs
            ),
            "residual_pearson_gain_ci95": ci(residual_gain, 2),
            "candidate_mse": candidate_mse,
            "reference_mse": reference_mse,
        },
        "secondary_natural": {
            "mse_improvement_mean": float(np.nanmean(mse_gain)),
            "relative_mse_reduction": (
                (natural_reference_mse - natural_candidate_mse) / natural_reference_mse
                if abs(natural_reference_mse) > EPS else float("nan")
            ),
            "pearson_gain_mean": float(np.nanmean(pearson_gain)),
            "residual_pearson_gain_mean": float(np.nanmean(residual_gain)),
            "candidate_mse": natural_candidate_mse,
            "reference_mse": natural_reference_mse,
        },
    }


def _organ_train_baseline(
    gt: np.ndarray,
    organs: np.ndarray,
    train: np.ndarray,
    test_organs: np.ndarray,
    test_mask_idx: np.ndarray,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    global_mean = np.mean(gt[train], axis=0)
    means: dict[str, np.ndarray] = {}
    for organ in np.unique(test_organs):
        rows = train & (organs == organ)
        if not np.any(rows):
            raise ValueError(f"training split lacks organ {organ!r} for gene-mean baseline")
        means[organ] = np.mean(gt[rows], axis=0)
    baseline_full = np.stack([means[organ] for organ in test_organs])
    baseline_masked = _masked_values(baseline_full, test_mask_idx)
    return baseline_masked, {"global": global_mean, **means}


def _parse_cache(path: Path) -> dict[str, np.ndarray | dict]:
    with np.load(path, allow_pickle=False) as z:
        required = {
            "sample_ids", "organs", "series_group_id", "split", "genes", "gt",
            "train_eligible", "random_shard", "mask_idx", "model_names",
            "predictions", "metadata_json",
        }
        missing = required - set(z.files)
        if missing:
            raise ValueError(f"prediction cache lacks required fields: {sorted(missing)}")
        data: dict[str, np.ndarray | dict] = {key: np.asarray(z[key]) for key in required - {"metadata_json"}}
        data["metadata"] = json.loads(str(z["metadata_json"].item()))
    return data


def _validate_cache_content(data: dict[str, np.ndarray | dict]) -> None:
    metadata = data["metadata"]
    assert isinstance(metadata, dict)
    if metadata.get("value_space") != "log1p_tpm":
        raise ValueError(
            "organ evaluation requires log1p(TPM) targets and predictions; "
            f"cache declares {metadata.get('value_space')!r}"
        )
    contract = metadata.get("value_space_contract")
    if not isinstance(contract, dict) or any(
        contract.get(field) != "log1p_tpm"
        for field in ("prediction_input", "cache_targets", "cache_predictions")
    ):
        raise ValueError("cache lacks a validated log1p(TPM) value-space contract")
    expected = metadata.get("content_sha256", {})
    mapping = {
        "sample_ids": data["sample_ids"],
        "organs": data["organs"],
        "series_group_id": data["series_group_id"],
        "split": data["split"],
        "train_eligible": data["train_eligible"],
        "random_shard": data["random_shard"],
        "genes": data["genes"],
        "expression": data["gt"],
        "predictions": data["predictions"],
        "mask_idx": data["mask_idx"],
        "model_names": data["model_names"],
    }
    for name, values in mapping.items():
        if expected.get(name) != _sha256_array(np.asarray(values)):
            raise ValueError(f"cache content hash mismatch for {name}")


def evaluate(args: argparse.Namespace) -> dict:
    cache_path = Path(args.cache)
    data = _parse_cache(cache_path)
    _validate_cache_content(data)
    sample_ids = np.asarray(data["sample_ids"]).astype(str)
    organs = np.asarray(data["organs"]).astype(str)
    groups = np.asarray(data["series_group_id"]).astype(str)
    splits = np.asarray(data["split"]).astype(str)
    train_eligible = np.asarray(data["train_eligible"], dtype=bool)
    genes = np.asarray(data["genes"]).astype(str)
    gt = np.asarray(data["gt"], dtype=np.float32)
    mask_idx = np.asarray(data["mask_idx"], dtype=np.int64)
    model_names = np.asarray(data["model_names"]).astype(str)
    predictions = np.asarray(data["predictions"], dtype=np.float32)
    metadata = data["metadata"]
    assert isinstance(metadata, dict)
    if "training_seed" not in metadata:
        raise ValueError("cache lacks bound training_seed provenance")
    training_seed = int(metadata["training_seed"])
    requested_training_seed = getattr(args, "training_seed", None)
    if requested_training_seed is not None and int(requested_training_seed) != training_seed:
        raise ValueError(
            f"requested training seed {requested_training_seed} does not match "
            f"cache provenance {training_seed}"
        )

    expected_shape = (len(model_names), len(sample_ids), len(genes))
    if predictions.shape != expected_shape or gt.shape != expected_shape[1:]:
        raise ValueError("cache matrices do not match identifier dimensions")
    if mask_idx.shape[0] != len(sample_ids):
        raise ValueError("mask_idx sample axis differs from cache")

    calibration = splits == args.calibration_split
    test = splits == args.test_split
    train_split_rows = splits == args.train_split
    if np.any(train_eligible & ~train_split_rows):
        raise ValueError("cache training eligibility includes rows outside train split")
    train = train_split_rows & train_eligible
    for label, rows in (("calibration", calibration), ("test", test), ("train", train)):
        if not np.any(rows):
            raise ValueError(f"cache has no {label} rows for requested split")
    split_overlap = {
        "train_calibration": sorted(set(groups[train_split_rows]) & set(groups[calibration])),
        "train_test": sorted(set(groups[train_split_rows]) & set(groups[test])),
        "calibration_test": sorted(set(groups[calibration]) & set(groups[test])),
    }
    if any(split_overlap.values()):
        raise ValueError(f"connected-study split leakage detected: {split_overlap}")

    name_to_index = {name: index for index, name in enumerate(model_names)}
    if len(name_to_index) != len(model_names) or "pooled" not in name_to_index:
        raise ValueError("model_names must be unique and contain pooled")
    organ_models = {
        name.split(":", 1)[1]: index
        for name, index in name_to_index.items() if name.startswith("organ:")
    }
    random_models = {
        name.split(":", 1)[1]: index
        for name, index in name_to_index.items() if name.startswith("random:")
    }
    if not organ_models or len(random_models) != len(organ_models):
        raise ValueError("organ experts require an equal number of matched random-shard experts")
    required_organs = set(organs[calibration]) | set(organs[test])
    missing_experts = required_organs - set(organ_models)
    if missing_experts:
        raise ValueError(f"missing organ experts for {sorted(missing_experts)}")
    expert_organs = sorted(organ_models)
    random_names = sorted(random_models)
    organ_indices = np.asarray([organ_models[label] for label in expert_organs])
    random_indices = np.asarray([random_models[label] for label in random_names])

    pred_masked = _masked_predictions(predictions, mask_idx)
    true_masked = _masked_values(gt, mask_idx)
    calibration_weight = _balanced_metric_weights(organs[calibration], groups[calibration])
    organ_calibration_pred = pred_masked[organ_indices][:, calibration]
    random_calibration_pred = pred_masked[random_indices][:, calibration]
    calibration_true = true_masked[calibration]

    fixed_organ_weights = fit_simplex_weights(
        organ_calibration_pred, calibration_true, calibration_weight
    )
    fixed_random_weights = fit_simplex_weights(
        random_calibration_pred, calibration_true, calibration_weight
    )
    soft_weights_by_organ: dict[str, np.ndarray] = {}
    calibration_best_random_by_organ: dict[str, str] = {}
    calibration_random_mse_by_organ: dict[str, dict[str, float]] = {}
    calibration_organs = organs[calibration]
    calibration_groups = groups[calibration]
    for organ in expert_organs:
        keep = calibration_organs == organ
        if not np.any(keep):
            raise ValueError(f"calibration split lacks organ {organ!r}")
        group_weight = _balanced_metric_weights(
            calibration_organs[keep], calibration_groups[keep]
        )
        soft_weights_by_organ[organ] = fit_simplex_weights(
            organ_calibration_pred[:, keep], calibration_true[keep], group_weight
        )
        random_mse = np.mean(
            (random_calibration_pred[:, keep] - calibration_true[keep][None, :, :]) ** 2,
            axis=2,
        )
        random_score = random_mse @ group_weight
        best_random_index = int(np.argmin(random_score))
        calibration_best_random_by_organ[organ] = random_names[best_random_index]
        calibration_random_mse_by_organ[organ] = {
            label: float(random_score[index])
            for index, label in enumerate(random_names)
        }

    mask_token = float(metadata.get("mask_token", args.mask_token))
    gate_features = masked_gate_features(gt, mask_idx, mask_token)
    classifier, classifier_weights = fit_blind_router(
        gate_features[calibration], calibration_organs, calibration_groups,
        seed=args.seed, max_iter=args.classifier_max_iter,
    )
    test_prob_raw = classifier.predict_proba(gate_features[test])
    classifier_classes = classifier.named_steps["logisticregression"].classes_.astype(str)
    test_prob = np.zeros((int(test.sum()), len(expert_organs)), dtype=np.float64)
    for class_index, label in enumerate(classifier_classes):
        if label not in organ_models:
            raise ValueError(f"router emitted class without organ expert: {label!r}")
        test_prob[:, expert_organs.index(label)] = test_prob_raw[:, class_index]
    if not np.allclose(test_prob.sum(axis=1), 1.0):
        raise RuntimeError("router probabilities do not cover all organ experts")
    predicted_organs = np.asarray(expert_organs)[np.argmax(test_prob, axis=1)]

    test_true = true_masked[test]
    test_organs = organs[test]
    test_groups = groups[test]
    test_organ_pred = pred_masked[organ_indices][:, test]
    test_random_pred = pred_masked[random_indices][:, test]
    n_test = len(test_true)
    fixed_organ_matrix = np.repeat(fixed_organ_weights[None, :], n_test, axis=0)
    fixed_random_matrix = np.repeat(fixed_random_weights[None, :], n_test, axis=0)
    true_hard_weights = np.zeros_like(fixed_organ_matrix)
    true_soft_weights = np.empty_like(fixed_organ_matrix)
    blind_hard_weights = np.zeros_like(fixed_organ_matrix)
    calibration_random_hard_weights = np.zeros_like(fixed_random_matrix)
    for row, (truth, predicted) in enumerate(zip(test_organs, predicted_organs)):
        true_hard_weights[row, expert_organs.index(truth)] = 1.0
        true_soft_weights[row] = soft_weights_by_organ[truth]
        blind_hard_weights[row, expert_organs.index(predicted)] = 1.0
        selected_random = calibration_best_random_by_organ[truth]
        calibration_random_hard_weights[row, random_names.index(selected_random)] = 1.0

    soft_oracle_weights = per_sample_simplex_weights(test_organ_pred, test_true)
    random_oracle_weights = per_sample_simplex_weights(test_random_pred, test_true)
    hard_oracle_index = np.argmin(
        np.mean((test_organ_pred - test_true[None, :, :]) ** 2, axis=2), axis=0
    )
    hard_oracle_weights = np.zeros_like(fixed_organ_matrix)
    hard_oracle_weights[np.arange(n_test), hard_oracle_index] = 1.0

    condition_predictions: dict[str, np.ndarray] = {
        "pooled": pred_masked[name_to_index["pooled"], test],
        "organ_fixed": apply_sample_weights(test_organ_pred, fixed_organ_matrix),
        "true_organ_hard": apply_sample_weights(test_organ_pred, true_hard_weights),
        "true_organ_soft": apply_sample_weights(test_organ_pred, true_soft_weights),
        "blind_organ_hard": apply_sample_weights(test_organ_pred, blind_hard_weights),
        "blind_organ_soft": apply_sample_weights(test_organ_pred, test_prob),
        "hard_oracle": apply_sample_weights(test_organ_pred, hard_oracle_weights),
        "soft_oracle": apply_sample_weights(test_organ_pred, soft_oracle_weights),
        "random_fixed": apply_sample_weights(test_random_pred, fixed_random_matrix),
        "random_soft_oracle": apply_sample_weights(test_random_pred, random_oracle_weights),
        "calibration_best_random_by_true_organ": apply_sample_weights(
            test_random_pred, calibration_random_hard_weights
        ),
    }
    for label, index in organ_models.items():
        condition_predictions[f"expert:{label}"] = pred_masked[index, test]
    for label, index in random_models.items():
        condition_predictions[f"random_expert:{label}"] = pred_masked[index, test]

    baseline_masked, baseline_means = _organ_train_baseline(
        gt, organs, train, test_organs, mask_idx[test]
    )
    condition_predictions["organ_gene_mean"] = baseline_masked
    condition_arrays = {
        name: _condition_arrays(prediction, test_true, baseline_masked)
        for name, prediction in condition_predictions.items()
    }
    condition_summaries = {
        name: _summarize_condition(arrays, test_groups, test_organs)
        for name, arrays in condition_arrays.items()
    }

    pair_specs = (
        ("pooled_vs_gene_mean", "pooled", "organ_gene_mean"),
        ("true_organ_hard_vs_pooled", "true_organ_hard", "pooled"),
        ("true_organ_soft_vs_organ_fixed", "true_organ_soft", "organ_fixed"),
        ("organ_fixed_vs_random_fixed", "organ_fixed", "random_fixed"),
        ("blind_hard_vs_pooled", "blind_organ_hard", "pooled"),
        ("blind_hard_vs_organ_fixed", "blind_organ_hard", "organ_fixed"),
        ("blind_soft_vs_pooled", "blind_organ_soft", "pooled"),
        ("blind_soft_vs_organ_fixed", "blind_organ_soft", "organ_fixed"),
        ("soft_oracle_vs_organ_fixed", "soft_oracle", "organ_fixed"),
        ("random_soft_oracle_vs_random_fixed", "random_soft_oracle", "random_fixed"),
        (
            "true_organ_hard_vs_calibration_best_random_by_organ",
            "true_organ_hard",
            "calibration_best_random_by_true_organ",
        ),
    )
    comparisons = {
        name: _comparison(
            name,
            condition_arrays[candidate],
            condition_arrays[reference],
            test_groups,
            test_organs,
            args.seed + 20 * index,
            args.bootstrap_reps,
        )
        for index, (name, candidate, reference) in enumerate(pair_specs)
    }
    true_gain = comparisons["true_organ_hard_vs_pooled"]["primary"]["mse_improvement_mean"]
    blind_gain = comparisons["blind_hard_vs_pooled"]["primary"]["mse_improvement_mean"]
    blind_recovery = blind_gain / true_gain if true_gain > EPS else float("nan")

    backbone_by_organ = {}
    direct_random_controls_by_organ = {}
    for index, organ in enumerate(expert_organs):
        keep = test_organs == organ
        if not np.any(keep):
            raise ValueError(f"test split lacks organ {organ!r}")
        backbone_by_organ[organ] = _comparison(
            f"expert_{organ}_vs_gene_mean",
            {metric: values[keep] for metric, values in condition_arrays[f"expert:{organ}"].items()},
            {metric: values[keep] for metric, values in condition_arrays["organ_gene_mean"].items()},
            test_groups[keep],
            test_organs[keep],
            args.seed + 1000 + index * 5,
            args.bootstrap_reps,
        )
        matching_arrays = {
            metric: values[keep]
            for metric, values in condition_arrays[f"expert:{organ}"].items()
        }
        random_comparisons = {}
        for random_index, random_name in enumerate(random_names):
            random_comparisons[random_name] = _comparison(
                f"expert_{organ}_vs_random_{random_name}",
                matching_arrays,
                {
                    metric: values[keep]
                    for metric, values in condition_arrays[
                        f"random_expert:{random_name}"
                    ].items()
                },
                test_groups[keep],
                test_organs[keep],
                args.seed + 2000 + index * 100 + random_index * 5,
                args.bootstrap_reps,
            )
        selected_random = calibration_best_random_by_organ[organ]
        direct_random_controls_by_organ[organ] = {
            "calibration_selected_random_expert": selected_random,
            "calibration_random_mse": calibration_random_mse_by_organ[organ],
            "matching_organ_vs_each_random": random_comparisons,
            "matching_organ_vs_calibration_selected_random": random_comparisons[
                selected_random
            ],
        }

    test_label_to_index = {label: index for index, label in enumerate(expert_organs)}
    y_true = np.asarray([test_label_to_index[label] for label in test_organs])
    y_pred = np.asarray([test_label_to_index[label] for label in predicted_organs])
    router_report = {
        "training_split": args.calibration_split,
        "uses_reconstruction_targets": False,
        "uses_test_labels_or_targets_for_fit": False,
        "class_weight": "balanced",
        "sampling_weight": "equal connected-study mass within organ class",
        "n_calibration_samples": int(calibration.sum()),
        "n_calibration_groups": int(len(np.unique(calibration_groups))),
        "calibration_sample_id_sha256": _sha256_array(sample_ids[calibration]),
        "calibration_observed_feature_sha256": _sha256_array(gate_features[calibration]),
        "classes": expert_organs,
        "test_accuracy": float(accuracy_score(y_true, y_pred)),
        "test_balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "test_log_loss": float(log_loss(y_true, test_prob, labels=np.arange(len(expert_organs)))),
        "test_confusion_matrix": confusion_matrix(
            y_true, y_pred, labels=np.arange(len(expert_organs))
        ).tolist(),
        "classifier_weight_min": float(classifier_weights.min()),
        "classifier_weight_max": float(classifier_weights.max()),
    }

    frame = pd.DataFrame({
        "sample_id": sample_ids[test],
        "organ": test_organs,
        "series_group_id": test_groups,
        "predicted_organ": predicted_organs,
    })
    for index, organ in enumerate(expert_organs):
        frame[f"router_probability__{organ}"] = test_prob[:, index]
    for condition, arrays in condition_arrays.items():
        safe = condition.replace(":", "__")
        for metric, values in arrays.items():
            frame[f"{safe}__{metric}"] = values

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = output_dir / "per_sample_metrics.csv"
    frame.to_csv(metrics_path, index=False)
    report = {
        "schema_version": SCHEMA_VERSION,
        "claim": "K-class calibration-only blind organ routing on frozen predictions",
        "training_seed": training_seed,
        "model_bundle_sha256": metadata.get("model_bundle_sha256"),
        "evaluation_seed": int(args.seed),
        "cache": str(cache_path.resolve()),
        "cache_metadata": metadata,
        "validation": {
            "leakage_free": True,
            "connected_study_overlap": split_overlap,
            "random_shard_count_matches_organs": len(random_models) == len(organ_models),
            "mask_hash_verified": True,
            "prediction_masks_match_cache": metadata.get("prediction_masks_verified") is True,
            "sample_hash_verified": True,
            "gene_hash_verified": True,
        },
        "splits": {
            "train": args.train_split,
            "calibration": args.calibration_split,
            "test": args.test_split,
            "n_train": int(train.sum()),
            "n_train_split_rows": int(train_split_rows.sum()),
            "n_calibration": int(calibration.sum()),
            "n_test": int(test.sum()),
            "n_test_groups": int(len(np.unique(test_groups))),
            "test_sample_id_sha256": _sha256_array(sample_ids[test]),
            "test_group_id_sha256": _sha256_array(test_groups),
            "test_organ_sha256": _sha256_array(test_organs),
            "mask_idx_sha256": _sha256_array(mask_idx[test]),
        },
        "models": {
            "model_names": model_names.tolist(),
            "organ_expert_order": expert_organs,
            "random_expert_order": random_names,
        },
        "calibration_rules": {
            "primary_weighting": "equal organ, then equal connected study within organ",
            "organ_fixed_weights": fixed_organ_weights.tolist(),
            "random_fixed_weights": fixed_random_weights.tolist(),
            "soft_weights_by_true_organ": {
                label: weights.tolist() for label, weights in soft_weights_by_organ.items()
            },
            "calibration_best_random_by_true_organ": calibration_best_random_by_organ,
        },
        "router": router_report,
        "baselines": {
            "source_split": args.train_split,
            "training_filter_column": metadata.get("training_eligibility", {}).get("column"),
            "n_training_rows": int(train.sum()),
            "training_sample_id_sha256": _sha256_array(sample_ids[train]),
            "type": "organ-specific train-only gene mean",
            "mean_sha256": {
                label: _sha256_array(values) for label, values in baseline_means.items()
            },
        },
        "conditions": condition_summaries,
        "comparisons": comparisons,
        "blind_hard_recovery_of_true_organ_gain": float(blind_recovery),
        "backbone_checks": {
            "pooled_vs_gene_mean": comparisons["pooled_vs_gene_mean"],
            "by_organ": backbone_by_organ,
        },
        "exploratory_random_controls": {
            "gating": False,
            "interpretation": (
                "post-seed-42 diagnostic; does not replace organ_fixed_vs_random_fixed"
            ),
            "selection_split": args.calibration_split,
            "uses_test_targets_for_selection": False,
            "uses_test_organ_for_routing": True,
            "global_true_organ_hard_vs_calibration_best_random_by_organ": comparisons[
                "true_organ_hard_vs_calibration_best_random_by_organ"
            ],
            "by_organ": direct_random_controls_by_organ,
        },
        "per_sample_metrics_csv": str(metrics_path.resolve()),
    }
    report_path = output_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--train-split", default="train")
    parser.add_argument("--calibration-split", default="calibration")
    parser.add_argument("--test-split", default="test")
    parser.add_argument("--mask-token", type=float, default=-10.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--training-seed", type=int,
        help="Optional assertion; the report seed is derived from prediction provenance.",
    )
    parser.add_argument("--bootstrap-reps", type=int, default=2000)
    parser.add_argument("--classifier-max-iter", type=int, default=2000)
    args = parser.parse_args()
    report = evaluate(args)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
