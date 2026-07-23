import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))

from build_stage1_k4_external_sample_review import (
    TARGET_ORGANS,
    apply_shortlist_amendment,
    build_sample_review,
    resolve_selector,
)


def test_resolve_selector_supports_regex_and_explicit_ids():
    group = pd.DataFrame([
        {
            "sample_id": "GSM1",
            "title": "donor1_control",
            "source_name_ch1": "brain",
            "characteristics_ch1": "disease state: control",
        },
        {
            "sample_id": "GSM2",
            "title": "donor1_disease",
            "source_name_ch1": "brain",
            "characteristics_ch1": "disease state: disease",
        },
    ])
    selected = resolve_selector(group, {
        "mode": "regex",
        "title_include_regex": "control",
        "metadata_include_all_regex": ["disease state:\\s*control"],
    })
    assert selected["sample_id"].tolist() == ["GSM1"]
    explicit = resolve_selector(group, {
        "mode": "explicit_sample_ids",
        "sample_ids": ["GSM2", "GSM1"],
    })
    assert explicit["sample_id"].tolist() == ["GSM2", "GSM1"]


def test_shortlist_amendment_replaces_exactly_one_group_in_place():
    shortlist = {
        "entries": [
            {"organ": "brain", "series_group_id": "GSE1"},
            {"organ": "liver", "series_group_id": "GSE2"},
        ]
    }
    amended = apply_shortlist_amendment(shortlist, {
        "metadata_only": True,
        "expression_values_read": False,
        "external_lockbox_frozen": False,
        "source_shortlist_sha256": "a" * 64,
        "replacements": [{
            "remove": {"organ": "liver", "series_group_id": "GSE2"},
            "add": {"organ": "liver", "series_group_id": "GSE3"},
        }],
    })
    assert amended["entries"] == [
        {"organ": "brain", "series_group_id": "GSE1"},
        {"organ": "liver", "series_group_id": "GSE3"},
    ]
    assert shortlist["entries"][1]["series_group_id"] == "GSE2"


def _write_fixture(tmp_path: Path):
    triage_rows = []
    geo_rows = []
    entries = []
    for index, organ in enumerate(TARGET_ORGANS):
        group_id = f"GSE{index + 1}"
        sample_id = f"GSM{index + 1}"
        triage_rows.append({
            "sample_id": sample_id,
            "series_id": group_id,
            "series_group_id": group_id,
            "organ": organ,
            "source_name_ch1": organ,
            "title": "healthy control",
            "characteristics_ch1": "disease state: control",
            "submitted_after_v11_creation": True,
            "classifier_tier": "high_confidence",
            "triage_tier": "priority_a_clean_positive_reference",
        })
        geo_rows.append({
            "organ": organ,
            "series_group_id": group_id,
            "series_tokens": group_id,
            "geo_pubmed_ids": "",
            "geo_bioproject_ids": f"PRJNA{index + 1}",
            "geo_series_titles": "Healthy study",
            "geo_overall_designs": "Bulk tissue",
            "geo_summaries": "Healthy control",
        })
        entries.append({
            "organ": organ,
            "series_group_id": group_id,
            "review_rationale": "synthetic healthy control",
            "donor_resolution_status": "pending",
            "selector": {"mode": "all_post_cutoff"},
        })
    triage_path = tmp_path / "triage.parquet"
    geo_path = tmp_path / "geo.csv"
    shortlist_path = tmp_path / "shortlist.json"
    pd.DataFrame(triage_rows).to_parquet(triage_path, index=False)
    pd.DataFrame(geo_rows).to_csv(geo_path, index=False)
    shortlist_path.write_text(json.dumps({
        "metadata_only": True,
        "expression_values_read": False,
        "external_lockbox_frozen": False,
        "study_status": "provisional_manual_review",
        "provisional_groups_per_organ": 1,
        "entries": entries,
    }))
    return triage_path, geo_path, shortlist_path


def test_build_sample_review_remains_metadata_only_and_pending(tmp_path):
    triage_path, geo_path, shortlist_path = _write_fixture(tmp_path)
    args = argparse.Namespace(
        sample_triage=str(triage_path),
        expected_triage_sha256=hashlib.sha256(triage_path.read_bytes()).hexdigest(),
        geo_study_review=str(geo_path),
        expected_geo_review_sha256=hashlib.sha256(geo_path.read_bytes()).hexdigest(),
        shortlist=str(shortlist_path),
        expected_shortlist_sha256=hashlib.sha256(
            shortlist_path.read_bytes()
        ).hexdigest(),
        code_commit="a" * 40,
        output_dir=str(tmp_path / "output"),
    )
    report = build_sample_review(args)
    assert report["status"] == "provisional_sample_review_ready_not_frozen"
    assert report["metadata_only"] is True
    assert report["expression_values_read"] is False
    assert report["efficacy_scoring_performed"] is False
    assert report["external_lockbox_frozen"] is False
    assert report["manual_decisions_complete"] is False
    samples = pd.read_csv(tmp_path / "output/provisional_sample_review.csv")
    groups = pd.read_csv(tmp_path / "output/provisional_study_review.csv")
    assert set(samples["manual_sample_decision"]) == {"pending"}
    assert set(groups["manual_study_decision"]) == {"pending"}


def test_build_sample_review_rejects_pre_cutoff_only_group(tmp_path):
    triage_path, geo_path, shortlist_path = _write_fixture(tmp_path)
    triage = pd.read_parquet(triage_path)
    triage.loc[triage["organ"] == "brain", "submitted_after_v11_creation"] = False
    triage.to_parquet(triage_path, index=False)
    args = argparse.Namespace(
        sample_triage=str(triage_path),
        expected_triage_sha256=hashlib.sha256(triage_path.read_bytes()).hexdigest(),
        geo_study_review=str(geo_path),
        expected_geo_review_sha256=hashlib.sha256(geo_path.read_bytes()).hexdigest(),
        shortlist=str(shortlist_path),
        expected_shortlist_sha256=hashlib.sha256(
            shortlist_path.read_bytes()
        ).hexdigest(),
        code_commit="a" * 40,
        output_dir=str(tmp_path / "output"),
    )
    with pytest.raises(ValueError, match="no post-cutoff samples"):
        build_sample_review(args)
