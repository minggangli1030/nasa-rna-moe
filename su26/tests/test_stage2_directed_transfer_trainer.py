from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch
from torch import nn

from core.train_stage2_directed_transfer import (
    _ExactScheduleBatchSampler,
    _initialize_expert,
    _load_contract,
    _tensor_state_sha256,
)
from core.train_manifest import sha256_file


def _contract(tmp_path: Path):
    schedules = pd.DataFrame(
        [
            {
                "arm_id": "sub__brain__liver",
                "draw_number": draw,
                "batch_number": draw // 2,
                "batch_position": draw % 2,
                "source_draw_number": draw // 2,
                "source_role": "brain" if draw % 2 == 0 else "liver",
                "source_label": "brain" if draw % 2 == 0 else "liver",
                "sample_id": "B" if draw % 2 == 0 else "L",
                "donor_id": "DB" if draw % 2 == 0 else "DL",
                "organ": "brain" if draw % 2 == 0 else "liver",
                "series_group_id": "DB" if draw % 2 == 0 else "DL",
            }
            for draw in range(4)
        ]
    )
    schedule_path = tmp_path / "schedules.parquet"
    schedules.to_parquet(schedule_path, index=False)
    definitions = {
        "schema_version": 1,
        "initialization_key": "shared",
        "arms": [
            {
                "arm_id": "sub__brain__liver",
                "batch_size": 2,
                "number_batches": 2,
                "total_draws": 4,
                "source_draws": {"brain": 2, "liver": 2},
                "source_draws_per_batch": {"brain": 1, "liver": 1},
                "evaluation_recipients": ["brain", "liver"],
            }
        ],
    }
    definitions_path = tmp_path / "definitions.json"
    definitions_path.write_text(json.dumps(definitions))
    manifest_path = tmp_path / "manifest.parquet"
    pd.DataFrame({"sample_id": ["B", "L"]}).to_parquet(manifest_path, index=False)
    report = {
        "status": "complete",
        "development_only": True,
        "expression_loaded": False,
        "model_fit": False,
        "best_seed_selection_allowed": False,
        "initialization_key": "shared",
        "counts": {"total_arms": 1, "total_schedule_draws": 4},
        "hashes": {
            "training_schedules_sha256": sha256_file(schedule_path),
            "arm_definitions_sha256": sha256_file(definitions_path),
            "manifest_sha256": sha256_file(manifest_path),
        },
    }
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report))
    return schedule_path, definitions_path, report_path, manifest_path


def test_contract_and_exact_sampler_preserve_source_local_draws(tmp_path: Path) -> None:
    schedule, definitions, report, manifest = _contract(tmp_path)
    frame, arms, _ = _load_contract(
        schedules_path=schedule,
        definitions_path=definitions,
        report_path=report,
        manifest_path=manifest,
        expected_schedule_sha256=sha256_file(schedule),
        expected_definitions_sha256=sha256_file(definitions),
    )
    assert len(arms) == 1
    sampler = _ExactScheduleBatchSampler(
        frame, {"B": 7, "L": 9}, batch_size=2
    )
    assert list(sampler) == [((7, 0), (9, 0)), ((7, 1), (9, 1))]


def test_contract_rejects_hash_and_per_batch_source_drift(tmp_path: Path) -> None:
    schedule, definitions, report, manifest = _contract(tmp_path)
    with pytest.raises(ValueError, match="expected SHA256"):
        _load_contract(
            schedules_path=schedule,
            definitions_path=definitions,
            report_path=report,
            manifest_path=manifest,
            expected_schedule_sha256="0" * 64,
            expected_definitions_sha256=sha256_file(definitions),
        )

    frame = pd.read_parquet(schedule)
    frame.loc[1, "source_role"] = "brain"
    frame.to_parquet(schedule, index=False)
    payload = json.loads(Path(report).read_text())
    payload["hashes"]["training_schedules_sha256"] = sha256_file(schedule)
    Path(report).write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="source totals|balanced per batch"):
        _load_contract(
            schedules_path=schedule,
            definitions_path=definitions,
            report_path=report,
            manifest_path=manifest,
            expected_schedule_sha256=sha256_file(schedule),
            expected_definitions_sha256=sha256_file(definitions),
        )


class _TinyTrunk(nn.Module):
    def __init__(self):
        super().__init__()
        self.gene_embedding = nn.Embedding(5, 6)


def test_semantic_initialization_is_identical_across_arms_and_seed_specific() -> None:
    first = _initialize_expert(
        hidden_dim=6,
        adapter_dim=3,
        training_seed=17,
        initialization_key="shared",
    )
    repeated = _initialize_expert(
        hidden_dim=6,
        adapter_dim=3,
        training_seed=17,
        initialization_key="shared",
    )
    other_seed = _initialize_expert(
        hidden_dim=6,
        adapter_dim=3,
        training_seed=42,
        initialization_key="shared",
    )
    assert _tensor_state_sha256(first.state_dict()) == _tensor_state_sha256(
        repeated.state_dict()
    )
    assert _tensor_state_sha256(first.state_dict()) != _tensor_state_sha256(
        other_seed.state_dict()
    )
