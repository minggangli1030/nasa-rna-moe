from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
for source_dir in (ROOT / "core", ROOT / "evaluation"):
    if str(source_dir) not in sys.path:
        sys.path.insert(0, str(source_dir))

from freeze_stage1_k4_random_mappings import (  # noqa: E402
    MODEL_SEEDS,
    aggregate_mapping,
)


def test_random_mapping_averages_seeds_then_samples_then_studies():
    organs = np.asarray(
        ["brain", "brain", "brain", "liver", "skeletal_muscle", "skin"]
    )
    groups = np.asarray(["brain-large", "brain-large", "brain-small", "l", "m", "s"])
    base = np.asarray(
        [
            [0.0, 2.0, 5.0, 6.0],
            [0.0, 2.0, 5.0, 6.0],
            [10.0, 2.0, 5.0, 6.0],
            [5.0, 4.0, 3.0, 2.0],
            [5.0, 1.0, 4.0, 3.0],
            [5.0, 4.0, 1.0, 3.0],
        ]
    )
    losses = {seed: base + offset for seed, offset in zip(MODEL_SEEDS, (0.0, 1.0, 2.0))}

    mapping, scores = aggregate_mapping(losses, organs, groups)

    # Brain expert 0 is 5.0 under equal sample mass, but 7.5 under equal
    # connected-study mass; expert 1 therefore wins after the required hierarchy.
    assert scores["brain"][0] == pytest.approx(6.0)
    assert scores["brain"][1] == pytest.approx(3.0)
    assert mapping == {
        "brain": 1,
        "liver": 3,
        "skeletal_muscle": 1,
        "skin": 2,
        "adipose": -1,
    }


def test_random_mapping_breaks_exact_ties_by_lowest_expert_and_fails_on_seed_gap():
    organs = np.asarray(["brain", "liver", "skeletal_muscle", "skin"])
    groups = np.asarray(["b", "l", "m", "s"])
    tied = np.ones((4, 4), dtype=np.float64)
    losses = {seed: tied.copy() for seed in MODEL_SEEDS}
    mapping, _ = aggregate_mapping(losses, organs, groups)
    assert all(mapping[organ] == 0 for organ in organs)

    losses.pop(MODEL_SEEDS[-1])
    with pytest.raises(ValueError, match="cover exactly"):
        aggregate_mapping(losses, organs, groups)
