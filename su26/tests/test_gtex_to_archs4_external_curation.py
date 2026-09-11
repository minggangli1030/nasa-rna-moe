from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))
sys.path.insert(0, str(ROOT / "evaluation"))

from build_gtex_to_archs4_external_curation import (  # noqa: E402
    _build_candidates,
    _build_workbook,
)


ORGANS = [
    "adipose",
    "brain",
    "colon",
    "heart",
    "liver",
    "lung",
    "skeletal_muscle",
    "skin",
]


def _frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = []
    for index, organ in enumerate(ORGANS):
        rows.append(
            {
                "h5_row": index,
                "geo_accession": f"GSM{1000 + index}",
                "series_id": f"GSE{2000 + index}",
                "source_name_ch1": organ.replace("_", " "),
                "title": f"healthy {organ} donor {index}",
                "characteristics_ch1": f"tissue: {organ}; status: healthy",
                "library_strategy": "RNA-Seq",
                "library_source": "transcriptomic",
                "submission_date": "2025-01-01",
                "last_update_date": "2025-02-01",
                "singlecellprobability": 0.0,
                "readsaligned": 100,
                "readstotal": 120,
            }
        )
    current = pd.DataFrame(rows)
    recovered = current.copy()
    recovered["organ"] = ORGANS
    recovered["uberon_id"] = [f"UBERON:{index:07d}" for index in range(8)]
    recovered["tier"] = "high_confidence"
    recovered["evidence"] = "characteristics_tissue"
    historical = pd.DataFrame(
        {
            "geo_accession": ["GSM-old"],
            "series_id": ["GSE-old"],
        }
    )
    return current, historical, recovered


def test_builds_expression_sealed_k8_candidate_family() -> None:
    current, historical, recovered = _frames()
    candidates, counts = _build_candidates(
        current,
        historical,
        recovered,
        organs=ORGANS,
        cutoff="2021-11-13",
    )
    assert candidates["organ"].tolist() == ORGANS
    assert candidates["submitted_after_v11_creation"].all()
    assert counts["candidate_samples"] == 8
    assert counts["candidate_connected_studies"] == 8

    triaged = candidates.assign(
        triage_tier="priority_a_clean_positive_reference",
        positive_reference_marker=True,
        classifier_tier="high_confidence",
        classifier_reasons="",
        triage_flags="",
    )
    workbook = _build_workbook(triaged, organs=ORGANS)
    assert workbook["organ"].tolist() == ORGANS
    assert set(workbook["manual_study_decision"]) == {"pending"}
    assert set(workbook["manual_donor_audit"]) == {"pending"}
    assert set(workbook["manual_near_duplicate_audit"]) == {"pending"}


def test_rejects_alignment_drift_and_historical_series_overlap() -> None:
    current, historical, recovered = _frames()
    recovered.loc[0, "geo_accession"] = "GSM-drift"
    with pytest.raises(ValueError, match="row-aligned"):
        _build_candidates(
            current,
            historical,
            recovered,
            organs=ORGANS,
            cutoff="2021-11-13",
        )

    current, historical, recovered = _frames()
    historical.loc[0, "series_id"] = recovered.loc[0, "series_id"]
    with pytest.raises(ValueError, match="does not cover all K8"):
        _build_candidates(
            current,
            historical,
            recovered,
            organs=ORGANS,
            cutoff="2021-11-13",
        )
