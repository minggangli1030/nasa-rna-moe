#!/usr/bin/env python3
"""Fit the target-hidden five-organ router for the frozen Stage-1 K4 candidate.

This is a fit-only operation over the already selected balanced-train plus
calibration development union.  It produces no accuracy or reconstruction
metric and accepts no test or external-data argument.
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


ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = ROOT / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from freeze_organ_k_router import (  # noqa: E402
    _fit_router,
    _sha256_array,
    _write_deterministic_npz,
    mask_score_genes,
)
from train_manifest import (  # noqa: E402
    load_expression_rows,
    read_manifest,
    select_manifest_rows,
    sha256_file,
    sha256_json,
    sha256_lines,
    validate_expression_metadata,
)


CANONICAL_ORGANS = (
    "adipose",
    "brain",
    "liver",
    "skeletal_muscle",
    "skin",
)


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _load_protocol(path: Path) -> dict[str, Any]:
    protocol = json.loads(path.read_text())
    evidence = protocol.get("evidence_label", {})
    firewall = protocol.get("firewall", {})
    prior = protocol.get("prior_evidence", {})
    if (
        evidence.get("label") != "final_refit_for_external_confirmation"
        or evidence.get("development_only") is not True
        or evidence.get("internal_efficacy_scoring") is not False
    ):
        raise ValueError("protocol does not authorize a metric-free final refit")
    if (
        firewall.get("test_access_allowed") is not False
        or firewall.get("external_access_allowed_during_refit") is not False
        or firewall.get("internal_efficacy_scoring_allowed") is not False
    ):
        raise ValueError("protocol firewall is not closed for final router fitting")
    if (
        prior.get("decision_branch") != "k4_robust"
        or prior.get("selected_candidate") != "k4_epe"
    ):
        raise ValueError("protocol does not freeze the selected K4-EPE candidate")
    return protocol


def _aligned_fit_frame(args: argparse.Namespace) -> pd.DataFrame:
    source = read_manifest(args.source_manifest)
    selection = select_manifest_rows(
        source,
        role="pooled",
        train_split=args.train_split,
        validation_split=args.calibration_split,
        train_filter_column=args.train_filter_column,
        sample_id_column=args.sample_id_column,
        split_column=args.source_split_column,
        organ_column=args.organ_column,
        group_column=args.group_column,
    )
    selected = pd.concat([selection.train, selection.validation], ignore_index=True)
    selected = selected[
        [args.sample_id_column, args.organ_column, args.group_column]
    ].copy()
    selected.columns = ["sample_id", "organ", "series_group_id"]
    for column in selected:
        if selected[column].isna().any():
            raise ValueError(f"selected fitting column {column!r} contains missing values")
        selected[column] = selected[column].astype(str)

    partition = pd.read_parquet(args.partition_manifest)
    required = {args.sample_id_column, args.organ_column, args.group_column, "fit_role"}
    missing = sorted(required - set(partition.columns))
    if missing:
        raise ValueError(f"final partition manifest lacks columns: {missing}")
    aligned = partition[
        [args.sample_id_column, args.organ_column, args.group_column]
    ].copy()
    aligned.columns = ["sample_id", "organ", "series_group_id"]
    for column in aligned:
        if aligned[column].isna().any():
            raise ValueError(f"partition fitting column {column!r} contains missing values")
        aligned[column] = aligned[column].astype(str)
    if not aligned.equals(selected):
        raise ValueError(
            "final partition rows do not exactly match balanced-train plus calibration"
        )
    if set(partition["fit_role"].astype(str)) != {"development_fit"}:
        raise ValueError("partition manifest contains a non-fitting role")
    if selected["sample_id"].duplicated().any():
        raise ValueError("final fitting sample IDs are not unique")
    if set(selected["organ"]) != set(CANONICAL_ORGANS):
        raise ValueError("final fitting data does not contain exactly five organs")
    if selected.groupby("series_group_id")["organ"].nunique().max() != 1:
        raise ValueError("a connected study spans router organ classes")
    return selected


def refit(args: argparse.Namespace) -> dict[str, Any]:
    paths = {
        "protocol": Path(args.protocol),
        "expression": Path(args.expression_parquet),
        "expression_metadata": Path(args.expression_metadata),
        "source_manifest": Path(args.source_manifest),
        "partition_manifest": Path(args.partition_manifest),
        "partition_report": Path(args.partition_report),
        "axis_definitions": Path(args.axis_definitions),
    }
    for path in paths.values():
        if not path.is_file():
            raise FileNotFoundError(path)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output_dir}")

    protocol = _load_protocol(paths["protocol"])
    data_contract = protocol["data"]
    router_contract = protocol.get("router", {})
    if int(args.router_seed) != int(router_contract.get("seed", -1)):
        raise ValueError("router seed differs from the frozen protocol")
    if float(args.mask_token) != float(data_contract.get("mask_token")):
        raise ValueError("router mask token differs from the frozen protocol")
    expected_hashes = {
        "expression": data_contract["development_expression_parquet_sha256"],
        "expression_metadata": data_contract[
            "development_expression_metadata_sha256"
        ],
        "source_manifest": data_contract["development_fit_manifest_sha256"],
        "axis_definitions": data_contract["axis_definitions_sha256"],
    }
    for name, expected in expected_hashes.items():
        if sha256_file(paths[name]) != expected:
            raise ValueError(f"{name} hash differs from the frozen protocol")

    partition_report = json.loads(paths["partition_report"].read_text())
    if (
        partition_report.get("status") != "complete"
        or partition_report.get("test_accessed") is not False
        or partition_report.get("internal_efficacy_scoring") is not False
    ):
        raise ValueError("final partition report is incomplete or violates the firewall")
    if partition_report.get("hashes", {}).get(
        "partition_manifest_sha256"
    ) != sha256_file(paths["partition_manifest"]):
        raise ValueError("partition report does not bind the final partition manifest")
    if partition_report.get("hashes", {}).get("protocol_sha256") != sha256_file(
        paths["protocol"]
    ):
        raise ValueError("partition report does not bind the final protocol")

    fit = _aligned_fit_frame(args)
    expected_n = int(data_contract["expected_fit_samples"])
    if len(fit) != expected_n:
        raise ValueError(f"expected {expected_n} fitting rows, found {len(fit)}")
    sample_ids = fit["sample_id"].to_numpy(dtype=str)
    organs = fit["organ"].to_numpy(dtype=str)
    groups = fit["series_group_id"].to_numpy(dtype=str)

    expression, expression_info = load_expression_rows(
        paths["expression"], sample_ids.tolist(), sample_id_column=args.sample_id_column
    )
    expression_contract = validate_expression_metadata(
        paths["expression"],
        expression_info.gene_columns,
        metadata_path=paths["expression_metadata"],
    )
    with np.load(paths["axis_definitions"], allow_pickle=False) as definitions:
        required = {"score_gene_indices", "gene_names"}
        if not required.issubset(definitions.files):
            raise ValueError("axis definitions lacks score genes or gene names")
        score_indices = np.asarray(definitions["score_gene_indices"], dtype=np.int64)
        definition_genes = np.asarray(definitions["gene_names"]).astype(str)
    genes = list(expression_info.gene_columns)
    if definition_genes.tolist() != genes:
        raise ValueError("axis-definition gene order differs from expression parquet")
    if len(genes) != int(data_contract["gene_count"]):
        raise ValueError("gene count differs from the frozen protocol")
    if len(score_indices) != int(data_contract["score_gene_count"]):
        raise ValueError("score-gene count differs from the frozen protocol")

    features = mask_score_genes(
        np.log1p(expression).astype(np.float32, copy=False),
        score_indices,
        args.mask_token,
    )
    if not np.all(features[:, score_indices] == np.float32(args.mask_token)):
        raise RuntimeError("router target-hiding assertion failed")
    model, sample_weights = _fit_router(
        features, organs, groups, seed=args.router_seed
    )
    scaler = model.named_steps["standardscaler"]
    classifier = model.named_steps["logisticregression"]
    classes = classifier.classes_.astype(str)
    if set(classes) != set(CANONICAL_ORGANS):
        raise RuntimeError("final router did not fit all five frozen classes")

    arrays = {
        "fit_sample_ids": sample_ids,
        "fit_organs": organs,
        "fit_series_group_id": groups,
        "gene_names": np.asarray(genes, dtype=str),
        "score_gene_indices": score_indices,
        "score_gene_names": np.asarray(genes, dtype=str)[score_indices],
        "mask_token": np.asarray(float(args.mask_token), dtype=np.float64),
        "classes": classes,
        "scaler_mean": scaler.mean_.astype(np.float64),
        "scaler_scale": scaler.scale_.astype(np.float64),
        "scaler_var": scaler.var_.astype(np.float64),
        "coefficients": classifier.coef_.astype(np.float64),
        "intercepts": classifier.intercept_.astype(np.float64),
        "n_iter": classifier.n_iter_.astype(np.int64),
        "sample_weight": np.asarray(sample_weights, dtype=np.float64),
        "active_adapter_organs": np.asarray(
            protocol["partitions"]["active_organs"], dtype=str
        ),
        "fallback_organ": np.asarray("adipose", dtype=str),
    }
    artifact_path = output_dir / "organ_k4_final_router.npz"
    _write_deterministic_npz(artifact_path, arrays)

    config = {
        "fit_pool": "balanced_train_plus_calibration",
        "n_fit_rows": int(len(fit)),
        "router_seed": int(args.router_seed),
        "mask_token": float(args.mask_token),
        "normalization": "log1p_tpm",
        "pipeline": ["StandardScaler", "LogisticRegression"],
        "logistic_regression": {
            "C": 1.0,
            "solver": "lbfgs",
            "class_weight": "balanced",
            "max_iter": 2000,
            "sample_weight": "equal connected-study mass within class",
        },
        "selection_or_tuning_metric": None,
        "predicted_adipose_dispatch": "pooled",
    }
    report = {
        "schema_version": 1,
        "status": "complete",
        "experiment": "stage1_k4_final_target_hidden_router_refit",
        "research_stage": "final_refit_for_external_confirmation",
        "development_only": True,
        "internally_confirmatory": False,
        "internal_efficacy_scoring": False,
        "test_accessed": False,
        "external_data_accessed": False,
        "performance_metrics_generated": False,
        "target_hiding": {
            "score_genes_masked_for_every_row": True,
            "n_score_genes": int(len(score_indices)),
            "score_gene_indices_sha256": _sha256_array(score_indices),
            "masked_feature_sha256": _sha256_array(features),
        },
        "config": config,
        "classes": classes.tolist(),
        "expression_contract": expression_contract,
        "hashes": {
            "protocol_sha256": sha256_file(paths["protocol"]),
            "expression_parquet_sha256": sha256_file(paths["expression"]),
            "expression_metadata_sha256": sha256_file(paths["expression_metadata"]),
            "source_manifest_sha256": sha256_file(paths["source_manifest"]),
            "partition_manifest_sha256": sha256_file(paths["partition_manifest"]),
            "partition_report_sha256": sha256_file(paths["partition_report"]),
            "axis_definitions_sha256": sha256_file(paths["axis_definitions"]),
            "fit_sample_ids_sha256": sha256_lines(sample_ids.tolist()),
            "gene_order_sha256": sha256_lines(genes),
            "resolved_config_sha256": sha256_json(config),
            "router_artifact_sha256": sha256_file(artifact_path),
            "router_source_sha256": sha256_file(Path(__file__)),
        },
        "artifact": str(artifact_path.resolve()),
    }
    _atomic_json(output_dir / "router_report.json", report)
    (output_dir / "COMPLETE").touch()
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expression-parquet", required=True)
    parser.add_argument("--expression-metadata", required=True)
    parser.add_argument("--source-manifest", required=True)
    parser.add_argument("--partition-manifest", required=True)
    parser.add_argument("--partition-report", required=True)
    parser.add_argument("--axis-definitions", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--router-seed", type=int, default=271828)
    parser.add_argument("--mask-token", type=float, default=-10.0)
    parser.add_argument("--train-split", default="train")
    parser.add_argument("--calibration-split", default="calibration")
    parser.add_argument("--train-filter-column", default="balanced_train")
    parser.add_argument("--source-split-column", default="split")
    parser.add_argument("--sample-id-column", default="sample_id")
    parser.add_argument("--organ-column", default="organ")
    parser.add_argument("--group-column", default="series_group_id")
    return parser


def main() -> None:
    report = refit(build_parser().parse_args())
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
