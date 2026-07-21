#!/usr/bin/env python3
"""Freeze organ-K5 and study-preserving matched-random confirmation axes.

This builder is deliberately metadata-only.  It consumes the frozen Stage 1
manifest and the already-frozen utility-axis gene definitions, but it accepts
no expression or target path.  The trainer artifact contains only balanced
training rows followed by calibration rows in the exact order selected by the
fixed-bank loader.  Test assignments are omitted unless explicitly requested,
and are then written to a separate sealed artifact.

The existing row-level ``random_0`` through ``random_4`` assignment is retained
unchanged as a non-gating diagnostic.  The confirmatory controls are three
preregistered random K5 axes that assign whole connected studies together and
balance sample count plus organ composition without reconstruction outcomes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = ROOT / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from train_manifest import (  # noqa: E402
    read_manifest,
    select_manifest_rows,
    sha256_file,
    sha256_json,
    sha256_lines,
    stable_seed,
)


CANONICAL_ORGANS = (
    "adipose",
    "brain",
    "liver",
    "skeletal_muscle",
    "skin",
)
CANONICAL_RANDOM_SHARDS = tuple(f"random_{index}" for index in range(5))
ORGAN_TO_LABEL = {name: index for index, name in enumerate(CANONICAL_ORGANS)}
RANDOM_SHARD_TO_LABEL = {
    name: index for index, name in enumerate(CANONICAL_RANDOM_SHARDS)
}
RANDOM_GROUP_AXIS_SEEDS = {
    "random_group_k5_p17": 17,
    "random_group_k5_p42": 42,
    "random_group_k5_p101": 101,
}
RANDOM_GROUP_AXES = tuple(RANDOM_GROUP_AXIS_SEEDS)
RANDOM_GROUP_LABEL_NAMES = tuple(f"random_group_{index}" for index in range(5))
PARTITION_AXES = (
    "organ_k5",
    "random_k5",
    *RANDOM_GROUP_AXES,
)

TRAIN_CAL_FILENAME = "train_cal_partitions.parquet"
PARTITION_REPORT_FILENAME = "partition_report.json"
SEALED_TEST_FILENAME = "sealed_test_assignments.parquet"
SEALED_TEST_REPORT_FILENAME = "sealed_test_report.json"

REQUIRED_MANIFEST_COLUMNS = {
    "sample_id",
    "organ",
    "series_group_id",
    "split",
    "balanced_train",
    "random_shard",
}
REQUIRED_DEFINITION_ARRAYS = {
    "probe_gene_indices",
    "score_gene_indices",
    "context_gene_indices",
    "gene_names",
}


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _atomic_parquet(frame: pd.DataFrame, path: Path) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_parquet(temporary, index=False)
    os.replace(temporary, path)


def _require_hash(report: dict[str, Any], name: str) -> str:
    value = report.get("hashes", {}).get(name)
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"utility partition report lacks valid hash {name!r}")
    return value


def _counts(values: Iterable[str], names: tuple[str, ...]) -> dict[str, int]:
    counts = pd.Series(list(values), dtype="object").value_counts().to_dict()
    return {name: int(counts.get(name, 0)) for name in names}


def _validate_utility_inputs(
    *,
    utility_report_path: Path,
    definitions_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not utility_report_path.is_file():
        raise FileNotFoundError(
            f"utility partition report does not exist: {utility_report_path}"
        )
    if not definitions_path.is_file():
        raise FileNotFoundError(f"axis definitions do not exist: {definitions_path}")
    report = json.loads(utility_report_path.read_text())
    if report.get("status") != "complete":
        raise ValueError("utility partition report is not complete")
    if report.get("test_accessed") is not False:
        raise ValueError("utility partition report accessed the sealed test split")
    definitions_hash = sha256_file(definitions_path)
    if definitions_hash != _require_hash(report, "axis_definitions_sha256"):
        raise ValueError("axis definitions hash differs from utility partition report")

    with np.load(definitions_path, allow_pickle=False) as archive:
        missing = sorted(REQUIRED_DEFINITION_ARRAYS - set(archive.files))
        if missing:
            raise ValueError(f"axis definitions lack required arrays: {missing}")
        gene_names = archive["gene_names"].astype(str)
        panels = {
            name: np.asarray(archive[name])
            for name in (
                "probe_gene_indices",
                "score_gene_indices",
                "context_gene_indices",
            )
        }
    if gene_names.ndim != 1 or not len(gene_names):
        raise ValueError("axis definition gene_names must be a nonempty vector")
    if len(set(gene_names.tolist())) != len(gene_names):
        raise ValueError("axis definition gene_names contain duplicates")
    normalized_panels: dict[str, np.ndarray] = {}
    for name, raw in panels.items():
        if raw.ndim != 1 or not len(raw):
            raise ValueError(f"axis definition {name} must be a nonempty vector")
        if not np.issubdtype(raw.dtype, np.integer):
            raise ValueError(f"axis definition {name} must contain integer indices")
        values = raw.astype(np.int64, copy=False)
        if values.min() < 0 or values.max() >= len(gene_names):
            raise ValueError(f"axis definition {name} contains an out-of-range index")
        if len(np.unique(values)) != len(values):
            raise ValueError(f"axis definition {name} contains duplicate indices")
        normalized_panels[name] = values
    joined = np.concatenate(list(normalized_panels.values()))
    if not np.array_equal(np.sort(joined), np.arange(len(gene_names))):
        raise ValueError("probe, score, and context gene panels are not a disjoint cover")

    gene_order_hash = sha256_lines(gene_names.tolist())
    reported_gene_hash = report.get("hashes", {}).get("gene_order_sha256")
    if reported_gene_hash is not None and reported_gene_hash != gene_order_hash:
        raise ValueError("axis definition gene order differs from utility report")
    reported_partition = report.get("gene_partition", {})
    expected_counts = {
        "probe_genes": len(normalized_panels["probe_gene_indices"]),
        "score_genes": len(normalized_panels["score_gene_indices"]),
        "context_genes": len(normalized_panels["context_gene_indices"]),
    }
    for key, expected in expected_counts.items():
        if key in reported_partition and int(reported_partition[key]) != expected:
            raise ValueError(f"utility report {key} differs from axis definitions")
    definition_summary = {
        "genes": int(len(gene_names)),
        **{key: int(value) for key, value in expected_counts.items()},
        "gene_order_sha256": gene_order_hash,
        "probe_gene_indices_sha256": sha256_lines(
            normalized_panels["probe_gene_indices"].tolist()
        ),
        "score_gene_indices_sha256": sha256_lines(
            normalized_panels["score_gene_indices"].tolist()
        ),
        "context_gene_indices_sha256": sha256_lines(
            normalized_panels["context_gene_indices"].tolist()
        ),
    }
    return report, definition_summary


def _validate_manifest(frame: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(REQUIRED_MANIFEST_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"source manifest lacks required columns: {missing}")
    output = frame.copy()
    for column in ("sample_id", "organ", "series_group_id", "split"):
        if output[column].isna().any():
            raise ValueError(f"source manifest column {column!r} contains missing values")
        output[column] = output[column].astype(str)
    if output["sample_id"].duplicated().any():
        duplicate = output.loc[output["sample_id"].duplicated(), "sample_id"].iloc[0]
        raise ValueError(f"source manifest contains duplicate sample ID {duplicate!r}")
    split_counts = output.groupby("series_group_id")["split"].nunique()
    if (split_counts > 1).any():
        leaked = split_counts[split_counts > 1].index.astype(str).tolist()[:5]
        raise ValueError(f"connected studies cross source splits: {leaked}")
    return output


def _validate_and_label_rows(frame: pd.DataFrame, *, role: str) -> pd.DataFrame:
    if frame.empty:
        raise ValueError(f"{role} contains no rows")
    organs = frame["organ"].astype(str)
    observed_organs = set(organs)
    if observed_organs != set(CANONICAL_ORGANS):
        missing = sorted(set(CANONICAL_ORGANS) - observed_organs)
        unexpected = sorted(observed_organs - set(CANONICAL_ORGANS))
        raise ValueError(
            f"{role} organ labels differ from canonical K5; "
            f"missing={missing}, unexpected={unexpected}"
        )
    if frame["random_shard"].isna().any():
        raise ValueError(f"{role} contains a missing frozen random_shard assignment")
    shards = frame["random_shard"].astype(str)
    observed_shards = set(shards)
    if observed_shards != set(CANONICAL_RANDOM_SHARDS):
        missing = sorted(set(CANONICAL_RANDOM_SHARDS) - observed_shards)
        unexpected = sorted(observed_shards - set(CANONICAL_RANDOM_SHARDS))
        raise ValueError(
            f"{role} random_shard values differ from frozen random_0..4 assignments; "
            f"missing={missing}, unexpected={unexpected}"
        )
    output = frame.copy()
    output["organ_k5"] = organs.map(ORGAN_TO_LABEL).astype(np.int64)
    output["random_k5"] = shards.map(RANDOM_SHARD_TO_LABEL).astype(np.int64)
    expected_labels = np.arange(5)
    for axis in ("organ_k5", "random_k5"):
        unique = np.sort(output[axis].unique())
        if not np.array_equal(unique, expected_labels):
            raise AssertionError(f"{role} {axis} labels are not contiguous K5: {unique}")
    return output


def _group_integrity_summary(
    frame: pd.DataFrame,
    label_column: str,
    *,
    fail_on_split: bool,
) -> dict[str, Any]:
    if label_column not in frame:
        raise ValueError(f"partition frame lacks axis {label_column!r}")
    by_group = frame.groupby("series_group_id", sort=True)[label_column].nunique()
    spanning = by_group[by_group != 1].index.astype(str).tolist()
    summary = {
        "passed": not spanning,
        "connected_studies": int(len(by_group)),
        "groups_spanning_shards": int(len(spanning)),
        "spanning_group_examples": spanning[:5],
    }
    if spanning and fail_on_split:
        raise ValueError(
            f"axis {label_column!r} splits connected studies across shards: "
            f"{spanning[:5]}"
        )
    return summary


def _study_preserving_balance_summary(
    frame: pd.DataFrame,
    label_column: str,
    *,
    fail_on_group_split: bool = True,
) -> dict[str, Any]:
    labels = frame[label_column].to_numpy(dtype=np.int64)
    if labels.ndim != 1 or len(labels) != len(frame):
        raise ValueError(f"axis {label_column!r} is not row aligned")
    if len(labels) and (labels.min() < 0 or labels.max() >= 5):
        raise ValueError(f"axis {label_column!r} has a label outside [0, 5)")
    total_counts = np.bincount(labels, minlength=5).astype(np.int64)
    organ_counts = np.zeros((5, len(CANONICAL_ORGANS)), dtype=np.int64)
    organ_values = frame["organ"].map(ORGAN_TO_LABEL).to_numpy(dtype=np.int64)
    np.add.at(organ_counts, (labels, organ_values), 1)
    per_organ_imbalance = {
        organ: int(organ_counts[:, index].max() - organ_counts[:, index].min())
        for index, organ in enumerate(CANONICAL_ORGANS)
    }
    organ_means = organ_counts.mean(axis=0)
    fractional_per_organ = {
        organ: (
            float(per_organ_imbalance[organ] / organ_means[index])
            if organ_means[index] > 0
            else 0.0
        )
        for index, organ in enumerate(CANONICAL_ORGANS)
    }
    total_mean = float(total_counts.mean())
    total_imbalance = int(total_counts.max() - total_counts.min())
    return {
        "counts": total_counts.tolist(),
        "organ_counts_by_shard": {
            str(shard): {
                organ: int(organ_counts[shard, organ_index])
                for organ_index, organ in enumerate(CANONICAL_ORGANS)
            }
            for shard in range(5)
        },
        "connected_studies_per_partition": [
            int(frame.loc[frame[label_column].eq(shard), "series_group_id"].nunique())
            for shard in range(5)
        ],
        "total_sample_imbalance_max_minus_min": total_imbalance,
        "total_sample_fractional_imbalance": (
            float(total_imbalance / total_mean) if total_mean > 0 else 0.0
        ),
        "per_organ_sample_imbalance_max_minus_min": per_organ_imbalance,
        "maximum_per_organ_sample_imbalance": int(
            max(per_organ_imbalance.values(), default=0)
        ),
        "per_organ_fractional_imbalance": fractional_per_organ,
        "maximum_per_organ_fractional_imbalance": float(
            max(fractional_per_organ.values(), default=0.0)
        ),
        "group_integrity": _group_integrity_summary(
            frame, label_column, fail_on_split=fail_on_group_split
        ),
    }


def _assign_study_preserving_labels(
    frame: pd.DataFrame,
    *,
    partition_seed: int,
    split_name: str,
    require_all_labels: bool,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Greedily balance group-atomic sample/organ loads across five shards."""
    if frame.empty:
        raise ValueError(f"cannot assign an empty split {split_name!r}")
    if set(frame["organ"].astype(str)) - set(CANONICAL_ORGANS):
        raise ValueError(f"split {split_name!r} contains a noncanonical organ")
    group_organ = (
        frame.groupby(["series_group_id", "organ"], sort=True)
        .size()
        .unstack(fill_value=0)
        .reindex(columns=CANONICAL_ORGANS, fill_value=0)
        .astype(np.int64)
    )
    if len(group_organ) < 5 and require_all_labels:
        raise ValueError(
            f"split {split_name!r} has only {len(group_organ)} connected studies; "
            "cannot cover five random-group labels"
        )
    organ_targets = group_organ.sum(axis=0).to_numpy(dtype=np.float64) / 5.0
    total_target = float(group_organ.to_numpy().sum()) / 5.0
    if np.any(organ_targets <= 0) or total_target <= 0:
        raise ValueError(f"split {split_name!r} lacks one or more canonical organs")

    records: list[tuple[str, np.ndarray, int, float, int]] = []
    for group, row in group_organ.iterrows():
        counts = row.to_numpy(dtype=np.int64)
        total = int(counts.sum())
        pressure = max(
            float(total / total_target),
            float(np.max(counts / organ_targets)),
        )
        tie = stable_seed(
            partition_seed, "study_preserving_k5", split_name, str(group), "order"
        )
        records.append((str(group), counts, total, pressure, tie))
    records.sort(key=lambda item: (-item[3], -item[2], item[4], item[0]))

    organ_loads = np.zeros((5, len(CANONICAL_ORGANS)), dtype=np.int64)
    total_loads = np.zeros(5, dtype=np.int64)
    assignment: dict[str, int] = {}
    for group, counts, total, _, _ in records:
        tie_order = np.random.default_rng(
            stable_seed(
                partition_seed,
                "study_preserving_k5",
                split_name,
                group,
                "shard_tie",
            )
        ).permutation(5)
        tie_rank = {int(shard): rank for rank, shard in enumerate(tie_order)}
        candidate_scores: list[tuple[float, float, float, int, int]] = []
        for shard in range(5):
            candidate_organs = organ_loads.copy()
            candidate_totals = total_loads.copy()
            candidate_organs[shard] += counts
            candidate_totals[shard] += total
            organ_objective = float(
                np.mean(np.square(candidate_organs / organ_targets[None, :]))
            )
            total_objective = float(
                np.mean(np.square(candidate_totals / total_target))
            )
            candidate_scores.append((
                round(organ_objective + total_objective, 14),
                float(np.max(candidate_organs / organ_targets[None, :])),
                float(np.max(candidate_totals / total_target)),
                tie_rank[shard],
                shard,
            ))
        shard = min(candidate_scores)[-1]
        assignment[group] = int(shard)
        organ_loads[shard] += counts
        total_loads[shard] += total

    labels = frame["series_group_id"].astype(str).map(assignment)
    if labels.isna().any():
        raise AssertionError("a connected study was left without a random-group label")
    labels_array = labels.to_numpy(dtype=np.int64)
    observed = np.sort(np.unique(labels_array))
    if require_all_labels and not np.array_equal(observed, np.arange(5)):
        raise ValueError(
            f"split {split_name!r} does not cover random-group labels 0..4: {observed}"
        )
    labeled = frame.copy()
    temporary_column = "_study_preserving_label"
    labeled[temporary_column] = labels_array
    summary = _study_preserving_balance_summary(
        labeled, temporary_column, fail_on_group_split=True
    )
    summary.update({
        "partition_seed": int(partition_seed),
        "split": str(split_name),
        "assignment_algorithm": (
            "outcome-free deterministic greedy group bin packing; minimize mean "
            "squared normalized organ loads plus total loads with seeded tie breaks"
        ),
        "group_assignment_sha256": sha256_lines(
            f"{group}\t{assignment[group]}" for group in sorted(assignment)
        ),
    })
    return labels_array, summary


def _add_study_preserving_axes(
    frame: pd.DataFrame,
    *,
    split_name: str,
    require_all_labels: bool,
) -> tuple[pd.DataFrame, dict[str, dict[str, Any]]]:
    output = frame.copy()
    summaries: dict[str, dict[str, Any]] = {}
    for axis, seed in RANDOM_GROUP_AXIS_SEEDS.items():
        labels, summary = _assign_study_preserving_labels(
            output,
            partition_seed=seed,
            split_name=split_name,
            require_all_labels=require_all_labels,
        )
        output[axis] = labels
        summaries[axis] = summary
    return output, summaries


def _artifact_rows(frame: pd.DataFrame, *, utility_split: str) -> pd.DataFrame:
    output = frame[
        ["sample_id", "split", "organ", "series_group_id", "random_shard"]
    ].copy()
    output.insert(1, "utility_split", utility_split)
    output["organ_k5"] = frame["organ_k5"].to_numpy(dtype=np.int64)
    output["random_k5"] = frame["random_k5"].to_numpy(dtype=np.int64)
    for axis in RANDOM_GROUP_AXES:
        output[axis] = frame[axis].to_numpy(dtype=np.int64)
    return output


def _axis_summary(
    train: pd.DataFrame,
    calibration: pd.DataFrame,
    *,
    source_column: str,
    label_column: str,
    label_names: tuple[str, ...],
    kind: str,
    gating_role: str,
    group_preserving: bool,
    partition_seed: int | None = None,
    balance_summaries: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    def split_summary(frame: pd.DataFrame, split_name: str) -> dict[str, Any]:
        label_counts = np.bincount(frame[label_column].to_numpy(), minlength=5)
        studies = [
            int(frame.loc[frame[label_column].eq(index), "series_group_id"].nunique())
            for index in range(5)
        ]
        output = {
            "counts": label_counts.astype(int).tolist(),
            "connected_studies_per_partition": studies,
            "group_integrity": _group_integrity_summary(
                frame,
                label_column,
                fail_on_split=group_preserving,
            ),
        }
        if balance_summaries is not None:
            output.update(balance_summaries[split_name])
        return output

    output = {
        "kind": kind,
        "k": 5,
        "label_names": list(label_names),
        "source_column": source_column,
        "mapping": {name: index for index, name in enumerate(label_names)},
        "gating_role": gating_role,
        "group_preserving": bool(group_preserving),
        "train": split_summary(train, "train"),
        "calibration": split_summary(calibration, "calibration"),
    }
    if partition_seed is not None:
        output["partition_seed"] = int(partition_seed)
    return output


def _assignment_hash(frame: pd.DataFrame, source_column: str) -> str:
    return sha256_lines(
        f"{row.sample_id}\t{getattr(row, source_column)}"
        for row in frame[["sample_id", source_column]].itertuples(index=False)
    )


def build(args: argparse.Namespace | SimpleNamespace) -> dict[str, Any]:
    """Build trainer-only confirmation partitions and optional sealed test labels."""
    manifest_path = Path(args.manifest)
    utility_report_path = Path(args.utility_partition_report)
    definitions_path = Path(args.utility_axis_definitions)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output_dir}")

    utility_report, definition_summary = _validate_utility_inputs(
        utility_report_path=utility_report_path,
        definitions_path=definitions_path,
    )
    manifest = _validate_manifest(read_manifest(manifest_path))
    manifest_hash = sha256_file(manifest_path)
    if manifest_hash != _require_hash(utility_report, "manifest_sha256"):
        raise ValueError("source manifest hash differs from utility partition report")

    train_split = str(getattr(args, "train_split", "train"))
    validation_split = str(getattr(args, "validation_split", "calibration"))
    test_split = str(getattr(args, "test_split", "test"))
    train_filter_column = str(
        getattr(args, "train_filter_column", "balanced_train")
    )
    if len({train_split, validation_split, test_split}) != 3:
        raise ValueError("train, calibration, and test split labels must be distinct")

    # This is intentionally the same selector, arguments, and ordering used by
    # train_fixed_partition_moe._load_inputs and run_packed_training.
    selection = select_manifest_rows(
        manifest,
        role="pooled",
        train_split=train_split,
        validation_split=validation_split,
        train_filter_column=train_filter_column,
    )
    train_ids = selection.train["sample_id"].astype(str).tolist()
    calibration_ids = selection.validation["sample_id"].astype(str).tolist()
    if sha256_lines(train_ids) != _require_hash(
        utility_report, "train_sample_ids_sha256"
    ):
        raise ValueError("balanced training sample order differs from utility report")
    if sha256_lines(calibration_ids) != _require_hash(
        utility_report, "calibration_sample_ids_sha256"
    ):
        raise ValueError("calibration sample order differs from utility report")
    utility_counts = utility_report.get("counts", {})
    if "train" in utility_counts and int(utility_counts["train"]) != len(train_ids):
        raise ValueError("utility report training count differs from source selection")
    if (
        "calibration" in utility_counts
        and int(utility_counts["calibration"]) != len(calibration_ids)
    ):
        raise ValueError("utility report calibration count differs from source selection")

    train = _validate_and_label_rows(selection.train, role="balanced training split")
    calibration = _validate_and_label_rows(
        selection.validation, role="calibration split"
    )
    train, train_group_summaries = _add_study_preserving_axes(
        train,
        split_name="train",
        require_all_labels=True,
    )
    calibration, calibration_group_summaries = _add_study_preserving_axes(
        calibration,
        split_name="calibration",
        require_all_labels=False,
    )
    organ_train_counts = _counts(train["organ"], CANONICAL_ORGANS)
    if len(set(organ_train_counts.values())) != 1:
        raise ValueError(f"balanced training organ counts differ: {organ_train_counts}")
    shard_train_counts = _counts(train["random_shard"], CANONICAL_RANDOM_SHARDS)
    if len(set(shard_train_counts.values())) != 1:
        raise ValueError(
            f"matched-random training shard counts differ: {shard_train_counts}"
        )

    train_cal = pd.concat(
        [
            _artifact_rows(train, utility_split="train"),
            _artifact_rows(calibration, utility_split="calibration"),
        ],
        ignore_index=True,
    )
    expected_ids = train_ids + calibration_ids
    if train_cal["sample_id"].tolist() != expected_ids:
        raise AssertionError("trainer partition sample order changed during construction")
    test_ids = set(manifest.loc[manifest["split"].eq(test_split), "sample_id"])
    if set(train_cal["sample_id"]) & test_ids:
        raise AssertionError("trainer partition artifact contains a test row")
    if test_split in set(train_cal["split"]):
        raise AssertionError("trainer partition artifact names the test split")

    partition_path = output_dir / TRAIN_CAL_FILENAME
    _atomic_parquet(train_cal, partition_path)
    config = {
        "train_split": train_split,
        "validation_split": validation_split,
        "test_split": test_split,
        "train_filter_column": train_filter_column,
        "canonical_organs": list(CANONICAL_ORGANS),
        "canonical_random_shards": list(CANONICAL_RANDOM_SHARDS),
        "random_group_partition_seeds": {
            axis: seed for axis, seed in RANDOM_GROUP_AXIS_SEEDS.items()
        },
        "random_group_assignment_population": {
            "train": "balanced_train rows",
            "calibration": "all calibration rows",
            "test": "all sealed test rows when emitted",
        },
        "emit_sealed_test": bool(getattr(args, "emit_sealed_test", False)),
    }
    hashes: dict[str, str] = {
        "manifest_sha256": manifest_hash,
        "utility_partition_report_sha256": sha256_file(utility_report_path),
        # Keep the compatibility key expected by the fixed-bank loader.
        "axis_definitions_sha256": sha256_file(definitions_path),
        "utility_axis_definitions_sha256": sha256_file(definitions_path),
        "partition_manifest_sha256": sha256_file(partition_path),
        "train_cal_partitions_sha256": sha256_file(partition_path),
        "train_sample_ids_sha256": sha256_lines(train_ids),
        "calibration_sample_ids_sha256": sha256_lines(calibration_ids),
        "train_cal_sample_ids_sha256": sha256_lines(expected_ids),
        "train_cal_organ_assignment_sha256": _assignment_hash(train_cal, "organ"),
        "train_cal_random_shard_assignment_sha256": _assignment_hash(
            train_cal, "random_shard"
        ),
        "gene_order_sha256": definition_summary["gene_order_sha256"],
        "probe_gene_indices_sha256": definition_summary[
            "probe_gene_indices_sha256"
        ],
        "score_gene_indices_sha256": definition_summary[
            "score_gene_indices_sha256"
        ],
        "context_gene_indices_sha256": definition_summary[
            "context_gene_indices_sha256"
        ],
        "resolved_config_sha256": sha256_json(config),
    }
    for axis in RANDOM_GROUP_AXES:
        hashes[f"train_cal_{axis}_assignment_sha256"] = _assignment_hash(
            train_cal, axis
        )

    sealed_metadata: dict[str, Any] | None = None
    if config["emit_sealed_test"]:
        test = manifest.loc[manifest["split"].eq(test_split)].copy()
        test = test.sort_values("sample_id").reset_index(drop=True)
        test = _validate_and_label_rows(test, role="sealed test split")
        test, test_group_summaries = _add_study_preserving_axes(
            test,
            split_name="test",
            require_all_labels=False,
        )
        sealed = _artifact_rows(test, utility_split="test")
        if set(sealed["sample_id"]) & set(expected_ids):
            raise AssertionError("sealed test assignments overlap train/calibration")
        sealed_path = output_dir / SEALED_TEST_FILENAME
        _atomic_parquet(sealed, sealed_path)
        sealed_metadata = {
            "schema_version": 1,
            "status": "complete",
            "artifact_role": "sealed_test_assignment_metadata",
            "sealed": True,
            "test_accessed": False,
            "test_expression_accessed": False,
            "test_targets_accessed": False,
            "assignment_metadata_materialized": True,
            "test_assignment_metadata_accessed": True,
            "counts": {"test": int(len(sealed))},
            "mappings": {
                "organ_k5": ORGAN_TO_LABEL,
                "random_k5": RANDOM_SHARD_TO_LABEL,
                **{
                    axis: {
                        name: index
                        for index, name in enumerate(RANDOM_GROUP_LABEL_NAMES)
                    }
                    for axis in RANDOM_GROUP_AXES
                },
            },
            "partitions": {
                axis: {
                    "kind": "study_preserving_matched_random_control",
                    "partition_seed": RANDOM_GROUP_AXIS_SEEDS[axis],
                    "gating_role": "preregistered_matched_random_control",
                    "group_preserving": True,
                    "test": test_group_summaries[axis],
                }
                for axis in RANDOM_GROUP_AXES
            },
            "hashes": {
                "manifest_sha256": manifest_hash,
                "sealed_test_assignments_sha256": sha256_file(sealed_path),
                "test_sample_ids_sha256": sha256_lines(sealed["sample_id"].tolist()),
                "test_organ_assignment_sha256": _assignment_hash(sealed, "organ"),
                "test_random_shard_assignment_sha256": _assignment_hash(
                    sealed, "random_shard"
                ),
                **{
                    f"test_{axis}_assignment_sha256": _assignment_hash(sealed, axis)
                    for axis in RANDOM_GROUP_AXES
                },
            },
            "guardrail": (
                "contains source-manifest assignment metadata only; no expression, "
                "reconstruction target, prediction, or metric was loaded or computed"
            ),
        }
        sealed_report_path = output_dir / SEALED_TEST_REPORT_FILENAME
        _atomic_json(sealed_report_path, sealed_metadata)
        hashes["sealed_test_assignments_sha256"] = sha256_file(sealed_path)
        hashes["sealed_test_report_sha256"] = sha256_file(sealed_report_path)

    report: dict[str, Any] = {
        "schema_version": 1,
        "status": "complete",
        "research_stage": "stage1_organ_k_confirmation",
        "experiment": "matched_hard_organ_k5_confirmation_partitions",
        "test_accessed": False,
        "test_expression_accessed": False,
        "test_targets_accessed": False,
        "test_assignment_metadata_accessed": bool(config["emit_sealed_test"]),
        "sealed_test_assignment_emitted": config["emit_sealed_test"],
        "axes": list(PARTITION_AXES),
        "gating_axes": ["organ_k5", *RANDOM_GROUP_AXES],
        "non_gating_diagnostic_axes": ["random_k5"],
        "counts": {
            "train": int(len(train)),
            "calibration": int(len(calibration)),
            "train_cal": int(len(train_cal)),
            "balanced_train_by_organ": organ_train_counts,
            "balanced_train_by_random_shard": shard_train_counts,
            "calibration_by_organ": _counts(
                calibration["organ"], CANONICAL_ORGANS
            ),
            "calibration_by_random_shard": _counts(
                calibration["random_shard"], CANONICAL_RANDOM_SHARDS
            ),
        },
        "partitions": {
            "organ_k5": _axis_summary(
                train,
                calibration,
                source_column="organ",
                label_column="organ_k5",
                label_names=CANONICAL_ORGANS,
                kind="canonical_organ_identity",
                gating_role="biological_primary",
                group_preserving=False,
            ),
            "random_k5": _axis_summary(
                train,
                calibration,
                source_column="random_shard",
                label_column="random_k5",
                label_names=CANONICAL_RANDOM_SHARDS,
                kind="legacy_row_level_random_assignment",
                gating_role="non_gating_diagnostic",
                group_preserving=False,
            ),
            **{
                axis: _axis_summary(
                    train,
                    calibration,
                    source_column="series_group_id",
                    label_column=axis,
                    label_names=RANDOM_GROUP_LABEL_NAMES,
                    kind="study_preserving_matched_random_control",
                    gating_role="preregistered_matched_random_control",
                    group_preserving=True,
                    partition_seed=seed,
                    balance_summaries={
                        "train": train_group_summaries[axis],
                        "calibration": calibration_group_summaries[axis],
                    },
                )
                for axis, seed in RANDOM_GROUP_AXIS_SEEDS.items()
            },
        },
        "gene_partition": {
            "source": "frozen utility-axis definitions",
            "genes": definition_summary["genes"],
            "probe_genes": definition_summary["probe_genes"],
            "score_genes": definition_summary["score_genes"],
            "context_genes": definition_summary["context_genes"],
        },
        "config": config,
        "hashes": hashes,
        "guardrails": [
            "trainer artifact contains balanced train then calibration rows only",
            "organ labels use the frozen canonical five-organ mapping",
            "legacy random_k5 maps existing row-level random_0..4 values unchanged and is non-gating",
            "confirmatory random-group axes assign whole connected studies and use no reconstruction outcomes",
            "the builder accepts no expression or reconstruction-target input",
            "optional test assignment metadata is emitted only as a separate sealed artifact",
        ],
    }
    if sealed_metadata is not None:
        report["sealed_test"] = {
            "artifact": SEALED_TEST_FILENAME,
            "report": SEALED_TEST_REPORT_FILENAME,
            "rows": sealed_metadata["counts"]["test"],
        }
    _atomic_json(output_dir / PARTITION_REPORT_FILENAME, report)
    (output_dir / "COMPLETE").touch()
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--utility-partition-report", required=True)
    parser.add_argument("--utility-axis-definitions", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--train-split", default="train")
    parser.add_argument("--validation-split", default="calibration")
    parser.add_argument("--test-split", default="test")
    parser.add_argument("--train-filter-column", default="balanced_train")
    parser.add_argument(
        "--emit-sealed-test",
        action="store_true",
        help="Write test assignment metadata separately; never reads expression/targets.",
    )
    return parser


def main() -> None:
    report = build(build_parser().parse_args())
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
