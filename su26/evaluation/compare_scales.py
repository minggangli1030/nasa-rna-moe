#!/usr/bin/env python3
"""Paired 5k-versus-20k comparison on identical samples and masks."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from headroom_metrics import balanced_group_mean, paired_bootstrap_ci


def _paired_summary(values, groups, species, seed, bootstrap_reps):
    return {
        "mean": balanced_group_mean(values, groups, species),
        "ci95": paired_bootstrap_ci(
            values, seed, bootstrap_reps, groups=groups, strata=species
        ),
    }


def compare_condition(
    five: pd.DataFrame,
    twenty: pd.DataFrame,
    condition: str,
    groups: np.ndarray,
    species: np.ndarray,
    seed: int,
    bootstrap_reps: int,
) -> dict:
    pearson_delta = (
        twenty[f"{condition}__pearson"].to_numpy()
        - five[f"{condition}__pearson"].to_numpy()
    )
    mse_improvement = (
        five[f"{condition}__mse"].to_numpy()
        - twenty[f"{condition}__mse"].to_numpy()
    )
    result = {
        "condition": condition,
        "pearson_20k_minus_5k": _paired_summary(
            pearson_delta, groups, species, seed, bootstrap_reps
        ),
        "mse_5k_minus_20k": _paired_summary(
            mse_improvement, groups, species, seed + 1, bootstrap_reps
        ),
    }
    return result


def compare_headroom(
    five: pd.DataFrame,
    twenty: pd.DataFrame,
    candidate: str,
    reference: str,
    groups: np.ndarray,
    species: np.ndarray,
    seed: int,
    bootstrap_reps: int,
) -> dict:
    pearson_gain_five = (
        five[f"{candidate}__pearson"].to_numpy()
        - five[f"{reference}__pearson"].to_numpy()
    )
    pearson_gain_twenty = (
        twenty[f"{candidate}__pearson"].to_numpy()
        - twenty[f"{reference}__pearson"].to_numpy()
    )
    mse_gain_five = (
        five[f"{reference}__mse"].to_numpy()
        - five[f"{candidate}__mse"].to_numpy()
    )
    mse_gain_twenty = (
        twenty[f"{reference}__mse"].to_numpy()
        - twenty[f"{candidate}__mse"].to_numpy()
    )
    result = {
        "candidate": candidate,
        "reference": reference,
        "pearson_headroom_5k": balanced_group_mean(pearson_gain_five, groups, species),
        "pearson_headroom_20k": balanced_group_mean(pearson_gain_twenty, groups, species),
        "pearson_headroom_change_20k_minus_5k": _paired_summary(
            pearson_gain_twenty - pearson_gain_five,
            groups, species, seed, bootstrap_reps,
        ),
        "mse_headroom_5k": balanced_group_mean(mse_gain_five, groups, species),
        "mse_headroom_20k": balanced_group_mean(mse_gain_twenty, groups, species),
        "mse_headroom_change_20k_minus_5k": _paired_summary(
            mse_gain_twenty - mse_gain_five,
            groups, species, seed + 1, bootstrap_reps,
        ),
    }
    return result


def _load_report(directory: str) -> tuple[Path, dict]:
    path = Path(directory) / "report.json"
    return path, json.loads(path.read_text())


def _sample_id_sha256(frame: pd.DataFrame) -> str:
    values = "\n".join(frame["sample_id"].astype(str)) + "\n"
    return hashlib.sha256(values.encode("utf-8")).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--five-k-dir", required=True)
    parser.add_argument("--twenty-k-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--group-column", default="series_group_id")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--bootstrap-reps", type=int, default=2000)
    args = parser.parse_args()

    five = pd.read_parquet(Path(args.five_k_dir) / "per_sample_metrics.parquet")
    twenty = pd.read_parquet(Path(args.twenty_k_dir) / "per_sample_metrics.parquet")
    five_report_path, five_report = _load_report(args.five_k_dir)
    twenty_report_path, twenty_report = _load_report(args.twenty_k_dir)
    shared_report_fields = (
        "mask_sha256", "source_cache_mask_sha256", "n_masked_genes",
        "n_common_genes", "input_space", "sample_filter", "group_column",
    )
    for field in shared_report_fields:
        if five_report.get(field) != twenty_report.get(field):
            raise ValueError(
                f"5k and 20k reports differ in {field}; paired scale comparison is invalid"
            )
    identity_columns = ["sample_id", "species", args.group_column, "fold"]
    for column in identity_columns:
        if column not in five or column not in twenty:
            raise ValueError(f"paired comparison is missing identity column: {column}")
        if not np.array_equal(five[column].astype(str), twenty[column].astype(str)):
            raise ValueError(f"5k and 20k differ in {column}; paired comparison is invalid")
    groups = five[args.group_column].astype(str).to_numpy()
    species = five["species"].astype(str).to_numpy()

    conditions = [
        "human", "mouse", "mixed", "uniform",
        "fixed_blend_mse_crossfit",
        "metadata_species_hard_mse_crossfit",
        "metadata_species_soft_mse_crossfit",
        "hard_oracle_pearson", "hard_oracle_mse", "soft_oracle_mse",
    ]
    direct = [
        compare_condition(
            five, twenty, condition, groups, species,
            args.seed + 10 * index, args.bootstrap_reps,
        )
        for index, condition in enumerate(conditions)
    ]
    headroom_pairs = [
        ("fixed_blend_mse_crossfit", "mixed"),
        ("metadata_species_hard_mse_crossfit", "mixed"),
        ("metadata_species_soft_mse_crossfit", "mixed"),
        ("metadata_species_soft_mse_crossfit", "fixed_blend_mse_crossfit"),
        ("hard_oracle_mse", "fixed_blend_mse_crossfit"),
        ("soft_oracle_mse", "fixed_blend_mse_crossfit"),
    ]
    headroom = [
        compare_headroom(
            five, twenty, candidate, reference, groups, species,
            args.seed + 1000 + 10 * index, args.bootstrap_reps,
        )
        for index, (candidate, reference) in enumerate(headroom_pairs)
    ]
    report = {
        "schema_version": 1,
        "estimand": "species-balanced study-macro paired change",
        "residual_scale_change": (
            "not estimated because 5k and 20k use different training-derived "
            "centering profiles; residual gains remain within-scale diagnostics"
        ),
        "n_samples": len(five),
        "n_groups": int(five[args.group_column].nunique()),
        "sample_id_sha256": _sample_id_sha256(five),
        "mask_sha256": five_report["mask_sha256"],
        "source_cache_mask_sha256": five_report["source_cache_mask_sha256"],
        "n_masked_genes": five_report["n_masked_genes"],
        "inputs": {
            "five_k_report": str(five_report_path.resolve()),
            "twenty_k_report": str(twenty_report_path.resolve()),
        },
        "direct_scale_change": direct,
        "headroom_change": headroom,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
