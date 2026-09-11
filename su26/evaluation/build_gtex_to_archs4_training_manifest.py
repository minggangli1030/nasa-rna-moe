#!/usr/bin/env python3
"""Build donor-disjoint GTEx training and matched random-control partitions.

This builder is expression-blind. It accepts an exact GTEx cohort that has already
been intersected with the pinned RNASeQC matrix header and emits train/calibration
metadata for pooled, organ, random, pooled-adapter, and router training.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = ROOT / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from train_manifest import sha256_file, sha256_json, sha256_lines  # noqa: E402


REQUIRED_COLUMNS = {"sample_id", "donor_id", "organ", "tissue_site"}
REQUIRED_STATUS = "frozen_gtex_to_archs4_development_contract"


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _atomic_parquet(frame: pd.DataFrame, path: Path) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_parquet(temporary, index=False)
    os.replace(temporary, path)


def _hash_rank(seed: int, label: str, value: str) -> bytes:
    payload = f"{seed}\0{label}\0{value}".encode("utf-8")
    return hashlib.sha256(payload).digest()


def _assign_donor_splits(
    frame: pd.DataFrame,
    *,
    seed: int,
    calibration_fraction: float,
) -> tuple[pd.Series, dict[str, Any]]:
    if not 0 < calibration_fraction < 0.5:
        raise ValueError("calibration fraction must lie in (0, 0.5)")
    donors = sorted(
        frame["donor_id"].astype(str).unique(),
        key=lambda value: (_hash_rank(seed, "gtex_split", value), value),
    )
    calibration_count = max(1, int(round(len(donors) * calibration_fraction)))
    if calibration_count >= len(donors):
        raise ValueError("calibration split would consume every donor")
    calibration = set(donors[:calibration_count])
    split = frame["donor_id"].astype(str).map(
        lambda value: "calibration" if value in calibration else "train"
    )
    if set(split) != {"train", "calibration"}:
        raise AssertionError("donor split did not produce both partitions")
    crossing = (
        pd.DataFrame({"donor_id": frame["donor_id"].astype(str), "split": split})
        .groupby("donor_id")["split"]
        .nunique()
    )
    if int(crossing.max()) != 1:
        raise AssertionError("a GTEx donor crosses train and calibration")
    return split, {
        "algorithm": "SHA256 rank of split seed NUL gtex_split NUL donor ID",
        "seed": int(seed),
        "calibration_fraction": float(calibration_fraction),
        "train_donors": int(
            frame.loc[split.eq("train"), "donor_id"].astype(str).nunique()
        ),
        "calibration_donors": int(
            frame.loc[split.eq("calibration"), "donor_id"].astype(str).nunique()
        ),
        "calibration_donor_ids_sha256": sha256_lines(sorted(calibration)),
    }


def _assign_balanced_random_donors(
    frame: pd.DataFrame,
    *,
    organs: tuple[str, ...],
    k: int,
    seed: int,
    split_name: str,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Greedily balance donor-atomic organ sample vectors over K random shards."""
    if k != len(organs):
        raise ValueError("random-control K must equal the organ count")
    donor_organ = (
        frame.groupby(["donor_id", "organ"], sort=True)
        .size()
        .unstack(fill_value=0)
        .reindex(columns=organs, fill_value=0)
        .astype(np.int64)
    )
    if len(donor_organ) < k:
        raise ValueError(f"split {split_name!r} has fewer donors than random shards")
    organ_targets = donor_organ.sum(axis=0).to_numpy(dtype=np.float64) / k
    donor_target = len(donor_organ) / float(k)
    sample_target = float(donor_organ.to_numpy().sum()) / k
    if np.any(organ_targets <= 0):
        raise ValueError(f"split {split_name!r} lacks one or more organs")

    records: list[tuple[str, np.ndarray, float, bytes]] = []
    for donor, row in donor_organ.iterrows():
        counts = row.to_numpy(dtype=np.int64)
        pressure = max(
            float(counts.sum() / sample_target),
            float(np.max(counts / organ_targets)),
        )
        records.append(
            (
                str(donor),
                counts,
                pressure,
                _hash_rank(seed, f"random_{split_name}_order", str(donor)),
            )
        )
    records.sort(key=lambda item: (-item[2], item[3], item[0]))

    organ_loads = np.zeros((k, len(organs)), dtype=np.int64)
    sample_loads = np.zeros(k, dtype=np.int64)
    donor_loads = np.zeros(k, dtype=np.int64)
    assignment: dict[str, int] = {}
    for donor, counts, _, _ in records:
        tie_order = sorted(
            range(k),
            key=lambda shard: (
                _hash_rank(seed, f"random_{split_name}_tie_{donor}", str(shard)),
                shard,
            ),
        )
        tie_rank = {shard: rank for rank, shard in enumerate(tie_order)}
        candidates: list[tuple[float, float, float, float, int, int]] = []
        for shard in range(k):
            candidate_organs = organ_loads.copy()
            candidate_samples = sample_loads.copy()
            candidate_donors = donor_loads.copy()
            candidate_organs[shard] += counts
            candidate_samples[shard] += int(counts.sum())
            candidate_donors[shard] += 1
            score = float(
                np.mean(np.square(candidate_organs / organ_targets[None, :]))
                + np.mean(np.square(candidate_samples / sample_target))
                + np.mean(np.square(candidate_donors / donor_target))
            )
            candidates.append(
                (
                    round(score, 14),
                    float(np.max(candidate_organs / organ_targets[None, :])),
                    float(np.max(candidate_samples / sample_target)),
                    float(np.max(candidate_donors / donor_target)),
                    tie_rank[shard],
                    shard,
                )
            )
        selected = min(candidates)[-1]
        assignment[donor] = int(selected)
        organ_loads[selected] += counts
        sample_loads[selected] += int(counts.sum())
        donor_loads[selected] += 1

    labels = frame["donor_id"].astype(str).map(assignment)
    if labels.isna().any():
        raise AssertionError("a donor lacks a random-control assignment")
    array = labels.to_numpy(dtype=np.int64)
    if not np.array_equal(np.unique(array), np.arange(k)):
        raise ValueError(f"split {split_name!r} random labels do not cover 0..K-1")
    check = frame.assign(_label=array).groupby("donor_id")["_label"].nunique()
    if int(check.max()) != 1:
        raise AssertionError("a random partition split a donor")
    return array, {
        "seed": int(seed),
        "split": split_name,
        "assignment_algorithm": (
            "outcome-free deterministic greedy donor-atomic balancing of organ "
            "sample vectors, total samples, and donor counts"
        ),
        "donors_per_shard": donor_loads.astype(int).tolist(),
        "samples_per_shard": sample_loads.astype(int).tolist(),
        "organ_samples_per_shard": {
            organ: organ_loads[:, index].astype(int).tolist()
            for index, organ in enumerate(organs)
        },
        "donor_assignment_sha256": sha256_lines(
            f"{donor}\t{assignment[donor]}" for donor in sorted(assignment)
        ),
    }


def _assignment_hash(frame: pd.DataFrame, axis: str) -> str:
    return sha256_lines(
        f"{row.sample_id}\t{getattr(row, axis)}"
        for row in frame[["sample_id", axis]].itertuples(index=False)
    )


def build(args: argparse.Namespace) -> dict[str, Any]:
    protocol_path = Path(args.protocol)
    if sha256_file(protocol_path) != args.expected_protocol_sha256:
        raise ValueError("GTEx-to-ARCHS4 protocol SHA256 mismatch")
    protocol = json.loads(protocol_path.read_text())
    if protocol.get("status") != REQUIRED_STATUS:
        raise ValueError("protocol is not frozen for GTEx development")
    if protocol.get("firewalls", {}).get(
        "archs4_lockbox_expression_access_before_candidate_freeze"
    ) is not False:
        raise ValueError("protocol does not close the ARCHS4 lockbox")
    if re.fullmatch(r"[0-9a-f]{40}", args.code_commit) is None:
        raise ValueError("manifest build requires a full Git commit")
    axis_definitions_path = Path(args.axis_definitions)
    expected_axis_hash = protocol["expression_contract"]["axis_definitions_sha256"]
    if sha256_file(axis_definitions_path) != expected_axis_hash:
        raise ValueError("axis definitions differ from frozen protocol")

    cohort_path = Path(args.sealed_cohort)
    expected_cohort_hash = protocol["gtex_development"]["sealed_cohort_sha256"]
    if sha256_file(cohort_path) != expected_cohort_hash:
        raise ValueError("sealed GTEx cohort differs from protocol")
    frame = pd.read_parquet(cohort_path)
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"sealed GTEx cohort lacks columns: {missing}")
    frame = frame.copy()
    for column in REQUIRED_COLUMNS:
        if frame[column].isna().any():
            raise ValueError(f"cohort column {column!r} contains missing values")
        frame[column] = frame[column].astype(str)
        if frame[column].eq("").any():
            raise ValueError(f"cohort column {column!r} contains empty values")
    if frame["sample_id"].duplicated().any():
        raise ValueError("sealed GTEx cohort repeats sample IDs")

    organs = tuple(protocol["organ_selection"]["ordered_organs"])
    if len(organs) < 2 or len(set(organs)) != len(organs):
        raise ValueError("protocol organ order is empty or duplicated")
    if set(frame["organ"]) != set(organs):
        raise ValueError("sealed GTEx cohort organ set differs from protocol")
    k = len(organs)
    split_contract = protocol["gtex_development"]
    split, split_report = _assign_donor_splits(
        frame,
        seed=int(split_contract["split_seed"]),
        calibration_fraction=float(split_contract["calibration_fraction"]),
    )
    frame["split"] = split
    frame["utility_split"] = split
    frame["series_group_id"] = frame["donor_id"]
    frame["balanced_train"] = True
    organ_to_label = {organ: index for index, organ in enumerate(organs)}
    organ_axis = f"organ_k{k}"
    frame[organ_axis] = frame["organ"].map(organ_to_label).astype(np.int64)
    frame["pooled_adapter"] = np.zeros(len(frame), dtype=np.int64)

    minimum = int(split_contract["minimum_donors_per_organ_per_split"])
    split_counts: dict[str, dict[str, dict[str, int]]] = {}
    for split_name in ("train", "calibration"):
        selected = frame[frame["split"].eq(split_name)]
        split_counts[split_name] = {}
        for organ in organs:
            subset = selected[selected["organ"].eq(organ)]
            donors = int(subset["donor_id"].nunique())
            if donors < minimum:
                raise ValueError(
                    f"{split_name} {organ} has {donors} donors, below {minimum}"
                )
            split_counts[split_name][organ] = {
                "samples": int(len(subset)),
                "donors": donors,
            }

    random_seeds = tuple(int(value) for value in split_contract["random_partition_seeds"])
    if not random_seeds or len(set(random_seeds)) != len(random_seeds):
        raise ValueError("random partition seeds are empty or duplicated")
    random_reports: dict[str, Any] = {}
    random_axes: list[str] = []
    for seed in random_seeds:
        axis = f"random_k{k}_p{seed}"
        random_axes.append(axis)
        labels = np.empty(len(frame), dtype=np.int64)
        random_reports[axis] = {}
        for split_name in ("train", "calibration"):
            mask = frame["split"].eq(split_name).to_numpy()
            assigned, report = _assign_balanced_random_donors(
                frame.loc[mask],
                organs=organs,
                k=k,
                seed=seed,
                split_name=split_name,
            )
            labels[np.flatnonzero(mask)] = assigned
            random_reports[axis][split_name] = report
        frame[axis] = labels

    split_order = pd.Categorical(
        frame["split"], categories=["train", "calibration"], ordered=True
    )
    frame = (
        frame.assign(_split_order=split_order)
        .sort_values(
            ["_split_order", "sample_id"],
            kind="mergesort",
        )
        .drop(columns="_split_order")
        .reset_index(drop=True)
    )
    output_columns = [
        "sample_id",
        "donor_id",
        "utility_split",
        "split",
        "balanced_train",
        "organ",
        "tissue_site",
        "series_group_id",
        organ_axis,
        *random_axes,
        "pooled_adapter",
    ]
    output = frame[output_columns]

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    manifest_path = output_dir / "gtex_training_manifest.parquet"
    _atomic_parquet(output, manifest_path)
    hashes = {
        "protocol_sha256": sha256_file(protocol_path),
        "sealed_cohort_sha256": sha256_file(cohort_path),
        "manifest_sha256": sha256_file(manifest_path),
        "partition_manifest_sha256": sha256_file(manifest_path),
        "axis_definitions_sha256": sha256_file(axis_definitions_path),
        "sample_order_sha256": sha256_lines(output["sample_id"]),
        "train_donor_ids_sha256": sha256_lines(
            sorted(output.loc[output["split"].eq("train"), "donor_id"].unique())
        ),
        "calibration_donor_ids_sha256": sha256_lines(
            sorted(
                output.loc[output["split"].eq("calibration"), "donor_id"].unique()
            )
        ),
        f"{organ_axis}_assignment_sha256": _assignment_hash(output, organ_axis),
    }
    for axis in random_axes:
        hashes[f"{axis}_assignment_sha256"] = _assignment_hash(output, axis)
    config = {
        "organs": list(organs),
        "k": k,
        "organ_axis": organ_axis,
        "random_axes": random_axes,
        "pooled_adapter_axis": "pooled_adapter",
        "split_unit": "global donor",
        "archs4_expression_accessed": False,
        "efficacy_scoring_performed": False,
    }
    report = {
        "schema_version": 1,
        "status": "complete",
        "test_accessed": False,
        "external_data_accessed": False,
        "code_commit": args.code_commit,
        "metadata_only": True,
        "expression_values_read": False,
        "archs4_expression_accessed": False,
        "efficacy_scoring_performed": False,
        "counts": {
            "samples": int(len(output)),
            "donors": int(output["donor_id"].nunique()),
            "by_split_and_organ": split_counts,
        },
        "split": split_report,
        "random_partitions": random_reports,
        "config": config,
        "hashes": hashes,
    }
    report["hashes"]["resolved_config_sha256"] = sha256_json(config)
    _atomic_json(output_dir / "manifest_report.json", report)
    (output_dir / "MANIFEST_COMPLETE").write_text(
        "GTEx donor-disjoint training manifest complete; ARCHS4 expression sealed.\n"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sealed-cohort", required=True)
    parser.add_argument("--axis-definitions", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    print(json.dumps(build(args), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
