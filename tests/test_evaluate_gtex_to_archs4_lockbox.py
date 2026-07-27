from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from evaluation.cache_gtex_to_archs4_lockbox_scores import (
    CONDITIONS,
    sha256_array,
)
from evaluation.evaluate_gtex_to_archs4_lockbox import evaluate
from evaluation.freeze_gtex_to_archs4_candidates import ORGANS, SEEDS


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_evaluator_aggregates_every_seed_and_study(tmp_path: Path) -> None:
    evaluator = (
        Path(__file__).resolve().parents[1]
        / "evaluation/evaluate_gtex_to_archs4_lockbox.py"
    )
    protocol = tmp_path / "protocol.json"
    protocol.write_text(
        json.dumps(
            {
                "implementation_hashes": {
                    "lockbox_evaluator_sha256": _sha(evaluator)
                }
            }
        )
    )
    organs = np.repeat(np.asarray(ORGANS), 8)
    groups = np.asarray(
        [f"{organ}-study-{index}" for organ in ORGANS for index in range(8)]
    )
    sample_ids = np.asarray([f"S{index}" for index in range(len(organs))])
    target = np.ones((len(organs), 4), dtype=np.float32)
    seed_reports = {}
    for seed in SEEDS:
        arrays = {
            "sample_ids": sample_ids,
            "groups": groups,
            "organs": organs,
            "target_masked": target,
        }
        for condition in CONDITIONS:
            error = 0.5 if condition == "pooled" else 0.25
            arrays[f"prediction__{condition}"] = target + error
        metadata = {
            "status": "complete",
            "seed": seed,
            "best_seed_selection_performed": False,
            "conditions": list(CONDITIONS),
            "content_sha256": {
                name: sha256_array(value) for name, value in arrays.items()
            },
        }
        path = tmp_path / f"seed{seed}.npz"
        np.savez(
            path,
            **arrays,
            metadata_json=np.asarray(json.dumps(metadata, sort_keys=True)),
        )
        seed_reports[str(seed)] = {
            "score_cache": str(path),
            "score_cache_sha256": _sha(path),
        }
    score_report = tmp_path / "score_report.json"
    score_report.write_text(
        json.dumps(
            {
                "status": "complete",
                "seeds": list(SEEDS),
                "all_prespecified_seeds_scored": True,
                "best_seed_selection_performed": False,
                "evidence_label": "preregistered_lockbox_evaluation",
                "seed_reports": seed_reports,
            }
        )
    )
    result = evaluate(
        argparse.Namespace(
            protocol=str(protocol),
            expected_protocol_sha256=_sha(protocol),
            score_cache_report=str(score_report),
            output=str(tmp_path / "evaluation.json"),
            bootstrap_seed=1,
            bootstrap_repetitions=100,
        )
    )
    assert result["seeds"] == [17, 42, 101]
    assert result["best_seed_selection_performed"] is False
    assert (
        result["aggregate"]["true_organ"][
            "mean_mse_improvement_vs_pooled_across_all_seeds"
        ]
        > 0
    )
