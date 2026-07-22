#!/usr/bin/env python3
"""Build train/calibration-only K4/K5 retraining partitions.

The K4 organ subset is frozen by the prior calibration-only Track-B report.
Adipose is encoded as pooled fallback ``-1``.  Three new K4 random controls
partition exactly the same four-organ population while keeping connected
studies atomic.  This builder accepts no expression or test artifact.
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

from train_manifest import sha256_file, sha256_json, sha256_lines, stable_seed  # noqa: E402


CANONICAL_ORGANS = (
    "adipose",
    "brain",
    "liver",
    "skeletal_muscle",
    "skin",
)
K4_ORGANS = (
    "brain",
    "liver",
    "skeletal_muscle",
    "skin",
)
K4_ORGAN_TO_LABEL = {name: index for index, name in enumerate(K4_ORGANS)}
RANDOM_SEEDS = (17, 42, 101)
K5_RANDOM_AXES = tuple(f"random_group_k5_p{seed}" for seed in RANDOM_SEEDS)
K4_EPE_AXES = tuple(f"random_group_k4_epe_p{seed}" for seed in RANDOM_SEEDS)
K4_TOTAL_AXES = tuple(
    f"random_group_k4_total_active_p{seed}" for seed in RANDOM_SEEDS
)
OUTPUT_AXES = (
    "organ_k5",
    "organ_k4_epe",
    "organ_k4_total_active",
    *K5_RANDOM_AXES,
    *K4_EPE_AXES,
    *K4_TOTAL_AXES,
)
REQUIRED_SOURCE_COLUMNS = {
    "sample_id",
    "utility_split",
    "split",
    "organ",
    "series_group_id",
    "organ_k5",
    *K5_RANDOM_AXES,
}


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _atomic_parquet(frame: pd.DataFrame, path: Path) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_parquet(temporary, index=False)
    os.replace(temporary, path)


def _assignment_hash(frame: pd.DataFrame, axis: str) -> str:
    return sha256_lines(
        f"{row.sample_id}\t{getattr(row, axis)}"
        for row in frame[["sample_id", axis]].itertuples(index=False)
    )


def _assign_group_atomic_k4(
    frame: pd.DataFrame,
    *,
    seed: int,
    split_name: str,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Assign active four-organ studies to four balanced random shards."""
    organs = frame["organ"].astype(str)
    active = organs.isin(K4_ORGANS).to_numpy()
    labels = np.full(len(frame), -1, dtype=np.int64)
    selected = frame.loc[active].copy()
    if selected.empty or set(selected["organ"].astype(str)) != set(K4_ORGANS):
        raise ValueError(f"split {split_name!r} lacks one or more active K4 organs")
    mixed_groups = frame.groupby("series_group_id")["organ"].nunique()
    if (mixed_groups != 1).any():
        examples = mixed_groups[mixed_groups != 1].index.astype(str).tolist()[:5]
        raise ValueError(f"connected groups mix organ/fallback roles: {examples}")

    group_organ = (
        selected.groupby(["series_group_id", "organ"], sort=True)
        .size()
        .unstack(fill_value=0)
        .reindex(columns=K4_ORGANS, fill_value=0)
        .astype(np.int64)
    )
    if len(group_organ) < 4:
        raise ValueError(f"split {split_name!r} has fewer than four active studies")
    organ_targets = group_organ.sum(axis=0).to_numpy(dtype=np.float64) / 4.0
    total_target = float(group_organ.to_numpy().sum()) / 4.0
    if np.any(organ_targets <= 0) or total_target <= 0:
        raise ValueError(f"split {split_name!r} has an invalid K4 target")

    records: list[tuple[str, np.ndarray, int, float, int]] = []
    for group, row in group_organ.iterrows():
        counts = row.to_numpy(dtype=np.int64)
        total = int(counts.sum())
        pressure = max(
            float(total / total_target),
            float(np.max(counts / organ_targets)),
        )
        tie = stable_seed(seed, "study_preserving_k4", split_name, str(group), "order")
        records.append((str(group), counts, total, pressure, tie))
    records.sort(key=lambda item: (-item[3], -item[2], item[4], item[0]))

    organ_loads = np.zeros((4, len(K4_ORGANS)), dtype=np.int64)
    total_loads = np.zeros(4, dtype=np.int64)
    assignment: dict[str, int] = {}
    for group, counts, total, _, _ in records:
        tie_order = np.random.default_rng(
            stable_seed(seed, "study_preserving_k4", split_name, group, "tie")
        ).permutation(4)
        tie_rank = {int(shard): rank for rank, shard in enumerate(tie_order)}
        candidates: list[tuple[float, float, float, int, int]] = []
        for shard in range(4):
            candidate_organs = organ_loads.copy()
            candidate_totals = total_loads.copy()
            candidate_organs[shard] += counts
            candidate_totals[shard] += total
            candidates.append((
                round(float(
                    np.mean(np.square(candidate_organs / organ_targets[None, :]))
                    + np.mean(np.square(candidate_totals / total_target))
                ), 14),
                float(np.max(candidate_organs / organ_targets[None, :])),
                float(np.max(candidate_totals / total_target)),
                tie_rank[shard],
                shard,
            ))
        shard = min(candidates)[-1]
        assignment[group] = int(shard)
        organ_loads[shard] += counts
        total_loads[shard] += total

    active_labels = selected["series_group_id"].astype(str).map(assignment)
    if active_labels.isna().any():
        raise AssertionError("an active connected group lacks a K4 random label")
    labels[np.flatnonzero(active)] = active_labels.to_numpy(dtype=np.int64)
    if not np.array_equal(np.unique(labels[labels >= 0]), np.arange(4)):
        raise ValueError(f"split {split_name!r} K4 random labels do not cover 0..3")
    labeled = frame.assign(_label=labels)
    active_labeled = labeled.loc[labeled["_label"] >= 0]
    spanning = active_labeled.groupby("series_group_id")["_label"].nunique()
    if (spanning != 1).any():
        raise AssertionError("a K4 random control split a connected study")
    counts = np.bincount(labels[labels >= 0], minlength=4)
    return labels, {
        "partition_seed": int(seed),
        "split": split_name,
        "active_counts": counts.astype(int).tolist(),
        "fallback_count": int(np.sum(labels < 0)),
        "active_connected_studies": int(active_labeled["series_group_id"].nunique()),
        "fallback_connected_studies": int(
            labeled.loc[labeled["_label"] < 0, "series_group_id"].nunique()
        ),
        "group_assignment_sha256": sha256_lines(
            f"{group}\t{assignment[group]}" for group in sorted(assignment)
        ),
        "assignment_algorithm": (
            "outcome-free deterministic greedy group bin packing over the frozen "
            "four-organ active population"
        ),
    }


def build(args: argparse.Namespace) -> dict[str, Any]:
    protocol_path = Path(args.protocol)
    source_path = Path(args.source_partition_manifest)
    source_report_path = Path(args.source_partition_report)
    track_b_path = Path(args.track_b_report)
    output_dir = Path(args.output_dir)
    for path in (protocol_path, source_path, source_report_path, track_b_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output_dir}")

    protocol = json.loads(protocol_path.read_text())
    if protocol.get("evidence_label", {}).get("development_only") is not True:
        raise ValueError("protocol is not development-only")
    if protocol.get("firewall", {}).get("test_access_allowed") is not False:
        raise ValueError("protocol does not prohibit test access")
    expected = protocol.get("data", {})
    if sha256_file(source_path) != expected.get("source_train_cal_partitions_sha256"):
        raise ValueError("source partition manifest hash differs from protocol")
    if sha256_file(source_report_path) != expected.get("source_partition_report_sha256"):
        raise ValueError("source partition report hash differs from protocol")
    if sha256_file(track_b_path) != protocol.get("prior_evidence", {}).get(
        "track_b_report_sha256"
    ):
        raise ValueError("Track-B report hash differs from protocol")

    source_report = json.loads(source_report_path.read_text())
    if source_report.get("status") != "complete" or source_report.get("test_accessed") is not False:
        raise ValueError("source partition report is invalid")
    track_b = json.loads(track_b_path.read_text())
    decision = track_b.get("decision", {})
    if (
        track_b.get("status") != "complete"
        or track_b.get("test_accessed") is not False
        or decision.get("selected_k") != 4
    ):
        raise ValueError("Track-B K4 nomination is invalid")
    selected = next(
        (row for row in decision.get("candidates", []) if row.get("k") == 4), None
    )
    frozen_specialists = protocol["prior_evidence"]["frozen_selection"]["k4_specialists"]
    if selected is None or selected.get("selected_specialists") != frozen_specialists:
        raise ValueError("Track-B K4 subset differs from the frozen protocol")

    frame = pd.read_parquet(source_path)
    missing = sorted(REQUIRED_SOURCE_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"source partition artifact lacks columns: {missing}")
    frame = frame.copy()
    for column in ("sample_id", "utility_split", "split", "organ", "series_group_id"):
        if frame[column].isna().any():
            raise ValueError(f"source column {column!r} contains missing values")
        frame[column] = frame[column].astype(str)
    if frame["sample_id"].duplicated().any():
        raise ValueError("source partition artifact contains duplicate sample IDs")
    if set(frame["utility_split"]) != {"train", "calibration"}:
        raise ValueError("source partition artifact is not exactly train/calibration")
    if "test" in set(frame["split"]):
        raise ValueError("source partition artifact contains forbidden test rows")
    if set(frame["organ"]) != set(CANONICAL_ORGANS):
        raise ValueError("source organs differ from the frozen five-organ family")
    if not np.array_equal(np.unique(frame["organ_k5"]), np.arange(5)):
        raise ValueError("source organ K5 labels are invalid")

    organ_k4 = frame["organ"].map(K4_ORGAN_TO_LABEL).fillna(-1).astype(np.int64)
    frame["organ_k4_epe"] = organ_k4
    frame["organ_k4_total_active"] = organ_k4
    balance: dict[str, dict[str, Any]] = {}
    for seed, epe_axis, total_axis in zip(RANDOM_SEEDS, K4_EPE_AXES, K4_TOTAL_AXES):
        split_labels: list[np.ndarray] = []
        balance[epe_axis] = {}
        for split_name in ("train", "calibration"):
            mask = frame["utility_split"].eq(split_name).to_numpy()
            labels, summary = _assign_group_atomic_k4(
                frame.loc[mask], seed=seed, split_name=split_name
            )
            split_labels.append(labels)
            balance[epe_axis][split_name] = summary
        combined = np.concatenate(split_labels)
        expected_order = np.concatenate([
            np.flatnonzero(frame["utility_split"].eq("train")),
            np.flatnonzero(frame["utility_split"].eq("calibration")),
        ])
        if not np.array_equal(expected_order, np.arange(len(frame))):
            raise ValueError("source rows are not ordered train then calibration")
        frame[epe_axis] = combined
        frame[total_axis] = combined

    output_columns = [
        "sample_id",
        "utility_split",
        "split",
        "organ",
        "series_group_id",
        *OUTPUT_AXES,
    ]
    output = frame[output_columns].copy()
    output_path = output_dir / "train_cal_partitions.parquet"
    _atomic_parquet(output, output_path)
    axis_configs: dict[str, Any] = {
        "organ_k5": {
            "k": 5,
            "label_names": list(CANONICAL_ORGANS),
            "fallback_label": None,
            "budget_view": "equal_per_expert_anchor",
        },
        "organ_k4_epe": {
            "k": 4,
            "label_names": list(K4_ORGANS),
            "fallback_label": -1,
            "fallback_name": "adipose",
            "budget_view": "equal_per_expert",
        },
        "organ_k4_total_active": {
            "k": 4,
            "label_names": list(K4_ORGANS),
            "fallback_label": -1,
            "fallback_name": "adipose",
            "budget_view": "equal_active_exposure_total",
        },
    }
    for axis in K5_RANDOM_AXES:
        axis_configs[axis] = {
            "k": 5,
            "label_names": [f"{axis}_shard_{index}" for index in range(5)],
            "fallback_label": None,
            "budget_view": "equal_per_expert_anchor",
            "group_preserving": True,
        }
    for seed, epe_axis, total_axis in zip(RANDOM_SEEDS, K4_EPE_AXES, K4_TOTAL_AXES):
        common = {
            "k": 4,
            "label_names": [f"random_group_k4_p{seed}_shard_{index}" for index in range(4)],
            "fallback_label": -1,
            "fallback_name": "adipose",
            "group_preserving": True,
            "partition_seed": seed,
        }
        axis_configs[epe_axis] = {**common, "budget_view": "equal_per_expert"}
        axis_configs[total_axis] = {
            **common,
            "budget_view": "equal_active_exposure_total",
        }

    hashes = {
        "protocol_sha256": sha256_file(protocol_path),
        "source_partition_manifest_sha256": sha256_file(source_path),
        "source_partition_report_sha256": sha256_file(source_report_path),
        "track_b_report_sha256": sha256_file(track_b_path),
        "axis_definitions_sha256": source_report["hashes"]["axis_definitions_sha256"],
        "partition_manifest_sha256": sha256_file(output_path),
        "train_sample_ids_sha256": sha256_lines(
            output.loc[output["utility_split"].eq("train"), "sample_id"].tolist()
        ),
        "calibration_sample_ids_sha256": sha256_lines(
            output.loc[output["utility_split"].eq("calibration"), "sample_id"].tolist()
        ),
    }
    for axis in OUTPUT_AXES:
        hashes[f"{axis}_assignment_sha256"] = _assignment_hash(output, axis)
    config = {
        "axes": list(OUTPUT_AXES),
        "k4_organs": list(K4_ORGANS),
        "fallback_label": -1,
        "random_partition_seeds": list(RANDOM_SEEDS),
        "test_access_allowed": False,
    }
    report = {
        "schema_version": 1,
        "status": "complete",
        "experiment": "development_only_genuine_organ_k4_k5_retraining_partitions",
        "development_only": True,
        "test_accessed": False,
        "test_assignment_metadata_accessed": False,
        "counts": {
            "train": int(output["utility_split"].eq("train").sum()),
            "calibration": int(output["utility_split"].eq("calibration").sum()),
        },
        "config": config,
        "axes": axis_configs,
        "k4_random_balance": balance,
        "hashes": hashes,
        "resolved_config_sha256": sha256_json(config),
        "artifact": str(output_path.resolve()),
    }
    _atomic_json(output_dir / "partition_report.json", report)
    (output_dir / "COMPLETE").touch()
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--source-partition-manifest", required=True)
    parser.add_argument("--source-partition-report", required=True)
    parser.add_argument("--track-b-report", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser


def main() -> None:
    report = build(build_parser().parse_args())
    print(json.dumps({
        "status": report["status"],
        "development_only": report["development_only"],
        "test_accessed": report["test_accessed"],
        "counts": report["counts"],
        "hashes": report["hashes"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
