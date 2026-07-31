#!/usr/bin/env python3
"""Build an immutable portable package from the exact validated K8 checkpoints."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import torch


SEEDS = (17, 42, 101)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _verify_source(root: Path, descriptor: dict, label: str) -> Path:
    path = root / descriptor["path"]
    if not path.is_file():
        raise FileNotFoundError(path)
    if sha256_file(path) != descriptor["sha256"]:
        raise ValueError(f"{label} SHA256 mismatch")
    if path.stat().st_size != int(descriptor["size_bytes"]):
        raise ValueError(f"{label} size mismatch")
    return path


def _checkpoint_health(path: Path, *, seed: int, kind: str) -> dict:
    value = torch.load(path, map_location="cpu", weights_only=False)
    if kind == "pooled":
        tensors = value.get("model_state_dict")
        config = value.get("config", {})
        if not isinstance(tensors, dict) or int(config.get("hidden_dim", -1)) != 768:
            raise ValueError(f"invalid pooled checkpoint for seed {seed}")
    else:
        tensors = value.get("expert_state_dict")
        if (
            not isinstance(tensors, dict)
            or value.get("axis") != "organ_k8"
            or int(value.get("training_seed", -1)) != seed
        ):
            raise ValueError(f"invalid organ bank checkpoint for seed {seed}")
    if not tensors or not all(torch.isfinite(tensor).all().item() for tensor in tensors.values()):
        raise ValueError(f"nonfinite tensors in {kind} checkpoint for seed {seed}")
    return {"tensor_count": len(tensors), "all_tensors_finite": True}


def build_package(
    *,
    protocol_path: Path,
    expected_protocol_sha256: str,
    ledger_path: Path,
    training_root: Path,
    output_dir: Path,
    code_commit: str,
) -> dict:
    if sha256_file(protocol_path) != expected_protocol_sha256:
        raise ValueError("package protocol SHA256 mismatch")
    protocol = json.loads(protocol_path.read_text())
    if protocol.get("status") != "frozen_before_final_k8_package_execution":
        raise ValueError("package protocol is not frozen")
    if protocol["source"]["candidate_ledger_sha256"] != sha256_file(ledger_path):
        raise ValueError("candidate ledger SHA256 mismatch")
    if tuple(protocol["architecture"]["seeds"]) != SEEDS:
        raise ValueError("seed family changed")
    if output_dir.exists():
        raise FileExistsError(output_dir)
    output_dir.mkdir(parents=True)
    ledger = json.loads(ledger_path.read_text())
    entries = {int(item["seed"]): item for item in ledger["seed_candidates"]}
    copied = []

    def copy_artifact(source: Path, relative: Path, role: str, source_relative: str) -> Path:
        destination = output_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        if sha256_file(destination) != sha256_file(source):
            raise RuntimeError(f"copy hash mismatch: {relative}")
        copied.append(
            {
                "path": str(relative),
                "role": role,
                "source_path": source_relative,
                "sha256": sha256_file(destination),
                "size_bytes": destination.stat().st_size,
            }
        )
        return destination

    health = {}
    for seed in SEEDS:
        entry = entries[seed]
        seed_dir = Path(f"seed{seed}")
        pooled_descriptor = entry["pooled"]["checkpoint"]
        pooled_source = _verify_source(training_root, pooled_descriptor, f"seed{seed} pooled")
        pooled_copy = copy_artifact(
            pooled_source,
            seed_dir / "pooled_checkpoint.pt",
            "pooled_checkpoint",
            pooled_descriptor["path"],
        )
        pooled_metadata = entry["pooled"]["metadata"]
        copy_artifact(
            _verify_source(training_root, pooled_metadata, f"seed{seed} pooled metadata"),
            seed_dir / "pooled_metadata.json",
            "pooled_metadata",
            pooled_metadata["path"],
        )
        bank_descriptor = entry["banks"]["organ_k8"]["checkpoint"]
        bank_copy = copy_artifact(
            _verify_source(training_root, bank_descriptor, f"seed{seed} organ bank"),
            seed_dir / "organ_k8_checkpoint.pt",
            "organ_k8_checkpoint",
            bank_descriptor["path"],
        )
        bank_metadata = entry["banks"]["organ_k8"]["metadata"]
        copy_artifact(
            _verify_source(training_root, bank_metadata, f"seed{seed} organ metadata"),
            seed_dir / "organ_k8_metadata.json",
            "organ_k8_metadata",
            bank_metadata["path"],
        )
        health[str(seed)] = {
            "pooled": _checkpoint_health(pooled_copy, seed=seed, kind="pooled"),
            "organ_k8": _checkpoint_health(bank_copy, seed=seed, kind="organ_k8"),
        }

    for key, filename, role in (
        ("artifact", "gtex_k8_target_hidden_router.npz", "target_hidden_router"),
        ("report", "router_report.json", "router_report"),
    ):
        descriptor = ledger["router"][key]
        copy_artifact(
            _verify_source(training_root, descriptor, role),
            Path("router") / filename,
            role,
            descriptor["path"],
        )
    copy_artifact(ledger_path, Path("provenance/candidate_ledger.json"), "candidate_ledger", str(ledger_path))
    copy_artifact(protocol_path, Path("provenance/package_protocol.json"), "package_protocol", str(protocol_path))

    output_contract_path = output_dir / "output_contract.json"
    output_contract_path.write_text(
        json.dumps(protocol["output_contract"], indent=2, sort_keys=True) + "\n"
    )
    copied.append(
        {
            "path": "output_contract.json",
            "role": "output_contract",
            "source_path": "frozen package protocol",
            "sha256": sha256_file(output_contract_path),
            "size_bytes": output_contract_path.stat().st_size,
        }
    )
    manifest = {
        "schema_version": 1,
        "status": "complete",
        "role": protocol["role"],
        "code_commit": code_commit,
        "protocol_sha256": expected_protocol_sha256,
        "candidate_ledger_sha256": sha256_file(ledger_path),
        "seeds": list(SEEDS),
        "files": sorted(copied, key=lambda item: item["path"]),
        "checkpoint_health": health,
        "weights_updated": False,
        "training_performed": False,
        "efficacy_scoring_performed": False,
        "archs4_expression_accessed": False,
        "osdr_accessed": False,
        "best_seed_selection": False,
    }
    manifest_path = output_dir / "package_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    files = sorted(
        path for path in output_dir.rglob("*") if path.is_file() and path.name not in {"FULL_SHA256SUMS", "PACKAGE_COMPLETE"}
    )
    sums = output_dir / "FULL_SHA256SUMS"
    sums.write_text(
        "".join(f"{sha256_file(path)}  {path.relative_to(output_dir)}\n" for path in files)
    )
    (output_dir / "PACKAGE_COMPLETE").write_text("complete\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--candidate-ledger", required=True, type=Path)
    parser.add_argument("--training-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--code-commit", required=True)
    args = parser.parse_args()
    result = build_package(
        protocol_path=args.protocol,
        expected_protocol_sha256=args.expected_protocol_sha256,
        ledger_path=args.candidate_ledger,
        training_root=args.training_root,
        output_dir=args.output_dir,
        code_commit=args.code_commit,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
