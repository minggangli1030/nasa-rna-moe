from __future__ import annotations

import sys
import unittest
from argparse import Namespace
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))

from build_organ_pilot_manifest import assign_group_splits, build_manifest  # noqa: E402


def test_group_split_is_deterministic_and_disjoint():
    groups = [f"GSE{i}" for i in range(20)]
    first = assign_group_splits(groups, 7, 0.15, 0.15)
    second = assign_group_splits(list(reversed(groups)), 7, 0.15, 0.15)
    assert first == second
    assert set(first) == set(groups)
    assert set(first.values()) == {"train", "calibration", "test"}


def test_group_split_balances_samples_without_splitting_large_groups():
    groups = [f"GSE{i}" for i in range(20)]
    weights = {group: 2 for group in groups}
    weights["GSE0"] = 10
    result = assign_group_splits(groups, 9, 0.2, 0.2, weights)
    total = sum(weights.values())
    fractions = {
        split: sum(weights[group] for group, value in result.items() if value == split) / total
        for split in ("calibration", "test")
    }
    assert abs(fractions["calibration"] - 0.2) < 0.04
    assert abs(fractions["test"] - 0.2) < 0.04


def test_manifest_uses_exact_specialist_union_and_removes_unsafe_groups():
    records = []
    for organ in ("brain", "liver"):
        for group_index in range(6):
            for sample_index in range(3):
                records.append({
                    "sample_id": f"{organ}-{group_index}-{sample_index}",
                    "organ": organ,
                    "series_group_id": f"{organ}-g{group_index}",
                    "tumor_like": False,
                })
    records.extend([
        {"sample_id": "tumor", "organ": "brain", "series_group_id": "tumor-g", "tumor_like": True},
        {"sample_id": "mixed-a", "organ": "brain", "series_group_id": "mixed-g", "tumor_like": False},
        {"sample_id": "mixed-b", "organ": "liver", "series_group_id": "mixed-g", "tumor_like": False},
    ])
    args = Namespace(
        exclude_tumor_like=True,
        seed=11,
        max_samples_per_group=2,
        min_series_groups=5,
        min_capped_samples=10,
        max_organs=0,
        calibration_fraction=0.2,
        test_fraction=0.2,
    )
    manifest, report = build_manifest(pd.DataFrame(records), args)
    assert set(manifest["organ"]) == {"brain", "liver"}
    assert "tumor" not in set(manifest["sample_id"])
    assert "mixed-g" not in set(manifest["series_group_id"])
    assert manifest.groupby("series_group_id")["split"].nunique().max() == 1
    assert report["pooled_train_is_exact_specialist_union"] is True
    assert report["pooled_train_sample_sha256"] == report["specialist_union_train_sample_sha256"]


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            suite.addTest(unittest.FunctionTestCase(value))
    return suite
