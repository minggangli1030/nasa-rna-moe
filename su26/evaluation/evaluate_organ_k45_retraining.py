#!/usr/bin/env python3
"""Evaluate the calibration-only genuine K4/K5 retraining experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import torch

from evaluate_organ_k_confirmation import comparison, _sha256_file
from evaluate_organ_k_search import _one_sided_cluster_p, holm_adjust
from headroom_metrics import balanced_group_mean


SEEDS = (17, 42, 101)
RANDOM_SEEDS = (17, 42, 101)
ARMS = {
    "k5": {
        "organ_axis": "organ_k5",
        "random_axes": tuple(f"random_group_k5_p{seed}" for seed in RANDOM_SEEDS),
        "k": 5,
        "updates": 1500,
        "target_exposures": 2400,
    },
    "k4_epe": {
        "organ_axis": "organ_k4_epe",
        "random_axes": tuple(
            f"random_group_k4_epe_p{seed}" for seed in RANDOM_SEEDS
        ),
        "k": 4,
        "updates": 1500,
        "target_exposures": 2400,
    },
    "k4_total_active": {
        "organ_axis": "organ_k4_total_active",
        "random_axes": tuple(
            f"random_group_k4_total_active_p{seed}" for seed in RANDOM_SEEDS
        ),
        "k": 4,
        "updates": 1875,
        "target_exposures": 3000,
    },
}
REQUIRED_ARRAYS = (
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


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _tensor_state_sha256(state: Mapping[str, torch.Tensor]) -> str:
    digest = hashlib.sha256()
    for name in sorted(state):
        value = state[name].detach().cpu().contiguous()
        digest.update(name.encode("utf-8"))
        digest.update(str(value.dtype).encode("utf-8"))
        digest.update(np.asarray(value.shape, dtype=np.int64).tobytes())
        digest.update(value.numpy().tobytes())
    return digest.hexdigest()


def _parse_seed_paths(values: list[str]) -> dict[int, Path]:
    output: dict[int, Path] = {}
    for raw in values:
        if "=" not in raw:
            raise ValueError("bank-run must use SEED=PATH")
        seed_raw, path_raw = raw.split("=", 1)
        seed = int(seed_raw)
        if seed in output:
            raise ValueError(f"duplicate bank-run seed {seed}")
        output[seed] = Path(path_raw)
    if tuple(sorted(output)) != SEEDS:
        raise ValueError(f"bank-run seeds must be exactly {SEEDS}")
    return output


def _load_bank(
    path: Path,
    *,
    axis: str,
    seed: int,
    expected_k: int,
    expected_updates: int,
    expected_target: int,
    expected_hashes: Mapping[str, str],
) -> dict[str, Any]:
    metadata_path = path / "run_metadata.json"
    score_path = path / "calibration_scores.npz"
    if not (path / "COMPLETE").is_file() or not metadata_path.is_file() or not score_path.is_file():
        raise ValueError(f"incomplete bank: {path}")
    metadata = json.loads(metadata_path.read_text())
    if (
        metadata.get("status") != "complete"
        or metadata.get("test_accessed") is not False
        or metadata.get("mechanical_only") is not False
        or metadata.get("axis") != axis
        or metadata.get("training_seed") != seed
    ):
        raise ValueError(f"invalid bank state: {path}")
    config = metadata.get("config", {})
    if (
        int(config.get("num_experts", -1)) != expected_k
        or int(config.get("final_update", -1)) != expected_updates
        or int(config.get("exposures_per_expert_target", -1)) != expected_target
        or config.get("checkpoint_policy") != "predetermined_final_update"
    ):
        raise ValueError(f"bank configuration differs from frozen arm: {path}")
    hashes = metadata.get("hashes", {})
    for key, expected in expected_hashes.items():
        if hashes.get(key) != expected:
            raise ValueError(f"bank {key} differs: {path}")
    if hashes.get("resolved_config_sha256") != _sha256_json(config):
        raise ValueError(f"bank resolved config hash differs: {path}")
    if metadata.get("artifacts", {}).get("calibration_scores_sha256") != _sha256_file(score_path):
        raise ValueError(f"bank calibration score hash differs: {path}")
    checkpoint_path = path / "final_experts.pt"
    if metadata.get("artifacts", {}).get("final_experts_sha256") != _sha256_file(checkpoint_path):
        raise ValueError(f"bank final checkpoint hash differs: {path}")
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    checkpoint_state = checkpoint.get("expert_state_dict")
    if not isinstance(checkpoint_state, dict):
        raise ValueError(f"bank final checkpoint lacks expert state: {path}")
    checkpoint_hashes = []
    for index in range(expected_k):
        prefix = f"experts.{index}."
        expert_state = {
            key[len(prefix):]: value
            for key, value in checkpoint_state.items()
            if key.startswith(prefix)
        }
        if not expert_state:
            raise ValueError(f"bank checkpoint lacks expert {index}: {path}")
        checkpoint_hashes.append(_tensor_state_sha256(expert_state))
    if checkpoint_hashes != metadata.get("artifacts", {}).get("expert_state_sha256"):
        raise ValueError(f"bank expert state hashes differ from checkpoint: {path}")
    realized = np.asarray(config.get("realized_exposure_counts", []), dtype=np.float64)
    if realized.shape != (expected_k,) or not np.isfinite(realized).all():
        raise ValueError(f"bank exposure accounting is invalid: {path}")
    deviation = float(np.max(np.abs(realized - expected_target) / expected_target))
    expert_hashes = metadata.get("artifacts", {}).get("expert_state_sha256")
    expert_keys = config.get("expert_initialization_keys")
    if (
        not isinstance(expert_hashes, list)
        or len(expert_hashes) != expected_k
        or not all(isinstance(value, str) and len(value) == 64 for value in expert_hashes)
        or not isinstance(expert_keys, list)
        or len(expert_keys) != expected_k
    ):
        raise ValueError(f"bank expert identity/hash accounting is invalid: {path}")
    with np.load(score_path, allow_pickle=False) as archive:
        missing = sorted(set(REQUIRED_ARRAYS) - set(archive.files))
        if missing:
            raise ValueError(f"bank lacks calibration arrays {missing}: {path}")
        arrays = {name: archive[name].copy() for name in REQUIRED_ARRAYS}
    count = len(arrays["sample_ids"])
    if arrays["expert_mse"].shape != (count, expected_k):
        raise ValueError(f"bank expert MSE shape is invalid: {path}")
    if any(np.asarray(arrays[name]).shape[0] != count for name in REQUIRED_ARRAYS):
        raise ValueError(f"bank calibration arrays are misaligned: {path}")
    labels = arrays["true_labels"].astype(np.int64)
    fallback = config.get("fallback_label")
    if fallback is None:
        if not np.array_equal(np.unique(labels), np.arange(expected_k)):
            raise ValueError(f"bank labels do not cover K without fallback: {path}")
    elif fallback != -1 or not np.array_equal(
        np.unique(labels[labels >= 0]), np.arange(expected_k)
    ):
        raise ValueError(f"bank fallback labels are invalid: {path}")
    return {
        "axis": axis,
        "seed": seed,
        "metadata": metadata,
        "arrays": arrays,
        "exposure_deviation": deviation,
        "expert_hash_by_key": dict(zip(expert_keys, expert_hashes)),
        "path": str(path),
    }


def _load_router(path: Path, report_path: Path) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    if not path.is_file() or not report_path.is_file():
        raise FileNotFoundError(path if not path.is_file() else report_path)
    report = json.loads(report_path.read_text())
    if (
        report.get("status") != "complete"
        or report.get("test_accessed") is not False
        or report.get("test_features_loaded") is not False
        or report.get("target_hiding", {}).get("score_genes_masked_for_every_sample") is not True
    ):
        raise ValueError("router report violates the development firewall")
    if report.get("hashes", {}).get("router_artifact_sha256") != _sha256_file(path):
        raise ValueError("router artifact differs from its report")
    with np.load(path, allow_pickle=False) as archive:
        required = {
            "calibration_sample_ids",
            "calibration_organs",
            "calibration_series_group_id",
            "crossfit_fold",
            "k5_crossfit_classes",
            "k5_crossfit_probabilities",
        }
        missing = sorted(required - set(archive.files))
        if missing:
            raise ValueError(f"router artifact lacks arrays: {missing}")
        arrays = {name: archive[name].copy() for name in required}
    probabilities = arrays["k5_crossfit_probabilities"].astype(np.float64)
    if probabilities.shape != (len(arrays["calibration_sample_ids"]), 5):
        raise ValueError("router probability shape is invalid")
    if not np.isfinite(probabilities).all() or not np.allclose(
        probabilities.sum(axis=1), 1.0, atol=1e-8
    ):
        raise ValueError("router probabilities are invalid")
    return arrays, report


def _routed_mse(
    pooled: np.ndarray,
    experts: np.ndarray,
    predicted_names: np.ndarray,
    label_names: list[str],
) -> np.ndarray:
    pooled = np.asarray(pooled, dtype=np.float64)
    experts = np.asarray(experts, dtype=np.float64)
    predicted_names = np.asarray(predicted_names).astype(str)
    if experts.shape != (len(pooled), len(label_names)):
        raise ValueError("routed expert arrays do not align")
    mapping = {name: index for index, name in enumerate(label_names)}
    output = pooled.copy()
    for name, index in mapping.items():
        rows = np.flatnonzero(predicted_names == name)
        output[rows] = experts[rows, index]
    unexpected = set(predicted_names) - set(label_names) - {"adipose"}
    if unexpected:
        raise ValueError(f"router predicted unknown classes: {sorted(unexpected)}")
    return output


def _relative_penalty_interval(
    k4: Mapping[int, np.ndarray],
    k5: Mapping[int, np.ndarray],
    groups: np.ndarray,
    organs: np.ndarray,
    *,
    seed: int,
    reps: int,
) -> dict[str, Any]:
    k4_matrix = np.stack([np.asarray(k4[value], dtype=np.float64) for value in SEEDS])
    k5_matrix = np.stack([np.asarray(k5[value], dtype=np.float64) for value in SEEDS])
    if k4_matrix.shape != k5_matrix.shape or k4_matrix.shape[1] != len(groups):
        raise ValueError("noninferiority arrays do not align")
    mean_k4 = k4_matrix.mean(axis=0)
    mean_k5 = k5_matrix.mean(axis=0)
    groups = np.asarray(groups).astype(str)
    organs = np.asarray(organs).astype(str)
    for group in np.unique(groups):
        if len(np.unique(organs[groups == group])) != 1:
            raise ValueError("a bootstrap group spans organs")
    observed_k4 = balanced_group_mean(mean_k4, groups, organs)
    observed_k5 = balanced_group_mean(mean_k5, groups, organs)
    observed = float((observed_k4 - observed_k5) / observed_k5)
    buckets: dict[str, dict[str, tuple[float, float]]] = {}
    for organ in np.unique(organs):
        in_organ = organs == organ
        buckets[organ] = {
            group: (
                float(mean_k4[in_organ & (groups == group)].mean()),
                float(mean_k5[in_organ & (groups == group)].mean()),
            )
            for group in np.unique(groups[in_organ])
        }
    rng = np.random.default_rng(seed)
    estimates = np.empty(reps, dtype=np.float64)
    for index in range(reps):
        organ_k4: list[float] = []
        organ_k5: list[float] = []
        for grouped in buckets.values():
            names = np.asarray(list(grouped), dtype=object)
            draw = rng.choice(names, size=len(names), replace=True)
            organ_k4.append(float(np.mean([grouped[name][0] for name in draw])))
            organ_k5.append(float(np.mean([grouped[name][1] for name in draw])))
        draw_k4 = float(np.mean(organ_k4))
        draw_k5 = float(np.mean(organ_k5))
        estimates[index] = (draw_k4 - draw_k5) / draw_k5
    low, high = np.quantile(estimates, [0.025, 0.975])
    per_seed = []
    for row in range(len(SEEDS)):
        value4 = balanced_group_mean(k4_matrix[row], groups, organs)
        value5 = balanced_group_mean(k5_matrix[row], groups, organs)
        per_seed.append(float((value4 - value5) / value5))
    return {
        "relative_mse_penalty": observed,
        "relative_mse_penalty_per_seed": per_seed,
        "paired_clustered_interval_95": [float(low), float(high)],
        "simultaneous_one_sided_upper_97_5": float(high),
    }


def decide(
    support: dict[str, bool],
    noninferiority: dict[str, bool],
) -> dict[str, Any]:
    if set(support) != set(ARMS) or set(noninferiority) != {"k4_epe", "k4_total_active"}:
        raise ValueError("decision inputs do not cover frozen arms")
    if not any(support.values()):
        branch = "no_supported_split"
        selected = None
    elif (
        support["k4_total_active"]
        and support["k4_epe"]
        and noninferiority["k4_total_active"]
        and noninferiority["k4_epe"]
    ):
        branch = "k4_robust"
        selected = "k4_epe"
    elif support["k4_total_active"] and noninferiority["k4_total_active"]:
        branch = "k4_budget_dependent"
        selected = "k4_total_active"
    elif support["k5"] and (
        not support["k4_total_active"] or not noninferiority["k4_total_active"]
    ):
        branch = "k5_retained"
        selected = "k5"
    elif support["k4_epe"] and noninferiority["k4_epe"]:
        branch = "k4_efficient"
        selected = "k4_epe"
    else:
        branch = "inconclusive"
        selected = None
    return {
        "decision_branch": branch,
        "selected_candidate_for_future_freeze": selected,
        "support_gates": support,
        "noninferiority_gates": noninferiority,
        "development_only": True,
        "test_accessed": False,
        "automatic_external_test_authorization": False,
    }


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    protocol_path = Path(args.protocol)
    partition_report_path = Path(args.partition_report)
    router_path = Path(args.router_artifact)
    router_report_path = Path(args.router_report)
    for path in (protocol_path, partition_report_path, router_path, router_report_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    protocol = json.loads(protocol_path.read_text())
    if (
        protocol.get("evidence_label", {}).get("development_only") is not True
        or protocol.get("firewall", {}).get("test_access_allowed") is not False
        or protocol.get("firewall", {}).get("test_cache_allowed") is not False
    ):
        raise ValueError("protocol does not enforce development-only evaluation")
    partition_report = json.loads(partition_report_path.read_text())
    if (
        partition_report.get("status") != "complete"
        or partition_report.get("test_accessed") is not False
        or partition_report.get("development_only") is not True
    ):
        raise ValueError("partition report violates the test firewall")
    protocol_hash = _sha256_file(protocol_path)
    partition_hash = partition_report.get("hashes", {}).get("partition_manifest_sha256")
    if partition_report.get("hashes", {}).get("protocol_sha256") != protocol_hash:
        raise ValueError("partition report used a different protocol")
    router, router_report = _load_router(router_path, router_report_path)
    firewall = protocol["score_firewall"]
    if _sha256_file(router_path) != firewall["router_artifact_sha256"]:
        raise ValueError("router artifact differs from the frozen protocol")
    if _sha256_file(router_report_path) != firewall["router_report_sha256"]:
        raise ValueError("router report differs from the frozen protocol")

    run_paths = _parse_seed_paths(args.bank_run)
    frozen_hashes = {
        "protocol_sha256": protocol_hash,
        "partition_manifest_sha256": str(partition_hash),
        "partition_report_sha256": _sha256_file(partition_report_path),
        "pooled_checkpoint_sha256": str(protocol["frozen_trunk"]["sha256"]),
        "expression_sha256": str(protocol["data"]["expression_sha256"]),
        "manifest_sha256": str(protocol["data"]["manifest_sha256"]),
        "axis_definitions_sha256": str(protocol["score_firewall"]["axis_definitions_sha256"]),
    }
    banks: dict[str, dict[int, dict[str, Any]]] = {}
    for arm_name, arm in ARMS.items():
        axes = (arm["organ_axis"], *arm["random_axes"])
        for axis in axes:
            banks[axis] = {
                seed: _load_bank(
                    run_paths[seed] / "banks" / axis,
                    axis=axis,
                    seed=seed,
                    expected_k=int(arm["k"]),
                    expected_updates=int(arm["updates"]),
                    expected_target=int(arm["target_exposures"]),
                    expected_hashes=frozen_hashes,
                )
                for seed in SEEDS
            }

    bank_provenance = {
        axis: {
            str(seed): {
                "path": bank["path"],
                "metadata_sha256": _sha256_file(Path(bank["path"]) / "run_metadata.json"),
                "calibration_scores_sha256": bank["metadata"]["artifacts"]["calibration_scores_sha256"],
                "final_experts_sha256": bank["metadata"]["artifacts"]["final_experts_sha256"],
                "expert_state_sha256": bank["metadata"]["artifacts"]["expert_state_sha256"],
            }
            for seed, bank in seed_banks.items()
        }
        for axis, seed_banks in banks.items()
    }

    reference = banks["organ_k5"][SEEDS[0]]["arrays"]
    sample_ids = reference["sample_ids"].astype(str)
    groups = reference["groups"].astype(str)
    organs = reference["organs"].astype(str)
    weights = reference["sample_weights"].astype(np.float64)
    for axis_banks in banks.values():
        for bank in axis_banks.values():
            arrays = bank["arrays"]
            for name, expected_values in (
                ("sample_ids", sample_ids),
                ("groups", groups),
                ("organs", organs),
            ):
                if not np.array_equal(arrays[name].astype(str), expected_values):
                    raise ValueError(f"calibration {name} differs across banks")
            if not np.allclose(arrays["sample_weights"], weights, atol=1e-15, rtol=0):
                raise ValueError("calibration sample weights differ across banks")
            if not np.allclose(arrays["pooled_mse"], reference["pooled_mse"], atol=1e-8, rtol=1e-7):
                raise ValueError("pooled calibration MSE differs across banks")
    if not np.array_equal(router["calibration_sample_ids"].astype(str), sample_ids):
        raise ValueError("router sample IDs differ from banks")
    if not np.array_equal(router["calibration_organs"].astype(str), organs):
        raise ValueError("router organs differ from banks")
    if not np.array_equal(router["calibration_series_group_id"].astype(str), groups):
        raise ValueError("router groups differ from banks")
    classes = router["k5_crossfit_classes"].astype(str)
    probabilities = router["k5_crossfit_probabilities"].astype(np.float64)
    predicted_names = classes[np.argmax(probabilities, axis=1)]

    # The paired EPE audit must reproduce every shared semantic organ expert.
    shared_hash_equal = True
    shared_hash_details: dict[str, dict[str, bool]] = {}
    expected_k5_keys = [
        "organ:adipose", "organ:brain", "organ:liver", "organ:skeletal_muscle", "organ:skin"
    ]
    expected_k4_keys = [
        "organ:brain", "organ:liver", "organ:skeletal_muscle", "organ:skin"
    ]
    for seed in SEEDS:
        if banks["organ_k5"][seed]["metadata"]["config"]["expert_initialization_keys"] != expected_k5_keys:
            raise ValueError("organ K5 semantic expert keys differ from protocol")
        for axis in ("organ_k4_epe", "organ_k4_total_active"):
            if banks[axis][seed]["metadata"]["config"]["expert_initialization_keys"] != expected_k4_keys:
                raise ValueError(f"{axis} semantic expert keys differ from protocol")
        if banks["organ_k4_epe"][seed]["metadata"]["config"]["expert_initialization_keys"] != banks["organ_k4_total_active"][seed]["metadata"]["config"]["expert_initialization_keys"]:
            raise ValueError("K4 budget arms do not reuse semantic expert keys")
        k5_hashes = banks["organ_k5"][seed]["expert_hash_by_key"]
        k4_hashes = banks["organ_k4_epe"][seed]["expert_hash_by_key"]
        shared = sorted(set(k5_hashes) & set(k4_hashes))
        if len(shared) != 4:
            raise ValueError("K4/K5 semantic initialization keys do not share four experts")
        shared_hash_details[str(seed)] = {
            key: bool(k5_hashes[key] == k4_hashes[key]) for key in shared
        }
        shared_hash_equal &= all(shared_hash_details[str(seed)].values())
        for epe_axis, total_axis in zip(
            ARMS["k4_epe"]["random_axes"], ARMS["k4_total_active"]["random_axes"]
        ):
            if banks[epe_axis][seed]["metadata"]["config"]["expert_initialization_keys"] != banks[total_axis][seed]["metadata"]["config"]["expert_initialization_keys"]:
                raise ValueError(f"matched random K4 initialization keys differ for {epe_axis}")
            if not np.array_equal(
                banks[epe_axis][seed]["arrays"]["true_labels"],
                banks[total_axis][seed]["arrays"]["true_labels"],
            ):
                raise ValueError(f"matched random K4 assignments differ for {epe_axis}")

    pooled_by_seed = {
        seed: banks["organ_k5"][seed]["arrays"]["pooled_mse"].astype(np.float64)
        for seed in SEEDS
    }
    arm_results: dict[str, Any] = {}
    blind_by_arm: dict[str, dict[int, np.ndarray]] = {}
    raw_pooled_p: list[float] = []
    raw_random_p: list[float] = []
    random_p_locations: list[tuple[str, str]] = []
    audit_arrays: dict[str, np.ndarray] = {
        "sample_ids": sample_ids,
        "groups": groups,
        "organs": organs,
        "router_predicted_organ": predicted_names,
        "seeds": np.asarray(SEEDS, dtype=np.int64),
    }
    for arm_index, (arm_name, arm) in enumerate(ARMS.items()):
        organ_axis = str(arm["organ_axis"])
        label_names = partition_report["axes"][organ_axis]["label_names"]
        blind = {
            seed: _routed_mse(
                pooled_by_seed[seed],
                banks[organ_axis][seed]["arrays"]["expert_mse"],
                predicted_names,
                label_names,
            )
            for seed in SEEDS
        }
        true = {
            seed: banks[organ_axis][seed]["arrays"]["true_partition_mse"].astype(np.float64)
            for seed in SEEDS
        }
        oracle = {}
        for seed in SEEDS:
            arrays = banks[organ_axis][seed]["arrays"]
            labels = arrays["true_labels"].astype(np.int64)
            oracle[seed] = np.where(
                labels < 0,
                pooled_by_seed[seed],
                arrays["oracle_mse"].astype(np.float64),
            )
        blind_by_arm[arm_name] = blind
        blind_vs_pooled = comparison(
            pooled_by_seed, blind, groups, organs, SEEDS,
            bootstrap_seed=args.bootstrap_seed + 100 + arm_index,
            bootstrap_reps=args.bootstrap_reps,
        )
        true_vs_pooled = comparison(
            pooled_by_seed, true, groups, organs, SEEDS,
            bootstrap_seed=args.bootstrap_seed + 200 + arm_index,
            bootstrap_reps=args.bootstrap_reps,
        )
        pooled_matrix = np.stack([pooled_by_seed[seed] for seed in SEEDS])
        blind_matrix = np.stack([blind[seed] for seed in SEEDS])
        pooled_p, pooled_ci = _one_sided_cluster_p(
            (pooled_matrix - blind_matrix).mean(axis=0),
            groups,
            organs,
            seed=args.bootstrap_seed + 300 + arm_index,
            n_bootstrap=args.bootstrap_reps,
        )
        raw_pooled_p.append(pooled_p)
        random_comparisons: dict[str, Any] = {}
        random_tests: dict[str, Any] = {}
        for partition_index, random_axis in enumerate(arm["random_axes"]):
            random_true = {
                seed: banks[random_axis][seed]["arrays"]["true_partition_mse"].astype(np.float64)
                for seed in SEEDS
            }
            metric = comparison(
                random_true, true, groups, organs, SEEDS,
                bootstrap_seed=args.bootstrap_seed + 400 + 10 * arm_index + partition_index,
                bootstrap_reps=args.bootstrap_reps,
            )
            random_matrix = np.stack([random_true[seed] for seed in SEEDS])
            true_matrix = np.stack([true[seed] for seed in SEEDS])
            p_value, interval = _one_sided_cluster_p(
                (random_matrix - true_matrix).mean(axis=0),
                groups,
                organs,
                seed=args.bootstrap_seed + 500 + 10 * arm_index + partition_index,
                n_bootstrap=args.bootstrap_reps,
            )
            random_comparisons[random_axis] = metric
            random_tests[random_axis] = {
                "p_value": p_value,
                "clustered_ci95_absolute_improvement": list(interval),
            }
            raw_random_p.append(p_value)
            random_p_locations.append((arm_name, random_axis))
        exposure_deviation = max(
            banks[axis][seed]["exposure_deviation"]
            for axis in (organ_axis, *arm["random_axes"])
            for seed in SEEDS
        )
        arm_results[arm_name] = {
            "organ_axis": organ_axis,
            "k": arm["k"],
            "budget_view": partition_report["axes"][organ_axis]["budget_view"],
            "blind_vs_pooled": blind_vs_pooled,
            "true_vs_pooled": true_vs_pooled,
            "true_vs_assigned_random": random_comparisons,
            "random_partition_tests": random_tests,
            "oracle_mse_per_seed": [
                balanced_group_mean(oracle[seed], groups, organs) for seed in SEEDS
            ],
            "raw_p_vs_pooled": pooled_p,
            "sign_flip_ci95_vs_pooled": list(pooled_ci),
            "maximum_exposure_fractional_deviation": exposure_deviation,
        }
        audit_arrays[f"{arm_name}_blind_mse"] = blind_matrix
        audit_arrays[f"{arm_name}_true_mse"] = np.stack([true[seed] for seed in SEEDS])

    adjusted_pooled = holm_adjust(np.asarray(raw_pooled_p, dtype=np.float64))
    adjusted_random = holm_adjust(np.asarray(raw_random_p, dtype=np.float64))
    for index, arm_name in enumerate(ARMS):
        arm_results[arm_name]["adjusted_p_vs_pooled"] = float(adjusted_pooled[index])
    for index, (arm_name, random_axis) in enumerate(random_p_locations):
        arm_results[arm_name]["random_partition_tests"][random_axis][
            "adjusted_p_value"
        ] = float(adjusted_random[index])

    maximum_deviation = float(protocol["evaluation"]["maximum_exposure_fractional_deviation"])
    support: dict[str, bool] = {}
    support_details: dict[str, Any] = {}
    for arm_name, result in arm_results.items():
        blind_metric = result["blind_vs_pooled"]
        true_metric = result["true_vs_pooled"]
        random_metrics = result["true_vs_assigned_random"]
        random_tests = result["random_partition_tests"]
        details = {
            "blind_vs_pooled": bool(
                blind_metric["relative_mse_reduction_mean"] >= 0.03
                and blind_metric["positive_clustered_interval"]
                and blind_metric["same_positive_sign"]
                and blind_metric["seed_sd_fraction_of_mean"] <= 0.5
                and result["adjusted_p_vs_pooled"] <= 0.05
            ),
            "true_vs_pooled": bool(
                true_metric["relative_mse_reduction_mean"] >= 0.03
                and true_metric["positive_clustered_interval"]
                and true_metric["same_positive_sign"]
                and true_metric["seed_sd_fraction_of_mean"] <= 0.5
            ),
            "true_vs_every_random": bool(all(
                metric["relative_mse_reduction_mean"] >= 0.03
                and metric["positive_clustered_interval"]
                and metric["same_positive_sign"]
                and metric["seed_sd_fraction_of_mean"] <= 0.5
                and random_tests[axis]["adjusted_p_value"] <= 0.05
                for axis, metric in random_metrics.items()
            )),
            "exposure": bool(
                result["maximum_exposure_fractional_deviation"] <= maximum_deviation
            ),
        }
        support_details[arm_name] = details
        support[arm_name] = bool(all(details.values()))

    margin = float(protocol["evaluation"]["k4_noninferiority_margin_relative_mse"])
    ni_metrics = {
        arm_name: _relative_penalty_interval(
            blind_by_arm[arm_name], blind_by_arm["k5"], groups, organs,
            seed=args.bootstrap_seed + 700 + index,
            reps=args.bootstrap_reps,
        )
        for index, arm_name in enumerate(("k4_epe", "k4_total_active"))
    }
    ni_gates = {
        arm_name: bool(metric["simultaneous_one_sided_upper_97_5"] <= margin)
        for arm_name, metric in ni_metrics.items()
    }
    technical_gates = {
        "development_firewall": True,
        "alignment": True,
        "router_target_hidden": True,
        "shared_epe_experts_bitwise_equal": bool(shared_hash_equal),
    }
    decision = decide(support, ni_gates)
    if not all(technical_gates.values()):
        decision = {
            **decision,
            "decision_branch": "technical_fail",
            "selected_candidate_for_future_freeze": None,
        }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise FileExistsError(f"evaluation output is not empty: {output_dir}")
    scores_path = output_dir / "calibration_decision_scores.npz"
    np.savez_compressed(scores_path, **audit_arrays)
    report = {
        "schema_version": 1,
        "status": "complete",
        "experiment": "development_only_genuine_organ_k4_k5_retraining",
        "development_only": True,
        "adaptive_to_prior_calibration_selection": True,
        "test_accessed": False,
        "test_features_loaded": False,
        "test_targets_loaded": False,
        "independent_confirmation": False,
        "external_confirmation_required": True,
        "arms": arm_results,
        "support_gate_details": support_details,
        "noninferiority": {
            "margin_relative_mse": margin,
            "metrics": ni_metrics,
            "gates": ni_gates,
        },
        "technical_gates": technical_gates,
        "shared_epe_expert_hash_equality": shared_hash_details,
        "decision": decision,
        "interpretation_guardrail": (
            "This calibration cohort selected K4. The report is adaptive development "
            "and may freeze one future candidate, but it cannot confirm K or organ biology."
        ),
        "inputs": {
            "bank_runs": {str(seed): str(run_paths[seed]) for seed in SEEDS},
            "router_artifact": str(router_path),
            "partition_report": str(partition_report_path),
        },
        "bank_provenance": bank_provenance,
        "hashes": {
            "protocol_sha256": protocol_hash,
            "partition_report_sha256": _sha256_file(partition_report_path),
            "partition_manifest_sha256": partition_hash,
            "router_artifact_sha256": _sha256_file(router_path),
            "router_report_sha256": _sha256_file(router_report_path),
            "decision_scores_sha256": _sha256_file(scores_path),
            "evaluator_source_sha256": _sha256_file(Path(__file__)),
        },
    }
    _atomic_json(output_dir / "report.json", report)
    (output_dir / "COMPLETE").touch()
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--partition-report", required=True)
    parser.add_argument("--router-artifact", required=True)
    parser.add_argument("--router-report", required=True)
    parser.add_argument("--bank-run", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--bootstrap-reps", type=int, default=2000)
    parser.add_argument("--bootstrap-seed", type=int, default=616161)
    return parser


def main() -> None:
    report = evaluate(build_parser().parse_args())
    print(json.dumps({
        "status": report["status"],
        "development_only": report["development_only"],
        "test_accessed": report["test_accessed"],
        "decision": report["decision"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
