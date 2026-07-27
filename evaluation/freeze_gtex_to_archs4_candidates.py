#!/usr/bin/env python3
"""Freeze the completed GTEx-only K8 candidate family without reading ARCHS4.

The ledger binds all three prespecified training seeds, every required pooled/organ/
random/control checkpoint, and the already-fit target-hidden router to the verified
training checksum manifest.  It is deliberately expression-blind: ARCHS4 paths are
not accepted and no efficacy metric is read or generated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path


SEEDS = (17, 42, 101)
AXES = (
    "organ_k8",
    "random_k8_p17",
    "random_k8_p42",
    "random_k8_p101",
    "pooled_adapter",
)
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


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _read_checksum_manifest(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            digest, raw_name = line.split(None, 1)
        except ValueError as error:
            raise ValueError(
                f"invalid checksum line {line_number}: {line!r}"
            ) from error
        name = raw_name.strip()
        if name.startswith("*"):
            name = name[1:]
        if name.startswith("./"):
            name = name[2:]
        if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ValueError(f"invalid SHA256 on checksum line {line_number}")
        if name in entries:
            raise ValueError(f"checksum manifest repeats {name!r}")
        entries[name] = digest
    if not entries:
        raise ValueError("checksum manifest is empty")
    return entries


def _verified_artifact(
    root: Path,
    entries: dict[str, str],
    relative: str,
) -> dict[str, str | int]:
    path = root / relative
    if not path.is_file():
        raise FileNotFoundError(path)
    expected = entries.get(relative)
    if expected is None:
        raise ValueError(f"training checksum manifest omits {relative}")
    observed = sha256_file(path)
    if observed != expected:
        raise ValueError(f"training artifact checksum mismatch: {relative}")
    return {
        "path": relative,
        "sha256": observed,
        "size_bytes": int(path.stat().st_size),
    }


def freeze_candidates(args: argparse.Namespace) -> dict:
    root = Path(args.training_root)
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(output)
    if re.fullmatch(r"[0-9a-f]{40}", args.code_commit) is None:
        raise ValueError("candidate freeze requires a full code commit")
    for marker in ("TRAINING_COMPLETE", "FULL_SHA256SUMS", "CODE_COMMIT", "PROTOCOL_SHA256"):
        if not (root / marker).is_file():
            raise FileNotFoundError(root / marker)
    if not (root / "TRAINING_STATUS").read_text().startswith("COMPLETE "):
        raise ValueError("training status is not complete")
    training_commit = (root / "CODE_COMMIT").read_text().strip()
    if training_commit != args.expected_training_commit:
        raise ValueError("training commit differs from frozen expectation")
    protocol_sha256 = (root / "PROTOCOL_SHA256").read_text().strip()
    if protocol_sha256 != args.expected_training_protocol_sha256:
        raise ValueError("training protocol differs from frozen expectation")

    checksum_path = root / "FULL_SHA256SUMS"
    if sha256_file(checksum_path) != args.expected_checksum_manifest_sha256:
        raise ValueError("training checksum-manifest hash mismatch")
    entries = _read_checksum_manifest(checksum_path)

    seed_ledgers = []
    for seed in SEEDS:
        pooled_relative = f"seed{seed}/pooled/best_model.pt"
        pooled_metadata_relative = f"seed{seed}/pooled/run_metadata.json"
        pooled = _verified_artifact(root, entries, pooled_relative)
        pooled_metadata_artifact = _verified_artifact(
            root, entries, pooled_metadata_relative
        )
        pooled_metadata = json.loads((root / pooled_metadata_relative).read_text())
        if pooled_metadata.get("status") != "complete":
            raise ValueError(f"seed {seed} pooled run is not complete")
        if int(pooled_metadata.get("seed", pooled_metadata.get("training", {}).get("seed", -1))) != seed:
            raise ValueError(f"seed {seed} pooled metadata seed mismatch")
        if pooled_metadata.get("hashes", {}).get("best_checkpoint_sha256") not in (
            None,
            pooled["sha256"],
        ):
            raise ValueError(f"seed {seed} pooled checkpoint metadata mismatch")

        banks = {}
        for axis in AXES:
            base = f"seed{seed}/banks/banks/{axis}"
            checkpoint = _verified_artifact(
                root, entries, f"{base}/final_experts.pt"
            )
            metadata_artifact = _verified_artifact(
                root, entries, f"{base}/run_metadata.json"
            )
            metadata = json.loads((root / f"{base}/run_metadata.json").read_text())
            if metadata.get("status") != "complete":
                raise ValueError(f"seed {seed} axis {axis} is not complete")
            if metadata.get("config", {}).get("axis") != axis:
                raise ValueError(f"seed {seed} axis metadata mismatch for {axis}")
            if int(metadata.get("training_seed", -1)) != seed:
                raise ValueError(f"seed {seed} bank seed mismatch for {axis}")
            if metadata.get("artifacts", {}).get(
                "final_experts_sha256"
            ) != checkpoint["sha256"]:
                raise ValueError(f"seed {seed} bank checkpoint mismatch for {axis}")
            if metadata.get("hashes", {}).get(
                "pooled_checkpoint_sha256"
            ) != pooled["sha256"]:
                raise ValueError(f"seed {seed} bank pooled binding mismatch for {axis}")
            if axis == "organ_k8" and metadata.get("config", {}).get(
                "expert_initialization_keys"
            ) != [f"organ:{organ}" for organ in ORGANS]:
                raise ValueError("organ K8 expert order differs from frozen organ order")
            banks[axis] = {
                "checkpoint": checkpoint,
                "metadata": metadata_artifact,
                "expert_order": metadata.get("config", {}).get(
                    "expert_initialization_keys"
                ),
                "final_update": metadata.get("config", {}).get("final_update"),
            }
        seed_ledgers.append({
            "seed": seed,
            "pooled": {
                "checkpoint": pooled,
                "metadata": pooled_metadata_artifact,
            },
            "banks": banks,
        })

    router = {
        "artifact": _verified_artifact(
            root, entries, "router/gtex_k8_target_hidden_router.npz"
        ),
        "report": _verified_artifact(
            root, entries, "router/router_report.json"
        ),
    }
    router_report = json.loads((root / router["report"]["path"]).read_text())
    if (
        router_report.get("status") != "complete"
        or router_report.get("archs4_expression_accessed") is not False
        or router_report.get("performance_metrics_generated") is not False
        or router_report.get("classes") != list(ORGANS)
    ):
        raise ValueError("router report violates the frozen pre-test contract")
    if router_report.get("hashes", {}).get(
        "router_artifact_sha256"
    ) != router["artifact"]["sha256"]:
        raise ValueError("router artifact differs from router report")

    ledger = {
        "schema_version": 1,
        "status": "frozen_gtex_only_k8_candidate_ledger",
        "code_commit": args.code_commit,
        "training_commit": training_commit,
        "training_protocol_sha256": protocol_sha256,
        "training_checksum_manifest_sha256": sha256_file(checksum_path),
        "training_root_role": "verified_completed_bundle",
        "training_root_path_is_runtime_config": True,
        "seeds": list(SEEDS),
        "best_seed_selection_allowed": False,
        "organs": list(ORGANS),
        "axes": list(AXES),
        "archs4_expression_accessed": False,
        "archs4_efficacy_scored": False,
        "fine_tuning_exposure": "zero",
        "seed_candidates": seed_ledgers,
        "router": router,
        "next_gate": (
            "Bind this ledger hash into the exact ARCHS4 lockbox membership, "
            "extractor, scorer, evaluator, and one-time launcher."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, output)
    return ledger


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training-root", required=True)
    parser.add_argument("--expected-training-commit", required=True)
    parser.add_argument("--expected-training-protocol-sha256", required=True)
    parser.add_argument("--expected-checksum-manifest-sha256", required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--output", required=True)
    print(json.dumps(freeze_candidates(parser.parse_args()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
