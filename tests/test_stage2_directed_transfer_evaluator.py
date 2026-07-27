from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from core.train_manifest import sha256_file
from evaluation.evaluate_stage2_directed_transfer import (
    ORGANS,
    RANDOM_AXES,
    SEEDS,
    _pair_arm,
    evaluate,
)


def _write_arm(
    root: Path,
    arm_id: str,
    recipients: list[str],
    adapter_by_organ: dict[str, float],
) -> None:
    arm = root / "arms" / arm_id
    arm.mkdir(parents=True)
    np.savez_compressed(
        arm / "calibration_scores.npz",
        sample_ids=np.asarray([f"sample-{organ}" for organ in recipients]),
        donor_ids=np.asarray([f"donor-{organ}" for organ in recipients]),
        groups=np.asarray([f"donor-{organ}" for organ in recipients]),
        organs=np.asarray(recipients),
        pooled_mse=np.ones(len(recipients), dtype=np.float64),
        adapter_mse=np.asarray(
            [adapter_by_organ[organ] for organ in recipients], dtype=np.float64
        ),
    )
    (arm / "run_metadata.json").write_text(
        json.dumps(
            {
                "status": "complete",
                "mechanical_only": False,
                "evaluation_recipients": recipients,
                "hashes": {
                    "score_cache_sha256": sha256_file(
                        arm / "calibration_scores.npz"
                    )
                },
            }
        )
    )


def _synthetic_roots(tmp_path: Path):
    definitions = []
    for recipient in ORGANS:
        definitions.append(
            {
                "arm_id": f"sub__{recipient}__recipient_only",
                "evaluation_recipients": [recipient],
            }
        )
    for left_index, left in enumerate(ORGANS):
        for right in ORGANS[left_index + 1 :]:
            definitions.append(
                {
                    "arm_id": f"sub__{left}__{right}",
                    "evaluation_recipients": [left, right],
                }
            )
    for recipient in ORGANS:
        for axis in RANDOM_AXES:
            definitions.append(
                {
                    "arm_id": f"sub__{recipient}__random__{axis}",
                    "evaluation_recipients": [recipient],
                }
            )
    assert len(definitions) == 60
    definitions_path = tmp_path / "definitions.json"
    definitions_path.write_text(json.dumps({"arms": definitions}))
    definitions_hash = sha256_file(definitions_path)
    schedule_hash = "a" * 64

    seed_roots = {}
    arm_ids = [value["arm_id"] for value in definitions]
    for seed in SEEDS:
        root = tmp_path / f"seed{seed}"
        (root / "arms").mkdir(parents=True)
        for recipient in ORGANS:
            _write_arm(
                root,
                f"sub__{recipient}__recipient_only",
                [recipient],
                {recipient: 1.0},
            )
        for left_index, left in enumerate(ORGANS):
            for right in ORGANS[left_index + 1 :]:
                _write_arm(
                    root,
                    f"sub__{left}__{right}",
                    [left, right],
                    {left: 0.9, right: 0.9},
                )
        for recipient in ORGANS:
            for axis in RANDOM_AXES:
                _write_arm(
                    root,
                    f"sub__{recipient}__random__{axis}",
                    [recipient],
                    {recipient: 0.99},
                )
        (root / "run_metadata.json").write_text(
            json.dumps(
                {
                    "status": "complete",
                    "mechanical_only": False,
                    "training_seed": seed,
                    "best_seed_selection_allowed": False,
                    "completed_arms": 60,
                    "arms": [{"arm_id": arm_id} for arm_id in arm_ids],
                    "hashes": {
                        "training_schedules_sha256": schedule_hash,
                        "arm_definitions_sha256": definitions_hash,
                    },
                }
            )
        )
        seed_roots[seed] = root
    return definitions_path, definitions_hash, schedule_hash, seed_roots


def test_evaluator_builds_directed_heatmap_matrices_and_stability(tmp_path: Path) -> None:
    definitions, definitions_hash, schedule_hash, roots = _synthetic_roots(tmp_path)
    output = tmp_path / "output"
    report = evaluate(
        argparse.Namespace(
            seed_root=[f"{seed}={root}" for seed, root in roots.items()],
            arm_definitions=str(definitions),
            expected_schedule_sha256=schedule_hash,
            expected_definitions_sha256=definitions_hash,
            output_dir=str(output),
            bootstrap_draws=25,
            bootstrap_seed=7,
            no_plot=True,
        )
    )
    assert report["status"] == "complete"
    assert report["summary"]["directed_edges"] == 56
    assert report["summary"]["all_seed_same_sign_edges"] == 56
    assert report["summary"]["positive_all_seed_and_ci_edges"] == 56
    effect = pd.read_csv(
        output / "directed_transfer_effect_percent.csv", index_col=0
    )
    positive = pd.read_csv(output / "seed_positive_count.csv", index_col=0)
    assert np.isclose(effect.loc["brain", "liver"], 10.0)
    assert positive.loc["brain", "liver"] == 3
    assert effect.loc["brain", "brain"] == 0


def test_pair_arm_is_order_invariant() -> None:
    assert _pair_arm("brain", "liver") == "sub__brain__liver"
    assert _pair_arm("liver", "brain") == "sub__brain__liver"
