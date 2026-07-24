#!/usr/bin/env python3
"""Fit the metric-free target-hidden K-organ router on GTEx development rows."""

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


REQUIRED_STATUS = "frozen_gtex_to_archs4_development_contract"


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def refit(args: argparse.Namespace) -> dict[str, Any]:
    paths = {
        "protocol": Path(args.protocol),
        "expression": Path(args.expression_parquet),
        "expression_metadata": Path(args.expression_metadata),
        "manifest": Path(args.manifest),
        "manifest_report": Path(args.manifest_report),
        "axis_definitions": Path(args.axis_definitions),
    }
    for path in paths.values():
        if not path.is_file():
            raise FileNotFoundError(path)
    if sha256_file(paths["protocol"]) != args.expected_protocol_sha256:
        raise ValueError("protocol SHA256 mismatch")
    protocol = json.loads(paths["protocol"].read_text())
    if protocol.get("status") != REQUIRED_STATUS:
        raise ValueError("protocol is not frozen for GTEx development")
    if protocol["firewalls"][
        "archs4_lockbox_expression_access_before_candidate_freeze"
    ] is not False:
        raise ValueError("ARCHS4 expression lockbox is not closed")
    organs_expected = tuple(protocol["organ_selection"]["ordered_organs"])
    if sha256_file(paths["axis_definitions"]) != protocol["expression_contract"][
        "axis_definitions_sha256"
    ]:
        raise ValueError("axis definitions differ from protocol")

    manifest_report = json.loads(paths["manifest_report"].read_text())
    if (
        manifest_report.get("status") != "complete"
        or manifest_report.get("test_accessed") is not False
        or manifest_report.get("archs4_expression_accessed") is not False
    ):
        raise ValueError("manifest report is incomplete or violates a firewall")
    expected_manifest_hash = manifest_report["hashes"].get("manifest_sha256")
    if expected_manifest_hash is None:
        expected_manifest_hash = manifest_report["hashes"].get(
            "partition_manifest_sha256"
        )
    if sha256_file(paths["manifest"]) != expected_manifest_hash:
        raise ValueError("manifest differs from its report")

    expression_report = json.loads(paths["expression_metadata"].read_text())
    if (
        expression_report.get("status") != "complete"
        or expression_report.get("archs4_expression_accessed") is not False
    ):
        raise ValueError("expression report is incomplete or violates a firewall")
    expected_expression_hash = expression_report.get("hashes", {}).get(
        "expression_sha256"
    )
    if expected_expression_hash is None:
        expected_expression_hash = expression_report.get("hashes", {}).get(
            "smoke_expression_sha256"
        )
    if expected_expression_hash != sha256_file(paths["expression"]):
        raise ValueError("expression differs from its report")

    source = read_manifest(paths["manifest"])
    selection = select_manifest_rows(
        source,
        role="pooled",
        train_split=args.train_split,
        validation_split=args.calibration_split,
        train_filter_column=args.train_filter_column,
        sample_id_column=args.sample_id_column,
        split_column=args.split_column,
        organ_column=args.organ_column,
        group_column=args.group_column,
    )
    fit = pd.concat([selection.train, selection.validation], ignore_index=True)
    required = {args.sample_id_column, args.organ_column, args.group_column}
    missing = sorted(required - set(fit.columns))
    if missing:
        raise ValueError(f"router fitting manifest lacks columns: {missing}")
    for column in required:
        if fit[column].isna().any():
            raise ValueError(f"router fitting column {column!r} has missing values")
        fit[column] = fit[column].astype(str)
    if fit[args.sample_id_column].duplicated().any():
        raise ValueError("router fitting sample IDs are not unique")
    if set(fit[args.organ_column]) != set(organs_expected):
        raise ValueError("router fitting organs differ from the frozen protocol")

    sample_ids = fit[args.sample_id_column].to_numpy(dtype=str)
    organs = fit[args.organ_column].to_numpy(dtype=str)
    groups = fit[args.group_column].to_numpy(dtype=str)
    expression, expression_info = load_expression_rows(
        paths["expression"],
        sample_ids.tolist(),
        sample_id_column=args.sample_id_column,
    )
    expression_contract = validate_expression_metadata(
        paths["expression"],
        expression_info.gene_columns,
        metadata_path=paths["expression_metadata"],
    )
    with np.load(paths["axis_definitions"], allow_pickle=False) as definitions:
        if not {"score_gene_indices", "gene_names"}.issubset(definitions.files):
            raise ValueError("axis definitions lack score genes or gene names")
        score_indices = np.asarray(definitions["score_gene_indices"], dtype=np.int64)
        definition_genes = np.asarray(definitions["gene_names"]).astype(str)
    genes = list(expression_info.gene_columns)
    if definition_genes.tolist() != genes:
        raise ValueError("axis-definition gene order differs from expression")
    if len(genes) != int(protocol["strict_model_family"]["gene_count"]):
        raise ValueError("gene count differs from frozen protocol")

    features = mask_score_genes(
        np.log1p(expression).astype(np.float32, copy=False),
        score_indices,
        args.mask_token,
    )
    if not np.all(features[:, score_indices] == np.float32(args.mask_token)):
        raise RuntimeError("router target-hiding assertion failed")
    model, sample_weights = _fit_router(
        features, organs, groups, seed=int(args.router_seed)
    )
    scaler = model.named_steps["standardscaler"]
    classifier = model.named_steps["logisticregression"]
    classes = classifier.classes_.astype(str)
    if classes.tolist() != list(organs_expected):
        raise RuntimeError("router class order differs from frozen organ order")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    arrays = {
        "fit_sample_ids": sample_ids,
        "fit_organs": organs,
        "fit_donor_ids": groups,
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
        "active_adapter_organs": np.asarray(organs_expected, dtype=str),
    }
    artifact_path = output_dir / "gtex_k8_target_hidden_router.npz"
    _write_deterministic_npz(artifact_path, arrays)
    config = {
        "fit_pool": "gtex_train_plus_calibration",
        "n_fit_rows": int(len(fit)),
        "n_donors": int(pd.Series(groups).nunique()),
        "router_seed": int(args.router_seed),
        "mask_token": float(args.mask_token),
        "normalization": "log1p_tpm",
        "pipeline": ["StandardScaler", "LogisticRegression"],
        "logistic_regression": {
            "C": 1.0,
            "solver": "lbfgs",
            "class_weight": "balanced",
            "max_iter": 2000,
            "sample_weight": "equal donor mass within organ",
        },
        "selection_or_tuning_metric": None,
    }
    report = {
        "schema_version": 1,
        "status": "complete",
        "experiment": "gtex_k8_target_hidden_router_refit",
        "development_only": True,
        "mechanical_only": bool(args.mechanical_only),
        "internal_efficacy_scoring": False,
        "performance_metrics_generated": False,
        "test_accessed": False,
        "archs4_expression_accessed": False,
        "classes": classes.tolist(),
        "target_hiding": {
            "score_genes_masked_for_every_row": True,
            "n_score_genes": int(len(score_indices)),
            "score_gene_indices_sha256": _sha256_array(score_indices),
            "masked_feature_sha256": _sha256_array(features),
        },
        "config": config,
        "expression_contract": expression_contract,
        "hashes": {
            "protocol_sha256": sha256_file(paths["protocol"]),
            "expression_parquet_sha256": sha256_file(paths["expression"]),
            "expression_metadata_sha256": sha256_file(paths["expression_metadata"]),
            "manifest_sha256": sha256_file(paths["manifest"]),
            "manifest_report_sha256": sha256_file(paths["manifest_report"]),
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
    (output_dir / "COMPLETE").write_text(
        "metric-free target-hidden GTEx router fit complete.\n"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--expression-parquet", required=True)
    parser.add_argument("--expression-metadata", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--manifest-report", required=True)
    parser.add_argument("--axis-definitions", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--router-seed", type=int, default=271828)
    parser.add_argument("--mask-token", type=float, default=-10.0)
    parser.add_argument("--train-split", default="train")
    parser.add_argument("--calibration-split", default="calibration")
    parser.add_argument("--train-filter-column", default="balanced_train")
    parser.add_argument("--split-column", default="split")
    parser.add_argument("--sample-id-column", default="sample_id")
    parser.add_argument("--organ-column", default="organ")
    parser.add_argument("--group-column", default="series_group_id")
    parser.add_argument("--mechanical-only", action="store_true")
    print(json.dumps(refit(parser.parse_args()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
