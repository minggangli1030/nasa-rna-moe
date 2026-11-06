from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import pytest

from evaluation.extract_gtex_to_archs4_lockbox import (
    CORE_EXTRACTOR,
    extract_lockbox,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path) -> argparse.Namespace:
    manifest = tmp_path / "manifest.csv"
    pd.DataFrame({
        "sample_id": ["S1", "S2"],
        "organ": ["brain", "skin"],
        "series_group_id": ["G1", "G2"],
        "split": ["test", "test"],
    }).to_csv(manifest, index=False)
    genes = tmp_path / "genes.txt"
    genes.write_text("A\nB\n")
    lengths = tmp_path / "lengths.csv"
    pd.DataFrame({
        "gene_symbol": ["A", "B"],
        "exon_length": [1000, 2000],
    }).to_csv(lengths, index=False)
    h5 = tmp_path / "human.h5"
    with h5py.File(h5, "w") as handle:
        handle.create_dataset(
            "data/expression",
            data=np.asarray([[10, 20], [30, 40]], dtype=np.float32),
        )
        handle.create_dataset(
            "meta/genes/gene_symbol", data=np.asarray(["A", "B"], dtype="S")
        )
        handle.create_dataset(
            "meta/samples/geo_accession", data=np.asarray(["S1", "S2"], dtype="S")
        )
    ledger = tmp_path / "ledger.json"
    ledger.write_text("{}")
    protocol_path = tmp_path / "protocol.json"
    wrapper_path = Path(__file__).resolve().parents[1] / "evaluation" / "extract_gtex_to_archs4_lockbox.py"
    protocol = {
        "status": "frozen_gtex_to_archs4_k8_lockbox_protocol",
        "archs4_expression_accessed": False,
        "fine_tuning": {"archs4_exposure": "zero"},
        "expression_access_gate": {
            "all_implementation_hashes_frozen": True,
            "one_time_access_only": True,
            "membership_changes_after_access_allowed": False,
        },
        "implementation_hashes": {
            "lockbox_extractor_wrapper_sha256": _sha(wrapper_path),
            "manifest_expression_core_sha256": _sha(CORE_EXTRACTOR),
        },
        "archs4_source": {"size_bytes": h5.stat().st_size},
    }
    protocol_path.write_text(json.dumps(protocol))
    freeze = tmp_path / "freeze.json"
    freeze.write_text(json.dumps({
        "status": "frozen_gtex_to_archs4_k8_lockbox_membership",
        "external_lockbox_frozen": True,
        "ready_for_expression_access": True,
        "archs4_expression_accessed": False,
        "protocol_sha256": _sha(protocol_path),
        "candidate_ledger_sha256": _sha(ledger),
        "hashes": {"lockbox_manifest_sha256": _sha(manifest)},
    }))
    return argparse.Namespace(
        protocol=str(protocol_path),
        expected_protocol_sha256=_sha(protocol_path),
        freeze_report=str(freeze),
        lockbox_manifest=str(manifest),
        candidate_ledger=str(ledger),
        human_h5=str(h5),
        canonical_genes=str(genes),
        human_exon_lengths=str(lengths),
        output_dir=str(tmp_path / "output"),
        code_commit="a" * 40,
        batch_size=2,
        parquet_row_group_size=2,
        qc_min_nonzero=1,
        compression="zstd",
    )


def test_protocol_gated_lockbox_extraction_marks_one_time_access(
    tmp_path: Path,
) -> None:
    args = _fixture(tmp_path)
    result = extract_lockbox(args)
    assert result["archs4_expression_accessed"] is True
    assert result["efficacy_scoring_performed"] is False
    assert (tmp_path / "output/LOCKBOX_EXPRESSION_ACCESSED").is_file()


def test_extractor_rejects_unfrozen_membership(tmp_path: Path) -> None:
    args = _fixture(tmp_path)
    freeze_path = Path(args.freeze_report)
    freeze = json.loads(freeze_path.read_text())
    freeze["ready_for_expression_access"] = False
    freeze_path.write_text(json.dumps(freeze))
    with pytest.raises(ValueError, match="not ready"):
        extract_lockbox(args)


def test_qc_amended_extractor_preserves_post_access_label(tmp_path: Path) -> None:
    args = _fixture(tmp_path)
    freeze_path = Path(args.freeze_report)
    manifest_path = Path(args.lockbox_manifest)
    freeze_path.write_text(
        json.dumps(
            {
                "status": "frozen_post_access_qc_amended_membership",
                "retained_samples": 821,
                "retained_study_groups": 63,
                "replacement_samples_added": 0,
                "efficacy_was_available_at_amendment": False,
                "hashes": {
                    "qc_amended_manifest_sha256": _sha(manifest_path)
                },
            }
        )
    )
    protocol_path = Path(args.protocol)
    protocol = json.loads(protocol_path.read_text())
    protocol.update(
        {
            "status": "frozen_gtex_to_archs4_k8_qc_amended_protocol",
            "archs4_expression_accessed_pre_amendment": True,
            "efficacy_scoring_performed_pre_amendment": False,
            "evidence_label": "post_access_qc_amended_external_evaluation",
            "qc_amendment": {"excluded_samples": 6},
            "source_contract": {
                "amendment_report_sha256": _sha(freeze_path),
                "candidate_ledger_sha256": _sha(Path(args.candidate_ledger)),
            },
            "expression_access_gate": {
                "all_implementation_hashes_frozen": True,
                "repeat_mechanical_extraction_authorized": True,
                "only_exact_qc_exclusions_allowed": True,
                "further_membership_changes_allowed": False,
            },
        }
    )
    protocol_path.write_text(json.dumps(protocol))
    args.expected_protocol_sha256 = _sha(protocol_path)
    result = extract_lockbox(args)
    assert result["status"] == "archs4_k8_qc_amended_expression_extracted"
    assert result["membership_changed_after_access"] is True
