import importlib.util
from pathlib import Path

import pandas as pd


MODULE_PATH = Path(__file__).resolve().parents[1] / "evaluation" / "build_gtex_k8_scale_manifests.py"
SPEC = importlib.util.spec_from_file_location("build_gtex_k8_scale_manifests", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_nested_donor_atomic_scale_selection():
    rows = []
    for organ in MODULE.ORGANS:
        for donor_index in range(6):
            for sample_index in range(2):
                rows.append(
                    {
                        "sample_id": f"{organ}-d{donor_index}-s{sample_index}",
                        "donor_id": f"{organ}-d{donor_index}",
                        "organ": organ,
                        "split": "train",
                    }
                )
        rows.append(
            {
                "sample_id": f"{organ}-cal",
                "donor_id": f"{organ}-cal",
                "organ": organ,
                "split": "calibration",
            }
        )
    frame, report = MODULE.select_nested_samples(
        pd.DataFrame(rows), budgets=[2, 4, 6], selection_seed=17
    )
    for budget in (2, 4, 6):
        selected = frame.loc[frame[f"scale_b{budget}"]]
        assert len(selected) == budget * 8
        assert selected["donor_id"].nunique() == budget * 8
        assert selected["split"].eq("train").all()
        assert report[str(budget)]["total_samples"] == budget * 8
    assert set(frame.loc[frame["scale_b2"], "sample_id"]).issubset(
        set(frame.loc[frame["scale_b4"], "sample_id"])
    )
