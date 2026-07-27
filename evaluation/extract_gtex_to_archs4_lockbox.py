#!/usr/bin/env python3
"""Execute the single protocol-gated ARCHS4 K8 lockbox expression extraction."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

from preprocessing.extract_manifest_expression import extract_manifest_expression


CORE_EXTRACTOR = Path(__file__).resolve().parents[1] / "preprocessing" / "extract_manifest_expression.py"


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def extract_lockbox(args: argparse.Namespace) -> dict:
    if re.fullmatch(r"[0-9a-f]{40}", args.code_commit) is None:
        raise ValueError("lockbox extraction requires a full code commit")
    protocol_path = Path(args.protocol)
    freeze_report_path = Path(args.freeze_report)
    manifest_path = Path(args.lockbox_manifest)
    candidate_ledger_path = Path(args.candidate_ledger)
    human_h5_path = Path(args.human_h5)
    output_dir = Path(args.output_dir)
    for path in (
        protocol_path,
        freeze_report_path,
        manifest_path,
        candidate_ledger_path,
        Path(args.canonical_genes),
        Path(args.human_exon_lengths),
    ):
        if not path.is_file():
            raise FileNotFoundError(path)
    if output_dir.exists():
        raise FileExistsError(output_dir)
    if sha256_file(protocol_path) != args.expected_protocol_sha256:
        raise ValueError("lockbox protocol SHA256 mismatch")
    protocol = json.loads(protocol_path.read_text())
    if (
        protocol.get("status") != "frozen_gtex_to_archs4_k8_lockbox_protocol"
        or protocol.get("archs4_expression_accessed") is not False
        or protocol.get("fine_tuning", {}).get("archs4_exposure") != "zero"
    ):
        raise ValueError("protocol does not authorize a sealed zero-exposure test")
    gate = protocol.get("expression_access_gate", {})
    if (
        gate.get("all_implementation_hashes_frozen") is not True
        or gate.get("one_time_access_only") is not True
        or gate.get("membership_changes_after_access_allowed") is not False
    ):
        raise ValueError("protocol expression-access gate is not closed")

    implementation = protocol.get("implementation_hashes", {})
    wrapper_path = Path(__file__).resolve()
    expected_implementations = {
        "lockbox_extractor_wrapper_sha256": sha256_file(wrapper_path),
        "manifest_expression_core_sha256": sha256_file(CORE_EXTRACTOR),
    }
    for name, observed in expected_implementations.items():
        if implementation.get(name) != observed:
            raise ValueError(f"frozen implementation hash mismatch for {name}")

    freeze_report = json.loads(freeze_report_path.read_text())
    if (
        freeze_report.get("status")
        != "frozen_gtex_to_archs4_k8_lockbox_membership"
        or freeze_report.get("external_lockbox_frozen") is not True
        or freeze_report.get("ready_for_expression_access") is not True
        or freeze_report.get("archs4_expression_accessed") is not False
    ):
        raise ValueError("lockbox membership is not ready for expression access")
    if freeze_report.get("protocol_sha256") != sha256_file(protocol_path):
        raise ValueError("freeze report binds a different protocol")
    if freeze_report.get("candidate_ledger_sha256") != sha256_file(
        candidate_ledger_path
    ):
        raise ValueError("freeze report binds a different candidate ledger")
    if freeze_report.get("hashes", {}).get(
        "lockbox_manifest_sha256"
    ) != sha256_file(manifest_path):
        raise ValueError("lockbox manifest differs from freeze report")

    h5_contract = protocol.get("archs4_source", {})
    if not human_h5_path.is_file():
        raise FileNotFoundError(human_h5_path)
    expected_size = h5_contract.get("size_bytes")
    if expected_size is not None and int(expected_size) != human_h5_path.stat().st_size:
        raise ValueError("ARCHS4 H5 size differs from frozen source contract")

    report = extract_manifest_expression(
        manifest_path=manifest_path,
        human_h5_path=human_h5_path,
        canonical_genes_path=Path(args.canonical_genes),
        human_exon_lengths_path=Path(args.human_exon_lengths),
        output_dir=output_dir,
        batch_size=int(args.batch_size),
        parquet_row_group_size=int(args.parquet_row_group_size),
        qc_min_nonzero=int(args.qc_min_nonzero),
        compression=str(args.compression),
        source_h5_sha256=h5_contract.get("sha256"),
        hash_source_h5=False,
    )
    access_report = {
        "schema_version": 1,
        "status": "archs4_k8_lockbox_expression_extracted_once",
        "code_commit": args.code_commit,
        "protocol_sha256": sha256_file(protocol_path),
        "freeze_report_sha256": sha256_file(freeze_report_path),
        "lockbox_manifest_sha256": sha256_file(manifest_path),
        "candidate_ledger_sha256": sha256_file(candidate_ledger_path),
        "archs4_expression_accessed": True,
        "efficacy_scoring_performed": False,
        "fine_tuning_exposure": "zero",
        "membership_changed_after_access": False,
        "expression_parquet_sha256": report["outputs"][
            "expression_parquet_sha256"
        ],
        "extraction_report_sha256": sha256_file(
            output_dir / "extraction_report.json"
        ),
        "selected_aggregated_counts_sha256": report["source_h5"][
            "selected_aggregated_counts_sha256"
        ],
        "next_gate": "Score every frozen seed/control exactly once; do not alter membership.",
    }
    access_path = output_dir / "lockbox_access_report.json"
    temporary = access_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(access_report, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, access_path)
    (output_dir / "LOCKBOX_EXPRESSION_ACCESSED").touch()
    return access_report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--freeze-report", required=True)
    parser.add_argument("--lockbox-manifest", required=True)
    parser.add_argument("--candidate-ledger", required=True)
    parser.add_argument("--human-h5", required=True)
    parser.add_argument("--canonical-genes", required=True)
    parser.add_argument("--human-exon-lengths", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--parquet-row-group-size", type=int, default=256)
    parser.add_argument("--qc-min-nonzero", type=int, default=14000)
    parser.add_argument("--compression", default="zstd")
    print(json.dumps(extract_lockbox(parser.parse_args()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
