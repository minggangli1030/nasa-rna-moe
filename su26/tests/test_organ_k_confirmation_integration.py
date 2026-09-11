from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))

from evaluate_organ_k_confirmation import (  # noqa: E402
    CANONICAL_ORGANS,
    EXPECTED_SEEDS,
    GROUP_RANDOM_AXES,
    build_parser as build_track_a_parser,
    evaluate as evaluate_track_a,
)
from evaluate_organ_k_search import (  # noqa: E402
    SPECIALIST_ORDER,
    build_parser as build_track_b_parser,
    evaluate as evaluate_track_b,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _token(name: str) -> str:
    return hashlib.sha256(name.encode("utf-8")).hexdigest()


def _calibration_rows() -> dict[str, np.ndarray]:
    sample_ids: list[str] = []
    groups: list[str] = []
    organs: list[str] = []
    folds: list[int] = []
    organ_labels: list[int] = []
    random_labels: list[int] = []
    organ_index = {name: index for index, name in enumerate(CANONICAL_ORGANS)}
    # Every outer fold contains every organ, and every row is its own connected
    # study. This keeps the fixture tiny while exercising the full estimand.
    for fold in range(5):
        for organ in CANONICAL_ORGANS:
            sample_ids.append(f"cal-f{fold}-{organ}")
            groups.append(f"cal-study-f{fold}-{organ}")
            organs.append(organ)
            folds.append(fold)
            organ_labels.append(organ_index[organ])
            random_labels.append((organ_index[organ] + fold + 1) % 5)
    output = {
        "sample_ids": np.asarray(sample_ids, dtype=str),
        "groups": np.asarray(groups, dtype=str),
        "organs": np.asarray(organs, dtype=str),
        "folds": np.asarray(folds, dtype=np.int64),
        "organ_labels": np.asarray(organ_labels, dtype=np.int64),
        "random_labels": np.asarray(random_labels, dtype=np.int64),
    }
    for partition_index, axis in enumerate(GROUP_RANDOM_AXES):
        output[axis] = (
            output["random_labels"] + partition_index + 1
        ) % 5
    return output


def _test_rows() -> dict[str, np.ndarray]:
    sample_ids: list[str] = []
    groups: list[str] = []
    organs: list[str] = []
    organ_labels: list[int] = []
    random_labels: list[int] = []
    for replicate in range(2):
        for organ_index, organ in enumerate(CANONICAL_ORGANS):
            sample_ids.append(f"test-r{replicate}-{organ}")
            groups.append(f"test-study-r{replicate}-{organ}")
            organs.append(organ)
            organ_labels.append(organ_index)
            random_labels.append((organ_index + replicate + 2) % 5)
    output = {
        "sample_ids": np.asarray(sample_ids, dtype=str),
        "groups": np.asarray(groups, dtype=str),
        "organs": np.asarray(organs, dtype=str),
        "organ_labels": np.asarray(organ_labels, dtype=np.int64),
        "random_labels": np.asarray(random_labels, dtype=np.int64),
    }
    for partition_index, axis in enumerate(GROUP_RANDOM_AXES):
        output[axis] = (
            output["random_labels"] + partition_index + 1
        ) % 5
    return output


def _write_bank(
    path: Path,
    *,
    axis: str,
    seed: int,
    calibration: dict[str, np.ndarray],
    common_hashes: dict[str, str],
) -> None:
    path.mkdir(parents=True)
    if axis == "organ_k5":
        labels = calibration["organ_labels"]
    elif axis == "random_k5":
        labels = calibration["random_labels"]
    else:
        labels = calibration[axis]
    n_samples = len(labels)
    pooled = np.full(n_samples, 1.0, dtype=np.float64)
    if axis == "organ_k5":
        expert = np.full((n_samples, 5), 0.99, dtype=np.float64)
        expert[np.arange(n_samples), calibration["organ_labels"]] = 0.70
    else:
        expert = np.stack(
            [np.full(n_samples, 0.92 + 0.01 * index) for index in range(5)],
            axis=1,
        )
    true_partition = expert[np.arange(n_samples), labels]
    score_path = path / "calibration_scores.npz"
    np.savez_compressed(
        score_path,
        sample_ids=calibration["sample_ids"],
        groups=calibration["groups"],
        organs=calibration["organs"],
        sample_weights=np.full(n_samples, 1.0 / n_samples, dtype=np.float64),
        pooled_mse=pooled,
        true_partition_mse=true_partition,
        oracle_mse=expert.min(axis=1),
        crossfit_fixed_mse=np.full(n_samples, 0.95, dtype=np.float64),
        expert_mse=expert,
        true_labels=labels,
    )
    metadata = {
        "schema_version": 1,
        "status": "complete",
        "axis": axis,
        "training_seed": seed,
        "test_accessed": False,
        "mechanical_only": False,
        "config": {
            "num_experts": 5,
            "final_update": 1500,
            "checkpoint_policy": "predetermined_final_update",
            "exposures_per_expert_target": 2400,
            "realized_exposure_counts": [2400] * 5,
        },
        "calibration_metrics": {
            "full_calibration_fixed_weights": [0.2] * 5,
        },
        "hashes": dict(common_hashes),
        "artifacts": {"calibration_scores_sha256": _sha256(score_path)},
    }
    (path / "run_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (path / "final_experts.pt").write_bytes(
        f"synthetic-final-experts:{axis}:{seed}".encode("utf-8")
    )
    (path / "COMPLETE").touch()


def _write_test_cache(
    path: Path,
    *,
    seed: int,
    test: dict[str, np.ndarray],
    fingerprints: dict[str, str],
    bank_run: Path,
) -> None:
    path.mkdir(parents=True)
    n_samples = len(test["sample_ids"])
    n_targets = 4
    target_row = np.asarray([1.0, 2.0, 4.0, 8.0], dtype=np.float64)
    error = np.asarray([1.0, -1.0, 1.0, -1.0], dtype=np.float64)
    target = np.stack(
        [target_row + 0.05 * index for index in range(n_samples)], axis=0
    )
    baseline = np.zeros_like(target)
    pooled = target + 0.50 * error
    organ_experts = np.empty((n_samples, 5, n_targets), dtype=np.float64)
    random_experts = np.empty((n_samples, 5, n_targets), dtype=np.float64)
    group_random_experts = {
        axis: np.empty((n_samples, 5, n_targets), dtype=np.float64)
        for axis in GROUP_RANDOM_AXES
    }
    for row, true_label in enumerate(test["organ_labels"]):
        for expert in range(5):
            scale = 0.05 if expert == true_label else 0.70 + 0.01 * expert
            organ_experts[row, expert] = target[row] + scale * error
            random_experts[row, expert] = target[row] + (0.40 + 0.02 * expert) * error
            for partition_index, axis in enumerate(GROUP_RANDOM_AXES):
                group_random_experts[axis][row, expert] = (
                    target[row]
                    + (0.38 + 0.02 * expert + 0.01 * partition_index) * error
                )
    probabilities = np.zeros((n_samples, 5), dtype=np.float64)
    probabilities[np.arange(n_samples), test["organ_labels"]] = 1.0
    score_path = path / "test_scores.npz"
    score_arrays = {
        "sample_ids": test["sample_ids"],
        "groups": test["groups"],
        "organs": test["organs"],
        "sample_weights": np.full(n_samples, 1.0 / n_samples, dtype=np.float64),
        "organ_labels": test["organ_labels"],
        "random_labels": test["random_labels"],
        "target_masked": target,
        "baseline_masked": baseline,
        "pooled_masked": pooled,
        "organ_expert_masked": organ_experts,
        "random_expert_masked": random_experts,
        "blind_k5_probabilities": probabilities,
        "blind_k5_predicted_organ": test["organs"],
        "k5_full_classes": np.asarray(CANONICAL_ORGANS, dtype=str),
        "organ_label_names": np.asarray(CANONICAL_ORGANS, dtype=str),
        "random_label_names": np.asarray(
            [f"random_{index}" for index in range(5)], dtype=str
        ),
        "score_gene_indices": np.arange(n_targets, dtype=np.int64),
        "score_gene_names": np.asarray(
            [f"score-{index}" for index in range(n_targets)]
        ),
    }
    for axis in GROUP_RANDOM_AXES:
        score_arrays[f"{axis}_labels"] = test[axis]
        score_arrays[f"{axis}_expert_masked"] = group_random_experts[axis]
    np.savez_compressed(
        score_path,
        **score_arrays,
    )
    hashes = {
        **fingerprints,
        "test_scores_sha256": _sha256(score_path),
    }
    report = {
        "schema_version": 1,
        "status": "complete",
        "experiment": "fixed_bank_locked_test_score_cache",
        "internal_locked_replication": True,
        "independent_confirmation": False,
        "authorized_test_access": True,
        "mechanical_only": False,
        "test_accessed": True,
        "test_expression_accessed": True,
        "test_targets_accessed": True,
        "model_fitting_during_test_access": False,
        "training_seed": seed,
        "counts": {
            "test_samples": n_samples,
            "test_groups": n_samples,
            "score_genes": n_targets,
            "experts_per_bank": 5,
        },
        "banks": {
            axis: {
                "final_experts_sha256": _sha256(
                    bank_run / "banks" / axis / "final_experts.pt"
                ),
                "run_metadata_sha256": _sha256(
                    bank_run / "banks" / axis / "run_metadata.json"
                ),
            }
            for axis in ("organ_k5", "random_k5", *GROUP_RANDOM_AXES)
        },
        "hashes": hashes,
        "artifacts": {
            "test_scores": str(score_path),
            "test_scores_sha256": _sha256(score_path),
        },
    }
    (path / "test_score_report.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )


def _write_fixture(root: Path) -> dict[str, object]:
    calibration = _calibration_rows()
    test = _test_rows()
    protocol_path = root / "protocol.json"
    protocol = {
        "schema_version": 1,
        "evidence_label": {
            "internal_locked_replication": True,
            "independent_confirmation": False,
        },
        "track_a_k5_internal_replication": {"immutable": True},
        "track_b_development_k_search": {
            "test_access_allowed": False,
            "definition_of_k": (
                "number of known organs receiving a specialist; all others use pooled"
            ),
            "scope_limit": (
                "this run does not estimate the globally optimal MoE expert count, "
                "retrain K-specific banks, merge organs into K latent groups, or "
                "test K greater than five"
            ),
            "specialist_order": list(SPECIALIST_ORDER),
            "subset_family": "all 31 nonempty subsets of the five specialists",
            "router_policy": "common_k5_probability_collapse",
            "strict_outer_inner_router": True,
            "matched_random_subset_family": (
                "all C(5,K) subsets independently within each preregistered "
                "partition and outer fold"
            ),
            "candidate_k": list(range(1, 6)),
        },
    }
    protocol_path.write_text(json.dumps(protocol, indent=2) + "\n")

    sealed = pd.DataFrame({
        "sample_id": test["sample_ids"],
        "utility_split": "test",
        "split": "test",
        "organ": test["organs"],
        "series_group_id": test["groups"],
        "random_shard": [f"random_{value}" for value in test["random_labels"]],
        "organ_k5": test["organ_labels"],
        "random_k5": test["random_labels"],
        **{axis: test[axis] for axis in GROUP_RANDOM_AXES},
    })
    sealed_path = root / "sealed_test_assignments.parquet"
    sealed.to_parquet(sealed_path, index=False)
    sealed_report_path = root / "sealed_test_report.json"
    sealed_report_path.write_text(json.dumps({
        "schema_version": 1,
        "status": "complete",
        "sealed": True,
        "test_accessed": False,
        "test_expression_accessed": False,
        "test_targets_accessed": False,
        "hashes": {
            "sealed_test_assignments_sha256": _sha256(sealed_path),
            **{
                f"test_{axis}_assignment_sha256": _token(
                    f"sealed-{axis}-assignment"
                )
                for axis in GROUP_RANDOM_AXES
            },
        },
    }, indent=2) + "\n")

    router_path = root / "organ_k_router.npz"
    router_arrays: dict[str, np.ndarray] = {
        "calibration_sample_ids": calibration["sample_ids"],
        "calibration_organs": calibration["organs"],
        "calibration_series_group_id": calibration["groups"],
        "crossfit_fold": calibration["folds"],
        "specialist_order": np.asarray(SPECIALIST_ORDER, dtype=str),
    }
    subset_ids = np.arange(1, 32, dtype=np.int64)
    subset_selected_mask = (
        (
            subset_ids[:, None]
            >> np.arange(len(SPECIALIST_ORDER), dtype=np.int64)
        )
        & 1
    ).astype(bool)
    subset_predicted = np.empty(
        (len(subset_ids), len(calibration["sample_ids"])), dtype="<U16"
    )
    for subset_row, selected_mask in enumerate(subset_selected_mask):
        selected = {
            name
            for name, include in zip(SPECIALIST_ORDER, selected_mask)
            if include
        }
        subset_predicted[subset_row] = np.asarray([
            organ if organ in selected else "other"
            for organ in calibration["organs"].astype(str)
        ])
    router_arrays.update({
        "subset_ids": subset_ids,
        "subset_k": subset_selected_mask.sum(axis=1).astype(np.int64),
        "subset_selected_mask": subset_selected_mask,
        "subset_crossfit_predicted_class": subset_predicted,
    })
    k5_classes = np.asarray(sorted(SPECIALIST_ORDER), dtype=str)
    class_index = {name: index for index, name in enumerate(k5_classes)}
    k5_probability = np.zeros((len(calibration["sample_ids"]), 5), dtype=np.float64)
    k5_probability[
        np.arange(len(k5_probability)),
        [class_index[name] for name in calibration["organs"].astype(str)],
    ] = 1.0
    outer_inner_probability = np.zeros((5, len(k5_probability), 5), dtype=np.float64)
    outer_inner_valid = np.zeros((5, len(k5_probability)), dtype=bool)
    for fold in range(5):
        fit = calibration["folds"] != fold
        outer_inner_probability[fold, fit] = k5_probability[fit]
        outer_inner_valid[fold, fit] = True
    router_arrays.update({
        "k5_crossfit_classes": k5_classes,
        "k5_crossfit_probabilities": k5_probability,
        "outer_inner_k5_probabilities": outer_inner_probability,
        "outer_inner_valid_mask": outer_inner_valid,
    })
    for k in range(1, 6):
        selected = set(SPECIALIST_ORDER[:k])
        predicted = np.asarray([
            organ if organ in selected else "other"
            for organ in calibration["organs"].astype(str)
        ])
        if k == 5:
            predicted = calibration["organs"].astype(str).copy()
        router_arrays[f"k{k}_classes"] = np.unique(predicted)
        router_arrays[f"k{k}_crossfit_predicted_class"] = predicted
    np.savez_compressed(router_path, **router_arrays)
    router_report_path = root / "router_report.json"
    router_report_path.write_text(json.dumps({
        "schema_version": 1,
        "status": "complete",
        "test_accessed": False,
        "test_features_loaded": False,
        "train_features_loaded": False,
        "hashes": {"router_artifact_sha256": _sha256(router_path)},
    }, indent=2) + "\n")

    common_hashes = {
        "protocol_sha256": _sha256(protocol_path),
        "manifest_sha256": _token("source-manifest"),
        "partition_manifest_sha256": _token("train-cal-partitions"),
        "axis_definitions_sha256": _token("axis-definitions"),
        "score_gene_indices_sha256": _token("score-panel"),
    }
    cache_fingerprints = {
        **common_hashes,
        "router_artifact_sha256": _sha256(router_path),
        "sealed_test_assignments_sha256": _sha256(sealed_path),
    }
    bank_runs: dict[int, Path] = {}
    test_caches: dict[int, Path] = {}
    for seed in EXPECTED_SEEDS:
        run_root = root / f"bank-seed-{seed}"
        _write_bank(
            run_root / "banks" / "organ_k5",
            axis="organ_k5",
            seed=seed,
            calibration=calibration,
            common_hashes=common_hashes,
        )
        _write_bank(
            run_root / "banks" / "random_k5",
            axis="random_k5",
            seed=seed,
            calibration=calibration,
            common_hashes=common_hashes,
        )
        for axis in GROUP_RANDOM_AXES:
            _write_bank(
                run_root / "banks" / axis,
                axis=axis,
                seed=seed,
                calibration=calibration,
                common_hashes=common_hashes,
            )
        cache_root = root / f"test-cache-seed-{seed}"
        _write_test_cache(
            cache_root,
            seed=seed,
            test=test,
            fingerprints=cache_fingerprints,
            bank_run=run_root,
        )
        bank_runs[seed] = run_root
        test_caches[seed] = cache_root
    return {
        "protocol": protocol_path,
        "router": router_path,
        "router_report": router_report_path,
        "sealed": sealed_path,
        "sealed_report": sealed_report_path,
        "bank_runs": bank_runs,
        "test_caches": test_caches,
        "calibration": calibration,
        "test": test,
    }


def _track_a_args(fixture: dict[str, object], output: Path):
    values = [
        "--protocol", str(fixture["protocol"]),
        "--router-artifact", str(fixture["router"]),
        "--router-report", str(fixture["router_report"]),
        "--sealed-test-assignments", str(fixture["sealed"]),
        "--sealed-test-report", str(fixture["sealed_report"]),
        "--output-dir", str(output),
        "--bootstrap-reps", "30",
        "--bootstrap-seed", "73",
    ]
    for seed in EXPECTED_SEEDS:
        values.extend([
            "--bank-run", f"{seed}={fixture['bank_runs'][seed]}",
            "--test-cache", f"{seed}={fixture['test_caches'][seed]}",
        ])
    return build_track_a_parser().parse_args(values)


def _track_b_args(
    fixture: dict[str, object], track_a_report: Path, output: Path
):
    values = [
        "--protocol", str(fixture["protocol"]),
        "--router-artifact", str(fixture["router"]),
        "--router-report", str(fixture["router_report"]),
        "--track-a-report", str(track_a_report),
        "--output-dir", str(output),
        "--bootstrap-reps", "30",
        "--bootstrap-seed", "91",
    ]
    for seed in EXPECTED_SEEDS:
        values.extend(["--bank-run", f"{seed}={fixture['bank_runs'][seed]}"])
    return build_track_b_parser().parse_args(values)


def test_track_a_then_track_b_end_to_end_with_firewall_and_output_guards(tmp_path):
    fixture = _write_fixture(tmp_path)

    # Track B must not inspect calibration search results until Track A has a
    # completed, explicitly test-accessing internal-replication report.
    premature_track_a = tmp_path / "premature-track-a.json"
    premature_track_a.write_text(json.dumps({
        "status": "running",
        "test_accessed": False,
        "internal_locked_replication": True,
    }))
    with pytest.raises(ValueError, match="Track A must complete"):
        evaluate_track_b(
            _track_b_args(fixture, premature_track_a, tmp_path / "too-early")
        )
    assert not (tmp_path / "too-early").exists()

    # Both evaluators must fail rather than overwrite or append to a nonempty
    # destination, even when all input artifacts are otherwise valid.
    blocked_a = tmp_path / "blocked-track-a"
    blocked_a.mkdir()
    (blocked_a / "sentinel").write_text("preserve")
    with pytest.raises(FileExistsError, match="not empty"):
        evaluate_track_a(_track_a_args(fixture, blocked_a))
    assert (blocked_a / "sentinel").read_text() == "preserve"
    assert not (blocked_a / "report.json").exists()

    track_a_root = tmp_path / "track-a"
    track_a = evaluate_track_a(_track_a_args(fixture, track_a_root))
    track_a_report = track_a_root / "report.json"
    assert track_a["status"] == "complete"
    assert track_a["test_accessed"] is True
    assert track_a["internal_locked_replication"] is True
    assert track_a["independent_confirmation"] is False
    for comparison_name in (
        "true_organ_hard_vs_assigned_random_k5",
        "true_organ_hard_vs_calibration_selected_random",
    ):
        family = track_a["comparisons"][comparison_name]
        assert set(family["partition_comparisons"]) == set(GROUP_RANDOM_AXES)
        assert "every partition must pass" in family["aggregation"]
    for seed in EXPECTED_SEEDS:
        assert set(track_a["inputs"]["bank_artifact_hashes"][str(seed)]) == {
            "organ_k5",
            "random_k5",
            *GROUP_RANDOM_AXES,
        }
        for axis in ("organ_k5", "random_k5", *GROUP_RANDOM_AXES):
            metadata_path = (
                fixture["bank_runs"][seed]
                / "banks"
                / axis
                / "run_metadata.json"
            )
            metadata = json.loads(metadata_path.read_text())
            assert metadata["calibration_metrics"][
                "full_calibration_fixed_weights"
            ] == [0.2] * 5
    assert track_a_report.stat().st_size > 0
    assert (track_a_root / "decision_scores.npz").stat().st_size > 0
    assert (track_a_root / "COMPLETE").is_file()
    track_a_hash_before_b = _sha256(track_a_report)

    blocked_b = tmp_path / "blocked-track-b"
    blocked_b.mkdir()
    (blocked_b / "sentinel").write_text("preserve")
    with pytest.raises(FileExistsError, match="not empty"):
        evaluate_track_b(_track_b_args(fixture, track_a_report, blocked_b))
    assert (blocked_b / "sentinel").read_text() == "preserve"
    assert not (blocked_b / "report.json").exists()

    track_b_root = tmp_path / "track-b"
    track_b = evaluate_track_b(
        _track_b_args(fixture, track_a_report, track_b_root)
    )
    assert track_b["status"] == "complete"
    assert track_b["test_accessed"] is False
    assert track_b["test_features_loaded"] is False
    assert track_b["test_targets_loaded"] is False
    assert track_b["selection_is_development_only"] is True
    assert track_b["strict_outer_inner_router"] is True
    assert track_b["router_policy"] == "common_k5_probability_collapse"
    assert track_b["decision"]["automatic_test_authorization"] is False
    for candidate in track_b["decision"]["candidates"]:
        k = int(candidate["k"])
        assert set(candidate["outer_fold_selected_subset_id"]) == {
            str(fold) for fold in range(5)
        }
        assert set(candidate["outer_fold_selected_random_subset_id"]) == set(
            GROUP_RANDOM_AXES
        )
        for axis in GROUP_RANDOM_AXES:
            selected = candidate["outer_fold_selected_random_subset_id"][axis]
            assert set(selected) == {str(fold) for fold in range(5)}
            assert all(int(subset_id).bit_count() == k for subset_id in selected.values())
            scores = candidate["outer_fold_random_fit_subset_scores"][axis]
            assert all(
                len(fold_scores) == math.comb(5, k)
                for fold_scores in scores.values()
            )
    candidates = track_b["decision"]["candidates"]
    assert [row["k"] for row in candidates] == list(range(1, 6))
    random_test_count = 0
    for row in candidates:
        k = row["k"]
        expected_subsets = (5, 10, 10, 5, 1)[k - 1]
        assert len(row["full_calibration_subset_scores"]) == expected_subsets
        assert len(row["outer_fold_selected_subset_id"]) == 5
        for subset_id in row["outer_fold_selected_subset_id"].values():
            assert bin(subset_id).count("1") == k
        for fit_scores in row["outer_fold_fit_subset_scores"].values():
            assert len(fit_scores) == expected_subsets
        assert set(row["random_partition_tests"]) == set(GROUP_RANDOM_AXES)
        for test in row["random_partition_tests"].values():
            assert "adjusted_p_value" in test
            assert "passes_holm" in test
            random_test_count += 1
    assert random_test_count == 15
    assert _sha256(track_a_report) == track_a_hash_before_b
    assert track_b["hashes"]["track_a_report_sha256"] == track_a_hash_before_b
    assert (track_b_root / "report.json").stat().st_size > 0
    score_path = track_b_root / "calibration_k_scores.npz"
    assert score_path.stat().st_size > 0
    assert (track_b_root / "COMPLETE").is_file()
    with np.load(score_path, allow_pickle=False) as scores:
        assert np.array_equal(
            scores["sample_ids"].astype(str),
            fixture["calibration"]["sample_ids"].astype(str),
        )
        assert not set(scores["sample_ids"].astype(str)) & set(
            fixture["test"]["sample_ids"].astype(str)
        )
        for k in range(1, 6):
            for axis in GROUP_RANDOM_AXES:
                assert scores[f"k{k}_{axis}_mse"].shape == (
                    len(EXPECTED_SEEDS),
                    len(fixture["calibration"]["sample_ids"]),
                )
