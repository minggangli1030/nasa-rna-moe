#!/usr/bin/env python3
"""Build nested, donor-atomic GTEx adapter-scale manifests without expression access."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd


ORGANS = (
    "adipose",
    "brain",
    "colon",
    "heart",
    "liver",
    "lung",
    "skeletal_muscle",
    "skin",
)


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_lines(values: list[str]) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(value.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _rank(seed: int, label: str, value: str) -> bytes:
    return hashlib.sha256(f"{seed}\0{label}\0{value}".encode("utf-8")).digest()


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _atomic_parquet(frame: pd.DataFrame, path: Path) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_parquet(temporary, index=False)
    os.replace(temporary, path)


def select_nested_samples(
    manifest: pd.DataFrame,
    *,
    budgets: list[int],
    selection_seed: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    required = {"sample_id", "donor_id", "organ", "split"}
    if required - set(manifest):
        raise ValueError("manifest lacks required columns")
    frame = manifest.copy()
    for column in required:
        if frame[column].isna().any():
            raise ValueError(f"manifest column {column} has missing values")
        frame[column] = frame[column].astype(str)
    if frame["sample_id"].duplicated().any():
        raise ValueError("manifest repeats sample IDs")
    if set(frame["organ"]) != set(ORGANS):
        raise ValueError("manifest organ set changed")
    if budgets != sorted(set(budgets)) or not budgets or budgets[0] < 2:
        raise ValueError("budgets must be sorted unique positive values")

    train = frame.loc[frame["split"].eq("train")]
    selected_by_organ: dict[str, list[str]] = {}
    donors_by_organ: dict[str, list[str]] = {}
    for organ in ORGANS:
        organ_train = train.loc[train["organ"].eq(organ)]
        donors = sorted(
            organ_train["donor_id"].unique().tolist(),
            key=lambda donor: (_rank(selection_seed, f"donor:{organ}", donor), donor),
        )
        if len(donors) < budgets[-1]:
            raise ValueError(
                f"organ {organ} has {len(donors)} train donors, below {budgets[-1]}"
            )
        sample_for_donor: dict[str, str] = {}
        for donor in donors:
            samples = organ_train.loc[
                organ_train["donor_id"].eq(donor), "sample_id"
            ].tolist()
            sample_for_donor[donor] = min(
                samples,
                key=lambda sample: (
                    _rank(selection_seed, f"sample:{organ}:{donor}", sample),
                    sample,
                ),
            )
        donors_by_organ[organ] = donors
        selected_by_organ[organ] = [sample_for_donor[donor] for donor in donors]

    report_budgets: dict[str, Any] = {}
    previous: set[str] = set()
    for budget in budgets:
        column = f"scale_b{budget}"
        selected: list[str] = []
        donor_ids: list[str] = []
        per_organ = {}
        for organ in ORGANS:
            samples = selected_by_organ[organ][:budget]
            donors = donors_by_organ[organ][:budget]
            selected.extend(samples)
            donor_ids.extend(donors)
            per_organ[organ] = {
                "samples": len(samples),
                "donors": len(donors),
                "sample_ids_sha256": sha256_lines(samples),
                "donor_ids_sha256": sha256_lines(donors),
            }
        selected_set = set(selected)
        if len(selected_set) != budget * len(ORGANS):
            raise AssertionError("a budget did not produce exactly one sample per donor")
        if previous and not previous.issubset(selected_set):
            raise AssertionError("budget selections are not nested")
        previous = selected_set
        frame[column] = frame["sample_id"].isin(selected_set)
        if frame.loc[frame[column], "split"].ne("train").any():
            raise AssertionError("a scale selection includes non-training rows")
        report_budgets[str(budget)] = {
            "filter_column": column,
            "total_samples": len(selected),
            "total_donors": len(donor_ids),
            "ordered_sample_ids_sha256": sha256_lines(selected),
            "ordered_donor_ids_sha256": sha256_lines(donor_ids),
            "per_organ": per_organ,
        }
    return frame, report_budgets


def build(args: argparse.Namespace) -> dict[str, Any]:
    protocol_path = Path(args.protocol)
    if sha256_file(protocol_path) != args.expected_protocol_sha256:
        raise ValueError("protocol SHA256 mismatch")
    protocol = json.loads(protocol_path.read_text())
    if protocol.get("status") != "frozen_gtex_k8_scale_manifest_protocol":
        raise ValueError("scale protocol is not frozen")
    expected_self = protocol["implementation"]["manifest_builder_sha256"]
    if expected_self != sha256_file(Path(__file__).resolve()):
        raise ValueError("manifest builder differs from frozen implementation")
    manifest_path = Path(args.manifest)
    if sha256_file(manifest_path) != protocol["inputs"]["manifest_sha256"]:
        raise ValueError("source manifest changed")
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise FileExistsError(output_dir)
    output_dir.mkdir(parents=True)
    manifest = pd.read_parquet(manifest_path)
    frame, budgets = select_nested_samples(
        manifest,
        budgets=[int(value) for value in protocol["data_curve"]["donors_per_organ"]],
        selection_seed=int(protocol["data_curve"]["selection_seed"]),
    )
    output_manifest = output_dir / "scale_manifest.parquet"
    _atomic_parquet(frame, output_manifest)
    artifact_lines = []
    for budget_text, budget_report in budgets.items():
        budget = int(budget_text)
        budget_dir = output_dir / f"b{budget}"
        budget_dir.mkdir()
        selected_train = frame.loc[
            frame["split"].eq("train") & frame[f"scale_b{budget}"]
        ]
        calibration = frame.loc[frame["split"].eq("calibration")]
        partition = pd.concat([selected_train, calibration], ignore_index=True)
        partition_path = budget_dir / "manifest.parquet"
        _atomic_parquet(partition, partition_path)
        partition_report = {
            "schema_version": 1,
            "status": "complete",
            "test_accessed": False,
            "external_data_accessed": False,
            "expression_values_read": False,
            "budget": budget,
            "selected_train_samples": int(len(selected_train)),
            "calibration_samples": int(len(calibration)),
            "hashes": {
                "partition_manifest_sha256": sha256_file(partition_path),
                "axis_definitions_sha256": protocol["inputs"]["axis_definitions_sha256"],
            },
        }
        partition_report_path = budget_dir / "manifest_report.json"
        _atomic_json(partition_report_path, partition_report)
        (budget_dir / "IMMUTABLE_SHA256SUMS").write_text(
            f"{sha256_file(partition_report_path)}  manifest_report.json\n"
            f"{sha256_file(partition_path)}  manifest.parquet\n"
        )
        budget_report["trainer_manifest_sha256"] = sha256_file(partition_path)
        budget_report["trainer_manifest_report_sha256"] = sha256_file(
            partition_report_path
        )
        budget_report["trainer_manifest_rows"] = int(len(partition))
        artifact_lines.extend(
            [
                f"{sha256_file(partition_report_path)}  b{budget}/manifest_report.json",
                f"{sha256_file(partition_path)}  b{budget}/manifest.parquet",
            ]
        )
    report = {
        "schema_version": 1,
        "status": "complete",
        "protocol_sha256": sha256_file(protocol_path),
        "source_manifest_sha256": sha256_file(manifest_path),
        "scale_manifest_sha256": sha256_file(output_manifest),
        "hashes": {
            "partition_manifest_sha256": sha256_file(output_manifest),
        },
        "expression_values_read": False,
        "calibration_membership_changed": False,
        "budgets": budgets,
    }
    report_path = output_dir / "manifest_report.json"
    _atomic_json(report_path, report)
    sums = output_dir / "IMMUTABLE_SHA256SUMS"
    sums.write_text(
        f"{sha256_file(report_path)}  manifest_report.json\n"
        f"{sha256_file(output_manifest)}  scale_manifest.parquet\n"
        + "\n".join(artifact_lines)
        + "\n"
    )
    (output_dir / "COMPLETE").write_text("COMPLETE\n")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


if __name__ == "__main__":
    build(parse_args())
