#!/usr/bin/env python3
"""Freeze exact K8 ARCHS4 membership and metadata strata before expression access."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

import pandas as pd


ORGANS = (
    "adipose",
    "brain",
    "colon",
    "heart",
    "liver",
    "lung",
    "skeletal_muscle",
    "skin",
)
REQUIRED_SAMPLE_COLUMNS = {
    "sample_id",
    "organ",
    "series_group_id",
    "submitted_after_v11_creation",
    "manual_sample_decision",
    "donor_resolution_status",
}
REQUIRED_STUDY_COLUMNS = {
    "organ",
    "series_group_id",
    "manual_study_decision",
    "manual_donor_audit",
    "manual_near_duplicate_audit",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bound_json(path: Path, expected: str, label: str) -> dict:
    if sha256_file(path) != expected:
        raise ValueError(f"{label} SHA256 mismatch")
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be a JSON object")
    return value


def _validate_source_hashes(protocol: dict, paths: dict[str, Path]) -> None:
    expected = protocol["source_contract"]
    for name, path in paths.items():
        key = f"{name}_sha256"
        if expected.get(key) != sha256_file(path):
            raise ValueError(f"source contract mismatch for {name}")


def freeze_lockbox(args: argparse.Namespace) -> dict:
    if re.fullmatch(r"[0-9a-f]{40}", args.code_commit) is None:
        raise ValueError("lockbox freeze requires a full code commit")
    protocol_path = Path(args.protocol)
    protocol = _bound_json(
        protocol_path, args.expected_protocol_sha256, "lockbox protocol"
    )
    if protocol.get("status") != "frozen_gtex_to_archs4_k8_lockbox_protocol":
        raise ValueError("unexpected lockbox protocol status")
    if protocol.get("archs4_expression_accessed") is not False:
        raise ValueError("lockbox protocol does not seal ARCHS4 expression")
    if protocol.get("fine_tuning", {}).get("archs4_exposure") != "zero":
        raise ValueError("first lockbox protocol must use zero ARCHS4 exposure")
    if protocol.get("candidate_policy", {}).get("best_seed_selection_allowed") is not False:
        raise ValueError("lockbox protocol allows best-seed selection")

    paths = {
        "candidate_ledger": Path(args.candidate_ledger),
        "sample_review": Path(args.sample_review),
        "study_review": Path(args.study_review),
        "sample_review_report": Path(args.sample_review_report),
        "donor_audit_samples": Path(args.donor_audit_samples),
        "donor_audit_studies": Path(args.donor_audit_studies),
        "donor_audit_report": Path(args.donor_audit_report),
    }
    for path in paths.values():
        if not path.is_file():
            raise FileNotFoundError(path)
    _validate_source_hashes(protocol, paths)

    ledger = json.loads(paths["candidate_ledger"].read_text())
    if (
        ledger.get("status") != "frozen_gtex_only_k8_candidate_ledger"
        or ledger.get("archs4_expression_accessed") is not False
        or ledger.get("archs4_efficacy_scored") is not False
        or ledger.get("seeds") != [17, 42, 101]
        or ledger.get("best_seed_selection_allowed") is not False
    ):
        raise ValueError("candidate ledger violates the pre-test contract")

    sample_report = json.loads(paths["sample_review_report"].read_text())
    donor_report = json.loads(paths["donor_audit_report"].read_text())
    if (
        sample_report.get("expression_values_read") is not False
        or sample_report.get("external_lockbox_frozen") is not False
        or sample_report.get("provisional_sample_rows") != 827
        or sample_report.get("provisional_group_rows") != 64
    ):
        raise ValueError("sample review does not match the frozen K8 source contract")
    checks = donor_report.get("readiness_checks", {})
    if (
        donor_report.get("expression_values_read") is not False
        or donor_report.get("ready_for_protocol_drafting") is not True
        or not checks
        or not all(checks.values())
        or donor_report.get("cross_group_explicit_identifier_overlaps") != []
    ):
        raise ValueError("donor audit did not pass every structural readiness check")

    samples = pd.read_csv(paths["sample_review"], keep_default_na=False)
    studies = pd.read_csv(paths["study_review"], keep_default_na=False)
    audited_samples = pd.read_csv(
        paths["donor_audit_samples"], keep_default_na=False
    )
    audited_studies = pd.read_csv(
        paths["donor_audit_studies"], keep_default_na=False
    )
    for label, frame, required in (
        ("sample review", samples, REQUIRED_SAMPLE_COLUMNS),
        ("study review", studies, REQUIRED_STUDY_COLUMNS),
    ):
        missing = sorted(required - set(frame.columns))
        if missing:
            raise KeyError(f"{label} lacks required columns: {missing}")
    if len(samples) != 827 or len(studies) != 64:
        raise ValueError("unexpected K8 review row count")
    if samples["sample_id"].duplicated().any():
        raise ValueError("sample review repeats accessions")
    if not samples["submitted_after_v11_creation"].astype(bool).all():
        raise ValueError("pre-firewall sample reached lockbox freeze")
    if set(samples["manual_sample_decision"]) != {"pending"}:
        raise ValueError("source sample decisions changed before protocol signoff")
    if set(studies["manual_study_decision"]) != {"pending"}:
        raise ValueError("source study decisions changed before protocol signoff")
    group_counts = studies.groupby("organ").size().reindex(ORGANS, fill_value=0)
    if not group_counts.eq(8).all():
        raise ValueError(f"lockbox does not have eight groups per organ: {group_counts.to_dict()}")
    if set(samples["organ"]) != set(ORGANS):
        raise ValueError("sample review does not cover the frozen K8 organs")
    sample_groups = set(zip(samples["organ"], samples["series_group_id"]))
    study_groups = set(zip(studies["organ"], studies["series_group_id"]))
    if sample_groups != study_groups:
        raise ValueError("sample/study group membership differs")
    if set(audited_samples["sample_id"]) != set(samples["sample_id"]):
        raise ValueError("donor audit sample membership differs")
    if set(zip(audited_studies["organ"], audited_studies["series_group_id"])) != study_groups:
        raise ValueError("donor audit study membership differs")
    if audited_samples["derived_donor_key"].duplicated().any():
        raise ValueError("donor audit contains duplicate within-group donor keys")

    signoff = protocol.get("metadata_signoff", {})
    if (
        signoff.get("decision") != "accept_exact_membership_with_title_proxy_limit"
        or signoff.get("title_proxy_is_verified_donor_identity") is not False
        or signoff.get("primary_power_unit") != "connected_study_group"
        or signoff.get("silent_exclusion_or_relabeling_allowed") is not False
    ):
        raise ValueError("metadata signoff is absent or overclaims donor verification")

    stratum_overrides = protocol.get("strata", {}).get(
        "series_group_overrides", {}
    )
    unknown_overrides = sorted(set(stratum_overrides) - set(studies["series_group_id"]))
    if unknown_overrides:
        raise ValueError(f"stratum overrides reference unknown groups: {unknown_overrides}")
    default_stratum = protocol.get("strata", {}).get("default", "reference_control")
    samples["split"] = "test"
    samples["analysis_role"] = "lockbox"
    samples["reference_stratum"] = samples["series_group_id"].map(
        lambda group: stratum_overrides.get(group, default_stratum)
    )
    samples["metadata_review_decision"] = "accept_frozen"
    samples["donor_identity_limit"] = "title_proxy_unless_explicit_identifier"
    samples["balanced_train"] = False
    studies["split"] = "test"
    studies["analysis_role"] = "lockbox"
    studies["reference_stratum"] = studies["series_group_id"].map(
        lambda group: stratum_overrides.get(group, default_stratum)
    )
    studies["metadata_review_decision"] = "accept_frozen"
    studies["donor_identity_limit"] = "title_proxy_unless_explicit_identifier"

    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise FileExistsError(output_dir)
    output_dir.mkdir(parents=True)
    manifest_path = output_dir / "lockbox_manifest.csv"
    studies_path = output_dir / "lockbox_studies.csv"
    samples.to_csv(manifest_path, index=False)
    studies.to_csv(studies_path, index=False)
    report = {
        "schema_version": 1,
        "status": "frozen_gtex_to_archs4_k8_lockbox_membership",
        "code_commit": args.code_commit,
        "protocol_sha256": sha256_file(protocol_path),
        "candidate_ledger_sha256": sha256_file(paths["candidate_ledger"]),
        "metadata_only": True,
        "archs4_expression_accessed": False,
        "efficacy_scoring_performed": False,
        "external_lockbox_frozen": True,
        "ready_for_expression_access": bool(
            protocol.get("expression_access_gate", {}).get(
                "all_implementation_hashes_frozen", False
            )
        ),
        "fine_tuning_exposure": "zero",
        "best_seed_selection_allowed": False,
        "sample_rows": int(len(samples)),
        "study_groups": int(len(studies)),
        "study_groups_per_organ": {
            organ: int(group_counts[organ]) for organ in ORGANS
        },
        "reference_stratum_counts": {
            str(key): int(value)
            for key, value in studies["reference_stratum"].value_counts().sort_index().items()
        },
        "donor_identity_limit": signoff.get("limitation"),
        "hashes": {
            "lockbox_manifest_sha256": sha256_file(manifest_path),
            "lockbox_studies_sha256": sha256_file(studies_path),
            **{
                f"source_{name}_sha256": sha256_file(path)
                for name, path in paths.items()
            },
        },
        "next_gate": (
            "Run the one-time launcher only if ready_for_expression_access is true "
            "and every implementation/candidate/source hash still matches."
        ),
    }
    report_path = output_dir / "lockbox_freeze_report.json"
    temporary = report_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, report_path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--candidate-ledger", required=True)
    parser.add_argument("--sample-review", required=True)
    parser.add_argument("--study-review", required=True)
    parser.add_argument("--sample-review-report", required=True)
    parser.add_argument("--donor-audit-samples", required=True)
    parser.add_argument("--donor-audit-studies", required=True)
    parser.add_argument("--donor-audit-report", required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--output-dir", required=True)
    print(json.dumps(freeze_lockbox(parser.parse_args()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
