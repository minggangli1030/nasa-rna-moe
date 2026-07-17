from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

from train_manifest import (  # noqa: E402
    DeterministicBudgetBatchSampler,
    DeterministicMaskedExpressionDataset,
    build_exposure_frame,
    balanced_validation_weights,
    deterministic_mask_indices,
    load_expression_rows,
    run_training,
    select_manifest_rows,
    sha256_lines,
    summarize_exposures,
    validate_expression_metadata,
)


def test_validation_weights_prevent_brain_and_large_studies_from_dominating():
    frame = pd.DataFrame([
        {"organ": "brain", "series_group_id": "brain-large"},
        {"organ": "brain", "series_group_id": "brain-large"},
        {"organ": "brain", "series_group_id": "brain-small"},
        {"organ": "skin", "series_group_id": "skin-only"},
    ])
    weights = balanced_validation_weights(frame)
    np.testing.assert_allclose(weights, [0.125, 0.125, 0.25, 0.5])


def test_manifest_roles_use_only_explicit_disjoint_splits():
    frame = pd.DataFrame([
        {"sample_id": "b-train", "organ": "brain", "series_group_id": "gb1", "split": "train", "random_shard": "r0"},
        {"sample_id": "s-train", "organ": "skin", "series_group_id": "gs1", "split": "train", "random_shard": "r1"},
        {"sample_id": "b-val", "organ": "brain", "series_group_id": "gb2", "split": "validation", "random_shard": "r0"},
        {"sample_id": "s-val", "organ": "skin", "series_group_id": "gs2", "split": "validation", "random_shard": "r1"},
        {"sample_id": "held", "organ": "brain", "series_group_id": "gb3", "split": "test", "random_shard": "r0"},
    ])
    pooled = select_manifest_rows(
        frame, role="pooled", train_split="train", validation_split="validation"
    )
    assert pooled.train["sample_id"].tolist() == ["b-train", "s-train"]
    assert pooled.validation["sample_id"].tolist() == ["b-val", "s-val"]
    organ = select_manifest_rows(
        frame,
        role="organ",
        organ="brain",
        train_split="train",
        validation_split="validation",
    )
    assert organ.train["sample_id"].tolist() == ["b-train"]
    random = select_manifest_rows(
        frame,
        role="random",
        random_shard="r1",
        train_split="train",
        validation_split="validation",
    )
    assert random.train["sample_id"].tolist() == ["s-train"]
    assert "held" not in set(pd.concat([pooled.train, pooled.validation])["sample_id"])


def test_manifest_rejects_connected_group_leakage():
    frame = pd.DataFrame([
        {"sample_id": "a", "organ": "brain", "series_group_id": "g1", "split": "train"},
        {"sample_id": "b", "organ": "brain", "series_group_id": "g1", "split": "validation"},
    ])
    with unittest.TestCase().assertRaisesRegex(ValueError, "study groups cross"):
        select_manifest_rows(
            frame, role="pooled", train_split="train", validation_split="validation"
        )


def test_train_filter_applies_only_to_train_and_preserves_role_matched_validation():
    frame = pd.DataFrame([
        {"sample_id": "bt0", "organ": "brain", "series_group_id": "g1", "split": "train", "random_shard": "r0", "balanced_train": True},
        {"sample_id": "bt1", "organ": "brain", "series_group_id": "g2", "split": "train", "random_shard": "r0", "balanced_train": False},
        {"sample_id": "st0", "organ": "skin", "series_group_id": "g3", "split": "train", "random_shard": "r1", "balanced_train": True},
        {"sample_id": "bv0", "organ": "brain", "series_group_id": "g4", "split": "validation", "random_shard": "r0", "balanced_train": False},
        {"sample_id": "sv1", "organ": "skin", "series_group_id": "g5", "split": "validation", "random_shard": "r1", "balanced_train": False},
    ])
    pooled = select_manifest_rows(
        frame,
        role="pooled",
        train_split="train",
        validation_split="validation",
        train_filter_column="balanced_train",
    )
    assert pooled.train["sample_id"].tolist() == ["bt0", "st0"]
    assert pooled.validation["sample_id"].tolist() == ["bv0", "sv1"]
    organ = select_manifest_rows(
        frame,
        role="organ",
        organ="brain",
        train_split="train",
        validation_split="validation",
        train_filter_column="balanced_train",
    )
    assert organ.train["sample_id"].tolist() == ["bt0"]
    assert organ.validation["sample_id"].tolist() == ["bv0"]
    random = select_manifest_rows(
        frame,
        role="random",
        random_shard="r0",
        train_split="train",
        validation_split="validation",
        train_filter_column="balanced_train",
    )
    assert random.train["sample_id"].tolist() == ["bt0"]
    assert random.validation["sample_id"].tolist() == ["bv0"]


def test_fixed_mask_matches_evaluator_algorithm_and_training_draws_change():
    expected_seed = int.from_bytes(
        hashlib.sha256(b"organ-moe-mask-v1\x0042\x00sample-a").digest()[:8], "little"
    )
    expected = np.sort(np.random.default_rng(expected_seed).choice(10, 3, replace=False))
    np.testing.assert_array_equal(
        deterministic_mask_indices("sample-a", 10, 0.3, 42), expected
    )
    values = np.arange(20, dtype=np.float32).reshape(2, 10)
    validation = DeterministicMaskedExpressionDataset(
        values,
        ["sample-a", "sample-b"],
        normalization="log1p_tpm",
        mask_ratio=0.3,
        mask_token=-10,
        seed=42,
        phase="validation",
        fixed_masks=True,
    )
    np.testing.assert_array_equal(validation.mask_indices(0, 0), expected)
    np.testing.assert_array_equal(validation.mask_indices(0, 99), expected)
    training = DeterministicMaskedExpressionDataset(
        values,
        ["sample-a", "sample-b"],
        normalization="log1p_tpm",
        mask_ratio=0.3,
        mask_token=-10,
        seed=42,
        phase="train",
        fixed_masks=False,
    )
    assert not np.array_equal(training.mask_indices(0, 0), training.mask_indices(0, 1))


def test_natural_sampler_is_global_deterministic_and_exact_budget():
    sample_ids = [f"s{i}" for i in range(11)]
    first = DeterministicBudgetBatchSampler(
        sample_ids, batch_size=4, max_updates=5, seed=7
    )
    second = DeterministicBudgetBatchSampler(
        sample_ids, batch_size=4, max_updates=5, seed=7
    )
    different = DeterministicBudgetBatchSampler(
        sample_ids, batch_size=4, max_updates=5, seed=8
    )
    assert len(first) == 5
    assert first.flat_indices == second.flat_indices
    assert first.flat_indices != different.flat_indices
    assert set(first.flat_indices[: len(sample_ids)]) == set(range(len(sample_ids)))


def _balanced_exposures(n_brain: int) -> tuple[dict[str, int], dict[str, list[int]]]:
    records = []
    for index in range(n_brain):
        records.append({
            "sample_id": f"brain-{index}",
            "organ": "brain",
            "series_group_id": f"brain-g{index % 3}",
        })
    for index in range(10):
        records.append({
            "sample_id": f"skin-{index}",
            "organ": "skin",
            "series_group_id": f"skin-g{index % 2}",
        })
    frame = pd.DataFrame(records).sort_values("sample_id").reset_index(drop=True)
    sampler = DeterministicBudgetBatchSampler(
        frame["sample_id"].tolist(),
        batch_size=8,
        max_updates=25,
        seed=19,
        sampling_mode="organ_balanced",
        organs=frame["organ"].tolist(),
        group_ids=frame["series_group_id"].tolist(),
    )
    exposures = build_exposure_frame(frame, sampler)
    organ_totals = exposures.groupby("organ")["exposure_count"].sum().to_dict()
    group_totals = (
        exposures.groupby(["organ", "series_group_id"])["exposure_count"]
        .sum()
        .groupby(level=0)
        .apply(list)
        .to_dict()
    )
    summary = summarize_exposures(exposures)
    assert summary["total_exposures"] == 200
    return organ_totals, group_totals


def test_organ_balanced_sampler_is_immune_to_brain_imbalance_and_group_aware():
    large_brain, groups = _balanced_exposures(90)
    small_brain, _ = _balanced_exposures(20)
    assert large_brain == {"brain": 100, "skin": 100}
    assert small_brain == large_brain
    for totals in groups.values():
        assert max(totals) - min(totals) <= 1


def test_expression_loader_preserves_requested_rows_and_gene_order():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "expression.parquet"
        pq.write_table(
            pa.table({
                "sample_id": ["s2", "s1", "s3"],
                "gene_b": np.asarray([2, 1, 3], dtype=np.float32),
                "gene_a": np.asarray([20, 10, 30], dtype=np.float32),
            }),
            path,
            row_group_size=2,
        )
        values, info = load_expression_rows(path, ["s1", "s3"])
        assert info.gene_columns == ("gene_b", "gene_a")
        np.testing.assert_array_equal(values, [[1, 10], [3, 30]])
        with unittest.TestCase().assertRaisesRegex(ValueError, "missing 1 requested"):
            load_expression_rows(path, ["missing"])


def test_expression_space_requires_tpm_and_checks_gene_hash():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        expression = root / "expression.parquet"
        expression.touch()
        with unittest.TestCase().assertRaises(FileNotFoundError):
            validate_expression_metadata(expression, ["g1", "g2"])
        assumed = validate_expression_metadata(
            expression, ["g1", "g2"], assume_expression_space="tpm"
        )
        assert assumed["model_value_space"] == "log1p_tpm"
        report = root / "extraction_report.json"
        report.write_text(json.dumps({
            "expression_space": "log1p_tpm",
            "gene_order_sha256": sha256_lines(["g1", "g2"]),
        }))
        with unittest.TestCase().assertRaisesRegex(ValueError, "requires unlogged TPM"):
            validate_expression_metadata(expression, ["g1", "g2"])
        report.write_text(json.dumps({
            "output": {
                "expression_space": "tpm",
                "gene_order_sha256": "wrong",
            }
        }))
        with unittest.TestCase().assertRaisesRegex(ValueError, "gene_order_sha256"):
            validate_expression_metadata(expression, ["g1", "g2"])


def _micro_args(root: Path) -> Namespace:
    return Namespace(
        expression_parquet=str(root / "expression.parquet"),
        expression_metadata=None,
        assume_expression_space="tpm",
        manifest=str(root / "manifest.csv"),
        output_dir=str(root / "run"),
        role="pooled",
        organ=None,
        random_shard=None,
        train_split="train",
        validation_split="validation",
        sample_id_column="sample_id",
        split_column="split",
        organ_column="organ",
        group_column="series_group_id",
        random_shard_column="random_shard",
        train_filter_column=None,
        sampling_mode="natural",
        seed=13,
        validation_mask_seed=42,
        max_updates=4,
        batch_size=2,
        validation_batch_size=2,
        validation_interval=2,
        learning_rate=1e-3,
        weight_decay=0.0,
        normalization="log1p_tpm",
        mask_ratio=0.5,
        mask_token=-10.0,
        hidden_dim=8,
        ffn_dim=16,
        num_heads=2,
        num_layers=1,
        ree_base=100.0,
        feature_type="sqr",
        compute_type="iter",
        gradient_checkpointing=False,
        use_amp=False,
        deterministic=True,
        device="cpu",
        num_workers=0,
        torch_threads=1,
        log_every=0,
        export_splits=["validation", "test"],
        export_checkpoint="last",
        export_mask_seed=42,
        export_batch_size=2,
    )


def test_cpu_micro_training_retains_best_last_and_exports_frozen_predictions():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        sample_ids = [f"s{i}" for i in range(8)]
        latent = np.arange(1, 9, dtype=np.float32)
        table = {"sample_id": sample_ids}
        for gene in range(6):
            table[f"g{gene}"] = latent * (gene + 1)
        pq.write_table(pa.table(table), root / "expression.parquet", row_group_size=3)
        pd.DataFrame([
            {
                "sample_id": sample_id,
                "organ": "brain" if index % 2 == 0 else "skin",
                "series_group_id": (
                    f"train-g{index}" if index < 4 else f"held-g{index}"
                ),
                "split": "train" if index < 4 else ("validation" if index < 6 else "test"),
            }
            for index, sample_id in enumerate(sample_ids)
        ]).to_csv(root / "manifest.csv", index=False)

        result = run_training(_micro_args(root))
        run_dir = root / "run"
        assert result["run_metadata"]["completed_updates"] == 4
        assert {path.name for path in run_dir.glob("*.pt")} == {
            "best_model.pt",
            "last_model.pt",
        }
        assert (run_dir / "sampling_exposures.csv").exists()
        assert (run_dir / "training_history.json").exists()
        with np.load(run_dir / "predictions.npz") as exported:
            assert str(exported["value_space"]) == "log1p_tpm"
            assert str(exported["mask_algorithm"]) == "organ-moe-mask-v1"
            assert exported["splits"].tolist() == ["validation", "test"]
            assert exported["predictions"].shape == (4, 6)
            assert exported["mask_indices"].shape == (4, 3)
            for sample_id, actual_mask in zip(exported["sample_ids"], exported["mask_indices"]):
                np.testing.assert_array_equal(
                    actual_mask,
                    deterministic_mask_indices(str(sample_id), 6, 0.5, 42),
                )
        checkpoint = torch.load(run_dir / "last_model.pt", map_location="cpu", weights_only=False)
        assert checkpoint["update"] == 4
        assert checkpoint["config"]["input_expression_space"] == "tpm"
        assert checkpoint["config"]["model_value_space"] == "log1p_tpm"

        second_args = _micro_args(root)
        second_args.output_dir = str(root / "run2")
        second = run_training(second_args)
        assert second["history"] == result["history"]
        second_checkpoint = torch.load(
            root / "run2/last_model.pt", map_location="cpu", weights_only=False
        )
        for name, value in checkpoint["model_state_dict"].items():
            assert torch.equal(value, second_checkpoint["model_state_dict"][name])
        with np.load(run_dir / "predictions.npz") as first_export, np.load(
            root / "run2/predictions.npz"
        ) as second_export:
            np.testing.assert_array_equal(
                first_export["predictions"], second_export["predictions"]
            )


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            suite.addTest(unittest.FunctionTestCase(value))
    return suite
