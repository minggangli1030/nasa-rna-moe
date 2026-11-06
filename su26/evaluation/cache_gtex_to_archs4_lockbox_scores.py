#!/usr/bin/env python3
"""Cache prespecified K8 predictions after the one-time ARCHS4 lockbox access.

This module performs no fitting or checkpoint selection.  It validates the frozen
protocol, candidate ledger, calibration-only random mappings, membership, access
report, expression artifact, and every model artifact before loading targets.
Only prespecified condition predictions are retained, so no test-driven expert
selection is possible downstream.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch import nn


ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = ROOT / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from train_latent_moe import ResidualExpert, load_frozen_trunk  # noqa: E402

try:
    from evaluation.freeze_gtex_to_archs4_candidates import ORGANS, SEEDS
    from evaluation.freeze_gtex_to_archs4_random_controls import RANDOM_AXES
except ModuleNotFoundError:
    from freeze_gtex_to_archs4_candidates import ORGANS, SEEDS
    from freeze_gtex_to_archs4_random_controls import RANDOM_AXES


CONDITIONS = (
    "pooled",
    "pooled_adapter",
    "true_organ",
    "blind_router_hard",
    "blind_router_soft",
    *RANDOM_AXES,
)


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_array(values: np.ndarray) -> str:
    values = np.asarray(values)
    digest = hashlib.sha256()
    digest.update(str(values.shape).encode())
    if values.dtype.kind in {"U", "S", "O"}:
        for value in values.astype(str).ravel(order="C"):
            digest.update(value.encode())
            digest.update(b"\0")
    else:
        contiguous = np.ascontiguousarray(values)
        digest.update(contiguous.dtype.str.encode())
        digest.update(contiguous.tobytes())
    return digest.hexdigest()


def write_deterministic_npz(path: Path, arrays: dict[str, np.ndarray]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        with zipfile.ZipFile(
            handle, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archive:
            for name in sorted(arrays):
                value = np.asarray(arrays[name])
                if value.dtype.kind == "O":
                    raise ValueError(f"object array forbidden: {name}")
                payload = io.BytesIO()
                np.lib.format.write_array(payload, value, allow_pickle=False)
                member = zipfile.ZipInfo(
                    f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0)
                )
                member.compress_type = zipfile.ZIP_DEFLATED
                member.external_attr = 0o600 << 16
                archive.writestr(member, payload.getvalue(), compresslevel=9)
    os.replace(temporary, path)


class ExpertBank(nn.Module):
    def __init__(self, hidden_dim: int, adapter_dim: int, num_experts: int):
        super().__init__()
        self.experts = nn.ModuleList(
            ResidualExpert(hidden_dim, adapter_dim) for _ in range(num_experts)
        )

    def forward(self, hidden: torch.Tensor, base: torch.Tensor) -> torch.Tensor:
        residual = torch.stack([expert(hidden) for expert in self.experts], dim=1)
        return base.unsqueeze(1) + residual


def _resolve_device(requested: str) -> torch.device:
    if requested == "auto":
        return torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    device = torch.device(requested)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError(f"CUDA requested but unavailable: {requested}")
    return device


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise TypeError(f"{path} is not a JSON object")
    return value


def _artifact(root: Path, descriptor: dict, label: str) -> Path:
    path = root / descriptor["path"]
    if not path.is_file():
        raise FileNotFoundError(path)
    if sha256_file(path) != descriptor["sha256"]:
        raise ValueError(f"{label} hash mismatch")
    return path


def validate_preflight(args: argparse.Namespace) -> dict[str, Any]:
    paths = {
        "protocol": Path(args.protocol),
        "candidate_ledger": Path(args.candidate_ledger),
        "random_mappings": Path(args.random_mappings),
        "lockbox_manifest": Path(args.lockbox_manifest),
        "freeze_report": Path(args.freeze_report),
        "expression": Path(args.expression_parquet),
        "extraction_report": Path(args.extraction_report),
        "access_report": Path(args.access_report),
    }
    for path in paths.values():
        if not path.is_file():
            raise FileNotFoundError(path)
    if sha256_file(paths["protocol"]) != args.expected_protocol_sha256:
        raise ValueError("protocol SHA256 mismatch")
    protocol = _load_json(paths["protocol"])
    protocol_status = protocol.get("status")
    amended = protocol_status == "frozen_gtex_to_archs4_k8_qc_amended_protocol"
    if (
        protocol_status
        not in {
            "frozen_gtex_to_archs4_k8_lockbox_protocol",
            "frozen_gtex_to_archs4_k8_qc_amended_protocol",
        }
        or protocol.get("expression_access_gate", {}).get(
            "all_implementation_hashes_frozen"
        )
        is not True
    ):
        raise ValueError("protocol is not a frozen implementation-bound lockbox")
    if amended and protocol.get(
        "evidence_label"
    ) != "post_access_qc_amended_external_evaluation":
        raise ValueError("QC-amended protocol lacks its required evidence label")
    expected_self = protocol.get("implementation_hashes", {}).get(
        "lockbox_score_cache_sha256"
    )
    if expected_self != sha256_file(Path(__file__).resolve()):
        raise ValueError("frozen score-cache implementation hash mismatch")
    sources = protocol.get("source_contract", {})
    for name in ("candidate_ledger", "random_mappings"):
        if sources.get(f"{name}_sha256") != sha256_file(paths[name]):
            raise ValueError(f"protocol source hash mismatch for {name}")

    ledger = _load_json(paths["candidate_ledger"])
    mappings = _load_json(paths["random_mappings"])
    freeze = _load_json(paths["freeze_report"])
    access = _load_json(paths["access_report"])
    extraction = _load_json(paths["extraction_report"])
    if (
        ledger.get("status") != "frozen_gtex_only_k8_candidate_ledger"
        or ledger.get("seeds") != list(SEEDS)
        or ledger.get("best_seed_selection_allowed") is not False
    ):
        raise ValueError("candidate ledger is not the sealed all-seed family")
    if (
        mappings.get("status")
        != "frozen_gtex_calibration_random_control_mappings"
        or mappings.get("candidate_ledger_sha256")
        != sha256_file(paths["candidate_ledger"])
        or mappings.get("archs4_expression_accessed") is not False
    ):
        raise ValueError("random controls were not frozen before ARCHS4 access")
    if amended:
        freeze_valid = (
            freeze.get("status") == "frozen_post_access_qc_amended_membership"
            and freeze.get("retained_samples") == 821
            and freeze.get("retained_study_groups") == 63
            and freeze.get("hashes", {}).get("qc_amended_manifest_sha256")
            == sha256_file(paths["lockbox_manifest"])
        )
        expected_access_status = "archs4_k8_qc_amended_expression_extracted"
    else:
        freeze_valid = (
            freeze.get("ready_for_expression_access") is True
            and freeze.get("hashes", {}).get("lockbox_manifest_sha256")
            == sha256_file(paths["lockbox_manifest"])
        )
        expected_access_status = "archs4_k8_lockbox_expression_extracted_once"
    if not freeze_valid:
        raise ValueError("membership freeze is not valid")
    if (
        access.get("status") != expected_access_status
        or access.get("protocol_sha256") != sha256_file(paths["protocol"])
        or access.get("candidate_ledger_sha256")
        != sha256_file(paths["candidate_ledger"])
        or access.get("lockbox_manifest_sha256")
        != sha256_file(paths["lockbox_manifest"])
        or access.get("expression_parquet_sha256")
        != sha256_file(paths["expression"])
    ):
        raise ValueError("expression access report does not bind current inputs")
    if extraction.get("outputs", {}).get(
        "expression_parquet_sha256"
    ) != sha256_file(paths["expression"]):
        raise ValueError("extraction report does not bind expression parquet")
    return {
        "paths": paths,
        "protocol": protocol,
        "ledger": ledger,
        "mappings": mappings,
        "access": access,
        "amended": amended,
    }


def _load_bank(
    root: Path,
    descriptor: dict,
    *,
    axis: str,
    seed: int,
    hidden_dim: int,
    device: torch.device,
) -> ExpertBank:
    checkpoint_path = _artifact(root, descriptor["checkpoint"], f"{seed}/{axis}")
    metadata_path = _artifact(root, descriptor["metadata"], f"{seed}/{axis} metadata")
    metadata = _load_json(metadata_path)
    config = metadata.get("config", {})
    expected_experts = 1 if axis == "pooled_adapter" else 8
    if (
        metadata.get("status") != "complete"
        or metadata.get("axis") != axis
        or int(metadata.get("training_seed", -1)) != seed
        or int(config.get("num_experts", -1)) != expected_experts
        or int(config.get("score_gene_count", -1)) != 4634
        or config.get("router_trainable") is not False
    ):
        raise ValueError(f"invalid frozen bank metadata for {seed}/{axis}")
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if (
        checkpoint.get("axis") != axis
        or int(checkpoint.get("training_seed", -1)) != seed
        or checkpoint.get("config") != config
    ):
        raise ValueError(f"invalid frozen checkpoint for {seed}/{axis}")
    bank = ExpertBank(
        hidden_dim, int(config["adapter_dim"]), num_experts=expected_experts
    )
    bank.load_state_dict(checkpoint["expert_state_dict"], strict=True)
    bank.requires_grad_(False)
    return bank.eval().to(device)


def _router(
    artifact_path: Path, genes: list[str], masked: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    with np.load(artifact_path, allow_pickle=False) as archive:
        arrays = {name: np.asarray(archive[name]) for name in archive.files}
    required = {
        "classes",
        "coefficients",
        "intercepts",
        "gene_names",
        "scaler_mean",
        "scaler_scale",
        "score_gene_indices",
        "mask_token",
    }
    if required - set(arrays):
        raise ValueError("router artifact lacks required arrays")
    if arrays["gene_names"].astype(str).tolist() != genes:
        raise ValueError("router gene order differs from expression")
    if arrays["classes"].astype(str).tolist() != list(ORGANS):
        raise ValueError("router classes differ from frozen organ order")
    logits = (
        (masked.astype(np.float64) - arrays["scaler_mean"])
        / arrays["scaler_scale"]
    ) @ arrays["coefficients"].T + arrays["intercepts"]
    logits -= logits.max(axis=1, keepdims=True)
    probabilities = np.exp(logits)
    probabilities /= probabilities.sum(axis=1, keepdims=True)
    if not np.isfinite(probabilities).all():
        raise RuntimeError("router produced nonfinite probabilities")
    return probabilities, arrays["score_gene_indices"].astype(np.int64)


def build_score_cache(args: argparse.Namespace) -> dict[str, Any]:
    preflight = validate_preflight(args)
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise FileExistsError(output_dir)
    output_dir.mkdir(parents=True)
    root = Path(args.training_root)
    ledger = preflight["ledger"]
    mappings = preflight["mappings"]
    manifest = pd.read_csv(preflight["paths"]["lockbox_manifest"], keep_default_na=False)
    expression = pd.read_parquet(preflight["paths"]["expression"])
    if "sample_id" not in expression or expression["sample_id"].duplicated().any():
        raise ValueError("expression cache lacks unique sample_id")
    expected_ids = manifest["sample_id"].astype(str).tolist()
    expression["sample_id"] = expression["sample_id"].astype(str)
    expression = expression.set_index("sample_id").reindex(expected_ids)
    if expression.isna().any().any() or expression.index.tolist() != expected_ids:
        raise ValueError("expression membership differs from lockbox manifest")
    genes = expression.columns.astype(str).tolist()
    truth = np.log1p(expression.to_numpy(dtype=np.float32))
    if not np.isfinite(truth).all() or np.any(truth < 0):
        raise ValueError("invalid TPM expression")

    router_path = _artifact(root, ledger["router"]["artifact"], "router")
    with np.load(router_path, allow_pickle=False) as archive:
        score_indices = archive["score_gene_indices"].astype(np.int64)
        mask_token = float(archive["mask_token"])
    masked = truth.copy()
    masked[:, score_indices] = np.float32(mask_token)
    probabilities, verified_score_indices = _router(router_path, genes, masked)
    if not np.array_equal(score_indices, verified_score_indices):
        raise ValueError("router score-gene indices changed")
    target = truth[:, score_indices].astype(np.float32)
    organs = manifest["organ"].to_numpy(dtype=str)
    groups = manifest["series_group_id"].to_numpy(dtype=str)
    if set(organs) != set(ORGANS):
        raise ValueError("manifest organ labels differ from frozen order")
    organ_labels = np.asarray([ORGANS.index(value) for value in organs], dtype=np.int64)
    hard_labels = probabilities.argmax(axis=1)
    device = _resolve_device(args.device)
    reports = {}
    seed_entries = {int(item["seed"]): item for item in ledger["seed_candidates"]}
    for seed in SEEDS:
        entry = seed_entries[seed]
        pooled_path = _artifact(root, entry["pooled"]["checkpoint"], f"{seed}/pooled")
        trunk, config, _ = load_frozen_trunk(pooled_path, device)
        if config["gene_list"] != genes or config["normalization"] != "log1p_tpm":
            raise ValueError(f"seed {seed} pooled trunk expression contract changed")
        hidden_dim = int(trunk.gene_embedding.embedding_dim)
        banks = {
            axis: _load_bank(
                root,
                entry["banks"][axis],
                axis=axis,
                seed=seed,
                hidden_dim=hidden_dim,
                device=device,
            )
            for axis in ("organ_k8", *RANDOM_AXES, "pooled_adapter")
        }
        predictions = {
            name: np.empty_like(target) for name in CONDITIONS
        }
        batch_size = int(args.batch_size)
        if batch_size < 1:
            raise ValueError("batch size must be positive")
        index = torch.as_tensor(score_indices, device=device)
        with torch.inference_mode():
            for start in range(0, len(masked), batch_size):
                stop = min(len(masked), start + batch_size)
                batch = torch.from_numpy(masked[start:stop]).to(device)
                hidden = trunk.encode(batch)
                base = trunk.decode(hidden)
                pooled = base.index_select(1, index).float().cpu().numpy()
                organ_bank = (
                    banks["organ_k8"](hidden, base)
                    .index_select(2, index)
                    .float()
                    .cpu()
                    .numpy()
                )
                predictions["pooled"][start:stop] = pooled
                predictions["pooled_adapter"][start:stop] = (
                    banks["pooled_adapter"](hidden, base)[:, 0]
                    .index_select(1, index)
                    .float()
                    .cpu()
                    .numpy()
                )
                local = np.arange(stop - start)
                predictions["true_organ"][start:stop] = organ_bank[
                    local, organ_labels[start:stop]
                ]
                predictions["blind_router_hard"][start:stop] = organ_bank[
                    local, hard_labels[start:stop]
                ]
                predictions["blind_router_soft"][start:stop] = np.einsum(
                    "nk,nkg->ng", probabilities[start:stop], organ_bank
                )
                for axis in RANDOM_AXES:
                    random_bank = (
                        banks[axis](hidden, base)
                        .index_select(2, index)
                        .float()
                        .cpu()
                        .numpy()
                    )
                    selected = np.asarray(
                        [
                            mappings["mappings"][str(seed)][axis]["by_organ"][
                                organ
                            ]["selected_random_expert_index"]
                            for organ in organs[start:stop]
                        ],
                        dtype=np.int64,
                    )
                    predictions[axis][start:stop] = random_bank[local, selected]
        arrays: dict[str, np.ndarray] = {
            "sample_ids": np.asarray(expected_ids, dtype=str),
            "groups": groups,
            "organs": organs,
            "score_gene_indices": score_indices,
            "target_masked": target,
            "router_probabilities": probabilities,
            "router_hard_labels": hard_labels,
            **{f"prediction__{name}": value for name, value in predictions.items()},
        }
        if not all(
            np.isfinite(value).all()
            for value in arrays.values()
            if value.dtype.kind not in {"U", "S"}
        ):
            raise RuntimeError(f"seed {seed} cache contains nonfinite values")
        metadata = {
            "schema_version": 1,
            "status": "complete",
            "seed": seed,
            "conditions": list(CONDITIONS),
            "protocol_sha256": sha256_file(preflight["paths"]["protocol"]),
            "candidate_ledger_sha256": sha256_file(preflight["paths"]["candidate_ledger"]),
            "random_mappings_sha256": sha256_file(preflight["paths"]["random_mappings"]),
            "expression_parquet_sha256": sha256_file(preflight["paths"]["expression"]),
            "targets_accessed": True,
            "model_fitting_performed": False,
            "best_seed_selection_performed": False,
            "evidence_label": (
                "post_access_qc_amended_external_evaluation"
                if preflight["amended"]
                else "preregistered_lockbox_evaluation"
            ),
            "content_sha256": {name: sha256_array(value) for name, value in arrays.items()},
        }
        arrays["metadata_json"] = np.asarray(json.dumps(metadata, sort_keys=True))
        output = output_dir / f"seed{seed}_scores.npz"
        write_deterministic_npz(output, arrays)
        reports[str(seed)] = {
            **metadata,
            "score_cache": str(output.resolve()),
            "score_cache_sha256": sha256_file(output),
        }
    report = {
        "schema_version": 1,
        "status": "complete",
        "seeds": list(SEEDS),
        "all_prespecified_seeds_scored": True,
        "best_seed_selection_performed": False,
        "model_fitting_performed": False,
        "evidence_label": (
            "post_access_qc_amended_external_evaluation"
            if preflight["amended"]
            else "preregistered_lockbox_evaluation"
        ),
        "conditions": list(CONDITIONS),
        "seed_reports": reports,
    }
    report_path = output_dir / "score_cache_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--candidate-ledger", required=True)
    parser.add_argument("--random-mappings", required=True)
    parser.add_argument("--lockbox-manifest", required=True)
    parser.add_argument("--freeze-report", required=True)
    parser.add_argument("--expression-parquet", required=True)
    parser.add_argument("--extraction-report", required=True)
    parser.add_argument("--access-report", required=True)
    parser.add_argument("--training-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--batch-size", type=int, default=8)
    print(json.dumps(build_score_cache(parser.parse_args()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
