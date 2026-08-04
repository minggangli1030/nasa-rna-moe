#!/usr/bin/env python3
"""Aggregate the frozen-trunk GTEx K8 adapter data-diversity curve."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


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
SEEDS = (17, 42, 101)


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def macro_organ_donor_mse(
    values: np.ndarray,
    organs: np.ndarray,
    groups: np.ndarray,
    selected_groups: dict[str, np.ndarray] | None = None,
) -> float:
    values = np.asarray(values, dtype=np.float64)
    organ_means = []
    for organ in ORGANS:
        rows = np.flatnonzero(organs == organ)
        donor_names = np.asarray(sorted(set(groups[rows].astype(str))), dtype=str)
        donor_values = {
            donor: float(values[rows[groups[rows] == donor]].mean())
            for donor in donor_names
        }
        selected = donor_names if selected_groups is None else selected_groups[organ]
        organ_means.append(float(np.mean([donor_values[str(donor)] for donor in selected])))
    return float(np.mean(organ_means))


def per_organ_donor_mse(
    values: np.ndarray,
    organs: np.ndarray,
    groups: np.ndarray,
    selected_groups: dict[str, np.ndarray] | None = None,
) -> dict[str, float]:
    values = np.asarray(values, dtype=np.float64)
    result = {}
    for organ in ORGANS:
        rows = np.flatnonzero(organs == organ)
        donor_names = np.asarray(sorted(set(groups[rows].astype(str))), dtype=str)
        donor_values = {
            donor: float(values[rows[groups[rows] == donor]].mean())
            for donor in donor_names
        }
        selected = donor_names if selected_groups is None else selected_groups[organ]
        result[organ] = float(np.mean([donor_values[str(donor)] for donor in selected]))
    return result


def relative_gain(reference: float, candidate: float) -> float:
    if reference <= 0 or not np.isfinite([reference, candidate]).all():
        raise ValueError("relative gain requires positive finite losses")
    return float(100.0 * (reference - candidate) / reference)


def _load_cache(path: Path) -> dict[str, np.ndarray]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with np.load(path, allow_pickle=False) as archive:
        return {name: np.asarray(archive[name]) for name in archive.files}


def _ci(values: np.ndarray) -> list[float]:
    return np.quantile(values, [0.025, 0.975]).astype(float).tolist()


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    protocol_path = Path(args.protocol)
    if sha256_file(protocol_path) != args.expected_protocol_sha256:
        raise ValueError("protocol SHA256 mismatch")
    protocol = json.loads(protocol_path.read_text())
    if protocol.get("status") != "frozen_gtex_k8_adapter_scale_protocol":
        raise ValueError("adapter-scale protocol is not frozen")
    if protocol["implementation"]["evaluator_sha256"] != sha256_file(Path(__file__).resolve()):
        raise ValueError("evaluator differs from frozen implementation")
    budgets = [int(value) for value in protocol["data_curve"]["donors_per_organ"]]
    if budgets != [25, 50, 100, 150, 200]:
        raise ValueError("unexpected frozen budgets")
    result_root = Path(args.result_root)
    conditions: dict[tuple[int, int, str], np.ndarray] = {}
    canonical: tuple[np.ndarray, np.ndarray, np.ndarray] | None = None
    cache_hashes: dict[str, str] = {}
    for budget in budgets:
        for seed in SEEDS:
            bank_root = result_root / f"b{budget}" / f"seed{seed}" / "banks" / "banks"
            axis_caches = {}
            for axis in ("organ_k8", "pooled_adapter"):
                path = bank_root / axis / "calibration_scores.npz"
                cache_hashes[str(path.relative_to(result_root))] = sha256_file(path)
                axis_caches[axis] = _load_cache(path)
            organ_cache = axis_caches["organ_k8"]
            current = (
                organ_cache["sample_ids"].astype(str),
                organ_cache["groups"].astype(str),
                organ_cache["organs"].astype(str),
            )
            if canonical is None:
                canonical = current
            elif not all(np.array_equal(left, right) for left, right in zip(canonical, current)):
                raise ValueError("calibration membership changed across runs")
            conditions[(budget, seed, "organ_k8")] = organ_cache["true_partition_mse"].astype(float)
            conditions[(budget, seed, "pooled")] = organ_cache["pooled_mse"].astype(float)
            conditions[(budget, seed, "pooled_adapter")] = axis_caches["pooled_adapter"][
                "true_partition_mse"
            ].astype(float)
    assert canonical is not None
    sample_ids, groups, organs = canonical
    if set(organs) != set(ORGANS):
        raise ValueError("calibration organ set changed")
    if any(len(value) != len(sample_ids) or not np.isfinite(value).all() for value in conditions.values()):
        raise ValueError("a condition contains invalid scores")

    points: dict[str, Any] = {}
    for budget in budgets:
        points[str(budget)] = {}
        for seed in SEEDS:
            losses = {
                condition: macro_organ_donor_mse(conditions[(budget, seed, condition)], organs, groups)
                for condition in ("pooled", "pooled_adapter", "organ_k8")
            }
            reference_by_organ = per_organ_donor_mse(
                conditions[(budget, seed, "pooled_adapter")], organs, groups
            )
            candidate_by_organ = per_organ_donor_mse(
                conditions[(budget, seed, "organ_k8")], organs, groups
            )
            points[str(budget)][str(seed)] = {
                "macro_organ_donor_mse": losses,
                "organ_minus_pooled_adapter_gain_percent": relative_gain(
                    losses["pooled_adapter"], losses["organ_k8"]
                ),
                "organ_minus_pooled_trunk_gain_percent": relative_gain(
                    losses["pooled"], losses["organ_k8"]
                ),
                "per_organ_gain_vs_pooled_adapter_percent": {
                    organ: relative_gain(reference_by_organ[organ], candidate_by_organ[organ])
                    for organ in ORGANS
                },
            }

    draws = int(protocol["statistics"]["donor_bootstrap_draws"])
    rng = np.random.default_rng(int(protocol["statistics"]["bootstrap_seed"]))
    donor_names = {
        organ: np.asarray(sorted(set(groups[organs == organ].astype(str))), dtype=str)
        for organ in ORGANS
    }
    gains = {
        (budget, seed, reference): np.empty(draws, dtype=float)
        for budget in budgets
        for seed in SEEDS
        for reference in ("pooled_adapter", "pooled")
    }
    for draw in range(draws):
        selected = {
            organ: rng.choice(values, size=len(values), replace=True)
            for organ, values in donor_names.items()
        }
        for budget in budgets:
            for seed in SEEDS:
                organ_loss = macro_organ_donor_mse(
                    conditions[(budget, seed, "organ_k8")], organs, groups, selected
                )
                for reference in ("pooled_adapter", "pooled"):
                    reference_loss = macro_organ_donor_mse(
                        conditions[(budget, seed, reference)], organs, groups, selected
                    )
                    gains[(budget, seed, reference)][draw] = relative_gain(
                        reference_loss, organ_loss
                    )
    bootstrap: dict[str, Any] = {}
    for budget in budgets:
        bootstrap[str(budget)] = {}
        for seed in SEEDS:
            bootstrap[str(budget)][str(seed)] = {
                reference: {
                    "mean_gain_percent": float(gains[(budget, seed, reference)].mean()),
                    "ci95": _ci(gains[(budget, seed, reference)]),
                }
                for reference in ("pooled_adapter", "pooled")
            }

    x = np.log(np.asarray(budgets, dtype=float))
    centered_x = x - x.mean()
    denominator = float(np.square(centered_x).sum())
    slopes: dict[str, Any] = {}
    for seed in SEEDS:
        matrix = np.stack([gains[(budget, seed, "pooled_adapter")] for budget in budgets])
        slope_draws = (centered_x[:, None] * matrix).sum(axis=0) / denominator
        point_y = np.asarray(
            [points[str(budget)][str(seed)]["organ_minus_pooled_adapter_gain_percent"] for budget in budgets]
        )
        point_slope = float((centered_x * point_y).sum() / denominator)
        slopes[str(seed)] = {"point_per_log_budget": point_slope, "ci95": _ci(slope_draws)}
    slope_signs = [np.sign(slopes[str(seed)]["point_per_log_budget"]) for seed in SEEDS]
    same_nonzero_sign = len(set(slope_signs)) == 1 and slope_signs[0] != 0
    every_interval_excludes_zero = all(
        interval[0] > 0 or interval[1] < 0 for interval in [slopes[str(seed)]["ci95"] for seed in SEEDS]
    )
    stable_budget_points = [
        budget
        for budget in budgets
        if all(
            bootstrap[str(budget)][str(seed)]["pooled_adapter"]["ci95"][0] > 0
            for seed in SEEDS
        )
    ]
    safety_violations = [
        {
            "budget": budget,
            "seed": seed,
            "organ": organ,
            "gain_vs_pooled_adapter_percent": points[str(budget)][str(seed)][
                "per_organ_gain_vs_pooled_adapter_percent"
            ][organ],
        }
        for budget in budgets
        for seed in SEEDS
        for organ in ORGANS
        if points[str(budget)][str(seed)]["per_organ_gain_vs_pooled_adapter_percent"][organ]
        < -float(protocol["safety"]["maximum_per_organ_harm_percent"])
    ]
    report = {
        "schema_version": 1,
        "status": "complete",
        "role": "frozen_trunk_adapter_data_diversity_development_curve",
        "protocol_sha256": sha256_file(protocol_path),
        "samples": len(sample_ids),
        "donors": int(len(set(groups))),
        "points": points,
        "bootstrap": bootstrap,
        "log_budget_slopes": slopes,
        "stable_positive_vs_pooled_adapter_budgets": stable_budget_points,
        "per_organ_safety": {
            "maximum_allowed_harm_percent": float(
                protocol["safety"]["maximum_per_organ_harm_percent"]
            ),
            "passes": not safety_violations,
            "violations": safety_violations,
        },
        "monotonic_decision": (
            "CONSISTENT_NONZERO_LOG_BUDGET_SLOPE"
            if same_nonzero_sign and every_interval_excludes_zero
            else "NO_ROBUST_MONOTONIC_CLAIM"
        ),
        "cache_sha256": cache_hashes,
        "firewalls": {
            "pooled_trunk_updated": False,
            "archs4_expression_accessed": False,
            "best_seed_or_budget_selected": False,
            "end_to_end_scaling_claim": False,
            "confirmation_claim": False,
        },
    }
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise FileExistsError(output_dir)
    output_dir.mkdir(parents=True)
    report_path = output_dir / "evaluation_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (output_dir / "IMMUTABLE_SHA256SUMS").write_text(
        f"{sha256_file(report_path)}  evaluation_report.json\n"
    )
    (output_dir / "COMPLETE").write_text("COMPLETE\n")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--result-root", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


if __name__ == "__main__":
    evaluate(parse_args())
