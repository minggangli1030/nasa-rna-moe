#!/usr/bin/env python3
"""Run the firewalled calibration-only search over deployed organ specialists K=1..5.

K is the number of the five known organs that receive a specialist.  All five
organs remain in the estimand and every unselected organ falls back to the
pooled trunk.  This program can nominate a K for a new confirmation; it cannot
authorize or inspect another test set.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from evaluate_organ_k_confirmation import (
    CANONICAL_ORGANS,
    EXPECTED_SEEDS,
    _load_bank,
    _parse_seed_paths,
    _sha256_file,
    _validate_bank_alignment,
    comparison,
)
from headroom_metrics import balanced_group_mean, paired_bootstrap_ci


SPECIALIST_ORDER = (
    "brain",
    "skin",
    "skeletal_muscle",
    "adipose",
    "liver",
)
GROUP_RANDOM_AXES = (
    "random_group_k5_p17",
    "random_group_k5_p42",
    "random_group_k5_p101",
)


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def apply_k_fallback(
    pooled: np.ndarray,
    experts: np.ndarray,
    assignments: np.ndarray,
    selected_experts: Sequence[int],
) -> np.ndarray:
    """Use assigned selected experts and copy pooled predictions otherwise."""
    pooled = np.asarray(pooled)
    experts = np.asarray(experts)
    assignments = np.asarray(assignments)
    if pooled.ndim != 2 or experts.ndim != 3:
        raise ValueError("pooled/experts must have shapes [N,M] and [N,K,M]")
    if experts.shape[0] != pooled.shape[0] or experts.shape[2] != pooled.shape[1]:
        raise ValueError("pooled and expert shapes do not align")
    if assignments.ndim != 1 or len(assignments) != len(pooled):
        raise ValueError("assignment vector does not align with samples")
    if not np.issubdtype(assignments.dtype, np.integer):
        raise ValueError("assignments must be integer expert indices")
    assignments = assignments.astype(np.int64, copy=False)
    if np.any(assignments < -1) or np.any(assignments >= experts.shape[1]):
        raise ValueError("assignment falls outside valid expert range")
    selected = [int(value) for value in selected_experts]
    if len(selected) != len(set(selected)):
        raise ValueError("selected experts contain a duplicate")
    if any(value < 0 or value >= experts.shape[1] for value in selected):
        raise ValueError("selected expert falls outside expert range")
    output = pooled.copy()
    selected_set = set(selected)
    use = np.asarray([value in selected_set for value in assignments], dtype=bool)
    rows = np.flatnonzero(use)
    if len(rows):
        output[rows] = experts[rows, assignments[rows]]
    return output


def holm_adjust(p_values: np.ndarray) -> np.ndarray:
    """Return Holm familywise adjusted p-values in their original order."""
    raw = np.asarray(p_values, dtype=np.float64)
    if raw.ndim != 1 or len(raw) == 0:
        raise ValueError("p-value family must be a nonempty vector")
    if not np.isfinite(raw).all():
        raise ValueError("p-values must be finite")
    if np.any(raw < 0) or np.any(raw > 1):
        raise ValueError("p-values must lie in [0, 1]")
    order = np.argsort(raw, kind="stable")
    sorted_raw = raw[order]
    adjusted_sorted = np.empty_like(sorted_raw)
    running = 0.0
    family_size = len(raw)
    for rank, value in enumerate(sorted_raw):
        running = max(running, (family_size - rank) * float(value))
        adjusted_sorted[rank] = min(1.0, running)
    adjusted = np.empty_like(adjusted_sorted)
    adjusted[order] = adjusted_sorted
    return adjusted


def select_k_one_se(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Choose the smallest viable K within one SE of the viable best mean."""
    by_k = {int(row["k"]): row for row in rows}
    if set(by_k) != set(range(1, 6)) or len(rows) != 5:
        raise ValueError("one-SE selection requires exactly K=1..5 candidates")
    eligible = sorted(
        k
        for k, row in by_k.items()
        if row.get("passes_pooled_holm") is True
        and row.get("passes_random_holm") is True
    )
    if not eligible:
        return {
            "eligible_k": [],
            "best_k": None,
            "best_mean_mse": None,
            "best_standard_error": None,
            "one_se_threshold": None,
            "within_one_se_k": [],
            "selected_k": None,
        }
    for k in eligible:
        mean = float(by_k[k]["mean_mse"])
        standard_error = float(by_k[k]["standard_error"])
        if not np.isfinite(mean) or not np.isfinite(standard_error) or standard_error < 0:
            raise ValueError("candidate mean/standard error is invalid")
    best_k = min(eligible, key=lambda k: (float(by_k[k]["mean_mse"]), k))
    best_mean = float(by_k[best_k]["mean_mse"])
    best_se = float(by_k[best_k]["standard_error"])
    threshold = best_mean + best_se
    within = sorted(k for k in eligible if float(by_k[k]["mean_mse"]) <= threshold)
    return {
        "eligible_k": eligible,
        "best_k": int(best_k),
        "best_mean_mse": best_mean,
        "best_standard_error": best_se,
        "one_se_threshold": float(threshold),
        "within_one_se_k": within,
        "selected_k": int(min(within)),
    }


def track_b_decision(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply two Holm families and the frozen development-only one-SE rule."""
    if len(rows) != 5 or {int(row.get("k", -1)) for row in rows} != set(range(1, 6)):
        raise ValueError("Track B requires the complete K=1..5 candidate family")
    ordered = sorted((dict(row) for row in rows), key=lambda row: int(row["k"]))
    if any(row.get("split") != "calibration" for row in ordered):
        raise ValueError("Track B is calibration-only and rejects test rows")
    pooled_adjusted = holm_adjust(
        np.asarray([row["p_vs_pooled"] for row in ordered], dtype=np.float64)
    )
    if not all(
        isinstance(row.get("random_partition_tests"), dict) for row in ordered
    ):
        raise ValueError(
            "Track B requires all three preregistered random partition tests"
        )
    random_keys = sorted(GROUP_RANDOM_AXES)
    if any(set(row["random_partition_tests"]) != set(random_keys) for row in ordered):
        raise ValueError("random partition families differ across K")
    raw_random = np.asarray([
        row["random_partition_tests"][name]["p_value"]
        for row in ordered
        for name in random_keys
    ], dtype=np.float64)
    adjusted_random_family = holm_adjust(raw_random)
    for index, row in enumerate(ordered):
        row["adjusted_p_vs_pooled"] = float(pooled_adjusted[index])
        row["passes_pooled_holm"] = bool(
            float(row["gain_vs_pooled"]) > 0 and pooled_adjusted[index] <= 0.05
        )
        adjusted_values: list[float] = []
        passes: list[bool] = []
        for random_index, name in enumerate(random_keys):
            adjusted = float(
                adjusted_random_family[index * len(random_keys) + random_index]
            )
            test = row["random_partition_tests"][name]
            test["adjusted_p_value"] = adjusted
            test["passes_holm"] = bool(
                float(test["relative_gain"]) > 0 and adjusted <= 0.05
            )
            adjusted_values.append(adjusted)
            passes.append(test["passes_holm"])
        row["adjusted_p_vs_random"] = float(max(adjusted_values))
        row["passes_random_holm"] = bool(all(passes))
    selection = select_k_one_se(ordered)
    selected_k = selection["selected_k"]
    return {
        "decision_branch": (
            "development_nomination" if selected_k is not None else "no_eligible_k"
        ),
        "selected_k": selected_k,
        "candidates": ordered,
        "selection": selection,
        "test_accessed": False,
        "automatic_test_authorization": False,
        "requires_new_frozen_retraining": bool(selected_k is not None),
        "requires_new_untouched_confirmation": bool(selected_k is not None),
    }


def _one_sided_cluster_p(
    differences: np.ndarray,
    groups: np.ndarray,
    organs: np.ndarray,
    *,
    seed: int,
    n_bootstrap: int,
) -> tuple[float, tuple[float, float]]:
    """Paired study-level sign-flip P value plus clustered bootstrap interval."""
    differences = np.asarray(differences, dtype=np.float64)
    groups = np.asarray(groups).astype(str)
    organs = np.asarray(organs).astype(str)
    if differences.ndim != 1 or differences.shape != groups.shape or groups.shape != organs.shape:
        raise ValueError("bootstrap arrays do not align")
    if not np.isfinite(differences).all():
        raise ValueError("bootstrap differences contain non-finite values")
    rng = np.random.default_rng(seed)
    buckets: dict[str, dict[str, float]] = {}
    for organ in np.unique(organs):
        in_organ = organs == organ
        buckets[organ] = {
            group: float(differences[in_organ & (groups == group)].mean())
            for group in np.unique(groups[in_organ])
        }
    observed = balanced_group_mean(differences, groups=groups, strata=organs)
    null_estimates = np.empty(n_bootstrap, dtype=np.float64)
    for draw_index in range(n_bootstrap):
        organ_means: list[float] = []
        for grouped in buckets.values():
            values = np.asarray(list(grouped.values()), dtype=np.float64)
            signs = rng.choice(np.asarray([-1.0, 1.0]), size=len(values))
            organ_means.append(float(np.mean(values * signs)))
        null_estimates[draw_index] = float(np.mean(organ_means))
    p_value = float(
        (1 + np.sum(null_estimates >= observed)) / (n_bootstrap + 1)
    )
    interval = paired_bootstrap_ci(
        differences,
        seed=seed + 1_000_003,
        n_bootstrap=n_bootstrap,
        groups=groups,
        strata=organs,
    )
    return p_value, interval


def _mse_with_fallback(
    pooled_mse: np.ndarray,
    expert_mse: np.ndarray,
    assignments: np.ndarray,
    selected_experts: Sequence[int],
) -> np.ndarray:
    pooled = np.asarray(pooled_mse, dtype=np.float64)
    experts = np.asarray(expert_mse, dtype=np.float64)
    assignments = np.asarray(assignments, dtype=np.int64)
    if pooled.ndim != 1 or experts.ndim != 2 or experts.shape[0] != len(pooled):
        raise ValueError("MSE arrays do not align")
    if assignments.shape != pooled.shape:
        raise ValueError("MSE assignments do not align")
    output = pooled.copy()
    selected = set(int(value) for value in selected_experts)
    use = np.asarray([value in selected for value in assignments], dtype=bool)
    rows = np.flatnonzero(use)
    if len(rows):
        output[rows] = experts[rows, assignments[rows]]
    return output


def _collapsed_router_assignments(
    probabilities: np.ndarray,
    class_names: np.ndarray,
    selected_mask: np.ndarray,
) -> np.ndarray:
    """Map common K5 probabilities to selected organ experts or pooled fallback."""
    values = np.asarray(probabilities, dtype=np.float64)
    names = np.asarray(class_names).astype(str)
    selected_mask = np.asarray(selected_mask, dtype=bool)
    if values.ndim != 2 or values.shape[1] != len(names):
        raise ValueError("router probability and class axes do not align")
    if len(names) != 5 or set(names) != set(SPECIALIST_ORDER):
        raise ValueError("router classes differ from the five specialist organs")
    if selected_mask.shape != (5,) or not selected_mask.any():
        raise ValueError("selected subset mask must be a nonempty five-vector")
    if not np.isfinite(values).all() or np.any(values < -1e-12):
        raise ValueError("router probabilities contain invalid values")
    if not np.allclose(values.sum(axis=1), 1.0, atol=1e-8):
        raise ValueError("router probabilities do not sum to one")
    selected = {
        name
        for name, include in zip(SPECIALIST_ORDER, selected_mask)
        if bool(include)
    }
    collapsed_names = np.asarray(
        sorted(selected | ({"other"} if len(selected) < 5 else set())), dtype=str
    )
    collapsed_index = {name: index for index, name in enumerate(collapsed_names)}
    collapsed = np.zeros((len(values), len(collapsed_names)), dtype=np.float64)
    for column, name in enumerate(names):
        destination = name if name in selected else "other"
        collapsed[:, collapsed_index[destination]] += values[:, column]
    predicted = collapsed_names[np.argmax(collapsed, axis=1)]
    expert_index = {name: index for index, name in enumerate(CANONICAL_ORGANS)}
    return np.asarray(
        [expert_index.get(name, -1) for name in predicted], dtype=np.int64
    )


def _router_arrays(path: Path, report_path: Path) -> tuple[dict[str, np.ndarray], dict]:
    if not path.is_file() or not report_path.is_file():
        raise FileNotFoundError(path if not path.is_file() else report_path)
    report = json.loads(report_path.read_text())
    if report.get("status") != "complete" or report.get("test_accessed") is not False:
        raise ValueError("K-search router is not a calibration-only completed artifact")
    if report.get("hashes", {}).get("router_artifact_sha256") != _sha256_file(path):
        raise ValueError("router artifact hash differs from router report")
    with np.load(path, allow_pickle=False) as archive:
        arrays = {name: archive[name].copy() for name in archive.files}
    required = {
        "calibration_sample_ids",
        "calibration_organs",
        "calibration_series_group_id",
        "crossfit_fold",
        "specialist_order",
        "subset_ids",
        "subset_k",
        "subset_selected_mask",
        "subset_crossfit_predicted_class",
        "k5_crossfit_classes",
        "k5_crossfit_probabilities",
        "outer_inner_k5_probabilities",
        "outer_inner_valid_mask",
    }
    for k in range(1, 6):
        required.update({f"k{k}_classes", f"k{k}_crossfit_predicted_class"})
    missing = sorted(required - set(arrays))
    if missing:
        raise ValueError(f"router artifact lacks arrays: {missing}")
    if tuple(arrays["specialist_order"].astype(str)) != SPECIALIST_ORDER:
        raise ValueError("router specialist order differs from frozen K-search order")
    if not np.array_equal(arrays["subset_ids"], np.arange(1, 32)):
        raise ValueError("router does not contain the exhaustive subset ID family")
    if arrays["subset_selected_mask"].shape != (31, 5):
        raise ValueError("router exhaustive subset mask has invalid shape")
    if arrays["subset_crossfit_predicted_class"].shape[0] != 31:
        raise ValueError("router exhaustive prediction family has invalid shape")
    n_samples = len(arrays["calibration_sample_ids"])
    if arrays["k5_crossfit_probabilities"].shape != (n_samples, 5):
        raise ValueError("router outer K5 probability array has invalid shape")
    if arrays["outer_inner_k5_probabilities"].shape != (5, n_samples, 5):
        raise ValueError("router nested inner probability array has invalid shape")
    if arrays["outer_inner_valid_mask"].shape != (5, n_samples):
        raise ValueError("router nested inner validity mask has invalid shape")
    if tuple(arrays["k5_crossfit_classes"].astype(str)) != tuple(
        sorted(SPECIALIST_ORDER)
    ):
        raise ValueError("router K5 crossfit class order is invalid")
    return arrays, report


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    protocol_path = Path(args.protocol)
    router_path = Path(args.router_artifact)
    router_report_path = Path(args.router_report)
    track_a_path = Path(args.track_a_report)
    for path in (protocol_path, router_path, router_report_path, track_a_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    protocol = json.loads(protocol_path.read_text())
    track_b_protocol = protocol.get("track_b_development_k_search", {})
    if track_b_protocol.get("test_access_allowed") is not False:
        raise ValueError("protocol does not enforce the Track B test firewall")
    if tuple(track_b_protocol.get("specialist_order", ())) != SPECIALIST_ORDER:
        raise ValueError("protocol specialist order differs from evaluator")
    if track_b_protocol.get("subset_family") != (
        "all 31 nonempty subsets of the five specialists"
    ):
        raise ValueError("protocol does not freeze the exhaustive subset family")
    if track_b_protocol.get("candidate_k") != list(range(1, 6)):
        raise ValueError("protocol candidate family differs from K=1..5")
    expected_scope_limit = (
        "this run does not estimate the globally optimal MoE expert count, "
        "retrain K-specific banks, merge organs into K latent groups, or test K "
        "greater than five"
    )
    if track_b_protocol.get("scope_limit") != expected_scope_limit:
        raise ValueError("protocol does not freeze the deployed-K scope limit")
    if track_b_protocol.get("router_policy") != "common_k5_probability_collapse":
        raise ValueError("protocol does not freeze the common K5 router policy")
    if track_b_protocol.get("strict_outer_inner_router") is not True:
        raise ValueError("protocol does not freeze strict outer/inner router selection")
    if track_b_protocol.get("matched_random_subset_family") != (
        "all C(5,K) subsets independently within each preregistered partition and outer fold"
    ):
        raise ValueError("protocol does not freeze matched random subset selection")
    track_a = json.loads(track_a_path.read_text())
    if track_a.get("status") != "complete" or track_a.get("test_accessed") is not True:
        raise ValueError("Track A must complete before Track B is inspected")
    if track_a.get("internal_locked_replication") is not True:
        raise ValueError("Track A evidence label is invalid")

    router, router_report = _router_arrays(router_path, router_report_path)
    run_paths = _parse_seed_paths(args.bank_run, name="bank-run")
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
    expected_protocol_hash = _sha256_file(protocol_path)
    expected_router_hash = _sha256_file(router_path)
    if track_a.get("hashes", {}).get("protocol_sha256") != expected_protocol_hash:
        raise ValueError("Track A used a different frozen protocol")
    if track_a.get("hashes", {}).get("router_artifact_sha256") != expected_router_hash:
        raise ValueError("Track A used a different frozen router")
    bank_artifact_hashes: dict[str, dict[str, dict[str, str]]] = {}
    for seed in EXPECTED_SEEDS:
        bank_artifact_hashes[str(seed)] = {}
        for axis in ("organ_k5", "random_k5", *GROUP_RANDOM_AXES):
            bank_dir = run_paths[seed] / "banks" / axis
            bank_artifact_hashes[str(seed)][axis] = {
                "final_experts_sha256": _sha256_file(bank_dir / "final_experts.pt"),
                "calibration_scores_sha256": _sha256_file(
                    bank_dir / "calibration_scores.npz"
                ),
                "run_metadata_sha256": _sha256_file(
                    bank_dir / "run_metadata.json"
                ),
            }
    if (
        track_a.get("inputs", {}).get("bank_artifact_hashes")
        != bank_artifact_hashes
    ):
        raise ValueError("Track B bank artifacts differ from Track A")
    alignment = _validate_bank_alignment(organ_banks, random_banks)
    for axis in GROUP_RANDOM_AXES:
        _validate_bank_alignment(organ_banks, group_random_banks[axis])
    sample_ids = alignment["sample_ids"]
    groups = alignment["groups"]
    organs = alignment["organs"]
    if not np.array_equal(router["calibration_sample_ids"].astype(str), sample_ids):
        raise ValueError("router and bank calibration sample order differs")
    if not np.array_equal(router["calibration_organs"].astype(str), organs):
        raise ValueError("router and bank calibration organ labels differ")
    if not np.array_equal(router["calibration_series_group_id"].astype(str), groups):
        raise ValueError("router and bank calibration groups differ")
    folds = router["crossfit_fold"].astype(np.int64)
    if folds.shape != sample_ids.shape or set(folds.tolist()) != set(range(5)):
        raise ValueError("router crossfit folds are incomplete")
    for fold in range(5):
        held_organs = set(organs[folds == fold])
        if held_organs != set(CANONICAL_ORGANS):
            raise ValueError(
                f"router crossfit fold {fold} lacks organ coverage: {held_organs}"
            )
    organ_to_expert = {name: index for index, name in enumerate(CANONICAL_ORGANS)}

    subset_ids = router["subset_ids"].astype(np.int64)
    subset_k = router["subset_k"].astype(np.int64)
    subset_masks = router["subset_selected_mask"].astype(bool)
    outer_probabilities = router["k5_crossfit_probabilities"].astype(np.float64)
    inner_probabilities = router["outer_inner_k5_probabilities"].astype(np.float64)
    inner_valid = router["outer_inner_valid_mask"].astype(bool)
    router_classes = router["k5_crossfit_classes"].astype(str)
    if not np.isfinite(outer_probabilities).all() or not np.allclose(
        outer_probabilities.sum(axis=1), 1.0, atol=1e-8
    ):
        raise ValueError("outer K5 router probabilities are invalid")
    for fold in range(5):
        expected_valid = folds != fold
        if not np.array_equal(inner_valid[fold], expected_valid):
            raise ValueError(
                f"nested router validity mask does not equal outer-fit rows: {fold}"
            )
        if not np.isfinite(inner_probabilities[fold, expected_valid]).all() or not np.allclose(
            inner_probabilities[fold, expected_valid].sum(axis=1), 1.0, atol=1e-8
        ):
            raise ValueError(f"nested inner K5 probabilities are invalid: {fold}")

    pooled_by_seed = {
        seed: organ_banks[seed]["arrays"]["pooled_mse"].astype(np.float64)
        for seed in EXPECTED_SEEDS
    }
    for seed in EXPECTED_SEEDS:
        for bank in (
            random_banks[seed],
            *[group_random_banks[axis][seed] for axis in GROUP_RANDOM_AXES],
        ):
            if not np.allclose(
                pooled_by_seed[seed],
                bank["arrays"]["pooled_mse"].astype(np.float64),
                rtol=1e-7,
                atol=1e-10,
            ):
                raise ValueError(
                    f"pooled calibration scores differ for {bank['axis']}, seed {seed}"
                )

    # Organ candidates use a strict nested routing design.  For a given outer
    # fold, subset selection sees only inner-OOF predictions produced without
    # any row from the outer-held fold; the held score uses the outer router.
    organ_outer_subset_mse: dict[int, dict[int, np.ndarray]] = {}
    organ_inner_subset_mse: dict[int, dict[int, dict[int, np.ndarray]]] = {
        fold: {} for fold in range(5)
    }
    for subset_row, subset_id_raw in enumerate(subset_ids):
        subset_id = int(subset_id_raw)
        selected_mask = subset_masks[subset_row]
        selected_names = [
            name
            for name, selected in zip(SPECIALIST_ORDER, selected_mask)
            if selected
        ]
        selected_experts = [organ_to_expert[name] for name in selected_names]
        outer_assignments = _collapsed_router_assignments(
            outer_probabilities, router_classes, selected_mask
        )
        organ_outer_subset_mse[subset_id] = {
            seed: _mse_with_fallback(
                pooled_by_seed[seed],
                organ_banks[seed]["arrays"]["expert_mse"],
                outer_assignments,
                selected_experts,
            )
            for seed in EXPECTED_SEEDS
        }
        for fold in range(5):
            fit = inner_valid[fold]
            inner_assignments = _collapsed_router_assignments(
                inner_probabilities[fold, fit], router_classes, selected_mask
            )
            organ_inner_subset_mse[fold][subset_id] = {
                seed: _mse_with_fallback(
                    pooled_by_seed[seed][fit],
                    organ_banks[seed]["arrays"]["expert_mse"][fit],
                    inner_assignments,
                    selected_experts,
                )
                for seed in EXPECTED_SEEDS
            }

    # Give every random control exactly the same C(5,K) subset-selection budget
    # as the organ arm.  Random assignment is frozen and outcome-free, so no
    # nuisance router needs an inner fit; subset choice still uses outer-fit
    # reconstruction outcomes only and is scored on the held fold.
    random_bank_families: dict[str, dict[int, dict[str, Any]]] = {
        "random_k5": random_banks,
        **group_random_banks,
    }
    random_subset_mse: dict[str, dict[int, dict[int, np.ndarray]]] = {
        axis: {} for axis in random_bank_families
    }
    for axis, banks in random_bank_families.items():
        for subset_row, subset_id_raw in enumerate(subset_ids):
            subset_id = int(subset_id_raw)
            selected_experts = np.flatnonzero(subset_masks[subset_row]).astype(int).tolist()
            random_subset_mse[axis][subset_id] = {
                seed: _mse_with_fallback(
                    pooled_by_seed[seed],
                    banks[seed]["arrays"]["expert_mse"],
                    banks[seed]["arrays"]["true_labels"].astype(np.int64),
                    selected_experts,
                )
                for seed in EXPECTED_SEEDS
            }

    candidate_rows: list[dict[str, Any]] = []
    audit_arrays: dict[str, np.ndarray] = {
        "sample_ids": sample_ids,
        "groups": groups,
        "organs": organs,
        "crossfit_fold": folds,
        "seeds": np.asarray(EXPECTED_SEEDS, dtype=np.int64),
        "specialist_order": np.asarray(SPECIALIST_ORDER, dtype=str),
    }
    for k in range(1, 6):
        candidate_subset_ids = subset_ids[subset_k == k].astype(int).tolist()
        blind_by_seed = {
            seed: np.empty(len(sample_ids), dtype=np.float64)
            for seed in EXPECTED_SEEDS
        }
        true_by_seed = {
            seed: np.empty(len(sample_ids), dtype=np.float64)
            for seed in EXPECTED_SEEDS
        }
        selected_subset_by_fold: dict[str, int] = {}
        fit_scores_by_fold: dict[str, dict[str, float]] = {}
        for fold in range(5):
            fit = folds != fold
            held = folds == fold
            if not np.array_equal(fit, inner_valid[fold]):
                raise RuntimeError("router inner-valid and evaluator outer-fit differ")
            fit_scores: dict[int, float] = {}
            for subset_id in candidate_subset_ids:
                seed_mean = np.mean(
                    np.stack([
                        organ_inner_subset_mse[fold][subset_id][seed]
                        for seed in EXPECTED_SEEDS
                    ]),
                    axis=0,
                )
                fit_scores[subset_id] = balanced_group_mean(
                    seed_mean, groups[fit], organs[fit]
                )
            selected_subset = min(
                candidate_subset_ids,
                key=lambda subset_id: (fit_scores[subset_id], subset_id),
            )
            selected_subset_by_fold[str(fold)] = int(selected_subset)
            fit_scores_by_fold[str(fold)] = {
                str(subset_id): float(fit_scores[subset_id])
                for subset_id in candidate_subset_ids
            }
            selected_row = int(np.flatnonzero(subset_ids == selected_subset)[0])
            selected_names = [
                name
                for name, selected in zip(
                    SPECIALIST_ORDER, subset_masks[selected_row]
                )
                if selected
            ]
            selected_experts = [organ_to_expert[name] for name in selected_names]
            true_assignments = np.asarray(
                [organ_to_expert[organ] for organ in organs[held]], dtype=np.int64
            )
            for seed in EXPECTED_SEEDS:
                blind_by_seed[seed][held] = organ_outer_subset_mse[
                    selected_subset
                ][seed][held]
                true_by_seed[seed][held] = _mse_with_fallback(
                    pooled_by_seed[seed][held],
                    organ_banks[seed]["arrays"]["expert_mse"][held],
                    true_assignments,
                    selected_experts,
                )

        full_subset_scores: dict[int, float] = {}
        for subset_id in candidate_subset_ids:
            seed_mean = np.mean(
                np.stack([
                    organ_outer_subset_mse[subset_id][seed]
                    for seed in EXPECTED_SEEDS
                ]),
                axis=0,
            )
            full_subset_scores[subset_id] = balanced_group_mean(
                seed_mean, groups, organs
            )
        final_subset = min(
            candidate_subset_ids,
            key=lambda subset_id: (full_subset_scores[subset_id], subset_id),
        )
        final_subset_row = int(np.flatnonzero(subset_ids == final_subset)[0])
        selected_organs = [
            name
            for name, selected in zip(
                SPECIALIST_ORDER, subset_masks[final_subset_row]
            )
            if selected
        ]
        selected_random_subset_by_axis: dict[str, dict[str, int]] = {}
        random_fit_scores_by_axis: dict[str, dict[str, dict[str, float]]] = {}
        random_by_axis: dict[str, dict[int, np.ndarray]] = {}
        for axis in random_bank_families:
            random_by_axis[axis] = {
                seed: np.empty(len(sample_ids), dtype=np.float64)
                for seed in EXPECTED_SEEDS
            }
            selected_random_subset_by_axis[axis] = {}
            random_fit_scores_by_axis[axis] = {}
            for fold in range(5):
                fit = folds != fold
                held = folds == fold
                fit_scores: dict[int, float] = {}
                for subset_id in candidate_subset_ids:
                    seed_mean = np.mean(
                        np.stack([
                            random_subset_mse[axis][subset_id][seed]
                            for seed in EXPECTED_SEEDS
                        ]),
                        axis=0,
                    )
                    fit_scores[subset_id] = balanced_group_mean(
                        seed_mean[fit], groups[fit], organs[fit]
                    )
                selected_subset = min(
                    candidate_subset_ids,
                    key=lambda subset_id: (fit_scores[subset_id], subset_id),
                )
                selected_random_subset_by_axis[axis][str(fold)] = int(
                    selected_subset
                )
                random_fit_scores_by_axis[axis][str(fold)] = {
                    str(subset_id): float(fit_scores[subset_id])
                    for subset_id in candidate_subset_ids
                }
                for seed in EXPECTED_SEEDS:
                    random_by_axis[axis][seed][held] = random_subset_mse[
                        axis
                    ][selected_subset][seed][held]

        legacy_random_by_seed = random_by_axis["random_k5"]
        group_random_by_axis = {
            axis: random_by_axis[axis] for axis in GROUP_RANDOM_AXES
        }

        vs_pooled = comparison(
            pooled_by_seed, blind_by_seed, groups, organs, EXPECTED_SEEDS,
            bootstrap_seed=args.bootstrap_seed + 100 + k,
            bootstrap_reps=args.bootstrap_reps,
        )
        legacy_vs_random = comparison(
            legacy_random_by_seed, blind_by_seed, groups, organs, EXPECTED_SEEDS,
            bootstrap_seed=args.bootstrap_seed + 200 + k,
            bootstrap_reps=args.bootstrap_reps,
        )
        true_vs_pooled = comparison(
            pooled_by_seed, true_by_seed, groups, organs, EXPECTED_SEEDS,
            bootstrap_seed=args.bootstrap_seed + 300 + k,
            bootstrap_reps=args.bootstrap_reps,
        )
        blind_matrix = np.stack([blind_by_seed[seed] for seed in EXPECTED_SEEDS])
        pooled_matrix = np.stack([pooled_by_seed[seed] for seed in EXPECTED_SEEDS])
        seed_mean_blind = blind_matrix.mean(axis=0)
        fold_means = np.asarray([
            balanced_group_mean(
                seed_mean_blind[folds == fold],
                groups[folds == fold],
                organs[folds == fold],
            )
            for fold in range(5)
        ])
        standard_error = float(np.std(fold_means, ddof=1) / math.sqrt(len(fold_means)))
        p_pooled, p_pooled_interval = _one_sided_cluster_p(
            (pooled_matrix - blind_matrix).mean(axis=0), groups, organs,
            seed=args.bootstrap_seed + 400 + k,
            n_bootstrap=args.bootstrap_reps,
        )
        random_partition_tests: dict[str, Any] = {}
        random_partition_comparisons: dict[str, Any] = {}
        for partition_index, axis in enumerate(GROUP_RANDOM_AXES):
            random_matrix = np.stack([
                group_random_by_axis[axis][seed] for seed in EXPECTED_SEEDS
            ])
            axis_comparison = comparison(
                group_random_by_axis[axis], blind_by_seed,
                groups, organs, EXPECTED_SEEDS,
                bootstrap_seed=args.bootstrap_seed + 500 + 10 * k + partition_index,
                bootstrap_reps=args.bootstrap_reps,
            )
            p_random, p_random_interval = _one_sided_cluster_p(
                (random_matrix - blind_matrix).mean(axis=0), groups, organs,
                seed=args.bootstrap_seed + 600 + 10 * k + partition_index,
                n_bootstrap=args.bootstrap_reps,
            )
            random_partition_tests[axis] = {
                "relative_gain": float(
                    axis_comparison["relative_mse_reduction_mean"]
                ),
                "p_value": p_random,
                "clustered_ci95_absolute_improvement": list(p_random_interval),
            }
            random_partition_comparisons[axis] = axis_comparison
        mean_mse = float(
            np.mean([
                balanced_group_mean(blind_by_seed[seed], groups, organs)
                for seed in EXPECTED_SEEDS
            ])
        )
        candidate_rows.append({
            "k": k,
            "split": "calibration",
            "selected_specialists": list(selected_organs),
            "final_full_calibration_subset_id": int(final_subset),
            "full_calibration_subset_scores": {
                str(subset_id): float(full_subset_scores[subset_id])
                for subset_id in candidate_subset_ids
            },
            "outer_fold_selected_subset_id": selected_subset_by_fold,
            "outer_fold_fit_subset_scores": fit_scores_by_fold,
            "outer_fold_selected_random_subset_id": {
                axis: selected_random_subset_by_axis[axis]
                for axis in GROUP_RANDOM_AXES
            },
            "outer_fold_random_fit_subset_scores": {
                axis: random_fit_scores_by_axis[axis]
                for axis in GROUP_RANDOM_AXES
            },
            "legacy_outer_fold_selected_random_subset_id_non_gating": (
                selected_random_subset_by_axis["random_k5"]
            ),
            "pooled_fallback_organs": [
                name for name in SPECIALIST_ORDER if name not in selected_organs
            ],
            "mean_mse": mean_mse,
            "standard_error": standard_error,
            "outer_fold_mean_mse": fold_means.tolist(),
            "gain_vs_pooled": float(vs_pooled["relative_mse_reduction_mean"]),
            "gain_vs_random": float(min(
                test["relative_gain"] for test in random_partition_tests.values()
            )),
            "p_vs_pooled": p_pooled,
            "p_vs_random": float(max(
                test["p_value"] for test in random_partition_tests.values()
            )),
            "bootstrap_ci95_absolute_vs_pooled": list(p_pooled_interval),
            "blind_vs_pooled": vs_pooled,
            "blind_vs_legacy_row_random_non_gating": legacy_vs_random,
            "blind_vs_group_random": random_partition_comparisons,
            "random_partition_tests": random_partition_tests,
            "true_fallback_vs_pooled": true_vs_pooled,
        })
        audit_arrays[f"k{k}_blind_mse"] = blind_matrix
        audit_arrays[f"k{k}_pooled_mse"] = pooled_matrix
        audit_arrays[f"k{k}_legacy_row_random_mse"] = np.stack([
            legacy_random_by_seed[seed] for seed in EXPECTED_SEEDS
        ])
        audit_arrays[f"k{k}_outer_selected_organ_subset_id"] = np.asarray(
            [selected_subset_by_fold[str(fold)] for fold in range(5)],
            dtype=np.int64,
        )
        for axis in GROUP_RANDOM_AXES:
            audit_arrays[f"k{k}_{axis}_mse"] = np.stack([
                group_random_by_axis[axis][seed] for seed in EXPECTED_SEEDS
            ])
            audit_arrays[f"k{k}_{axis}_outer_selected_subset_id"] = np.asarray(
                [
                    selected_random_subset_by_axis[axis][str(fold)]
                    for fold in range(5)
                ],
                dtype=np.int64,
            )

    decision = track_b_decision(candidate_rows)
    output_dir = Path(args.output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"K-search output is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    score_path = output_dir / "calibration_k_scores.npz"
    np.savez_compressed(score_path, **audit_arrays)
    report = {
        "schema_version": 1,
        "status": "complete",
        "experiment": "calibration_only_deployed_organ_specialist_k_search",
        "test_accessed": False,
        "test_features_loaded": False,
        "test_targets_loaded": False,
        "track_a_test_derived_report_opened_for_completion_and_hash_checks": True,
        "track_a_test_effects_used_for_k_selection": False,
        "decision": decision,
        "definition_of_k": track_b_protocol["definition_of_k"],
        "scope_limit": expected_scope_limit,
        "specialist_order": list(SPECIALIST_ORDER),
        "subset_family": track_b_protocol["subset_family"],
        "router_policy": track_b_protocol["router_policy"],
        "strict_outer_inner_router": True,
        "matched_random_subset_family": track_b_protocol[
            "matched_random_subset_family"
        ],
        "population": "all five calibration organs for every K",
        "selection_is_development_only": True,
        "hashes": {
            "protocol_sha256": expected_protocol_hash,
            "router_artifact_sha256": expected_router_hash,
            "router_report_sha256": _sha256_file(router_report_path),
            "track_a_report_sha256": _sha256_file(track_a_path),
            "calibration_k_scores_sha256": _sha256_file(score_path),
            "evaluator_source_sha256": _sha256_file(Path(__file__)),
        },
        "inputs": {
            "bank_runs": {str(seed): str(run_paths[seed]) for seed in EXPECTED_SEEDS},
            "bank_artifact_hashes": bank_artifact_hashes,
            "calibration_samples": int(len(sample_ids)),
            "calibration_groups": int(len(np.unique(groups))),
            "bootstrap_reps": int(args.bootstrap_reps),
            "bootstrap_seed": int(args.bootstrap_seed),
        },
        "guardrail": (
            "This calibration-only search can nominate a deployed specialist count. "
            "It neither changes the immutable K5 Track-A result nor authorizes a test."
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
    parser.add_argument("--track-a-report", required=True)
    parser.add_argument("--bank-run", action="append", required=True, help="SEED=PATH")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--bootstrap-reps", type=int, default=2000)
    parser.add_argument("--bootstrap-seed", type=int, default=515151)
    return parser


def main() -> None:
    report = evaluate(build_parser().parse_args())
    print(json.dumps({
        "status": report["status"],
        "decision": report["decision"],
        "test_accessed": report["test_accessed"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
