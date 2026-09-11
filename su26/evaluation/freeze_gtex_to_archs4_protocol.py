#!/usr/bin/env python3
"""Create the final implementation-bound GTEx-to-ARCHS4 K8 protocol."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IMPLEMENTATIONS = {
    "protocol_freezer_sha256": Path(__file__).resolve(),
    "candidate_freezer_sha256": ROOT / "evaluation/freeze_gtex_to_archs4_candidates.py",
    "random_control_freezer_sha256": ROOT / "evaluation/freeze_gtex_to_archs4_random_controls.py",
    "lockbox_membership_freezer_sha256": ROOT / "evaluation/freeze_gtex_to_archs4_lockbox.py",
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


def freeze_protocol(args: argparse.Namespace) -> dict:
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(output)
    if re.fullmatch(r"[0-9a-f]{40}", args.code_commit) is None:
        raise ValueError("protocol freeze requires a full implementation commit")
    sources = {
        "candidate_ledger": Path(args.candidate_ledger),
        "random_mappings": Path(args.random_mappings),
        "sample_review": Path(args.sample_review),
        "study_review": Path(args.study_review),
        "sample_review_report": Path(args.sample_review_report),
        "donor_audit_samples": Path(args.donor_audit_samples),
        "donor_audit_studies": Path(args.donor_audit_studies),
        "donor_audit_report": Path(args.donor_audit_report),
    }
    for path in (*sources.values(), *IMPLEMENTATIONS.values()):
        if not path.is_file():
            raise FileNotFoundError(path)
    ledger = json.loads(sources["candidate_ledger"].read_text())
    mappings = json.loads(sources["random_mappings"].read_text())
    if (
        ledger.get("archs4_expression_accessed") is not False
        or ledger.get("archs4_efficacy_scored") is not False
        or ledger.get("best_seed_selection_allowed") is not False
        or ledger.get("seeds") != [17, 42, 101]
    ):
        raise ValueError("candidate ledger is not eligible for protocol freeze")
    if (
        mappings.get("archs4_expression_accessed") is not False
        or mappings.get("candidate_ledger_sha256")
        != sha256_file(sources["candidate_ledger"])
    ):
        raise ValueError("random mappings are not eligible for protocol freeze")
    h5 = Path(args.human_h5)
    if not h5.is_file():
        raise FileNotFoundError(h5)
    source_contract = {
        f"{name}_sha256": sha256_file(path) for name, path in sources.items()
    }
    protocol = {
        "schema_version": 1,
        "status": "frozen_gtex_to_archs4_k8_lockbox_protocol",
        "implementation_commit": args.code_commit,
        "archs4_expression_accessed": False,
        "efficacy_scoring_performed": False,
        "source_contract": source_contract,
        "implementation_hashes": {
            name: sha256_file(path) for name, path in IMPLEMENTATIONS.items()
        },
        "candidate_policy": {
            "seeds": [17, 42, 101],
            "all_prespecified_seeds_required": True,
            "best_seed_selection_allowed": False,
            "candidate_ledger_sha256": source_contract[
                "candidate_ledger_sha256"
            ],
            "random_control_mappings_sha256": source_contract[
                "random_mappings_sha256"
            ],
        },
        "fine_tuning": {
            "archs4_exposure": "zero",
            "post_access_training_allowed": False,
            "post_access_checkpoint_selection_allowed": False,
        },
        "metadata_signoff": {
            "decision": "accept_exact_membership_with_title_proxy_limit",
            "title_proxy_is_verified_donor_identity": False,
            "primary_power_unit": "connected_study_group",
            "silent_exclusion_or_relabeling_allowed": False,
            "limitation": (
                "No explicit cross-study identifier overlap was found; title-derived "
                "donor keys remain a bounded proxy and are not verified identities."
            ),
        },
        "strata": {
            "default": "reference_control",
            "series_group_overrides": {},
            "primary_estimator": "equal organ then equal connected study",
            "exploratory_by_organ": True,
        },
        "evaluation": {
            "primary_metric": "masked log1p(TPM) MSE",
            "primary_estimand": "equal-organ equal-connected-study mean",
            "uncertainty": "paired connected-study bootstrap within organ",
            "one_sided_diagnostic": True,
            "router_conditions": ["true_organ", "blind_router_hard", "blind_router_soft"],
            "random_control_axes": [
                "random_k8_p17",
                "random_k8_p42",
                "random_k8_p101",
            ],
        },
        "expression_access_gate": {
            "all_implementation_hashes_frozen": True,
            "one_time_access_only": True,
            "membership_changes_after_access_allowed": False,
            "automatic_run_after_preflight": True,
            "pause_only_on_integrity_or_scientific_contract_failure": True,
        },
        "archs4_source": {
            "path_is_runtime_configuration": True,
            "size_bytes": int(h5.stat().st_size),
            "sha256": args.human_h5_sha256 or None,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, output)
    return protocol


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-ledger", required=True)
    parser.add_argument("--random-mappings", required=True)
    parser.add_argument("--sample-review", required=True)
    parser.add_argument("--study-review", required=True)
    parser.add_argument("--sample-review-report", required=True)
    parser.add_argument("--donor-audit-samples", required=True)
    parser.add_argument("--donor-audit-studies", required=True)
    parser.add_argument("--donor-audit-report", required=True)
    parser.add_argument("--human-h5", required=True)
    parser.add_argument("--human-h5-sha256")
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--output", required=True)
    print(json.dumps(freeze_protocol(parser.parse_args()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
