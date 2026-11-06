#!/usr/bin/env python3
"""Aggregate the three frozen tissue-site Tier-2 seed reports without selection."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SEEDS = (17, 42, 101)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def aggregate(protocol_path: Path, result_root: Path) -> dict:
    protocol_sha256 = sha256_file(protocol_path)
    protocol = json.loads(protocol_path.read_text())
    if protocol.get("status") != "frozen_before_tissue_site_tier2_outcome_access":
        raise ValueError("tissue-site Tier-2 protocol is not frozen")
    if tuple(protocol["inputs"]["seeds"]) != SEEDS:
        raise ValueError("frozen seed family changed")

    reports = {}
    for seed in SEEDS:
        path = result_root / f"seed{seed}" / "tissue_site_tier2_report.json"
        report = json.loads(path.read_text())
        if int(report["seed"]) != seed:
            raise ValueError(f"seed report mismatch for {seed}")
        if report["protocol_sha256"] != protocol_sha256:
            raise ValueError(f"protocol hash mismatch for seed {seed}")
        reports[str(seed)] = report

    all_pass = all(report["all_gates_pass"] is True for report in reports.values())
    decision = protocol["decision"]["pass" if all_pass else "fail"]
    comparisons = {}
    for name in (
        "soft_site_vs_protected_base",
        "soft_site_vs_soft_shuffled_site",
        "soft_site_vs_generic_capacity_matched",
    ):
        comparisons[name] = {
            seed: reports[str(seed)]["pairwise"][name]
            for seed in SEEDS
        }
    failed_gates = {
        seed: sorted(
            name for name, passed in reports[str(seed)]["gates"].items() if not passed
        )
        for seed in SEEDS
    }
    return {
        "schema_version": 1,
        "status": "complete",
        "protocol_sha256": protocol_sha256,
        "seeds": list(SEEDS),
        "all_seeds_pass": all_pass,
        "decision": decision,
        "failed_gates_by_seed": failed_gates,
        "comparisons": comparisons,
        "seed_report_sha256": {
            str(seed): sha256_file(
                result_root / f"seed{seed}" / "tissue_site_tier2_report.json"
            )
            for seed in SEEDS
        },
        "best_seed_selection": False,
        "threshold_changes": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--result-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = aggregate(args.protocol, args.result_root)
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
