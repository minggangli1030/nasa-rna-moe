#!/usr/bin/env python3
"""Evaluate the locked internal K5 organ-specialist replication.

This is the only decision program allowed to consume the already-inspected,
study-disjoint test cache.  The router and every model bank must have been
frozen before that cache was produced.  The resulting evidence is explicitly
an internal locked replication, not an independent biological confirmation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from headroom_metrics import balanced_group_mean, paired_bootstrap_ci, pearson_rows


EXPECTED_SEEDS = (17, 42, 101)
CANONICAL_ORGANS = (
    "adipose",
    "brain",
    "liver",
    "skeletal_muscle",
    "skin",
)
GROUP_RANDOM_AXES = (
    "random_group_k5_p17",
    "random_group_k5_p42",
    "random_group_k5_p101",
)
COMMON_HASHES = (
    "protocol_sha256",
    "manifest_sha256",
    "partition_manifest_sha256",
    "axis_definitions_sha256",
    "score_gene_indices_sha256",
    "router_artifact_sha256",
    "sealed_test_assignments_sha256",
)
REQUIRED_CACHE_ARRAYS = (
    "sample_ids",
    "groups",
    "organs",
    "sample_weights",
    "organ_labels",
    "random_labels",
    "target_masked",
    "baseline_masked",
    "pooled_masked",
    "organ_expert_masked",
    "random_expert_masked",
    "blind_k5_probabilities",
    "blind_k5_predicted_organ",
    "k5_full_classes",
    *tuple(
        name
        for axis in GROUP_RANDOM_AXES
        for name in (f"{axis}_labels", f"{axis}_expert_masked")
    ),
)
REQUIRED_CALIBRATION_ARRAYS = (
    "sample_ids",
    "groups",
    "organs",
    "sample_weights",
    "pooled_mse",
    "true_partition_mse",
    "oracle_mse",
    "crossfit_fixed_mse",
    "expert_mse",
    "true_labels",
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


def _seed_matrix(
    values: Mapping[int, np.ndarray] | np.ndarray,
    seeds: Sequence[int],
    *,
    name: str,
) -> np.ndarray:
    expected = [int(seed) for seed in seeds]
    if isinstance(values, Mapping):
        observed = sorted(int(seed) for seed in values)
        if observed != sorted(expected):
            raise ValueError(f"{name} seed keys differ from requested seeds")
        matrix = np.stack([np.asarray(values[seed], dtype=np.float64) for seed in expected])
    else:
        matrix = np.asarray(values, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] != len(expected):
        raise ValueError(f"{name} shape does not align with seed axis")
    if not np.isfinite(matrix).all():
        raise ValueError(f"{name} contains non-finite values")
    return matrix


def comparison(
    control: Mapping[int, np.ndarray] | np.ndarray,
    candidate: Mapping[int, np.ndarray] | np.ndarray,
    groups: np.ndarray,
    organs: np.ndarray,
    seeds: Sequence[int],
    *,
    bootstrap_seed: int = 271828,
    bootstrap_reps: int = 2000,
) -> dict[str, Any]:
    """Compare aligned per-seed MSE arrays using the frozen balanced estimand."""
    control_matrix = _seed_matrix(control, seeds, name="control")
    candidate_matrix = _seed_matrix(candidate, seeds, name="candidate")
    if candidate_matrix.shape != control_matrix.shape:
        raise ValueError("candidate and control shapes do not align")
    groups = np.asarray(groups).astype(str)
    organs = np.asarray(organs).astype(str)
    if groups.ndim != 1 or organs.ndim != 1 or groups.shape != organs.shape:
        raise ValueError("group and organ arrays do not align")
    if control_matrix.shape[1] != len(groups):
        raise ValueError("metric sample axis does not align with groups and organs")
    if np.any(control_matrix < 0) or np.any(candidate_matrix < 0):
        raise ValueError("MSE comparison contains a negative value")

    absolute: list[float] = []
    relative: list[float] = []
    control_means: list[float] = []
    candidate_means: list[float] = []
    for row in range(len(seeds)):
        control_mean = balanced_group_mean(control_matrix[row], groups, organs)
        candidate_mean = balanced_group_mean(candidate_matrix[row], groups, organs)
        if not np.isfinite(control_mean) or control_mean <= 0:
            raise ValueError("comparison control has non-positive balanced MSE")
        control_means.append(float(control_mean))
        candidate_means.append(float(candidate_mean))
        absolute.append(float(control_mean - candidate_mean))
        relative.append(float((control_mean - candidate_mean) / control_mean))
    seed_mean_difference = np.mean(control_matrix - candidate_matrix, axis=0)
    interval = paired_bootstrap_ci(
        seed_mean_difference,
        seed=int(bootstrap_seed),
        n_bootstrap=int(bootstrap_reps),
        groups=groups,
        strata=organs,
    )
    relative_mean = float(np.mean(relative))
    seed_sd = float(np.std(relative, ddof=1)) if len(relative) > 1 else 0.0
    return {
        "control_mse_per_seed": control_means,
        "candidate_mse_per_seed": candidate_means,
        "absolute_mse_improvement_per_seed": absolute,
        "relative_mse_reduction_per_seed": relative,
        "relative_mse_reduction_mean": relative_mean,
        "study_clustered_ci95_of_seed_mean_absolute_improvement": list(interval),
        "positive_clustered_interval": bool(interval[0] > 0),
        "same_positive_sign": bool(all(value > 0 for value in absolute)),
        "seed_sd": seed_sd,
        "seed_sd_fraction_of_mean": (
            float(seed_sd / abs(relative_mean))
            if relative_mean != 0
            else float("inf")
        ),
    }


def _correlation_comparison(
    control: Mapping[int, np.ndarray] | np.ndarray,
    candidate: Mapping[int, np.ndarray] | np.ndarray,
    groups: np.ndarray,
    organs: np.ndarray,
    seeds: Sequence[int],
    *,
    bootstrap_seed: int,
    bootstrap_reps: int,
) -> dict[str, Any]:
    control_matrix = _seed_matrix(control, seeds, name="control correlation")
    candidate_matrix = _seed_matrix(candidate, seeds, name="candidate correlation")
    if control_matrix.shape != candidate_matrix.shape:
        raise ValueError("correlation arrays do not align")
    groups = np.asarray(groups).astype(str)
    organs = np.asarray(organs).astype(str)
    if control_matrix.shape[1] != len(groups) or groups.shape != organs.shape:
        raise ValueError("correlation sample axis does not align")
    gains = candidate_matrix - control_matrix
    per_seed = [
        balanced_group_mean(row, groups=groups, strata=organs) for row in gains
    ]
    interval = paired_bootstrap_ci(
        gains.mean(axis=0),
        seed=bootstrap_seed,
        n_bootstrap=bootstrap_reps,
        groups=groups,
        strata=organs,
    )
    return {
        "gain_per_seed": [float(value) for value in per_seed],
        "gain_mean": float(np.mean(per_seed)),
        "study_clustered_ci95_of_seed_mean_gain": list(interval),
        "positive_clustered_interval": bool(interval[0] > 0),
        "same_positive_sign": bool(all(value > 0 for value in per_seed)),
    }


def validate_alignment(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Fail closed unless three normalized test runs share exact provenance/order."""
    if len(runs) != len(EXPECTED_SEEDS):
        raise ValueError("confirmation requires exactly three frozen seeds")
    seeds = [run.get("seed") for run in runs]
    if sorted(seeds) != list(EXPECTED_SEEDS) or len(set(seeds)) != len(seeds):
        raise ValueError(f"confirmation seed set is invalid: {seeds}")
    ordered = sorted(runs, key=lambda run: int(run["seed"]))
    first = ordered[0]
    for run in ordered:
        if run.get("status") != "complete":
            raise ValueError("test cache is not complete")
        if run.get("split") != "test":
            raise ValueError("confirmation cache must contain only the test split")
        if run.get("authorized_test_access") is not True:
            raise ValueError("test access is not explicitly authorized")
        if run.get("mechanical_only") is not False:
            raise ValueError("mechanical-only results cannot enter confirmation")
        for name in ("sample_ids", "groups", "organs", "sample_weights"):
            values = np.asarray(run.get(name))
            if values.ndim != 1:
                raise ValueError(f"{name} does not align to a sample vector")
        sample_count = len(run["sample_ids"])
        if sample_count == 0 or len(set(np.asarray(run["sample_ids"]).astype(str))) != sample_count:
            raise ValueError("sample IDs are empty or duplicated")
        if any(len(np.asarray(run[name])) != sample_count for name in ("groups", "organs", "sample_weights")):
            raise ValueError("sample metadata lengths do not align")
        for name, values in run.get("arrays", {}).items():
            values = np.asarray(values)
            if name == "k5_full_classes":
                if values.ndim != 1 or len(values) != 5:
                    raise ValueError("global K5 router classes have invalid shape")
                continue
            if values.ndim < 1 or values.shape[0] != sample_count:
                raise ValueError(f"array {name!r} length does not align to samples")
        missing_hashes = sorted(set(COMMON_HASHES) - set(run.get("hashes", {})))
        if missing_hashes:
            raise ValueError(f"run lacks confirmation fingerprints: {missing_hashes}")
    for name in ("sample_ids", "groups", "organs"):
        reference = np.asarray(first[name]).astype(str)
        for run in ordered[1:]:
            if not np.array_equal(reference, np.asarray(run[name]).astype(str)):
                raise ValueError(f"{name} differs across test runs")
    reference_weights = np.asarray(first["sample_weights"], dtype=np.float64)
    for run in ordered[1:]:
        if not np.allclose(
            reference_weights,
            np.asarray(run["sample_weights"], dtype=np.float64),
            rtol=0,
            atol=1e-15,
        ):
            raise ValueError("sample weights differ across test runs")
    fingerprints: dict[str, str] = {}
    for name in COMMON_HASHES:
        values = {str(run["hashes"][name]) for run in ordered}
        if len(values) != 1:
            raise ValueError(f"fingerprint/hash {name} differs across test runs")
        fingerprints[name] = values.pop()
    return {
        "seeds": list(EXPECTED_SEEDS),
        "sample_count": int(len(first["sample_ids"])),
        "fingerprints": fingerprints,
        "authorized_test_access": True,
    }


def _metric_gate(
    metric: dict[str, Any],
    *,
    minimum_gain: float,
    require_residual: bool = False,
) -> bool:
    return bool(
        float(metric.get("relative_mse_reduction_mean", -np.inf)) >= minimum_gain
        and metric.get("positive_clustered_interval") is True
        and metric.get("same_positive_sign") is True
        and float(metric.get("seed_sd_fraction_of_mean", np.inf)) <= 0.5
        and (
            not require_residual
            or metric.get("positive_residual_pearson_interval") is True
        )
    )


def _conservative_random_family(
    partition_comparisons: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Collapse preregistered random partitions by their least favorable gate."""
    if set(partition_comparisons) != set(GROUP_RANDOM_AXES):
        raise ValueError("random-control family differs from the frozen three axes")
    rows = list(partition_comparisons.values())
    return {
        "partition_comparisons": partition_comparisons,
        "relative_mse_reduction_mean": float(
            min(row["relative_mse_reduction_mean"] for row in rows)
        ),
        "relative_mse_reduction_per_seed": [
            value
            for axis in GROUP_RANDOM_AXES
            for value in partition_comparisons[axis][
                "relative_mse_reduction_per_seed"
            ]
        ],
        "positive_clustered_interval": bool(
            all(row["positive_clustered_interval"] for row in rows)
        ),
        "same_positive_sign": bool(
            all(row["same_positive_sign"] for row in rows)
        ),
        "seed_sd_fraction_of_mean": float(
            max(row["seed_sd_fraction_of_mean"] for row in rows)
        ),
        "aggregation": (
            "least favorable of three preregistered connected-study-preserving "
            "random partitions; every partition must pass"
        ),
    }


def track_a_decision(
    comparisons: dict[str, Any],
    *,
    oracle_gate: bool,
    technical_gates: dict[str, bool],
) -> dict[str, Any]:
    """Apply the frozen Track-A gates with explicit diagnostic precedence."""
    blind = comparisons["blind_organ_hard_vs_pooled"]
    true_pooled = comparisons["true_organ_hard_vs_pooled"]
    assigned_random = comparisons["true_organ_hard_vs_assigned_random_k5"]
    selected_random = comparisons[
        "true_organ_hard_vs_calibration_selected_random"
    ]
    gates = {
        "technical": bool(technical_gates) and all(technical_gates.values()),
        "true_specialization_vs_pooled": _metric_gate(
            true_pooled, minimum_gain=0.03, require_residual=True
        ),
        "random_control": bool(
            _metric_gate(assigned_random, minimum_gain=0.03)
            and _metric_gate(selected_random, minimum_gain=0.0)
        ),
        "calibration_oracle_headroom": bool(oracle_gate),
        "blind_router": _metric_gate(
            blind, minimum_gain=0.03, require_residual=True
        ),
        "blind_recovery": bool(
            float(comparisons.get("blind_recovery_of_true_gain", -np.inf)) >= 0.8
        ),
    }
    if not gates["technical"]:
        branch = "technical_fail"
    elif not gates["true_specialization_vs_pooled"] or not gates["calibration_oracle_headroom"]:
        branch = "pooled_fail"
    elif not gates["random_control"]:
        branch = "random_control_fail"
    elif not gates["blind_router"] or not gates["blind_recovery"]:
        branch = "true_pass_blind_fail"
    else:
        branch = "pass"
    return {
        "decision_branch": branch,
        "all_gates_pass": bool(branch == "pass"),
        "gates": gates,
        "technical_gates": {key: bool(value) for key, value in technical_gates.items()},
        "test_accessed": True,
        "internal_locked_replication": True,
        "independent_confirmation": False,
        "automatic_external_test_authorization": False,
    }


def _load_bank(path: Path, *, axis: str, seed: int) -> dict[str, Any]:
    metadata_path = path / "run_metadata.json"
    score_path = path / "calibration_scores.npz"
    if not (path / "COMPLETE").is_file() or not metadata_path.is_file() or not score_path.is_file():
        raise ValueError(f"incomplete calibration bank: {path}")
    metadata = json.loads(metadata_path.read_text())
    if metadata.get("status") != "complete" or metadata.get("test_accessed") is not False:
        raise ValueError(f"invalid calibration bank state: {path}")
    if metadata.get("mechanical_only") is not False:
        raise ValueError(f"mechanical-only bank cannot enter confirmation: {path}")
    if metadata.get("axis") != axis or metadata.get("training_seed") != seed:
        raise ValueError(f"bank axis or seed mismatch: {path}")
    config = metadata.get("config", {})
    if int(config.get("num_experts", -1)) != 5 or int(config.get("final_update", -1)) != 1500:
        raise ValueError(f"bank does not satisfy frozen K5/update contract: {path}")
    if config.get("checkpoint_policy") != "predetermined_final_update":
        raise ValueError(f"bank selected a checkpoint: {path}")
    target = int(config.get("exposures_per_expert_target", -1))
    realized = np.asarray(config.get("realized_exposure_counts", []), dtype=np.float64)
    if target != 2400 or realized.shape != (5,):
        raise ValueError(f"bank exposure accounting is invalid: {path}")
    deviation = float(np.max(np.abs(realized - target) / target))
    fixed_weights = np.asarray(
        metadata.get("calibration_metrics", {}).get(
            "full_calibration_fixed_weights", []
        ),
        dtype=np.float64,
    )
    if (
        fixed_weights.shape != (5,)
        or not np.isfinite(fixed_weights).all()
        or np.any(fixed_weights < -1e-10)
        or not np.isclose(fixed_weights.sum(), 1.0, atol=1e-8)
    ):
        raise ValueError(f"bank lacks valid full-calibration fixed weights: {path}")
    expected_score_hash = metadata.get("artifacts", {}).get("calibration_scores_sha256")
    if expected_score_hash != _sha256_file(score_path):
        raise ValueError(f"calibration score hash mismatch: {path}")
    with np.load(score_path, allow_pickle=False) as archive:
        missing = sorted(set(REQUIRED_CALIBRATION_ARRAYS) - set(archive.files))
        if missing:
            raise ValueError(f"calibration bank lacks arrays {missing}: {path}")
        arrays = {name: archive[name].copy() for name in REQUIRED_CALIBRATION_ARRAYS}
    n_samples = len(arrays["sample_ids"])
    if arrays["expert_mse"].shape != (n_samples, 5):
        raise ValueError(f"calibration expert MSE has wrong shape: {path}")
    for name in REQUIRED_CALIBRATION_ARRAYS:
        if np.asarray(arrays[name]).shape[0] != n_samples:
            raise ValueError(f"calibration array {name} is misaligned: {path}")
    return {
        "axis": axis,
        "seed": seed,
        "metadata": metadata,
        "arrays": arrays,
        "maximum_exposure_fractional_deviation": deviation,
        "full_calibration_fixed_weights": fixed_weights,
        "path": str(path),
    }


def _read_report_hash(report: dict[str, Any], names: Sequence[str]) -> str | None:
    hashes = report.get("hashes", {})
    for name in names:
        value = hashes.get(name)
        if value is not None:
            return str(value)
    return None


def _load_cache(path: Path, *, seed: int) -> dict[str, Any]:
    score_path = path / "test_scores.npz"
    report_path = path / "test_score_report.json"
    if not score_path.is_file() or not report_path.is_file():
        raise ValueError(f"test cache is incomplete: {path}")
    report = json.loads(report_path.read_text())
    if report.get("status") != "complete" or report.get("test_accessed") is not True:
        raise ValueError(f"test cache lacks explicit completed test access: {path}")
    if report.get("mechanical_only") is not False:
        raise ValueError(f"mechanical cache cannot enter confirmation: {path}")
    report_seed = report.get("training_seed", report.get("seed"))
    if int(report_seed) != seed:
        raise ValueError(f"test cache seed mismatch: {path}")
    expected = _read_report_hash(
        report, ("test_scores_sha256", "score_artifact_sha256")
    )
    if expected != _sha256_file(score_path):
        raise ValueError(f"test score hash mismatch: {path}")
    with np.load(score_path, allow_pickle=False) as archive:
        missing = sorted(set(REQUIRED_CACHE_ARRAYS) - set(archive.files))
        if missing:
            raise ValueError(f"test cache lacks arrays {missing}: {path}")
        arrays = {name: archive[name].copy() for name in REQUIRED_CACHE_ARRAYS}
    n_samples = len(arrays["sample_ids"])
    target = np.asarray(arrays["target_masked"], dtype=np.float64)
    if target.ndim != 2 or target.shape[0] != n_samples or target.shape[1] == 0:
        raise ValueError(f"test target cache has wrong shape: {path}")
    for name in ("baseline_masked", "pooled_masked"):
        if np.asarray(arrays[name]).shape != target.shape:
            raise ValueError(f"test cache {name} shape differs from target: {path}")
    for name in ("organ_expert_masked", "random_expert_masked"):
        if np.asarray(arrays[name]).shape != (n_samples, 5, target.shape[1]):
            raise ValueError(f"test cache {name} shape is invalid: {path}")
    for axis in GROUP_RANDOM_AXES:
        if np.asarray(arrays[f"{axis}_labels"]).shape != (n_samples,):
            raise ValueError(f"test cache {axis} labels are invalid: {path}")
        if np.asarray(arrays[f"{axis}_expert_masked"]).shape != (
            n_samples, 5, target.shape[1]
        ):
            raise ValueError(f"test cache {axis} expert shape is invalid: {path}")
    if np.asarray(arrays["blind_k5_probabilities"]).shape != (n_samples, 5):
        raise ValueError(f"blind router probability shape is invalid: {path}")
    hashes = report.get("hashes", {})
    normalized_hashes: dict[str, str] = {}
    aliases = {
        "protocol_sha256": ("protocol_sha256",),
        "manifest_sha256": ("manifest_sha256", "source_manifest_sha256"),
        "partition_manifest_sha256": ("partition_manifest_sha256",),
        "axis_definitions_sha256": ("axis_definitions_sha256",),
        "score_gene_indices_sha256": ("score_gene_indices_sha256",),
        "router_artifact_sha256": ("router_artifact_sha256",),
        "sealed_test_assignments_sha256": ("sealed_test_assignments_sha256",),
    }
    for canonical, choices in aliases.items():
        value = next((hashes.get(name) for name in choices if hashes.get(name)), None)
        if value is None:
            raise ValueError(f"test cache lacks fingerprint {canonical}: {path}")
        normalized_hashes[canonical] = str(value)
    return {
        "status": "complete",
        "seed": seed,
        "split": "test",
        "authorized_test_access": bool(
            report.get("authorized_test_access", report.get("test_accessed"))
        ),
        "mechanical_only": bool(report.get("mechanical_only")),
        "sample_ids": arrays["sample_ids"].astype(str),
        "groups": arrays["groups"].astype(str),
        "organs": arrays["organs"].astype(str),
        "sample_weights": arrays["sample_weights"].astype(np.float64),
        "arrays": arrays,
        "hashes": normalized_hashes,
        "report": report,
        "score_path": str(score_path),
        "report_path": str(report_path),
    }


def _validate_bank_alignment(
    organ_banks: dict[int, dict[str, Any]], random_banks: dict[int, dict[str, Any]]
) -> dict[str, Any]:
    reference = organ_banks[EXPECTED_SEEDS[0]]["arrays"]
    for seed in EXPECTED_SEEDS:
        for bank in (organ_banks[seed], random_banks[seed]):
            arrays = bank["arrays"]
            for name in ("sample_ids", "groups", "organs"):
                if not np.array_equal(arrays[name].astype(str), reference[name].astype(str)):
                    raise ValueError(f"calibration {name} differs at seed {seed}")
            if not np.allclose(
                arrays["sample_weights"].astype(float),
                reference["sample_weights"].astype(float),
                atol=1e-15,
                rtol=0,
            ):
                raise ValueError(f"calibration weights differ at seed {seed}")
        organ_hashes = organ_banks[seed]["metadata"].get("hashes", {})
        random_hashes = random_banks[seed]["metadata"].get("hashes", {})
        for name in (
            "protocol_sha256",
            "manifest_sha256",
            "partition_manifest_sha256",
            "axis_definitions_sha256",
            "score_gene_indices_sha256",
        ):
            if organ_hashes.get(name) != random_hashes.get(name):
                raise ValueError(f"matched bank fingerprint {name} differs at seed {seed}")
    return {
        "sample_ids": reference["sample_ids"].astype(str),
        "groups": reference["groups"].astype(str),
        "organs": reference["organs"].astype(str),
    }


def _condition_predictions(
    cache: dict[str, Any],
    random_choices: dict[str, np.ndarray],
    fixed_weights: dict[str, np.ndarray],
) -> dict[str, np.ndarray]:
    arrays = cache["arrays"]
    target = arrays["target_masked"].astype(np.float64)
    pooled = arrays["pooled_masked"].astype(np.float64)
    organ_experts = arrays["organ_expert_masked"].astype(np.float64)
    legacy_random_experts = arrays["random_expert_masked"].astype(np.float64)
    organ_labels = arrays["organ_labels"].astype(np.int64)
    legacy_random_labels = arrays["random_labels"].astype(np.int64)
    rows = np.arange(len(target))
    if organ_labels.min(initial=0) < 0 or organ_labels.max(initial=0) >= 5:
        raise ValueError("test organ labels fall outside K5")
    if (
        legacy_random_labels.min(initial=0) < 0
        or legacy_random_labels.max(initial=0) >= 5
    ):
        raise ValueError("test random labels fall outside K5")
    class_names = arrays["k5_full_classes"].astype(str)
    if len(class_names) != 5 or set(class_names) != set(CANONICAL_ORGANS):
        raise ValueError("blind router classes differ from the canonical organs")
    probabilities = arrays["blind_k5_probabilities"].astype(np.float64)
    if not np.allclose(probabilities.sum(axis=1), 1.0, atol=1e-8):
        raise ValueError("blind router probabilities do not sum to one")
    predicted_names = arrays["blind_k5_predicted_organ"].astype(str)
    if not set(predicted_names) <= set(CANONICAL_ORGANS):
        raise ValueError("blind router predicted an unknown organ")
    canonical_index = {name: index for index, name in enumerate(CANONICAL_ORGANS)}
    blind_labels = np.asarray([canonical_index[name] for name in predicted_names])
    probability_by_expert = np.empty_like(probabilities)
    for column, name in enumerate(class_names):
        probability_by_expert[:, canonical_index[name]] = probabilities[:, column]
    soft = np.einsum("nk,nkm->nm", probability_by_expert, organ_experts)
    organ_error = np.square(organ_experts - target[:, None, :]).mean(axis=2)
    output = {
        "pooled": pooled,
        "true_organ_hard": organ_experts[rows, organ_labels],
        "blind_organ_hard": organ_experts[rows, blind_labels],
        "blind_organ_soft": soft,
        "organ_full_calibration_fixed": np.einsum(
            "k,nkm->nm", fixed_weights["organ_k5"], organ_experts
        ),
        "legacy_assigned_random_k5_hard": legacy_random_experts[
            rows, legacy_random_labels
        ],
        "legacy_calibration_selected_random": legacy_random_experts[
            rows, random_choices["random_k5"][organ_labels]
        ],
        "legacy_random_full_calibration_fixed": np.einsum(
            "k,nkm->nm", fixed_weights["random_k5"], legacy_random_experts
        ),
        "organ_hard_oracle": organ_experts[rows, np.argmin(organ_error, axis=1)],
    }
    for axis in GROUP_RANDOM_AXES:
        experts = arrays[f"{axis}_expert_masked"].astype(np.float64)
        labels = arrays[f"{axis}_labels"].astype(np.int64)
        if labels.min(initial=0) < 0 or labels.max(initial=0) >= 5:
            raise ValueError(f"test {axis} labels fall outside K5")
        output[f"{axis}_assigned_hard"] = experts[rows, labels]
        output[f"{axis}_calibration_selected_by_organ"] = experts[
            rows, random_choices[axis][organ_labels]
        ]
        output[f"{axis}_full_calibration_fixed"] = np.einsum(
            "k,nkm->nm", fixed_weights[axis], experts
        )
    return output


def _selected_random_experts(bank: dict[str, Any]) -> np.ndarray:
    arrays = bank["arrays"]
    organs = arrays["organs"].astype(str)
    groups = arrays["groups"].astype(str)
    expert_mse = arrays["expert_mse"].astype(np.float64)
    selected = np.empty(5, dtype=np.int64)
    for organ_index, organ in enumerate(CANONICAL_ORGANS):
        mask = organs == organ
        if not mask.any():
            raise ValueError(f"calibration lacks organ {organ}")
        scores = [
            balanced_group_mean(expert_mse[mask, expert], groups[mask])
            for expert in range(5)
        ]
        selected[organ_index] = int(np.argmin(scores))
    return selected


def _parse_seed_paths(values: Sequence[str], *, name: str) -> dict[int, Path]:
    output: dict[int, Path] = {}
    for raw in values:
        if "=" not in raw:
            raise ValueError(f"{name} must use SEED=PATH syntax")
        seed_raw, path_raw = raw.split("=", 1)
        seed = int(seed_raw)
        if seed in output:
            raise ValueError(f"duplicate {name} seed {seed}")
        output[seed] = Path(path_raw)
    if set(output) != set(EXPECTED_SEEDS):
        raise ValueError(f"{name} seeds must be exactly {EXPECTED_SEEDS}")
    return output


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    protocol_path = Path(args.protocol)
    router_path = Path(args.router_artifact)
    router_report_path = Path(args.router_report)
    sealed_path = Path(args.sealed_test_assignments)
    sealed_report_path = Path(args.sealed_test_report)
    for path in (protocol_path, router_path, router_report_path, sealed_path, sealed_report_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    protocol = json.loads(protocol_path.read_text())
    if protocol.get("track_a_k5_internal_replication", {}).get("immutable") is not True:
        raise ValueError("protocol does not freeze immutable Track A")
    if protocol.get("evidence_label", {}).get("independent_confirmation") is not False:
        raise ValueError("protocol mislabels the internal replication")
    router_report = json.loads(router_report_path.read_text())
    if router_report.get("status") != "complete" or router_report.get("test_accessed") is not False:
        raise ValueError("router was not frozen without test access")
    if _read_report_hash(router_report, ("router_artifact_sha256",)) != _sha256_file(router_path):
        raise ValueError("router artifact hash differs from router report")
    sealed_report = json.loads(sealed_report_path.read_text())
    expected_sealed_hash = _read_report_hash(
        sealed_report, ("sealed_test_assignments_sha256", "artifact_sha256")
    )
    if expected_sealed_hash != _sha256_file(sealed_path):
        raise ValueError("sealed test assignment hash differs from its report")

    run_paths = _parse_seed_paths(args.bank_run, name="bank-run")
    cache_paths = _parse_seed_paths(args.test_cache, name="test-cache")
    organ_banks = {
        seed: _load_bank(path / "banks" / "organ_k5", axis="organ_k5", seed=seed)
        for seed, path in run_paths.items()
    }
    random_banks = {
        seed: _load_bank(path / "banks" / "random_k5", axis="random_k5", seed=seed)
        for seed, path in run_paths.items()
    }
    group_random_banks = {
        axis: {
            seed: _load_bank(path / "banks" / axis, axis=axis, seed=seed)
            for seed, path in run_paths.items()
        }
        for axis in GROUP_RANDOM_AXES
    }
    calibration_alignment = _validate_bank_alignment(organ_banks, random_banks)
    for axis in GROUP_RANDOM_AXES:
        _validate_bank_alignment(organ_banks, group_random_banks[axis])
    caches = {seed: _load_cache(path, seed=seed) for seed, path in cache_paths.items()}
    for seed in EXPECTED_SEEDS:
        cached_banks = caches[seed]["report"].get("banks", {})
        for axis in ("organ_k5", "random_k5", *GROUP_RANDOM_AXES):
            if axis == "organ_k5":
                current_bank = organ_banks[seed]
            elif axis == "random_k5":
                current_bank = random_banks[seed]
            else:
                current_bank = group_random_banks[axis][seed]
            cached = cached_banks.get(axis)
            if not isinstance(cached, dict):
                raise ValueError(
                    f"test cache lacks checkpoint binding for {axis}, seed {seed}"
                )
            bank_dir = run_paths[seed] / "banks" / axis
            expected_binding = {
                "final_experts_sha256": _sha256_file(
                    bank_dir / "final_experts.pt"
                ),
                "run_metadata_sha256": _sha256_file(
                    bank_dir / "run_metadata.json"
                ),
            }
            for name, expected in expected_binding.items():
                if cached.get(name) != expected:
                    raise ValueError(
                        f"test cache {axis} {name} differs from current bank, "
                        f"seed {seed}"
                    )
    normalized = [caches[seed] for seed in EXPECTED_SEEDS]
    test_alignment = validate_alignment(normalized)
    invariant_cache_arrays = (
        "organ_labels",
        "random_labels",
        "target_masked",
        "baseline_masked",
        "pooled_masked",
        "blind_k5_probabilities",
        "blind_k5_predicted_organ",
        "k5_full_classes",
        *[f"{axis}_labels" for axis in GROUP_RANDOM_AXES],
    )
    reference_cache = normalized[0]["arrays"]
    for run in normalized[1:]:
        for name in invariant_cache_arrays:
            reference_value = np.asarray(reference_cache[name])
            observed_value = np.asarray(run["arrays"][name])
            if reference_value.dtype.kind in {"U", "S", "O"}:
                matches = np.array_equal(
                    reference_value.astype(str), observed_value.astype(str)
                )
            else:
                matches = np.allclose(
                    reference_value,
                    observed_value,
                    rtol=1e-7,
                    atol=1e-10,
                    equal_nan=False,
                )
            if not matches:
                raise ValueError(f"seed-invariant test cache array {name} differs")
    expected_protocol_hash = _sha256_file(protocol_path)
    expected_router_hash = _sha256_file(router_path)
    expected_sealed = _sha256_file(sealed_path)
    if test_alignment["fingerprints"]["protocol_sha256"] != expected_protocol_hash:
        raise ValueError("test caches used a different protocol")
    if test_alignment["fingerprints"]["router_artifact_sha256"] != expected_router_hash:
        raise ValueError("test caches used a different router")
    if test_alignment["fingerprints"]["sealed_test_assignments_sha256"] != expected_sealed:
        raise ValueError("test caches used different sealed assignments")

    groups = normalized[0]["groups"]
    organs = normalized[0]["organs"]
    condition_predictions: dict[int, dict[str, np.ndarray]] = {}
    condition_mse: dict[str, dict[int, np.ndarray]] = {}
    condition_residual: dict[str, dict[int, np.ndarray]] = {}
    selected_random: dict[int, dict[str, list[int]]] = {}
    router_accuracy: dict[int, float] = {}
    for seed in EXPECTED_SEEDS:
        choices = {
            "random_k5": _selected_random_experts(random_banks[seed]),
            **{
                axis: _selected_random_experts(group_random_banks[axis][seed])
                for axis in GROUP_RANDOM_AXES
            },
        }
        selected_random[seed] = {
            axis: values.tolist() for axis, values in choices.items()
        }
        fixed_weights = {
            "organ_k5": organ_banks[seed]["full_calibration_fixed_weights"],
            "random_k5": random_banks[seed]["full_calibration_fixed_weights"],
            **{
                axis: group_random_banks[axis][seed][
                    "full_calibration_fixed_weights"
                ]
                for axis in GROUP_RANDOM_AXES
            },
        }
        predictions = _condition_predictions(
            caches[seed], choices, fixed_weights
        )
        condition_predictions[seed] = predictions
        target = caches[seed]["arrays"]["target_masked"].astype(np.float64)
        baseline = caches[seed]["arrays"]["baseline_masked"].astype(np.float64)
        true_names = caches[seed]["arrays"]["organs"].astype(str)
        predicted_names = caches[seed]["arrays"]["blind_k5_predicted_organ"].astype(str)
        router_accuracy[seed] = balanced_group_mean(
            (predicted_names == true_names).astype(float), groups, organs
        )
        for name, prediction in predictions.items():
            condition_mse.setdefault(name, {})[seed] = np.square(
                prediction - target
            ).mean(axis=1)
            condition_residual.setdefault(name, {})[seed] = pearson_rows(
                prediction - baseline, target - baseline
            )

    comparisons = {
        "blind_organ_hard_vs_pooled": comparison(
            condition_mse["pooled"], condition_mse["blind_organ_hard"],
            groups, organs, EXPECTED_SEEDS,
            bootstrap_seed=args.bootstrap_seed + 1,
            bootstrap_reps=args.bootstrap_reps,
        ),
        "true_organ_hard_vs_pooled": comparison(
            condition_mse["pooled"], condition_mse["true_organ_hard"],
            groups, organs, EXPECTED_SEEDS,
            bootstrap_seed=args.bootstrap_seed + 2,
            bootstrap_reps=args.bootstrap_reps,
        ),
    }
    assigned_group_comparisons = {
        axis: comparison(
            condition_mse[f"{axis}_assigned_hard"],
            condition_mse["true_organ_hard"],
            groups, organs, EXPECTED_SEEDS,
            bootstrap_seed=args.bootstrap_seed + 30 + index,
            bootstrap_reps=args.bootstrap_reps,
        )
        for index, axis in enumerate(GROUP_RANDOM_AXES)
    }
    selected_group_comparisons = {
        axis: comparison(
            condition_mse[f"{axis}_calibration_selected_by_organ"],
            condition_mse["true_organ_hard"],
            groups, organs, EXPECTED_SEEDS,
            bootstrap_seed=args.bootstrap_seed + 40 + index,
            bootstrap_reps=args.bootstrap_reps,
        )
        for index, axis in enumerate(GROUP_RANDOM_AXES)
    }
    comparisons["true_organ_hard_vs_assigned_random_k5"] = (
        _conservative_random_family(assigned_group_comparisons)
    )
    comparisons["true_organ_hard_vs_calibration_selected_random"] = (
        _conservative_random_family(selected_group_comparisons)
    )
    comparisons["legacy_true_organ_vs_row_random_assigned_non_gating"] = comparison(
        condition_mse["legacy_assigned_random_k5_hard"],
        condition_mse["true_organ_hard"],
        groups, organs, EXPECTED_SEEDS,
        bootstrap_seed=args.bootstrap_seed + 50,
        bootstrap_reps=args.bootstrap_reps,
    )
    comparisons["legacy_organ_fixed_vs_row_random_fixed_non_gating"] = comparison(
        condition_mse["legacy_random_full_calibration_fixed"],
        condition_mse["organ_full_calibration_fixed"],
        groups, organs, EXPECTED_SEEDS,
        bootstrap_seed=args.bootstrap_seed + 51,
        bootstrap_reps=args.bootstrap_reps,
    )
    comparisons["organ_fixed_vs_group_random_fixed_non_gating"] = {
        axis: comparison(
            condition_mse[f"{axis}_full_calibration_fixed"],
            condition_mse["organ_full_calibration_fixed"],
            groups, organs, EXPECTED_SEEDS,
            bootstrap_seed=args.bootstrap_seed + 60 + index,
            bootstrap_reps=args.bootstrap_reps,
        )
        for index, axis in enumerate(GROUP_RANDOM_AXES)
    }
    for key, candidate_name in (
        ("blind_organ_hard_vs_pooled", "blind_organ_hard"),
        ("true_organ_hard_vs_pooled", "true_organ_hard"),
    ):
        residual = _correlation_comparison(
            condition_residual["pooled"], condition_residual[candidate_name],
            groups, organs, EXPECTED_SEEDS,
            bootstrap_seed=args.bootstrap_seed + (11 if "blind" in key else 12),
            bootstrap_reps=args.bootstrap_reps,
        )
        comparisons[key]["residual_pearson"] = residual
        comparisons[key]["positive_residual_pearson_interval"] = residual[
            "positive_clustered_interval"
        ]

    true_gain = comparisons["true_organ_hard_vs_pooled"][
        "relative_mse_reduction_mean"
    ]
    blind_gain = comparisons["blind_organ_hard_vs_pooled"][
        "relative_mse_reduction_mean"
    ]
    recovery = float(blind_gain / true_gain) if true_gain > 0 else 0.0
    comparisons["blind_recovery_of_true_gain"] = recovery

    cal_groups = calibration_alignment["groups"]
    cal_organs = calibration_alignment["organs"]
    calibration_oracle = comparison(
        {seed: organ_banks[seed]["arrays"]["crossfit_fixed_mse"] for seed in EXPECTED_SEEDS},
        {seed: organ_banks[seed]["arrays"]["oracle_mse"] for seed in EXPECTED_SEEDS},
        cal_groups,
        cal_organs,
        EXPECTED_SEEDS,
        bootstrap_seed=args.bootstrap_seed + 20,
        bootstrap_reps=args.bootstrap_reps,
    )
    oracle_gate = _metric_gate(calibration_oracle, minimum_gain=0.03)
    maximum_exposure = max(
        bank["maximum_exposure_fractional_deviation"]
        for bank in (
            list(organ_banks.values())
            + list(random_banks.values())
            + [
                group_random_banks[axis][seed]
                for axis in GROUP_RANDOM_AXES
                for seed in EXPECTED_SEEDS
            ]
        )
    )
    technical_gates = {
        "provenance": True,
        "alignment": True,
        "router_frozen_before_test": True,
        "matched_k5_banks": True,
        "exposure": bool(maximum_exposure <= 0.05),
    }
    decision = track_a_decision(
        comparisons, oracle_gate=oracle_gate, technical_gates=technical_gates
    )

    conditions: dict[str, Any] = {}
    for name, per_seed in condition_mse.items():
        means = [
            balanced_group_mean(per_seed[seed], groups, organs)
            for seed in EXPECTED_SEEDS
        ]
        residual_means = [
            balanced_group_mean(condition_residual[name][seed], groups, organs)
            for seed in EXPECTED_SEEDS
        ]
        conditions[name] = {
            "balanced_mse_per_seed": [float(value) for value in means],
            "balanced_mse_mean": float(np.mean(means)),
            "balanced_residual_pearson_per_seed": [float(value) for value in residual_means],
            "balanced_residual_pearson_mean": float(np.mean(residual_means)),
            "natural_sample_weighted_mse_per_seed": [
                float(np.mean(per_seed[seed])) for seed in EXPECTED_SEEDS
            ],
            "natural_sample_weighted_mse_mean": float(np.mean([
                np.mean(per_seed[seed]) for seed in EXPECTED_SEEDS
            ])),
        }

    output_dir = Path(args.output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"confirmation output is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    score_artifact = output_dir / "decision_scores.npz"
    score_arrays: dict[str, np.ndarray] = {
        "sample_ids": normalized[0]["sample_ids"],
        "groups": groups,
        "organs": organs,
        "seeds": np.asarray(EXPECTED_SEEDS, dtype=np.int64),
    }
    for name, per_seed in condition_mse.items():
        score_arrays[f"{name}_mse"] = np.stack(
            [per_seed[seed] for seed in EXPECTED_SEEDS]
        )
        score_arrays[f"{name}_residual_pearson"] = np.stack(
            [condition_residual[name][seed] for seed in EXPECTED_SEEDS]
        )
    np.savez_compressed(score_artifact, **score_arrays)
    bank_artifact_hashes: dict[str, Any] = {}
    for seed in EXPECTED_SEEDS:
        bank_artifact_hashes[str(seed)] = {}
        for axis in ("organ_k5", "random_k5", *GROUP_RANDOM_AXES):
            bank_dir = run_paths[seed] / "banks" / axis
            bank_artifact_hashes[str(seed)][axis] = {
                "final_experts_sha256": _sha256_file(bank_dir / "final_experts.pt"),
                "calibration_scores_sha256": _sha256_file(
                    bank_dir / "calibration_scores.npz"
                ),
                "run_metadata_sha256": _sha256_file(bank_dir / "run_metadata.json"),
            }
    cache_artifact_hashes = {
        str(seed): {
            "test_scores_sha256": _sha256_file(
                cache_paths[seed] / "test_scores.npz"
            ),
            "test_score_report_sha256": _sha256_file(
                cache_paths[seed] / "test_score_report.json"
            ),
        }
        for seed in EXPECTED_SEEDS
    }
    report = {
        "schema_version": 1,
        "status": "complete",
        "experiment": "locked_internal_organ_k5_architecture_replication",
        "test_accessed": True,
        "internal_locked_replication": True,
        "independent_confirmation": False,
        "external_confirmation_required": True,
        "decision": decision,
        "conditions": conditions,
        "comparisons": comparisons,
        "calibration_oracle_vs_crossfit_fixed": calibration_oracle,
        "calibration_oracle_gate": oracle_gate,
        "blind_router_balanced_accuracy_per_seed": {
            str(seed): float(router_accuracy[seed]) for seed in EXPECTED_SEEDS
        },
        "calibration_selected_random_expert_by_organ": {
            str(seed): {
                axis: {
                    organ: int(selected_random[seed][axis][index])
                    for index, organ in enumerate(CANONICAL_ORGANS)
                }
                for axis in ("random_k5", *GROUP_RANDOM_AXES)
            }
            for seed in EXPECTED_SEEDS
        },
        "technical": {
            "gates": technical_gates,
            "maximum_exposure_fractional_deviation": maximum_exposure,
            "test_alignment": test_alignment,
            "calibration_samples": int(len(calibration_alignment["sample_ids"])),
            "bootstrap_reps": int(args.bootstrap_reps),
            "bootstrap_seed": int(args.bootstrap_seed),
        },
        "hashes": {
            "protocol_sha256": expected_protocol_hash,
            "router_artifact_sha256": expected_router_hash,
            "router_report_sha256": _sha256_file(router_report_path),
            "sealed_test_assignments_sha256": expected_sealed,
            "sealed_test_report_sha256": _sha256_file(sealed_report_path),
            "decision_scores_sha256": _sha256_file(score_artifact),
            "evaluator_source_sha256": _sha256_file(Path(__file__)),
        },
        "inputs": {
            "bank_runs": {str(seed): str(run_paths[seed]) for seed in EXPECTED_SEEDS},
            "test_caches": {str(seed): str(cache_paths[seed]) for seed in EXPECTED_SEEDS},
            "bank_artifact_hashes": bank_artifact_hashes,
            "test_cache_artifact_hashes": cache_artifact_hashes,
        },
        "interpretation_guardrail": (
            "The test cohort was inspected in prior Stage 1 work. This result may "
            "validate the architecture internally but cannot establish independent "
            "biological confirmation; a new external lockbox remains required."
        ),
    }
    _atomic_json(output_dir / "report.json", report)
    (output_dir / "COMPLETE").touch()
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--router-artifact", required=True)
    parser.add_argument("--router-report", required=True)
    parser.add_argument("--sealed-test-assignments", required=True)
    parser.add_argument("--sealed-test-report", required=True)
    parser.add_argument("--bank-run", action="append", required=True, help="SEED=PATH")
    parser.add_argument("--test-cache", action="append", required=True, help="SEED=PATH")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--bootstrap-reps", type=int, default=2000)
    parser.add_argument("--bootstrap-seed", type=int, default=424242)
    return parser


def main() -> None:
    report = evaluate(build_parser().parse_args())
    print(json.dumps({
        "status": report["status"],
        "decision": report["decision"],
        "independent_confirmation": report["independent_confirmation"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
