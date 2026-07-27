from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pytest

from evaluation.freeze_gtex_to_archs4_candidates import (
    AXES,
    ORGANS,
    SEEDS,
    freeze_candidates,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return _sha(path)


def _fixture(tmp_path: Path) -> tuple[Path, argparse.Namespace]:
    root = tmp_path / "training"
    _write(root / "TRAINING_COMPLETE", "")
    _write(root / "TRAINING_STATUS", "COMPLETE now\n")
    _write(root / "CODE_COMMIT", "1" * 40 + "\n")
    _write(root / "PROTOCOL_SHA256", "2" * 64 + "\n")
    manifest_entries = []
    for seed in SEEDS:
        pooled = root / f"seed{seed}/pooled/best_model.pt"
        pooled_hash = _write(pooled, f"pooled-{seed}")
        pooled_meta = {
            "status": "complete",
            "seed": seed,
            "hashes": {"best_checkpoint_sha256": pooled_hash},
        }
        _write(
            root / f"seed{seed}/pooled/run_metadata.json",
            json.dumps(pooled_meta),
        )
        for axis in AXES:
            checkpoint = root / f"seed{seed}/banks/banks/{axis}/final_experts.pt"
            checkpoint_hash = _write(checkpoint, f"{seed}-{axis}")
            config = {"axis": axis, "final_update": 1500}
            if axis == "organ_k8":
                config["expert_initialization_keys"] = [
                    f"organ:{organ}" for organ in ORGANS
                ]
            metadata = {
                "status": "complete",
                "training_seed": seed,
                "config": config,
                "hashes": {"pooled_checkpoint_sha256": pooled_hash},
                "artifacts": {"final_experts_sha256": checkpoint_hash},
            }
            _write(
                root / f"seed{seed}/banks/banks/{axis}/run_metadata.json",
                json.dumps(metadata),
            )
    router_hash = _write(root / "router/gtex_k8_target_hidden_router.npz", "router")
    _write(
        root / "router/router_report.json",
        json.dumps({
            "status": "complete",
            "archs4_expression_accessed": False,
            "performance_metrics_generated": False,
            "classes": list(ORGANS),
            "hashes": {"router_artifact_sha256": router_hash},
        }),
    )
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "FULL_SHA256SUMS":
            relative = path.relative_to(root)
            manifest_entries.append(f"{_sha(path)}  ./{relative}\n")
    checksum = root / "FULL_SHA256SUMS"
    checksum.write_text("".join(manifest_entries))
    args = argparse.Namespace(
        training_root=str(root),
        expected_training_commit="1" * 40,
        expected_training_protocol_sha256="2" * 64,
        expected_checksum_manifest_sha256=_sha(checksum),
        code_commit="3" * 40,
        output=str(tmp_path / "ledger.json"),
    )
    return root, args


def test_candidate_freeze_binds_every_seed_axis_and_router(tmp_path: Path) -> None:
    _, args = _fixture(tmp_path)
    result = freeze_candidates(args)
    assert result["status"] == "frozen_gtex_only_k8_candidate_ledger"
    assert result["seeds"] == [17, 42, 101]
    assert result["best_seed_selection_allowed"] is False
    assert result["archs4_expression_accessed"] is False
    assert all(set(seed["banks"]) == set(AXES) for seed in result["seed_candidates"])


def test_candidate_freeze_rejects_checkpoint_tampering(tmp_path: Path) -> None:
    root, args = _fixture(tmp_path)
    (root / "seed17/pooled/best_model.pt").write_text("tampered")
    with pytest.raises(ValueError, match="checksum mismatch"):
        freeze_candidates(args)
