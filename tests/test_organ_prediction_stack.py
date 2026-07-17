from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evaluation"))

from cache_organ_predictions import build_cache, deterministic_mask_indices  # noqa: E402
from decide_organ_specialization import decide  # noqa: E402
from evaluate_organ_moe import (  # noqa: E402
    apply_sample_weights,
    evaluate,
    masked_gate_features,
    per_sample_simplex_weights,
)


def test_masks_are_deterministic_and_sample_order_independent():
    ids = np.array(["s3", "s1", "s2"])
    first = deterministic_mask_indices(ids, 20, seed=17, mask_fraction=0.3)
    reordered_ids = ids[[1, 2, 0]]
    second = deterministic_mask_indices(reordered_ids, 20, seed=17, mask_fraction=0.3)
    by_id = {sample: mask for sample, mask in zip(reordered_ids, second)}
    for sample, mask in zip(ids, first):
        np.testing.assert_array_equal(mask, by_id[sample])
    # Match the Stage 0/trainer contract: floor, not round (16 * .30 = 4.8).
    assert deterministic_mask_indices(ids, 16, seed=17, mask_fraction=0.3).shape[1] == 4


def test_exact_soft_oracle_reaches_best_vertex_on_shared_offset_case():
    n_experts = n_positions = 5
    predictions = np.asarray([
        np.full(n_positions, 10.0) + np.eye(n_positions)[expert] * 0.2
        for expert in range(n_experts)
    ])
    truth = predictions[0][None, :]
    weights = per_sample_simplex_weights(predictions[:, None, :], truth)
    mixed = apply_sample_weights(predictions[:, None, :], weights)
    np.testing.assert_allclose(weights[0], [1, 0, 0, 0, 0], atol=1e-7)
    assert float(np.mean((mixed - truth) ** 2)) < 1e-12


def _write_npz(
    path: Path, sample_ids: np.ndarray, genes: np.ndarray, key: str,
    values: np.ndarray, value_space: str, *, targets: np.ndarray | None = None,
    provenance: dict | None = None,
) -> None:
    fields = {
        "sample_ids": sample_ids.astype("U"),
        "genes": genes.astype("U"),
        **{key: values.astype(np.float32)},
        "value_space": np.asarray(value_space),
    }
    if key == "predictions":
        assert targets is not None and provenance is not None
        fields.update({
            "targets": targets.astype(np.float32),
            "mask_indices": deterministic_mask_indices(
                sample_ids, len(genes), seed=31, mask_fraction=0.30
            ).astype(np.int64),
            "mask_seed": np.asarray(31, dtype=np.int64),
            "mask_algorithm": np.asarray("organ-moe-mask-v1"),
            "mask_ratio": np.asarray(0.30, dtype=np.float64),
            "mask_token": np.asarray(-10.0, dtype=np.float64),
            "model_role": np.asarray(provenance["model_role"]),
            "model_selector_json": np.asarray(json.dumps(provenance["model_selector"])),
            "training_seed": np.asarray(17, dtype=np.int64),
            "train_sample_ids_sha256": np.asarray(provenance["train_hash"]),
            "checkpoint_sha256": np.asarray(provenance["checkpoint_sha256"]),
            "expression_file_sha256": np.asarray(provenance["expression_file_sha256"]),
        })
    np.savez_compressed(path, **fields)


def test_cache_and_evaluator_run_end_to_end_without_target_visible_router(tmp_path):
    rng = np.random.default_rng(8)
    organ_names = ["brain", "liver", "lung"]
    split_names = ["train", "calibration", "test"]
    rows = []
    for split in split_names:
        for organ in organ_names:
            for group_index in range(2):
                group = f"{split}-{organ}-{group_index}"
                for sample_index in range(2):
                    rows.append((f"{group}-{sample_index}", organ, group, split))
    manifest = pd.DataFrame(rows, columns=["sample_id", "organ", "series_group_id", "split"])
    manifest["balanced_train"] = manifest["split"].eq("train")
    manifest["random_shard"] = [
        organ_names[index % len(organ_names)] for index in range(len(manifest))
    ]
    manifest_path = tmp_path / "manifest.csv"
    manifest.to_csv(manifest_path, index=False)
    sample_ids = manifest["sample_id"].to_numpy(dtype=str)
    organs = manifest["organ"].to_numpy(dtype=str)
    genes = np.asarray([f"g{i}" for i in range(15)])

    bases = {
        "brain": np.r_[np.full(5, 7.0), np.full(10, 1.0)],
        "liver": np.r_[np.full(5, 1.0), np.full(5, 7.0), np.full(5, 1.0)],
        "lung": np.r_[np.full(10, 1.0), np.full(5, 7.0)],
    }
    target = np.stack([bases[organ] + rng.normal(0.0, 0.40, len(genes)) for organ in organs])
    target = np.maximum(target, 0.05).astype(np.float32)
    raw_tpm = np.expm1(target)
    expression_path = tmp_path / "expression.parquet"
    expression_frame = pd.DataFrame(raw_tpm, columns=genes)
    expression_frame.insert(0, "sample_id", sample_ids)
    expression_frame.to_parquet(expression_path, index=False)
    expression_hash = hashlib.sha256(expression_path.read_bytes()).hexdigest()
    export_target = np.log1p(
        pd.read_parquet(expression_path)[genes.tolist()].to_numpy(dtype=np.float32)
    ).astype(np.float32)

    def train_hash(role: str, label: str | None = None) -> str:
        keep = manifest["balanced_train"].to_numpy(copy=True)
        if role == "organ":
            keep &= manifest["organ"].eq(label).to_numpy()
        elif role == "random":
            keep &= manifest["random_shard"].eq(label).to_numpy()
        ids = sorted(manifest.loc[keep, "sample_id"].astype(str))
        return hashlib.sha256("".join(f"{value}\n" for value in ids).encode()).hexdigest()

    def provenance(role: str, label: str | None = None) -> dict:
        selector = {"role": role}
        if role == "organ":
            selector["organ"] = str(label)
        elif role == "random":
            selector["random_shard"] = str(label)
        return {
            "model_role": role,
            "model_selector": selector,
            "train_hash": train_hash(role, label),
            "checkpoint_sha256": hashlib.sha256(f"{role}:{label}".encode()).hexdigest(),
            "expression_file_sha256": expression_hash,
        }

    prediction_specs = []
    pooled = target + rng.normal(0.0, 0.12, target.shape)
    pooled_path = tmp_path / "pooled.npz"
    _write_npz(
        pooled_path, sample_ids, genes, "predictions", pooled, "log1p_tpm",
        targets=export_target, provenance=provenance("pooled"),
    )
    prediction_specs.append(f"pooled={pooled_path}")
    for expert_index, expert in enumerate(organ_names):
        scale = np.where(organs[:, None] == expert, 0.025, 0.50)
        values = target + rng.normal(size=target.shape) * scale
        path = tmp_path / f"organ-{expert}.npz"
        _write_npz(
            path, sample_ids, genes, "predictions", values, "log1p_tpm",
            targets=export_target, provenance=provenance("organ", expert),
        )
        prediction_specs.append(f"organ:{expert}={path}")
    for shard_index, shard in enumerate(organ_names):
        values = target + rng.normal(0.0, 0.38, target.shape)
        path = tmp_path / f"random-{shard}.npz"
        _write_npz(
            path, sample_ids, genes, "predictions", values, "log1p_tpm",
            targets=export_target, provenance=provenance("random", shard),
        )
        prediction_specs.append(f"random:{shard}={path}")

    cache_path = tmp_path / "cache.npz"
    metadata = build_cache(SimpleNamespace(
        manifest_csv=manifest_path,
        expression=expression_path,
        prediction=prediction_specs,
        output=cache_path,
        train_filter_column="balanced_train",
        train_split="train",
        random_shard_column="random_shard",
        mask_seed=31,
        mask_fraction=0.30,
        mask_count=None,
        mask_token=-10.0,
        expression_input_space="tpm",
        prediction_input_space="log1p_tpm",
    ))
    assert metadata["value_space_contract"]["expression_transform"] == "log1p"
    with np.load(cache_path, allow_pickle=False) as cache:
        np.testing.assert_allclose(cache["gt"], target, rtol=1e-6, atol=1e-6)
        observed = masked_gate_features(cache["gt"], cache["mask_idx"], -10.0)
        gathered = observed[np.arange(len(observed))[:, None], cache["mask_idx"]]
        np.testing.assert_array_equal(gathered, -10.0)

    report = evaluate(SimpleNamespace(
        cache=cache_path,
        output_dir=tmp_path / "evaluation",
        train_split="train",
        calibration_split="calibration",
        test_split="test",
        mask_token=-10.0,
        seed=19,
        training_seed=17,
        bootstrap_reps=80,
        classifier_max_iter=1000,
    ))
    assert report["validation"]["leakage_free"]
    assert report["router"]["training_split"] == "calibration"
    assert report["router"]["uses_reconstruction_targets"] is False
    assert report["router"]["uses_test_labels_or_targets_for_fit"] is False
    assert report["router"]["test_balanced_accuracy"] > 0.75
    assert report["comparisons"]["true_organ_hard_vs_pooled"]["primary"][
        "mse_improvement_mean"
    ] > 0.0
    assert "random_soft_oracle_vs_random_fixed" in report["comparisons"]
    assert "primary_balanced_organ_study_macro" in report["conditions"]["pooled"]
    assert "secondary_natural_sample_mean" in report["conditions"]["pooled"]
    assert (tmp_path / "evaluation" / "report.json").is_file()
    assert (tmp_path / "evaluation" / "per_sample_metrics.csv").is_file()

    with np.load(pooled_path, allow_pickle=False) as exported:
        bad_export = {name: np.asarray(exported[name]) for name in exported.files}
    bad_export["mask_seed"] = np.asarray(999, dtype=np.int64)
    np.savez_compressed(pooled_path, **bad_export)
    with pytest.raises(ValueError, match="mask_seed 999"):
        build_cache(SimpleNamespace(
            manifest_csv=manifest_path,
            expression=expression_path,
            prediction=prediction_specs,
            output=tmp_path / "bad-cache.npz",
            train_filter_column="balanced_train",
            train_split="train",
            random_shard_column="random_shard",
            mask_seed=31,
            mask_fraction=0.30,
            mask_count=None,
            mask_token=-10.0,
            expression_input_space="tpm",
            prediction_input_space="log1p_tpm",
        ))


def _primary(relative: float = 0.10, effect: float = 1.0) -> dict:
    return {
        "mse_improvement_mean": effect,
        "mse_improvement_ci95": [effect * 0.8, effect * 1.2],
        "relative_mse_reduction": relative,
        "pearson_gain_mean": 0.1,
        "pearson_gain_ci95": [0.08, 0.12],
        "residual_pearson_gain_mean": 0.1,
        "residual_pearson_gain_ci95": [0.08, 0.12],
        "candidate_mse": 9.0,
        "reference_mse": 10.0,
    }


def _seed_report(seed: int) -> dict:
    names = (
        "true_organ_hard_vs_pooled", "soft_oracle_vs_organ_fixed",
        "organ_fixed_vs_random_fixed", "blind_hard_vs_pooled",
        "blind_hard_vs_organ_fixed", "blind_soft_vs_organ_fixed",
    )
    comparison = lambda name: {"name": name, "primary": _primary()}  # noqa: E731
    pooled = comparison("pooled_vs_gene_mean")
    return {
        "training_seed": seed,
        "splits": {
            "test_sample_id_sha256": "samples", "test_group_id_sha256": "groups",
            "test_organ_sha256": "organs", "mask_idx_sha256": "masks",
        },
        "validation": {
            "leakage_free": True, "random_shard_count_matches_organs": True,
            "mask_hash_verified": True, "prediction_masks_match_cache": True,
            "sample_hash_verified": True,
            "gene_hash_verified": True,
        },
        "cache_metadata": {
            "value_space": "log1p_tpm",
            "value_space_contract": {
                "prediction_input": "log1p_tpm", "cache_targets": "log1p_tpm",
                "cache_predictions": "log1p_tpm",
            },
            "content_sha256": {"genes": "genes"},
        },
        "comparisons": {name: comparison(name) for name in names},
        "backbone_checks": {
            "pooled_vs_gene_mean": pooled,
            "by_organ": {
                organ: comparison(f"expert_{organ}_vs_gene_mean")
                for organ in ("brain", "liver", "lung")
            },
        },
    }


def test_decider_emits_green_named_amber_branches_and_red():
    reports = [_seed_report(seed) for seed in (17, 42, 101)]
    assert decide(copy.deepcopy(reports))["status"] == "green"

    router_failure = copy.deepcopy(reports)
    for report in router_failure:
        report["comparisons"]["blind_hard_vs_pooled"]["primary"] = _primary(0.01)
        report["comparisons"]["blind_hard_vs_organ_fixed"]["primary"] = _primary(-0.01, -0.1)
        report["comparisons"]["blind_soft_vs_organ_fixed"]["primary"] = _primary(0.01)
    assert decide(router_failure)["status"] == "amber_router"

    ensemble_only = copy.deepcopy(reports)
    for report in ensemble_only:
        report["comparisons"]["blind_hard_vs_pooled"]["primary"] = _primary(0.01)
        report["comparisons"]["blind_hard_vs_organ_fixed"]["primary"] = _primary(0.02)
        report["comparisons"]["blind_soft_vs_organ_fixed"]["primary"] = _primary(0.01)
    assert decide(ensemble_only)["status"] == "amber_ensemble"

    wrong_axis = copy.deepcopy(reports)
    for report in wrong_axis:
        report["comparisons"]["true_organ_hard_vs_pooled"]["primary"] = _primary(0.01)
    assert decide(wrong_axis)["status"] == "amber_axis"

    no_oracle = copy.deepcopy(reports)
    for report in no_oracle:
        report["comparisons"]["soft_oracle_vs_organ_fixed"]["primary"] = _primary(0.01)
    assert decide(no_oracle)["status"] == "red"
