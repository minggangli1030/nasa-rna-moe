from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))

from filter_manifest_by_expression_qc import filter_manifest  # noqa: E402


def _hash(values) -> str:
    return hashlib.sha256(("\n".join(values) + "\n").encode()).hexdigest()


def _fixture():
    rows = []
    for organ in ("brain", "skin"):
        for split in ("train", "calibration", "test"):
            for index in range(2):
                rows.append({
                    "sample_id": f"{organ}-{split}-{index}",
                    "organ": organ,
                    "series_group_id": f"{organ}-{split}-g{index}",
                    "split": split,
                })
    frame = pd.DataFrame(rows)
    failed = ["brain-train-0", "skin-test-1"]
    report = {
        "status": "failed_qc",
        "manifest": {
            "n_samples": len(frame),
            "ordered_sample_id_sha256": _hash(frame["sample_id"].tolist()),
        },
        "qc": {"failures": [{"sample_id": value} for value in failed]},
    }
    return frame, report


def test_filters_only_explicit_failures_and_preserves_splits():
    frame, extraction = _fixture()
    filtered, report = filter_manifest(frame, extraction)
    assert report["n_before"] == 12
    assert report["n_removed"] == 2
    assert report["n_after"] == 10
    assert "brain-train-0" not in set(filtered["sample_id"])
    assert "skin-test-1" not in set(filtered["sample_id"])
    assert filtered.groupby("series_group_id")["split"].nunique().max() == 1


def test_rejects_report_for_different_manifest():
    frame, extraction = _fixture()
    reordered = frame.iloc[::-1].reset_index(drop=True)
    try:
        filter_manifest(reordered, extraction)
    except ValueError as exc:
        assert "order hash" in str(exc)
    else:
        raise AssertionError("expected manifest/report mismatch rejection")


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            suite.addTest(unittest.FunctionTestCase(value))
    return suite
