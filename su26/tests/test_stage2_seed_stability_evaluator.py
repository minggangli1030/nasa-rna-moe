from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from core.train_manifest import sha256_file
from evaluation.evaluate_stage2_directed_transfer import ORGANS
from evaluation.evaluate_stage2_seed_stability import evaluate


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
        pooled_mse=np.asarray([1.2], dtype=np.float64),
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


def test_crossed_stability_evaluator_classifies_reproducible_edges(
    tmp_path: Path,
) -> None:
    trunks = [17, 42, 101]
    opts = [211, 223, 227]
    edges = [
        {
            "recipient": recipient,
            "donor": ORGANS[(index + 1) % len(ORGANS)],
        }
        for index, recipient in enumerate(ORGANS)
    ]
    protocol = tmp_path / "protocol.json"
    protocol.write_text(
        json.dumps(
            {
                "status": "frozen_before_stability_outcomes",
                "diagnostic_training_started_before_freeze": False,
                "diagnostic_outcomes_accessed_before_freeze": False,
                "best_seed_selection_allowed": False,
                "factor_design": {
                    "trunk_seeds": trunks,
                    "optimization_seeds": opts,
                },
                "edges": edges,
                "decision_gates": {
                    "minimum_absolute_effect_percent": 0.5,
                    "required_positive_combos": 8,
                    "reproducible_map_required_stable_edges": 6,
                    "raw_addition_required_helpful_edges": 3,
                },
                "bootstrap": {"draws": 20, "seed": 7},
            }
        )
    )
    arm_ids = []
    for edge in edges:
        recipient = edge["recipient"]
        arm_ids.extend(
            [
                f"diag__{recipient}__recipient_only",
                f"diag__{recipient}__self_control",
                f"diag__{recipient}__{edge['donor']}",
            ]
        )
    definitions = tmp_path / "definitions.json"
    definitions.write_text(
        json.dumps({"arms": [{"arm_id": arm_id} for arm_id in arm_ids]})
    )
    schedule_hash = "a" * 64
    definitions_hash = sha256_file(definitions)
    combo_roots = []
    for trunk in trunks:
        for opt in opts:
            root = tmp_path / f"trunk{trunk}-opt{opt}"
            (root / "arms").mkdir(parents=True)
            for edge_index, edge in enumerate(edges):
                recipient = edge["recipient"]
                _write_arm(
                    root, f"diag__{recipient}__recipient_only", recipient, 1.0
                )
                _write_arm(
                    root, f"diag__{recipient}__self_control", recipient, 0.95
                )
                _write_arm(
                    root,
                    f"diag__{recipient}__{edge['donor']}",
                    recipient,
                    0.9 if edge_index < 4 else 1.1,
                )
            (root / "run_metadata.json").write_text(
                json.dumps(
                    {
                        "status": "complete",
                        "mechanical_only": False,
                        "best_seed_selection_allowed": False,
                        "training_seed": trunk,
                        "trunk_seed": trunk,
                        "optimization_seed": opt,
                        "mask_seed": opt,
                        "loader_seed": opt,
                        "completed_arms": 24,
                        "arms": [{"arm_id": arm_id} for arm_id in arm_ids],
                        "config": {"use_amp": False},
                        "hashes": {
                            "training_schedules_sha256": schedule_hash,
                            "arm_definitions_sha256": definitions_hash,
                        },
                    }
                )
            )
            combo_roots.append(f"{trunk}:{opt}={root}")

    output = tmp_path / "output"
    report = evaluate(
        argparse.Namespace(
            combo_root=combo_roots,
            protocol=str(protocol),
            expected_protocol_sha256=sha256_file(protocol),
            arm_definitions=str(definitions),
            expected_schedule_sha256=schedule_hash,
            expected_definitions_sha256=definitions_hash,
            output_dir=str(output),
        )
    )
    assert report["summary"] == {
        "edges": 8,
        "stable_helpful_edges": 4,
        "stable_harmful_edges": 4,
        "unstable_or_negligible_edges": 0,
        "decision": "raw_addition_has_actionable_reproducible_helpful_structure",
    }
    frame = pd.read_csv(output / "stability_edges.csv")
    assert frame["positive_combo_count"].tolist() == [9] * 4 + [0] * 4
