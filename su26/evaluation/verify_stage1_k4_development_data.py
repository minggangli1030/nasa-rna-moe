#!/usr/bin/env python3
"""Verify the physically separate development-only expression artifact.

The final Stage-1 refit must not open the historical combined train/calibration/test
Parquet.  This verifier accepts only the already frozen K45 train+calibration
manifest and an expression directory extracted directly from ARCHS4 H5 using that
manifest.  It emits a deterministic firewall report that can be hash-pinned by the
final-refit protocol.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = ROOT / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from train_manifest import sha256_file, sha256_json, sha256_lines  # noqa: E402


EXPECTED_SOURCE_PARTITION_SHA256 = (
    "09c45edc5dd6389020495f8fd4718995cd82ee7828197a96c0fa44ef46e98bf2"
)
EXPECTED_EXTRACTOR_SHA256 = (
    "c4c694584c23b1e4032472bc7de8bc5a56913e0eda2365dd78ffe8f26995fa45"
)
EXPECTED_CANONICAL_GENES_SHA256 = (
    "3332cb312000e426a866d669b3ba9b6206da50d70094fb5f9d30ef168e860dff"
)
EXPECTED_EXON_LENGTHS_SHA256 = (
    "c272e5b8e23698bfb009fad019268897dd173f333dc437b7dd97d28894108609"
)
EXPECTED_FIT_ROWS = 2657
EXPECTED_TRAIN_ROWS = 1815
EXPECTED_CALIBRATION_ROWS = 842
EXPECTED_GENES = 15448


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def verify(args: argparse.Namespace) -> dict[str, Any]:
    data_root = Path(args.data_root)
    source_manifest_path = Path(args.source_partition_manifest)
    paths = {
        "expression": data_root / "expression.parquet",
        "manifest": data_root / "manifest.parquet",
        "metadata": data_root / "extraction_report.json",
        "genes": data_root / "genes.txt",
    }
    for path in (source_manifest_path, *paths.values()):
        if not path.is_file():
            raise FileNotFoundError(path)
    report_path = data_root / "firewall_report.json"
    marker_path = data_root / "FIREWALL_VERIFIED"
    if report_path.exists() or marker_path.exists():
        raise FileExistsError("development-data firewall output already exists")
    if sha256_file(source_manifest_path) != EXPECTED_SOURCE_PARTITION_SHA256:
        raise ValueError("source K45 train+calibration manifest hash changed")

    source = pd.read_parquet(source_manifest_path)
    materialized = pd.read_parquet(paths["manifest"])
    if list(source.columns) != list(materialized.columns):
        raise ValueError("materialized development manifest columns changed")
    try:
        pd.testing.assert_frame_equal(
            materialized,
            source,
            check_dtype=True,
            check_like=False,
            check_exact=True,
        )
    except AssertionError as exc:
        raise ValueError("materialized development manifest differs from K45") from exc
    required = {"sample_id", "split", "utility_split", "organ", "series_group_id"}
    if not required.issubset(materialized.columns):
        raise ValueError("development manifest lacks required firewall columns")
    if materialized["sample_id"].duplicated().any():
        raise ValueError("development manifest contains duplicate sample IDs")
    if set(materialized["split"].astype(str)) != {"train", "calibration"}:
        raise ValueError("development manifest contains a forbidden split")
    if set(materialized["utility_split"].astype(str)) != {"train", "calibration"}:
        raise ValueError("development manifest contains forbidden utility provenance")
    if (
        len(materialized) != EXPECTED_FIT_ROWS
        or int(materialized["split"].eq("train").sum()) != EXPECTED_TRAIN_ROWS
        or int(materialized["split"].eq("calibration").sum())
        != EXPECTED_CALIBRATION_ROWS
    ):
        raise ValueError("development manifest counts differ from the frozen pool")

    extraction = _load_json(paths["metadata"])
    outputs = extraction.get("outputs", {})
    inputs = extraction.get("inputs", {})
    expression = extraction.get("expression", {})
    contract = extraction.get("contract", {})
    source_h5 = extraction.get("source_h5", {})
    if (
        extraction.get("status") != "complete"
        or extraction.get("expression_space") != "tpm"
        or expression.get("n_requested_samples") != EXPECTED_FIT_ROWS
        or expression.get("n_published_samples") != EXPECTED_FIT_ROWS
        or expression.get("n_genes") != EXPECTED_GENES
        or expression.get("sample_order_matches_manifest") is not True
        or inputs.get("manifest_file_sha256") != EXPECTED_SOURCE_PARTITION_SHA256
        or inputs.get("extractor_sha256") != EXPECTED_EXTRACTOR_SHA256
        or inputs.get("canonical_genes_file_sha256")
        != EXPECTED_CANONICAL_GENES_SHA256
        or inputs.get("human_exon_lengths_file_sha256")
        != EXPECTED_EXON_LENGTHS_SHA256
        or contract.get("random_sampling_or_split") is not False
        or contract.get("silent_sample_drops") is not False
        or contract.get("log1p_applications") != 0
        or contract.get("tpm_applications") != 1
        or source_h5.get("all_manifest_samples_resolved_exactly_once") is not True
    ):
        raise ValueError("development extraction report violates the frozen firewall")
    if outputs.get("expression_parquet_sha256") != sha256_file(paths["expression"]):
        raise ValueError("development expression hash differs from extraction report")
    if outputs.get("manifest_parquet_sha256") != sha256_file(paths["manifest"]):
        raise ValueError("development manifest hash differs from extraction report")
    if outputs.get("genes_file_sha256") != sha256_file(paths["genes"]):
        raise ValueError("development gene-list hash differs from extraction report")

    parquet = pq.ParquetFile(paths["expression"])
    names = parquet.schema_arrow.names
    if names[0] != "sample_id" or len(names) != EXPECTED_GENES + 1:
        raise ValueError("development expression schema differs from the frozen gene axis")
    expression_ids = (
        parquet.read(columns=["sample_id"])
        .column("sample_id")
        .to_pylist()
    )
    manifest_ids = materialized["sample_id"].astype(str).tolist()
    if [str(value) for value in expression_ids] != manifest_ids:
        raise ValueError("development expression rows differ from the manifest order")
    genes = [line.strip() for line in paths["genes"].read_text().splitlines() if line.strip()]
    if names[1:] != genes or len(genes) != EXPECTED_GENES:
        raise ValueError("development expression gene columns differ from genes.txt")

    config = {
        "source_mode": "direct_manifest_selected_ARCHS4_H5_extraction",
        "runtime_expression_container": "development_only",
        "historical_combined_expression_opened": False,
        "historical_combined_manifest_opened": False,
        "old_test_rows_requested": False,
        "old_test_rows_emitted": False,
        "random_sampling_or_split": False,
        "row_order": "exact frozen K45 train then calibration order",
    }
    hashes = {
        "source_k45_partition_manifest_sha256": sha256_file(source_manifest_path),
        "development_expression_sha256": sha256_file(paths["expression"]),
        "development_manifest_sha256": sha256_file(paths["manifest"]),
        "development_extraction_report_sha256": sha256_file(paths["metadata"]),
        "genes_sha256": sha256_file(paths["genes"]),
        "ordered_sample_ids_sha256": sha256_lines(manifest_ids),
        "gene_order_sha256": sha256_lines(genes),
        "selected_aggregated_counts_sha256": source_h5.get(
            "selected_aggregated_counts_sha256"
        ),
        "extractor_sha256": EXPECTED_EXTRACTOR_SHA256,
        "resolved_config_sha256": sha256_json(config),
    }
    report = {
        "schema_version": 1,
        "status": "complete",
        "artifact_role": "stage1_k4_development_only_expression_firewall",
        "development_only": True,
        "runtime_authorized_for_final_refit": True,
        "test_rows_present": False,
        "test_expression_available_to_runtime": False,
        "test_targets_or_scores_accessed": False,
        "counts": {
            "fit": EXPECTED_FIT_ROWS,
            "train": EXPECTED_TRAIN_ROWS,
            "calibration": EXPECTED_CALIBRATION_ROWS,
            "genes": EXPECTED_GENES,
        },
        "config": config,
        "hashes": hashes,
    }
    _atomic_json(report_path, report)
    marker_path.write_text("verified\n")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", required=True)
    parser.add_argument("--source-partition-manifest", required=True)
    return parser


def main() -> None:
    report = verify(build_parser().parse_args())
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
