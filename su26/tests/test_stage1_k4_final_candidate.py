from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))
sys.path.insert(0, str(ROOT / "evaluation"))

from freeze_stage1_k4_final_candidate import (  # noqa: E402
    AXES,
    EXPECTED_PROTOCOL_SHA256,
    validate_portable_candidate,
)
from train_manifest import sha256_file  # noqa: E402


COMMIT = "abcdef1234567890abcdef1234567890abcdef12"


def _write(path: Path, value: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)
    return sha256_file(path)


def _portable_fixture(root: Path) -> Path:
    artifacts: dict[str, object] = {"path_policy": "relative"}
    hashes: dict[str, str] = {}
    ordinary = {
        "protocol": "bundle/protocol.json",
        "partition_manifest": "bundle/partitions/manifest.parquet",
        "partition_report": "bundle/partitions/report.json",
        "random_mappings": "bundle/random_mappings.json",
        "router_artifact": "bundle/router/router.npz",
        "router_report": "bundle/router/report.json",
        "pooled_checkpoint": "bundle/pooled.pt",
        "axis_definitions": "bundle/axis.npz",
        "k45_evaluation_report": "bundle/k45.json",
    }
    for key, relative in ordinary.items():
        artifacts[key] = relative
        hashes[key] = _write(root / relative, key)

    development_root = root / "bundle/development_data"
    development_names = {
        "development_expression": "expression.parquet",
        "development_expression_metadata": "extraction_report.json",
        "development_extracted_manifest": "manifest.parquet",
        "development_firewall_report": "firewall_report.json",
        "development_genes": "genes.txt",
        "development_firewall_marker": "FIREWALL_VERIFIED",
        "development_firewall_log": "firewall_verification.log",
    }
    manifest_lines = []
    for key, filename in development_names.items():
        relative = f"bundle/development_data/{filename}"
        artifacts[key] = relative
        digest = _write(root / relative, key)
        hashes[key] = digest
        manifest_lines.append(f"{digest}  ./{filename}\n")
    checksum_relative = "bundle/development_data/FULL_SHA256SUMS"
    artifacts["development_data_sha256s"] = checksum_relative
    hashes["development_data_sha256s"] = _write(
        root / checksum_relative, "".join(sorted(manifest_lines))
    )

    seed_artifacts = {}
    for seed in (17, 42, 101):
        files = {}
        for filename in (
            "run_metadata.json",
            "fit_exposures.parquet",
            "fit_exposure_report.json",
            "fit_schedule.parquet",
        ):
            relative = f"bundle/seeds/seed{seed}/{filename}"
            files[filename] = {
                "path": relative,
                "sha256": _write(root / relative, f"{seed}/{filename}"),
            }
        banks = {}
        for axis in AXES:
            checkpoint = f"bundle/seeds/seed{seed}/banks/{axis}/final_experts.pt"
            metadata = f"bundle/seeds/seed{seed}/banks/{axis}/run_metadata.json"
            banks[axis] = {
                "checkpoint": checkpoint,
                "checkpoint_sha256": _write(root / checkpoint, f"{seed}/{axis}/ckpt"),
                "metadata": metadata,
                "metadata_sha256": _write(root / metadata, f"{seed}/{axis}/meta"),
            }
        seed_artifacts[str(seed)] = {"files": files, "banks": banks}
    artifacts["seeds"] = seed_artifacts

    manifest = {
        "status": "frozen",
        "code_commit": COMMIT,
        "internal_efficacy_scoring": False,
        "test_accessed": False,
        "external_data_accessed": False,
        "artifacts": artifacts,
        "hashes": {
            "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
            "portable_bundle_files": hashes,
        },
    }
    path = root / "candidate_manifest.json"
    path.write_text(json.dumps(manifest))
    return path


def test_portable_candidate_validates_development_and_schedule_files(tmp_path):
    manifest = _portable_fixture(tmp_path)
    assert validate_portable_candidate(manifest, expected_code_commit=COMMIT)[
        "status"
    ] == "frozen"

    schedule = (
        tmp_path / "bundle/seeds/seed17/fit_schedule.parquet"
    )
    schedule.write_text("tampered")
    with pytest.raises(ValueError, match="candidate seed file hash failed"):
        validate_portable_candidate(manifest, expected_code_commit=COMMIT)
