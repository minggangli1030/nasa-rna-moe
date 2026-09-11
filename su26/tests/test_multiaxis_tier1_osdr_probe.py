import numpy as np
import pandas as pd

from evaluation.evaluate_multiaxis_tier1_osdr_probe import (
    hallmark_features,
    join_candidate_metadata,
    normalize_exact,
    study_bootstrap_delta,
)


def test_normalize_exact_preserves_missing_and_normalizes_case():
    assert normalize_exact("  Left  Lung ") == "left lung"
    assert normalize_exact(np.nan) == "__missing__"


def test_join_candidate_metadata_is_exact_and_order_preserving():
    retained = pd.DataFrame(
        {"study_id": ["S2", "S1"], "sample_name": ["b", "a"]}
    )
    candidates = pd.DataFrame(
        {
            "id.accession": ["S1", "S2"],
            "id.sample name": ["a", "b"],
            "id.assay name": ["A", "B"],
        }
    )
    joined = join_candidate_metadata(retained, candidates)
    assert joined["id.assay name"].tolist() == ["B", "A"]


def test_hallmark_features_excludes_score_genes():
    expression = pd.DataFrame(
        {
            "A": [1.0, 3.0],
            "B": [9.0, 9.0],
            **{f"G{i}": [float(i), float(i + 2)] for i in range(10)},
        }
    )
    sets = {"H": tuple(["A", "B"] + [f"G{i}" for i in range(10)])}
    features, coverage = hallmark_features(expression, sets, {"B"})
    assert coverage == {"H": 11}
    assert np.allclose(features[:, 0], expression[["A"] + [f"G{i}" for i in range(10)]].mean(axis=1))


def test_study_bootstrap_delta_tracks_better_probabilities():
    labels = np.tile([0, 1], 10)
    groups = np.repeat([f"S{i}" for i in range(10)], 2)
    base = np.full(20, 0.5)
    candidate = labels * 0.8 + 0.1
    result = study_bootstrap_delta(
        labels, base, candidate, groups, replicates=50, seed=17
    )
    assert result["ci95"][0] > 0
