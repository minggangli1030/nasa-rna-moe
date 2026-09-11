from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evaluation"))

from headroom_metrics import (  # noqa: E402
    apply_sample_weights,
    crossfit_best_expert,
    crossfit_fixed_mse_blend,
    crossfit_species_mse_router,
    make_crossfit_folds,
    mse_rows,
    pearson_rows,
    simplex_least_squares,
    soft_oracle_mse_weights,
)


def test_soft_oracle_exceeds_every_hard_expert():
    first = np.array([0.0, 0.0, 1.0, 1.0])
    second = np.array([0.0, 1.0, 0.0, 1.0])
    third = np.zeros(4)
    true = np.array([0.0, 0.5, 0.5, 1.0])
    design = np.stack([first, second, third], axis=1)

    weights = simplex_least_squares(design, true)
    blended = design @ weights

    np.testing.assert_allclose(weights, [0.5, 0.5, 0.0], atol=1e-10)
    assert np.mean((blended - true) ** 2) < 1e-12
    assert pearson_rows(blended[None, :], true[None, :])[0] == 1.0
    assert max(
        pearson_rows(first[None, :], true[None, :])[0],
        pearson_rows(second[None, :], true[None, :])[0],
    ) < 0.8


def test_per_sample_soft_oracle_never_worse_than_best_hard_mse():
    rng = np.random.default_rng(7)
    pred = rng.normal(size=(3, 12, 30))
    true = rng.normal(size=(12, 30))
    weights = soft_oracle_mse_weights(pred, true)
    blended = apply_sample_weights(pred, weights)
    oracle_mse = mse_rows(blended, true)
    hard_mse = np.stack([mse_rows(p, true) for p in pred]).min(axis=0)

    assert np.all(weights >= -1e-12)
    np.testing.assert_allclose(weights.sum(axis=1), 1.0)
    assert np.all(oracle_mse <= hard_mse + 1e-10)


def test_constant_prediction_scores_zero_not_missing():
    pred = np.ones((2, 5))
    true = np.array([[0, 1, 2, 3, 4], [4, 3, 2, 1, 0]], dtype=float)
    np.testing.assert_array_equal(pearson_rows(pred, true), [0.0, 0.0])


def test_grouped_folds_keep_studies_intact_and_stratified():
    groups = np.array(["h1"] * 3 + ["h2"] * 3 + ["h3"] * 3
                      + ["m1"] * 3 + ["m2"] * 3 + ["m3"] * 3)
    species = np.array(["human"] * 9 + ["mouse"] * 9)
    folds = make_crossfit_folds(
        len(groups), 3, seed=11, strata=species, groups=groups
    )

    for group in np.unique(groups):
        assert len(np.unique(folds[groups == group])) == 1
    for fold in range(3):
        assert set(species[folds == fold]) == {"human", "mouse"}


def test_crossfit_fixed_blend_does_not_fit_on_heldout_fold():
    # Fold 0 favors expert 0, while the calibration-only fold 1 favors expert 1.
    true = np.ones((4, 5))
    pred = np.zeros((3, 4, 5))
    pred[0, :2] = 1.0
    pred[1, 2:] = 1.0
    folds = np.array([0, 0, 1, 1])

    result = crossfit_fixed_mse_blend(pred, true, folds)

    np.testing.assert_allclose(result.fold_weights[0], [0.0, 1.0, 0.0])
    np.testing.assert_allclose(result.fold_weights[1], [1.0, 0.0, 0.0])
    # Each held-out fold is intentionally predicted by the opposite expert.
    np.testing.assert_allclose(result.pred_masked, 0.0)


def test_best_single_is_selected_on_other_folds():
    true = np.ones((4, 5))
    pred = np.zeros((3, 4, 5))
    pred[0, :2] = 1.0
    pred[1, 2:] = 1.0
    folds = np.array([0, 0, 1, 1])

    result = crossfit_best_expert(pred, true, folds, "mse")

    assert result.expert_by_fold == [1, 0]
    np.testing.assert_allclose(result.pred_masked, 0.0)


def test_species_router_is_fitted_out_of_fold():
    species = np.array(["human", "human", "mouse", "mouse"] * 2)
    folds = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    true = np.ones((8, 4))
    pred = np.zeros((3, 8, 4))
    pred[0, species == "human"] = 1.0
    pred[1, species == "mouse"] = 1.0

    result = crossfit_species_mse_router(pred, true, folds, species)

    np.testing.assert_allclose(result.hard_pred_masked, true)
    np.testing.assert_allclose(result.soft_pred_masked, true)
    assert all(mapping == {"human": 0, "mouse": 1} for mapping in result.hard_experts)


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            suite.addTest(unittest.FunctionTestCase(value))
    return suite
