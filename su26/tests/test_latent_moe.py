from __future__ import annotations

import json
import sys
import tempfile
from argparse import Namespace
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

from train_latent_moe import (  # noqa: E402
    FrozenTrunkResidualMoE,
    encode_partition_labels,
    run_training,
    simplex_least_squares_weights,
)
from train_manifest import sha256_lines  # noqa: E402
from train_single import ExpressionPerformer  # noqa: E402


def _fixture(root: Path) -> tuple[Path, Path, Path, Path]:
    genes = [f"g{index}" for index in range(8)]
    sample_ids = [f"s{index:02d}" for index in range(12)]
    rng = np.random.default_rng(4)
    table = {"sample_id": sample_ids}
    for index, gene in enumerate(genes):
        table[gene] = np.abs(rng.normal(index + 1, 0.2, len(sample_ids))).astype(np.float32)
    expression = root / "expression.parquet"
    pq.write_table(pa.table(table), expression, row_group_size=4)
    metadata = root / "extraction_report.json"
    metadata.write_text(json.dumps({
        "status": "complete",
        "expression_space": "tpm",
        "gene_order_sha256": sha256_lines(genes),
    }))
    rows = []
    for index, sample_id in enumerate(sample_ids):
        rows.append({
            "sample_id": sample_id,
            "organ": "brain" if index % 2 == 0 else "skin",
            "random_shard": "random_0" if index % 2 == 0 else "random_1",
            "series_group_id": f"group_{index}",
            "label_evidence": "characteristics_tissue",
            "single_cell_probability": 0.01 * index,
            "split": "train" if index < 8 else "calibration",
            "balanced_train": index < 8,
        })
    manifest = root / "manifest.csv"
    pd.DataFrame(rows).to_csv(manifest, index=False)
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
            "mask_ratio": 0.25,
            "mask_token": -10.0,
            "normalization": "log1p_tpm",
            "gene_list": genes,
        },
        "model_state_dict": trunk.state_dict(),
    }, checkpoint)
    return expression, metadata, manifest, checkpoint


def _args(root: Path, mode: str) -> Namespace:
    expression, metadata, manifest, checkpoint = _fixture(root)
    return Namespace(
        expression_parquet=str(expression),
        expression_metadata=str(metadata),
        manifest=str(manifest),
        pooled_checkpoint=str(checkpoint),
        output_dir=str(root / f"run_{mode}"),
        mode=mode,
        seed=17,
        train_split="train",
        validation_split="calibration",
        train_filter_column="balanced_train",
        sample_id_column="sample_id",
        organ_column="organ",
        group_column="series_group_id",
        random_shard_column="random_shard",
        num_experts=2,
        adapter_dim=4,
        router_hidden_dim=4,
        max_updates=2,
        validation_interval=1,
        batch_size=2,
        validation_batch_size=2,
        mask_ratio=0.25,
        mask_token=-10.0,
        mask_seed=271828,
        repeated_mask_seeds=[271828, 271829],
        learning_rate=1e-3,
        weight_decay=0.0,
        temperature=0.7,
        load_balance_weight=0.05,
        entropy_weight=0.001,
        router_supervision_weight=0.1,
        device="cpu",
        num_workers=0,
        use_amp=False,
    )


def test_frozen_trunk_moe_shapes_and_only_adapter_router_are_trainable():
    trunk = ExpressionPerformer(
        num_genes=6,
        hidden_dim=8,
        n_heads=2,
        n_layers=1,
        ffn_dim=16,
        gradient_checkpointing=False,
    )
    trunk.requires_grad_(False)
    model = FrozenTrunkResidualMoE(
        trunk,
        num_experts=3,
        adapter_dim=4,
        router_hidden_dim=5,
        mask_token=-10.0,
    )
    predictions, logits, base = model(torch.randn(2, 6))
    assert predictions.shape == (2, 3, 6)
    assert logits.shape == (2, 3)
    assert base.shape == (2, 6)
    assert all(not parameter.requires_grad for parameter in model.trunk.parameters())
    assert model.trainable_state_dict()
    assert not any(name.startswith("trunk.") for name in model.trainable_state_dict())


def test_partition_labels_are_sorted_and_label_free_uses_no_targets():
    frame = pd.DataFrame({
        "organ": ["skin", "brain", "skin"],
        "random_shard": ["random_1", "random_0", "random_1"],
    })
    labels, names = encode_partition_labels(
        frame,
        mode="organ_supervised",
        organ_column="organ",
        random_shard_column="random_shard",
    )
    assert names == ["brain", "skin"]
    assert labels.tolist() == [1, 0, 1]
    labels, _ = encode_partition_labels(
        frame,
        mode="label_free",
        organ_column="organ",
        random_shard_column="random_shard",
    )
    assert labels is None


def test_simplex_fixed_blend_recovers_dominant_expert():
    target = np.asarray([[1.0, 2.0], [2.0, 3.0]])
    experts = np.stack([target, target + 3.0], axis=1)
    weights = simplex_least_squares_weights(experts, target)
    np.testing.assert_allclose(weights, [1.0, 0.0], atol=1e-6)


def test_simplex_fixed_blend_handles_collinear_experts_deterministically():
    target = np.asarray([[1.0, 2.0], [2.0, 3.0]])
    experts = np.stack([target + 1.0, target + 1.0, target - 1.0], axis=1)
    first = simplex_least_squares_weights(experts, target)
    second = simplex_least_squares_weights(experts, target)
    np.testing.assert_allclose(first, second)
    np.testing.assert_allclose(first.sum(), 1.0)
    assert np.all(first >= 0.0)
    blended = np.einsum("k,nkm->nm", first, experts)
    np.testing.assert_allclose(blended, target, atol=1e-8)


def test_simplex_fixed_blend_respects_sample_weights():
    target = np.asarray([[0.0], [10.0]])
    experts = np.asarray([[[0.0], [10.0]], [[0.0], [10.0]]])
    first_heavy = simplex_least_squares_weights(
        experts, target, sample_weights=np.asarray([0.9, 0.1])
    )
    second_heavy = simplex_least_squares_weights(
        experts, target, sample_weights=np.asarray([0.1, 0.9])
    )
    assert first_heavy[0] > first_heavy[1]
    assert second_heavy[1] > second_heavy[0]


def test_micro_runs_complete_for_supervised_and_label_free_modes():
    for mode in ("organ_supervised", "balanced_random", "label_free"):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = run_training(_args(root, mode))
            output = root / f"run_{mode}"
            assert result["status"] == "complete"
            assert result["test_accessed"] is False
            assert (output / "COMPLETE").exists()
            with np.load(output / "routes_validation.npz") as routes:
                assert routes["routes"].shape == (4,)
                assert routes["probabilities"].shape == (4, 2)
            checkpoint = torch.load(
                output / "best_adapter_router.pt", map_location="cpu", weights_only=False
            )
            assert not any(
                name.startswith("trunk.")
                for name in checkpoint["adapter_router_state_dict"]
            )
