from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))

from evaluate_organ_k_confirmation import (  # noqa: E402
    GROUP_RANDOM_AXES,
    _conservative_random_family,
    comparison,
    track_a_decision,
    validate_alignment,
)


EXPECTED_SEEDS = (17, 42, 101)
COMMON_HASHES = {
    name: hashlib.sha256(name.encode("utf-8")).hexdigest()
    for name in (
        "protocol_sha256",
        "manifest_sha256",
        "partition_manifest_sha256",
        "axis_definitions_sha256",
        "score_gene_indices_sha256",
        "router_artifact_sha256",
        "sealed_test_assignments_sha256",
    )
}


def _aligned_runs() -> list[dict]:
    sample_ids = np.asarray([f"sample-{index}" for index in range(10)])
    groups = np.asarray([f"study-{index // 2}" for index in range(10)])
    organs = np.asarray(
        ["adipose", "brain", "liver", "skeletal_muscle", "skin"] * 2
    )
    weights = np.full(len(sample_ids), 1.0 / len(sample_ids), dtype=np.float64)
    return [
        {
            "status": "complete",
            "seed": seed,
            "split": "test",
            "authorized_test_access": True,
            "mechanical_only": False,
            "sample_ids": sample_ids.copy(),
            "groups": groups.copy(),
            "organs": organs.copy(),
            "sample_weights": weights.copy(),
            "arrays": {
                "pooled_mse": np.full(len(sample_ids), 1.0),
                "true_organ_hard_mse": np.full(len(sample_ids), 0.94),
                "blind_organ_hard_mse": np.full(len(sample_ids), 0.95),
                **{
                    f"{axis}_assigned_hard_mse": np.full(len(sample_ids), 0.99)
                    for axis in GROUP_RANDOM_AXES
                },
            },
            "hashes": dict(COMMON_HASHES),
        }
        for seed in EXPECTED_SEEDS
    ]


def test_alignment_accepts_only_exact_seed_and_provenance_contract():
    result = validate_alignment(_aligned_runs())
    assert result["seeds"] == list(EXPECTED_SEEDS)
    assert result["sample_count"] == 10
    assert result["fingerprints"] == COMMON_HASHES
    assert result["authorized_test_access"] is True


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("order", "sample"),
        ("groups", "group"),
        ("fingerprint", "fingerprint|hash"),
        ("authorization", "authoriz"),
        ("mechanical", "mechanical"),
        ("missing_seed", "seed"),
        ("duplicate_seed", "seed"),
        ("array_length", "align|length"),
    ],
)
def test_alignment_fails_closed_on_any_material_drift(mutation, message):
    runs = _aligned_runs()
    if mutation == "order":
        runs[1]["sample_ids"] = runs[1]["sample_ids"][::-1]
    elif mutation == "groups":
        runs[2]["groups"][0] = "different-study"
    elif mutation == "fingerprint":
        runs[1]["hashes"]["router_artifact_sha256"] = "other-router"
    elif mutation == "authorization":
        runs[0]["authorized_test_access"] = False
    elif mutation == "mechanical":
        runs[0]["mechanical_only"] = True
    elif mutation == "missing_seed":
        runs.pop()
    elif mutation == "duplicate_seed":
        runs[2]["seed"] = 42
    else:
        runs[1]["arrays"]["blind_organ_hard_mse"] = np.ones(9)
    with pytest.raises(ValueError, match=message):
        validate_alignment(runs)


def _synthetic_metric_arrays(
    candidate_levels: tuple[float, float, float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    # Two samples in each organ and one connected study per sample make the
    # balanced estimand transparent while retaining the real 3 x N layout.
    organs = np.asarray(
        ["adipose", "brain", "liver", "skeletal_muscle", "skin"] * 2
    )
    groups = np.asarray([f"study-{index}" for index in range(len(organs))])
    seeds = np.asarray(EXPECTED_SEEDS, dtype=np.int64)
    control = np.ones((len(seeds), len(organs)), dtype=np.float64)
    candidate = np.stack(
        [np.full(len(organs), value) for value in candidate_levels]
    )
    return control, candidate, groups, organs, seeds


def test_comparison_accepts_2d_and_seed_mapping_arrays_with_same_result():
    control, candidate, groups, organs, seeds = _synthetic_metric_arrays(
        (0.95, 0.94, 0.96)
    )
    matrix_result = comparison(control, candidate, groups, organs, seeds)
    mapping_result = comparison(
        {int(seed): control[index] for index, seed in enumerate(seeds)},
        {int(seed): candidate[index] for index, seed in enumerate(seeds)},
        groups,
        organs,
        seeds,
    )
    assert matrix_result["relative_mse_reduction_per_seed"] == pytest.approx(
        [0.05, 0.06, 0.04]
    )
    assert matrix_result["relative_mse_reduction_mean"] == pytest.approx(0.05)
    assert matrix_result["same_positive_sign"] is True
    assert matrix_result["seed_sd_fraction_of_mean"] == pytest.approx(0.2)
    assert mapping_result == matrix_result


def test_comparison_rejects_seed_or_sample_axis_misalignment():
    control, candidate, groups, organs, seeds = _synthetic_metric_arrays(
        (0.95, 0.94, 0.96)
    )
    with pytest.raises(ValueError, match="seed|shape|align"):
        comparison(control[:2], candidate, groups, organs, seeds)
    with pytest.raises(ValueError, match="sample|shape|align"):
        comparison(control, candidate[:, :-1], groups, organs, seeds)
    with pytest.raises(ValueError, match="seed"):
        comparison(
            {17: control[0], 42: control[1]},
            {17: candidate[0], 42: candidate[1]},
            groups,
            organs,
            seeds,
        )


def _metric(gain: float, *, interval: bool = True) -> dict:
    return {
        "relative_mse_reduction_mean": float(gain),
        "relative_mse_reduction_per_seed": [float(gain)] * 3,
        "same_positive_sign": gain > 0,
        "seed_sd_fraction_of_mean": 0.0 if gain != 0 else float("inf"),
        "positive_clustered_interval": bool(interval),
        "positive_residual_pearson_interval": bool(interval),
    }


def _random_family(gain: float) -> dict:
    return _conservative_random_family({
        axis: _metric(gain + partition_index * 0.001)
        for partition_index, axis in enumerate(GROUP_RANDOM_AXES)
    })


def _passing_comparisons() -> dict[str, dict | float]:
    return {
        "blind_organ_hard_vs_pooled": _metric(0.04),
        "true_organ_hard_vs_pooled": _metric(0.05),
        "true_organ_hard_vs_assigned_random_k5": _random_family(0.04),
        "true_organ_hard_vs_calibration_selected_random": _random_family(0.01),
        "blind_recovery_of_true_gain": 0.80,
    }


@pytest.mark.parametrize(
    ("mutation", "oracle_gate", "technical_gates", "expected_branch"),
    [
        (None, True, {"provenance": True, "exposure": True}, "pass"),
        (
            "blind",
            True,
            {"provenance": True, "exposure": True},
            "true_pass_blind_fail",
        ),
        (
            "random",
            True,
            {"provenance": True, "exposure": True},
            "random_control_fail",
        ),
        (
            "pooled",
            True,
            {"provenance": True, "exposure": True},
            "pooled_fail",
        ),
        (
            None,
            True,
            {"provenance": True, "exposure": False},
            "technical_fail",
        ),
        (
            None,
            False,
            {"provenance": True, "exposure": True},
            "pooled_fail",
        ),
    ],
)
def test_track_a_decision_has_explicit_precedence_and_all_frozen_gates(
    mutation, oracle_gate, technical_gates, expected_branch
):
    comparisons = _passing_comparisons()
    if mutation == "blind":
        comparisons["blind_organ_hard_vs_pooled"] = _metric(0.02)
    elif mutation == "random":
        partitions = comparisons[
            "true_organ_hard_vs_assigned_random_k5"
        ]["partition_comparisons"]
        partitions[GROUP_RANDOM_AXES[-1]] = _metric(0.02)
        comparisons["true_organ_hard_vs_assigned_random_k5"] = (
            _conservative_random_family(partitions)
        )
    elif mutation == "pooled":
        comparisons["true_organ_hard_vs_pooled"] = _metric(0.02)
    result = track_a_decision(
        comparisons,
        oracle_gate=oracle_gate,
        technical_gates=technical_gates,
    )
    assert result["decision_branch"] == expected_branch
    assert result["test_accessed"] is True
    assert result["automatic_external_test_authorization"] is False
    assert result["all_gates_pass"] is (expected_branch == "pass")


def test_track_a_interval_recovery_and_seed_stability_are_gating():
    for name, value in (
        ("positive_clustered_interval", False),
        ("positive_residual_pearson_interval", False),
        ("same_positive_sign", False),
        ("seed_sd_fraction_of_mean", 0.51),
    ):
        comparisons = _passing_comparisons()
        comparisons["blind_organ_hard_vs_pooled"][name] = value
        result = track_a_decision(
            comparisons,
            oracle_gate=True,
            technical_gates={"provenance": True, "exposure": True},
        )
        assert result["decision_branch"] == "true_pass_blind_fail"
        assert result["gates"]["blind_router"] is False

    comparisons = _passing_comparisons()
    comparisons["blind_recovery_of_true_gain"] = 0.799
    result = track_a_decision(
        comparisons,
        oracle_gate=True,
        technical_gates={"provenance": True, "exposure": True},
    )
    assert result["decision_branch"] == "true_pass_blind_fail"
    assert result["gates"]["blind_recovery"] is False


def test_track_a_random_selected_interval_is_a_random_control_gate():
    comparisons = _passing_comparisons()
    partitions = comparisons[
        "true_organ_hard_vs_calibration_selected_random"
    ]["partition_comparisons"]
    partitions[GROUP_RANDOM_AXES[1]]["positive_clustered_interval"] = False
    comparisons["true_organ_hard_vs_calibration_selected_random"] = (
        _conservative_random_family(partitions)
    )
    result = track_a_decision(
        comparisons,
        oracle_gate=True,
        technical_gates={"provenance": True, "exposure": True},
    )
    assert result["decision_branch"] == "random_control_fail"
    assert result["gates"]["random_control"] is False


def test_random_control_family_uses_least_favorable_of_all_three_partitions():
    partitions = {
        GROUP_RANDOM_AXES[0]: _metric(0.06),
        GROUP_RANDOM_AXES[1]: _metric(0.04),
        GROUP_RANDOM_AXES[2]: _metric(0.05),
    }
    partitions[GROUP_RANDOM_AXES[2]]["seed_sd_fraction_of_mean"] = 0.4
    family = _conservative_random_family(partitions)
    assert set(family["partition_comparisons"]) == set(GROUP_RANDOM_AXES)
    assert family["relative_mse_reduction_mean"] == pytest.approx(0.04)
    assert family["seed_sd_fraction_of_mean"] == pytest.approx(0.4)
    assert len(family["relative_mse_reduction_per_seed"]) == 9
    assert "every partition must pass" in family["aggregation"]

    with pytest.raises(ValueError, match="three axes|family"):
        _conservative_random_family({
            axis: partitions[axis] for axis in GROUP_RANDOM_AXES[:2]
        })
