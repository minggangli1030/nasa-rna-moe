#!/usr/bin/env python3
"""Apply the frozen multiaxis Tier-1 gates across all seeds and OSDR."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def evaluate_axis(
    axis: str,
    reports: list[dict],
    osdr_report: dict,
    *,
    maximum_harm: float,
) -> dict:
    per_seed = []
    for report in reports:
        result = report["results"][axis]
        outcomes = result["outcomes"]
        primary = outcomes["post_private_coefficients"]
        protected = outcomes["protected_private_error"]
        minimum_protected = min(protected["per_organ_incremental_r2"].values())
        gates = {
            "coverage": bool(result["coverage"]["pass"]),
            "technical_proxy": bool(result["technical_proxy_pass"]),
            "all_outcomes_positive": all(
                outcome["incremental_r2"] > 0 for outcome in outcomes.values()
            ),
            "primary_above_permutation_p95": bool(
                primary["within_organ_permutation"]["real_above_p95"]
            ),
            "primary_bootstrap_lower_positive": bool(
                primary["donor_bootstrap"]["ci95"][0] > 0
            ),
            "per_organ_safety": bool(minimum_protected >= -maximum_harm),
        }
        per_seed.append(
            {
                "seed": int(report["seed"]),
                "gates": gates,
                "all_training_gates_pass": bool(all(gates.values())),
                "primary_incremental_r2": float(primary["incremental_r2"]),
                "primary_bootstrap_ci95": primary["donor_bootstrap"]["ci95"],
                "minimum_protected_per_organ_incremental_r2": float(
                    minimum_protected
                ),
                "maximum_absolute_technical_proxy_partial_correlation": float(
                    result["maximum_absolute_technical_proxy_partial_correlation"]
                ),
                "outcome_incremental_r2": {
                    name: float(value["incremental_r2"])
                    for name, value in outcomes.items()
                },
            }
        )
    downstream = osdr_report["results"][axis]
    downstream_pass = bool(downstream["positive_gate"])
    all_seed_training_pass = bool(
        all(item["all_training_gates_pass"] for item in per_seed)
    )
    return {
        "per_seed": per_seed,
        "all_seed_training_pass": all_seed_training_pass,
        "osdr_downstream_positive": downstream_pass,
        "osdr_auroc_minus_organ_base": float(
            downstream["auroc_minus_organ_base"]
        ),
        "osdr_study_bootstrap_ci95": downstream["study_bootstrap"]["ci95"],
        "mean_primary_incremental_r2": float(
            np.mean([item["primary_incremental_r2"] for item in per_seed])
        ),
        "tier1_pass": bool(all_seed_training_pass and downstream_pass),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--osdr-report", required=True)
    parser.add_argument("--seed-report", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    protocol_path = Path(args.protocol)
    if sha256_file(protocol_path) != args.expected_protocol_sha256:
        raise ValueError("Tier-1 protocol SHA256 mismatch")
    protocol = json.loads(protocol_path.read_text())
    if protocol.get("status") != "frozen_before_tier1_incremental_outcome_access":
        raise ValueError("Tier-1 protocol is not frozen")
    reports = [json.loads(Path(path).read_text()) for path in args.seed_report]
    expected_seeds = sorted(protocol["training_screen"]["seeds"])
    if sorted(int(report["seed"]) for report in reports) != expected_seeds:
        raise ValueError("seed report set differs from frozen protocol")
    if any(report.get("status") != "complete" for report in reports):
        raise ValueError("incomplete seed report")
    if any(
        report.get("protocol_sha256") != args.expected_protocol_sha256
        for report in reports
    ):
        raise ValueError("seed report protocol mismatch")
    osdr_path = Path(args.osdr_report)
    osdr_report = json.loads(osdr_path.read_text())
    if osdr_report.get("status") != "complete":
        raise ValueError("OSDR probe is incomplete")

    maximum_harm = float(
        protocol["training_screen"]["per_organ_safety"][
            "maximum_incremental_r2_harm"
        ]
    )
    axes = sorted(protocol["candidates"])
    results = {
        axis: evaluate_axis(
            axis, reports, osdr_report, maximum_harm=maximum_harm
        )
        for axis in axes
    }
    passing = [axis for axis in axes if results[axis]["tier1_pass"]]
    ranked = sorted(
        passing,
        key=lambda axis: (-results[axis]["mean_primary_incremental_r2"], axis),
    )
    maximum = int(
        protocol["advance_gate"]["maximum_axes_advancing_to_tier2"]
    )
    advanced = ranked[:maximum]
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise FileExistsError(output_dir)
    output_dir.mkdir(parents=True)
    report = {
        "schema_version": 1,
        "status": "complete",
        "role": "deterministic frozen multiaxis Tier-1 gate aggregation",
        "protocol_sha256": sha256_file(protocol_path),
        "input_sha256": {
            "osdr_report": sha256_file(osdr_path),
            "seed_reports": {
                str(report["seed"]): sha256_file(Path(path))
                for report, path in zip(reports, args.seed_report)
            },
        },
        "seeds": expected_seeds,
        "best_seed_selection": False,
        "maximum_axes_advancing_to_tier2": maximum,
        "ranking_rule": "descending mean all-seed primary post-private-coefficient incremental R2, then axis name",
        "results": results,
        "tier1_passing_axes": passing,
        "tier2_advanced_axes": advanced,
    }
    report_path = output_dir / "multiaxis_tier1_aggregate_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (output_dir / "IMMUTABLE_SHA256SUMS").write_text(
        f"{sha256_file(report_path)}  {report_path.name}\n"
    )
    (output_dir / "COMPLETE").write_text("complete\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
