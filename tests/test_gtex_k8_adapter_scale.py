import importlib.util
from pathlib import Path

import numpy as np


MODULE_PATH = Path(__file__).resolve().parents[1] / "evaluation" / "evaluate_gtex_k8_adapter_scale.py"
SPEC = importlib.util.spec_from_file_location("evaluate_gtex_k8_adapter_scale", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_macro_organ_donor_mse_equalizes_organs_and_donors():
    organs = np.repeat(np.asarray(MODULE.ORGANS), 3)
    groups = np.tile(np.asarray(["a", "a", "b"]), 8)
    values = np.tile(np.asarray([1.0, 3.0, 5.0]), 8)
    # donor a mean=2, donor b mean=5, organ mean=3.5, then equal-organ mean=3.5
    assert MODULE.macro_organ_donor_mse(values, organs, groups) == 3.5


def test_relative_gain_direction():
    assert MODULE.relative_gain(10.0, 9.0) == 10.0
    assert MODULE.relative_gain(10.0, 11.0) == -10.0
