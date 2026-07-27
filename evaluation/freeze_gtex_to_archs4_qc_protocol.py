#!/usr/bin/env python3
"""Freeze the versioned post-access QC-amended ARCHS4 evaluation protocol."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IMPLEMENTATIONS = {
    "qc_protocol_freezer_sha256": Path(__file__).resolve(),
    "qc_membership_amender_sha256": ROOT / "evaluation/amend_gtex_to_archs4_qc_lockbox.py",
    "lockbox_extractor_wrapper_sha256": ROOT / "evaluation/extract_gtex_to_archs4_lockbox.py",
    "manifest_expression_core_sha256": ROOT / "preprocessing/extract_manifest_expression.py",
    "lockbox_score_cache_sha256": ROOT / "evaluation/cache_gtex_to_archs4_lockbox_scores.py",
    "lockbox_evaluator_sha256": ROOT / "evaluation/evaluate_gtex_to_archs4_lockbox.py",
    "one_time_launcher_sha256": ROOT / "runs/launch_gtex_to_archs4_lockbox.py",
}


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def freeze_qc_protocol(args: argparse.Namespace) -> dict:
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(output)
    if re.fullmatch(r"[0-9a-f]{40}", args.code_commit) is None:
        raise ValueError("QC protocol requires a full implementation commit")
    paths = {
        "parent_protocol": Path(args.parent_protocol),
        "qc_failure": Path(args.qc_failure_artifact),
        "approval": Path(args.approval),
        "candidate_ledger": Path(args.candidate_ledger),
        "random_mappings": Path(args.random_mappings),
        "amended_manifest": Path(args.amended_manifest),
        "amendment_report": Path(args.amendment_report),
        "human_h5": Path(args.human_h5),
    }
    for path in (*paths.values(), *IMPLEMENTATIONS.values()):
        if not path.is_file():
            raise FileNotFoundError(path)
    parent = json.loads(paths["parent_protocol"].read_text())
    failure = json.loads(paths["qc_failure"].read_text())
    approval = json.loads(paths["approval"].read_text())
    amendment = json.loads(paths["amendment_report"].read_text())
    if (
        parent.get("status") != "frozen_gtex_to_archs4_k8_lockbox_protocol"
        or failure.get("protocol_sha256") != sha256_file(paths["parent_protocol"])
        or failure.get("scoring_started") is not False
        or failure.get("lockbox_samples_published") != 0
    ):
        raise ValueError("parent attempt is not an efficacy-blind QC failure")
    if (
        amendment.get("status") != "frozen_post_access_qc_amended_membership"
        or amendment.get("parent_protocol_sha256")
        != sha256_file(paths["parent_protocol"])
        or amendment.get("qc_failure_artifact_sha256")
        != sha256_file(paths["qc_failure"])
        or amendment.get("approval_sha256") != sha256_file(paths["approval"])
        or amendment.get("hashes", {}).get("qc_amended_manifest_sha256")
        != sha256_file(paths["amended_manifest"])
        or amendment.get("retained_samples") != 821
        or amendment.get("retained_study_groups") != 63
    ):
        raise ValueError("QC amendment artifacts violate the authorized contract")
    if (
        approval.get("user_authorized") is not True
        or approval.get("exclude_exact_qc_failures_only") is not True
        or approval.get("add_replacements") is not False
        or approval.get("lower_qc_threshold") is not False
    ):
        raise ValueError("QC amendment lacks exact user authorization")
    h5 = paths["human_h5"]
    if (
        int(h5.stat().st_size) != int(parent["archs4_source"]["size_bytes"])
        or args.human_h5_sha256 != parent["archs4_source"]["sha256"]
    ):
        raise ValueError("QC amendment must use the identical frozen H5")
    protocol = {
        "schema_version": 1,
        "status": "frozen_gtex_to_archs4_k8_qc_amended_protocol",
        "evidence_label": "post_access_qc_amended_external_evaluation",
        "implementation_commit": args.code_commit,
        "archs4_expression_accessed_pre_amendment": True,
        "efficacy_scoring_performed_pre_amendment": False,
        "implementation_hashes": {
            name: sha256_file(path) for name, path in IMPLEMENTATIONS.items()
        },
        "source_contract": {
            "candidate_ledger_sha256": sha256_file(paths["candidate_ledger"]),
            "random_mappings_sha256": sha256_file(paths["random_mappings"]),
            "parent_protocol_sha256": sha256_file(paths["parent_protocol"]),
            "qc_failure_sha256": sha256_file(paths["qc_failure"]),
            "approval_sha256": sha256_file(paths["approval"]),
            "amended_manifest_sha256": sha256_file(paths["amended_manifest"]),
            "amendment_report_sha256": sha256_file(paths["amendment_report"]),
        },
        "candidate_policy": {
            "seeds": [17, 42, 101],
            "all_prespecified_seeds_required": True,
            "best_seed_selection_allowed": False,
        },
        "qc_amendment": {
            "threshold_nonzero_genes": 14000,
            "threshold_changed": False,
            "excluded_sample_ids": amendment["excluded_sample_ids"],
            "excluded_samples": 6,
            "retained_samples": 821,
            "retained_study_groups": 63,
            "retained_study_groups_per_organ": amendment[
                "retained_study_groups_per_organ"
            ],
            "all_eight_organs_retained": True,
            "replacement_samples_added": 0,
            "replacement_studies_added": 0,
            "efficacy_available_when_amended": False,
        },
        "fine_tuning": {
            "archs4_exposure": "zero",
            "post_access_training_allowed": False,
            "post_access_checkpoint_selection_allowed": False,
        },
        "evaluation": {
            "primary_metric": "masked log1p(TPM) MSE",
            "primary_estimand": "equal-organ equal-connected-study mean",
            "uncertainty": "paired connected-study bootstrap within organ",
            "organs": [
                "adipose",
                "brain",
                "colon",
                "heart",
                "liver",
                "lung",
                "skeletal_muscle",
                "skin",
            ],
            "unequal_study_counts_allowed_as_frozen": True,
        },
        "expression_access_gate": {
            "all_implementation_hashes_frozen": True,
            "repeat_mechanical_extraction_authorized": True,
            "only_exact_qc_exclusions_allowed": True,
            "further_membership_changes_allowed": False,
        },
        "archs4_source": {
            "size_bytes": int(h5.stat().st_size),
            "sha256": args.human_h5_sha256,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, output)
    return protocol


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent-protocol", required=True)
    parser.add_argument("--qc-failure-artifact", required=True)
    parser.add_argument("--approval", required=True)
    parser.add_argument("--candidate-ledger", required=True)
    parser.add_argument("--random-mappings", required=True)
    parser.add_argument("--amended-manifest", required=True)
    parser.add_argument("--amendment-report", required=True)
    parser.add_argument("--human-h5", required=True)
    parser.add_argument("--human-h5-sha256", required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--output", required=True)
    print(json.dumps(freeze_qc_protocol(parser.parse_args()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
