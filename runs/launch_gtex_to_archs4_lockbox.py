#!/usr/bin/env python3
"""Run membership freeze, one-time extraction, all-seed scoring, and evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.cache_gtex_to_archs4_lockbox_scores import build_score_cache
from evaluation.evaluate_gtex_to_archs4_lockbox import evaluate
from evaluation.extract_gtex_to_archs4_lockbox import extract_lockbox
from evaluation.freeze_gtex_to_archs4_lockbox import freeze_lockbox


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def launch(args: argparse.Namespace) -> dict:
    protocol_path = Path(args.protocol)
    output = Path(args.output_dir)
    phase = str(args.phase)
    if phase not in {"all", "extract", "score"}:
        raise ValueError(f"unsupported launcher phase: {phase}")
    if phase in {"all", "extract"}:
        required_extract_args = (
            "sample_review",
            "study_review",
            "sample_review_report",
            "donor_audit_samples",
            "donor_audit_studies",
            "donor_audit_report",
            "human_h5",
            "canonical_genes",
            "human_exon_lengths",
        )
        missing = [
            name for name in required_extract_args if not getattr(args, name, None)
        ]
        if missing:
            raise ValueError(f"extract phase lacks required arguments: {missing}")
    if phase in {"all", "extract"} and output.exists():
        raise FileExistsError(output)
    if phase == "score" and not output.is_dir():
        raise FileNotFoundError(output)
    if re.fullmatch(r"[0-9a-f]{40}", args.code_commit) is None:
        raise ValueError("launcher requires a full implementation commit")
    if sha256_file(protocol_path) != args.expected_protocol_sha256:
        raise ValueError("protocol SHA256 mismatch")
    protocol = json.loads(protocol_path.read_text())
    if protocol.get("implementation_hashes", {}).get(
        "one_time_launcher_sha256"
    ) != sha256_file(Path(__file__).resolve()):
        raise ValueError("launcher differs from frozen implementation")
    if protocol.get("implementation_commit") != args.code_commit:
        raise ValueError("launcher code commit differs from protocol")
    changed = subprocess.run(
        [
            "git",
            "diff",
            "--quiet",
            args.code_commit,
            "--",
            "evaluation",
            "preprocessing/extract_manifest_expression.py",
            "runs/launch_gtex_to_archs4_lockbox.py",
        ],
        cwd=ROOT,
        check=False,
    )
    if changed.returncode != 0:
        raise RuntimeError("implementation files differ from the frozen commit")

    if phase in {"all", "extract"}:
        output.mkdir(parents=True)
    status_path = output / "launcher_status.json"

    def status(stage: str, state: str) -> None:
        temporary = status_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(
                {
                    "status": state,
                    "stage": stage,
                    "protocol_sha256": sha256_file(protocol_path),
                    "code_commit": args.code_commit,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        os.replace(temporary, status_path)

    membership_dir = output / "membership"
    expression_dir = output / "expression"
    if phase in {"all", "extract"}:
        status("membership_freeze", "running")
        freeze_lockbox(
            argparse.Namespace(
                protocol=str(protocol_path),
                expected_protocol_sha256=args.expected_protocol_sha256,
                candidate_ledger=args.candidate_ledger,
                sample_review=args.sample_review,
                study_review=args.study_review,
                sample_review_report=args.sample_review_report,
                donor_audit_samples=args.donor_audit_samples,
                donor_audit_studies=args.donor_audit_studies,
                donor_audit_report=args.donor_audit_report,
                code_commit=args.code_commit,
                output_dir=str(membership_dir),
            )
        )
        status("expression_extraction", "running")
        extract_lockbox(
            argparse.Namespace(
                protocol=str(protocol_path),
                expected_protocol_sha256=args.expected_protocol_sha256,
                freeze_report=str(membership_dir / "lockbox_freeze_report.json"),
                lockbox_manifest=str(membership_dir / "lockbox_manifest.csv"),
                candidate_ledger=args.candidate_ledger,
                human_h5=args.human_h5,
                canonical_genes=args.canonical_genes,
                human_exon_lengths=args.human_exon_lengths,
                output_dir=str(expression_dir),
                code_commit=args.code_commit,
                batch_size=args.extraction_batch_size,
                parquet_row_group_size=args.parquet_row_group_size,
                qc_min_nonzero=args.qc_min_nonzero,
                compression="zstd",
            )
        )
        if phase == "extract":
            handoff = {
                "status": "handoff_ready",
                "stage": "expression_extraction_complete",
                "protocol_sha256": sha256_file(protocol_path),
                "code_commit": args.code_commit,
                "membership_dir": str(membership_dir.resolve()),
                "expression_dir": str(expression_dir.resolve()),
                "freeze_report_sha256": sha256_file(
                    membership_dir / "lockbox_freeze_report.json"
                ),
                "access_report_sha256": sha256_file(
                    expression_dir / "lockbox_access_report.json"
                ),
                "expression_parquet_sha256": sha256_file(
                    expression_dir / "expression.parquet"
                ),
                "next_phase": "score",
            }
            temporary = status_path.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(handoff, indent=2, sort_keys=True) + "\n")
            os.replace(temporary, status_path)
            (output / "LOCKBOX_HANDOFF_READY").touch()
            return handoff
    else:
        required_handoff = (
            output / "LOCKBOX_HANDOFF_READY",
            membership_dir / "lockbox_freeze_report.json",
            membership_dir / "lockbox_manifest.csv",
            expression_dir / "expression.parquet",
            expression_dir / "extraction_report.json",
            expression_dir / "lockbox_access_report.json",
        )
        for path in required_handoff:
            if not path.is_file():
                raise FileNotFoundError(path)
        prior = json.loads(status_path.read_text())
        if (
            prior.get("status") != "handoff_ready"
            or prior.get("protocol_sha256") != sha256_file(protocol_path)
            or prior.get("expression_parquet_sha256")
            != sha256_file(expression_dir / "expression.parquet")
        ):
            raise ValueError("transferred extraction handoff failed validation")
    status("all_seed_scoring", "running")
    scores_dir = output / "scores"
    build_score_cache(
        argparse.Namespace(
            protocol=str(protocol_path),
            expected_protocol_sha256=args.expected_protocol_sha256,
            candidate_ledger=args.candidate_ledger,
            random_mappings=args.random_mappings,
            lockbox_manifest=str(membership_dir / "lockbox_manifest.csv"),
            freeze_report=str(membership_dir / "lockbox_freeze_report.json"),
            expression_parquet=str(expression_dir / "expression.parquet"),
            extraction_report=str(expression_dir / "extraction_report.json"),
            access_report=str(expression_dir / "lockbox_access_report.json"),
            training_root=args.training_root,
            output_dir=str(scores_dir),
            device=args.device,
            batch_size=args.score_batch_size,
        )
    )
    status("study_macro_evaluation", "running")
    evaluation_path = output / "evaluation_report.json"
    evaluate(
        argparse.Namespace(
            protocol=str(protocol_path),
            expected_protocol_sha256=args.expected_protocol_sha256,
            score_cache_report=str(scores_dir / "score_cache_report.json"),
            output=str(evaluation_path),
            bootstrap_seed=args.bootstrap_seed,
            bootstrap_repetitions=args.bootstrap_repetitions,
        )
    )
    final = {
        "status": "complete",
        "stage": "complete",
        "protocol_sha256": sha256_file(protocol_path),
        "code_commit": args.code_commit,
        "evaluation_report": str(evaluation_path.resolve()),
        "evaluation_report_sha256": sha256_file(evaluation_path),
        "all_prespecified_seeds_scored": True,
        "best_seed_selection_performed": False,
        "fine_tuning_performed": False,
    }
    temporary = status_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(final, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, status_path)
    (output / "LOCKBOX_PIPELINE_COMPLETE").touch()
    return final


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--candidate-ledger", required=True)
    parser.add_argument("--random-mappings", required=True)
    parser.add_argument("--sample-review")
    parser.add_argument("--study-review")
    parser.add_argument("--sample-review-report")
    parser.add_argument("--donor-audit-samples")
    parser.add_argument("--donor-audit-studies")
    parser.add_argument("--donor-audit-report")
    parser.add_argument("--human-h5")
    parser.add_argument("--canonical-genes")
    parser.add_argument("--human-exon-lengths")
    parser.add_argument("--training-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument(
        "--phase",
        choices=("all", "extract", "score"),
        default="all",
        help="Use extract locally and score after copying the complete handoff.",
    )
    parser.add_argument("--device", default="auto")
    parser.add_argument("--extraction-batch-size", type=int, default=128)
    parser.add_argument("--parquet-row-group-size", type=int, default=256)
    parser.add_argument("--qc-min-nonzero", type=int, default=14000)
    parser.add_argument("--score-batch-size", type=int, default=8)
    parser.add_argument("--bootstrap-seed", type=int, default=314159)
    parser.add_argument("--bootstrap-repetitions", type=int, default=10000)
    print(json.dumps(launch(parser.parse_args()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
