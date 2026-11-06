#!/usr/bin/env python3
"""Aggregate the calibration-only competitive utility-axis pilot.

The evaluator accepts the seven fixed expert banks at each of the three frozen
training seeds.  It never opens a test artifact.  Only ``head_gradient_k2`` is
the preregistered confirmatory candidate; a successful secondary candidate can
justify a new confirmation protocol, but cannot unlock the sealed test split.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np

from headroom_metrics import balanced_group_mean, paired_bootstrap_ci


EXPECTED_SEEDS = (17, 42, 101)
PRIMARY_CANDIDATE = "head_gradient_k2"
CANDIDATES = (
    "head_gradient_k2",
    "head_gradient_k3",
    "residual_pca_k2",
    "residual_pca_k3",
)
CONTROLS = ("random_k2", "random_k3", "organ_k5")
EXPECTED_AXES = CANDIDATES + CONTROLS
COMMON_FINGERPRINT_FIELDS = (
    "protocol_sha256",
    "pooled_checkpoint_sha256",
    "expression_sha256",
    "manifest_sha256",
    "partition_manifest_sha256",
    "partition_report_sha256",
    "axis_definitions_sha256",
    "train_sample_ids_sha256",
    "calibration_sample_ids_sha256",
    "gene_order_sha256",
    "score_gene_indices_sha256",
)
REQUIRED_ARRAYS = (
    "sample_ids",
    "pooled_mse",
    "true_partition_mse",
    "oracle_mse",
    "crossfit_fixed_mse",
    "true_labels",
    "groups",
    "organs",
    "sample_weights",
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _axis_k(axis: str) -> int:
    suffix = axis.rsplit("_k", 1)
    if len(suffix) != 2 or not suffix[1].isdigit():
        raise ValueError(f"axis name does not encode K: {axis!r}")
    return int(suffix[1])


def _load_run(path: Path) -> dict[str, Any]:
    if not (path / "COMPLETE").is_file():
        raise ValueError(f"bank is incomplete: {path}")
    metadata_path = path / "run_metadata.json"
    score_path = path / "calibration_scores.npz"
    if not metadata_path.is_file() or not score_path.is_file():
        raise ValueError(f"bank lacks metadata or calibration scores: {path}")
    metadata = json.loads(metadata_path.read_text())
    if metadata.get("status") != "complete":
        raise ValueError(f"bank metadata is not complete: {path}")
    if metadata.get("test_accessed") is not False:
        raise ValueError(f"bank accessed the sealed test split: {path}")
    if metadata.get("mechanical_only") is not False:
        raise ValueError(f"mechanical-only bank cannot enter a decision: {path}")
    axis = metadata.get("axis")
    if axis not in EXPECTED_AXES:
        raise ValueError(f"unexpected utility-axis bank {axis!r}: {path}")
    seed = metadata.get("training_seed")
    if not isinstance(seed, int) or seed not in EXPECTED_SEEDS:
        raise ValueError(f"unexpected training seed {seed!r}: {path}")
    expected_hash = metadata.get("artifacts", {}).get("calibration_scores_sha256")
    if not expected_hash or _sha256_file(score_path) != expected_hash:
        raise ValueError(f"calibration score hash mismatch: {path}")
    with np.load(score_path, allow_pickle=False) as archive:
        missing = sorted(set(REQUIRED_ARRAYS) - set(archive.files))
        if missing:
            raise ValueError(f"calibration scores lack {missing}: {path}")
        arrays = {name: archive[name].copy() for name in REQUIRED_ARRAYS}
    _validate_arrays(arrays, axis=axis, path=path)
    config = metadata.get("config", {})
    k = _axis_k(axis)
    if int(config.get("num_experts", -1)) != k:
        raise ValueError(f"metadata K differs from axis name: {path}")
    expected_update = {2: 600, 3: 900, 5: 1500}[k]
    if int(config.get("final_update", -1)) != expected_update:
        raise ValueError(f"bank did not use the frozen final update: {path}")
    if config.get("router_trainable") is not False:
        raise ValueError(f"fixed bank unexpectedly trained a router: {path}")
    if config.get("checkpoint_policy") != "predetermined_final_update":
        raise ValueError(f"bank used calibration checkpoint selection: {path}")
    target_exposure = int(config.get("exposures_per_expert_target", -1))
    realized = np.asarray(config.get("realized_exposure_counts", []), dtype=np.int64)
    if target_exposure <= 0 or realized.shape != (k,) or realized.sum() != expected_update * 8:
        raise ValueError(f"bank exposure accounting is invalid: {path}")
    maximum_exposure_deviation = float(
        np.max(np.abs(realized - target_exposure) / target_exposure)
    )
    if maximum_exposure_deviation > 0.05:
        raise ValueError(
            f"bank realized exposure differs by more than 5%: {path}"
        )
    hashes = metadata.get("hashes", {})
    missing_hashes = sorted(set(COMMON_FINGERPRINT_FIELDS) - set(hashes))
    if missing_hashes:
        raise ValueError(f"bank lacks common fingerprints {missing_hashes}: {path}")
    return {
        "path": str(path),
        "axis": axis,
        "seed": seed,
        "metadata": metadata,
        "arrays": arrays,
    }


def _validate_arrays(arrays: dict[str, np.ndarray], *, axis: str, path: Path) -> None:
    sample_ids = arrays["sample_ids"].astype(str)
    n_samples = len(sample_ids)
    if n_samples == 0 or len(set(sample_ids.tolist())) != n_samples:
        raise ValueError(f"sample IDs are empty or duplicated: {path}")
    for name in REQUIRED_ARRAYS:
        if arrays[name].ndim != 1 or len(arrays[name]) != n_samples:
            raise ValueError(f"array {name!r} is not sample-aligned: {path}")
    for name in (
        "pooled_mse",
        "true_partition_mse",
        "oracle_mse",
        "crossfit_fixed_mse",
    ):
        values = arrays[name].astype(np.float64)
        if not np.isfinite(values).all() or np.any(values < 0):
            raise ValueError(f"array {name!r} contains invalid MSE values: {path}")
    weights = arrays["sample_weights"].astype(np.float64)
    if not np.isfinite(weights).all() or np.any(weights < 0):
        raise ValueError(f"sample weights are invalid: {path}")
    if not np.isclose(weights.sum(), 1.0):
        raise ValueError(f"sample weights do not sum to one: {path}")
    labels = arrays["true_labels"]
    if not np.issubdtype(labels.dtype, np.integer):
        raise ValueError(f"true labels are not integers: {path}")
    labels = labels.astype(np.int64)
    k = _axis_k(axis)
    if labels.min(initial=0) < 0 or labels.max(initial=0) >= k:
        raise ValueError(f"true labels fall outside [0, {k}): {path}")


def _validate_alignment(loaded: list[dict[str, Any]]) -> dict[str, Any]:
    first = loaded[0]
    reference = first["arrays"]
    for run in loaded[1:]:
        arrays = run["arrays"]
        for name in ("sample_ids", "groups", "organs"):
            if not np.array_equal(arrays[name].astype(str), reference[name].astype(str)):
                raise ValueError(
                    f"{name} differs between {first['path']} and {run['path']}"
                )
        if not np.allclose(
            arrays["sample_weights"].astype(float),
            reference["sample_weights"].astype(float),
            rtol=0.0,
            atol=1e-15,
        ):
            raise ValueError(f"sample weights differ across banks: {run['path']}")
    fingerprints = {
        field: sorted(
            {run["metadata"]["hashes"][field] for run in loaded}
        )
        for field in COMMON_FINGERPRINT_FIELDS
    }
    if any(len(values) != 1 for values in fingerprints.values()):
        raise ValueError(f"bank fingerprints differ: {fingerprints}")
    for seed in EXPECTED_SEEDS:
        seed_runs = [run for run in loaded if run["seed"] == seed]
        pooled = seed_runs[0]["arrays"]["pooled_mse"].astype(float)
        for run in seed_runs[1:]:
            if not np.allclose(
                run["arrays"]["pooled_mse"].astype(float),
                pooled,
                rtol=1e-7,
                atol=1e-10,
            ):
                raise ValueError(
                    f"pooled calibration scores differ within seed {seed}: {run['path']}"
                )
    return {name: values[0] for name, values in fingerprints.items()}


def _relative(
    control: np.ndarray,
    candidate: np.ndarray,
    *,
    groups: np.ndarray,
    organs: np.ndarray,
) -> float:
    control_mean = balanced_group_mean(control, groups=groups, strata=organs)
    candidate_mean = balanced_group_mean(candidate, groups=groups, strata=organs)
    if control_mean <= 0:
        raise ValueError("comparison control has non-positive balanced MSE")
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
    reference = candidate_runs[EXPECTED_SEEDS[0]]["arrays"]
    groups = reference["groups"].astype(str)
    organs = reference["organs"].astype(str)
    sample_ids = reference["sample_ids"].astype(str)
    per_seed_relative: list[float] = []
    per_seed_absolute: list[float] = []
    differences: list[np.ndarray] = []
    for seed in EXPECTED_SEEDS:
        candidate = candidate_runs[seed]["arrays"]
        control = control_runs[seed]["arrays"]
        if not np.array_equal(candidate["sample_ids"].astype(str), sample_ids):
            raise ValueError(f"candidate sample order differs at seed {seed}")
        if not np.array_equal(control["sample_ids"].astype(str), sample_ids):
            raise ValueError(f"control sample order differs at seed {seed}")
        difference = (
            control[control_key].astype(np.float64)
            - candidate[candidate_key].astype(np.float64)
        )
        differences.append(difference)
        per_seed_absolute.append(
            balanced_group_mean(difference, groups=groups, strata=organs)
        )
        per_seed_relative.append(
            _relative(
                control[control_key].astype(np.float64),
                candidate[candidate_key].astype(np.float64),
                groups=groups,
                organs=organs,
            )
        )
    mean_difference = np.mean(np.stack(differences), axis=0)
    interval = paired_bootstrap_ci(
        mean_difference,
        seed=bootstrap_seed,
        n_bootstrap=bootstrap_reps,
        groups=groups,
        strata=organs,
    )
    mean_relative = float(np.mean(per_seed_relative))
    seed_sd = float(np.std(per_seed_relative, ddof=1))
    return {
        "candidate_metric": candidate_key,
        "control_metric": control_key,
        "relative_mse_reduction_mean": mean_relative,
        "relative_mse_reduction_per_seed": per_seed_relative,
        "absolute_mse_improvement_per_seed": per_seed_absolute,
        "study_clustered_ci95_of_seed_mean_absolute_improvement": list(interval),
        "same_positive_sign": bool(all(value > 0 for value in per_seed_absolute)),
        "seed_sd": seed_sd,
        "seed_sd_fraction_of_mean": (
            float(seed_sd / abs(mean_relative))
            if mean_relative != 0
            else float("inf")
        ),
    }


def _comparison_pass(
    comparison: dict[str, Any],
    *,
    minimum_relative_gain: float,
    maximum_seed_sd_fraction: float,
) -> bool:
    return bool(
        comparison["relative_mse_reduction_mean"] >= minimum_relative_gain
        and comparison["same_positive_sign"]
        and comparison[
            "study_clustered_ci95_of_seed_mean_absolute_improvement"
        ][0]
        > 0
        and comparison["seed_sd_fraction_of_mean"]
        <= maximum_seed_sd_fraction
    )


def _observed_partition_summary(arrays: dict[str, np.ndarray], k: int) -> dict[str, Any]:
    labels = arrays["true_labels"].astype(np.int64)
    groups = arrays["groups"].astype(str)
    counts = np.bincount(labels, minlength=k).astype(np.float64)
    fractions = counts / counts.sum()
    studies: list[int] = []
    dominance: list[float] = []
    for label in range(k):
        route_groups = groups[labels == label]
        unique, group_counts = np.unique(route_groups, return_counts=True)
        studies.append(int(len(unique)))
        dominance.append(
            float(group_counts.max() / group_counts.sum()) if len(unique) else 1.0
        )
    return {
        "counts": counts.astype(int).tolist(),
        "fractions": fractions.tolist(),
        "minimum_fraction": float(fractions.min()),
        "effective_k": float(1.0 / np.square(fractions).sum()),
        "connected_studies_per_partition": studies,
        "maximum_single_study_fraction": float(max(dominance)),
    }


def _partition_gates(
    axis: str,
    arrays: dict[str, np.ndarray],
    report: dict[str, Any],
    args: argparse.Namespace,
) -> tuple[dict[str, Any], dict[str, bool]]:
    k = _axis_k(axis)
    axis_report = report.get("partitions", {}).get(axis)
    if not isinstance(axis_report, dict):
        raise ValueError(f"partition report lacks candidate {axis!r}")
    if int(axis_report.get("k", -1)) != k:
        raise ValueError(f"partition report K differs for {axis}")
    stability = axis_report.get("clustering_stability", {})
    minimum_ami = float(stability.get("minimum_pairwise_ami", float("nan")))
    observed = _observed_partition_summary(arrays, k)
    reported_calibration = axis_report.get("calibration", {})
    for name in (
        "minimum_fraction",
        "effective_k",
        "maximum_single_study_fraction",
    ):
        if name not in reported_calibration or not np.isclose(
            float(reported_calibration[name]), float(observed[name]), atol=1e-12
        ):
            raise ValueError(f"partition report calibration {name} differs for {axis}")
    if reported_calibration.get("connected_studies_per_partition") != observed[
        "connected_studies_per_partition"
    ]:
        raise ValueError(f"partition report study counts differ for {axis}")
    gates = {
        "clustering_stability": bool(minimum_ami >= args.minimum_ami),
        "minimum_partition_fraction": bool(
            observed["minimum_fraction"] >= args.minimum_partition_fraction
        ),
        "effective_k": bool(
            observed["effective_k"]
            >= args.minimum_effective_expert_fraction * k
        ),
        "minimum_studies_per_partition": bool(
            min(observed["connected_studies_per_partition"])
            >= args.minimum_studies_per_partition
        ),
        "study_dominance": bool(
            observed["maximum_single_study_fraction"]
            <= args.maximum_study_dominance
        ),
    }
    summary = {
        **observed,
        "clustering_stability": stability,
        "minimum_pairwise_ami": minimum_ami,
    }
    return summary, gates


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    loaded = [_load_run(Path(value)) for value in args.run]
    by_axis: dict[str, dict[int, dict[str, Any]]] = {
        axis: {} for axis in EXPECTED_AXES
    }
    for run in loaded:
        axis = run["axis"]
        seed = run["seed"]
        if seed in by_axis[axis]:
            raise ValueError(f"duplicate utility-axis bank {axis}/seed{seed}")
        by_axis[axis][seed] = run
    expected_seed_set = set(EXPECTED_SEEDS)
    observed_axes = {axis for axis, runs in by_axis.items() if runs}
    if observed_axes != set(EXPECTED_AXES):
        raise ValueError(
            f"pilot requires exact axes {list(EXPECTED_AXES)}, found {sorted(observed_axes)}"
        )
    for axis, runs in by_axis.items():
        if set(runs) != expected_seed_set:
            raise ValueError(
                f"axis {axis} requires exact seeds {list(EXPECTED_SEEDS)}, "
                f"found {sorted(runs)}"
            )
        reference_labels = runs[EXPECTED_SEEDS[0]]["arrays"]["true_labels"]
        for seed in EXPECTED_SEEDS[1:]:
            if not np.array_equal(
                runs[seed]["arrays"]["true_labels"], reference_labels
            ):
                raise ValueError(f"fixed labels differ across seeds for {axis}")
    if len(loaded) != len(EXPECTED_AXES) * len(EXPECTED_SEEDS):
        raise ValueError("pilot requires exactly one run per axis and seed")
    fingerprints = _validate_alignment(loaded)

    partition_report_path = Path(args.partition_report)
    partition_report = json.loads(partition_report_path.read_text())
    if (
        partition_report.get("status") != "complete"
        or partition_report.get("test_accessed") is not False
    ):
        raise ValueError("partition report is incomplete or accessed test")
    if _sha256_file(partition_report_path) != fingerprints["partition_report_sha256"]:
        raise ValueError("partition report does not match bank fingerprints")
    if partition_report.get("primary_candidate") != PRIMARY_CANDIDATE:
        raise ValueError("partition report changed the confirmatory primary candidate")
    if tuple(partition_report.get("candidate_family", ())) != CANDIDATES:
        raise ValueError("partition report candidate family differs from frozen family")
    if set(partition_report.get("controls", ())) != set(CONTROLS):
        raise ValueError("partition report controls differ from frozen controls")

    candidates: dict[str, Any] = {}
    for candidate_index, axis in enumerate(CANDIDATES):
        k = _axis_k(axis)
        random_axis = f"random_k{k}"
        bootstrap_base = args.bootstrap_seed + candidate_index * 10
        comparisons = {
            "true_partition_vs_pooled": _comparison(
                by_axis[axis],
                by_axis[axis],
                candidate_key="true_partition_mse",
                control_key="pooled_mse",
                bootstrap_seed=bootstrap_base,
                bootstrap_reps=args.bootstrap_reps,
            ),
            "true_partition_vs_matched_random": _comparison(
                by_axis[axis],
                by_axis[random_axis],
                candidate_key="true_partition_mse",
                control_key="true_partition_mse",
                bootstrap_seed=bootstrap_base + 1,
                bootstrap_reps=args.bootstrap_reps,
            ),
            "oracle_vs_crossfit_fixed": _comparison(
                by_axis[axis],
                by_axis[axis],
                candidate_key="oracle_mse",
                control_key="crossfit_fixed_mse",
                bootstrap_seed=bootstrap_base + 2,
                bootstrap_reps=args.bootstrap_reps,
            ),
            "true_partition_vs_organ_k5": _comparison(
                by_axis[axis],
                by_axis["organ_k5"],
                candidate_key="true_partition_mse",
                control_key="true_partition_mse",
                bootstrap_seed=bootstrap_base + 3,
                bootstrap_reps=args.bootstrap_reps,
            ),
        }
        comparison_gates = {
            "minimum_3pct_vs_pooled": _comparison_pass(
                comparisons["true_partition_vs_pooled"],
                minimum_relative_gain=args.minimum_relative_gain,
                maximum_seed_sd_fraction=args.maximum_seed_sd_fraction,
            ),
            "positive_vs_matched_random": _comparison_pass(
                comparisons["true_partition_vs_matched_random"],
                minimum_relative_gain=0.0,
                maximum_seed_sd_fraction=args.maximum_seed_sd_fraction,
            ),
            "minimum_3pct_oracle_vs_crossfit_fixed": _comparison_pass(
                comparisons["oracle_vs_crossfit_fixed"],
                minimum_relative_gain=args.minimum_relative_gain,
                maximum_seed_sd_fraction=args.maximum_seed_sd_fraction,
            ),
        }
        partition_summary, partition_gates = _partition_gates(
            axis,
            by_axis[axis][EXPECTED_SEEDS[0]]["arrays"],
            partition_report,
            args,
        )
        core_pass = bool(
            all(comparison_gates.values()) and all(partition_gates.values())
        )
        organ_replacement_pass = bool(
            core_pass
            and _comparison_pass(
                comparisons["true_partition_vs_organ_k5"],
                minimum_relative_gain=args.minimum_relative_gain,
                maximum_seed_sd_fraction=args.maximum_seed_sd_fraction,
            )
        )
        branch = (
            "replacement_candidate"
            if organ_replacement_pass
            else "augmentation_candidate"
            if core_pass
            else "stop_candidate"
        )
        candidates[axis] = {
            "primary": axis == PRIMARY_CANDIDATE,
            "k": k,
            "matched_random_axis": random_axis,
            "comparisons": comparisons,
            "comparison_gates": comparison_gates,
            "partition_summary": partition_summary,
            "partition_gates": partition_gates,
            "core_pass": core_pass,
            "organ_replacement_pass": organ_replacement_pass,
            "branch": branch,
        }

    primary = candidates[PRIMARY_CANDIDATE]
    passing_secondaries = [
        axis for axis in CANDIDATES[1:] if candidates[axis]["core_pass"]
    ]
    if primary["core_pass"]:
        status = "screen_pass_primary"
        decision_branch = primary["branch"]
        authorized_next_step = (
            "do not access test yet; freeze head_gradient_k2 in a separate confirmation "
            f"protocol as a {primary['branch'].replace('_candidate', '')} axis"
        )
    elif passing_secondaries:
        status = "screen_pass_secondary_only"
        decision_branch = "secondary_requires_new_confirmation"
        authorized_next_step = (
            "do not access test; freeze exactly one passing secondary in a new "
            "preregistered confirmation before any test evaluation"
        )
    else:
        status = "screen_fail"
        decision_branch = "stop_discrete_utility_axis"
        authorized_next_step = (
            "do not access test; stop this discrete label-free utility-axis branch"
        )

    result = {
        "schema_version": 1,
        "status": status,
        "decision_branch": decision_branch,
        "test_accessed": False,
        "test_access_authorized": False,
        "confirmatory_primary": PRIMARY_CANDIDATE,
        "training_seeds": list(EXPECTED_SEEDS),
        "passing_secondary_candidates": passing_secondaries,
        "candidates": candidates,
        "fingerprints": fingerprints,
        "thresholds": {
            "minimum_relative_gain": args.minimum_relative_gain,
            "maximum_seed_sd_fraction": args.maximum_seed_sd_fraction,
            "minimum_ami": args.minimum_ami,
            "minimum_partition_fraction": args.minimum_partition_fraction,
            "minimum_effective_expert_fraction": args.minimum_effective_expert_fraction,
            "minimum_studies_per_partition": args.minimum_studies_per_partition,
            "maximum_study_dominance": args.maximum_study_dominance,
        },
        "authorized_next_step": authorized_next_step,
    }
    _atomic_json(Path(args.output), result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="append", required=True)
    parser.add_argument("--partition-report", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--bootstrap-reps", type=int, default=2000)
    parser.add_argument("--bootstrap-seed", type=int, default=8675309)
    parser.add_argument("--minimum-relative-gain", type=float, default=0.03)
    parser.add_argument("--maximum-seed-sd-fraction", type=float, default=0.5)
    parser.add_argument("--minimum-ami", type=float, default=0.5)
    parser.add_argument("--minimum-partition-fraction", type=float, default=0.10)
    parser.add_argument(
        "--minimum-effective-expert-fraction", type=float, default=0.8
    )
    parser.add_argument("--minimum-studies-per-partition", type=int, default=5)
    parser.add_argument("--maximum-study-dominance", type=float, default=0.5)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = evaluate(args)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
