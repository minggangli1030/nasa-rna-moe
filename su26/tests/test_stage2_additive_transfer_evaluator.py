from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from core.train_manifest import sha256_file
from evaluation.evaluate_stage2_additive_transfer import evaluate
from evaluation.evaluate_stage2_directed_transfer import ORGANS, RANDOM_AXES, SEEDS


def _write_arm(root: Path, arm_id: str, organ: str, adapter_mse: float) -> None:
    arm = root / "arms" / arm_id
    arm.mkdir(parents=True)
    scores = arm / "calibration_scores.npz"
    np.savez_compressed(
        scores,
        sample_ids=pd.Series([f"sample-{organ}"]).astype(str).to_numpy(),
        donor_ids=pd.Series([f"donor-{organ}"]).astype(str).to_numpy(),
        groups=pd.Series([f"group-{organ}"]).astype(str).to_numpy(),
        organs=pd.Series([organ]).astype(str).to_numpy(),
        pooled_mse=np.asarray([1.1], dtype=np.float64),
        adapter_mse=np.asarray([adapter_mse], dtype=np.float64),
    )
    (arm / "run_metadata.json").write_text(
        json.dumps(
            {
                "status": "complete",
                "mechanical_only": False,
                "evaluation_recipients": [organ],
                "hashes": {"score_cache_sha256": sha256_file(scores)},
            }
        )
    )


def _fixture(tmp_path: Path):
    substitution_schedule_hash = "a" * 64
    additive_schedule_hash = "b" * 64
    edges = [
        {
            "recipient": recipient,
            "donor": ORGANS[(index + 1) % len(ORGANS)],
            "stratum": ("high", "middle", "low")[index % 3],
            "frozen_expert_utility_cosine_similarity": 0.8 - index / 20,
        }
        for index, recipient in enumerate(ORGANS)
    ]
    freeze = tmp_path / "freeze.json"
    freeze.write_text(
        json.dumps(
            {
                "status": "frozen_before_directed_transfer_outcomes",
                "transfer_training_started_before_freeze": False,
                "transfer_score_cache_accessed_before_freeze": False,
                "best_seed_selection_allowed": False,
                "edges": edges,
            }
        )
    )

    additive_arm_ids = []
    for recipient in ORGANS:
        additive_arm_ids.append(f"add__{recipient}__self_control")
        additive_arm_ids.extend(
            f"add__{recipient}__random__{axis}" for axis in RANDOM_AXES
        )
    additive_arm_ids.extend(
        f"add__{edge['recipient']}__{edge['donor']}" for edge in edges
    )
    assert len(additive_arm_ids) == 40
    definitions = tmp_path / "definitions.json"
    definitions.write_text(
        json.dumps({"schema_version": 1, "arms": [
            {"arm_id": arm_id} for arm_id in additive_arm_ids
        ]})
    )
    definitions_hash = sha256_file(definitions)

    substitution_roots = {}
    additive_roots = {}
    for seed in SEEDS:
        substitution = tmp_path / f"sub-seed{seed}"
        additive = tmp_path / f"add-seed{seed}"
        (substitution / "arms").mkdir(parents=True)
        (additive / "arms").mkdir(parents=True)
        for edge in edges:
            recipient = edge["recipient"]
            donor = edge["donor"]
            _write_arm(
                substitution,
                f"sub__{recipient}__recipient_only",
                recipient,
                1.0,
            )
            _write_arm(
                additive,
                f"add__{recipient}__{donor}",
                recipient,
                0.9,
            )
            _write_arm(
                additive,
                f"add__{recipient}__self_control",
                recipient,
                0.95,
            )
            for axis in RANDOM_AXES:
                _write_arm(
                    additive,
                    f"add__{recipient}__random__{axis}",
                    recipient,
                    0.98,
                )
        substitution_arm_ids = [
            f"sub__{recipient}__recipient_only" for recipient in ORGANS
        ] + [f"unused-{index}" for index in range(52)]
        (substitution / "run_metadata.json").write_text(
            json.dumps(
                {
                    "status": "complete",
                    "mechanical_only": False,
                    "training_seed": seed,
                    "best_seed_selection_allowed": False,
                    "completed_arms": 60,
                    "arms": [
                        {"arm_id": arm_id} for arm_id in substitution_arm_ids
                    ],
                    "hashes": {
                        "training_schedules_sha256": substitution_schedule_hash
                    },
                }
            )
        )
        (additive / "run_metadata.json").write_text(
            json.dumps(
                {
                    "status": "complete",
                    "mechanical_only": False,
                    "training_seed": seed,
                    "best_seed_selection_allowed": False,
                    "completed_arms": 40,
                    "arms": [
                        {"arm_id": arm_id} for arm_id in additive_arm_ids
                    ],
                    "hashes": {
                        "training_schedules_sha256": additive_schedule_hash,
                        "arm_definitions_sha256": definitions_hash,
                    },
                }
            )
        )
        substitution_roots[seed] = substitution
        additive_roots[seed] = additive
    return {
        "substitution_roots": substitution_roots,
        "additive_roots": additive_roots,
        "substitution_schedule_hash": substitution_schedule_hash,
        "additive_schedule_hash": additive_schedule_hash,
        "definitions": definitions,
        "definitions_hash": definitions_hash,
        "freeze": freeze,
        "freeze_hash": sha256_file(freeze),
    }


def test_additive_evaluator_compares_frozen_edges_and_controls(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    output = tmp_path / "output"
    report = evaluate(
        argparse.Namespace(
            substitution_seed_root=[
                f"{seed}={root}"
                for seed, root in fixture["substitution_roots"].items()
            ],
            additive_seed_root=[
                f"{seed}={root}"
                for seed, root in fixture["additive_roots"].items()
            ],
            additive_arm_definitions=str(fixture["definitions"]),
            edge_freeze=str(fixture["freeze"]),
            expected_substitution_schedule_sha256=fixture[
                "substitution_schedule_hash"
            ],
            expected_additive_schedule_sha256=fixture["additive_schedule_hash"],
            expected_additive_definitions_sha256=fixture["definitions_hash"],
            expected_edge_freeze_sha256=fixture["freeze_hash"],
            output_dir=str(output),
            bootstrap_draws=25,
            bootstrap_seed=9,
            no_plot=True,
        )
    )
    assert report["status"] == "complete"
    assert report["summary"] == {
        "frozen_edges": 8,
        "positive_all_seed_and_ci_edges": 8,
        "negative_all_seed_and_ci_edges": 0,
        "beats_a2250_all_seed_edges": 8,
        "beats_all_random_all_seed_edges": 8,
    }
    edges = pd.read_csv(output / "additive_edges.csv")
    assert np.allclose(edges["mean_effect_vs_a1500_percent"], 10.0)
    assert edges["positive_seed_count"].eq(3).all()
