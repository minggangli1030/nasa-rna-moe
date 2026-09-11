from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from evaluation.audit_stage2_gtex_k8_frozen_experts import audit
from evaluation.freeze_gtex_to_archs4_candidates import ORGANS, SEEDS


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_audit_builds_seed_stable_named_expert_matrix(tmp_path: Path) -> None:
    training = tmp_path / "training"
    candidates = []
    sample_ids = np.asarray(
        [f"{organ}-{index}" for organ in ORGANS for index in range(2)]
    )
    organs = np.repeat(np.asarray(ORGANS), 2)
    groups = np.asarray(
        [f"donor-{organ}-{index}" for organ in ORGANS for index in range(2)]
    )
    labels = np.asarray([ORGANS.index(organ) for organ in organs], dtype=np.int64)
    for seed in SEEDS:
        path = training / f"seed{seed}/organ/calibration_scores.npz"
        path.parent.mkdir(parents=True)
        pooled = np.ones(len(organs), dtype=np.float64)
        expert = np.full((len(organs), len(ORGANS)), 1.05, dtype=np.float64)
        for row, label in enumerate(labels):
            expert[row, label] = 0.9
        np.savez(
            path,
            sample_ids=sample_ids,
            groups=groups,
            organs=organs,
            sample_weights=np.ones(len(organs), dtype=np.float64),
            pooled_mse=pooled,
            true_partition_mse=np.full(len(organs), 0.9, dtype=np.float64),
            oracle_mse=np.full(len(organs), 0.9, dtype=np.float64),
            expert_mse=expert,
            true_labels=labels,
        )
        candidates.append(
            {
                "seed": seed,
                "banks": {
                    "organ_k8": {
                        "calibration_scores": {
                            "path": str(path.relative_to(training)),
                            "sha256": _sha(path),
                        }
                    }
                },
            }
        )
    ledger = tmp_path / "ledger.json"
    ledger.write_text(
        json.dumps(
            {
                "status": "frozen_gtex_only_k8_candidate_ledger",
                "organs": list(ORGANS),
                "best_seed_selection_allowed": False,
                "fine_tuning_exposure": "zero",
                "seed_candidates": candidates,
            }
        )
    )

    result = audit(
        argparse.Namespace(
            candidate_ledger=str(ledger),
            expected_candidate_ledger_sha256=_sha(ledger),
            training_root=str(training),
            output_dir=str(tmp_path / "output"),
        )
    )

    assert result["status"] == "complete"
    assert result["development_only"] is True
    assert result["archs4_expression_loaded"] is False
    assert np.isclose(
        result["mean_true_dispatch_relative_mse_improvement_percent"], 10.0
    )
    for organ in ORGANS:
        summary = result["recipient_summary"][organ]
        assert np.isclose(
            summary["named_expert_relative_mse_improvement_percent"], 10.0
        )
        assert summary["named_expert_positive_seed_count"] == 3
        assert summary["named_expert_rank_among_8"] == 1
        assert summary["best_expert"] == organ
    matrix = pd.read_csv(
        tmp_path / "output/mean_relative_mse_improvement_percent.csv",
        index_col=0,
    )
    assert matrix.loc["brain", "brain"] == 10.0
    assert matrix.loc["brain", "liver"] == -5.0


def test_audit_rejects_missing_prespecified_seeds(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.json"
    ledger.write_text(
        json.dumps(
            {
                "status": "frozen_gtex_only_k8_candidate_ledger",
                "organs": list(ORGANS),
                "best_seed_selection_allowed": False,
                "fine_tuning_exposure": "zero",
                "seed_candidates": [],
            }
        )
    )
    with np.testing.assert_raises_regex(ValueError, "exactly one seed"):
        audit(
            argparse.Namespace(
                candidate_ledger=str(ledger),
                expected_candidate_ledger_sha256=_sha(ledger),
                training_root=str(tmp_path / "training"),
                output_dir=str(tmp_path / "output"),
            )
        )
