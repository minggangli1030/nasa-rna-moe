"""Numerical helpers for the frozen multiaxis Tier-1 screen."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from core.stage2b_diagnostics import grouped_ridge_predictions


def stable_one_hot(values: Sequence[str], categories: Sequence[str] | None = None):
    text = np.asarray([str(value) for value in values], dtype=str)
    levels = (
        tuple(sorted(np.unique(text).tolist()))
        if categories is None
        else tuple(str(value) for value in categories)
    )
    lookup = {value: index for index, value in enumerate(levels)}
    if any(value not in lookup for value in text):
        raise ValueError("categorical value is absent from frozen levels")
    output = np.zeros((len(text), len(levels)), dtype=np.float64)
    output[np.arange(len(text)), [lookup[value] for value in text]] = 1.0
    return output, levels


def fixed_scale_numeric(values: Sequence[float], scale: float) -> np.ndarray:
    raw = np.asarray(values, dtype=np.float64)
    if scale <= 0:
        raise ValueError("numeric scale must be positive")
    missing = ~np.isfinite(raw)
    scaled = np.where(missing, 0.0, raw / float(scale))
    return np.column_stack([scaled, missing.astype(np.float64)])


def incremental_grouped_ridge(
    base: np.ndarray,
    candidate: np.ndarray,
    target: np.ndarray,
    groups: Sequence[str],
    *,
    folds: int,
    fold_seed: int,
    ridge_grid: Sequence[float],
) -> dict:
    y = np.asarray(target, dtype=np.float64)
    if y.ndim == 1:
        y = y[:, None]
    base_prediction, base_folds = grouped_ridge_predictions(
        np.asarray(base, dtype=np.float64),
        y,
        groups,
        folds=folds,
        fold_seed=fold_seed,
        ridge_grid=ridge_grid,
    )
    candidate_prediction, candidate_folds = grouped_ridge_predictions(
        np.column_stack([base, candidate]).astype(np.float64),
        y,
        groups,
        folds=folds,
        fold_seed=fold_seed,
        ridge_grid=ridge_grid,
    )
    centered = y - y.mean(axis=0, keepdims=True)
    denominator = float(np.mean(np.square(centered)))
    base_mse = float(np.mean(np.square(y - base_prediction)))
    candidate_mse = float(np.mean(np.square(y - candidate_prediction)))
    delta = 0.0 if denominator == 0 else (base_mse - candidate_mse) / denominator
    return {
        "base_prediction": base_prediction,
        "candidate_prediction": candidate_prediction,
        "base_mse": base_mse,
        "candidate_mse": candidate_mse,
        "incremental_r2": float(delta),
        "base_folds": base_folds,
        "candidate_folds": candidate_folds,
    }


def permute_within_organ(
    candidate: np.ndarray,
    organs: Sequence[str],
    *,
    seed: int,
) -> np.ndarray:
    values = np.asarray(candidate)
    labels = np.asarray([str(value) for value in organs], dtype=str)
    if len(values) != len(labels):
        raise ValueError("candidate and organ rows differ")
    rng = np.random.default_rng(seed)
    output = values.copy()
    for organ in sorted(np.unique(labels)):
        rows = np.flatnonzero(labels == organ)
        output[rows] = values[rng.permutation(rows)]
    return output


def donor_bootstrap_incremental_r2(
    target: np.ndarray,
    base_prediction: np.ndarray,
    candidate_prediction: np.ndarray,
    donors: Sequence[str],
    *,
    replicates: int,
    seed: int,
) -> dict:
    y = np.asarray(target, dtype=np.float64)
    if y.ndim == 1:
        y = y[:, None]
    base = np.asarray(base_prediction, dtype=np.float64)
    candidate = np.asarray(candidate_prediction, dtype=np.float64)
    groups = np.asarray([str(value) for value in donors], dtype=str)
    unique = np.unique(groups)
    positions = {donor: np.flatnonzero(groups == donor) for donor in unique}
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(replicates):
        sampled = rng.choice(unique, size=len(unique), replace=True)
        rows = np.concatenate([positions[donor] for donor in sampled])
        centered = y[rows] - y[rows].mean(axis=0, keepdims=True)
        denominator = float(np.mean(np.square(centered)))
        base_mse = float(np.mean(np.square(y[rows] - base[rows])))
        candidate_mse = float(np.mean(np.square(y[rows] - candidate[rows])))
        values.append(
            0.0 if denominator == 0 else (base_mse - candidate_mse) / denominator
        )
    return {
        "replicates": int(replicates),
        "median": float(np.median(values)),
        "ci95": np.quantile(values, [0.025, 0.975]).astype(float).tolist(),
    }


def partial_correlations(
    candidate: np.ndarray,
    proxies: np.ndarray,
    organ_one_hot: np.ndarray,
) -> list[list[float]]:
    axis = np.asarray(candidate, dtype=np.float64)
    technical = np.asarray(proxies, dtype=np.float64)
    organ = np.asarray(organ_one_hot, dtype=np.float64)
    design = np.column_stack([np.ones(len(organ)), organ])
    axis_residual = axis - design @ np.linalg.lstsq(design, axis, rcond=None)[0]
    proxy_residual = technical - design @ np.linalg.lstsq(
        design, technical, rcond=None
    )[0]
    output = np.zeros((axis.shape[1], technical.shape[1]), dtype=np.float64)
    for row in range(axis.shape[1]):
        for column in range(technical.shape[1]):
            a = axis_residual[:, row]
            b = proxy_residual[:, column]
            output[row, column] = (
                0.0
                if np.std(a) < 1e-12 or np.std(b) < 1e-12
                else float(np.corrcoef(a, b)[0, 1])
            )
    return output.astype(float).tolist()
