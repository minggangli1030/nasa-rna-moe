from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from evaluation.amend_gtex_to_archs4_qc_lockbox import ORGANS, build_amendment


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path) -> argparse.Namespace:
    rows = []
    for organ in ORGANS:
        for group_index in range(8):
            n = 5 if organ == "liver" and group_index == 0 else 2
            for sample_index in range(n):
                rows.append(
                    {
                        "sample_id": f"{organ}-{group_index}-{sample_index}",
                        "organ": organ,
                        "series_group_id": f"{organ}-g{group_index}",
                    }
                )
    while len(rows) < 827:
        index = len(rows)
        rows.append(
            {
                "sample_id": f"extra-{index}",
                "organ": "brain",
                "series_group_id": "brain-g1",
            }
        )
    manifest = tmp_path / "manifest.csv"
    pd.DataFrame(rows).to_csv(manifest, index=False)
    parent = tmp_path / "parent.json"
    parent.write_text(json.dumps({"status": "frozen_gtex_to_archs4_k8_lockbox_protocol"}))
    freeze = tmp_path / "freeze.json"
    freeze.write_text(
        json.dumps({"hashes": {"lockbox_manifest_sha256": _sha(manifest)}})
    )
    excluded = [f"liver-0-{index}" for index in range(5)] + ["brain-1-0"]
    failure = tmp_path / "failure.json"
    failure.write_text(
        json.dumps(
            {
                "status": "failed_closed_at_expression_qc",
                "protocol_sha256": _sha(parent),
                "lockbox_samples_requested": 827,
                "lockbox_samples_published": 0,
                "scoring_started": False,
                "membership_changed": False,
                "qc_min_nonzero_genes": 14000,
                "failed_samples": [
                    {"sample_id": sample, "nonzero_genes": index + 1}
                    for index, sample in enumerate(excluded)
                ],
            }
        )
    )
    approval = tmp_path / "approval.json"
    approval.write_text(
        json.dumps(
            {
                "decision": "proceed_with_versioned_qc_amended_external_evaluation",
                "exclude_exact_qc_failures_only": True,
                "add_replacements": False,
                "lower_qc_threshold": False,
                "allow_tuning": False,
                "allow_best_seed_selection": False,
            }
        )
    )
    return argparse.Namespace(
        parent_protocol=str(parent),
        parent_freeze_report=str(freeze),
        parent_manifest=str(manifest),
        qc_failure_artifact=str(failure),
        approval=str(approval),
        code_commit="a" * 40,
        output_dir=str(tmp_path / "amended"),
    )


def test_amendment_removes_only_exact_qc_failures(tmp_path: Path) -> None:
    args = _fixture(tmp_path)
    result = build_amendment(args)
    assert result["retained_samples"] == 821
    assert result["retained_study_groups"] == 63
    assert result["retained_study_groups_per_organ"]["liver"] == 7
    assert result["replacement_samples_added"] == 0


def test_amendment_rejects_threshold_relaxation(tmp_path: Path) -> None:
    args = _fixture(tmp_path)
    approval = Path(args.approval)
    value = json.loads(approval.read_text())
    value["lower_qc_threshold"] = True
    approval.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="does not authorize"):
        build_amendment(args)
