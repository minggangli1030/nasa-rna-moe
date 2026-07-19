#!/usr/bin/env python3
"""Fail unless a Stage 1 smoke report is structurally and numerically healthy."""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path


REQUIRED_VALIDATION = (
    "leakage_free",
    "random_shard_count_matches_organs",
    "mask_hash_verified",
    "prediction_masks_match_cache",
    "sample_hash_verified",
    "gene_hash_verified",
)
REQUIRED_CONDITIONS = (
    "pooled", "organ_fixed", "true_organ_hard", "blind_organ_hard",
    "blind_organ_soft", "hard_oracle", "soft_oracle", "random_fixed",
    "random_soft_oracle", "calibration_best_random_by_true_organ",
    "organ_gene_mean",
)
REQUIRED_COMPARISONS = (
    "pooled_vs_gene_mean", "true_organ_hard_vs_pooled",
    "organ_fixed_vs_random_fixed", "blind_hard_vs_pooled",
    "blind_soft_vs_organ_fixed", "soft_oracle_vs_organ_fixed",
    "true_organ_hard_vs_calibration_best_random_by_organ",
)


def _finite_tree(value) -> bool:
    if isinstance(value, dict):
        return all(_finite_tree(item) for item in value.values())
    if isinstance(value, list):
        return all(_finite_tree(item) for item in value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return math.isfinite(float(value))
    return True


def check(report: dict) -> dict:
    issues: list[str] = []
    validation = report.get("validation", {})
    for field in REQUIRED_VALIDATION:
        if validation.get(field) is not True:
            issues.append(f"validation.{field} is not true")
    router = report.get("router", {})
    if router.get("uses_reconstruction_targets") is not False:
        issues.append("router target-hiding assertion failed")
    if router.get("uses_test_labels_or_targets_for_fit") is not False:
        issues.append("router test-isolation assertion failed")
    direct_control = report.get("exploratory_random_controls", {})
    if direct_control.get("gating") is not False:
        issues.append("direct random control must be explicitly non-gating")
    if direct_control.get("selection_split") != report.get("splits", {}).get("calibration"):
        issues.append("direct random control was not selected on calibration")
    if direct_control.get("uses_test_targets_for_selection") is not False:
        issues.append("direct random control test-target isolation failed")
    if direct_control.get("uses_test_organ_for_routing") is not True:
        issues.append("direct random control must declare true-organ routing")
    conditions = report.get("conditions", {})
    comparisons = report.get("comparisons", {})
    for name in REQUIRED_CONDITIONS:
        if name not in conditions:
            issues.append(f"missing condition {name}")
    for name in REQUIRED_COMPARISONS:
        if name not in comparisons:
            issues.append(f"missing comparison {name}")
    for name, condition in conditions.items():
        mse = condition.get("primary_balanced_organ_study_macro", {}).get("mse")
        if not isinstance(mse, (int, float)) or not math.isfinite(float(mse)):
            issues.append(f"condition {name} lacks finite primary MSE")
    for name, comparison in comparisons.items():
        primary = comparison.get("primary", {})
        for field in (
            "candidate_mse", "reference_mse", "mse_improvement_mean",
            "relative_mse_reduction",
        ):
            value = primary.get(field)
            if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                issues.append(f"comparison {name} lacks finite {field}")
    organs = report.get("models", {}).get("organ_expert_order", [])
    randoms = report.get("models", {}).get("random_expert_order", [])
    if len(organs) < 2 or len(randoms) != len(organs):
        issues.append("organ/random expert counts are invalid")
    splits = report.get("splits", {})
    for field in ("n_train", "n_calibration", "n_test", "n_test_groups"):
        if int(splits.get(field, 0)) <= 0:
            issues.append(f"splits.{field} is not positive")
    return {
        "schema_version": 1,
        "status": "pass" if not issues else "fail",
        "mechanical_only": True,
        "biological_evidence": False,
        "issues": issues,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = check(json.loads(Path(args.report).read_text()))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, output)
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
