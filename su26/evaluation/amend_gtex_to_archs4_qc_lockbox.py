#!/usr/bin/env python3
"""Create the exact post-access QC-amended ARCHS4 manifest without replacements."""

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


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_amendment(args: argparse.Namespace) -> dict:
    if re.fullmatch(r"[0-9a-f]{40}", args.code_commit) is None:
        raise ValueError("QC amendment requires a full implementation commit")
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise FileExistsError(output_dir)
    paths = {
        "parent_protocol": Path(args.parent_protocol),
        "parent_freeze_report": Path(args.parent_freeze_report),
        "parent_manifest": Path(args.parent_manifest),
        "qc_failure": Path(args.qc_failure_artifact),
        "approval": Path(args.approval),
    }
    for path in paths.values():
        if not path.is_file():
            raise FileNotFoundError(path)
    parent = json.loads(paths["parent_protocol"].read_text())
    freeze = json.loads(paths["parent_freeze_report"].read_text())
    failure = json.loads(paths["qc_failure"].read_text())
    approval = json.loads(paths["approval"].read_text())
    if (
        parent.get("status") != "frozen_gtex_to_archs4_k8_lockbox_protocol"
        or sha256_file(paths["parent_protocol"]) != failure.get("protocol_sha256")
        or freeze.get("hashes", {}).get("lockbox_manifest_sha256")
        != sha256_file(paths["parent_manifest"])
    ):
        raise ValueError("parent lockbox artifacts do not form one frozen attempt")
    if (
        failure.get("status") != "failed_closed_at_expression_qc"
        or failure.get("lockbox_samples_requested") != 827
        or failure.get("lockbox_samples_published") != 0
        or failure.get("scoring_started") is not False
        or failure.get("membership_changed") is not False
        or failure.get("qc_min_nonzero_genes") != 14000
    ):
        raise ValueError("QC failure is not the sealed zero-efficacy parent failure")
    if (
        approval.get("decision")
        != "proceed_with_versioned_qc_amended_external_evaluation"
        or approval.get("exclude_exact_qc_failures_only") is not True
        or approval.get("add_replacements") is not False
        or approval.get("lower_qc_threshold") is not False
        or approval.get("allow_tuning") is not False
        or approval.get("allow_best_seed_selection") is not False
    ):
        raise ValueError("user approval does not authorize the exact amendment")
    failures = failure.get("failed_samples", [])
    excluded_ids = [str(item["sample_id"]) for item in failures]
    if (
        len(excluded_ids) != 6
        or len(set(excluded_ids)) != 6
        or any(int(item["nonzero_genes"]) >= 14000 for item in failures)
    ):
        raise ValueError("failure artifact does not contain exactly six QC failures")
    manifest = pd.read_csv(paths["parent_manifest"], keep_default_na=False)
    if len(manifest) != 827 or manifest["sample_id"].duplicated().any():
        raise ValueError("parent manifest is not the frozen 827-row lockbox")
    if not set(excluded_ids).issubset(set(manifest["sample_id"].astype(str))):
        raise ValueError("QC exclusions are not all in the parent manifest")
    amended = manifest.loc[
        ~manifest["sample_id"].astype(str).isin(excluded_ids)
    ].copy()
    amended["qc_amendment_role"] = "retained_after_objective_pre_score_qc"
    if len(amended) != 821 or set(amended["organ"]) != set(ORGANS):
        raise ValueError("amendment must retain 821 rows and all eight organs")
    group_counts = (
        amended.groupby("organ")["series_group_id"]
        .nunique()
        .reindex(ORGANS, fill_value=0)
    )
    expected_groups = {
        organ: (7 if organ == "liver" else 8) for organ in ORGANS
    }
    if group_counts.to_dict() != expected_groups:
        raise ValueError(
            f"amended group counts differ from exact expectation: {group_counts.to_dict()}"
        )
    output_dir.mkdir(parents=True)
    manifest_path = output_dir / "qc_amended_manifest.csv"
    amended.to_csv(manifest_path, index=False)
    report = {
        "schema_version": 1,
        "status": "frozen_post_access_qc_amended_membership",
        "code_commit": args.code_commit,
        "evidence_label": "post_access_qc_amended_external_evaluation",
        "parent_protocol_sha256": sha256_file(paths["parent_protocol"]),
        "parent_freeze_report_sha256": sha256_file(paths["parent_freeze_report"]),
        "parent_manifest_sha256": sha256_file(paths["parent_manifest"]),
        "qc_failure_artifact_sha256": sha256_file(paths["qc_failure"]),
        "approval_sha256": sha256_file(paths["approval"]),
        "qc_threshold_unchanged": 14000,
        "excluded_sample_ids": excluded_ids,
        "excluded_samples": 6,
        "retained_samples": 821,
        "retained_study_groups": int(amended["series_group_id"].nunique()),
        "retained_study_groups_per_organ": {
            organ: int(group_counts[organ]) for organ in ORGANS
        },
        "all_eight_organs_retained": True,
        "replacement_samples_added": 0,
        "replacement_studies_added": 0,
        "efficacy_was_available_at_amendment": False,
        "fine_tuning_allowed": False,
        "best_seed_selection_allowed": False,
        "hashes": {
            "qc_amended_manifest_sha256": sha256_file(manifest_path),
        },
    }
    report_path = output_dir / "qc_amendment_report.json"
    temporary = report_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, report_path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent-protocol", required=True)
    parser.add_argument("--parent-freeze-report", required=True)
    parser.add_argument("--parent-manifest", required=True)
    parser.add_argument("--qc-failure-artifact", required=True)
    parser.add_argument("--approval", required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--output-dir", required=True)
    print(json.dumps(build_amendment(parser.parse_args()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
