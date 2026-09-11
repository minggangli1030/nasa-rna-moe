#!/usr/bin/env python3
"""Freeze a fair, study-disjoint organ-specialist pilot manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


SPLITS = ("train", "calibration", "test")


def sha256_lines(values) -> str:
    payload = "\n".join(str(value) for value in values) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def stable_seed(seed: int, label: str) -> int:
    digest = hashlib.sha256(f"{seed}:{label}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "little")


def assign_group_splits(
    groups: list[str],
    seed: int,
    calibration_fraction: float,
    test_fraction: float,
    group_weights: dict[str, int] | None = None,
    search_trials: int = 2_000,
) -> dict[str, str]:
    """Assign whole studies while approximately balancing sample counts."""
    groups = sorted(set(groups))
    if len(groups) < 3:
        raise ValueError("at least three groups are required to make three splits")
    if calibration_fraction <= 0 or test_fraction <= 0:
        raise ValueError("calibration and test fractions must be positive")
    if calibration_fraction + test_fraction >= 1:
        raise ValueError("calibration and test fractions must sum to less than one")

    n_calibration = max(1, round(len(groups) * calibration_fraction))
    n_test = max(1, round(len(groups) * test_fraction))
    if n_calibration + n_test >= len(groups):
        raise ValueError("not enough groups remain for training")

    weights = group_weights or {group: 1 for group in groups}
    if set(weights) != set(groups):
        raise ValueError("group weights must cover exactly the supplied groups")
    total_weight = sum(weights.values())
    rng = np.random.default_rng(seed)
    best_order = None
    best_score = float("inf")
    for _ in range(search_trials):
        order = np.asarray(groups, dtype=object)
        rng.shuffle(order)
        test_weight = sum(weights[group] for group in order[:n_test])
        calibration_weight = sum(
            weights[group] for group in order[n_test:n_test + n_calibration]
        )
        score = (
            abs(test_weight / total_weight - test_fraction)
            + abs(calibration_weight / total_weight - calibration_fraction)
        )
        if score < best_score:
            best_score = score
            best_order = order.copy()
    if best_order is None:
        raise AssertionError("split search did not produce an assignment")

    assignments = {group: "test" for group in best_order[:n_test]}
    assignments.update({
        group: "calibration"
        for group in best_order[n_test:n_test + n_calibration]
    })
    assignments.update({
        group: "train" for group in best_order[n_test + n_calibration:]
    })
    return assignments


def build_manifest(frame: pd.DataFrame, args) -> tuple[pd.DataFrame, dict]:
    required = {"sample_id", "organ", "series_group_id", "tumor_like"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"organ candidates are missing columns: {sorted(missing)}")
    if frame["sample_id"].duplicated().any():
        raise ValueError("organ candidates contain duplicate sample IDs")

    work = frame.copy()
    exclusions = {"tumor_like": 0, "multi_organ_group": 0}
    if args.exclude_tumor_like:
        tumor_mask = work["tumor_like"].astype(bool)
        exclusions["tumor_like"] = int(tumor_mask.sum())
        work = work.loc[~tumor_mask].copy()

    organs_per_group = work.groupby("series_group_id")["organ"].nunique()
    multi_organ_groups = set(organs_per_group[organs_per_group > 1].index)
    multi_mask = work["series_group_id"].isin(multi_organ_groups)
    exclusions["multi_organ_group"] = int(multi_mask.sum())
    work = work.loc[~multi_mask].copy()

    capped_parts = []
    for (organ, group), subset in work.groupby(["organ", "series_group_id"], sort=True):
        subset = subset.copy()
        rng = np.random.default_rng(stable_seed(args.seed, f"{organ}:{group}:cap"))
        subset["_rank"] = rng.random(len(subset))
        capped_parts.append(subset.nsmallest(args.max_samples_per_group, "_rank"))
    capped = pd.concat(capped_parts, ignore_index=True).drop(columns="_rank")

    availability_rows = []
    for organ, subset in capped.groupby("organ", sort=True):
        availability_rows.append({
            "organ": organ,
            "n_capped_samples": int(len(subset)),
            "n_series_groups": int(subset["series_group_id"].nunique()),
        })
    availability = pd.DataFrame(availability_rows)
    availability["eligible"] = (
        (availability["n_capped_samples"] >= args.min_capped_samples)
        & (availability["n_series_groups"] >= args.min_series_groups)
    )
    eligible = availability.loc[availability["eligible"]].sort_values(
        ["n_series_groups", "n_capped_samples", "organ"],
        ascending=[False, False, True],
    )
    if args.max_organs:
        eligible = eligible.head(args.max_organs)
    organs = eligible["organ"].tolist()
    if len(organs) < 2:
        raise ValueError(f"only {len(organs)} organs passed the pilot thresholds")

    selected = capped.loc[capped["organ"].isin(organs)].copy()
    selected["split"] = ""
    for organ in organs:
        mask = selected["organ"].eq(organ)
        assignments = assign_group_splits(
            selected.loc[mask, "series_group_id"].tolist(),
            stable_seed(args.seed, f"{organ}:split"),
            args.calibration_fraction,
            args.test_fraction,
            selected.loc[mask].groupby("series_group_id").size().to_dict(),
        )
        selected.loc[mask, "split"] = selected.loc[mask, "series_group_id"].map(assignments)

    if (selected["split"] == "").any():
        raise AssertionError("some selected rows were not assigned a split")
    overlap = selected.groupby("series_group_id")["split"].nunique()
    if (overlap > 1).any():
        raise AssertionError("connected study groups overlap cohort splits")

    selected = selected.sort_values(
        ["split", "organ", "series_group_id", "sample_id"]
    ).reset_index(drop=True)
    columns = [
        "sample_id", "organ", "series_group_id", "split", "label_evidence",
        "series_id", "source_name", "title", "characteristics",
        "single_cell_probability", "tumor_like",
    ]
    selected = selected[[column for column in columns if column in selected.columns]]

    counts = (
        selected.groupby(["organ", "split"], sort=True)
        .agg(n_samples=("sample_id", "size"), n_series_groups=("series_group_id", "nunique"))
        .reset_index()
    )
    train_ids = selected.loc[selected["split"].eq("train"), "sample_id"].tolist()
    specialist_train_ids = []
    for organ in organs:
        specialist_train_ids.extend(
            selected.loc[
                selected["split"].eq("train") & selected["organ"].eq(organ),
                "sample_id",
            ].tolist()
        )
    report = {
        "schema_version": 1,
        "seed": args.seed,
        "selection": {
            "exclude_tumor_like": args.exclude_tumor_like,
            "max_samples_per_group": args.max_samples_per_group,
            "min_series_groups": args.min_series_groups,
            "min_capped_samples": args.min_capped_samples,
            "max_organs": args.max_organs,
        },
        "split_fractions": {
            "calibration": args.calibration_fraction,
            "test": args.test_fraction,
        },
        "excluded_rows": exclusions,
        "organs": organs,
        "n_experts": len(organs),
        "n_samples": int(len(selected)),
        "n_train_samples": len(train_ids),
        "n_connected_series_groups": int(selected["series_group_id"].nunique()),
        "pooled_train_sample_sha256": sha256_lines(sorted(train_ids)),
        "specialist_union_train_sample_sha256": sha256_lines(sorted(specialist_train_ids)),
        "pooled_train_is_exact_specialist_union": sorted(train_ids) == sorted(specialist_train_ids),
        "manifest_sample_sha256": sha256_lines(selected["sample_id"].tolist()),
        "availability": availability.sort_values("organ").to_dict("records"),
        "cohort_counts": counts.to_dict("records"),
        "warning": (
            "This freezes a conservative regex-labeled pipeline pilot. Manually validate labels "
            "and expand ontology-backed coverage before a definitive organ-specialization claim."
        ),
    }
    return selected, report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-samples-per-group", type=int, default=20)
    parser.add_argument("--min-series-groups", type=int, default=45)
    parser.add_argument("--min-capped-samples", type=int, default=300)
    parser.add_argument("--max-organs", type=int, default=0)
    parser.add_argument("--calibration-fraction", type=float, default=0.15)
    parser.add_argument("--test-fraction", type=float, default=0.15)
    parser.add_argument(
        "--include-tumor-like", dest="exclude_tumor_like", action="store_false"
    )
    parser.set_defaults(exclude_tumor_like=True)
    args = parser.parse_args()

    frame = pd.read_parquet(args.candidates)
    manifest, report = build_manifest(frame, args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest.to_parquet(output_dir / "organ_pilot_manifest.parquet", index=False)
    manifest.to_csv(output_dir / "organ_pilot_manifest.csv", index=False)
    (output_dir / "manifest_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
