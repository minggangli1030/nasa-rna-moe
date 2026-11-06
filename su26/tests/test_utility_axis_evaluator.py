from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from argparse import Namespace
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))

from evaluate_utility_axis_pilot import (  # noqa: E402
    CANDIDATES,
    CONTROLS,
    EXPECTED_AXES,
    EXPECTED_SEEDS,
    evaluate,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _labels(axis: str, n_samples: int) -> np.ndarray:
    k = int(axis.rsplit("_k", 1)[1])
    return np.arange(n_samples, dtype=np.int64) % k


def _partition_summary(labels: np.ndarray, groups: np.ndarray, k: int) -> dict:
    counts = np.bincount(labels, minlength=k)
    fractions = counts / counts.sum()
    studies = []
    dominance = []
    for label in range(k):
        selected = groups[labels == label]
        unique, group_counts = np.unique(selected, return_counts=True)
        studies.append(int(len(unique)))
        dominance.append(float(group_counts.max() / group_counts.sum()))
    return {
        "counts": counts.tolist(),
        "fractions": fractions.tolist(),
        "minimum_fraction": float(fractions.min()),
        "effective_k": float(1.0 / np.square(fractions).sum()),
        "connected_studies_per_partition": studies,
        "maximum_single_study_fraction": float(max(dominance)),
    }


def _fixture(root: Path) -> tuple[list[str], Path]:
    n_samples = 30
    sample_ids = np.asarray([f"sample-{index}" for index in range(n_samples)])
    groups = np.asarray([f"study-{index}" for index in range(n_samples)])
    organs = np.asarray([f"organ-{index % 5}" for index in range(n_samples)])
    weights = np.full(n_samples, 1.0 / n_samples, dtype=np.float64)

    partitions = {}
    for axis in CANDIDATES:
        labels = _labels(axis, n_samples)
        k = int(axis.rsplit("_k", 1)[1])
        partitions[axis] = {
            "k": k,
            "clustering_stability": {
                "minimum_pairwise_ami": 0.9,
                "mean_pairwise_ami": 0.95,
            },
            "calibration": _partition_summary(labels, groups, k),
        }
    report = {
        "status": "complete",
        "test_accessed": False,
        "primary_candidate": "head_gradient_k2",
        "candidate_family": list(CANDIDATES),
        "controls": list(CONTROLS),
        "partitions": partitions,
    }
    report_path = root / "partition_report.json"
    report_path.write_text(json.dumps(report))
    report_hash = _sha256(report_path)

    common_hashes = {
        "protocol_sha256": "protocol",
        "pooled_checkpoint_sha256": "pooled",
        "expression_sha256": "expression",
        "manifest_sha256": "manifest",
        "partition_manifest_sha256": "partitions",
        "partition_report_sha256": report_hash,
        "axis_definitions_sha256": "definitions",
        "train_sample_ids_sha256": "train-ids",
        "calibration_sample_ids_sha256": "calibration-ids",
        "gene_order_sha256": "genes",
        "score_gene_indices_sha256": "score-genes",
    }
    paths = []
    for axis in EXPECTED_AXES:
        k = int(axis.rsplit("_k", 1)[1])
        labels = _labels(axis, n_samples)
        if axis == "head_gradient_k2":
            true_mse = 0.85
        elif axis in CANDIDATES:
            true_mse = 0.90
        elif axis.startswith("random_"):
            true_mse = 0.96
        else:
            true_mse = 0.92
        for seed in EXPECTED_SEEDS:
            path = root / f"{axis}_seed{seed}"
            path.mkdir()
            scores = path / "calibration_scores.npz"
            np.savez_compressed(
                scores,
                sample_ids=sample_ids,
                groups=groups,
                organs=organs,
                sample_weights=weights,
                pooled_mse=np.full(n_samples, 1.0),
                true_partition_mse=np.full(n_samples, true_mse),
                oracle_mse=np.full(n_samples, 0.80),
                crossfit_fixed_mse=np.full(n_samples, 0.95),
                true_labels=labels,
            )
            metadata = {
                "status": "complete",
                "axis": axis,
                "training_seed": seed,
                "test_accessed": False,
                "mechanical_only": False,
                "config": {
                    "num_experts": k,
                    "final_update": {2: 600, 3: 900, 5: 1500}[k],
                    "router_trainable": False,
                    "checkpoint_policy": "predetermined_final_update",
                    "exposures_per_expert_target": 2400,
                    "realized_exposure_counts": [2400] * k,
                },
                "hashes": common_hashes,
                "artifacts": {"calibration_scores_sha256": _sha256(scores)},
            }
            (path / "run_metadata.json").write_text(json.dumps(metadata))
            (path / "COMPLETE").touch()
            paths.append(str(path))
    return paths, report_path


def _args(root: Path, paths: list[str], report_path: Path) -> Namespace:
    return Namespace(
        run=paths,
        partition_report=str(report_path),
        output=str(root / "decision.json"),
        bootstrap_reps=50,
        bootstrap_seed=7,
        minimum_relative_gain=0.03,
        maximum_seed_sd_fraction=0.5,
        minimum_ami=0.5,
        minimum_partition_fraction=0.10,
        minimum_effective_expert_fraction=0.8,
        minimum_studies_per_partition=5,
        maximum_study_dominance=0.5,
    )


def test_primary_replacement_pass_never_authorizes_test_directly():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        paths, report = _fixture(root)
        result = evaluate(_args(root, paths, report))

        assert result["status"] == "screen_pass_primary"
        assert result["decision_branch"] == "replacement_candidate"
        assert result["test_accessed"] is False
        assert result["test_access_authorized"] is False
        assert "do not access test yet" in result["authorized_next_step"]
        primary = result["candidates"]["head_gradient_k2"]
        assert primary["core_pass"] is True
        assert primary["organ_replacement_pass"] is True
        assert all(primary["comparison_gates"].values())
        assert all(primary["partition_gates"].values())


def test_evaluator_requires_every_frozen_axis_seed_bank():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        paths, report = _fixture(root)
        try:
            evaluate(_args(root, paths[:-1], report))
        except ValueError as error:
            assert "exact seeds" in str(error)
        else:
            raise AssertionError("expected missing-bank rejection")
