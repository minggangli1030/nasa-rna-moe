from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pytest

from evaluation.cache_gtex_to_archs4_lockbox_scores import (
    validate_preflight,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path) -> argparse.Namespace:
    paths = {
        name: tmp_path / name
        for name in (
            "ledger.json",
            "mappings.json",
            "manifest.csv",
            "freeze.json",
            "expression.parquet",
            "extraction.json",
            "access.json",
        )
    }
    paths["ledger.json"].write_text(
        json.dumps(
            {
                "status": "frozen_gtex_only_k8_candidate_ledger",
                "seeds": [17, 42, 101],
                "best_seed_selection_allowed": False,
            }
        )
    )
    paths["mappings.json"].write_text(
        json.dumps(
            {
                "status": "frozen_gtex_calibration_random_control_mappings",
                "candidate_ledger_sha256": _sha(paths["ledger.json"]),
                "archs4_expression_accessed": False,
            }
        )
    )
    paths["manifest.csv"].write_text("sample_id\nS1\n")
    paths["expression.parquet"].write_bytes(b"expression")
    paths["freeze.json"].write_text(
        json.dumps(
            {
                "ready_for_expression_access": True,
                "hashes": {
                    "lockbox_manifest_sha256": _sha(paths["manifest.csv"])
                },
            }
        )
    )
    paths["extraction.json"].write_text(
        json.dumps(
            {
                "outputs": {
                    "expression_parquet_sha256": _sha(
                        paths["expression.parquet"]
                    )
                }
            }
        )
    )
    protocol = tmp_path / "protocol.json"
    scorer = (
        Path(__file__).resolve().parents[1]
        / "evaluation/cache_gtex_to_archs4_lockbox_scores.py"
    )
    protocol.write_text(
        json.dumps(
            {
                "status": "frozen_gtex_to_archs4_k8_lockbox_protocol",
                "expression_access_gate": {
                    "all_implementation_hashes_frozen": True
                },
                "implementation_hashes": {
                    "lockbox_score_cache_sha256": _sha(scorer)
                },
                "source_contract": {
                    "candidate_ledger_sha256": _sha(paths["ledger.json"]),
                    "random_mappings_sha256": _sha(paths["mappings.json"]),
                },
            }
        )
    )
    paths["access.json"].write_text(
        json.dumps(
            {
                "status": "archs4_k8_lockbox_expression_extracted_once",
                "protocol_sha256": _sha(protocol),
                "candidate_ledger_sha256": _sha(paths["ledger.json"]),
                "lockbox_manifest_sha256": _sha(paths["manifest.csv"]),
                "expression_parquet_sha256": _sha(paths["expression.parquet"]),
            }
        )
    )
    return argparse.Namespace(
        protocol=str(protocol),
        expected_protocol_sha256=_sha(protocol),
        candidate_ledger=str(paths["ledger.json"]),
        random_mappings=str(paths["mappings.json"]),
        lockbox_manifest=str(paths["manifest.csv"]),
        freeze_report=str(paths["freeze.json"]),
        expression_parquet=str(paths["expression.parquet"]),
        extraction_report=str(paths["extraction.json"]),
        access_report=str(paths["access.json"]),
    )


def test_score_preflight_accepts_fully_bound_inputs(tmp_path: Path) -> None:
    result = validate_preflight(_fixture(tmp_path))
    assert result["ledger"]["seeds"] == [17, 42, 101]


def test_score_preflight_rejects_changed_expression(tmp_path: Path) -> None:
    args = _fixture(tmp_path)
    Path(args.expression_parquet).write_bytes(b"changed")
    with pytest.raises(ValueError, match="access report"):
        validate_preflight(args)
