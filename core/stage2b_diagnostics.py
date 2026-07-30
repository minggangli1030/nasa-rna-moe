"""Numerical primitives shared by the frozen Stage 2B diagnostics."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

import numpy as np


def array_sha256(value: np.ndarray) -> str:
    """Hash an array together with its dtype and shape."""

    array = np.ascontiguousarray(value)
    digest = hashlib.sha256()
    digest.update(str(array.dtype).encode("utf-8"))
    digest.update(np.asarray(array.shape, dtype=np.int64).tobytes())
    digest.update(array.tobytes())
    return digest.hexdigest()


def fixed_decoder_ridge(
    residual: np.ndarray,
    decoder: np.ndarray,
    ridge_lambda: float,
) -> np.ndarray:
    """Solve coefficients for residual ~= coefficients @ decoder."""

    residual = np.asarray(residual, dtype=np.float64)
    decoder = np.asarray(decoder, dtype=np.float64)
    if residual.ndim != 2 or decoder.ndim != 2:
        raise ValueError("residual and decoder must be matrices")
    if residual.shape[1] != decoder.shape[1]:
        raise ValueError("residual and decoder gene dimensions differ")
    if ridge_lambda < 0 or not np.isfinite(residual).all():
        raise ValueError("ridge must be nonnegative and residual finite")
    gram = decoder @ decoder.T
    right = residual @ decoder.T
    try:
        solved = np.linalg.solve(
            gram + float(ridge_lambda) * np.eye(len(gram)),
            right.T,
        ).T
    except np.linalg.LinAlgError as error:
        raise ValueError("fixed-decoder ridge system is singular") from error
    return solved.astype(np.float32)


def reconstruction_mse(
    residual: np.ndarray, coefficients: np.ndarray, decoder: np.ndarray
) -> float:
    reconstructed = np.asarray(coefficients) @ np.asarray(decoder)
    return float(np.mean(np.square(np.asarray(residual) - reconstructed)))


def deterministic_group_folds(
    groups: Sequence[str], folds: int, seed: int
) -> np.ndarray:
    """Assign every group to exactly one deterministic balanced fold."""

    values = np.asarray([str(value) for value in groups], dtype=str)
    unique = np.unique(values)
    if folds < 2 or len(unique) < folds:
        raise ValueError("fold count must be between two and the number of groups")
    keyed = sorted(
        unique.tolist(),
        key=lambda value: hashlib.sha256(
            f"{seed}\0{value}".encode("utf-8")
        ).digest(),
    )
    mapping = {value: index % folds for index, value in enumerate(keyed)}
    return np.asarray([mapping[value] for value in values], dtype=np.int64)


def grouped_ridge_predictions(
    features: np.ndarray,
    targets: np.ndarray,
    groups: Sequence[str],
    *,
    folds: int,
    fold_seed: int,
    ridge_grid: Sequence[float],
) -> tuple[np.ndarray, list[dict]]:
    """Nested training-fold ridge selection with donor-held-out predictions."""

    x = np.asarray(features, dtype=np.float64)
    y = np.asarray(targets, dtype=np.float64)
    if x.ndim != 2 or y.ndim != 2 or len(x) != len(y):
        raise ValueError("features and targets must be aligned matrices")
    assignment = deterministic_group_folds(groups, folds, fold_seed)
    output = np.empty_like(y)
    records: list[dict] = []
    for fold in range(folds):
        test = assignment == fold
        train = ~test
        train_groups = np.asarray(groups, dtype=str)[train]
        inner_folds = min(folds - 1, len(np.unique(train_groups)))
        inner = deterministic_group_folds(
            train_groups, inner_folds, fold_seed + 1009 + fold
        )
        errors_by_ridge = {float(ridge): [] for ridge in ridge_grid}
        for inner_fold in range(inner_folds):
            inner_test = inner == inner_fold
            inner_train = ~inner_test
            grid_predictions = _ridge_grid_predictions(
                x[train][inner_train],
                y[train][inner_train],
                x[train][inner_test],
                ridge_grid,
            )
            for ridge, prediction in grid_predictions.items():
                errors_by_ridge[ridge].append(
                    float(np.mean(np.square(y[train][inner_test] - prediction)))
                )
        scores = [
            (float(np.mean(errors)), ridge)
            for ridge, errors in errors_by_ridge.items()
        ]
        _, selected = min(scores, key=lambda item: (item[0], item[1]))
        weights = _ridge_weights(x[train], y[train], selected)
        output[test] = _apply_ridge_weights(x[test], weights)
        records.append(
            {
                "fold": fold,
                "selected_ridge": selected,
                "train_rows": int(train.sum()),
                "test_rows": int(test.sum()),
            }
        )
    return output.astype(np.float32), records


def _ridge_weights(x: np.ndarray, y: np.ndarray, ridge: float) -> np.ndarray:
    x_mean = x.mean(axis=0, keepdims=True)
    y_mean = y.mean(axis=0, keepdims=True)
    xc = x - x_mean
    yc = y - y_mean
    gram = xc.T @ xc + ridge * np.eye(x.shape[1])
    weights = np.linalg.solve(gram, xc.T @ yc)
    intercept = y_mean - x_mean @ weights
    return np.vstack([intercept, weights])


def _apply_ridge_weights(x: np.ndarray, weights: np.ndarray) -> np.ndarray:
    return weights[:1] + x @ weights[1:]


def _ridge_grid_predictions(
    train_x: np.ndarray,
    train_y: np.ndarray,
    test_x: np.ndarray,
    ridge_grid: Sequence[float],
) -> dict[float, np.ndarray]:
    """Fit an entire ridge grid from one eigendecomposition."""

    x_mean = train_x.mean(axis=0, keepdims=True)
    y_mean = train_y.mean(axis=0, keepdims=True)
    xc = train_x - x_mean
    yc = train_y - y_mean
    gram = xc.T @ xc
    eigenvalue, eigenvector = np.linalg.eigh(gram)
    projected = eigenvector.T @ (xc.T @ yc)
    centered_test = test_x - x_mean
    return {
        float(ridge): y_mean
        + centered_test
        @ (
            eigenvector
            @ (projected / (eigenvalue[:, None] + float(ridge)))
        )
        for ridge in ridge_grid
    }
