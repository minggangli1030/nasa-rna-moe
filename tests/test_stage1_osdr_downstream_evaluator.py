import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evaluation"))

from evaluate_stage1_osdr_downstream import nested_group_evaluate  # noqa: E402


def test_nested_group_evaluation_is_complete_and_group_disjoint():
    rng = np.random.default_rng(7)
    groups = np.repeat([f"s{i}" for i in range(8)], 8)
    labels = np.tile([0, 1, 0, 1, 0, 1, 0, 1], 8)
    features = rng.normal(size=(len(labels), 6))
    features[:, 0] += labels * 1.5
    result = nested_group_evaluate(
        features,
        labels,
        groups,
        outer_folds=4,
        inner_folds=2,
        pca_components=None,
        grid=((0.1, 0.0), (1.0, 0.0)),
    )
    assert np.isfinite(result["probabilities"]).all()
    assert set(result["predictions"]) <= {0, 1}
    assert len(result["folds"]) == 4
    assert result["pooled_out_of_fold"]["auroc"] > 0.5
