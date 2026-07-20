from __future__ import annotations

import json
import sys
import tempfile
from argparse import Namespace
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))

from evaluate_latent_axis_pilot import evaluate  # noqa: E402


def _write_run(root: Path, mode: str, seed: int, label_free_mse: float = 0.70) -> Path:
    path = root / f"{mode}_seed{seed}"
    path.mkdir()
    hashes = {
        "pooled_checkpoint_sha256": "pooled",
        "expression_sha256": "expression",
        "manifest_sha256": "manifest",
        "train_sample_ids_sha256": "train",
        "validation_sample_ids_sha256": "validation",
        "gene_order_sha256": "genes",
        "resolved_config_sha256": "config",
    }
    metrics = {
        "effective_experts": 4.5,
        "minimum_route_fraction": 0.1,
    }
    (path / "run_metadata.json").write_text(json.dumps({
        "status": "complete",
        "test_accessed": False,
        "mode": mode,
        "training_seed": seed,
        "hashes": hashes,
        "validation_metrics": metrics,
    }))
    (path / "COMPLETE").touch()
    sample_ids = np.asarray([f"s{index}" for index in range(10)])
    groups = np.asarray([f"g{index}" for index in range(10)])
    organs = np.asarray(["brain"] * 5 + ["skin"] * 5)
    routes = np.asarray([0, 0, 1, 1, 2, 2, 3, 3, 4, 4])
    if seed == 42:
        routes = (routes + 1) % 5
    elif seed == 101:
        routes = (routes + 2) % 5
    candidate = np.full(10, label_free_mse)
    np.savez_compressed(
        path / "routes_validation.npz",
        sample_ids=sample_ids,
        groups=groups,
        organs=organs,
        label_evidence=np.asarray(["tissue"] * 5 + ["source"] * 5),
        single_cell_probability=np.linspace(0.01, 0.10, 10),
        routes=routes,
        probabilities=np.eye(5, dtype=np.float32)[routes],
        pooled_mse=np.full(10, 1.0),
        fixed_mse=np.full(10, 0.95 if mode == "balanced_random" else 0.90),
        router_hard_mse=candidate if mode == "label_free" else np.full(10, 0.88),
        router_soft_mse=candidate,
        oracle_mse=np.full(10, 0.6),
        true_partition_mse=np.full(10, 0.90),
    )
    np.savez_compressed(
        path / "routes_validation_mask271829.npz",
        sample_ids=sample_ids,
        groups=groups,
        organs=organs,
        label_evidence=np.asarray(["tissue"] * 5 + ["source"] * 5),
        single_cell_probability=np.linspace(0.01, 0.10, 10),
        routes=routes,
        probabilities=np.eye(5, dtype=np.float32)[routes],
    )
    return path


def _args(root: Path, label_free_mse: float = 0.70) -> Namespace:
    runs = []
    for mode in ("organ_supervised", "balanced_random", "label_free"):
        for seed in (17, 42, 101):
            runs.append(str(_write_run(root, mode, seed, label_free_mse)))
    return Namespace(
        run=runs,
        output=str(root / "report.json"),
        min_seeds=3,
        num_experts=5,
        bootstrap_reps=100,
        bootstrap_seed=7,
        minimum_relative_gain=0.03,
        maximum_seed_sd_fraction=0.5,
        minimum_ami=0.5,
        minimum_effective_expert_fraction=0.6,
        minimum_route_fraction=0.02,
        maximum_study_dominance=0.5,
    )


def test_latent_axis_screen_passes_stable_label_free_gain():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        report = evaluate(_args(root))
        assert report["status"] == "screen_pass"
        assert all(report["gates"].values())
        assert report["test_accessed"] is False
        assert report["route_stability"]["minimum_seed_ami"] == 1.0
        assert report["authorized_next_step"].startswith("freeze the learned axis")


def test_latent_axis_screen_blocks_test_when_candidate_loses():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        report = evaluate(_args(root, label_free_mse=0.98))
        assert report["status"] == "screen_fail"
        assert not report["gates"]["label_free_vs_organ_true_partition"]
        assert "do not access test" in report["authorized_next_step"]
