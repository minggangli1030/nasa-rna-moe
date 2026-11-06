"""Explicit, self-describing metrics for Stage 2B representation diagnostics."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

import numpy as np


Convention = Literal["raw", "standardized", "whitened"]
AggregationUnit = Literal["sample", "donor", "within_organ"]


def ridge_effective_dof(decoder: np.ndarray, ridge_lambda: float) -> float:
    """Effective degrees of freedom of one fixed-decoder ridge solve."""

    values = np.asarray(decoder, dtype=np.float64)
    if values.ndim != 2 or not min(values.shape):
        raise ValueError("decoder must be a nonempty matrix")
    if not np.isfinite(values).all() or ridge_lambda < 0:
        raise ValueError("decoder and ridge lambda must be finite and nonnegative")
    singular = np.linalg.svd(values, compute_uv=False)
    squared = np.square(singular)
    return float(np.sum(squared / (squared + float(ridge_lambda))))


@dataclass(frozen=True)
class RankRecord:
    entropy_rank: float
    participation_ratio: float
    eigenvalues: list[float]
    cumulative_variance: list[float]
    convention: Convention
    aggregation_unit: AggregationUnit
    n_rows: int
    n_dims: int
    ridge_lambda: float
    effective_dof: float
    oracle_ceiling: float | None
    fraction_of_ceiling: float | None

    def to_dict(self) -> dict:
        return asdict(self)


def rank_record(
    values: np.ndarray,
    *,
    convention: Convention,
    aggregation_unit: AggregationUnit,
    ridge_lambda: float,
    effective_dof: float,
    oracle_ceiling: float | None = None,
) -> RankRecord:
    """Compute both common effective-rank definitions and retain their context."""

    matrix = np.asarray(values, dtype=np.float64)
    if matrix.ndim != 2 or not min(matrix.shape):
        raise ValueError("rank input must be a nonempty two-dimensional matrix")
    if not np.isfinite(matrix).all():
        raise ValueError("rank input contains nonfinite values")
    n_rows, n_dims = matrix.shape
    if n_rows <= n_dims:
        raise ValueError(
            f"rank input requires n_rows > n_dims, observed {n_rows} <= {n_dims}"
        )
    if convention not in ("raw", "standardized", "whitened"):
        raise ValueError(f"unknown rank convention {convention!r}")
    if aggregation_unit not in ("sample", "donor", "within_organ"):
        raise ValueError(f"unknown aggregation unit {aggregation_unit!r}")
    if ridge_lambda < 0 or effective_dof < 0:
        raise ValueError("ridge lambda and effective degrees of freedom must be nonnegative")
    if oracle_ceiling is not None and oracle_ceiling <= 0:
        raise ValueError("oracle ceiling must be positive when provided")

    centered = matrix - matrix.mean(axis=0, keepdims=True)
    singular = np.linalg.svd(centered, compute_uv=False)
    eigenvalues = np.square(singular) / float(n_rows - 1)
    if len(eigenvalues) < n_dims:
        eigenvalues = np.pad(eigenvalues, (0, n_dims - len(eigenvalues)))
    total = float(eigenvalues.sum())
    if total <= 0:
        probability = np.zeros_like(eigenvalues)
        entropy_rank = 0.0
        participation = 0.0
        cumulative = np.zeros_like(eigenvalues)
    else:
        probability = eigenvalues / total
        active = probability[probability > 0]
        entropy_rank = float(np.exp(-np.sum(active * np.log(active))))
        participation = float(1.0 / np.square(probability).sum())
        cumulative = np.cumsum(probability)
    fraction = (
        None if oracle_ceiling is None else entropy_rank / float(oracle_ceiling)
    )
    return RankRecord(
        entropy_rank=entropy_rank,
        participation_ratio=participation,
        eigenvalues=eigenvalues.astype(float).tolist(),
        cumulative_variance=cumulative.astype(float).tolist(),
        convention=convention,
        aggregation_unit=aggregation_unit,
        n_rows=n_rows,
        n_dims=n_dims,
        ridge_lambda=float(ridge_lambda),
        effective_dof=float(effective_dof),
        oracle_ceiling=None if oracle_ceiling is None else float(oracle_ceiling),
        fraction_of_ceiling=None if fraction is None else float(fraction),
    )
