#!/usr/bin/env python3
"""Validate and freeze the complete Stage-1 K4 final-refit candidate bundle."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = ROOT / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from train_manifest import sha256_file, sha256_json  # noqa: E402


SEEDS = (17, 42, 101)
AXES = (
    "organ_k4_final",
    "random_group_k4_final_p17",
    "random_group_k4_final_p42",
    "random_group_k4_final_p101",
    "pooled_adapter",
)
EXPERT_KEYS = {
    "organ_k4_final": [
        "organ:brain",
        "organ:liver",
        "organ:skeletal_muscle",
        "organ:skin",
    ],
    "random_group_k4_final_p17": [f"random:k4:p17:{index}" for index in range(4)],
    "random_group_k4_final_p42": [f"random:k4:p42:{index}" for index in range(4)],
    "random_group_k4_final_p101": [
        f"random:k4:p101:{index}" for index in range(4)
    ],
    "pooled_adapter": ["control:pooled_residual"],
}
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
CHECKSUM_LINE_PATTERN = re.compile(r"^([0-9a-f]{64})  (.+)$")
EXPECTED_PROTOCOL_SHA256 = (
    "718f4a876ba641e53aaff3ad75db8c70c727db0a086477b13c17487672cbb85b"
)


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _copy_verified(source: Path, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    shutil.copyfile(source, temporary)
    source_hash = sha256_file(source)
    if sha256_file(temporary) != source_hash:
        raise IOError(f"candidate bundle copy verification failed: {source}")
    os.replace(temporary, destination)
    return source_hash


def _read_checksum_manifest(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in path.read_text().splitlines():
        match = CHECKSUM_LINE_PATTERN.fullmatch(line)
        if match is None:
            raise ValueError(f"invalid checksum-manifest line: {line!r}")
        digest, raw_name = match.groups()
        relative = Path(raw_name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"unsafe checksum-manifest path: {raw_name!r}")
        normalized = str(relative)
        if normalized in entries:
            raise ValueError(f"duplicate checksum-manifest path: {raw_name!r}")
        entries[normalized] = digest
    if not entries:
        raise ValueError("development-data checksum manifest is empty")
    return entries


def validate_portable_candidate(
    manifest_path: str | Path, *, expected_code_commit: str
) -> dict[str, Any]:
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text())
    if (
        manifest.get("status") != "frozen"
        or manifest.get("code_commit") != expected_code_commit
        or manifest.get("internal_efficacy_scoring") is not False
        or manifest.get("test_accessed") is not False
        or manifest.get("external_data_accessed") is not False
        or manifest.get("hashes", {}).get("protocol_sha256")
        != EXPECTED_PROTOCOL_SHA256
    ):
        raise ValueError("candidate manifest header violates the frozen contract")
    root = manifest_path.parent
    artifacts = manifest.get("artifacts", {})
    portable_hashes = manifest.get("hashes", {}).get("portable_bundle_files", {})
    path_keys = {
        "protocol": "protocol",
        "partition_manifest": "partition_manifest",
        "partition_report": "partition_report",
        "random_mappings": "random_mappings",
        "router_artifact": "router_artifact",
        "router_report": "router_report",
        "pooled_checkpoint": "pooled_checkpoint",
        "axis_definitions": "axis_definitions",
        "k45_evaluation_report": "k45_evaluation_report",
        "development_expression": "development_expression",
        "development_expression_metadata": "development_expression_metadata",
        "development_extracted_manifest": "development_extracted_manifest",
        "development_firewall_report": "development_firewall_report",
        "development_data_sha256s": "development_data_sha256s",
        "development_genes": "development_genes",
        "development_firewall_marker": "development_firewall_marker",
        "development_firewall_log": "development_firewall_log",
    }
    if set(portable_hashes) != set(path_keys):
        raise ValueError("candidate portable file hash family is incomplete")
    for hash_key, artifact_key in path_keys.items():
        relative = Path(artifacts.get(artifact_key, ""))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"candidate path is not safely relative: {artifact_key}")
        path = root / relative
        if not path.is_file() or sha256_file(path) != portable_hashes[hash_key]:
            raise ValueError(f"candidate portable artifact hash failed: {artifact_key}")
    checksum_path = root / Path(artifacts["development_data_sha256s"])
    development_entries = _read_checksum_manifest(checksum_path)
    development_root = checksum_path.parent
    for relative, digest in development_entries.items():
        path = development_root / relative
        if not path.is_file() or sha256_file(path) != digest:
            raise ValueError(
                f"portable development-data checksum failed: {relative}"
            )
    seeds = artifacts.get("seeds", {})
    if set(seeds) != {"17", "42", "101"}:
        raise ValueError("candidate portable seed family is incomplete")
    for seed, seed_value in seeds.items():
        seed_files = seed_value.get("files", {})
        if set(seed_files) != {
            "run_metadata.json",
            "fit_exposures.parquet",
            "fit_exposure_report.json",
            "fit_schedule.parquet",
        }:
            raise ValueError(f"candidate seed {seed} file family is incomplete")
        for filename, item in seed_files.items():
            relative = Path(item.get("path", ""))
            path = root / relative
            if (
                relative.is_absolute()
                or ".." in relative.parts
                or not path.is_file()
                or sha256_file(path) != item.get("sha256")
            ):
                raise ValueError(f"candidate seed file hash failed: {seed}/{filename}")
        banks = seed_value.get("banks", {})
        if set(banks) != set(AXES):
            raise ValueError(f"candidate seed {seed} bank family is incomplete")
        for axis, item in banks.items():
            for path_key, hash_key in (
                ("checkpoint", "checkpoint_sha256"),
                ("metadata", "metadata_sha256"),
            ):
                relative = Path(item.get(path_key, ""))
                path = root / relative
                if (
                    relative.is_absolute()
                    or ".." in relative.parts
                    or not path.is_file()
                    or sha256_file(path) != item.get(hash_key)
                ):
                    raise ValueError(
                        f"candidate bank hash failed: {seed}/{axis}/{path_key}"
                    )
    return manifest


def _parse_seed_roots(values: list[str]) -> dict[int, Path]:
    result: dict[int, Path] = {}
    for raw in values:
        if "=" not in raw:
            raise ValueError("seed-root must use SEED=PATH")
        seed_text, path_text = raw.split("=", 1)
        seed = int(seed_text)
        if seed in result:
            raise ValueError(f"duplicate seed root {seed}")
        result[seed] = Path(path_text)
    if tuple(sorted(result)) != SEEDS:
        raise ValueError(f"seed roots must cover exactly {SEEDS}")
    return result


def freeze(args: argparse.Namespace) -> dict[str, Any]:
    paths = {
        "protocol": Path(args.protocol),
        "partition_manifest": Path(args.partition_manifest),
        "partition_report": Path(args.partition_report),
        "random_mappings": Path(args.random_mappings),
        "router_artifact": Path(args.router_artifact),
        "router_report": Path(args.router_report),
        "pooled_checkpoint": Path(args.pooled_checkpoint),
        "k45_evaluation_report": Path(args.k45_evaluation_report),
        "axis_definitions": Path(args.axis_definitions),
        "development_expression": Path(args.development_expression),
        "development_expression_metadata": Path(
            args.development_expression_metadata
        ),
        "development_extracted_manifest": Path(
            args.development_extracted_manifest
        ),
        "development_firewall_report": Path(args.development_firewall_report),
        "development_data_sha256s": Path(args.development_data_sha256s),
    }
    for path in paths.values():
        if not path.is_file():
            raise FileNotFoundError(path)
    if COMMIT_PATTERN.fullmatch(args.code_commit) is None:
        raise ValueError("code commit must be a hexadecimal Git commit")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output_dir}")

    protocol = json.loads(paths["protocol"].read_text())
    protocol_hash = sha256_file(paths["protocol"])
    if protocol_hash != EXPECTED_PROTOCOL_SHA256:
        raise ValueError("final protocol hash differs from the frozen release")
    if (
        protocol.get("prior_evidence", {}).get("decision_branch") != "k4_robust"
        or protocol.get("prior_evidence", {}).get("selected_candidate") != "k4_epe"
        or protocol.get("firewall", {}).get("test_access_allowed") is not False
        or protocol.get("firewall", {}).get("external_access_allowed_during_refit")
        is not False
    ):
        raise ValueError("final protocol does not freeze the K4-EPE refit firewall")
    data = protocol["data"]
    if sha256_file(paths["pooled_checkpoint"]) != data["pooled_checkpoint_sha256"]:
        raise ValueError("pooled checkpoint differs from final protocol")
    if sha256_file(paths["axis_definitions"]) != data["axis_definitions_sha256"]:
        raise ValueError("axis definitions differ from final protocol")
    if sha256_file(paths["k45_evaluation_report"]) != protocol["prior_evidence"][
        "k45_evaluation_report_sha256"
    ]:
        raise ValueError("K45 decision evidence differs from final protocol")
    development_hash_contract = {
        "development_expression": "development_expression_parquet_sha256",
        "development_expression_metadata": "development_expression_metadata_sha256",
        "development_extracted_manifest": "development_extracted_manifest_sha256",
        "development_firewall_report": "development_firewall_report_sha256",
        "development_data_sha256s": "development_data_full_sha256s_sha256",
    }
    for path_key, protocol_key in development_hash_contract.items():
        if sha256_file(paths[path_key]) != data[protocol_key]:
            raise ValueError(f"{path_key} differs from the frozen protocol")
    development_root = paths["development_data_sha256s"].parent
    development_entries = _read_checksum_manifest(paths["development_data_sha256s"])
    expected_development_entries = {
        "FIREWALL_VERIFIED",
        "expression.parquet",
        "extraction_report.json",
        "firewall_report.json",
        "firewall_verification.log",
        "genes.txt",
        "manifest.parquet",
    }
    if set(development_entries) != expected_development_entries:
        raise ValueError("development-data checksum file family changed")
    for relative, digest in development_entries.items():
        source = development_root / relative
        if not source.is_file() or source.is_symlink() or sha256_file(source) != digest:
            raise ValueError(f"development-data checksum failed: {relative}")
    if sha256_file(development_root / "genes.txt") != data[
        "development_gene_list_sha256"
    ]:
        raise ValueError("development gene list differs from the frozen protocol")
    firewall_report = json.loads(paths["development_firewall_report"].read_text())
    if (
        firewall_report.get("status") != "complete"
        or firewall_report.get("runtime_authorized_for_final_refit") is not True
        or firewall_report.get("test_rows_present") is not False
        or firewall_report.get("test_expression_available_to_runtime") is not False
        or firewall_report.get("test_targets_or_scores_accessed") is not False
        or firewall_report.get("hashes", {}).get(
            "development_expression_sha256"
        )
        != sha256_file(paths["development_expression"])
    ):
        raise ValueError("development-data firewall report is invalid")

    partition_report = json.loads(paths["partition_report"].read_text())
    if (
        partition_report.get("status") != "complete"
        or partition_report.get("internal_efficacy_scoring") is not False
        or partition_report.get("test_accessed") is not False
        or partition_report.get("hashes", {}).get("protocol_sha256") != protocol_hash
        or partition_report.get("hashes", {}).get("partition_manifest_sha256")
        != sha256_file(paths["partition_manifest"])
        or sha256_file(paths["partition_manifest"])
        != data["development_fit_manifest_sha256"]
    ):
        raise ValueError("final partition artifacts violate their frozen contract")

    mapping_report = json.loads(paths["random_mappings"].read_text())
    k45_report = json.loads(paths["k45_evaluation_report"].read_text())
    if (
        mapping_report.get("status") != "complete"
        or mapping_report.get("candidate_selection") is not False
        or mapping_report.get("test_accessed") is not False
        or mapping_report.get("external_data_accessed") is not False
        or mapping_report.get("hashes", {}).get("protocol_sha256") != protocol_hash
        or set(mapping_report.get("mappings", {})) != {"17", "42", "101"}
    ):
        raise ValueError("random-control mappings violate their frozen contract")
    if mapping_report.get("hashes", {}).get(
        "k45_evaluation_report_sha256"
    ) != sha256_file(paths["k45_evaluation_report"]):
        raise ValueError("random mappings do not bind the K45 decision report")
    for partition_seed in (17, 42, 101):
        key = str(partition_seed)
        source_axis = f"random_group_k4_epe_p{partition_seed}"
        final_axis = f"random_group_k4_final_p{partition_seed}"
        item = mapping_report["mappings"].get(key, {})
        organ_map = item.get("organ_to_expert", {})
        score_table = item.get("equal_study_mse_by_organ_and_expert", {})
        if (
            item.get("source_axis") != source_axis
            or item.get("final_axis") != final_axis
            or set(organ_map) != {
                "adipose",
                "brain",
                "liver",
                "skeletal_muscle",
                "skin",
            }
            or organ_map.get("adipose") != -1
            or any(
                organ_map.get(organ) not in {0, 1, 2, 3}
                for organ in ("brain", "liver", "skeletal_muscle", "skin")
            )
            or any(
                not isinstance(score_table.get(organ), list)
                or len(score_table[organ]) != 4
                or organ_map.get(organ)
                != min(
                    range(4),
                    key=lambda index: (score_table[organ][index], index),
                )
                for organ in ("brain", "liver", "skeletal_muscle", "skin")
            )
        ):
            raise ValueError(f"random mapping schema failed for partition {key}")
        source_hashes = mapping_report["hashes"].get("sources", {}).get(key, {})
        for model_seed in SEEDS:
            provenance = (
                k45_report.get("bank_provenance", {})
                .get(source_axis, {})
                .get(str(model_seed), {})
            )
            if (
                source_hashes.get(f"seed{model_seed}_metadata_sha256")
                != provenance.get("metadata_sha256")
                or source_hashes.get(f"seed{model_seed}_scores_sha256")
                != provenance.get("calibration_scores_sha256")
                or source_hashes.get(f"seed{model_seed}_checkpoint_sha256")
                != provenance.get("final_experts_sha256")
            ):
                raise ValueError(
                    f"random mapping provenance failed: partition={key} seed={model_seed}"
                )

    router_report = json.loads(paths["router_report"].read_text())
    router_config = router_report.get("config", {})
    frozen_router = protocol.get("router", {})
    if (
        router_report.get("status") != "complete"
        or router_report.get("internal_efficacy_scoring") is not False
        or router_report.get("performance_metrics_generated") is not False
        or router_report.get("test_accessed") is not False
        or router_report.get("external_data_accessed") is not False
        or router_report.get("hashes", {}).get("protocol_sha256") != protocol_hash
        or router_report.get("hashes", {}).get("router_artifact_sha256")
        != sha256_file(paths["router_artifact"])
        or router_report.get("hashes", {}).get("partition_manifest_sha256")
        != sha256_file(paths["partition_manifest"])
        or router_report.get("hashes", {}).get("source_manifest_sha256")
        != sha256_file(paths["partition_manifest"])
        or router_report.get("hashes", {}).get("expression_parquet_sha256")
        != data["development_expression_parquet_sha256"]
        or router_report.get("hashes", {}).get("expression_metadata_sha256")
        != data["development_expression_metadata_sha256"]
        or router_config.get("router_seed") != frozen_router.get("seed")
        or router_config.get("mask_token") != data.get("mask_token")
        or router_config.get("pipeline") != frozen_router.get("pipeline")
        or router_config.get("logistic_regression", {}).get("C")
        != frozen_router.get("C")
        or router_config.get("logistic_regression", {}).get("solver")
        != frozen_router.get("solver")
        or router_config.get("logistic_regression", {}).get("class_weight")
        != frozen_router.get("class_weight")
        or router_config.get("logistic_regression", {}).get("max_iter")
        != frozen_router.get("max_iter")
        or router_report.get("target_hiding", {}).get("n_score_genes")
        != data.get("score_gene_count")
    ):
        raise ValueError("final router artifacts violate their frozen contract")

    seed_roots = _parse_seed_roots(args.seed_root)
    seed_artifacts: dict[str, Any] = {}
    for seed in SEEDS:
        seed_root = seed_roots[seed]
        metadata_path = seed_root / "run_metadata.json"
        complete_path = seed_root / "COMPLETE"
        for path in (metadata_path, complete_path):
            if not path.exists():
                raise FileNotFoundError(path)
        metadata = json.loads(metadata_path.read_text())
        config = metadata.get("config", {})
        hashes = metadata.get("hashes", {})
        if (
            metadata.get("status") != "complete"
            or metadata.get("training_seed") != seed
            or metadata.get("code_commit") != args.code_commit
            or metadata.get("test_accessed") is not False
            or metadata.get("external_data_accessed") is not False
            or metadata.get("internal_efficacy_scoring") is not False
            or metadata.get("mechanical_only") is not False
            or metadata.get("counts", {}).get("fit") != data["expected_fit_samples"]
            or metadata.get("fit_exposure_summary", {}).get("zero_exposure_samples")
            != 0
            or config.get("axes") != list(AXES)
            or config.get("final_refit") is not True
            or config.get("calibration_evaluation_performed") is not False
            or config.get("sampling_mode") != "organ_sample_balanced"
            or config.get("mask_phase") != "packed_final_refit_banks"
            or config.get("ordered_schedule_rows") != 12000
            or config.get("max_updates") != 1500
            or set(config.get("bank_update_budgets", {}).values()) != {1500}
            or config.get("adapter_dim") != 64
            or config.get("batch_size") != 8
            or config.get("mask_ratio") != 0.3
            or config.get("mask_token") != -10.0
            or config.get("normalization") != "log1p_tpm"
            or config.get("learning_rate") != 0.001
            or config.get("weight_decay") != 0.01
            or config.get("optimizer") != "AdamW"
            or config.get("checkpoint_policy")
            != "predetermined_final_update_per_bank"
            or config.get("scheduler") != "CosineAnnealingLR"
            or config.get("axis_expert_keys") != EXPERT_KEYS
            or config.get("use_amp") is not True
            or config.get("maximum_exposure_fractional_deviation") != 0.05
            or config.get("target_exposures_per_expert")
            != {
                "organ_k4_final": 2400,
                "random_group_k4_final_p17": 2400,
                "random_group_k4_final_p42": 2400,
                "random_group_k4_final_p101": 2400,
                "pooled_adapter": 12000,
            }
            or any(
                float(value) > 0.05
                for value in config.get(
                    "exposure_fractional_deviations", {}
                ).values()
            )
            or config.get("fallback_draw_counts", {}).get("organ_k4_final")
            != 2400
            or config.get("fallback_draw_counts", {}).get(
                "random_group_k4_final_p17"
            )
            != 2400
            or config.get("fallback_draw_counts", {}).get(
                "random_group_k4_final_p42"
            )
            != 2400
            or config.get("fallback_draw_counts", {}).get(
                "random_group_k4_final_p101"
            )
            != 2400
            or config.get("fallback_draw_counts", {}).get("pooled_adapter") != 0
            or hashes.get("protocol_sha256") != protocol_hash
            or hashes.get("pooled_checkpoint_sha256")
            != data["pooled_checkpoint_sha256"]
            or hashes.get("expression_sha256")
            != data["development_expression_parquet_sha256"]
            or hashes.get("expression_metadata_sha256")
            != data["development_expression_metadata_sha256"]
            or hashes.get("manifest_sha256")
            != data["development_fit_manifest_sha256"]
            or hashes.get("partition_manifest_sha256")
            != sha256_file(paths["partition_manifest"])
        ):
            raise ValueError(f"final refit seed {seed} violates its frozen contract")

        exposure_path = seed_root / "fit_exposures.parquet"
        exposure_report_path = seed_root / "fit_exposure_report.json"
        schedule_path = seed_root / "fit_schedule.parquet"
        for path in (exposure_path, exposure_report_path, schedule_path):
            if not path.is_file():
                raise FileNotFoundError(path)
        exposure_report = json.loads(exposure_report_path.read_text())
        if (
            hashes.get("fit_exposures_sha256") != sha256_file(exposure_path)
            or hashes.get("fit_exposure_report_sha256")
            != sha256_file(exposure_report_path)
            or hashes.get("fit_schedule_sha256") != sha256_file(schedule_path)
            or exposure_report.get("artifacts", {}).get("fit_exposures_sha256")
            != sha256_file(exposure_path)
            or exposure_report.get("artifacts", {}).get("fit_schedule_sha256")
            != sha256_file(schedule_path)
            or exposure_report.get("artifacts", {}).get("ordered_schedule_rows")
            != 12000
            or exposure_report.get("test_accessed") is not False
            or exposure_report.get("external_data_accessed") is not False
            or exposure_report.get("internal_efficacy_scoring") is not False
        ):
            raise ValueError(f"final refit schedule ledger failed for seed {seed}")

        banks: dict[str, Any] = {}
        for axis in AXES:
            bank_dir = seed_root / "banks" / axis
            bank_metadata_path = bank_dir / "run_metadata.json"
            checkpoint_path = bank_dir / "final_experts.pt"
            for path in (bank_metadata_path, checkpoint_path, bank_dir / "COMPLETE"):
                if not path.exists():
                    raise FileNotFoundError(path)
            if (bank_dir / "calibration_scores.npz").exists():
                raise ValueError(f"final refit bank emitted forbidden efficacy scores: {axis}")
            bank = json.loads(bank_metadata_path.read_text())
            bank_config = bank.get("config", {})
            expected_experts = 1 if axis == "pooled_adapter" else 4
            expected_exposure = 12000 if axis == "pooled_adapter" else 2400
            if (
                bank.get("status") != "complete"
                or bank.get("axis") != axis
                or bank.get("training_seed") != seed
                or bank.get("code_commit") != args.code_commit
                or bank.get("test_accessed") is not False
                or bank.get("external_data_accessed") is not False
                or bank.get("internal_efficacy_scoring") is not False
                or "calibration_metrics" in bank
                or bank_config.get("num_experts") != expected_experts
                or bank_config.get("adapter_dim") != 64
                or bank_config.get("final_update") != 1500
                or bank_config.get("exposures_per_expert_target") != expected_exposure
                or bank_config.get("expert_initialization_keys") != EXPERT_KEYS[axis]
                or bank_config.get("batch_size") != 8
                or bank_config.get("mask_ratio") != 0.3
                or bank_config.get("mask_token") != -10.0
                or bank_config.get("normalization") != "log1p_tpm"
                or bank_config.get("scheduler") != "CosineAnnealingLR"
                or float(
                    bank_config.get(
                        "maximum_realized_exposure_fractional_deviation", 1.0
                    )
                )
                > 0.05
                or bank_config.get("calibration_evaluation_performed") is not False
                or bank.get("artifacts", {}).get("final_experts_sha256")
                != sha256_file(checkpoint_path)
                or bank.get("artifacts", {}).get("all_final_tensors_finite") is not True
                or bank.get("artifacts", {}).get("checkpoint_roundtrip_verified")
                is not True
            ):
                raise ValueError(f"final bank contract failed: seed={seed} axis={axis}")
            banks[axis] = {
                "checkpoint": str(checkpoint_path.resolve()),
                "checkpoint_sha256": sha256_file(checkpoint_path),
                "metadata": str(bank_metadata_path.resolve()),
                "metadata_sha256": sha256_file(bank_metadata_path),
                "expert_state_sha256": bank["artifacts"]["expert_state_sha256"],
            }
        seed_artifacts[str(seed)] = {
            "root": str(seed_root.resolve()),
            "run_metadata_sha256": sha256_file(metadata_path),
            "banks": banks,
        }

    bundle_root = output_dir / "bundle"
    bundle_files = {
        "protocol": bundle_root / "protocol.json",
        "partition_manifest": bundle_root / "partitions" / "development_fit_manifest.parquet",
        "partition_report": bundle_root / "partitions" / "partition_report.json",
        "random_mappings": bundle_root / "random_control_mappings.json",
        "router_artifact": bundle_root / "router" / "organ_k4_final_router.npz",
        "router_report": bundle_root / "router" / "router_report.json",
        "pooled_checkpoint": bundle_root / "pooled" / "pooled_trunk.pt",
        "axis_definitions": bundle_root / "axis_definitions.npz",
        "k45_evaluation_report": bundle_root / "provenance" / "k45_evaluation_report.json",
        "development_expression": bundle_root / "development_data" / "expression.parquet",
        "development_expression_metadata": bundle_root
        / "development_data"
        / "extraction_report.json",
        "development_extracted_manifest": bundle_root
        / "development_data"
        / "manifest.parquet",
        "development_firewall_report": bundle_root
        / "development_data"
        / "firewall_report.json",
        "development_data_sha256s": bundle_root
        / "development_data"
        / "FULL_SHA256SUMS",
        "development_genes": bundle_root / "development_data" / "genes.txt",
        "development_firewall_marker": bundle_root
        / "development_data"
        / "FIREWALL_VERIFIED",
        "development_firewall_log": bundle_root
        / "development_data"
        / "firewall_verification.log",
    }
    paths["development_genes"] = development_root / "genes.txt"
    paths["development_firewall_marker"] = development_root / "FIREWALL_VERIFIED"
    paths["development_firewall_log"] = development_root / "firewall_verification.log"
    bundle_hashes = {
        name: _copy_verified(paths[name], destination)
        for name, destination in bundle_files.items()
    }
    portable_seeds: dict[str, Any] = {}
    for seed in SEEDS:
        source_root = seed_roots[seed]
        seed_bundle = bundle_root / "seeds" / f"seed{seed}"
        top_files = {}
        for filename in (
            "run_metadata.json",
            "fit_exposures.parquet",
            "fit_exposure_report.json",
            "fit_schedule.parquet",
        ):
            source = source_root / filename
            if not source.is_file():
                raise FileNotFoundError(source)
            destination = seed_bundle / filename
            top_files[filename] = {
                "path": str(destination.relative_to(output_dir)),
                "sha256": _copy_verified(source, destination),
            }
        portable_banks = {}
        for axis in AXES:
            bank_bundle = seed_bundle / "banks" / axis
            source_bank = source_root / "banks" / axis
            checkpoint_destination = bank_bundle / "final_experts.pt"
            metadata_destination = bank_bundle / "run_metadata.json"
            portable_banks[axis] = {
                "checkpoint": str(checkpoint_destination.relative_to(output_dir)),
                "checkpoint_sha256": _copy_verified(
                    source_bank / "final_experts.pt", checkpoint_destination
                ),
                "metadata": str(metadata_destination.relative_to(output_dir)),
                "metadata_sha256": _copy_verified(
                    source_bank / "run_metadata.json", metadata_destination
                ),
            }
        portable_seeds[str(seed)] = {
            "files": top_files,
            "banks": portable_banks,
        }

    config = {
        "selected_candidate": "k4_epe",
        "training_seeds": list(SEEDS),
        "axes": list(AXES),
        "deployment_seed_policy": "retain all seeds; no best-seed selection",
        "external_loss_policy": "average prespecified seed-level losses per sample",
        "old_internal_test_included": False,
        "external_data_accessed": False,
    }
    manifest = {
        "schema_version": 1,
        "status": "frozen",
        "artifact_role": "stage1_k4_final_candidate_bundle",
        "research_stage": "final_refit_for_external_confirmation",
        "development_only": True,
        "internally_confirmatory": False,
        "internal_efficacy_scoring": False,
        "test_accessed": False,
        "external_data_accessed": False,
        "code_commit": args.code_commit,
        "config": config,
        "artifacts": {
            "path_policy": "relative to the candidate directory",
            "protocol": str(bundle_files["protocol"].relative_to(output_dir)),
            "partition_manifest": str(
                bundle_files["partition_manifest"].relative_to(output_dir)
            ),
            "partition_report": str(
                bundle_files["partition_report"].relative_to(output_dir)
            ),
            "random_mappings": str(
                bundle_files["random_mappings"].relative_to(output_dir)
            ),
            "router_artifact": str(
                bundle_files["router_artifact"].relative_to(output_dir)
            ),
            "router_report": str(
                bundle_files["router_report"].relative_to(output_dir)
            ),
            "pooled_checkpoint": str(
                bundle_files["pooled_checkpoint"].relative_to(output_dir)
            ),
            "axis_definitions": str(
                bundle_files["axis_definitions"].relative_to(output_dir)
            ),
            "k45_evaluation_report": str(
                bundle_files["k45_evaluation_report"].relative_to(output_dir)
            ),
            "development_expression": str(
                bundle_files["development_expression"].relative_to(output_dir)
            ),
            "development_expression_metadata": str(
                bundle_files["development_expression_metadata"].relative_to(output_dir)
            ),
            "development_extracted_manifest": str(
                bundle_files["development_extracted_manifest"].relative_to(output_dir)
            ),
            "development_firewall_report": str(
                bundle_files["development_firewall_report"].relative_to(output_dir)
            ),
            "development_data_sha256s": str(
                bundle_files["development_data_sha256s"].relative_to(output_dir)
            ),
            "development_genes": str(
                bundle_files["development_genes"].relative_to(output_dir)
            ),
            "development_firewall_marker": str(
                bundle_files["development_firewall_marker"].relative_to(output_dir)
            ),
            "development_firewall_log": str(
                bundle_files["development_firewall_log"].relative_to(output_dir)
            ),
            "seeds": portable_seeds,
        },
        "source_artifacts": {"seeds": seed_artifacts},
        "hashes": {
            "protocol_sha256": protocol_hash,
            "partition_manifest_sha256": sha256_file(paths["partition_manifest"]),
            "partition_report_sha256": sha256_file(paths["partition_report"]),
            "random_mappings_sha256": sha256_file(paths["random_mappings"]),
            "router_artifact_sha256": sha256_file(paths["router_artifact"]),
            "router_report_sha256": sha256_file(paths["router_report"]),
            "pooled_checkpoint_sha256": sha256_file(paths["pooled_checkpoint"]),
            "k45_evaluation_report_sha256": sha256_file(
                paths["k45_evaluation_report"]
            ),
            "axis_definitions_sha256": sha256_file(paths["axis_definitions"]),
            "portable_bundle_files": bundle_hashes,
            "resolved_config_sha256": sha256_json(config),
        },
        "external_confirmation_required": True,
    }
    manifest_path = output_dir / "candidate_manifest.json"
    _atomic_json(manifest_path, manifest)
    validate_portable_candidate(
        manifest_path, expected_code_commit=args.code_commit
    )
    (output_dir / "FINAL_CANDIDATE_FROZEN").touch()
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--partition-manifest", required=True)
    parser.add_argument("--partition-report", required=True)
    parser.add_argument("--random-mappings", required=True)
    parser.add_argument("--router-artifact", required=True)
    parser.add_argument("--router-report", required=True)
    parser.add_argument("--pooled-checkpoint", required=True)
    parser.add_argument("--k45-evaluation-report", required=True)
    parser.add_argument("--axis-definitions", required=True)
    parser.add_argument("--development-expression", required=True)
    parser.add_argument("--development-expression-metadata", required=True)
    parser.add_argument("--development-extracted-manifest", required=True)
    parser.add_argument("--development-firewall-report", required=True)
    parser.add_argument("--development-data-sha256s", required=True)
    parser.add_argument("--seed-root", action="append", required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser


def main() -> None:
    manifest = freeze(build_parser().parse_args())
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
