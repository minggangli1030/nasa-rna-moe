from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from evaluation.freeze_gtex_to_archs4_lockbox import ORGANS, freeze_lockbox


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path) -> argparse.Namespace:
    groups = [
        (organ, f"{organ}-g{index}")
        for organ in ORGANS
        for index in range(8)
    ]
    samples = pd.DataFrame([
        {
            "sample_id": f"S{index}",
            "organ": organ,
            "series_group_id": group,
            "submitted_after_v11_creation": True,
            "manual_sample_decision": "pending",
            "donor_resolution_status": "title_proxy",
            "derived_donor_key": f"{organ}|{group}|S{index}",
        }
        for index, (organ, group) in enumerate(
            groups[index % len(groups)] for index in range(827)
        )
    ])
    studies = pd.DataFrame([
        {
            "organ": organ,
            "series_group_id": group,
            "manual_study_decision": "pending",
            "manual_donor_audit": "pending",
            "manual_near_duplicate_audit": "pending",
        }
        for organ, group in groups
    ])
    paths = {
        "sample_review": tmp_path / "samples.csv",
        "study_review": tmp_path / "studies.csv",
        "sample_review_report": tmp_path / "sample_report.json",
        "donor_audit_samples": tmp_path / "audited_samples.csv",
        "donor_audit_studies": tmp_path / "audited_studies.csv",
        "donor_audit_report": tmp_path / "donor_report.json",
        "candidate_ledger": tmp_path / "ledger.json",
    }
    samples.drop(columns="derived_donor_key").to_csv(
        paths["sample_review"], index=False
    )
    studies.to_csv(paths["study_review"], index=False)
    samples.to_csv(paths["donor_audit_samples"], index=False)
    studies.to_csv(paths["donor_audit_studies"], index=False)
    paths["sample_review_report"].write_text(json.dumps({
        "expression_values_read": False,
        "external_lockbox_frozen": False,
        "provisional_sample_rows": 827,
        "provisional_group_rows": 64,
    }))
    paths["donor_audit_report"].write_text(json.dumps({
        "expression_values_read": False,
        "ready_for_protocol_drafting": True,
        "readiness_checks": {"a": True, "b": True},
        "cross_group_explicit_identifier_overlaps": [],
    }))
    paths["candidate_ledger"].write_text(json.dumps({
        "status": "frozen_gtex_only_k8_candidate_ledger",
        "archs4_expression_accessed": False,
        "archs4_efficacy_scored": False,
        "seeds": [17, 42, 101],
        "best_seed_selection_allowed": False,
    }))
    protocol = {
        "status": "frozen_gtex_to_archs4_k8_lockbox_protocol",
        "archs4_expression_accessed": False,
        "fine_tuning": {"archs4_exposure": "zero"},
        "candidate_policy": {"best_seed_selection_allowed": False},
        "metadata_signoff": {
            "decision": "accept_exact_membership_with_title_proxy_limit",
            "title_proxy_is_verified_donor_identity": False,
            "primary_power_unit": "connected_study_group",
            "silent_exclusion_or_relabeling_allowed": False,
            "limitation": "synthetic title-proxy limit",
        },
        "strata": {"default": "reference_control", "series_group_overrides": {}},
        "expression_access_gate": {"all_implementation_hashes_frozen": True},
        "source_contract": {
            f"{name}_sha256": _sha(path) for name, path in paths.items()
        },
    }
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(json.dumps(protocol))
    return argparse.Namespace(
        protocol=str(protocol_path),
        expected_protocol_sha256=_sha(protocol_path),
        code_commit="a" * 40,
        output_dir=str(tmp_path / "output"),
        **{name: str(path) for name, path in paths.items()},
    )


def test_freeze_accepts_exact_membership_without_overclaiming_donors(
    tmp_path: Path,
) -> None:
    args = _fixture(tmp_path)
    result = freeze_lockbox(args)
    assert result["external_lockbox_frozen"] is True
    assert result["ready_for_expression_access"] is True
    manifest = pd.read_csv(tmp_path / "output/lockbox_manifest.csv")
    assert len(manifest) == 827
    assert set(manifest["split"]) == {"test"}
    assert set(manifest["metadata_review_decision"]) == {"accept_frozen"}
    assert set(manifest["donor_identity_limit"]) == {
        "title_proxy_unless_explicit_identifier"
    }


def test_freeze_rejects_pre_firewall_sample(tmp_path: Path) -> None:
    args = _fixture(tmp_path)
    samples_path = Path(args.sample_review)
    samples = pd.read_csv(samples_path)
    samples.loc[0, "submitted_after_v11_creation"] = False
    samples.to_csv(samples_path, index=False)
    protocol_path = Path(args.protocol)
    protocol = json.loads(protocol_path.read_text())
    protocol["source_contract"]["sample_review_sha256"] = _sha(samples_path)
    protocol_path.write_text(json.dumps(protocol))
    args.expected_protocol_sha256 = _sha(protocol_path)
    with pytest.raises(ValueError, match="pre-firewall"):
        freeze_lockbox(args)
