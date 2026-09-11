#!/usr/bin/env python3
"""Extract deterministic training-only Stage 2B canonical caches and B1 probes."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.stage2b_cache import CanonicalCacheKey  # noqa: E402
from core.stage2b_diagnostics import (  # noqa: E402
    array_sha256,
    fixed_decoder_ridge,
    reconstruction_mse,
)
from core.train_latent_moe import load_frozen_trunk  # noqa: E402
from core.train_manifest import (  # noqa: E402
    load_expression_rows,
    seed_everything,
    sha256_file,
    stable_seed,
    validate_expression_metadata,
)
from core.train_stage2_aligned_program_repair import (  # noqa: E402
    _load_basis,
    _make_condition,
)


SEEDS = (17, 42, 101)


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _parse_seed_paths(values: list[str], label: str) -> dict[int, Path]:
    parsed: dict[int, Path] = {}
    for value in values:
        seed_text, separator, path_text = value.partition("=")
        if not separator:
            raise ValueError(f"{label} must use SEED=PATH")
        parsed[int(seed_text)] = Path(path_text)
    if tuple(sorted(parsed)) != SEEDS:
        raise ValueError(f"{label} must provide exactly {SEEDS}")
    return parsed


def _load_protocol(args: argparse.Namespace) -> tuple[Path, dict[str, Any]]:
    path = Path(args.protocol)
    if sha256_file(path) != args.expected_protocol_sha256:
        raise ValueError("Stage 2B protocol SHA256 mismatch")
    protocol = json.loads(path.read_text())
    if protocol.get("status") != "frozen_before_stage2b_diagnostic_access":
        raise ValueError("Stage 2B protocol is not frozen")
    firewalls = protocol.get("firewalls", {})
    if (
        firewalls.get("archs4_access") is not False
        or firewalls.get("calibration_split_access") is not False
        or firewalls.get("neural_checkpoint_updates") is not False
    ):
        raise ValueError("Stage 2B protocol firewalls are incomplete")
    return path, protocol


def _verify_common(
    args: argparse.Namespace, protocol: dict[str, Any]
) -> tuple[pd.DataFrame, np.ndarray, list[str], np.ndarray, np.ndarray]:
    paths = {
        "expression_sha256": Path(args.expression_parquet),
        "expression_metadata_sha256": Path(args.expression_metadata),
        "manifest_sha256": Path(args.manifest),
        "axis_definitions_sha256": Path(args.axis_definitions),
        "basis_bundle_sha256": Path(args.basis_bundle),
    }
    for key, path in paths.items():
        if sha256_file(path) != protocol["inputs"][key]:
            raise ValueError(f"{key} differs from frozen Stage 2B protocol")
    manifest = pd.read_parquet(args.manifest)
    training = (
        manifest.loc[
            manifest["split"].astype(str).eq("train")
            & manifest["balanced_train"].astype(bool)
        ]
        .sort_values("sample_id")
        .reset_index(drop=True)
    )
    if len(training) != int(protocol["inputs"]["training_samples"]):
        raise ValueError("training population size differs from protocol")
    with np.load(args.axis_definitions, allow_pickle=False) as archive:
        score_indices = archive["score_gene_indices"].astype(np.int64)
        gene_names = archive["gene_names"].astype(str).tolist()
    if array_sha256(score_indices) != protocol["inputs"]["score_index_sha256"]:
        raise ValueError("score index differs from protocol")
    program, random, hashes = _load_basis(
        Path(args.basis_bundle),
        expected_sha256=protocol["inputs"]["basis_bundle_sha256"],
        gene_names=gene_names,
        score_indices=score_indices,
    )
    if hashes["program_decoder_sha256"] != protocol["inputs"]["program_decoder_sha256"]:
        raise ValueError("program decoder differs from protocol")
    if hashes["random_decoder_sha256"] != protocol["inputs"]["random_decoder_sha256"]:
        raise ValueError("random decoder differs from protocol")
    return training, score_indices, gene_names, program, random


def _select_rows(
    training: pd.DataFrame, samples_per_organ: int | None
) -> pd.DataFrame:
    if samples_per_organ is None:
        return training.copy()
    if samples_per_organ < 1:
        raise ValueError("samples per organ must be positive")
    selected = (
        training.groupby("organ_k8", sort=True, group_keys=False)
        .head(samples_per_organ)
        .sort_values("sample_id")
        .copy()
    )
    if selected["organ_k8"].nunique() != 8:
        raise ValueError("probe selection does not cover all eight organs")
    return selected


def _load_private(
    *,
    path: Path,
    protocol: dict[str, Any],
    seed: int,
    hidden_dim: int,
    score_indices: np.ndarray,
    private_adapter_dim: int,
    device: torch.device,
):
    expected = protocol["inputs"]["valid_private_inputs"][str(seed)][
        "final_heads_sha256"
    ]
    if sha256_file(path) != expected:
        raise ValueError(f"private seed {seed} checkpoint differs from protocol")
    try:
        checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    except TypeError:
        checkpoint = torch.load(path, map_location="cpu")
    prefix = protocol["inputs"]["valid_private_inputs"][str(seed)][
        "valid_state_prefix"
    ]
    state = {
        key[len(prefix) :]: value
        for key, value in checkpoint["state_dict"].items()
        if key.startswith(prefix)
    }
    condition = _make_condition(
        hidden_dim=hidden_dim,
        score_indices=score_indices,
        decoder=None,
        program_head_dim=1,
        private_adapter_dim=private_adapter_dim,
        experts=8,
    )
    condition.load_state_dict(state, strict=True)
    condition.requires_grad_(False)
    condition.eval()
    return condition.to(device)


def _infer(
    *,
    expression: np.ndarray,
    labels: np.ndarray,
    trunk,
    private,
    score_indices: np.ndarray,
    mask_token: float,
    batch_size: int,
    device: torch.device,
) -> dict[str, np.ndarray]:
    logged = np.log1p(np.asarray(expression, dtype=np.float32))
    non_score = np.setdiff1d(
        np.arange(logged.shape[1], dtype=np.int64),
        score_indices,
        assume_unique=True,
    )
    score_tensor = torch.as_tensor(score_indices, device=device, dtype=torch.long)
    non_score_tensor = torch.as_tensor(non_score, device=device, dtype=torch.long)
    rows: dict[str, list[np.ndarray]] = {
        "h_canon": [],
        "r_full": [],
        "pooled_prediction": [],
        "private_prediction": [],
        "truth_score": [],
    }
    with torch.inference_mode():
        for start in range(0, len(logged), batch_size):
            stop = min(len(logged), start + batch_size)
            truth = torch.from_numpy(logged[start:stop]).to(device)
            masked = truth.clone()
            masked.index_fill_(1, score_tensor, float(mask_token))
            hidden = trunk.encode(masked)
            pooled = trunk.decode(hidden).index_select(1, score_tensor)
            label = torch.as_tensor(
                labels[start:stop], device=device, dtype=torch.long
            )
            private_residual, _ = private(hidden, masked, label)
            truth_score = truth.index_select(1, score_tensor)
            residual = truth_score - pooled - private_residual
            summary = hidden.index_select(1, non_score_tensor).mean(dim=1)
            values = {
                "h_canon": summary,
                "r_full": residual,
                "pooled_prediction": pooled,
                "private_prediction": private_residual,
                "truth_score": truth_score,
            }
            for name, value in values.items():
                rows[name].append(value.detach().cpu().float().numpy())
    return {
        name: np.ascontiguousarray(np.concatenate(parts), dtype=np.float32)
        for name, parts in rows.items()
    }


def _load_seed_models(
    *,
    seed: int,
    pooled_path: Path,
    private_path: Path,
    protocol: dict[str, Any],
    score_indices: np.ndarray,
    device: torch.device,
):
    if sha256_file(pooled_path) != protocol["inputs"]["pooled_checkpoint_sha256"][
        str(seed)
    ]:
        raise ValueError(f"pooled seed {seed} checkpoint differs from protocol")
    trunk, config, _ = load_frozen_trunk(pooled_path, device)
    private = _load_private(
        path=private_path,
        protocol=protocol,
        seed=seed,
        hidden_dim=int(trunk.gene_embedding.embedding_dim),
        score_indices=score_indices,
        private_adapter_dim=int(protocol["source_training"]["private_adapter_dim"]),
        device=device,
    )
    if float(config["mask_token"]) != float(protocol["canonical_cache"]["mask_token"]):
        raise ValueError("pooled trunk mask token differs from protocol")
    return trunk, private, config


def select_ridge(args: argparse.Namespace) -> dict[str, Any]:
    protocol_path, protocol = _load_protocol(args)
    training, score_indices, gene_names, decoder, _ = _verify_common(args, protocol)
    probe = _select_rows(
        training, int(protocol["ridge_selection"]["probe_samples_per_organ"])
    )
    expression, info = load_expression_rows(
        args.expression_parquet, probe["sample_id"].astype(str).tolist()
    )
    validate_expression_metadata(
        args.expression_parquet,
        info.gene_columns,
        metadata_path=args.expression_metadata,
    )
    if list(info.gene_columns) != gene_names:
        raise ValueError("expression gene order differs from axis definitions")
    pooled = _parse_seed_paths(args.pooled_checkpoint, "pooled checkpoint")
    private = _parse_seed_paths(args.private_checkpoint, "private checkpoint")
    device = torch.device(args.device)
    scores = {
        str(value): {"sum_squared_error": 0.0, "elements": 0}
        for value in protocol["ridge_selection"]["grid"]
    }
    seed_records = {}
    for seed in SEEDS:
        seed_everything(seed, deterministic=True)
        trunk, private_model, _ = _load_seed_models(
            seed=seed,
            pooled_path=pooled[seed],
            private_path=private[seed],
            protocol=protocol,
            score_indices=score_indices,
            device=device,
        )
        inferred = _infer(
            expression=expression,
            labels=probe["organ_k8"].to_numpy(dtype=np.int64),
            trunk=trunk,
            private=private_model,
            score_indices=score_indices,
            mask_token=float(protocol["canonical_cache"]["mask_token"]),
            batch_size=int(protocol["canonical_cache"]["fixed_batch_size"]),
            device=device,
        )
        for ridge in protocol["ridge_selection"]["grid"]:
            coefficient = fixed_decoder_ridge(inferred["r_full"], decoder, ridge)
            squared = np.square(
                inferred["r_full"].astype(np.float64)
                - coefficient.astype(np.float64) @ decoder.astype(np.float64)
            )
            record = scores[str(ridge)]
            record["sum_squared_error"] += float(squared.sum())
            record["elements"] += int(squared.size)
        seed_records[str(seed)] = {
            "probe_residual_sha256": array_sha256(inferred["r_full"]),
            "probe_hidden_sha256": array_sha256(inferred["h_canon"]),
        }
        del trunk, private_model, inferred
        if device.type == "cuda":
            torch.cuda.empty_cache()
    objective = {
        key: value["sum_squared_error"] / value["elements"]
        for key, value in scores.items()
    }
    selected = min(
        (float(value), float(key)) for key, value in objective.items()
    )[1]
    output = {
        "schema_version": 1,
        "status": "complete",
        "mechanical_only": bool(args.mechanical_only),
        "protocol_sha256": sha256_file(protocol_path),
        "selected_ridge_lambda": selected,
        "selection_rule": protocol["ridge_selection"]["selection"],
        "objective_mse": objective,
        "probe_rows": len(probe),
        "seed_records": seed_records,
        "completed_at_utc": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        raise FileExistsError(output_path)
    _atomic_json(output_path, output)
    return output


def _partial_solve(
    residual: np.ndarray,
    decoder: np.ndarray,
    local_mask: np.ndarray,
    ridge: float,
) -> np.ndarray:
    return fixed_decoder_ridge(
        residual[:, local_mask], decoder[:, local_mask], ridge
    )


def _b1_probe(
    *,
    expression: np.ndarray,
    sample_ordinals: np.ndarray,
    labels: np.ndarray,
    sample_ids: list[str],
    full: dict[str, np.ndarray],
    decoder: np.ndarray,
    trunk,
    private,
    score_indices: np.ndarray,
    mask_token: float,
    ridge: float,
    replicates: int,
    mask_ratio: float,
    mask_seed: int,
    batch_size: int,
    device: torch.device,
) -> dict[str, np.ndarray]:
    count = max(1, int(len(score_indices) * mask_ratio))
    behavioral, geometric, combined = [], [], []
    conditions, leverage = [], []
    logged = np.log1p(np.asarray(expression, dtype=np.float32))
    score_tensor = torch.as_tensor(score_indices, device=device, dtype=torch.long)
    for replicate in range(replicates):
        masks = []
        for sample_id in sample_ids:
            rng = np.random.default_rng(
                stable_seed(mask_seed, "stage2b_b1", sample_id, replicate)
            )
            masks.append(
                np.sort(
                    rng.choice(len(score_indices), count, replace=False)
                ).astype(np.int64)
            )
        behavior_rows, geometry_rows, combined_rows = [], [], []
        condition_rows, leverage_rows = [], []
        with torch.inference_mode():
            for start in range(0, len(logged), batch_size):
                stop = min(len(logged), start + batch_size)
                truth = torch.from_numpy(logged[start:stop]).to(device)
                masked = truth.clone()
                local_batch = masks[start:stop]
                for row, local in enumerate(local_batch):
                    global_index = score_tensor[
                        torch.as_tensor(local, device=device, dtype=torch.long)
                    ]
                    masked[row].index_fill_(0, global_index, float(mask_token))
                hidden = trunk.encode(masked)
                pooled = trunk.decode(hidden).index_select(1, score_tensor)
                label = torch.as_tensor(
                    labels[start:stop], device=device, dtype=torch.long
                )
                private_residual, _ = private(hidden, masked, label)
                truth_score = truth.index_select(1, score_tensor)
                partial_residual = (
                    truth_score - pooled - private_residual
                ).detach().cpu().float().numpy()
                for offset, local in enumerate(local_batch):
                    row = start + offset
                    behavior_rows.append(
                        fixed_decoder_ridge(
                            partial_residual[offset : offset + 1],
                            decoder,
                            ridge,
                        )[0]
                    )
                    geometry_rows.append(
                        _partial_solve(
                            full["r_full"][row : row + 1],
                            decoder,
                            local,
                            ridge,
                        )[0]
                    )
                    combined_rows.append(
                        _partial_solve(
                            partial_residual[offset : offset + 1],
                            decoder,
                            local,
                            ridge,
                        )[0]
                    )
                    selected = decoder[:, local].astype(np.float64)
                    gram = selected @ selected.T
                    regularized = gram + ridge * np.eye(len(gram))
                    condition_rows.append(float(np.linalg.cond(regularized)))
                    hat = selected.T @ np.linalg.solve(regularized, selected)
                    leverage_rows.append(float(np.max(np.diag(hat))))
        behavioral.append(np.asarray(behavior_rows, dtype=np.float32))
        geometric.append(np.asarray(geometry_rows, dtype=np.float32))
        combined.append(np.asarray(combined_rows, dtype=np.float32))
        conditions.append(np.asarray(condition_rows, dtype=np.float32))
        leverage.append(np.asarray(leverage_rows, dtype=np.float32))
    return {
        "sample_ordinal": sample_ordinals.astype(np.int64),
        "behavioral_coefficients": np.stack(behavioral, axis=1),
        "geometric_coefficients": np.stack(geometric, axis=1),
        "combined_legacy_coefficients": np.stack(combined, axis=1),
        "gram_condition_number": np.stack(conditions, axis=1),
        "maximum_leverage": np.stack(leverage, axis=1),
    }


def extract(args: argparse.Namespace) -> dict[str, Any]:
    protocol_path, protocol = _load_protocol(args)
    training, score_indices, gene_names, decoder, _ = _verify_common(args, protocol)
    ridge_path = Path(args.ridge_selection_report)
    ridge_report = json.loads(ridge_path.read_text())
    if (
        ridge_report.get("status") != "complete"
        or ridge_report.get("protocol_sha256") != sha256_file(protocol_path)
    ):
        raise ValueError("ridge-selection report does not match protocol")
    ridge = float(ridge_report["selected_ridge_lambda"])
    if ridge not in protocol["ridge_selection"]["grid"]:
        raise ValueError("selected ridge is outside frozen grid")
    selected = _select_rows(training, args.max_samples_per_organ)
    expression, info = load_expression_rows(
        args.expression_parquet, selected["sample_id"].astype(str).tolist()
    )
    validate_expression_metadata(
        args.expression_parquet,
        info.gene_columns,
        metadata_path=args.expression_metadata,
    )
    if list(info.gene_columns) != gene_names:
        raise ValueError("expression gene order differs from axis definitions")
    seed_everything(args.seed, deterministic=True)
    device = torch.device(args.device)
    trunk, private, _ = _load_seed_models(
        seed=args.seed,
        pooled_path=Path(args.pooled_checkpoint),
        private_path=Path(args.private_checkpoint),
        protocol=protocol,
        score_indices=score_indices,
        device=device,
    )
    labels = selected["organ_k8"].to_numpy(dtype=np.int64)
    inferred = _infer(
        expression=expression,
        labels=labels,
        trunk=trunk,
        private=private,
        score_indices=score_indices,
        mask_token=float(protocol["canonical_cache"]["mask_token"]),
        batch_size=int(protocol["canonical_cache"]["fixed_batch_size"]),
        device=device,
    )
    probe_rows = min(
        int(protocol["canonical_cache"]["determinism_probe_samples"]),
        len(selected),
    )
    repeated = _infer(
        expression=expression[:probe_rows],
        labels=labels[:probe_rows],
        trunk=trunk,
        private=private,
        score_indices=score_indices,
        mask_token=float(protocol["canonical_cache"]["mask_token"]),
        batch_size=int(protocol["canonical_cache"]["fixed_batch_size"]),
        device=device,
    )
    for name in inferred:
        if not np.array_equal(inferred[name][:probe_rows], repeated[name]):
            raise RuntimeError(f"determinism probe failed for {name}")
    inferred["c_canon"] = fixed_decoder_ridge(
        inferred["r_full"], decoder, ridge
    )
    inferred["sample_ordinal"] = selected.index.to_numpy(dtype=np.int64)
    inferred["organ_label"] = labels
    inferred["pooled_mse"] = np.mean(
        np.square(inferred["truth_score"] - inferred["pooled_prediction"]), axis=1
    ).astype(np.float32)
    inferred["private_mse"] = np.mean(
        np.square(
            inferred["truth_score"]
            - inferred["pooled_prediction"]
            - inferred["private_prediction"]
        ),
        axis=1,
    ).astype(np.float32)
    sample_keys = []
    for sample_id in selected["sample_id"].astype(str):
        key = CanonicalCacheKey(
            sample_id=sample_id,
            trunk_checkpoint_sha256=protocol["inputs"]["pooled_checkpoint_sha256"][
                str(args.seed)
            ],
            manifest_sha256=protocol["inputs"]["manifest_sha256"],
            score_index_sha256=protocol["inputs"]["score_index_sha256"],
            decoder_sha256=protocol["inputs"]["program_decoder_sha256"],
            mask_token_id=f"float:{float(protocol['canonical_cache']['mask_token'])}",
            preprocessing_version=protocol["canonical_cache"][
                "preprocessing_version"
            ],
            ridge_lambda=ridge,
            dtype_policy=protocol["canonical_cache"]["dtype_policy"],
        )
        sample_keys.append(np.frombuffer(bytes.fromhex(key.sha256()), dtype=np.uint8))
    inferred["sample_cache_key_sha256"] = np.stack(sample_keys)

    b1_frame = (
        selected.groupby("organ_k8", sort=True, group_keys=False)
        .head(args.b1_samples_per_organ)
        .sort_values("sample_id")
    )
    selected_position = {
        sample_id: index
        for index, sample_id in enumerate(selected["sample_id"].astype(str))
    }
    b1_positions = np.asarray(
        [selected_position[value] for value in b1_frame["sample_id"].astype(str)],
        dtype=np.int64,
    )
    b1 = _b1_probe(
        expression=expression[b1_positions],
        sample_ordinals=b1_frame.index.to_numpy(dtype=np.int64),
        labels=b1_frame["organ_k8"].to_numpy(dtype=np.int64),
        sample_ids=b1_frame["sample_id"].astype(str).tolist(),
        full={name: value[b1_positions] for name, value in inferred.items() if len(value) == len(selected)},
        decoder=decoder,
        trunk=trunk,
        private=private,
        score_indices=score_indices,
        mask_token=float(protocol["canonical_cache"]["mask_token"]),
        ridge=ridge,
        replicates=int(protocol["b1_mask_decomposition"]["replicates"]),
        mask_ratio=float(protocol["b1_mask_decomposition"]["partial_mask_ratio"]),
        mask_seed=int(protocol["b1_mask_decomposition"]["mask_seed"]),
        batch_size=int(protocol["canonical_cache"]["fixed_batch_size"]),
        device=device,
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    cache_path = output_dir / "canonical_cache.npz"
    b1_path = output_dir / "b1_mask_probe.npz"
    np.savez_compressed(cache_path, **inferred)
    np.savez_compressed(b1_path, **b1)
    metadata = {
        "schema_version": 1,
        "status": "complete",
        "mechanical_only": bool(args.mechanical_only),
        "seed": args.seed,
        "protocol_sha256": sha256_file(protocol_path),
        "ridge_selection_report_sha256": sha256_file(ridge_path),
        "ridge_lambda": ridge,
        "rows": len(selected),
        "b1_rows": len(b1_frame),
        "determinism_probe_rows": probe_rows,
        "determinism": "bitwise_identical",
        "canonical_reconstruction_mse": reconstruction_mse(
            inferred["r_full"], inferred["c_canon"], decoder
        ),
        "hashes": {
            "canonical_cache_sha256": sha256_file(cache_path),
            "b1_mask_probe_sha256": sha256_file(b1_path),
            "canonical_arrays": {
                name: array_sha256(value) for name, value in inferred.items()
            },
            "b1_arrays": {name: array_sha256(value) for name, value in b1.items()},
        },
        "completed_at_utc": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
    }
    metadata_path = output_dir / "run_metadata.json"
    _atomic_json(metadata_path, metadata)
    lines = [
        f"{sha256_file(path)}  {path.name}"
        for path in (cache_path, b1_path, metadata_path)
    ]
    (output_dir / "IMMUTABLE_SHA256SUMS").write_text("\n".join(lines) + "\n")
    (output_dir / "COMPLETE").touch()
    return metadata


def _common_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--expression-parquet", required=True)
    parser.add_argument("--expression-metadata", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--axis-definitions", required=True)
    parser.add_argument("--basis-bundle", required=True)
    parser.add_argument("--device", required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    ridge = subparsers.add_parser("select-ridge")
    _common_parser(ridge)
    ridge.add_argument("--pooled-checkpoint", action="append", required=True)
    ridge.add_argument("--private-checkpoint", action="append", required=True)
    ridge.add_argument("--mechanical-only", action="store_true")
    ridge.add_argument("--output", required=True)
    cache = subparsers.add_parser("extract")
    _common_parser(cache)
    cache.add_argument("--seed", type=int, choices=SEEDS, required=True)
    cache.add_argument("--pooled-checkpoint", required=True)
    cache.add_argument("--private-checkpoint", required=True)
    cache.add_argument("--ridge-selection-report", required=True)
    cache.add_argument("--max-samples-per-organ", type=int)
    cache.add_argument("--b1-samples-per-organ", type=int, default=32)
    cache.add_argument("--mechanical-only", action="store_true")
    cache.add_argument("--output-dir", required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = select_ridge(args) if args.command == "select-ridge" else extract(args)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
