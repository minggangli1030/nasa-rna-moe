from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from evaluation.freeze_gtex_to_archs4_candidates import ORGANS, SEEDS
from evaluation.freeze_gtex_to_archs4_random_controls import (
    RANDOM_AXES,
    freeze_random_controls,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path) -> argparse.Namespace:
    root = tmp_path / "training"
    seed_entries = []
    organs = np.repeat(np.asarray(ORGANS), 2)
    groups = np.asarray(
        [f"{organ}-g{index}" for organ in ORGANS for index in range(2)]
    )
    sample_ids = np.asarray([f"S{index}" for index in range(len(organs))])
    for seed in SEEDS:
        banks = {}
        for axis_index, axis in enumerate(RANDOM_AXES):
            path = root / f"seed{seed}/{axis}.npz"
            path.parent.mkdir(parents=True, exist_ok=True)
            expert_mse = np.ones((len(organs), 8), dtype=np.float64)
            for organ_index, organ in enumerate(ORGANS):
                expert_mse[organs == organ, (organ_index + axis_index) % 8] = 0.0
            np.savez(
                path,
                sample_ids=sample_ids,
                groups=groups,
                organs=organs,
                expert_mse=expert_mse,
            )
            banks[axis] = {
                "calibration_scores": {
                    "path": str(path.relative_to(root)),
                    "sha256": _sha(path),
                    "size_bytes": path.stat().st_size,
                }
            }
        seed_entries.append({"seed": seed, "banks": banks})
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps({
        "status": "frozen_gtex_only_k8_candidate_ledger",
        "archs4_expression_accessed": False,
        "seeds": list(SEEDS),
        "seed_candidates": seed_entries,
    }))
    return argparse.Namespace(
        candidate_ledger=str(ledger),
        expected_candidate_ledger_sha256=_sha(ledger),
        training_root=str(root),
        output=str(tmp_path / "mappings.json"),
    )


def test_random_mapping_is_frozen_from_calibration_only(tmp_path: Path) -> None:
    args = _fixture(tmp_path)
    result = freeze_random_controls(args)
    assert result["archs4_expression_accessed"] is False
    for seed in SEEDS:
        for axis_index, axis in enumerate(RANDOM_AXES):
            for organ_index, organ in enumerate(ORGANS):
                selected = result["mappings"][str(seed)][axis]["by_organ"][organ][
                    "selected_random_expert_index"
                ]
                assert selected == (organ_index + axis_index) % 8


def test_random_mapping_rejects_tampered_scores(tmp_path: Path) -> None:
    args = _fixture(tmp_path)
    path = next(Path(args.training_root).rglob("*.npz"))
    path.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="hash mismatch"):
        freeze_random_controls(args)
