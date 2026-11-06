import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))

from build_stage1_k4_external_curation import build_workbook


def test_curation_workbook_is_metadata_only_and_never_final(tmp_path):
    candidates = pd.DataFrame([
        {
            "sample_id": "GSM1",
            "series_id": "GSE1",
            "series_group_id": "GSE1",
            "organ": "brain",
            "source_name_ch1": "normal brain tissue",
            "title": "healthy control",
            "characteristics_ch1": "tissue: brain,disease state: healthy",
            "singlecellprobability": 0.0,
            "submitted_after_v11_creation": True,
        },
        {
            "sample_id": "GSM2",
            "series_id": "GSE2",
            "series_group_id": "GSE2",
            "organ": "liver",
            "source_name_ch1": "HepG2 cells",
            "title": "control",
            "characteristics_ch1": "tissue: liver",
            "singlecellprobability": 0.0,
            "submitted_after_v11_creation": True,
        },
    ])
    candidate_path = tmp_path / "candidate.parquet"
    candidates.to_parquet(candidate_path, index=False)
    candidate_hash = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
    scout_report_path = tmp_path / "scout_report.json"
    scout_report_path.write_text(json.dumps({
        "metadata_only": True,
        "expression_values_read": False,
        "hashes": {"candidate_metadata_sha256": candidate_hash},
    }))
    args = argparse.Namespace(
        candidate_metadata=str(candidate_path),
        scout_report=str(scout_report_path),
        expected_candidate_sha256=candidate_hash,
        ontology=str(ROOT / "data/ontology/uberon_organ_map.json"),
        code_commit="a" * 40,
        output_dir=str(tmp_path / "curation"),
    )
    report = build_workbook(args)
    assert report["metadata_only"] is True
    assert report["efficacy_scoring_performed"] is False
    assert report["external_lockbox_frozen"] is False
    assert report["automated_decisions_are_final"] is False

    workbook = pd.read_csv(
        tmp_path / "curation/study_curation_workbook.csv"
    )
    assert set(workbook["review_decision"]) == {"pending"}
    assert workbook.loc[workbook["organ"] == "brain", "automated_priority"].item() == "A"
    assert (
        workbook.loc[workbook["organ"] == "liver", "automated_priority"].item()
        == "excluded_only"
    )
