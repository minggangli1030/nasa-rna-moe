#!/usr/bin/env python3
"""Evaluate the single frozen GTEx score cache against prospective gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from stage1_k4_gtex_common import (
    ACTIVE_ORGANS,
    BOOTSTRAP_DRAWS,
    BOOTSTRAP_SEED,
    ORGANS,
    PARTITION_SEEDS,
    SEEDS,
    atomic_json,
    donor_bootstrap_comparison,
    donor_bootstrap_difference,
    donor_organ_means,
    equal_organ_mean,
    holm_adjust,
    load_frozen_protocol,
    sha256_file,
    sha256_lines,
)


def _condition_columns(condition: str, metric: str) -> list[str]:
    if condition == "pooled":
        return [f"pooled__{metric}"]
    return [f"seed{seed}__{condition}__{metric}" for seed in SEEDS]


def _average_condition(
    frame: pd.DataFrame, condition: str, metric: str, output_name: str
) -> None:
    columns = _condition_columns(condition, metric)
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"score cache lacks condition columns: {missing}")
    frame[output_name] = frame[columns].mean(axis=1)


def _comparison(
    frame: pd.DataFrame,
    control: str,
    candidate: str,
    *,
    bootstrap_seed: int,
) -> dict[str, Any]:
    donor = donor_organ_means(frame, [control, candidate])
    return donor_bootstrap_comparison(
        donor,
        control,
        candidate,
        draws=BOOTSTRAP_DRAWS,
        seed=bootstrap_seed,
    )


def _correlation_comparison(
    frame: pd.DataFrame,
    control: str,
    candidate: str,
    *,
    bootstrap_seed: int,
) -> dict[str, Any]:
    donor = donor_organ_means(frame, [control, candidate])
    return donor_bootstrap_difference(
        donor,
        candidate,
        control,
        draws=BOOTSTRAP_DRAWS,
        seed=bootstrap_seed,
    )


def _seed_diagnostics(frame: pd.DataFrame, condition: str) -> dict[str, Any]:
    per_seed: list[float] = []
    for seed in SEEDS:
        candidate = f"seed{seed}__{condition}__mse"
        donor = donor_organ_means(frame, ["pooled__mse", candidate])
        control_mean = equal_organ_mean(donor, "pooled__mse")
        candidate_mean = equal_organ_mean(donor, candidate)
        per_seed.append((control_mean - candidate_mean) / control_mean)
    mean = float(np.mean(per_seed))
    sd = float(np.std(per_seed, ddof=1))
    return {
        "relative_reduction_per_seed": per_seed,
        "mean": mean,
        "sample_sd": sd,
        "all_positive": bool(all(value > 0 for value in per_seed)),
        "sd_at_most_half_mean": bool(mean > 0 and sd <= 0.5 * mean),
    }


def _organ_effects(frame: pd.DataFrame) -> dict[str, Any]:
    donor = donor_organ_means(frame, ["pooled_mse", "true_mse"])
    output: dict[str, Any] = {}
    for organ in ACTIVE_ORGANS:
        subset = donor[donor["organ"].astype(str).eq(organ)]
        control = float(subset["pooled_mse"].mean())
        candidate = float(subset["true_mse"].mean())
        output[organ] = {
            "pooled_mse": control,
            "true_k4_mse": candidate,
            "relative_reduction": (control - candidate) / control,
            "nonnegative": candidate <= control,
        }
    return output


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    protocol = load_frozen_protocol(args.protocol, args.expected_protocol_sha256)
    score_dir = Path(args.score_dir)
    score_path = score_dir / "gtex_sample_scores.parquet"
    score_report_path = score_dir / "score_report.json"
    if not (score_dir / "SCORING_COMPLETE").is_file():
        raise ValueError("GTEx scoring is incomplete")
    score_report = json.loads(score_report_path.read_text())
    if (
        score_report.get("status") != "complete"
        or score_report.get("protocol_sha256") != sha256_file(args.protocol)
        or score_report.get("score_cache_sha256") != sha256_file(score_path)
        or score_report.get("full_predictions_serialized") is not False
    ):
        raise ValueError("GTEx score report is invalid")
    frame = pd.read_parquet(score_path)
    required_metadata = {
        "sample_id",
        "donor_id",
        "organ",
        "tissue_site",
        "router_predicted_organ",
        "router_correct",
    }
    missing = sorted(required_metadata - set(frame.columns))
    if missing:
        raise ValueError(f"GTEx score cache lacks metadata: {missing}")
    if frame["sample_id"].duplicated().any():
        raise ValueError("GTEx score cache repeats samples")
    if set(frame["organ"].astype(str)) != set(ORGANS):
        raise ValueError("GTEx score cache does not cover all organs")
    if sha256_lines(frame["sample_id"]) != score_report["sample_order_sha256"]:
        raise ValueError("GTEx score cache sample order changed")

    _average_condition(frame, "pooled", "mse", "pooled_mse")
    _average_condition(frame, "pooled", "residual_pearson", "pooled_corr")
    for condition, prefix in (
        ("true_k4", "true"),
        ("blind_k4", "blind"),
        ("pooled_adapter", "pooled_adapter"),
    ):
        _average_condition(frame, condition, "mse", f"{prefix}_mse")
        _average_condition(
            frame, condition, "residual_pearson", f"{prefix}_corr"
        )
    for partition in PARTITION_SEEDS:
        for dispatch in ("assigned", "mapped"):
            condition = f"random_p{partition}_{dispatch}"
            prefix = f"random_p{partition}_{dispatch}"
            _average_condition(frame, condition, "mse", f"{prefix}_mse")
            _average_condition(
                frame, condition, "residual_pearson", f"{prefix}_corr"
            )

    comparisons: dict[str, Any] = {}
    comparisons["true_vs_pooled"] = _comparison(
        frame, "pooled_mse", "true_mse", bootstrap_seed=BOOTSTRAP_SEED + 1
    )
    comparisons["blind_vs_pooled"] = _comparison(
        frame, "pooled_mse", "blind_mse", bootstrap_seed=BOOTSTRAP_SEED + 2
    )
    comparisons["blind_vs_pooled_adapter"] = _comparison(
        frame,
        "pooled_adapter_mse",
        "blind_mse",
        bootstrap_seed=BOOTSTRAP_SEED + 3,
    )
    correlations = {
        "true_vs_pooled": _correlation_comparison(
            frame, "pooled_corr", "true_corr", bootstrap_seed=BOOTSTRAP_SEED + 11
        ),
        "blind_vs_pooled": _correlation_comparison(
            frame, "pooled_corr", "blind_corr", bootstrap_seed=BOOTSTRAP_SEED + 12
        ),
    }
    for partition in PARTITION_SEEDS:
        comparisons[f"true_vs_random_p{partition}_assigned"] = _comparison(
            frame,
            f"random_p{partition}_assigned_mse",
            "true_mse",
            bootstrap_seed=BOOTSTRAP_SEED + 100 + partition,
        )
        comparisons[f"blind_vs_random_p{partition}_mapped"] = _comparison(
            frame,
            f"random_p{partition}_mapped_mse",
            "blind_mse",
            bootstrap_seed=BOOTSTRAP_SEED + 200 + partition,
        )

    true_random_p = {
        str(partition): comparisons[
            f"true_vs_random_p{partition}_assigned"
        ]["one_sided_p"]
        for partition in PARTITION_SEEDS
    }
    blind_random_p = {
        str(partition): comparisons[
            f"blind_vs_random_p{partition}_mapped"
        ]["one_sided_p"]
        for partition in PARTITION_SEEDS
    }
    true_holm = holm_adjust(true_random_p)
    blind_holm = holm_adjust(blind_random_p)
    for partition in PARTITION_SEEDS:
        comparisons[f"true_vs_random_p{partition}_assigned"][
            "holm_adjusted_p"
        ] = true_holm[str(partition)]
        comparisons[f"blind_vs_random_p{partition}_mapped"][
            "holm_adjusted_p"
        ] = blind_holm[str(partition)]

    router_accuracy = float(frame["router_correct"].astype(bool).mean())
    true_gain = comparisons["true_vs_pooled"]["absolute_improvement"]
    blind_gain = comparisons["blind_vs_pooled"]["absolute_improvement"]
    router_recovery = float(blind_gain / true_gain) if true_gain > 0 else float("-inf")
    seed_diagnostics = {
        "true_k4": _seed_diagnostics(frame, "true_k4"),
        "blind_k4": _seed_diagnostics(frame, "blind_k4"),
    }
    organ_effects = _organ_effects(frame)

    gates = {
        "true_vs_pooled": bool(
            comparisons["true_vs_pooled"]["relative_reduction"] >= 0.03
            and comparisons["true_vs_pooled"]["absolute_ci95"][0] > 0
        ),
        "blind_vs_pooled": bool(
            comparisons["blind_vs_pooled"]["relative_reduction"] >= 0.03
            and comparisons["blind_vs_pooled"]["absolute_ci95"][0] > 0
            and correlations["blind_vs_pooled"]["gain_ci95"][0] > 0
        ),
        "true_vs_all_assigned_random": bool(
            all(
                comparisons[f"true_vs_random_p{partition}_assigned"][
                    "relative_reduction"
                ]
                >= 0.03
                and comparisons[f"true_vs_random_p{partition}_assigned"][
                    "absolute_ci95"
                ][0]
                > 0
                and comparisons[f"true_vs_random_p{partition}_assigned"][
                    "holm_adjusted_p"
                ]
                <= 0.05
                for partition in PARTITION_SEEDS
            )
        ),
        "blind_vs_all_mapped_random": bool(
            all(
                comparisons[f"blind_vs_random_p{partition}_mapped"][
                    "relative_reduction"
                ]
                > 0
                and comparisons[f"blind_vs_random_p{partition}_mapped"][
                    "absolute_ci95"
                ][0]
                > 0
                and comparisons[f"blind_vs_random_p{partition}_mapped"][
                    "holm_adjusted_p"
                ]
                <= 0.05
                for partition in PARTITION_SEEDS
            )
        ),
        "blind_vs_pooled_adapter": bool(
            comparisons["blind_vs_pooled_adapter"]["absolute_ci95"][0] > 0
        ),
        "router_recovery": bool(router_recovery >= 0.80),
        "seed_stability": bool(
            all(
                item["all_positive"] and item["sd_at_most_half_mean"]
                for item in seed_diagnostics.values()
            )
        ),
        "active_organ_safety": bool(
            all(item["nonnegative"] for item in organ_effects.values())
        ),
    }
    if not gates["true_vs_pooled"]:
        decision = "no_external_gain"
    elif not (
        gates["true_vs_all_assigned_random"]
        and gates["blind_vs_all_mapped_random"]
        and gates["blind_vs_pooled_adapter"]
    ):
        decision = "generic_capacity_or_partition_fail"
    elif not (
        gates["blind_vs_pooled"]
        and gates["router_recovery"]
    ):
        decision = "router_bottleneck"
    elif all(gates.values()):
        decision = "full_external_pass"
    else:
        decision = "inconclusive"

    report = {
        "schema_version": 1,
        "status": "complete",
        "decision": decision,
        "evidence_role": protocol["evidence_role"],
        "claim_limit": protocol["claim_limit"],
        "protocol_sha256": sha256_file(args.protocol),
        "score_report_sha256": sha256_file(score_report_path),
        "score_cache_sha256": sha256_file(score_path),
        "samples": len(frame),
        "donors": int(frame["donor_id"].nunique()),
        "organ_counts": {
            organ: {
                "samples": int(frame["organ"].astype(str).eq(organ).sum()),
                "donors": int(
                    frame.loc[
                        frame["organ"].astype(str).eq(organ), "donor_id"
                    ].nunique()
                ),
            }
            for organ in ORGANS
        },
        "estimand": protocol["estimand"],
        "comparisons": comparisons,
        "residual_correlation_comparisons": correlations,
        "router": {
            "accuracy": router_accuracy,
            "gain_recovery_fraction": router_recovery,
        },
        "seed_diagnostics": seed_diagnostics,
        "active_organ_effects": organ_effects,
        "gates": gates,
        "all_gates_pass": bool(all(gates.values())),
        "bootstrap": {
            "draws": BOOTSTRAP_DRAWS,
            "base_seed": BOOTSTRAP_SEED,
            "unit": "global donor with cross-organ correlation preserved",
        },
    }
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    atomic_json(output_dir / "evaluation_report.json", report)
    (output_dir / "EVALUATION_COMPLETE").write_text(
        f"decision={decision}\nall_gates_pass={str(all(gates.values())).lower()}\n"
    )
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--score-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser


def main() -> None:
    print(json.dumps(evaluate(build_parser().parse_args()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
