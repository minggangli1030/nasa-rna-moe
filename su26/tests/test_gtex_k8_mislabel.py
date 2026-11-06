import importlib.util
from pathlib import Path

import numpy as np


MODULE_PATH = Path(__file__).resolve().parents[1] / "evaluation" / "evaluate_gtex_k8_mislabel.py"
SPEC = importlib.util.spec_from_file_location("evaluate_gtex_k8_mislabel", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)
compatibility_margin = MODULE.compatibility_margin
macro_organ_auc = MODULE.macro_organ_auc


def test_compatibility_margin_is_zero_at_best_assignment():
    errors = np.stack([np.roll(np.arange(8, dtype=float), shift) for shift in range(8)])
    margins = compatibility_margin(errors)
    assert margins.shape == (8, 8)
    assert np.allclose(margins.min(axis=1), 0.0)


def test_perfect_true_assignment_has_unit_macro_auc():
    true_labels = np.repeat(np.arange(8), 2)
    errors = np.ones((16, 8), dtype=float)
    errors[np.arange(16), true_labels] = 0.0
    margins = compatibility_margin(errors)
    assert macro_organ_auc(margins, true_labels) == 1.0
