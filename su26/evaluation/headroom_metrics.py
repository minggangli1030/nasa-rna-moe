"""Pure metric helpers for interspecies expert headroom evaluation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


EPS = 1e-12


def masked_values(values: np.ndarray, mask_idx: np.ndarray) -> np.ndarray:
    """Gather a fixed number of masked positions from every sample."""
    values = np.asarray(values)
    mask_idx = np.asarray(mask_idx, dtype=np.int64)
    if values.ndim != 2 or mask_idx.ndim != 2:
        raise ValueError("values and mask_idx must both be rank-2 arrays")
    if values.shape[0] != mask_idx.shape[0]:
        raise ValueError("values and mask_idx must have the same sample count")
    if mask_idx.size and (mask_idx.min() < 0 or mask_idx.max() >= values.shape[1]):
        raise ValueError("mask_idx contains an out-of-range gene position")
    return values[np.arange(values.shape[0])[:, None], mask_idx]


def pearson_rows(pred: np.ndarray, true: np.ndarray) -> np.ndarray:
    """Vectorized Pearson correlation for corresponding rows."""
    pred = np.asarray(pred, dtype=np.float64)
    true = np.asarray(true, dtype=np.float64)
    if pred.shape != true.shape or pred.ndim != 2:
        raise ValueError("pred and true must be same-shaped rank-2 arrays")
    pred_centered = pred - pred.mean(axis=1, keepdims=True)
    true_centered = true - true.mean(axis=1, keepdims=True)
    numerator = np.sum(pred_centered * true_centered, axis=1)
    denominator = np.sqrt(
        np.sum(pred_centered * pred_centered, axis=1)
        * np.sum(true_centered * true_centered, axis=1)
    )
    out = np.full(pred.shape[0], np.nan, dtype=np.float64)
    true_ss = np.sum(true_centered * true_centered, axis=1)
    pred_ss = np.sum(pred_centered * pred_centered, axis=1)
    true_valid = true_ss > EPS
    pred_valid = pred_ss > EPS
    valid = true_valid & pred_valid
    out[valid] = numerator[valid] / denominator[valid]
    # A constant prediction contains no rank information. Score it as zero
    # when the target varies instead of silently dropping that sample.
    out[true_valid & ~pred_valid] = 0.0
    return out


def mse_rows(pred: np.ndarray, true: np.ndarray) -> np.ndarray:
    pred = np.asarray(pred, dtype=np.float64)
    true = np.asarray(true, dtype=np.float64)
    if pred.shape != true.shape or pred.ndim != 2:
        raise ValueError("pred and true must be same-shaped rank-2 arrays")
    return np.mean((pred - true) ** 2, axis=1)


def simplex_least_squares(pred: np.ndarray, true: np.ndarray) -> np.ndarray:
    """Exact least-squares weights on the 3-expert probability simplex.

    The optimum of a convex quadratic over a triangle is either in its
    interior, on one of its edges, or at a vertex. Enumerating those cases is
    deterministic and avoids depending on a numerical optimizer.
    """
    pred = np.asarray(pred, dtype=np.float64)
    true = np.asarray(true, dtype=np.float64)
    if pred.ndim != 2 or pred.shape[1] != 3:
        raise ValueError("pred must have shape (observations, 3)")
    if true.shape != (pred.shape[0],):
        raise ValueError("true must have shape (observations,)")
    if not np.isfinite(pred).all() or not np.isfinite(true).all():
        raise ValueError("simplex least squares requires finite inputs")

    candidates: list[np.ndarray] = []
    for expert_idx in range(3):
        w = np.zeros(3, dtype=np.float64)
        w[expert_idx] = 1.0
        candidates.append(w)

    for i, j in ((0, 1), (0, 2), (1, 2)):
        direction = pred[:, i] - pred[:, j]
        denom = float(direction @ direction)
        if denom <= EPS:
            alpha = 0.5
        else:
            alpha = float(direction @ (true - pred[:, j]) / denom)
        alpha = float(np.clip(alpha, 0.0, 1.0))
        w = np.zeros(3, dtype=np.float64)
        w[i] = alpha
        w[j] = 1.0 - alpha
        candidates.append(w)

    gram = pred.T @ pred
    rhs = pred.T @ true
    kkt = np.block(
        [[gram, np.ones((3, 1), dtype=np.float64)],
         [np.ones((1, 3), dtype=np.float64), np.zeros((1, 1), dtype=np.float64)]]
    )
    solution = np.linalg.lstsq(kkt, np.concatenate([rhs, [1.0]]), rcond=None)[0][:3]
    if np.all(solution >= -1e-10):
        solution = np.maximum(solution, 0.0)
        solution /= solution.sum()
        candidates.append(solution)

    losses = [float(np.mean((pred @ w - true) ** 2)) for w in candidates]
    return candidates[int(np.argmin(losses))]


def soft_oracle_mse_weights(pred_masked: np.ndarray, true_masked: np.ndarray) -> np.ndarray:
    """Return per-sample optimal convex weights under masked-position MSE.

    pred_masked has shape (experts=3, samples, masked_genes).
    """
    pred_masked = np.asarray(pred_masked, dtype=np.float64)
    true_masked = np.asarray(true_masked, dtype=np.float64)
    if pred_masked.ndim != 3 or pred_masked.shape[0] != 3:
        raise ValueError("pred_masked must have shape (3, samples, masked_genes)")
    if true_masked.shape != pred_masked.shape[1:]:
        raise ValueError("true_masked shape must match pred_masked sample/gene axes")
    return np.stack(
        [simplex_least_squares(pred_masked[:, i, :].T, true_masked[i])
         for i in range(true_masked.shape[0])],
        axis=0,
    )


def apply_sample_weights(pred_masked: np.ndarray, weights: np.ndarray) -> np.ndarray:
    pred_masked = np.asarray(pred_masked, dtype=np.float64)
    weights = np.asarray(weights, dtype=np.float64)
    if pred_masked.ndim != 3 or weights.shape != (pred_masked.shape[1], pred_masked.shape[0]):
        raise ValueError("weights must have shape (samples, experts)")
    return np.einsum("ne,enk->nk", weights, pred_masked)


def make_crossfit_folds(
    n_samples: int,
    n_folds: int,
    seed: int,
    strata: np.ndarray | None = None,
    groups: np.ndarray | None = None,
) -> np.ndarray:
    """Assign deterministic folds, keeping groups intact when supplied."""
    if n_folds < 2 or n_folds > n_samples:
        raise ValueError("n_folds must be between 2 and n_samples")
    rng = np.random.default_rng(seed)
    fold = np.full(n_samples, -1, dtype=np.int64)

    if groups is not None:
        groups = np.asarray(groups).astype(str)
        if groups.shape != (n_samples,):
            raise ValueError("groups must have one value per sample")
        if strata is None:
            strata = np.full(n_samples, "__all__", dtype=object)
        else:
            strata = np.asarray(strata).astype(str)
        # A group should not straddle strata. If it does, treat its stratum as
        # mixed and still keep the group intact.
        group_to_rows: dict[str, np.ndarray] = {
            g: np.flatnonzero(groups == g) for g in np.unique(groups)
        }
        buckets: dict[str, list[str]] = {}
        for group, rows in group_to_rows.items():
            labels = np.unique(strata[rows])
            label = labels[0] if len(labels) == 1 else "__mixed__"
            buckets.setdefault(label, []).append(group)
        for group_names in buckets.values():
            rng.shuffle(group_names)
            # Greedy assignment by current sample count keeps uneven studies
            # from producing severely imbalanced folds.
            counts = np.zeros(n_folds, dtype=np.int64)
            for group in sorted(group_names, key=lambda g: -len(group_to_rows[g])):
                choices = np.flatnonzero(counts == counts.min())
                target = int(rng.choice(choices))
                rows = group_to_rows[group]
                fold[rows] = target
                counts[target] += len(rows)
    else:
        if strata is None:
            strata = np.full(n_samples, "__all__", dtype=object)
        else:
            strata = np.asarray(strata).astype(str)
            if strata.shape != (n_samples,):
                raise ValueError("strata must have one value per sample")
        for label in np.unique(strata):
            rows = np.flatnonzero(strata == label)
            rng.shuffle(rows)
            fold[rows] = np.arange(len(rows)) % n_folds

    if np.any(fold < 0) or len(np.unique(fold)) != n_folds:
        raise RuntimeError("failed to construct all requested cross-fit folds")
    return fold


@dataclass
class CrossfitBlend:
    pred_masked: np.ndarray
    fold_weights: list[list[float]]
    fold_ids: np.ndarray


@dataclass
class CrossfitBestExpert:
    pred_masked: np.ndarray
    expert_by_fold: list[int]


def crossfit_best_expert(
    pred_masked: np.ndarray,
    true_masked: np.ndarray,
    fold_ids: np.ndarray,
    objective: str,
) -> CrossfitBestExpert:
    """Select one expert on calibration folds and apply it to the held-out fold."""
    pred_masked = np.asarray(pred_masked, dtype=np.float64)
    true_masked = np.asarray(true_masked, dtype=np.float64)
    fold_ids = np.asarray(fold_ids, dtype=np.int64)
    if pred_masked.shape[0] != 3 or pred_masked.shape[1:] != true_masked.shape:
        raise ValueError("incompatible prediction/target shapes")
    if fold_ids.shape != (true_masked.shape[0],):
        raise ValueError("fold_ids must have one value per sample")
    if objective not in {"mse", "pearson"}:
        raise ValueError("objective must be 'mse' or 'pearson'")

    out = np.empty_like(true_masked, dtype=np.float64)
    choices = []
    for fold in sorted(np.unique(fold_ids)):
        train = fold_ids != fold
        test = fold_ids == fold
        if objective == "mse":
            scores = np.mean(
                (pred_masked[:, train, :] - true_masked[None, train, :]) ** 2,
                axis=(1, 2),
            )
            best = int(np.argmin(scores))
        else:
            scores = np.array([
                pearson_rows(pred_masked[i, train], true_masked[train]).mean()
                for i in range(3)
            ])
            best = int(np.argmax(scores))
        out[test] = pred_masked[best, test]
        choices.append(best)
    return CrossfitBestExpert(pred_masked=out, expert_by_fold=choices)


def crossfit_fixed_mse_blend(
    pred_masked: np.ndarray,
    true_masked: np.ndarray,
    fold_ids: np.ndarray,
) -> CrossfitBlend:
    """Fit one global simplex blend on other folds and predict each held-out fold."""
    pred_masked = np.asarray(pred_masked, dtype=np.float64)
    true_masked = np.asarray(true_masked, dtype=np.float64)
    fold_ids = np.asarray(fold_ids, dtype=np.int64)
    if pred_masked.shape[0] != 3 or pred_masked.shape[1:] != true_masked.shape:
        raise ValueError("incompatible prediction/target shapes")
    if fold_ids.shape != (true_masked.shape[0],):
        raise ValueError("fold_ids must have one value per sample")

    out = np.empty_like(true_masked, dtype=np.float64)
    fold_weights: list[list[float]] = []
    for fold in sorted(np.unique(fold_ids)):
        train = fold_ids != fold
        test = fold_ids == fold
        design = pred_masked[:, train, :].transpose(1, 2, 0).reshape(-1, 3)
        target = true_masked[train].reshape(-1)
        weights = simplex_least_squares(design, target)
        out[test] = np.einsum("e,enk->nk", weights, pred_masked[:, test, :])
        fold_weights.append(weights.tolist())
    return CrossfitBlend(pred_masked=out, fold_weights=fold_weights, fold_ids=fold_ids)


@dataclass
class CrossfitSpeciesRouter:
    hard_pred_masked: np.ndarray
    soft_pred_masked: np.ndarray
    hard_experts: list[dict[str, int]]
    soft_weights: list[dict[str, list[float]]]


def crossfit_species_mse_router(
    pred_masked: np.ndarray,
    true_masked: np.ndarray,
    fold_ids: np.ndarray,
    species: np.ndarray,
) -> CrossfitSpeciesRouter:
    """Fit species-conditioned hard and soft MSE routers out of fold."""
    pred_masked = np.asarray(pred_masked, dtype=np.float64)
    true_masked = np.asarray(true_masked, dtype=np.float64)
    fold_ids = np.asarray(fold_ids, dtype=np.int64)
    species = np.asarray(species).astype(str)
    if pred_masked.shape[0] != 3 or pred_masked.shape[1:] != true_masked.shape:
        raise ValueError("incompatible prediction/target shapes")
    if fold_ids.shape != (true_masked.shape[0],) or species.shape != fold_ids.shape:
        raise ValueError("fold_ids and species must have one value per sample")

    hard_out = np.empty_like(true_masked, dtype=np.float64)
    soft_out = np.empty_like(true_masked, dtype=np.float64)
    hard_experts: list[dict[str, int]] = []
    soft_weights: list[dict[str, list[float]]] = []
    for fold in sorted(np.unique(fold_ids)):
        fold_hard: dict[str, int] = {}
        fold_soft: dict[str, list[float]] = {}
        for label in sorted(np.unique(species)):
            train = (fold_ids != fold) & (species == label)
            test = (fold_ids == fold) & (species == label)
            if not np.any(test):
                continue
            if not np.any(train):
                raise ValueError(f"no calibration samples for species {label!r} in fold {fold}")

            per_expert_mse = np.mean(
                (pred_masked[:, train, :] - true_masked[None, train, :]) ** 2,
                axis=(1, 2),
            )
            best = int(np.argmin(per_expert_mse))
            hard_out[test] = pred_masked[best, test, :]
            fold_hard[label] = best

            design = pred_masked[:, train, :].transpose(1, 2, 0).reshape(-1, 3)
            target = true_masked[train].reshape(-1)
            weights = simplex_least_squares(design, target)
            soft_out[test] = np.einsum("e,enk->nk", weights, pred_masked[:, test, :])
            fold_soft[label] = weights.tolist()
        hard_experts.append(fold_hard)
        soft_weights.append(fold_soft)

    return CrossfitSpeciesRouter(
        hard_pred_masked=hard_out,
        soft_pred_masked=soft_out,
        hard_experts=hard_experts,
        soft_weights=soft_weights,
    )


def paired_bootstrap_ci(
    differences: np.ndarray,
    seed: int,
    n_bootstrap: int = 2000,
    groups: np.ndarray | None = None,
    strata: np.ndarray | None = None,
) -> tuple[float, float]:
    """Paired percentile CI for a mean difference, clustered if requested."""
    differences = np.asarray(differences, dtype=np.float64)
    valid = np.isfinite(differences)
    differences = differences[valid]
    if differences.size == 0:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    if strata is None:
        strata = np.full(len(valid), "__all__", dtype=object)
    else:
        strata = np.asarray(strata).astype(str)
        if strata.shape != valid.shape:
            raise ValueError("strata must have one value per original difference")
    strata = strata[valid]

    estimates = np.empty(n_bootstrap, dtype=np.float64)
    if groups is None and len(np.unique(strata)) == 1:
        for i in range(n_bootstrap):
            draw = rng.integers(0, len(differences), size=len(differences))
            estimates[i] = differences[draw].mean()
    else:
        if groups is None:
            groups = np.arange(len(valid)).astype(str)
        else:
            groups = np.asarray(groups).astype(str)
            if groups.shape != valid.shape:
                raise ValueError("groups must have one value per original difference")
        groups = groups[valid]
        buckets: dict[str, dict[str, float]] = {}
        for label in np.unique(strata):
            in_stratum = strata == label
            labels = np.unique(groups[in_stratum])
            buckets[label] = {
                group: float(differences[in_stratum & (groups == group)].mean())
                for group in labels
            }
        for i in range(n_bootstrap):
            stratum_means = []
            for grouped in buckets.values():
                labels = np.array(list(grouped), dtype=object)
                draw = rng.choice(labels, size=len(labels), replace=True)
                stratum_means.append(float(np.mean([grouped[group] for group in draw])))
            estimates[i] = float(np.mean(stratum_means))
    low, high = np.quantile(estimates, [0.025, 0.975])
    return float(low), float(high)


def balanced_group_mean(
    values: np.ndarray,
    groups: np.ndarray | None = None,
    strata: np.ndarray | None = None,
) -> float:
    """Mean each study equally within stratum, then mean strata equally."""
    values = np.asarray(values, dtype=np.float64)
    valid = np.isfinite(values)
    if not valid.any():
        return float("nan")
    values = values[valid]
    if strata is None:
        strata = np.full(len(valid), "__all__", dtype=object)
    else:
        strata = np.asarray(strata).astype(str)
        if strata.shape != valid.shape:
            raise ValueError("strata must have one value per original value")
    strata = strata[valid]
    if groups is None:
        groups = np.arange(len(valid)).astype(str)
    else:
        groups = np.asarray(groups).astype(str)
        if groups.shape != valid.shape:
            raise ValueError("groups must have one value per original value")
    groups = groups[valid]

    stratum_means = []
    for label in np.unique(strata):
        in_stratum = strata == label
        group_means = [
            values[in_stratum & (groups == group)].mean()
            for group in np.unique(groups[in_stratum])
        ]
        stratum_means.append(float(np.mean(group_means)))
    return float(np.mean(stratum_means))
