from __future__ import annotations

import json
import sys
from argparse import Namespace
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))
sys.path.insert(0, str(ROOT / "evaluation"))

from build_utility_axis_partitions import build  # noqa: E402
from train_fixed_partition_banks import run_packed_training  # noqa: E402
from train_manifest import sha256_lines, stable_seed  # noqa: E402
from train_single import ExpressionPerformer  # noqa: E402


def _fixture(root: Path):
    genes = [f"g{index}" for index in range(20)]
    sample_ids = [f"s{index:02d}" for index in range(30)]
    rng = np.random.default_rng(112)
    table = {"sample_id": sample_ids}
    for index, gene in enumerate(genes):
        table[gene] = np.abs(
            rng.normal(1.0 + index / 10.0, 0.25, len(sample_ids))
        ).astype(np.float32)
    expression = root / "expression.parquet"
    pq.write_table(pa.table(table), expression, row_group_size=5)
    expression_metadata = root / "extraction_report.json"
    expression_metadata.write_text(json.dumps({
        "status": "complete",
        "expression_space": "tpm",
        "gene_order_sha256": sha256_lines(genes),
    }))
    organs = ["adipose", "brain", "liver", "skeletal_muscle", "skin"]
    rows = []
    for index, sample_id in enumerate(sample_ids):
        rows.append({
            "sample_id": sample_id,
            "organ": organs[index % len(organs)],
            "series_group_id": f"study_{index:02d}",
            "split": "train" if index < 20 else "calibration",
            "balanced_train": index < 20,
        })
    manifest = root / "manifest.parquet"
    pd.DataFrame(rows).to_parquet(manifest, index=False)
    trunk = ExpressionPerformer(
        num_genes=len(genes),
        hidden_dim=8,
        n_heads=2,
        n_layers=1,
        ffn_dim=16,
        gradient_checkpointing=False,
    )
    checkpoint = root / "pooled.pt"
    torch.save({
        "schema_version": 1,
        "update": 3,
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
    }, checkpoint)
    protocol = root / "protocol.json"
    protocol.write_text(json.dumps({"test_access_before_pass": False}))
    return expression, expression_metadata, manifest, checkpoint, protocol


def test_real_pipeline_shape_builds_axes_and_packed_hard_banks(tmp_path):
    expression, expression_metadata, manifest, checkpoint, protocol = _fixture(tmp_path)
    axis_root = tmp_path / "axis"
    report = build(Namespace(
        expression_parquet=str(expression),
        expression_metadata=str(expression_metadata),
        manifest=str(manifest),
        pooled_checkpoint=str(checkpoint),
        protocol=str(protocol),
        output_dir=str(axis_root),
        axis_seed=314159,
        primary_candidate="head_gradient_k2",
        k_values=[2, 3],
        probe_fraction=0.10,
        score_fraction=0.30,
        pca_components=4,
        cluster_restarts=2,
        batch_size=5,
        mask_token=-10.0,
        train_split="train",
        validation_split="calibration",
        train_filter_column="balanced_train",
        sample_id_column="sample_id",
        organ_column="organ",
        group_column="series_group_id",
        device="cpu",
    ))
    assert report["status"] == "complete"
    assert report["test_accessed"] is False
    assert (axis_root / "COMPLETE").exists()

    packed_root = tmp_path / "packed"
    result = run_packed_training(Namespace(
        expression_parquet=str(expression),
        expression_metadata=str(expression_metadata),
        manifest=str(manifest),
        pooled_checkpoint=str(checkpoint),
        protocol=str(protocol),
        partition_manifest=str(axis_root / "partition_manifest.parquet"),
        partition_report=str(axis_root / "partition_report.json"),
        axis_definitions=str(axis_root / "axis_definitions.npz"),
        axis=["head_gradient_k2", "random_k2", "organ_k5"],
        output_dir=str(packed_root),
        seed=17,
        train_split="train",
        validation_split="calibration",
        train_filter_column="balanced_train",
        sample_id_column="sample_id",
        organ_column="organ",
        group_column="series_group_id",
        adapter_dim=4,
        exposures_per_expert=10,
        max_updates=1,
        batch_size=2,
        validation_batch_size=5,
        mask_ratio=0.30,
        mask_token=-10.0,
        learning_rate=1e-3,
        weight_decay=0.0,
        crossfit_folds=2,
        crossfit_seed=8675309,
        log_interval=1,
        device="cpu",
        num_workers=0,
        use_amp=False,
        smoke_only=True,
    ))
    assert result["status"] == "complete"
    assert result["test_accessed"] is False
    assert set(result["banks"]) == {"head_gradient_k2", "random_k2", "organ_k5"}
    for axis in result["banks"]:
        bank = packed_root / "banks" / axis
        assert (bank / "COMPLETE").exists()
        metadata = json.loads((bank / "run_metadata.json").read_text())
        assert metadata["test_accessed"] is False
        checkpoint_value = torch.load(
            bank / "final_experts.pt", map_location="cpu", weights_only=False
        )
        assert checkpoint_value["expert_state_dict"]
        assert all(
            name.startswith("experts.")
            for name in checkpoint_value["expert_state_dict"]
        )


def test_packed_final_refit_merges_train_cal_and_emits_no_efficacy_scores(tmp_path):
    expression, expression_metadata, manifest, checkpoint, protocol = _fixture(tmp_path)
    axis_root = tmp_path / "axis"
    build(Namespace(
        expression_parquet=str(expression),
        expression_metadata=str(expression_metadata),
        manifest=str(manifest),
        pooled_checkpoint=str(checkpoint),
        protocol=str(protocol),
        output_dir=str(axis_root),
        axis_seed=314159,
        primary_candidate="head_gradient_k2",
        k_values=[2, 3],
        probe_fraction=0.10,
        score_fraction=0.30,
        pca_components=4,
        cluster_restarts=2,
        batch_size=5,
        mask_token=-10.0,
        train_split="train",
        validation_split="calibration",
        train_filter_column="balanced_train",
        sample_id_column="sample_id",
        organ_column="organ",
        group_column="series_group_id",
        device="cpu",
    ))

    packed_root = tmp_path / "final_refit"
    result = run_packed_training(Namespace(
        expression_parquet=str(expression),
        expression_metadata=str(expression_metadata),
        manifest=str(manifest),
        pooled_checkpoint=str(checkpoint),
        protocol=str(protocol),
        partition_manifest=str(axis_root / "partition_manifest.parquet"),
        partition_report=str(axis_root / "partition_report.json"),
        axis_definitions=str(axis_root / "axis_definitions.npz"),
        axis=["organ_k5"],
        axis_expert_key=[
            "organ_k5=organ:adipose,organ:brain,organ:liver,"
            "organ:skeletal_muscle,organ:skin"
        ],
        output_dir=str(packed_root),
        seed=17,
        code_commit="abcdef1234567890abcdef1234567890abcdef12",
        train_split="train",
        validation_split="calibration",
        train_filter_column="balanced_train",
        sample_id_column="sample_id",
        organ_column="organ",
        group_column="series_group_id",
        adapter_dim=4,
        exposures_per_expert=6,
        max_updates=None,
        batch_size=2,
        validation_batch_size=5,
        mask_ratio=0.30,
        mask_token=-10.0,
        learning_rate=1e-3,
        weight_decay=0.0,
        crossfit_folds=2,
        crossfit_seed=8675309,
        log_interval=15,
        device="cpu",
        num_workers=0,
        use_amp=False,
        smoke_only=False,
        final_refit=True,
        sampling_mode="organ_sample_balanced",
    ))

    assert result["status"] == "complete"
    assert result["code_commit"] == "abcdef1234567890abcdef1234567890abcdef12"
    assert result["counts"]["fit"] == 30
    assert result["fitting_roles"] == ["train", "calibration"]
    assert result["internal_efficacy_scoring"] is False
    assert result["fit_exposure_summary"]["zero_exposure_samples"] == 0
    assert result["config"]["ordered_schedule_rows"] == 30
    assert (packed_root / "fit_schedule.parquet").is_file()
    schedule = pd.read_parquet(packed_root / "fit_schedule.parquet")
    assert schedule["draw_number"].tolist() == list(range(30))
    assert schedule["update"].tolist() == [value // 2 + 1 for value in range(30)]
    assert schedule["mask_seed_u64_hex"].tolist() == [
        f"{stable_seed(17, 'mask', 'packed_final_refit_banks', row.sample_id, row.draw_number):016x}"
        for row in schedule.itertuples(index=False)
    ]
    assert result["exposure_counts"]["organ_k5"] == [6, 6, 6, 6, 6]
    bank = packed_root / "banks" / "organ_k5"
    assert not (bank / "calibration_scores.npz").exists()
    metadata = json.loads((bank / "run_metadata.json").read_text())
    assert metadata["internal_efficacy_scoring"] is False
    assert metadata["config"]["calibration_evaluation_performed"] is False
    assert "calibration_metrics" not in metadata
    assert metadata["artifacts"]["all_final_tensors_finite"] is True
    assert metadata["artifacts"]["checkpoint_roundtrip_verified"] is True
