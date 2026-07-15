from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))

from audit_archs4_organs import CELL_LIKE, classify_organ  # noqa: E402


def test_conservative_organ_classifier_prefers_source_and_rejects_conflicts():
    assert classify_organ("left ventricle tissue", "control") == (
        "heart", "source", ["heart"]
    )
    assert classify_organ("biopsy", "normal liver tissue") == (
        "liver", "title", ["liver"]
    )
    label, evidence, hits = classify_organ("brain and liver tissue", "mixed sample")
    assert label is None
    assert evidence == "ambiguous"
    assert hits == ["brain", "liver"]


def test_cell_like_filter_excludes_cultured_organ_derived_material():
    assert CELL_LIKE.search("human mammary epithelial cells")
    assert CELL_LIKE.search("cultured kidney organoid")
    assert not CELL_LIKE.search("normal kidney tissue biopsy")


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            suite.addTest(unittest.FunctionTestCase(value))
    return suite
