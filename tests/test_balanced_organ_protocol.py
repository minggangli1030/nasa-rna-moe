from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))

from build_balanced_organ_protocol import build_balanced_protocol  # noqa: E402


def _manifest(counts: dict[str, list[int]]) -> pd.DataFrame:
    rows = []
    for organ, group_sizes in counts.items():
        for group_index, size in enumerate(group_sizes):
            for sample_index in range(size):
                rows.append({
                    "sample_id": f"{organ}-{group_index}-{sample_index}",
                    "organ": organ,
                    "series_group_id": f"{organ}-g{group_index}",
                    "split": "train",
                })
        rows.append({
            "sample_id": f"{organ}-test",
            "organ": organ,
            "series_group_id": f"{organ}-test-g",
            "split": "test",
        })
    return pd.DataFrame(rows)


def test_balances_organs_and_random_shards_without_dropping_natural_rows():
    frame = _manifest({
        "brain": [8, 5, 3],
        "colon": [2, 2, 2, 2, 2],
        "liver": [4, 4, 4],
    })
    output, report = build_balanced_protocol(frame, seed=17)
    assert len(output) == len(frame)
    assert report["target_per_organ"] == 10
    selected = output.loc[output["balanced_train"]]
    assert selected.groupby("organ").size().to_dict() == {
        "brain": 10,
        "colon": 10,
        "liver": 10,
    }
    assert set(selected.groupby("random_shard").size()) == {10}
    mixture = selected.groupby(["random_shard", "organ"]).size().unstack(fill_value=0)
    assert int((mixture.max() - mixture.min()).max()) <= 1
    study_counts = selected.groupby("random_shard")["series_group_id"].nunique()
    assert int(study_counts.max() - study_counts.min()) <= 1
    assert not output.loc[output["split"].eq("test"), "balanced_train"].any()
    assert (output.loc[output["split"].eq("test"), "random_shard"] != "").all()


def test_is_order_invariant_and_spreads_selection_across_studies():
    frame = _manifest({"brain": [20, 1, 1, 1], "skin": [3, 3, 3, 3]})
    first, first_report = build_balanced_protocol(frame, seed=42, target_per_organ=8)
    second, second_report = build_balanced_protocol(
        frame.sample(frac=1.0, random_state=9), seed=42, target_per_organ=8
    )
    first_map = first.set_index("sample_id")[["balanced_train", "random_shard"]].sort_index()
    second_map = second.set_index("sample_id")[["balanced_train", "random_shard"]].sort_index()
    pd.testing.assert_frame_equal(first_map, second_map)
    assert first_report["balanced_sample_id_sha256"] == second_report["balanced_sample_id_sha256"]
    brain_groups = first.loc[
        first["balanced_train"] & first["organ"].eq("brain"), "series_group_id"
    ].nunique()
    assert brain_groups == 4


def test_rejects_split_leakage_and_oversized_target():
    frame = _manifest({"brain": [3, 3], "skin": [3, 3]})
    leaked = frame.copy()
    leaked.loc[leaked.index[-1], "series_group_id"] = leaked.iloc[0]["series_group_id"]
    try:
        build_balanced_protocol(leaked)
    except ValueError as exc:
        assert "cross splits" in str(exc)
    else:
        raise AssertionError("expected connected-study leakage rejection")

    try:
        build_balanced_protocol(frame, target_per_organ=7)
    except ValueError as exc:
        assert "exceeds availability" in str(exc)
    else:
        raise AssertionError("expected oversized target rejection")


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            suite.addTest(unittest.FunctionTestCase(value))
    return suite
