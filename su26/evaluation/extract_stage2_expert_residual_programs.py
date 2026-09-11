#!/usr/bin/env python3
"""Extract frozen organ-expert functional programs on GTEx calibration data.

This is a read-only Stage 2 representation audit. It loads every prespecified
Stage 1 seed, masks the frozen score-gene panel, verifies sample-level scores
against the original calibration caches, and stores gene-level errors and
functional corrections for the frozen evaluator.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch


ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = ROOT / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from train_latent_moe import load_frozen_trunk  # noqa: E402
from train_manifest import load_expression_rows, sha256_file, sha256_lines  # noqa: E402

try:
    from evaluation.cache_gtex_to_archs4_lockbox_scores import (
        ExpertBank,
        sha256_array,
        write_deterministic_npz,
    )
    from evaluation.freeze_gtex_to_archs4_candidates import ORGANS, SEEDS
    from evaluation.freeze_gtex_to_archs4_random_controls import RANDOM_AXES
except ModuleNotFoundError:
    from cache_gtex_to_archs4_lockbox_scores import (  # type: ignore
        ExpertBank,
        sha256_array,
        write_deterministic_npz,
    )
    from freeze_gtex_to_archs4_candidates import ORGANS, SEEDS  # type: ignore
    from freeze_gtex_to_archs4_random_controls import RANDOM_AXES  # type: ignore


ARRAY_NAMES = (
    "pooled_squared_error",
    "pooled_adapter_squared_error",
    "specialist_squared_error",
    "random_assigned_mean_squared_error",
    "specialist_minus_pooled_adapter_prediction",
    "random_mean_minus_pooled_adapter_prediction",
)


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise TypeError(f"{path} is not a JSON object")
    return value


def _artifact(root: Path, descriptor: dict[str, Any], label: str) -> Path:
    path = root / str(descriptor["path"])
    if not path.is_file():
        raise FileNotFoundError(path)
    if sha256_file(path) != descriptor["sha256"]:
        raise ValueError(f"{label} SHA256 mismatch")
    return path


def _load_bank(
    root: Path,
    descriptor: dict[str, Any],
    *,
    axis: str,
    seed: int,
    hidden_dim: int,
    device: torch.device,
) -> ExpertBank:
    checkpoint_path = _artifact(root, descriptor["checkpoint"], f"{seed}/{axis}")
    try:
        checkpoint = torch.load(
            checkpoint_path, map_location="cpu", weights_only=False
        )
    except TypeError:
        checkpoint = torch.load(checkpoint_path, map_location="cpu")
    config = checkpoint.get("config", {})
    if (
        checkpoint.get("axis") != axis
        or int(checkpoint.get("training_seed", -1)) != seed
        or int(config.get("final_update", -1)) != 1500
    ):
        raise ValueError(f"{seed}/{axis} checkpoint contract changed")
    bank = ExpertBank(
        hidden_dim,
        int(config["adapter_dim"]),
        int(config["num_experts"]),
    )
    bank.load_state_dict(checkpoint["expert_state_dict"])
    bank.requires_grad_(False)
    bank.eval()
    return bank.to(device)


def _assert_original_scores(
    *,
    root: Path,
    entry: dict[str, Any],
    arrays: dict[str, np.ndarray],
    random_axis_errors: dict[str, np.ndarray],
) -> None:
    checks = {
        "organ_k8": (
            arrays["specialist_squared_error"].mean(axis=1),
            "true_partition_mse",
        ),
        "pooled_adapter": (
            arrays["pooled_adapter_squared_error"].mean(axis=1),
            "true_partition_mse",
        ),
    }
    for axis, values in random_axis_errors.items():
        checks[axis] = (values.mean(axis=1), "true_partition_mse")
    pooled_checked = False
    for axis, (observed, key) in checks.items():
        score_path = _artifact(
            root,
            entry["banks"][axis]["calibration_scores"],
            f"{entry['seed']}/{axis}/calibration_scores",
        )
        with np.load(score_path, allow_pickle=False) as archive:
            expected = archive[key].astype(np.float64)
            if not pooled_checked:
                pooled = arrays["pooled_squared_error"].mean(axis=1)
                if not np.allclose(
                    pooled, archive["pooled_mse"], rtol=2e-5, atol=2e-6
                ):
                    raise ValueError("recomputed pooled scores differ from frozen cache")
                pooled_checked = True
        if not np.allclose(observed, expected, rtol=2e-5, atol=2e-6):
            raise ValueError(f"recomputed {axis} scores differ from frozen cache")


def extract(args: argparse.Namespace) -> dict[str, Any]:
    protocol_path = Path(args.protocol)
    ledger_path = Path(args.candidate_ledger)
    expression_path = Path(args.expression_parquet)
    extraction_report_path = Path(args.extraction_report)
    manifest_path = Path(args.manifest)
    manifest_report_path = Path(args.manifest_report)
    axes_path = Path(args.axis_definitions)
    training_root = Path(args.training_root)
    output_dir = Path(args.output_dir)
    for path in (
        protocol_path,
        ledger_path,
        expression_path,
        extraction_report_path,
        manifest_path,
        manifest_report_path,
        axes_path,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)
    if sha256_file(protocol_path) != args.expected_protocol_sha256:
        raise ValueError("protocol SHA256 mismatch")
    protocol = _json(protocol_path)
    if protocol.get("status") != "frozen_before_representation_outputs":
        raise ValueError("representation protocol is not frozen")
    expected = protocol["inputs"]
    observed_hashes = {
        "candidate_ledger_sha256": sha256_file(ledger_path),
        "expression_sha256": sha256_file(expression_path),
        "manifest_sha256": sha256_file(manifest_path),
        "axis_definitions_sha256": sha256_file(axes_path),
    }
    for name, value in observed_hashes.items():
        if value != expected[name]:
            raise ValueError(f"{name} differs from frozen protocol")
    extraction_report = _json(extraction_report_path)
    manifest_report = _json(manifest_report_path)
    if (
        extraction_report.get("status") != "complete"
        or extraction_report.get("archs4_expression_accessed") is not False
        or manifest_report.get("status") != "complete"
        or manifest_report.get("test_accessed") is not False
    ):
        raise ValueError("GTEx source reports violate the development-data firewall")
    if (
        manifest_report["hashes"]["calibration_donor_ids_sha256"]
        != expected["calibration_donor_ids_sha256"]
    ):
        raise ValueError("calibration donor set differs from frozen protocol")
    ledger = _json(ledger_path)
    if (
        ledger.get("status") != "frozen_gtex_only_k8_candidate_ledger"
        or ledger.get("archs4_expression_accessed") is not False
        or ledger.get("best_seed_selection_allowed") is not False
    ):
        raise ValueError("candidate ledger violates the frozen-model firewall")
    if output_dir.exists():
        raise FileExistsError(output_dir)
    output_dir.mkdir(parents=True)

    manifest = pd.read_parquet(manifest_path)
    calibration = manifest.loc[manifest["split"].astype(str) == "calibration"].copy()
    if len(calibration) != int(expected["calibration_samples"]):
        raise ValueError("calibration sample count changed")
    sample_ids = calibration["sample_id"].astype(str).tolist()
    expression, expression_info = load_expression_rows(
        expression_path, sample_ids, sample_id_column="sample_id"
    )
    with np.load(axes_path, allow_pickle=False) as archive:
        score_indices = archive["score_gene_indices"].astype(np.int64)
        gene_names = archive["gene_names"].astype(str)
    if gene_names.tolist() != list(expression_info.gene_columns):
        raise ValueError("axis and expression gene order differ")
    if len(score_indices) != int(expected["score_genes"]):
        raise ValueError("score-gene count changed")
    score_gene_names = gene_names[score_indices]
    truth_full = np.log1p(expression).astype(np.float32, copy=False)
    truth = truth_full[:, score_indices].copy()
    masked = truth_full.copy()
    masked[:, score_indices] = np.float32(-10.0)
    organs = calibration["organ"].to_numpy(dtype=str)
    donors = calibration["series_group_id"].to_numpy(dtype=str)
    if set(organs) != set(ORGANS) or list(expected["organs"]) != list(ORGANS):
        raise ValueError("organ labels differ from frozen order")
    organ_labels = calibration["organ_k8"].to_numpy(dtype=np.int64)
    if not np.array_equal(organ_labels, np.asarray([ORGANS.index(x) for x in organs])):
        raise ValueError("organ labels do not match semantic expert order")
    random_labels = {
        axis: calibration[axis].to_numpy(dtype=np.int64) for axis in RANDOM_AXES
    }
    if any(np.any((values < 0) | (values >= 8)) for values in random_labels.values()):
        raise ValueError("random K8 calibration labels are invalid")

    requested_device = args.device
    device = torch.device(
        "cuda:0"
        if requested_device == "auto" and torch.cuda.is_available()
        else ("cpu" if requested_device == "auto" else requested_device)
    )
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    entries = {int(item["seed"]): item for item in ledger["seed_candidates"]}
    report: dict[str, Any] = {
        "schema_version": 1,
        "status": "running",
        "research_stage": "stage2_representation_first_pivot",
        "code_commit": args.code_commit,
        "protocol_sha256": args.expected_protocol_sha256,
        "model_fitting_performed": False,
        "archs4_accessed": False,
        "best_seed_selection_performed": False,
        "seeds": {},
    }
    for seed in SEEDS:
        entry = entries[seed]
        pooled_path = _artifact(
            training_root, entry["pooled"]["checkpoint"], f"{seed}/pooled"
        )
        trunk, config, _ = load_frozen_trunk(pooled_path, device)
        if (
            list(config["gene_list"]) != gene_names.tolist()
            or config["normalization"] != "log1p_tpm"
            or not np.isclose(float(config["mask_token"]), -10.0)
        ):
            raise ValueError(f"seed {seed} pooled expression contract changed")
        hidden_dim = int(trunk.gene_embedding.embedding_dim)
        banks = {
            axis: _load_bank(
                training_root,
                entry["banks"][axis],
                axis=axis,
                seed=seed,
                hidden_dim=hidden_dim,
                device=device,
            )
            for axis in ("organ_k8", *RANDOM_AXES, "pooled_adapter")
        }
        shape = truth.shape
        predictions = {
            "pooled": np.empty(shape, dtype=np.float32),
            "pooled_adapter": np.empty(shape, dtype=np.float32),
            "specialist": np.empty(shape, dtype=np.float32),
        }
        random_predictions = {
            axis: np.empty(shape, dtype=np.float32) for axis in RANDOM_AXES
        }
        score_tensor = torch.as_tensor(score_indices, device=device)
        with torch.inference_mode():
            for start in range(0, len(masked), args.batch_size):
                stop = min(len(masked), start + args.batch_size)
                batch = torch.from_numpy(masked[start:stop]).to(device)
                hidden = trunk.encode(batch)
                base = trunk.decode(hidden)
                local = np.arange(stop - start)
                predictions["pooled"][start:stop] = (
                    base.index_select(1, score_tensor).float().cpu().numpy()
                )
                pooled_adapter = banks["pooled_adapter"](hidden, base)[:, 0]
                predictions["pooled_adapter"][start:stop] = (
                    pooled_adapter.index_select(1, score_tensor).float().cpu().numpy()
                )
                organ_all = (
                    banks["organ_k8"](hidden, base)
                    .index_select(2, score_tensor)
                    .float()
                    .cpu()
                    .numpy()
                )
                predictions["specialist"][start:stop] = organ_all[
                    local, organ_labels[start:stop]
                ]
                for axis in RANDOM_AXES:
                    random_all = (
                        banks[axis](hidden, base)
                        .index_select(2, score_tensor)
                        .float()
                        .cpu()
                        .numpy()
                    )
                    random_predictions[axis][start:stop] = random_all[
                        local, random_labels[axis][start:stop]
                    ]
        squared = {
            name: np.square(value - truth, dtype=np.float32)
            for name, value in predictions.items()
        }
        random_squared = {
            axis: np.square(value - truth, dtype=np.float32)
            for axis, value in random_predictions.items()
        }
        random_prediction_mean = np.mean(
            np.stack(list(random_predictions.values()), axis=0), axis=0
        ).astype(np.float32)
        arrays: dict[str, np.ndarray] = {
            "sample_ids": np.asarray(sample_ids, dtype=str),
            "donors": donors,
            "organs": organs,
            "score_gene_indices": score_indices,
            "score_gene_names": score_gene_names,
            "pooled_squared_error": squared["pooled"],
            "pooled_adapter_squared_error": squared["pooled_adapter"],
            "specialist_squared_error": squared["specialist"],
            "random_assigned_mean_squared_error": np.mean(
                np.stack(list(random_squared.values()), axis=0), axis=0
            ).astype(np.float32),
            "specialist_minus_pooled_adapter_prediction": (
                predictions["specialist"] - predictions["pooled_adapter"]
            ).astype(np.float32),
            "random_mean_minus_pooled_adapter_prediction": (
                random_prediction_mean - predictions["pooled_adapter"]
            ).astype(np.float32),
        }
        _assert_original_scores(
            root=training_root,
            entry=entry,
            arrays=arrays,
            random_axis_errors=random_squared,
        )
        if not all(
            np.isfinite(value).all()
            for value in arrays.values()
            if value.dtype.kind not in {"U", "S"}
        ):
            raise FloatingPointError(f"seed {seed} extraction contains nonfinite values")
        metadata = {
            "schema_version": 1,
            "status": "complete",
            "seed": seed,
            "code_commit": args.code_commit,
            "protocol_sha256": args.expected_protocol_sha256,
            "candidate_ledger_sha256": observed_hashes["candidate_ledger_sha256"],
            "expression_sha256": observed_hashes["expression_sha256"],
            "manifest_sha256": observed_hashes["manifest_sha256"],
            "axis_definitions_sha256": observed_hashes["axis_definitions_sha256"],
            "sample_ids_sha256": sha256_lines(sample_ids),
            "donor_ids_sha256": sha256_lines(sorted(set(donors))),
            "model_fitting_performed": False,
            "archs4_accessed": False,
            "original_calibration_score_roundtrip_verified": True,
            "content_sha256": {
                name: sha256_array(value) for name, value in arrays.items()
            },
        }
        arrays["metadata_json"] = np.asarray(json.dumps(metadata, sort_keys=True))
        output_path = output_dir / f"seed{seed}_gene_scores.npz"
        write_deterministic_npz(output_path, arrays)
        report["seeds"][str(seed)] = {
            **metadata,
            "path": str(output_path.resolve()),
            "sha256": sha256_file(output_path),
            "size_bytes": output_path.stat().st_size,
        }
        del trunk, banks
        if device.type == "cuda":
            torch.cuda.empty_cache()
    report["status"] = "complete"
    report_path = output_dir / "extraction_report.json"
    temporary = report_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, report_path)
    (output_dir / "COMPLETE").touch()
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--candidate-ledger", required=True)
    parser.add_argument("--training-root", required=True)
    parser.add_argument("--expression-parquet", required=True)
    parser.add_argument("--extraction-report", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--manifest-report", required=True)
    parser.add_argument("--axis-definitions", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--device", default="auto")
    return parser


if __name__ == "__main__":
    print(json.dumps(extract(build_parser().parse_args()), indent=2, sort_keys=True))
