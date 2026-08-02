from __future__ import annotations

import numpy as np

from evaluation.audit_osdr_encoder_validity import (
    aggregate_verdict,
    balanced_group_splits,
    distribution_verdict,
    input_domain_verdict,
    organ_recovery_verdict,
)


def test_balanced_group_splits_preserve_classes_and_groups():
    groups = np.asarray(
        ["brain_a"] * 4 + ["brain_b"] * 3 + ["brain_c"] * 2
        + ["muscle_a"] * 5 + ["muscle_b"] * 4 + ["muscle_c"] * 3
    )
    labels = np.asarray([0] * 9 + [1] * 12)
    for train, test in balanced_group_splits(labels, groups, 3):
        assert set(labels[train]) == {0, 1}
        assert set(labels[test]) == {0, 1}
        assert not (set(groups[train]) & set(groups[test]))


def test_frozen_verdicts_are_fail_closed():
    a = {
        "out_of_distribution_rank_ratio": 0.5,
        "out_of_distribution_median_abs_z": 3.0,
        "out_of_distribution_dead_fraction": 0.25,
        "in_distribution_rank_ratio": 0.7,
        "in_distribution_median_abs_z": 2.0,
    }
    assert distribution_verdict(
        rank_ratio=0.4, median_abs_z=1.0, dead_fraction=0.0, thresholds=a
    ) == "ENCODER_OUT_OF_DISTRIBUTION"
    assert distribution_verdict(
        rank_ratio=0.8, median_abs_z=1.0, dead_fraction=0.0, thresholds=a
    ) == "ENCODER_IN_DISTRIBUTION"
    b = {
        "minimum_raw_balanced_accuracy": 0.7,
        "recovers_organ_ratio": 0.7,
        "degenerate_ratio": 0.5,
    }
    assert organ_recovery_verdict(0.9, [0.8, 0.75, 0.72], b) == "ENCODER_RECOVERS_ORGAN"
    assert organ_recovery_verdict(0.9, [0.3, 0.4, 0.49], b) == "ENCODER_DEGENERATE"
    c = {"shift_fraction": 0.1, "ok_fraction": 0.05}
    assert input_domain_verdict(
        imputed_fraction=0.11,
        constant_fraction=0.01,
        normalization_identical=True,
        thresholds=c,
    ) == "INPUT_DOMAIN_SHIFT"
    assert aggregate_verdict(
        "ENCODER_IN_DISTRIBUTION", "ENCODER_RECOVERS_ORGAN", "INPUT_DOMAIN_SHIFT"
    ) == "CROSS_SPECIES_ENCODER_BREAKDOWN"
