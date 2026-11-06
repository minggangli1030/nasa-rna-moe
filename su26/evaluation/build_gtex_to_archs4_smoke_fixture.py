#!/usr/bin/env python3
"""Build a small, coverage-complete real-GTEx mechanical smoke fixture."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import sys

ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = ROOT / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from train_manifest import (  # noqa: E402
    load_expression_rows,
    sha256_file,
    sha256_lines,
)


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _coverage_subset(
    frame: pd.DataFrame,
    *,
    organ_axis: str,
    random_axes: list[str],
    minimum_rows: int,
) -> pd.DataFrame:
    selected: set[int] = set()
    for organ in sorted(frame["organ"].astype(str).unique()):
        selected.add(int(frame.index[frame["organ"].astype(str).eq(organ)][0]))
    for axis in [organ_axis, *random_axes]:
        for label in sorted(frame[axis].astype(int).unique()):
            selected.add(int(frame.index[frame[axis].astype(int).eq(label)][0]))
        for organ in sorted(frame["organ"].astype(str).unique()):
            organ_rows = frame[frame["organ"].astype(str).eq(organ)]
            for label in sorted(frame[axis].astype(int).unique()):
                candidates = organ_rows[organ_rows[axis].astype(int).eq(label)]
                if not candidates.empty:
                    selected.add(int(candidates.index[0]))
    for index in frame.index:
        if len(selected) >= minimum_rows:
            break
        selected.add(int(index))
    subset = frame.loc[sorted(selected)].copy()
    if set(subset[organ_axis].astype(int)) != set(frame[organ_axis].astype(int)):
        raise AssertionError("smoke subset lost an organ label")
    for axis in random_axes:
        if set(subset[axis].astype(int)) != set(frame[axis].astype(int)):
            raise AssertionError(f"smoke subset lost a label for {axis}")
    return subset


def build(args: argparse.Namespace) -> dict[str, Any]:
    protocol_path = Path(args.protocol)
    if sha256_file(protocol_path) != args.expected_protocol_sha256:
        raise ValueError("protocol SHA256 mismatch")
    protocol = json.loads(protocol_path.read_text())
    if protocol.get("status") != "frozen_gtex_to_archs4_development_contract":
        raise ValueError("protocol is not frozen")
    if protocol["firewalls"][
        "archs4_lockbox_expression_access_before_candidate_freeze"
    ] is not False:
        raise ValueError("ARCHS4 expression lockbox is not closed")

    manifest_path = Path(args.manifest)
    manifest_report_path = Path(args.manifest_report)
    manifest_report = json.loads(manifest_report_path.read_text())
    if manifest_report.get("status") != "complete":
        raise ValueError("manifest report is incomplete")
    if manifest_report.get("archs4_expression_accessed") is not False:
        raise ValueError("manifest report indicates ARCHS4 expression access")
    if sha256_file(manifest_path) != manifest_report["hashes"]["manifest_sha256"]:
        raise ValueError("manifest differs from its report")
    manifest = pd.read_parquet(manifest_path)
    config = manifest_report["config"]
    organ_axis = str(config["organ_axis"])
    random_axes = [str(value) for value in config["random_axes"]]
    required = {
        "sample_id",
        "donor_id",
        "split",
        "organ",
        "series_group_id",
        organ_axis,
        *random_axes,
        "pooled_adapter",
    }
    missing = sorted(required - set(manifest.columns))
    if missing:
        raise ValueError(f"manifest lacks smoke columns: {missing}")

    selected_parts = []
    for split_name in ("train", "calibration"):
        split = manifest[manifest["split"].eq(split_name)].copy()
        if split.empty:
            raise ValueError(f"manifest lacks {split_name}")
        selected_parts.append(
            _coverage_subset(
                split,
                organ_axis=organ_axis,
                random_axes=random_axes,
                minimum_rows=int(args.minimum_rows_per_split),
            )
        )
    smoke_manifest = pd.concat(selected_parts, ignore_index=True)
    crossing = smoke_manifest.groupby("donor_id")["split"].nunique()
    if int(crossing.max()) != 1:
        raise AssertionError("smoke fixture crosses a donor between splits")

    expression_path = Path(args.expression)
    expression_report_path = Path(args.expression_report)
    expression_report = json.loads(expression_report_path.read_text())
    if expression_report.get("status") != "complete":
        raise ValueError("expression report is incomplete")
    if expression_report.get("archs4_expression_accessed") is not False:
        raise ValueError("expression report indicates ARCHS4 access")
    expected_expression_hash = expression_report.get("hashes", {}).get(
        "expression_sha256"
    )
    if expected_expression_hash != sha256_file(expression_path):
        raise ValueError("expression differs from its extraction report")
    sample_ids = smoke_manifest["sample_id"].astype(str).tolist()
    values, expression_info = load_expression_rows(expression_path, sample_ids)
    if values.shape[0] != len(smoke_manifest):
        raise AssertionError("smoke expression row count changed")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    smoke_manifest_path = output_dir / "smoke_manifest.parquet"
    smoke_expression_path = output_dir / "smoke_expression.parquet"
    smoke_manifest.to_parquet(smoke_manifest_path, index=False)
    smoke_expression = pd.DataFrame(
        values,
        columns=list(expression_info.gene_columns),
    )
    smoke_expression.insert(0, "sample_id", sample_ids)
    smoke_expression.to_parquet(smoke_expression_path, index=False)

    axis_path = Path(args.axis_definitions)
    if sha256_file(axis_path) != protocol["expression_contract"][
        "axis_definitions_sha256"
    ]:
        raise ValueError("axis definitions differ from protocol")
    smoke_expression_report = {
        "schema_version": 1,
        "status": "complete",
        "mechanical_only": True,
        "expression_space": "tpm",
        "log_transform_applied": False,
        "archs4_expression_accessed": False,
        "samples": int(len(smoke_manifest)),
        "genes": int(len(expression_info.gene_columns)),
        "gene_order_sha256": sha256_lines(expression_info.gene_columns),
        "hashes": {
            "source_expression_sha256": sha256_file(expression_path),
            "source_expression_report_sha256": sha256_file(expression_report_path),
            "smoke_expression_sha256": sha256_file(smoke_expression_path),
        },
    }
    smoke_expression_report_path = output_dir / "extraction_report.json"
    _atomic_json(smoke_expression_report_path, smoke_expression_report)

    partition_report = {
        "schema_version": 1,
        "status": "complete",
        "mechanical_only": True,
        "test_accessed": False,
        "external_data_accessed": False,
        "archs4_expression_accessed": False,
        "hashes": {
            "partition_manifest_sha256": sha256_file(smoke_manifest_path),
            "axis_definitions_sha256": sha256_file(axis_path),
        },
    }
    partition_report_path = output_dir / "partition_report.json"
    _atomic_json(partition_report_path, partition_report)

    report = {
        "schema_version": 1,
        "status": "complete",
        "mechanical_only": True,
        "efficacy_scoring_performed": False,
        "archs4_expression_accessed": False,
        "counts": {
            "samples": int(len(smoke_manifest)),
            "train": int(smoke_manifest["split"].eq("train").sum()),
            "calibration": int(
                smoke_manifest["split"].eq("calibration").sum()
            ),
            "donors": int(smoke_manifest["donor_id"].nunique()),
        },
        "coverage": {
            "organ_axis": organ_axis,
            "random_axes": random_axes,
            "organs": sorted(smoke_manifest["organ"].astype(str).unique()),
        },
        "hashes": {
            "protocol_sha256": sha256_file(protocol_path),
            "source_manifest_sha256": sha256_file(manifest_path),
            "source_manifest_report_sha256": sha256_file(manifest_report_path),
            "source_expression_sha256": sha256_file(expression_path),
            "source_expression_report_sha256": sha256_file(expression_report_path),
            "smoke_manifest_sha256": sha256_file(smoke_manifest_path),
            "smoke_expression_sha256": sha256_file(smoke_expression_path),
            "smoke_expression_report_sha256": sha256_file(
                smoke_expression_report_path
            ),
            "partition_report_sha256": sha256_file(partition_report_path),
            "sample_order_sha256": sha256_lines(sample_ids),
        },
    }
    _atomic_json(output_dir / "smoke_fixture_report.json", report)
    (output_dir / "SMOKE_FIXTURE_COMPLETE").write_text(
        "mechanical-only GTEx smoke fixture complete; ARCHS4 expression sealed.\n"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--manifest-report", required=True)
    parser.add_argument("--expression", required=True)
    parser.add_argument("--expression-report", required=True)
    parser.add_argument("--axis-definitions", required=True)
    parser.add_argument("--minimum-rows-per-split", type=int, default=64)
    parser.add_argument("--output-dir", required=True)
    print(json.dumps(build(parser.parse_args()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
