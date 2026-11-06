#!/usr/bin/env python3
"""Apply the frozen Stage 1 organ-specialization decision boundary.

The input is one evaluator ``report.json`` per independently trained seed.  Study
uncertainty comes from each report's paired clustered interval; between-training-seed
uncertainty and the preregistered sign/SD checks are added here.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import t


SCHEMA_VERSION = 1
DEFAULT_THRESHOLDS = {
    "known_organ_relative_mse": 0.05,
    "oracle_relative_mse": 0.03,
    "organ_vs_random_relative_mse": 0.03,
    "blind_hard_relative_mse": 0.05,
    "blind_soft_relative_mse": 0.03,
    "blind_recovery": 0.80,
    "max_seed_sd_fraction": 0.50,
}


def _finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _seed_interval(values: np.ndarray) -> tuple[float, float]:
    mean = float(np.mean(values))
    if len(values) < 2 or np.allclose(values, values[0]):
        return mean, mean
    half_width = float(t.ppf(0.975, len(values) - 1) * np.std(values, ddof=1) / math.sqrt(len(values)))
    return mean - half_width, mean + half_width


def _aggregate_comparison(reports: list[dict], name: str) -> dict:
    primary = []
    for report in reports:
        try:
            primary.append(report["comparisons"][name]["primary"])
        except KeyError as exc:
            raise ValueError(f"report lacks comparison {name!r}") from exc

    def aggregate(metric: str, ci_metric: str) -> dict:
        values = np.asarray([item[metric] for item in primary], dtype=np.float64)
        study_lows = np.asarray([item[ci_metric][0] for item in primary], dtype=np.float64)
        study_highs = np.asarray([item[ci_metric][1] for item in primary], dtype=np.float64)
        if not np.all(np.isfinite(np.r_[values, study_lows, study_highs])):
            raise ValueError(f"{name}: non-finite {metric} or confidence interval")
        seed_low, seed_high = _seed_interval(values)
        mean = float(values.mean())
        seed_sd = float(values.std(ddof=1)) if len(values) > 1 else 0.0
        return {
            "mean": mean,
            "study_seed_ci95": [min(float(study_lows.mean()), seed_low),
                                max(float(study_highs.mean()), seed_high)],
            "per_seed": values.tolist(),
            "seed_sd": seed_sd,
            "same_positive_sign": bool(np.all(values > 0.0)),
            "same_negative_sign": bool(np.all(values < 0.0)),
            "seed_sd_fraction_of_mean": seed_sd / abs(mean) if abs(mean) > 1e-12 else float("inf"),
        }

    relative = np.asarray([item["relative_mse_reduction"] for item in primary], dtype=np.float64)
    if not np.all(np.isfinite(relative)):
        raise ValueError(f"{name}: non-finite relative MSE reduction")
    return {
        "mse": aggregate("mse_improvement_mean", "mse_improvement_ci95"),
        "residual_pearson": aggregate(
            "residual_pearson_gain_mean", "residual_pearson_gain_ci95"
        ),
        "relative_mse_reduction_mean": float(relative.mean()),
        "relative_mse_reduction_per_seed": relative.tolist(),
    }


def _aggregate_backbone(reports: list[dict], organ: str | None) -> dict:
    synthetic = []
    for report in reports:
        check = (
            report["backbone_checks"]["pooled_vs_gene_mean"]
            if organ is None
            else report["backbone_checks"]["by_organ"][organ]
        )
        synthetic.append({"comparisons": {"backbone": check}})
    return _aggregate_comparison(synthetic, "backbone")


def _effect_stable(aggregate: dict, threshold: float) -> bool:
    effect = aggregate["mse"]
    return bool(
        effect["same_positive_sign"]
        and effect["study_seed_ci95"][0] > 0.0
        and effect["seed_sd_fraction_of_mean"] < threshold
    )


def _effect_reproducible(aggregate: dict, threshold: float) -> bool:
    """Accept a stable nonzero sign; direction is judged by the downstream gate."""
    effect = aggregate["mse"]
    low, high = effect["study_seed_ci95"]
    same_sign = effect["same_positive_sign"] or effect["same_negative_sign"]
    excludes_zero = low > 0.0 or high < 0.0
    return bool(
        same_sign
        and excludes_zero
        and effect["seed_sd_fraction_of_mean"] < threshold
    )


def _mse_gate(aggregate: dict, relative: float, max_sd_fraction: float) -> bool:
    return bool(
        aggregate["relative_mse_reduction_mean"] >= relative
        and _effect_stable(aggregate, max_sd_fraction)
    )


def _mse_residual_gate(aggregate: dict, relative: float, max_sd_fraction: float) -> bool:
    residual = aggregate["residual_pearson"]
    return bool(
        _mse_gate(aggregate, relative, max_sd_fraction)
        and residual["same_positive_sign"]
        and residual["study_seed_ci95"][0] > 0.0
        and residual["seed_sd_fraction_of_mean"] < max_sd_fraction
    )


def _technical_audit(reports: list[dict], min_seeds: int) -> tuple[dict, list[str]]:
    reasons: list[str] = []
    seeds = [report.get("training_seed") for report in reports]
    if len(reports) < min_seeds:
        reasons.append(f"need at least {min_seeds} training-seed reports; received {len(reports)}")
    if len(set(seeds)) != len(seeds):
        reasons.append("training_seed values are not unique")

    fingerprint_fields = (
        "test_sample_id_sha256", "test_group_id_sha256", "test_organ_sha256",
        "mask_idx_sha256",
    )
    fingerprints = {
        field: {report.get("splits", {}).get(field) for report in reports}
        for field in fingerprint_fields
    }
    content_fields = (
        "sample_ids", "organs", "series_group_id", "split", "train_eligible",
        "random_shard", "genes", "expression", "mask_idx",
    )
    content_fingerprints = {
        field: {
            report.get("cache_metadata", {}).get("content_sha256", {}).get(field)
            for report in reports
        }
        for field in content_fields
    }
    for field, values in fingerprints.items():
        if None in values or len(values) != 1:
            reasons.append(f"seed reports disagree on {field}")
    for field, values in content_fingerprints.items():
        if None in values or len(values) != 1:
            reasons.append(f"seed reports disagree on cache input {field}")

    required_validation = (
        "leakage_free", "random_shard_count_matches_organs", "mask_hash_verified",
        "prediction_masks_match_cache", "sample_hash_verified", "gene_hash_verified",
    )
    for index, report in enumerate(reports):
        validation = report.get("validation", {})
        failed = [field for field in required_validation if validation.get(field) is not True]
        if failed:
            reasons.append(f"report {index} failed validation: {', '.join(failed)}")
        contract = report.get("cache_metadata", {}).get("value_space_contract", {})
        if report.get("cache_metadata", {}).get("value_space") != "log1p_tpm" or any(
            contract.get(field) != "log1p_tpm"
            for field in ("prediction_input", "cache_targets", "cache_predictions")
        ):
            reasons.append(f"report {index} lacks the validated log1p(TPM) contract")

    return {
        "passed": not reasons,
        "n_reports": len(reports),
        "minimum_training_seeds": min_seeds,
        "training_seeds": seeds,
        "fingerprints": {field: sorted(str(value) for value in values) for field, values in fingerprints.items()},
        "content_fingerprints": {
            field: sorted(str(value) for value in values)
            for field, values in content_fingerprints.items()
        },
    }, reasons


def _aggregate_non_gating_diagnostics(reports: list[dict]) -> dict:
    comparison_name = "true_organ_hard_vs_calibration_best_random_by_organ"
    if not all(comparison_name in report.get("comparisons", {}) for report in reports):
        return {
            "available": False,
            "gating": False,
            "reason": "one or more reports predate the direct organ-vs-random diagnostic",
        }

    organ_sets = [
        set(report.get("exploratory_random_controls", {}).get("by_organ", {}))
        for report in reports
    ]
    if not organ_sets or any(organs != organ_sets[0] for organs in organ_sets[1:]):
        raise ValueError("seed reports disagree on direct-control organ sets")
    by_organ = {}
    for organ in sorted(organ_sets[0]):
        synthetic = []
        selected_random = []
        for report in reports:
            detail = report["exploratory_random_controls"]["by_organ"][organ]
            selected_random.append(detail["calibration_selected_random_expert"])
            synthetic.append({
                "comparisons": {
                    "direct": detail["matching_organ_vs_calibration_selected_random"]
                }
            })
        by_organ[organ] = {
            "calibration_selected_random_expert_per_seed": selected_random,
            "matching_organ_vs_calibration_selected_random": _aggregate_comparison(
                synthetic, "direct"
            ),
        }
    return {
        "available": True,
        "gating": False,
        "interpretation": (
            "post-seed-42 diagnostic; cannot replace the frozen organ-fixed gate"
        ),
        "global": _aggregate_comparison(reports, comparison_name),
        "by_organ": by_organ,
    }


def decide(
    reports: list[dict],
    *,
    min_seeds: int = 3,
    thresholds: dict[str, float] | None = None,
) -> dict:
    if not reports:
        raise ValueError("at least one evaluator report is required")
    limits = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    technical, technical_reasons = _technical_audit(reports, min_seeds)
    comparison_names = (
        "true_organ_hard_vs_pooled", "soft_oracle_vs_organ_fixed",
        "organ_fixed_vs_random_fixed", "blind_hard_vs_pooled",
        "blind_hard_vs_organ_fixed", "blind_soft_vs_organ_fixed",
    )
    aggregates = {name: _aggregate_comparison(reports, name) for name in comparison_names}

    expert_sets = [set(report["backbone_checks"]["by_organ"]) for report in reports]
    if any(experts != expert_sets[0] for experts in expert_sets[1:]):
        technical_reasons.append("seed reports disagree on claim-bearing organ experts")
        technical["passed"] = False
    backbone = {"pooled": _aggregate_backbone(reports, None)}
    for organ in sorted(set.intersection(*expert_sets)):
        backbone[f"organ:{organ}"] = _aggregate_backbone(reports, organ)

    max_sd = limits["max_seed_sd_fraction"]
    backbone_detail = {
        name: _mse_residual_gate(result, 0.0, max_sd)
        for name, result in backbone.items()
    }
    true_pass = _mse_residual_gate(
        aggregates["true_organ_hard_vs_pooled"], limits["known_organ_relative_mse"], max_sd
    )
    oracle_pass = _mse_gate(
        aggregates["soft_oracle_vs_organ_fixed"], limits["oracle_relative_mse"], max_sd
    )
    random_pass = _mse_gate(
        aggregates["organ_fixed_vs_random_fixed"], limits["organ_vs_random_relative_mse"], max_sd
    )
    blind_hard_pass = _mse_residual_gate(
        aggregates["blind_hard_vs_pooled"], limits["blind_hard_relative_mse"], max_sd
    )
    blind_soft_pass = _mse_gate(
        aggregates["blind_soft_vs_organ_fixed"], limits["blind_soft_relative_mse"], max_sd
    )
    true_gain = aggregates["true_organ_hard_vs_pooled"]["mse"]["mean"]
    blind_gain = aggregates["blind_hard_vs_pooled"]["mse"]["mean"]
    recovery = blind_gain / true_gain if true_gain > 1e-12 else float("nan")
    recovery_pass = _finite(recovery) and recovery >= limits["blind_recovery"]
    blind_pass = blind_hard_pass and blind_soft_pass and recovery_pass
    non_gating_diagnostics = _aggregate_non_gating_diagnostics(reports)

    core_stability = {
        name: _effect_reproducible(aggregates[name], max_sd)
        for name in (
            "true_organ_hard_vs_pooled", "soft_oracle_vs_organ_fixed",
            "organ_fixed_vs_random_fixed",
        )
    }
    gates = {
        "technical_validity": technical["passed"],
        "backbone_health": all(backbone_detail.values()),
        "backbone_health_by_model": backbone_detail,
        "training_seed_stability": all(core_stability.values()),
        "training_seed_stability_by_effect": core_stability,
        "known_organ_ceiling": true_pass,
        "soft_oracle_ceiling": oracle_pass,
        "organ_vs_random_shards": random_pass,
        "blind_hard": blind_hard_pass,
        "blind_soft": blind_soft_pass,
        "blind_recovery": bool(recovery_pass),
        "blind_router": blind_pass,
    }

    reasons = list(technical_reasons)
    if not technical["passed"]:
        status = "red"
        branch = "technical_invalid"
        authorized = "stop; repair provenance, leakage, scale, masks, or seed coverage"
    elif not gates["backbone_health"]:
        status = "red"
        branch = "backbone_failure"
        authorized = "stop; repair data/model evaluation before Stage 2"
        reasons.append("pooled or claim-bearing expert failed the strict train-only gene-mean baseline")
    elif not gates["training_seed_stability"]:
        status = "red"
        branch = "seed_instability"
        authorized = "add preregistered seeds or stop expansion"
        reasons.append("a core specialization effect changed sign, included zero, or seed SD was too large")
    elif not oracle_pass:
        status = "red"
        branch = "no_oracle_headroom"
        authorized = "stop the MoE discovery path"
        reasons.append("soft oracle did not establish useful sample-dependent expert complementarity")
    elif not true_pass or not random_pass:
        status = "amber_axis"
        branch = "organ_is_wrong_axis"
        authorized = "at most a bounded shared-trunk label-free feasibility pilot"
        reasons.append("oracle headroom exists, but organ identity failed pooled and/or random-shard controls")
    elif not blind_pass:
        ensemble_only = (
            _effect_stable(aggregates["blind_hard_vs_organ_fixed"], max_sd)
            and not blind_hard_pass
        )
        status = "amber_ensemble" if ensemble_only else "amber_router"
        branch = "ensemble_only" if ensemble_only else "router_failure"
        authorized = (
            "mechanistic routing only; no better-system claim"
            if ensemble_only else
            "selected controlled transfer only; diagnose the router before label-free interpretation"
        )
        reasons.append("organ experts work, but the blind routing gate is incomplete")
    else:
        status = "green"
        branch = "all_stage1_gates_pass"
        authorized = "selected transfer confirmation and frozen-trunk label-free MoE pilot"
        reasons.append("all machine-evaluable Stage 1 specialization gates passed")

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "branch": branch,
        "authorized_next_experiment": authorized,
        "thresholds": limits,
        "technical_audit": technical,
        "gates": gates,
        "blind_hard_recovery_of_true_organ_gain": float(recovery),
        "aggregates": aggregates,
        "backbone_aggregates": backbone,
        "non_gating_diagnostics": non_gating_diagnostics,
        "reasons": reasons,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="append", required=True,
                        help="Repeat once per independently trained seed.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--min-seeds", type=int, default=3)
    args = parser.parse_args()
    reports = [json.loads(Path(path).read_text()) for path in args.report]
    decision = decide(reports, min_seeds=args.min_seeds)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n")
    print(json.dumps(decision, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
