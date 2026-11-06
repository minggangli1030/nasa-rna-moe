import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evaluation"))

from evaluate_post_d2_phase1 import (  # noqa: E402
    _center_from_training_groups,
    paired_study_bootstrap,
    select_low_label_indices,
    sha256_file,
    verify_protocol,
)

import numpy as np


def test_paired_study_bootstrap_is_directional_and_deterministic():
    rows = []
    for study_index, study in enumerate(("S1", "S2", "S3")):
        for label in (0, 1):
            sample = f"{study}-{label}"
            rows.extend(
                [
                    {
                        "representation": "candidate",
                        "sample_id": sample,
                        "study_id": study,
                        "organ": "skeletal_muscle",
                        "label": label,
                        "probability": 0.1 + 0.8 * label,
                    },
                    {
                        "representation": "baseline",
                        "sample_id": sample,
                        "study_id": study,
                        "organ": "skeletal_muscle",
                        "label": label,
                        "probability": 0.45 + 0.1 * ((label + study_index) % 2),
                    },
                ]
            )
    frame = pd.DataFrame(rows)
    first = paired_study_bootstrap(
        frame,
        candidate="candidate",
        baseline="baseline",
        seed=17,
        replicates=100,
    )
    second = paired_study_bootstrap(
        frame,
        candidate="candidate",
        baseline="baseline",
        seed=17,
        replicates=100,
    )
    assert first == second
    assert first["delta_auroc"] > 0
    assert first["study_bootstrap_ci95"][0] >= 0


def test_protocol_hash_is_fail_closed(tmp_path: Path):
    path = tmp_path / "protocol.json"
    path.write_text(
        json.dumps({"status": "frozen_post_d2_secondary_analysis_before_execution"})
    )
    digest = sha256_file(path)
    assert verify_protocol(path, digest)["status"].startswith("frozen_post_d2")
    path.write_text("{}")
    try:
        verify_protocol(path, digest)
    except ValueError as error:
        assert "mismatch" in str(error)
    else:
        raise AssertionError("modified protocol did not fail closed")


def test_fold_fit_centering_uses_training_means_only():
    x_train = np.asarray([[1.0], [3.0], [10.0], [14.0]], dtype=np.float32)
    organ_train = np.asarray(["a", "a", "b", "b"])
    x_test = np.asarray([[101.0], [114.0]], dtype=np.float32)
    organ_test = np.asarray(["a", "b"])
    train, test = _center_from_training_groups(
        x_train, organ_train, x_test, organ_test
    )
    assert np.allclose(train, [[-1.0], [1.0], [-2.0], [2.0]])
    assert np.allclose(test, [[99.0], [102.0]])


def test_low_label_selection_is_paired_grouped_and_reproducible():
    groups = np.repeat(["a", "b", "c", "d"], 6)
    labels = np.tile([0, 0, 0, 1, 1, 1], 4)
    train_index = np.arange(len(labels))
    first = select_low_label_indices(
        train_index, groups, labels, fraction=0.05, seed=3101
    )
    second = select_low_label_indices(
        train_index, groups, labels, fraction=0.05, seed=3101
    )
    assert np.array_equal(first, second)
    assert len(first) == 8
    assert len(np.unique(groups[first])) == 4
    for group in np.unique(groups[first]):
        assert set(labels[first][groups[first] == group]) == {0, 1}


def test_full_label_selection_preserves_every_training_row():
    groups = np.repeat(["a", "b", "c"], 4)
    labels = np.tile([0, 0, 1, 1], 3)
    train_index = np.asarray([0, 1, 2, 3, 5, 6, 8, 9, 10, 11])
    selected = select_low_label_indices(
        train_index, groups, labels, fraction=1.0, seed=3101
    )
    assert np.array_equal(selected, train_index)
