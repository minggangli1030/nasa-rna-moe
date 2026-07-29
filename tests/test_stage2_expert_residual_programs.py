from __future__ import annotations

import numpy as np
import pandas as pd

from evaluation.extract_stage2_expert_residual_programs import ARRAY_NAMES
from evaluation.evaluate_stage2_expert_residual_programs import (
    _bootstrap_ci,
    _cosine,
    _donor_means,
    _spearman,
    _top_jaccard,
)


def test_string_metadata_is_serializable_without_object_dtype():
    frame = pd.DataFrame({"organ": ["brain"], "donor": ["GTEX-1"]})
    organs = frame["organ"].to_numpy(dtype=str)
    donors = frame["donor"].to_numpy(dtype=str)
    assert organs.dtype.kind == "U"
    assert donors.dtype.kind == "U"
    assert "specialist_squared_error" in ARRAY_NAMES


def test_similarity_helpers_identify_reproducible_programs():
    left = np.arange(1.0, 121.0)
    right = 2.0 * left + 7.0
    assert _cosine(left, left) == 1.0
    assert _spearman(left, right) == 1.0
    assert _top_jaccard(left, right, 100) == 1.0


def test_donor_means_prevent_replicate_weighting():
    values = np.asarray([[1.0, 2.0], [3.0, 4.0], [10.0, 20.0]])
    donors = np.asarray(["a", "a", "b"])
    names, means = _donor_means(values, donors)
    assert names.tolist() == ["a", "b"]
    np.testing.assert_allclose(means, [[2.0, 3.0], [10.0, 20.0]])


def test_bootstrap_interval_is_deterministic_and_directional():
    values = np.ones((12, 3), dtype=np.float32)
    first = _bootstrap_ci(values, replicates=100, seed=17, levels=(0.95,))
    second = _bootstrap_ci(values, replicates=100, seed=17, levels=(0.95,))
    np.testing.assert_array_equal(first[0.95][0], second[0.95][0])
    np.testing.assert_array_equal(first[0.95][1], second[0.95][1])
    assert np.all(first[0.95][0] > 0)
