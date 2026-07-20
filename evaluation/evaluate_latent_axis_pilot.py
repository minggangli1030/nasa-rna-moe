#!/usr/bin/env python3
"""Evaluate the frozen-trunk latent-axis pilot without opening the test split."""

from __future__ import annotations

import argparse
import itertools
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import adjusted_mutual_info_score

from headroom_metrics import balanced_group_mean, paired_bootstrap_ci


MODES = ("organ_supervised", "balanced_random", "label_free")


def _load_run(path: Path) -> dict[str, Any]:
    if not (path / "COMPLETE").exists():
        raise ValueError(f"run is incomplete: {path}")
    metadata = json.loads((path / "run_metadata.json").read_text())
    if metadata.get("status") != "complete":
        raise ValueError(f"run metadata is not complete: {path}")
    if metadata.get("test_accessed") is not False:
        raise ValueError(f"pilot run accessed test data: {path}")
    mode = metadata.get("mode")
    if mode not in MODES:
        raise ValueError(f"unexpected mode {mode!r}: {path}")
    with np.load(path / "routes_validation.npz") as archive:
        arrays = {name: archive[name].copy() for name in archive.files}
    return {"path": str(path), "metadata": metadata, "arrays": arrays}


def _relative(control: np.ndarray, candidate: np.ndarray, groups, organs) -> float:
    control_mean = balanced_group_mean(control, groups=groups, strata=organs)
    candidate_mean = balanced_group_mean(candidate, groups=groups, strata=organs)
    return float((control_mean - candidate_mean) / control_mean)


def _comparison(
    candidate_runs: dict[int, dict[str, Any]],
    control_runs: dict[int, dict[str, Any]],
    *,
    candidate_key: str,
    control_key: str,
    bootstrap_seed: int,
    bootstrap_reps: int,
) -> dict[str, Any]:
    seeds = sorted(candidate_runs)
    per_seed = []
    per_seed_absolute = []
    averaged_differences = []
    reference = candidate_runs[seeds[0]]["arrays"]
    reference_ids = reference["sample_ids"].astype(str)
    groups = reference["groups"].astype(str)
    organs = reference["organs"].astype(str)
    for seed in seeds:
        candidate = candidate_runs[seed]["arrays"]
        control = control_runs[seed]["arrays"]
        if not np.array_equal(candidate["sample_ids"].astype(str), reference_ids):
            raise ValueError("candidate sample order differs across seeds")
        if not np.array_equal(control["sample_ids"].astype(str), reference_ids):
            raise ValueError("control sample order differs from candidate")
        difference = control[control_key].astype(float) - candidate[candidate_key].astype(float)
        per_seed_absolute.append(
            balanced_group_mean(difference, groups=groups, strata=organs)
        )
        per_seed.append(
            _relative(
                control[control_key].astype(float),
                candidate[candidate_key].astype(float),
                groups,
                organs,
            )
        )
        averaged_differences.append(difference)
    mean_difference = np.mean(np.stack(averaged_differences), axis=0)
    ci = paired_bootstrap_ci(
        mean_difference,
        seed=bootstrap_seed,
        n_bootstrap=bootstrap_reps,
        groups=groups,
        strata=organs,
    )
    mean = float(np.mean(per_seed))
    seed_sd = float(np.std(per_seed, ddof=1)) if len(per_seed) > 1 else 0.0
    return {
        "relative_mse_reduction_mean": mean,
        "relative_mse_reduction_per_seed": per_seed,
        "absolute_mse_improvement_per_seed": per_seed_absolute,
        "study_clustered_ci95_of_seed_mean_absolute_improvement": list(ci),
        "same_positive_sign": bool(all(value > 0 for value in per_seed_absolute)),
        "seed_sd": seed_sd,
        "seed_sd_fraction_of_mean": (
            float(seed_sd / abs(mean)) if mean != 0 else float("inf")
        ),
    }


def _route_stability(runs: dict[int, dict[str, Any]]) -> dict[str, Any]:
    seed_pairs = []
    for left, right in itertools.combinations(sorted(runs), 2):
        left_routes = runs[left]["arrays"]["routes"]
        right_routes = runs[right]["arrays"]["routes"]
        seed_pairs.append({
            "seeds": [left, right],
            "ami": float(adjusted_mutual_info_score(left_routes, right_routes)),
        })
    mask_pairs = []
    for seed, run in sorted(runs.items()):
        path = Path(run["path"])
        primary = run["arrays"]["routes"]
        for repeated in sorted(path.glob("routes_validation_mask*.npz")):
            with np.load(repeated) as archive:
                repeated_routes = archive["routes"].copy()
            mask_pairs.append({
                "training_seed": seed,
                "artifact": repeated.name,
                "ami": float(adjusted_mutual_info_score(primary, repeated_routes)),
            })
    seed_amis = [item["ami"] for item in seed_pairs]
    mask_amis = [item["ami"] for item in mask_pairs]
    return {
        "seed_pairs": seed_pairs,
        "mask_pairs": mask_pairs,
        "minimum_seed_ami": float(min(seed_amis)) if seed_amis else float("nan"),
        "mean_seed_ami": float(np.mean(seed_amis)) if seed_amis else float("nan"),
        "minimum_mask_ami": float(min(mask_amis)) if mask_amis else float("nan"),
        "mean_mask_ami": float(np.mean(mask_amis)) if mask_amis else float("nan"),
    }


def _route_probes(runs: dict[int, dict[str, Any]]) -> dict[str, Any]:
    output = {}
    for seed, run in sorted(runs.items()):
        arrays = run["arrays"]
        routes = arrays["routes"]
        organs = arrays["organs"].astype(str)
        groups = arrays["groups"].astype(str)
        evidence = arrays["label_evidence"].astype(str)
        single_cell_probability = arrays["single_cell_probability"].astype(float)
        dominance = []
        for route in sorted(np.unique(routes)):
            route_groups = groups[routes == route]
            counts = np.unique(route_groups, return_counts=True)[1]
            dominance.append(float(counts.max() / counts.sum()))
        centered = single_cell_probability - single_cell_probability.mean()
        total_ss = float(np.square(centered).sum())
        between_ss = 0.0
        for route in np.unique(routes):
            values = single_cell_probability[routes == route]
            between_ss += len(values) * float(
                (values.mean() - single_cell_probability.mean()) ** 2
            )
        output[str(seed)] = {
            "organ_ami": float(adjusted_mutual_info_score(organs, routes)),
            "study_ami": float(adjusted_mutual_info_score(groups, routes)),
            "label_evidence_ami": float(
                adjusted_mutual_info_score(evidence, routes)
            ),
            "single_cell_probability_eta_squared": (
                float(between_ss / total_ss) if total_ss > 0 else 0.0
            ),
            "maximum_single_study_fraction_within_route": max(dominance),
        }
    return output


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    loaded = [_load_run(Path(value)) for value in args.run]
    by_mode: dict[str, dict[int, dict[str, Any]]] = {mode: {} for mode in MODES}
    for run in loaded:
        metadata = run["metadata"]
        mode = metadata["mode"]
        seed = int(metadata["training_seed"])
        if seed in by_mode[mode]:
            raise ValueError(f"duplicate mode/seed run: {mode}/{seed}")
        by_mode[mode][seed] = run
    seed_sets = {mode: set(runs) for mode, runs in by_mode.items()}
    if any(len(seeds) < args.min_seeds for seeds in seed_sets.values()):
        raise ValueError(f"each mode needs at least {args.min_seeds} seeds: {seed_sets}")
    if len({tuple(sorted(seeds)) for seeds in seed_sets.values()}) != 1:
        raise ValueError(f"modes have different training seeds: {seed_sets}")
    expected_seeds = {17, 42, 101}
    if any(seeds != expected_seeds for seeds in seed_sets.values()):
        raise ValueError(f"pilot requires exactly seeds {sorted(expected_seeds)}: {seed_sets}")

    fingerprint_fields = (
        "pooled_checkpoint_sha256", "expression_sha256", "manifest_sha256",
        "train_sample_ids_sha256", "validation_sample_ids_sha256", "gene_order_sha256",
        "resolved_config_sha256",
    )
    fingerprints = {
        field: sorted({run["metadata"]["hashes"][field] for run in loaded})
        for field in fingerprint_fields
    }
    if any(len(values) != 1 for values in fingerprints.values()):
        raise ValueError(f"run fingerprints differ: {fingerprints}")

    comparisons = {
        "label_free_vs_pooled": _comparison(
            by_mode["label_free"], by_mode["label_free"],
            candidate_key="router_hard_mse", control_key="pooled_mse",
            bootstrap_seed=args.bootstrap_seed, bootstrap_reps=args.bootstrap_reps,
        ),
        "label_free_vs_organ_true_partition": _comparison(
            by_mode["label_free"], by_mode["organ_supervised"],
            candidate_key="router_hard_mse", control_key="true_partition_mse",
            bootstrap_seed=args.bootstrap_seed + 1, bootstrap_reps=args.bootstrap_reps,
        ),
        "label_free_vs_balanced_random_true_partition": _comparison(
            by_mode["label_free"], by_mode["balanced_random"],
            candidate_key="router_hard_mse", control_key="true_partition_mse",
            bootstrap_seed=args.bootstrap_seed + 2, bootstrap_reps=args.bootstrap_reps,
        ),
        "label_free_vs_balanced_random_fixed": _comparison(
            by_mode["label_free"], by_mode["balanced_random"],
            candidate_key="router_hard_mse", control_key="fixed_mse",
            bootstrap_seed=args.bootstrap_seed + 3, bootstrap_reps=args.bootstrap_reps,
        ),
    }
    stability = _route_stability(by_mode["label_free"])
    probes = _route_probes(by_mode["label_free"])
    utilization = {
        str(seed): run["metadata"]["validation_metrics"]
        for seed, run in sorted(by_mode["label_free"].items())
    }

    comparison_pass = {
        name: bool(
            value["relative_mse_reduction_mean"] >= args.minimum_relative_gain
            and value["same_positive_sign"]
            and value["study_clustered_ci95_of_seed_mean_absolute_improvement"][0] > 0
            and value["seed_sd_fraction_of_mean"] <= args.maximum_seed_sd_fraction
        )
        for name, value in comparisons.items()
    }
    utilization_pass = all(
        metrics["effective_experts"] >= args.minimum_effective_expert_fraction * args.num_experts
        and metrics["minimum_route_fraction"] >= args.minimum_route_fraction
        for metrics in utilization.values()
    )
    stability_pass = bool(
        stability["minimum_seed_ami"] >= args.minimum_ami
        and stability["minimum_mask_ami"] >= args.minimum_ami
    )
    study_probe_pass = all(
        value["maximum_single_study_fraction_within_route"] <= args.maximum_study_dominance
        for value in probes.values()
    )
    passed = bool(all(comparison_pass.values()) and utilization_pass and stability_pass and study_probe_pass)
    result = {
        "schema_version": 1,
        "status": "screen_pass" if passed else "screen_fail",
        "test_accessed": False,
        "training_seeds": sorted(next(iter(seed_sets.values()))),
        "comparisons": comparisons,
        "route_stability": stability,
        "route_probes": probes,
        "utilization": utilization,
        "gates": {
            **comparison_pass,
            "utilization": utilization_pass,
            "route_stability": stability_pass,
            "study_dominance": study_probe_pass,
        },
        "fingerprints": fingerprints,
        "thresholds": {
            "minimum_relative_gain": args.minimum_relative_gain,
            "maximum_seed_sd_fraction": args.maximum_seed_sd_fraction,
            "minimum_ami": args.minimum_ami,
            "minimum_effective_expert_fraction": args.minimum_effective_expert_fraction,
            "minimum_route_fraction": args.minimum_route_fraction,
            "maximum_study_dominance": args.maximum_study_dominance,
        },
        "authorized_next_step": (
            "freeze the learned axis and evaluate once on the untouched test split"
            if passed else
            "do not access test; revise or stop the latent-axis pilot using calibration evidence only"
        ),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, output)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="append", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--min-seeds", type=int, default=3)
    parser.add_argument("--num-experts", type=int, default=5)
    parser.add_argument("--bootstrap-reps", type=int, default=2000)
    parser.add_argument("--bootstrap-seed", type=int, default=8675309)
    parser.add_argument("--minimum-relative-gain", type=float, default=0.03)
    parser.add_argument("--maximum-seed-sd-fraction", type=float, default=0.5)
    parser.add_argument("--minimum-ami", type=float, default=0.5)
    parser.add_argument("--minimum-effective-expert-fraction", type=float, default=0.6)
    parser.add_argument("--minimum-route-fraction", type=float, default=0.02)
    parser.add_argument("--maximum-study-dominance", type=float, default=0.5)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = evaluate(args)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
