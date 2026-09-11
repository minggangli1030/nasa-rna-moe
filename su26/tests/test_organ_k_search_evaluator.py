from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))

from evaluate_organ_k_search import (  # noqa: E402
    GROUP_RANDOM_AXES,
    apply_k_fallback,
    holm_adjust,
    select_k_one_se,
    track_b_decision,
)


def test_k_fallback_uses_selected_specialists_and_pooled_everywhere_else():
    pooled = np.arange(18, dtype=np.float64).reshape(6, 3)
    experts = np.stack(
        [pooled + 100.0 * (expert + 1) for expert in range(5)], axis=1
    )
    assignments = np.asarray([0, 1, 2, 3, 4, -1], dtype=np.int64)
    actual = apply_k_fallback(
        pooled,
        experts,
        assignments,
        selected_experts=[0, 2],
    )
    expected = pooled.copy()
    expected[0] = experts[0, 0]
    expected[2] = experts[2, 2]
    np.testing.assert_array_equal(actual, expected)
    # Inputs must remain immutable because the same cached predictions are
    # reused for every nested K candidate.
    np.testing.assert_array_equal(pooled, np.arange(18).reshape(6, 3))


def test_k_fallback_k5_uses_every_assigned_expert_and_validates_shapes():
    pooled = np.zeros((5, 2), dtype=np.float64)
    experts = np.empty((5, 5, 2), dtype=np.float64)
    for sample in range(5):
        for expert in range(5):
            experts[sample, expert] = [sample, expert]
    assignments = np.arange(5, dtype=np.int64)
    actual = apply_k_fallback(
        pooled, experts, assignments, selected_experts=list(range(5))
    )
    np.testing.assert_array_equal(
        actual, experts[np.arange(5), assignments]
    )
    with pytest.raises(ValueError, match="shape|align"):
        apply_k_fallback(pooled, experts[:-1], assignments, [0])
    with pytest.raises(ValueError, match="assignment|range"):
        apply_k_fallback(pooled, experts, np.asarray([0, 1, 2, 3, 7]), [0])
    with pytest.raises(ValueError, match="selected|duplicate"):
        apply_k_fallback(pooled, experts, assignments, [0, 0])


def test_holm_adjust_is_familywise_monotone_and_order_preserving():
    adjusted = holm_adjust(np.asarray([0.01, 0.03, 0.04], dtype=np.float64))
    np.testing.assert_allclose(adjusted, [0.03, 0.06, 0.06])
    reordered = holm_adjust(np.asarray([0.04, 0.01, 0.03], dtype=np.float64))
    np.testing.assert_allclose(reordered, [0.06, 0.03, 0.06])
    assert np.all(adjusted >= np.asarray([0.01, 0.03, 0.04]))
    assert np.all(adjusted <= 1.0)


@pytest.mark.parametrize("values", [[-0.1, 0.2], [0.2, 1.1], [0.1, np.nan], []])
def test_holm_adjust_rejects_invalid_families(values):
    with pytest.raises(ValueError, match=r"p-value|nonempty|finite|\[0, 1\]"):
        holm_adjust(np.asarray(values, dtype=np.float64))


def _selection_rows() -> list[dict]:
    return [
        {
            "k": 1,
            "mean_mse": 0.960,
            "standard_error": 0.010,
            "passes_pooled_holm": False,
            "passes_random_holm": False,
        },
        {
            "k": 2,
            "mean_mse": 0.920,
            "standard_error": 0.012,
            "passes_pooled_holm": True,
            "passes_random_holm": True,
        },
        {
            "k": 3,
            "mean_mse": 0.905,
            "standard_error": 0.015,
            "passes_pooled_holm": True,
            "passes_random_holm": True,
        },
        {
            "k": 4,
            "mean_mse": 0.900,
            "standard_error": 0.025,
            "passes_pooled_holm": True,
            "passes_random_holm": True,
        },
        {
            "k": 5,
            "mean_mse": 0.901,
            "standard_error": 0.020,
            "passes_pooled_holm": True,
            "passes_random_holm": True,
        },
    ]


def test_one_se_selects_smallest_eligible_k_within_best_standard_error():
    result = select_k_one_se(_selection_rows())
    assert result["best_k"] == 4
    assert result["best_mean_mse"] == pytest.approx(0.900)
    assert result["one_se_threshold"] == pytest.approx(0.925)
    assert result["eligible_k"] == [2, 3, 4, 5]
    assert result["within_one_se_k"] == [2, 3, 4, 5]
    assert result["selected_k"] == 2


def test_one_se_returns_no_nomination_without_both_corrected_controls():
    rows = _selection_rows()
    for row in rows:
        row["passes_random_holm"] = False
    result = select_k_one_se(rows)
    assert result["eligible_k"] == []
    assert result["within_one_se_k"] == []
    assert result["selected_k"] is None
    assert result["best_k"] is None


def _decision_rows() -> list[dict]:
    means = [0.960, 0.920, 0.905, 0.900, 0.901]
    standard_errors = [0.010, 0.012, 0.015, 0.025, 0.020]
    pooled_p = [0.20, 0.005, 0.006, 0.007, 0.008]
    random_p = [0.30, 0.0004, 0.0005, 0.0006, 0.0007]
    return [
        {
            "k": k,
            "split": "calibration",
            "mean_mse": means[k - 1],
            "standard_error": standard_errors[k - 1],
            "gain_vs_pooled": -0.01 if k == 1 else 0.04,
            "gain_vs_random": -0.01 if k == 1 else 0.02,
            "p_vs_pooled": pooled_p[k - 1],
            "p_vs_random": random_p[k - 1],
            "random_partition_tests": {
                axis: {
                    "relative_gain": -0.01 if k == 1 else 0.02,
                    "p_value": min(
                        1.0, random_p[k - 1] + partition_index * 0.00001
                    ),
                }
                for partition_index, axis in enumerate(GROUP_RANDOM_AXES)
            },
        }
        for k in range(1, 6)
    ]


def test_track_b_holm_families_and_one_se_nomination_are_development_only():
    rows = _decision_rows()
    expected_random_adjusted = holm_adjust(np.asarray([
        row["random_partition_tests"][axis]["p_value"]
        for row in rows
        for axis in sorted(GROUP_RANDOM_AXES)
    ]))
    result = track_b_decision(rows)
    assert result["decision_branch"] == "development_nomination"
    assert result["selected_k"] == 2
    assert result["test_accessed"] is False
    assert result["automatic_test_authorization"] is False
    assert result["requires_new_frozen_retraining"] is True
    assert result["requires_new_untouched_confirmation"] is True
    by_k = {row["k"]: row for row in result["candidates"]}
    assert by_k[1]["passes_pooled_holm"] is False
    assert by_k[1]["passes_random_holm"] is False
    observed_random_adjusted: list[float] = []
    for k in range(2, 6):
        assert by_k[k]["adjusted_p_vs_pooled"] <= 0.05
        assert by_k[k]["adjusted_p_vs_random"] <= 0.05
        assert by_k[k]["passes_pooled_holm"] is True
        assert by_k[k]["passes_random_holm"] is True
    for k in range(1, 6):
        assert set(by_k[k]["random_partition_tests"]) == set(GROUP_RANDOM_AXES)
        for axis in sorted(GROUP_RANDOM_AXES):
            test = by_k[k]["random_partition_tests"][axis]
            observed_random_adjusted.append(test["adjusted_p_value"])
            assert test["passes_holm"] is (k != 1)
    assert len(observed_random_adjusted) == 15
    np.testing.assert_allclose(observed_random_adjusted, expected_random_adjusted)
    assert result["selection"]["best_k"] == 4
    assert result["selection"]["selected_k"] == 2


def test_track_b_fails_closed_on_test_rows_or_incomplete_k_family():
    rows = _decision_rows()
    rows[0]["split"] = "test"
    with pytest.raises(ValueError, match="test|calibration"):
        track_b_decision(rows)
    with pytest.raises(ValueError, match="K|k|1.*5|candidate"):
        track_b_decision(_decision_rows()[:-1])

    mismatched = _decision_rows()
    del mismatched[0]["random_partition_tests"][GROUP_RANDOM_AXES[-1]]
    with pytest.raises(ValueError, match="random partition families differ"):
        track_b_decision(mismatched)


def test_track_b_rejects_legacy_single_random_control_contract():
    rows = _decision_rows()
    for row in rows:
        del row["random_partition_tests"]
    with pytest.raises(ValueError, match="three|partition|random"):
        track_b_decision(rows)


def test_track_b_no_eligible_k_is_terminal_for_this_development_search():
    rows = _decision_rows()
    for row in rows:
        for test in row["random_partition_tests"].values():
            test["p_value"] = 0.5
    result = track_b_decision(rows)
    assert result["decision_branch"] == "no_eligible_k"
    assert result["selected_k"] is None
    assert result["test_accessed"] is False
    assert result["automatic_test_authorization"] is False
