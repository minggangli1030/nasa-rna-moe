#!/usr/bin/env python3
"""Launch assigned frozen-trunk adapter-scale combinations sequentially."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


ORGANS = (
    "adipose",
    "brain",
    "colon",
    "heart",
    "liver",
    "lung",
    "skeletal_muscle",
    "skin",
)
SEEDS = (17, 42, 101)
BUDGETS = (25, 50, 100, 150, 200)


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_status(path: Path, text: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text.rstrip() + "\n")
    os.replace(temporary, path)


def _parse_combo(value: str) -> tuple[int, int]:
    try:
        budget, seed = [int(part) for part in value.split(":", maxsplit=1)]
    except Exception as error:
        raise argparse.ArgumentTypeError("combo must be BUDGET:SEED") from error
    if budget not in BUDGETS or seed not in SEEDS:
        raise argparse.ArgumentTypeError("combo uses an unsupported budget or seed")
    return budget, seed


def run(args: argparse.Namespace) -> None:
    root = Path(__file__).resolve().parents[1]
    protocol_path = Path(args.protocol)
    if sha256_file(protocol_path) != args.expected_protocol_sha256:
        raise ValueError("protocol SHA256 mismatch")
    protocol = json.loads(protocol_path.read_text())
    if protocol.get("status") != "frozen_gtex_k8_adapter_scale_protocol":
        raise ValueError("protocol is not frozen")
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    if commit != args.code_commit:
        raise ValueError("deployed commit differs from requested commit")
    if subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=root,
        text=True,
    ).strip():
        raise ValueError("deployed tracked worktree is dirty")
    inputs = {
        "expression": (Path(args.expression_parquet), protocol["inputs"]["expression_sha256"]),
        "expression_metadata": (
            Path(args.expression_metadata),
            protocol["inputs"]["expression_metadata_sha256"],
        ),
        "manifest": (Path(args.manifest), protocol["inputs"]["scale_manifest_sha256"]),
        "manifest_report": (
            Path(args.manifest_report),
            protocol["inputs"]["scale_manifest_report_sha256"],
        ),
        "axis_definitions": (
            Path(args.axis_definitions),
            protocol["inputs"]["axis_definitions_sha256"],
        ),
    }
    for name, (path, expected) in inputs.items():
        if not path.is_file() or sha256_file(path) != expected:
            raise ValueError(f"{name} is absent or changed")
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    status_path = output_root / "SCALE_STATUS"
    combinations = args.combo or [(budget, seed) for budget in BUDGETS for seed in SEEDS]
    if len(set(combinations)) != len(combinations):
        raise ValueError("assigned combinations are duplicated")
    update_budget = 2 if args.smoke_only else int(protocol["model"]["axis_update_budget"])
    organ_exposures = 2 if args.smoke_only else int(
        protocol["model"]["organ_target_exposures_per_expert"]
    )
    pooled_exposures = 16 if args.smoke_only else int(
        protocol["model"]["pooled_adapter_total_target_exposures"]
    )
    for index, (budget, seed) in enumerate(combinations, start=1):
        seed_root = output_root / f"b{budget}" / f"seed{seed}"
        bank_root = seed_root / "banks"
        if (bank_root / "COMPLETE").exists():
            metadata = json.loads((bank_root / "run_metadata.json").read_text())
            if metadata.get("status") != "complete":
                raise ValueError(f"completed marker has invalid metadata: {bank_root}")
            continue
        if bank_root.exists():
            raise FileExistsError(f"incomplete output already exists: {bank_root}")
        seed_root.mkdir(parents=True, exist_ok=True)
        _atomic_status(
            status_path,
            f"RUNNING combo={index}/{len(combinations)} budget={budget} seed={seed}",
        )
        pooled_checkpoint = Path(args.training_root) / f"seed{seed}" / "pooled" / "best_model.pt"
        expected_checkpoint = protocol["model"]["pooled_trunk_checkpoint_sha256_by_seed"][str(seed)]
        if not pooled_checkpoint.is_file() or sha256_file(pooled_checkpoint) != expected_checkpoint:
            raise ValueError(f"pooled checkpoint changed for seed {seed}")
        command = [
            args.python_bin,
            str(root / "core" / "train_fixed_partition_banks.py"),
            "--expression-parquet", str(inputs["expression"][0]),
            "--expression-metadata", str(inputs["expression_metadata"][0]),
            "--manifest", str(inputs["manifest"][0]),
            "--pooled-checkpoint", str(pooled_checkpoint),
            "--protocol", str(protocol_path),
            "--partition-manifest", str(inputs["manifest"][0]),
            "--partition-report", str(inputs["manifest_report"][0]),
            "--axis-definitions", str(inputs["axis_definitions"][0]),
            "--axis", "organ_k8",
            "--axis", "pooled_adapter",
            "--axis-update-budget", f"organ_k8={update_budget}",
            "--axis-update-budget", f"pooled_adapter={update_budget}",
            "--axis-target-exposures", f"organ_k8={organ_exposures}",
            "--axis-target-exposures", f"pooled_adapter={pooled_exposures}",
            "--axis-expert-key", "organ_k8=" + ",".join(f"organ:{organ}" for organ in ORGANS),
            "--require-calibration-coverage",
            "--sampling-mode", "organ_sample_balanced",
            "--output-dir", str(bank_root),
            "--research-stage", "gtex_k8_adapter_scale_development",
            "--experiment", f"gtex_k8_adapter_scale_b{budget}",
            "--bank-experiment", "gtex_k8_scale_residual_bank",
            "--seed", str(seed),
            "--code-commit", commit,
            "--train-split", "train",
            "--validation-split", "calibration",
            "--train-filter-column", f"scale_b{budget}",
            "--adapter-dim", "64",
            "--exposures-per-expert", "1500",
            "--maximum-exposure-fractional-deviation", "0.05",
            "--max-updates", str(update_budget),
            "--batch-size", "8",
            "--validation-batch-size", "8",
            "--mask-ratio", "0.30",
            "--mask-token", "-10.0",
            "--learning-rate", "0.001",
            "--weight-decay", "0.01",
            "--crossfit-folds", "5",
            "--crossfit-seed", "8675309",
            "--log-interval", "100",
            "--device", "cuda",
            "--num-workers", "0",
            "--use-amp",
        ]
        if args.smoke_only:
            command.append("--smoke-only")
        log_path = seed_root / "banks.log"
        with log_path.open("wb") as log:
            subprocess.run(command, cwd=root, stdout=log, stderr=subprocess.STDOUT, check=True)
        metadata = json.loads((bank_root / "run_metadata.json").read_text())
        if metadata.get("status") != "complete" or int(metadata.get("training_seed", -1)) != seed:
            raise ValueError(f"invalid completed metadata for budget {budget}, seed {seed}")
        for axis in ("organ_k8", "pooled_adapter"):
            axis_metadata = json.loads((bank_root / "banks" / axis / "run_metadata.json").read_text())
            if (
                axis_metadata.get("status") != "complete"
                or int(axis_metadata.get("final_update", -1)) != update_budget
                or axis_metadata.get("test_accessed") is not False
                or axis_metadata.get("external_data_accessed") is not False
            ):
                raise ValueError(f"invalid {axis} metadata for budget {budget}, seed {seed}")
        (seed_root / "COMBINATION_COMPLETE").write_text("COMPLETE\n")
    _atomic_status(status_path, f"COMPLETE combinations={len(combinations)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--expression-parquet", required=True)
    parser.add_argument("--expression-metadata", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--manifest-report", required=True)
    parser.add_argument("--axis-definitions", required=True)
    parser.add_argument("--training-root", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--combo", action="append", type=_parse_combo)
    parser.add_argument("--smoke-only", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
