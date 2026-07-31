#!/usr/bin/env python3
"""Cache frozen organ-MoE downstream embeddings on the OSDR development cohort."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

from final_organ_embedding import (  # noqa: E402
    compose_embeddings,
    expert_bottleneck_summaries,
    observed_mean,
)
from train_latent_moe import load_frozen_trunk  # noqa: E402
from cache_gtex_to_archs4_lockbox_scores import (  # noqa: E402
    ORGANS,
    SEEDS,
    _artifact,
    _load_bank,
    _router,
    sha256_array,
    sha256_file,
    write_deterministic_npz,
)
from evaluate_osdr import load_coverage_artifact  # noqa: E402


CONDITIONS = (
    "pooled_hidden",
    "pooled_hidden_plus_router",
    "true_organ_embedding",
    "blind_router_hard_embedding",
    "blind_router_soft_embedding",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--candidate-ledger", required=True)
    parser.add_argument("--training-root", required=True)
    parser.add_argument("--cohort-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--seeds", nargs="+", type=int, default=list(SEEDS))
    args = parser.parse_args()

    protocol_path = Path(args.protocol)
    ledger_path = Path(args.candidate_ledger)
    cohort_root = Path(args.cohort_root)
    output_dir = Path(args.output_dir)
    if sha256_file(protocol_path) != args.expected_protocol_sha256:
        raise ValueError("embedding protocol SHA256 mismatch")
    protocol = json.loads(protocol_path.read_text())
    if protocol.get("status") != "frozen_before_final_organ_embedding_development_outcome_access":
        raise ValueError("embedding development protocol is not frozen")
    if protocol["inputs"]["stage1_candidate_ledger_sha256"] != sha256_file(ledger_path):
        raise ValueError("candidate ledger hash mismatch")
    seeds = tuple(args.seeds)
    if tuple(protocol["inputs"]["seeds"]) != SEEDS or not set(seeds).issubset(SEEDS):
        raise ValueError("requested seeds are outside the frozen family")
    if output_dir.exists():
        raise FileExistsError(output_dir)
    output_dir.mkdir(parents=True)

    qc_report_path = cohort_root / "downstream_qc_report.json"
    qc_report = json.loads(qc_report_path.read_text())
    if qc_report.get("status") != "complete" or qc_report.get("no_replacements") is not True:
        raise ValueError("OSDR cohort QC is incomplete")
    expression_path = cohort_root / "osdr_expression_v3.parquet"
    coverage_path = cohort_root / "osdr_coverage_v3.npz"
    retained_path = cohort_root / "retained_cohort.csv"
    for path, key in (
        (expression_path, "expression_sha256"),
        (coverage_path, "coverage_sha256"),
        (retained_path, "retained_cohort_sha256"),
    ):
        if sha256_file(path) != qc_report["hashes"][key]:
            raise ValueError(f"OSDR cohort artifact hash mismatch: {path.name}")

    expression = pd.read_parquet(expression_path)
    expression.index = expression.index.astype(str)
    all_sample_ids = expression.index.to_numpy(dtype=str)
    metadata_columns = {"sample_name", "condition", "spaceflight", "study_id", "species"}
    genes = [column for column in expression.columns if column not in metadata_columns]
    full_coverage = load_coverage_artifact(coverage_path, all_sample_ids, genes)
    retained = pd.read_csv(retained_path, keep_default_na=False)
    retained = retained.rename(columns={retained.columns[0]: "sample_id"}).set_index("sample_id")
    retained = retained[
        retained["valid_study_organ_contrast"].astype(str).str.lower().eq("true")
    ]
    positions = pd.Index(all_sample_ids).get_indexer(retained.index)
    if np.any(positions < 0):
        raise ValueError("retained OSDR membership is absent from coverage cache")
    coverage = full_coverage[positions]
    expression = expression.reindex(retained.index)
    if expression.isna().any().any():
        raise ValueError("retained OSDR membership is absent from expression cache")
    truth = expression[genes].to_numpy(dtype=np.float32)
    if not np.isfinite(truth).all():
        raise ValueError("OSDR expression contains nonfinite values")

    ledger = json.loads(ledger_path.read_text())
    training_root = Path(args.training_root)
    router_path = _artifact(training_root, ledger["router"]["artifact"], "router")
    with np.load(router_path, allow_pickle=False) as archive:
        score_indices = archive["score_gene_indices"].astype(np.int64)
        mask_token = float(archive["mask_token"])
        if archive["gene_names"].astype(str).tolist() != genes:
            raise ValueError("OSDR gene order differs from the frozen Stage 1 router")
    masked = truth.copy()
    masked[~coverage] = np.float32(mask_token)
    masked[:, score_indices] = np.float32(mask_token)
    probabilities, verified_indices = _router(router_path, genes, masked)
    if not np.array_equal(score_indices, verified_indices):
        raise ValueError("router score panel changed")

    organs = retained["organ"].to_numpy(dtype=str)
    groups = retained["study_id"].to_numpy(dtype=str)
    labels = retained["frozen_label"].astype(int).to_numpy()
    organ_labels = np.asarray([ORGANS.index(value) for value in organs], dtype=np.int64)
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    entries = {int(item["seed"]): item for item in ledger["seed_candidates"]}
    reports = {}

    for seed in seeds:
        entry = entries[seed]
        pooled_path = _artifact(training_root, entry["pooled"]["checkpoint"], f"{seed}/pooled")
        trunk, config, _ = load_frozen_trunk(pooled_path, device)
        if config["gene_list"] != genes or config["normalization"] != "log1p_tpm":
            raise ValueError(f"seed {seed} expression contract changed")
        hidden_dim = int(trunk.gene_embedding.embedding_dim)
        bank = _load_bank(
            training_root,
            entry["banks"]["organ_k8"],
            axis="organ_k8",
            seed=seed,
            hidden_dim=hidden_dim,
            device=device,
        )
        features = {
            "pooled_hidden": np.empty((len(masked), hidden_dim), dtype=np.float32),
            "pooled_hidden_plus_router": np.empty((len(masked), hidden_dim + 8), dtype=np.float32),
            "true_organ_embedding": np.empty((len(masked), hidden_dim + 64 + 8), dtype=np.float32),
            "blind_router_hard_embedding": np.empty((len(masked), hidden_dim + 64 + 8), dtype=np.float32),
            "blind_router_soft_embedding": np.empty((len(masked), hidden_dim + 64 + 8), dtype=np.float32),
        }
        with torch.inference_mode():
            for start in range(0, len(masked), args.batch_size):
                stop = min(start + args.batch_size, len(masked))
                batch = torch.from_numpy(masked[start:stop]).to(device)
                hidden = trunk.encode(batch)
                observed = batch.ne(mask_token)
                pooled_summary = observed_mean(hidden, observed)
                expert_summary = expert_bottleneck_summaries(
                    bank.experts, hidden, observed
                )
                composed = compose_embeddings(
                    pooled_summary,
                    expert_summary,
                    torch.from_numpy(probabilities[start:stop]).to(device),
                    torch.from_numpy(organ_labels[start:stop]).to(device),
                )
                for name, values in composed.items():
                    features[name][start:stop] = values.float().cpu().numpy()
        arrays = {
            "sample_ids": expression.index.to_numpy(dtype=str),
            "groups": groups,
            "organs": organs,
            "labels": labels.astype(np.int64),
            "router_probabilities": probabilities.astype(np.float32),
            **{f"feature__{name}": value for name, value in features.items()},
        }
        if not all(
            np.isfinite(value).all()
            for value in arrays.values()
            if np.asarray(value).dtype.kind not in {"U", "S", "O"}
        ):
            raise RuntimeError(f"seed {seed} embedding contains nonfinite values")
        metadata = {
            "schema_version": 1,
            "status": "complete",
            "seed": seed,
            "conditions": list(CONDITIONS),
            "protocol_sha256": sha256_file(protocol_path),
            "candidate_ledger_sha256": sha256_file(ledger_path),
            "cohort_qc_report_sha256": sha256_file(qc_report_path),
            "model_fitting_performed": False,
            "checkpoint_updates": False,
            "best_seed_selection": False,
            "content_sha256": {key: sha256_array(value) for key, value in arrays.items()},
        }
        arrays["metadata_json"] = np.asarray(json.dumps(metadata, sort_keys=True))
        output = output_dir / f"seed{seed}_features.npz"
        write_deterministic_npz(output, arrays)
        reports[str(seed)] = {**metadata, "output_sha256": sha256_file(output)}
        del trunk, bank
        if device.type == "cuda":
            torch.cuda.empty_cache()
    report = {
        "schema_version": 1,
        "status": "complete",
        "protocol_sha256": sha256_file(protocol_path),
        "n_samples": int(len(expression)),
        "n_studies": int(pd.Series(groups).nunique()),
        "seeds": reports,
    }
    (output_dir / "feature_cache_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    (output_dir / "COMPLETE").write_text("complete\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
