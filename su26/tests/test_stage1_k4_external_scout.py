import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))

from build_stage1_k4_external_scout import (
    _manual_review_sheet,
    build_scout,
    sha256_lines,
    sha256_pairs,
)


def test_external_scout_excludes_historical_samples_and_series(tmp_path):
    historical = pd.DataFrame({
        "geo_accession": ["GSM_OLD", "GSM_OTHER"],
        "series_id": ["GSE_OLD", "GSE_OTHER"],
    })
    historical_path = tmp_path / "historical.parquet"
    historical.to_parquet(historical_path, index=False)

    base = {
        "h5_row": [0, 1, 2],
        "geo_accession": ["GSM_OLD", "GSM_SHARED_SERIES", "GSM_NEW"],
        "series_id": ["GSE_NEW_A", "GSE_OLD", "GSE_NEW_B"],
        "source_name_ch1": ["brain", "brain", "brain"],
        "title": ["brain tissue", "brain tissue", "brain tissue"],
        "characteristics_ch1": ["tissue: brain"] * 3,
        "singlecellprobability": [0.0] * 3,
        "library_strategy": ["RNA-Seq"] * 3,
        "library_source": ["TRANSCRIPTOMIC"] * 3,
        "submission_date": ["2024-01-01"] * 3,
        "last_update_date": ["2024-01-02"] * 3,
        "readsaligned": [1_000_000.0] * 3,
        "readstotal": [1_100_000.0] * 3,
    }
    current = pd.DataFrame(base)
    current_path = tmp_path / "current.parquet"
    current.to_parquet(current_path, index=False)
    current_hash = hashlib.sha256(current_path.read_bytes()).hexdigest()
    current_report_path = tmp_path / "current_report.json"
    current_report_path.write_text(json.dumps({
        "metadata_only": True,
        "expression_values_read": False,
        "output_parquet_sha256": current_hash,
    }))

    args = argparse.Namespace(
        code_commit="a" * 40,
        protocol=str(ROOT / "artifacts/stage1_k4_external_scout/protocol.json"),
        current_metadata=str(current_path),
        current_report=str(current_report_path),
        historical_metadata=str(historical_path),
        expected_historical_accession_sha256=sha256_lines(
            historical["geo_accession"].tolist()
        ),
        expected_historical_series_mapping_sha256=sha256_pairs(
            historical["geo_accession"].tolist(),
            historical["series_id"].tolist(),
        ),
        ontology=str(ROOT / "data/ontology/uberon_organ_map.json"),
        output_dir=str(tmp_path / "scout"),
        batch_size=2,
        single_cell_threshold=0.5,
        temporal_cutoff="2021-11-13",
        manual_review_per_organ=50,
    )
    report = build_scout(args)
    candidates = pd.read_parquet(tmp_path / "scout/candidate_metadata.parquet")
    assert candidates["sample_id"].tolist() == ["GSM_NEW"]
    assert report["exclusions"]["historical_sample"] == 1
    assert report["exclusions"]["historical_series"] == 1
    assert report["expression_values_read"] is False
    assert report["external_lockbox_frozen"] is False


def test_review_round_two_excludes_prior_connected_series():
    candidates = pd.DataFrame({
        "organ": ["brain"] * 4 + ["liver"] * 4,
        "series_group_id": [
            "GSE1", "GSE2", "GSE3", "GSE4",
            "GSE5", "GSE6", "GSE7", "GSE8",
        ],
        "series_id": [
            "GSE1", "GSE2", "GSE3", "GSE4",
            "GSE5", "GSE6", "GSE7", "GSE8",
        ],
        "sample_id": [f"GSM{i}" for i in range(1, 9)],
    })
    review = _manual_review_sheet(
        candidates,
        per_organ=2,
        excluded_series_tokens={"GSE1", "GSE5"},
    )
    assert review.groupby("organ").size().to_dict() == {"brain": 2, "liver": 2}
    assert set(review["series_group_id"]).isdisjoint({"GSE1", "GSE5"})


def test_review_exclusion_survives_connected_group_shrinkage():
    candidates = pd.DataFrame({
        "organ": ["brain", "brain"],
        "series_group_id": ["GSE2|GSE3", "GSE4"],
        "series_id": ["GSE2 GSE3", "GSE4"],
        "sample_id": ["GSM2", "GSM4"],
    })
    review = _manual_review_sheet(
        candidates,
        per_organ=5,
        excluded_series_tokens={"GSE1", "GSE2"},
    )
    assert review["sample_id"].tolist() == ["GSM4"]
