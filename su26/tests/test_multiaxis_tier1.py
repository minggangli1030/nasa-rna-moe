import numpy as np

from core.multiaxis_tier1 import (
    donor_bootstrap_incremental_r2,
    incremental_grouped_ridge,
    partial_correlations,
    permute_within_organ,
    stable_one_hot,
)


def test_within_organ_permutation_never_crosses_organs():
    values = np.arange(12)[:, None]
    organs = np.repeat(["a", "b", "c"], 4)
    shuffled = permute_within_organ(values, organs, seed=17)
    for organ in np.unique(organs):
        rows = np.flatnonzero(organs == organ)
        assert sorted(shuffled[rows, 0]) == sorted(values[rows, 0])


def test_incremental_grouped_ridge_detects_candidate_signal():
    rng = np.random.default_rng(42)
    donors = np.repeat([f"d{i}" for i in range(30)], 2)
    base = rng.normal(size=(len(donors), 2))
    candidate = rng.normal(size=(len(donors), 1))
    target = 4 * candidate + 0.05 * rng.normal(size=(len(donors), 1))
    result = incremental_grouped_ridge(
        base,
        candidate,
        target,
        donors,
        folds=5,
        fold_seed=9,
        ridge_grid=[0.001, 0.1],
    )
    assert result["incremental_r2"] > 0.95
    boot = donor_bootstrap_incremental_r2(
        target,
        result["base_prediction"],
        result["candidate_prediction"],
        donors,
        replicates=100,
        seed=11,
    )
    assert boot["ci95"][0] > 0


def test_partial_correlation_removes_organ_mean():
    organs = np.repeat(["a", "b"], 20)
    encoded, _ = stable_one_hot(organs)
    candidate = encoded[:, :1] * 10
    proxy = encoded[:, 1:] * 5
    correlations = partial_correlations(candidate, proxy, encoded)
    assert abs(correlations[0][0]) < 1e-8
