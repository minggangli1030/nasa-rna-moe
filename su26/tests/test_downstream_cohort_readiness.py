import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evaluation"))

from audit_downstream_cohort_readiness import (  # noqa: E402
    build_osdr_candidate,
    map_osdr_organ,
)


def test_strict_organ_mapping_is_fail_closed():
    assert map_osdr_organ("Left Lobe of the Liver") == "liver"
    assert map_osdr_organ("Right hippocampus") == "brain"
    assert map_osdr_organ("Right quadriceps femoris") == "skeletal_muscle"
    assert map_osdr_organ("liver and lung") == ""
    assert map_osdr_organ("kidney") == ""


def test_candidate_requires_both_labels_within_study_organ():
    rows = [
        ("OSD-1", "a", "Liver", "Space Flight"),
        ("OSD-1", "b", "Liver", "Ground Control"),
        ("OSD-2", "c", "Liver", "Space Flight"),
        ("OSD-1", "d", "Kidney", "Ground Control"),
    ]
    frame = pd.DataFrame(
        rows,
        columns=[
            "id.accession",
            "id.sample name",
            "study.characteristics.material type",
            "study.factor value.spaceflight",
        ],
    )
    frame["counts_file"] = frame["id.accession"] + ".csv"
    frame["counts_path"] = "missing/" + frame["counts_file"]
    result = build_osdr_candidate(frame)
    assert result["id.sample name"].tolist() == ["a", "b"]
    assert result["downstream_label"].tolist() == [1, 0]
