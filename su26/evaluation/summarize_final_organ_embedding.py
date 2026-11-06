#!/usr/bin/env python3
"""Apply the frozen all-seed gate to the final organ-embedding development run."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SEEDS = (17, 42, 101)
DEPLOYABLE = (
    "pooled_hidden_plus_router",
    "blind_router_hard_embedding",
    "blind_router_soft_embedding",
)
REPORTABLE = (
    "pooled_hidden",
    "pooled_hidden_plus_router",
    "pooled_hidden_plus_organ_label",
    "true_organ_embedding",
    "blind_router_hard_embedding",
    "blind_router_soft_embedding",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def summarize(protocol_path: Path, report_path: Path) -> dict:
    protocol = json.loads(protocol_path.read_text())
    report = json.loads(report_path.read_text())
    if protocol.get("status") != "frozen_before_final_organ_embedding_development_outcome_access":
        raise ValueError("embedding protocol is not frozen")
    if report.get("status") != "complete" or report.get("smoke") is not False:
        raise ValueError("full embedding evaluation is incomplete")
    protocol_sha256 = sha256_file(protocol_path)
    if report.get("protocol_sha256") != protocol_sha256:
        raise ValueError("evaluation protocol hash mismatch")
    results = report["results"]
    raw = float(results["raw_expression"]["pooled_out_of_fold"]["auroc"])
    pca = float(results["pca_64"]["pooled_out_of_fold"]["auroc"])
    auroc = {name: {} for name in REPORTABLE}
    for name in REPORTABLE:
        for seed in SEEDS:
            auroc[name][str(seed)] = float(
                results[f"seed{seed}__{name}"]["pooled_out_of_fold"]["auroc"]
            )
    gates = {}
    for name in DEPLOYABLE:
        comparisons = {}
        passed = True
        for seed in SEEDS:
            candidate = auroc[name][str(seed)]
            pooled = auroc["pooled_hidden"][str(seed)]
            item = {
                "candidate_auroc": candidate,
                "minus_pooled_hidden": candidate - pooled,
                "minus_raw_expression": candidate - raw,
                "minus_pca_64": candidate - pca,
                "beats_all_references": candidate > pooled and candidate > raw and candidate > pca,
            }
            comparisons[str(seed)] = item
            passed = passed and item["beats_all_references"]
        gates[name] = {"all_seed_gate_pass": passed, "by_seed": comparisons}
    any_pass = any(item["all_seed_gate_pass"] for item in gates.values())
    return {
        "schema_version": 1,
        "status": "complete",
        "role": "accessed_cross_species_downstream_development",
        "protocol_sha256": protocol_sha256,
        "evaluation_report_sha256": sha256_file(report_path),
        "raw_expression_auroc": raw,
        "pca_64_auroc": pca,
        "auroc": auroc,
        "deployable_gates": gates,
        "any_deployable_embedding_passes": any_pass,
        "decision": (
            "carry_fixed_blind_embedding_to_prospective_confirmation"
            if any_pass
            else "no_downstream_positive_embedding_retain_reconstruction_model_and_raw_pca_gates"
        ),
        "best_seed_selection": False,
        "post_hoc_condition_selection": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--evaluation-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = summarize(args.protocol, args.evaluation_report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
