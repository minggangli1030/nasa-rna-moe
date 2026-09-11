from __future__ import annotations

import json
import sys
from argparse import Namespace
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))
sys.path.insert(0, str(ROOT / "evaluation"))

from cache_organ_k_confirmation_scores import (  # noqa: E402
    CANONICAL_ORGANS,
    CANONICAL_RANDOM_SHARDS,
    ExpertBank,
    GROUP_RANDOM_AXES,
    _assignment_hash,
    _sha256_array,
    build_cache,
    mask_score_genes,
)
from evaluate_organ_k_confirmation import _load_cache  # noqa: E402
from train_manifest import sha256_file, sha256_json, sha256_lines  # noqa: E402
from train_single import ExpressionPerformer  # noqa: E402


def _write_fixture(root: Path) -> tuple[Namespace, pd.DataFrame, list[str], np.ndarray]:
    root.mkdir(parents=True, exist_ok=True)
    genes = [f"g{index}" for index in range(10)]
    score = np.asarray([1, 4, 8], dtype=np.int64)
    rows: list[dict] = []
    expression_rows: list[dict] = []
    for split_index, split in enumerate(("train", "calibration", "test")):
        for organ_index, organ in enumerate(CANONICAL_ORGANS):
            sample_id = f"{split}-{organ}"
            random_index = (organ_index + 2) % 5
            rows.append({
                "sample_id": sample_id,
                "organ": organ,
                "series_group_id": f"{split}-study-{organ}",
                "split": split,
                "balanced_train": split == "train",
                "random_shard": CANONICAL_RANDOM_SHARDS[random_index],
            })
            values = {
                gene: np.float32(
                    0.5 + split_index + organ_index / 10.0 + gene_index / 50.0
                )
                for gene_index, gene in enumerate(genes)
            }
            expression_rows.append({"sample_id": sample_id, **values})
    manifest_frame = pd.DataFrame(rows)
    manifest = root / "manifest.parquet"
    manifest_frame.to_parquet(manifest, index=False)
    expression_frame = pd.DataFrame(expression_rows)
    expression = root / "expression.parquet"
    pq.write_table(pa.Table.from_pandas(expression_frame), expression, row_group_size=3)
    expression_metadata = root / "extraction_report.json"
    expression_metadata.write_text(json.dumps({
        "status": "complete",
        "expression_space": "tpm",
        "gene_order_sha256": sha256_lines(genes),
    }))

    trunk = ExpressionPerformer(
        num_genes=len(genes),
        hidden_dim=8,
        n_heads=2,
        n_layers=1,
        ffn_dim=16,
        gradient_checkpointing=False,
    )
    pooled = root / "pooled.pt"
    torch.save({
        "schema_version": 1,
        "update": 7,
        "config": {
            "num_genes": len(genes),
            "hidden_dim": 8,
            "ffn_dim": 16,
            "num_heads": 2,
            "num_layers": 1,
            "ree_base": 100.0,
            "feature_type": "sqr",
            "compute_type": "iter",
            "mask_token": -10.0,
            "normalization": "log1p_tpm",
            "gene_list": genes,
        },
        "model_state_dict": trunk.state_dict(),
    }, pooled)
    definitions = root / "axis_definitions.npz"
    np.savez_compressed(
        definitions,
        gene_names=np.asarray(genes, dtype=str),
        score_gene_indices=score,
        probe_gene_indices=np.asarray([0, 2], dtype=np.int64),
        context_gene_indices=np.asarray([3, 5, 6, 7, 9], dtype=np.int64),
    )

    sealed = manifest_frame.loc[manifest_frame["split"].eq("test")].copy()
    sealed = sealed.sort_values("sample_id").reset_index(drop=True)
    sealed.insert(1, "utility_split", "test")
    sealed["organ_k5"] = sealed["organ"].map(
        {name: index for index, name in enumerate(CANONICAL_ORGANS)}
    ).astype(np.int64)
    sealed["random_k5"] = sealed["random_shard"].map(
        {name: index for index, name in enumerate(CANONICAL_RANDOM_SHARDS)}
    ).astype(np.int64)
    for partition_index, axis in enumerate(GROUP_RANDOM_AXES):
        sealed[axis] = (
            sealed["organ_k5"].to_numpy(dtype=np.int64)
            + partition_index
            + 1
        ) % 5
    sealed = sealed[
        [
            "sample_id",
            "utility_split",
            "split",
            "organ",
            "series_group_id",
            "random_shard",
            "organ_k5",
            "random_k5",
            *GROUP_RANDOM_AXES,
        ]
    ]
    sealed_path = root / "sealed_test_assignments.parquet"
    sealed.to_parquet(sealed_path, index=False)
    sealed_report = root / "sealed_test_report.json"
    sealed_report.write_text(json.dumps({
        "schema_version": 1,
        "status": "complete",
        "artifact_role": "sealed_test_assignment_metadata",
        "sealed": True,
        "test_accessed": False,
        "test_expression_accessed": False,
        "test_targets_accessed": False,
        "counts": {"test": len(sealed)},
        "mappings": {
            "organ_k5": {
                name: index for index, name in enumerate(CANONICAL_ORGANS)
            },
            "random_k5": {
                name: index for index, name in enumerate(CANONICAL_RANDOM_SHARDS)
            },
            **{
                axis: {f"random_group_{index}": index for index in range(5)}
                for axis in GROUP_RANDOM_AXES
            },
        },
        "hashes": {
            "manifest_sha256": sha256_file(manifest),
            "sealed_test_assignments_sha256": sha256_file(sealed_path),
            "test_sample_ids_sha256": sha256_lines(sealed["sample_id"].tolist()),
            "test_organ_assignment_sha256": _assignment_hash(sealed, "organ"),
            "test_random_shard_assignment_sha256": _assignment_hash(
                sealed, "random_shard"
            ),
            **{
                f"test_{axis}_assignment_sha256": _assignment_hash(sealed, axis)
                for axis in GROUP_RANDOM_AXES
            },
        },
        "guardrail": "metadata-only fixture",
    }))

    protocol = root / "protocol.json"
    protocol.write_text(json.dumps({
        "schema_version": 1,
        "authorization": {"requested_by_user": True},
        "evidence_label": {
            "internal_locked_replication": True,
            "independent_confirmation": False,
        },
    }, sort_keys=True))

    common_hashes = {
        "pooled_checkpoint_sha256": sha256_file(pooled),
        "expression_sha256": sha256_file(expression),
        "manifest_sha256": sha256_file(manifest),
        "axis_definitions_sha256": sha256_file(definitions),
        "protocol_sha256": sha256_file(protocol),
        "partition_manifest_sha256": "2" * 64,
        "score_gene_indices_sha256": sha256_lines(score.tolist()),
    }
    bank_biases = {
        "organ_k5": [0.0, 0.1, 0.2, 0.3, 0.4],
        "random_k5": [0.0, -0.05, -0.10, -0.15, -0.20],
        "random_group_k5_p17": [0.01, 0.02, 0.03, 0.04, 0.05],
        "random_group_k5_p42": [-0.01, -0.02, -0.03, -0.04, -0.05],
        "random_group_k5_p101": [0.02, 0.04, 0.06, 0.08, 0.10],
    }
    for axis, biases in bank_biases.items():
        bank_dir = root / axis
        bank_dir.mkdir()
        model = ExpertBank(hidden_dim=8, adapter_dim=4)
        with torch.no_grad():
            for expert, bias in zip(model.experts, biases):
                for parameter in expert.parameters():
                    parameter.zero_()
                expert.up.bias.fill_(bias)
        config = {
            "axis": axis,
            "num_experts": 5,
            "adapter_dim": 4,
            "router_trainable": False,
            "final_update": 1500,
            "score_gene_count": len(score),
            "checkpoint_policy": "predetermined_final_update",
        }
        checkpoint_path = bank_dir / "final_experts.pt"
        torch.save({
            "schema_version": 1,
            "axis": axis,
            "training_seed": 17,
            "final_update": 1500,
            "config": config,
            "expert_state_dict": model.state_dict(),
            "pooled_checkpoint_sha256": common_hashes["pooled_checkpoint_sha256"],
        }, checkpoint_path)
        (bank_dir / "run_metadata.json").write_text(json.dumps({
            "schema_version": 1,
            "status": "complete",
            "axis": axis,
            "training_seed": 17,
            "test_accessed": False,
            "mechanical_only": False,
            "config": config,
            "calibration_metrics": {
                "full_calibration_fixed_weights": [0.2] * 5,
            },
            "hashes": {
                **common_hashes,
                "resolved_config_sha256": sha256_json(config),
            },
            "artifacts": {
                "final_experts_sha256": sha256_file(checkpoint_path),
            },
        }))
        (bank_dir / "COMPLETE").touch()

    router = root / "organ_k_router.npz"
    classes = np.asarray(CANONICAL_ORGANS, dtype=str)
    scaler_mean = np.zeros(len(genes), dtype=np.float64)
    scaler_scale = np.ones(len(genes), dtype=np.float64)
    coefficients = np.zeros((5, len(genes)), dtype=np.float64)
    intercepts = np.arange(5, dtype=np.float64) / 10.0
    np.savez_compressed(
        router,
        gene_names=np.asarray(genes, dtype=str),
        score_gene_indices=score,
        mask_token=np.asarray(-10.0, dtype=np.float64),
        k5_full_classes=classes,
        k5_full_scaler_mean=scaler_mean,
        k5_full_scaler_scale=scaler_scale,
        k5_full_coefficients=coefficients,
        k5_full_intercepts=intercepts,
    )
    router_report = root / "router_report.json"
    router_report.write_text(json.dumps({
        "schema_version": 1,
        "status": "complete",
        "test_accessed": False,
        "test_features_loaded": False,
        "target_hiding": {"score_genes_masked_for_every_sample": True},
        "config": {"mask_token": -10.0},
        "full_calibration_k5": {
            "scaler_mean_sha256": _sha256_array(scaler_mean),
            "scaler_scale_sha256": _sha256_array(scaler_scale),
            "coefficient_sha256": _sha256_array(coefficients),
            "intercept_sha256": _sha256_array(intercepts),
        },
        "hashes": {
            "router_artifact_sha256": sha256_file(router),
            "expression_parquet_sha256": sha256_file(expression),
            "expression_metadata_sha256": sha256_file(expression_metadata),
            "source_manifest_sha256": sha256_file(manifest),
            "axis_definitions_sha256": sha256_file(definitions),
            "gene_order_sha256": sha256_lines(genes),
        },
    }))

    args = Namespace(
        protocol=str(protocol),
        expression_parquet=str(expression),
        expression_metadata=str(expression_metadata),
        manifest=str(manifest),
        pooled_checkpoint=str(pooled),
        axis_definitions=str(definitions),
        sealed_test_assignments=str(sealed_path),
        sealed_test_report=str(sealed_report),
        organ_bank_dir=str(root / "organ_k5"),
        random_bank_dir=str(root / "random_k5"),
        group_random_bank=[
            f"{axis}={root / axis}" for axis in GROUP_RANDOM_AXES
        ],
        router_artifact=str(router),
        router_report=str(router_report),
        output_dir=str(root / "output"),
        expected_seed=17,
        expected_final_update=1500,
        batch_size=2,
        device="cpu",
        sample_id_column="sample_id",
        organ_column="organ",
        group_column="series_group_id",
        split_column="split",
        random_shard_column="random_shard",
        train_filter_column="balanced_train",
        train_split="train",
        test_split="test",
    )
    return args, expression_frame, genes, score


def test_reloads_fixed_banks_and_caches_canonical_dispatch_shapes(tmp_path):
    args, expression, _, score = _write_fixture(tmp_path)
    report = build_cache(args)
    output = Path(args.output_dir) / "test_scores.npz"
    with np.load(output, allow_pickle=False) as cache:
        assert cache["sample_ids"].shape == (5,)
        assert cache["target_masked"].shape == (5, len(score))
        assert cache["baseline_masked"].shape == (5, len(score))
        assert cache["pooled_masked"].shape == (5, len(score))
        assert cache["organ_expert_masked"].shape == (5, 5, len(score))
        assert cache["random_expert_masked"].shape == (5, 5, len(score))
        for axis in GROUP_RANDOM_AXES:
            assert cache[f"{axis}_labels"].shape == (5,)
            assert cache[f"{axis}_expert_masked"].shape == (5, 5, len(score))
        assert cache["blind_k5_probabilities"].shape == (5, 5)
        assert np.allclose(cache["blind_k5_probabilities"].sum(axis=1), 1.0)
        assert set(cache["blind_k5_predicted_organ"]) == {"skin"}
        assert np.array_equal(cache["organ_labels"], np.arange(5))

        pooled = cache["pooled_masked"]
        for expert, bias in enumerate((0.0, 0.1, 0.2, 0.3, 0.4)):
            assert np.allclose(
                cache["organ_expert_masked"][:, expert] - pooled,
                bias,
                atol=1e-6,
            )
        for expert, bias in enumerate((0.0, -0.05, -0.10, -0.15, -0.20)):
            assert np.allclose(
                cache["random_expert_masked"][:, expert] - pooled,
                bias,
                atol=1e-6,
            )
        for axis, biases in {
            "random_group_k5_p17": (0.01, 0.02, 0.03, 0.04, 0.05),
            "random_group_k5_p42": (-0.01, -0.02, -0.03, -0.04, -0.05),
            "random_group_k5_p101": (0.02, 0.04, 0.06, 0.08, 0.10),
        }.items():
            for expert, bias in enumerate(biases):
                assert np.allclose(
                    cache[f"{axis}_expert_masked"][:, expert] - pooled,
                    bias,
                    atol=1e-6,
                )
        row = np.arange(5)
        dispatched = cache["organ_expert_masked"][row, cache["organ_labels"]]
        expected_bias = cache["organ_labels"][:, None] / 10.0
        assert np.allclose(dispatched - pooled, expected_bias, atol=1e-6)

        test = expression.loc[expression["sample_id"].str.startswith("test-")].copy()
        test = test.sort_values("sample_id")
        expected_target = np.log1p(
            test[[f"g{index}" for index in score]].to_numpy(dtype=np.float32)
        )
        assert np.allclose(cache["target_masked"], expected_target)
        assert json.loads(str(cache["metadata_json"].item()))["test_accessed"] is True

    assert report["status"] == "complete"
    assert report["internal_locked_replication"] is True
    assert report["test_accessed"] is True
    assert report["baseline"]["test_targets_used_for_fit"] is False
    assert report["baseline"]["n_fit_samples"] == 5
    assert report["router"]["router_was_prefrozen"] is True
    assert report["router"]["target_hiding_verified"] is True
    assert set(report["banks"]) == {
        "organ_k5",
        "random_k5",
        *GROUP_RANDOM_AXES,
    }
    for axis in GROUP_RANDOM_AXES:
        assert f"test_{axis}_assignment_sha256" in report["hashes"]
    assert report["artifacts"]["test_scores_sha256"] == sha256_file(output)
    loaded = _load_cache(Path(args.output_dir), seed=17)
    assert loaded["split"] == "test"
    assert loaded["authorized_test_access"] is True


def test_score_mask_hides_only_frozen_panel():
    values = np.arange(24, dtype=np.float32).reshape(3, 8)
    original = values.copy()
    masked = mask_score_genes(values, np.asarray([1, 5, 7]), -10.0)
    assert np.array_equal(values, original)
    assert np.all(masked[:, [1, 5, 7]] == -10.0)
    assert np.array_equal(masked[:, [0, 2, 3, 4, 6]], original[:, [0, 2, 3, 4, 6]])
    with pytest.raises(ValueError, match="duplicates"):
        mask_score_genes(values, np.asarray([1, 1]), -10.0)


def test_rejects_source_split_group_leakage_before_test_scoring(tmp_path):
    args, _, _, _ = _write_fixture(tmp_path)
    manifest = pd.read_parquet(args.manifest)
    train_group = manifest.loc[manifest["split"].eq("train"), "series_group_id"].iloc[0]
    test_row = manifest.index[manifest["split"].eq("test")][0]
    manifest.loc[test_row, "series_group_id"] = train_group
    manifest.to_parquet(args.manifest, index=False)
    with pytest.raises(ValueError, match="connected study groups cross"):
        build_cache(args)


def test_rejects_nonexact_sealed_ids_and_bank_seed_mismatch(tmp_path):
    args, _, _, _ = _write_fixture(tmp_path)
    sealed = pd.read_parquet(args.sealed_test_assignments).iloc[:-1]
    sealed.to_parquet(args.sealed_test_assignments, index=False)
    with pytest.raises(ValueError, match="do not exactly match"):
        build_cache(args)

    args, _, _, _ = _write_fixture(tmp_path / "seed")
    metadata_path = Path(args.random_bank_dir) / "run_metadata.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["training_seed"] = 42
    metadata_path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="bank seed"):
        build_cache(args)


def test_cache_archive_and_content_hashes_are_deterministic(tmp_path):
    args, _, _, _ = _write_fixture(tmp_path)
    first_report = build_cache(args)
    first_path = Path(args.output_dir) / "test_scores.npz"
    first_hash = sha256_file(first_path)

    args.output_dir = str(tmp_path / "second-output")
    second_report = build_cache(args)
    second_path = Path(args.output_dir) / "test_scores.npz"
    assert sha256_file(second_path) == first_hash
    assert second_report["content_sha256"] == first_report["content_sha256"]
    assert second_report["hashes"] == first_report["hashes"]
    with np.load(second_path, allow_pickle=False) as cache:
        for name, expected in second_report["content_sha256"].items():
            assert _sha256_array(cache[name]) == expected
