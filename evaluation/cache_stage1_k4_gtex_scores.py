#!/usr/bin/env python3
"""Score the frozen Stage 1 K4 candidate once on sealed GTEx expression.

Only compact per-sample MSE and residual-correlation metrics are retained.
Full target or prediction vectors are deliberately not serialized.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import torch
from torch import nn


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

from train_latent_moe import ResidualExpert, load_frozen_trunk  # noqa: E402
from train_manifest import load_expression_rows  # noqa: E402
from freeze_stage1_k4_final_candidate import validate_portable_candidate  # noqa: E402
from headroom_metrics import mse_rows, pearson_rows  # noqa: E402
from stage1_k4_gtex_common import (  # noqa: E402
    ACTIVE_ORGANS,
    FALLBACK_LABEL,
    ORGAN_TO_EXPERT,
    ORGANS,
    PARTITION_SEEDS,
    SEEDS,
    atomic_json,
    deterministic_random_assignments,
    load_frozen_protocol,
    sha256_file,
    sha256_lines,
)


class ExpertBank(nn.Module):
    def __init__(self, hidden_dim: int, adapter_dim: int, num_experts: int):
        super().__init__()
        self.experts = nn.ModuleList(
            ResidualExpert(hidden_dim, adapter_dim) for _ in range(num_experts)
        )

    def forward(self, hidden: torch.Tensor) -> torch.Tensor:
        return torch.stack([expert(hidden) for expert in self.experts], dim=1)


def _device(name: str) -> torch.device:
    if name == "auto":
        return torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    device = torch.device(name)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable")
    return device


def _load_bank(
    candidate_root: Path,
    manifest: dict[str, Any],
    *,
    seed: int,
    axis: str,
    hidden_dim: int,
    device: torch.device,
) -> ExpertBank:
    record = manifest["artifacts"]["seeds"][str(seed)]["banks"][axis]
    checkpoint_path = candidate_root / record["checkpoint"]
    metadata_path = candidate_root / record["metadata"]
    metadata = json.loads(metadata_path.read_text())
    if (
        metadata.get("status") != "complete"
        or metadata.get("axis") != axis
        or int(metadata.get("training_seed", -1)) != seed
        or metadata.get("test_accessed") is not False
        or metadata.get("internal_efficacy_scoring") is not False
    ):
        raise ValueError(f"candidate bank header is invalid: seed={seed} axis={axis}")
    config = metadata["config"]
    expected_experts = 1 if axis == "pooled_adapter" else 4
    if (
        int(config.get("num_experts", -1)) != expected_experts
        or int(config.get("final_update", -1)) != 1500
        or int(config.get("score_gene_count", -1)) != 4634
        or config.get("checkpoint_policy") != "predetermined_final_update"
    ):
        raise ValueError(f"candidate bank config is invalid: seed={seed} axis={axis}")
    try:
        checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    except TypeError:
        checkpoint = torch.load(checkpoint_path, map_location="cpu")
    if (
        checkpoint.get("axis") != axis
        or int(checkpoint.get("training_seed", -1)) != seed
        or checkpoint.get("config") != config
    ):
        raise ValueError(f"candidate checkpoint metadata mismatch: {seed}/{axis}")
    bank = ExpertBank(
        hidden_dim, int(config["adapter_dim"]), num_experts=expected_experts
    )
    bank.load_state_dict(checkpoint["expert_state_dict"], strict=True)
    bank.requires_grad_(False)
    bank.eval().to(device)
    return bank


def _load_router(
    path: Path, genes: list[str], score_indices: np.ndarray, mask_token: float
) -> dict[str, np.ndarray]:
    required = {
        "gene_names",
        "score_gene_indices",
        "mask_token",
        "classes",
        "scaler_mean",
        "scaler_scale",
        "coefficients",
        "intercepts",
        "active_adapter_organs",
        "fallback_organ",
    }
    with np.load(path, allow_pickle=False) as archive:
        missing = sorted(required - set(archive.files))
        if missing:
            raise ValueError(f"router lacks arrays: {missing}")
        router = {name: np.asarray(archive[name]) for name in required}
    if router["gene_names"].astype(str).tolist() != genes:
        raise ValueError("router gene order differs from frozen trunk")
    if not np.array_equal(router["score_gene_indices"], score_indices):
        raise ValueError("router score indices differ from frozen axes")
    if float(router["mask_token"].item()) != mask_token:
        raise ValueError("router mask token differs from frozen trunk")
    if tuple(router["classes"].astype(str)) != ORGANS:
        raise ValueError("router class order changed")
    if tuple(router["active_adapter_organs"].astype(str)) != ACTIVE_ORGANS:
        raise ValueError("router active organ order changed")
    if str(router["fallback_organ"].item()) != "adipose":
        raise ValueError("router fallback organ changed")
    if np.any(router["scaler_scale"] <= 0):
        raise ValueError("router contains a nonpositive scale")
    return router


def _router_predict(masked: np.ndarray, router: dict[str, np.ndarray]) -> np.ndarray:
    scaled = (
        masked.astype(np.float64) - router["scaler_mean"].astype(np.float64)
    ) / router["scaler_scale"].astype(np.float64)
    logits = (
        scaled @ router["coefficients"].astype(np.float64).T
        + router["intercepts"].astype(np.float64)
    )
    return router["classes"].astype(str)[np.argmax(logits, axis=1)]


def _dispatch(
    base_score: np.ndarray, residual_score: np.ndarray, labels: np.ndarray
) -> np.ndarray:
    output = base_score.copy()
    active = labels >= 0
    if active.any():
        output[active] += residual_score[
            np.flatnonzero(active), labels[active].astype(np.int64)
        ]
    return output


def _add_metrics(
    output: dict[str, np.ndarray],
    name: str,
    prediction: np.ndarray,
    target: np.ndarray,
    baseline: np.ndarray,
) -> None:
    output[f"{name}__mse"] = mse_rows(prediction, target).astype(np.float64)
    correlation = pearson_rows(prediction - baseline, target - baseline)
    if not np.isfinite(correlation).all():
        raise ValueError(f"{name} residual correlation is nonfinite")
    output[f"{name}__residual_pearson"] = correlation.astype(np.float64)


def _development_baseline(
    candidate_root: Path,
    manifest: dict[str, Any],
    genes: list[str],
    score_indices: np.ndarray,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    artifacts = manifest["artifacts"]
    expression_path = candidate_root / artifacts["development_expression"]
    manifest_path = candidate_root / artifacts["development_extracted_manifest"]
    rows = pd.read_parquet(manifest_path)
    required = {"sample_id", "organ"}
    if not required.issubset(rows.columns):
        raise ValueError("development manifest lacks baseline columns")
    rows = rows.sort_values("sample_id").reset_index(drop=True)
    expression, info = load_expression_rows(
        expression_path, rows["sample_id"].astype(str).tolist()
    )
    if list(info.gene_columns) != genes:
        raise ValueError("development expression gene order changed")
    if np.any(expression < 0) or not np.isfinite(expression).all():
        raise ValueError("development TPM contains invalid values")
    score = np.log1p(expression[:, score_indices]).astype(np.float32)
    baseline: dict[str, np.ndarray] = {}
    for organ in ORGANS:
        selected = rows["organ"].astype(str).eq(organ).to_numpy()
        if not selected.any():
            raise ValueError(f"development baseline lacks {organ}")
        baseline[organ] = score[selected].mean(axis=0, dtype=np.float64).astype(
            np.float32
        )
    report = {
        "definition": "development-refit-only organ-specific mean log1p score panel",
        "development_samples": len(rows),
        "development_sample_ids_sha256": sha256_lines(rows["sample_id"]),
        "development_expression_sha256": sha256_file(expression_path),
        "development_manifest_sha256": sha256_file(manifest_path),
        "organ_counts": {
            organ: int(rows["organ"].astype(str).eq(organ).sum()) for organ in ORGANS
        },
        "external_targets_used_for_fit": False,
    }
    return baseline, report


def build_scores(args: argparse.Namespace) -> dict[str, Any]:
    protocol = load_frozen_protocol(args.protocol, args.expected_protocol_sha256)
    candidate_manifest_path = Path(args.candidate_manifest)
    expected_commit = protocol["model"]["candidate_code_commit"]
    manifest = validate_portable_candidate(
        candidate_manifest_path, expected_code_commit=expected_commit
    )
    if sha256_file(candidate_manifest_path) != protocol["model"]["candidate_manifest_sha256"]:
        raise ValueError("candidate manifest differs from GTEx protocol")
    candidate_root = candidate_manifest_path.parent
    extraction_dir = Path(args.extraction_dir)
    extraction_report_path = extraction_dir / "extraction_report.json"
    expression_path = extraction_dir / "expression.parquet"
    if not (extraction_dir / "EXTRACTION_COMPLETE").is_file():
        raise ValueError("GTEx extraction is incomplete")
    extraction_report = json.loads(extraction_report_path.read_text())
    if (
        extraction_report.get("status") != "complete"
        or extraction_report.get("protocol_sha256") != sha256_file(args.protocol)
        or extraction_report.get("expression_sha256") != sha256_file(expression_path)
    ):
        raise ValueError("GTEx extraction report is invalid")
    header_dir = Path(args.header_dir)
    sealed_path = header_dir / "sealed_cohort.parquet"
    cohort = pd.read_parquet(sealed_path).sort_values("sample_id").reset_index(drop=True)
    if extraction_report["sealed_cohort_sha256"] != sha256_file(sealed_path):
        raise ValueError("sealed cohort differs from extraction")

    genes_path = candidate_root / manifest["artifacts"]["development_genes"]
    genes = genes_path.read_text().splitlines()
    pooled_path = candidate_root / manifest["artifacts"]["pooled_checkpoint"]
    axes_path = candidate_root / manifest["artifacts"]["axis_definitions"]
    router_path = candidate_root / manifest["artifacts"]["router_artifact"]
    random_mapping_path = candidate_root / manifest["artifacts"]["random_mappings"]
    device = _device(args.device)
    trunk, config, _ = load_frozen_trunk(pooled_path, device)
    if config.get("normalization") != "log1p_tpm" or config["gene_list"] != genes:
        raise ValueError("frozen trunk expression contract changed")
    mask_token = float(config["mask_token"])
    with np.load(axes_path, allow_pickle=False) as axes:
        score_indices = np.asarray(axes["score_gene_indices"], dtype=np.int64)
        if axes["gene_names"].astype(str).tolist() != genes:
            raise ValueError("frozen axis gene order changed")
    if len(score_indices) != 4634:
        raise ValueError("frozen score panel size changed")
    router = _load_router(router_path, genes, score_indices, mask_token)
    random_mapping = json.loads(random_mapping_path.read_text())["mappings"]
    baseline, baseline_report = _development_baseline(
        candidate_root, manifest, genes, score_indices
    )

    banks: dict[int, dict[str, ExpertBank]] = {}
    hidden_dim = int(trunk.gene_embedding.embedding_dim)
    for seed in SEEDS:
        banks[seed] = {
            axis: _load_bank(
                candidate_root,
                manifest,
                seed=seed,
                axis=axis,
                hidden_dim=hidden_dim,
                device=device,
            )
            for axis in (
                "organ_k4_final",
                "pooled_adapter",
                *[
                    f"random_group_k4_final_p{partition}"
                    for partition in PARTITION_SEEDS
                ],
            )
        }

    metadata = cohort[
        ["sample_id", "donor_id", "organ", "tissue_site"]
    ].copy()
    metadata["true_expert"] = metadata["organ"].map(ORGAN_TO_EXPERT).fillna(
        FALLBACK_LABEL
    ).astype(np.int64)
    for partition in PARTITION_SEEDS:
        metadata[f"p{partition}_assigned_expert"] = deterministic_random_assignments(
            metadata, partition
        )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    output_path = output_dir / "gtex_sample_scores.parquet"
    writer: pq.ParquetWriter | None = None
    source = pq.ParquetFile(expression_path)
    if source.schema_arrow.names != ["sample_id", *genes]:
        raise ValueError("GTEx expression columns differ from frozen gene order")
    offset = 0
    trunk.eval()
    score_tensor = torch.as_tensor(score_indices, device=device)
    with torch.inference_mode():
        try:
            for batch in source.iter_batches(batch_size=int(args.batch_size)):
                frame = batch.to_pandas()
                batch_ids = frame.pop("sample_id").astype(str).to_numpy()
                expected = metadata.iloc[offset : offset + len(frame)]
                if not np.array_equal(batch_ids, expected["sample_id"].astype(str)):
                    raise ValueError("GTEx expression and sealed cohort order differ")
                expression = frame.to_numpy(dtype=np.float32)
                if expression.shape[1] != len(genes):
                    raise ValueError("GTEx expression gene count differs from candidate")
                if np.any(expression < 0) or not np.isfinite(expression).all():
                    raise ValueError("GTEx TPM contains invalid values")
                truth = np.log1p(expression).astype(np.float32)
                masked = truth.copy()
                masked[:, score_indices] = np.float32(mask_token)
                predicted_organs = _router_predict(masked, router)
                true_labels = expected["true_expert"].to_numpy(dtype=np.int64)
                blind_labels = np.asarray(
                    [ORGAN_TO_EXPERT.get(organ, FALLBACK_LABEL) for organ in predicted_organs],
                    dtype=np.int64,
                )
                target = truth[:, score_indices]
                baseline_batch = np.stack(
                    [baseline[organ] for organ in expected["organ"].astype(str)]
                )
                tensor = torch.from_numpy(masked).to(device)
                hidden = trunk.encode(tensor)
                base = trunk.decode(hidden)
                base_score = base.index_select(1, score_tensor).float().cpu().numpy()
                metrics: dict[str, np.ndarray] = {}
                _add_metrics(metrics, "pooled", base_score, target, baseline_batch)
                for seed in SEEDS:
                    seed_banks = banks[seed]
                    organ_residual = seed_banks["organ_k4_final"](hidden).index_select(
                        2, score_tensor
                    ).float().cpu().numpy()
                    pooled_residual = seed_banks["pooled_adapter"](hidden)[
                        :, 0
                    ].index_select(1, score_tensor).float().cpu().numpy()
                    _add_metrics(
                        metrics,
                        f"seed{seed}__pooled_adapter",
                        base_score + pooled_residual,
                        target,
                        baseline_batch,
                    )
                    _add_metrics(
                        metrics,
                        f"seed{seed}__true_k4",
                        _dispatch(base_score, organ_residual, true_labels),
                        target,
                        baseline_batch,
                    )
                    _add_metrics(
                        metrics,
                        f"seed{seed}__blind_k4",
                        _dispatch(base_score, organ_residual, blind_labels),
                        target,
                        baseline_batch,
                    )
                    for partition in PARTITION_SEEDS:
                        axis = f"random_group_k4_final_p{partition}"
                        random_residual = seed_banks[axis](hidden).index_select(
                            2, score_tensor
                        ).float().cpu().numpy()
                        assigned = expected[
                            f"p{partition}_assigned_expert"
                        ].to_numpy(dtype=np.int64)
                        mapping = random_mapping[str(partition)]["organ_to_expert"]
                        mapped = np.asarray(
                            [int(mapping[organ]) for organ in predicted_organs],
                            dtype=np.int64,
                        )
                        _add_metrics(
                            metrics,
                            f"seed{seed}__random_p{partition}_assigned",
                            _dispatch(base_score, random_residual, assigned),
                            target,
                            baseline_batch,
                        )
                        _add_metrics(
                            metrics,
                            f"seed{seed}__random_p{partition}_mapped",
                            _dispatch(base_score, random_residual, mapped),
                            target,
                            baseline_batch,
                        )
                scored = expected.reset_index(drop=True).copy()
                scored["router_predicted_organ"] = predicted_organs
                scored["router_correct"] = (
                    predicted_organs == expected["organ"].astype(str).to_numpy()
                )
                for name, values in metrics.items():
                    scored[name] = values
                table = pa.Table.from_pandas(scored, preserve_index=False)
                if writer is None:
                    writer = pq.ParquetWriter(output_path, table.schema)
                writer.write_table(table, row_group_size=len(table))
                offset += len(frame)
        finally:
            if writer is not None:
                writer.close()
    if offset != len(metadata):
        raise ValueError("GTEx expression row count differs from sealed cohort")

    report = {
        "schema_version": 1,
        "status": "complete",
        "one_time_external_scoring": True,
        "model_fitting": False,
        "checkpoint_selection": False,
        "full_predictions_serialized": False,
        "protocol_sha256": sha256_file(args.protocol),
        "candidate_manifest_sha256": sha256_file(candidate_manifest_path),
        "extraction_report_sha256": sha256_file(extraction_report_path),
        "expression_sha256": sha256_file(expression_path),
        "sealed_cohort_sha256": sha256_file(sealed_path),
        "score_cache_sha256": sha256_file(output_path),
        "sample_order_sha256": sha256_lines(metadata["sample_id"]),
        "samples": len(metadata),
        "donors": int(metadata["donor_id"].nunique()),
        "training_seeds": list(SEEDS),
        "partition_seeds": list(PARTITION_SEEDS),
        "score_genes": len(score_indices),
        "baseline": baseline_report,
        "target_hiding": {
            "score_genes_replaced_by_mask_token": True,
            "mask_token": mask_token,
            "same_masked_features_for_router_and_models": True,
        },
        "random_assignment": protocol["controls"]["assigned_random_algorithm"],
        "artifacts": {"sample_scores": str(output_path.resolve())},
    }
    atomic_json(output_dir / "score_report.json", report)
    (output_dir / "SCORING_COMPLETE").write_text("one-time frozen scoring complete\n")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--candidate-manifest", required=True)
    parser.add_argument("--header-dir", required=True)
    parser.add_argument("--extraction-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--device", default="auto")
    return parser


def main() -> None:
    print(json.dumps(build_scores(build_parser().parse_args()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
