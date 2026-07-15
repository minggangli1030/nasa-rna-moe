from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))

from evaluate_blind_species_gate import _fit_router, masked_gate_features  # noqa: E402


def test_masked_gate_features_hide_every_reconstruction_target():
    values = np.arange(24, dtype=np.float32).reshape(4, 6)
    mask = np.array([[0, 2], [1, 3], [2, 4], [3, 5]])
    features = masked_gate_features(values, mask, -10.0)
    np.testing.assert_array_equal(features[np.arange(4)[:, None], mask], -10.0)
    keep = np.ones_like(values, dtype=bool)
    keep[np.arange(4)[:, None], mask] = False
    np.testing.assert_array_equal(features[keep], values[keep])
    np.testing.assert_array_equal(values, np.arange(24, dtype=np.float32).reshape(4, 6))


def test_calibration_router_finds_species_specialists_and_convex_weights():
    true = np.array([[1.0, 2.0], [1.2, 2.2], [4.0, 5.0], [4.2, 5.2]])
    pred = np.stack([
        true + np.array([[0.0], [0.0], [2.0], [2.0]]),
        true + np.array([[2.0], [2.0], [0.0], [0.0]]),
        true + 0.5,
    ])
    labels = np.array(["human", "human", "mouse", "mouse"])
    router = _fit_router(pred, true, labels)
    assert router["hard"] == {"human": 0, "mouse": 1}
    for weights in [router["fixed"], *router["soft"].values()]:
        assert np.all(weights >= 0)
        assert abs(weights.sum() - 1.0) < 1e-12


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            suite.addTest(unittest.FunctionTestCase(value))
    return suite
