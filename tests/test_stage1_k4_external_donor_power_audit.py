import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))

from build_stage1_k4_external_donor_power_audit import (
    TARGET_ORGANS,
    build_donor_power_audit,
    exact_sign_test_sensitivity,
)


def test_exact_sign_test_sensitivity_is_monotone():
    result = exact_sign_test_sensitivity(40, 0.025, [0.6, 0.7, 0.8])
    assert result["minimum_positive_studies_for_rejection"] > 20
    powers = list(result["power_by_true_positive_study_probability"].values())
    assert powers == sorted(powers)
    assert result["achieved_null_tail_probability"] <= 0.025


def _write_fixture(tmp_path: Path):
    sample_rows = []
    study_rows = []
    for index, organ in enumerate(TARGET_ORGANS):
        group_id = f"GSE{index + 1}"
        sample_rows.append({
            "sample_id": f"GSM{index + 1}",
            "organ": organ,
            "series_group_id": group_id,
            "title": f"donor_{index + 1}",
            "characteristics_ch1": "tissue: control",
            "submitted_after_v11_creation": True,
            "manual_sample_decision": "pending",
        })
        study_rows.append({
            "organ": organ,
            "series_group_id": group_id,
            "n_provisional_selector_matches": 1,
            "manual_study_decision": "pending",
        })
    samples_path = tmp_path / "samples.csv"
    studies_path = tmp_path / "studies.csv"
    pd.DataFrame(sample_rows).to_csv(samples_path, index=False)
    pd.DataFrame(study_rows).to_csv(studies_path, index=False)
    report_path = tmp_path / "source_report.json"
    report_path.write_text(json.dumps({
        "metadata_only": True,
        "expression_values_read": False,
        "external_lockbox_frozen": False,
        "hashes": {
            "provisional_sample_review_sha256": hashlib.sha256(
                samples_path.read_bytes()
            ).hexdigest(),
            "provisional_study_review_sha256": hashlib.sha256(
                studies_path.read_bytes()
            ).hexdigest(),
        },
    }))
    protocol = {
        "metadata_only": True,
        "expression_values_read": False,
        "external_lockbox_frozen": False,
        "source_contract": {
            "expected_sample_rows": 5,
            "expected_study_rows": 5,
            "expected_groups_per_organ": 1,
            "expected_provisional_sample_review_sha256": hashlib.sha256(
                samples_path.read_bytes()
            ).hexdigest(),
            "expected_provisional_study_review_sha256": hashlib.sha256(
                studies_path.read_bytes()
            ).hexdigest(),
        },
        "donor_key_contract": {
            "default_basis": "title proxy",
            "explicit_characteristic_overrides": [],
            "conservative_single_sample_groups": [],
            "cross_group_explicit_identifier_fields": ["donor_id"],
        },
        "analysis_unit_contract": {"primary_unit": "connected_study_group"},
        "power_sensitivity_contract": {
            "exact_sign_test_clusters": 5,
            "one_sided_alpha": 0.1,
            "positive_study_probability_grid": [0.7],
            "warning": "design only",
        },
        "readiness_rules": {
            "minimum_groups_per_organ": 1,
            "minimum_total_study_groups": 5,
        },
        "next_gate": "draft protocol",
    }
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(json.dumps(protocol))
    return samples_path, studies_path, report_path, protocol_path


def test_build_donor_power_audit_never_authorizes_expression(tmp_path):
    samples, studies, report, protocol = _write_fixture(tmp_path)
    args = argparse.Namespace(
        samples=str(samples),
        studies=str(studies),
        source_report=str(report),
        protocol=str(protocol),
        expected_protocol_sha256=hashlib.sha256(
            protocol.read_bytes()
        ).hexdigest(),
        code_commit="a" * 40,
        output_dir=str(tmp_path / "output"),
    )
    result = build_donor_power_audit(args)
    assert result["ready_for_protocol_drafting"] is True
    assert result["ready_for_lockbox_freeze"] is False
    assert result["ready_for_expression_access"] is False
    assert result["expression_values_read"] is False


def test_build_donor_power_audit_rejects_cross_study_explicit_overlap(tmp_path):
    samples, studies, report, protocol = _write_fixture(tmp_path)
    table = pd.read_csv(samples)
    table.loc[0, "characteristics_ch1"] = "donor_id: SAME"
    table.loc[1, "characteristics_ch1"] = "donor_id: SAME"
    table.to_csv(samples, index=False)
    source = json.loads(report.read_text())
    source["hashes"]["provisional_sample_review_sha256"] = hashlib.sha256(
        samples.read_bytes()
    ).hexdigest()
    report.write_text(json.dumps(source))
    contract = json.loads(protocol.read_text())
    contract["source_contract"][
        "expected_provisional_sample_review_sha256"
    ] = hashlib.sha256(samples.read_bytes()).hexdigest()
    protocol.write_text(json.dumps(contract))
    args = argparse.Namespace(
        samples=str(samples),
        studies=str(studies),
        source_report=str(report),
        protocol=str(protocol),
        expected_protocol_sha256=hashlib.sha256(
            protocol.read_bytes()
        ).hexdigest(),
        code_commit="a" * 40,
        output_dir=str(tmp_path / "output"),
    )
    result = build_donor_power_audit(args)
    assert result["ready_for_protocol_drafting"] is False
    assert len(result["cross_group_explicit_identifier_overlaps"]) == 1
