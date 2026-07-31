#!/usr/bin/env python3
"""Evaluate one frozen Stage 2B seed under the common Tier-1 axis screen."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.multiaxis_tier1 import (
    donor_bootstrap_incremental_r2,
    fixed_scale_numeric,
    incremental_grouped_ridge,
    partial_correlations,
    permute_within_organ,
    stable_one_hot,
)
from core.stage2b_diagnostics import array_sha256
from core.train_manifest import sha256_file


def atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def parse_gmt(path: Path) -> dict[str, tuple[str, ...]]:
    output = {}
    for line in path.read_text().splitlines():
        fields = line.rstrip().split("\t")
        if len(fields) < 3:
            raise ValueError("invalid GMT row")
        output[fields[0]] = tuple(dict.fromkeys(fields[2:]))
    if len(output) != 50 or any(not name.startswith("HALLMARK_") for name in output):
        raise ValueError("Hallmark GMT must contain exactly 50 named sets")
    return output


def load_cache(
    root: Path, seed: int, expected_protocol: str, expected_metadata_sha: str
) -> dict[str, np.ndarray]:
    metadata_path = root / "run_metadata.json"
    if sha256_file(metadata_path) != expected_metadata_sha:
        raise ValueError("seed run metadata SHA256 differs from Tier-1 protocol")
    metadata = json.loads(metadata_path.read_text())
    if (
        metadata.get("status") != "complete"
        or metadata.get("mechanical_only") is not False
        or int(metadata.get("seed", -1)) != seed
        or metadata.get("protocol_sha256") != expected_protocol
        or int(metadata.get("rows", -1)) != 7369
    ):
        raise ValueError("canonical cache metadata is not a valid frozen full run")
    path = root / "canonical_cache.npz"
    if sha256_file(path) != metadata["hashes"]["canonical_cache_sha256"]:
        raise ValueError("canonical cache file SHA256 differs")
    with np.load(path, allow_pickle=False) as archive:
        cache = {name: archive[name] for name in archive.files}
    for name, value in cache.items():
        if array_sha256(value) != metadata["hashes"]["canonical_arrays"][name]:
            raise ValueError(f"canonical array hash differs: {name}")
    if not np.array_equal(cache["sample_ordinal"], np.arange(7369)):
        raise ValueError("canonical cache order does not reconstruct training rows")
    return cache


def _normalized_numeric(series: pd.Series) -> np.ndarray:
    return pd.to_numeric(series, errors="coerce").to_numpy(dtype=np.float64)


def build_features(
    training: pd.DataFrame,
    metadata: pd.DataFrame,
    expression: pd.DataFrame,
    gene_names: list[str],
    score_indices: np.ndarray,
    hallmark: dict[str, tuple[str, ...]],
    protocol: dict,
) -> tuple[np.ndarray, dict[str, np.ndarray], dict[str, Any], np.ndarray]:
    aligned = metadata.set_index("sample_id").reindex(
        training["sample_id"].astype(str)
    )
    if aligned.index.has_duplicates or aligned.isna().all(axis=1).any():
        raise ValueError("training metadata does not align one-to-one")
    if (
        aligned["donor_id"].astype(str).to_numpy()
        != training["series_group_id"].astype(str).to_numpy()
    ).any():
        raise ValueError("training metadata donor join differs")

    organ, organ_levels = stable_one_hot(training["organ"].astype(str))
    rin = _normalized_numeric(aligned["rin"])
    ischemic = _normalized_numeric(aligned["ischemic_time_minutes"])
    values = expression[gene_names].to_numpy(dtype=np.float32)
    if not np.isfinite(values).all():
        raise ValueError("training expression contains nonfinite values")
    logged = np.log1p(values, dtype=np.float32)
    detected = (values > 0).mean(axis=1).astype(np.float64)
    log_sum = np.log1p(values.sum(axis=1)).astype(np.float64) / 20.0
    technical = np.column_stack(
        [
            np.where(np.isfinite(rin), rin / 10.0, 0.0),
            np.where(np.isfinite(ischemic), ischemic / 2000.0, 0.0),
            detected,
            log_sum,
        ]
    )
    base = np.column_stack(
        [
            organ,
            fixed_scale_numeric(rin, 10.0),
            fixed_scale_numeric(ischemic, 2000.0),
            detected,
            log_sum,
        ]
    )

    tissue, tissue_levels = stable_one_hot(aligned["tissue_site"].astype(str))
    sex, sex_levels = stable_one_hot(aligned["sex_code"].astype(str))
    age, age_levels = stable_one_hot(aligned["age_bracket"].astype(str))

    score_set = set(np.asarray(gene_names, dtype=str)[score_indices].tolist())
    gene_lookup = {gene: index for index, gene in enumerate(gene_names)}
    visible_sets = {}
    program_columns = []
    union_indices = sorted(
        {
            gene_lookup[gene]
            for members in hallmark.values()
            for gene in members
            if gene in gene_lookup and gene not in score_set
        }
    )
    union = logged[:, union_indices].astype(np.float64)
    mean = union.mean(axis=0)
    scale = union.std(axis=0, ddof=1)
    standardized = (union - mean) / np.maximum(scale, 1e-8)
    union_lookup = {gene_names[index]: offset for offset, index in enumerate(union_indices)}
    minimum = int(
        protocol["candidates"]["hallmark_50"]["minimum_visible_genes_per_set"]
    )
    for name, members in sorted(hallmark.items()):
        retained = [gene for gene in members if gene in union_lookup]
        if len(retained) < minimum:
            raise ValueError(f"{name} has fewer than {minimum} visible genes")
        visible_sets[name] = retained
        program_columns.append(
            standardized[:, [union_lookup[gene] for gene in retained]].mean(axis=1)
        )
    programs = np.column_stack(program_columns)
    if programs.shape[1] != 50 or np.any(programs.std(axis=0) == 0):
        raise ValueError("Hallmark block is incomplete or constant")

    candidates = {
        "tissue_site": tissue,
        "sex": sex,
        "age_bracket": age,
        "hallmark_50": programs,
    }
    inventory = {
        "organ_levels": list(organ_levels),
        "tissue_site_levels": list(tissue_levels),
        "sex_levels": list(sex_levels),
        "age_bracket_levels": list(age_levels),
        "hallmark_names": sorted(hallmark),
        "hallmark_visible_gene_counts": {
            name: len(genes) for name, genes in visible_sets.items()
        },
        "hallmark_visible_gene_sha256": hashlib.sha256(
            json.dumps(visible_sets, sort_keys=True).encode()
        ).hexdigest(),
        "rows": len(training),
        "donors": int(training["series_group_id"].astype(str).nunique()),
    }
    return base, candidates, inventory, technical


def coverage_records(
    training: pd.DataFrame, metadata: pd.DataFrame, candidates: dict[str, np.ndarray]
) -> dict[str, Any]:
    joined = training[["sample_id", "series_group_id", "organ"]].merge(
        metadata, on="sample_id", how="left", validate="one_to_one"
    )
    records: dict[str, Any] = {}
    site = (
        joined.groupby(["organ", "tissue_site"])["series_group_id"]
        .nunique()
        .rename("donors")
        .reset_index()
    )
    eligible = site.loc[site["donors"] >= 20].groupby("organ").size()
    records["tissue_site"] = {
        "informative_organs_with_two_eligible_sites": int((eligible >= 2).sum()),
        "pass": bool((eligible >= 2).sum() >= 5),
    }
    for name, field in (("sex", "sex_code"), ("age_bracket", "age_bracket")):
        table = (
            joined.groupby(field)
            .agg(
                donors=("series_group_id", "nunique"),
                organs=("organ", "nunique"),
            )
            .reset_index()
        )
        passed = bool(((table["donors"] >= 20) & (table["organs"] >= 5)).all())
        records[name] = {
            "levels": table.to_dict(orient="records"),
            "pass": passed,
        }
    programs = candidates["hallmark_50"]
    records["hallmark_50"] = {
        "programs": int(programs.shape[1]),
        "nonconstant_programs": int(np.sum(programs.std(axis=0) > 0)),
        "organs_with_nonconstant_block": int(
            sum(
                np.all(programs[training["organ"].astype(str).to_numpy() == organ].std(axis=0) > 0)
                for organ in sorted(training["organ"].astype(str).unique())
            )
        ),
    }
    records["hallmark_50"]["pass"] = bool(
        records["hallmark_50"]["programs"] == 50
        and records["hallmark_50"]["nonconstant_programs"] == 50
        and records["hallmark_50"]["organs_with_nonconstant_block"] == 8
    )
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--stage2b-protocol", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--expression", required=True)
    parser.add_argument("--router", required=True)
    parser.add_argument("--hallmark-gmt", required=True)
    parser.add_argument("--cache-root", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    protocol_path = Path(args.protocol)
    if sha256_file(protocol_path) != args.expected_protocol_sha256:
        raise ValueError("Tier-1 protocol SHA256 mismatch")
    protocol = json.loads(protocol_path.read_text())
    if protocol.get("status") != "frozen_before_tier1_incremental_outcome_access":
        raise ValueError("Tier-1 protocol is not frozen")
    expected = protocol["inputs"]
    for path, key in (
        (args.stage2b_protocol, "stage2b_protocol_sha256"),
        (args.metadata, "training_metadata_sha256"),
        (args.hallmark_gmt, "hallmark_gmt_sha256"),
        (args.router, "router_sha256"),
    ):
        if sha256_file(path) != expected[key]:
            raise ValueError(f"input SHA256 mismatch: {key}")
    if args.seed not in protocol["training_screen"]["seeds"]:
        raise ValueError("seed is outside frozen protocol")

    stage2b_sha = sha256_file(args.stage2b_protocol)
    cache = load_cache(
        Path(args.cache_root),
        args.seed,
        stage2b_sha,
        expected["seed_run_metadata_sha256"][str(args.seed)],
    )
    manifest = pd.read_parquet(args.manifest)
    training = (
        manifest.loc[
            manifest["split"].astype(str).eq("train")
            & manifest["balanced_train"].astype(bool)
        ]
        .sort_values("sample_id")
        .reset_index(drop=True)
    )
    metadata = pd.read_parquet(args.metadata)
    expression = pd.read_parquet(args.expression)
    expression.index = expression.index.astype(str)
    expression = expression.reindex(training["sample_id"].astype(str))
    with np.load(args.router, allow_pickle=False) as archive:
        gene_names = archive["gene_names"].astype(str).tolist()
        score_indices = archive["score_gene_indices"].astype(np.int64)
    if expression[gene_names].isna().any().any():
        raise ValueError("expression does not align to training membership")

    base, candidates, inventory, technical = build_features(
        training,
        metadata,
        expression,
        gene_names,
        score_indices,
        parse_gmt(Path(args.hallmark_gmt)),
        protocol,
    )
    coverage = coverage_records(training, metadata, candidates)
    donors = training["series_group_id"].astype(str).to_numpy()
    organs = training["organ"].astype(str).to_numpy()
    organ_one_hot, _ = stable_one_hot(organs)
    outcomes = {
        "pooled_reconstruction_error": cache["pooled_mse"],
        "protected_private_error": cache["private_mse"],
        "post_private_coefficients": cache["c_canon"],
    }
    screen = protocol["training_screen"]
    fold_seed = int(screen["fold_seed_base"]) + args.seed
    results: dict[str, Any] = {}
    for name, candidate in candidates.items():
        axis_result: dict[str, Any] = {
            "coverage": coverage[name],
            "technical_proxy_partial_correlations": partial_correlations(
                candidate, technical, organ_one_hot
            ),
            "outcomes": {},
        }
        for outcome_name, target in outcomes.items():
            fit = incremental_grouped_ridge(
                base,
                candidate,
                target,
                donors,
                folds=int(screen["folds"]),
                fold_seed=fold_seed,
                ridge_grid=screen["ridge_grid"],
            )
            record = {
                key: value
                for key, value in fit.items()
                if key not in {"base_prediction", "candidate_prediction"}
            }
            record["donor_bootstrap"] = donor_bootstrap_incremental_r2(
                target,
                fit["base_prediction"],
                fit["candidate_prediction"],
                donors,
                replicates=int(screen["donor_bootstrap"]["replicates"]),
                seed=int(screen["donor_bootstrap"]["seed"]) + args.seed,
            )
            per_organ = {}
            y = np.asarray(target)
            if y.ndim == 1:
                y = y[:, None]
            denominator = float(np.mean(np.square(y - y.mean(axis=0))))
            for organ in sorted(np.unique(organs)):
                rows = organs == organ
                base_mse = float(
                    np.mean(np.square(y[rows] - fit["base_prediction"][rows]))
                )
                candidate_mse = float(
                    np.mean(np.square(y[rows] - fit["candidate_prediction"][rows]))
                )
                per_organ[organ] = (
                    0.0
                    if denominator == 0
                    else (base_mse - candidate_mse) / denominator
                )
            record["per_organ_incremental_r2"] = per_organ
            if outcome_name == screen["primary_outcome"]:
                null = []
                for replicate in range(
                    int(screen["within_organ_permutation"]["replicates"])
                ):
                    shuffled = permute_within_organ(
                        candidate,
                        organs,
                        seed=int(screen["within_organ_permutation"]["seed"])
                        + args.seed * 1000
                        + replicate,
                    )
                    permuted = incremental_grouped_ridge(
                        base,
                        shuffled,
                        target,
                        donors,
                        folds=int(screen["folds"]),
                        fold_seed=fold_seed,
                        ridge_grid=screen["ridge_grid"],
                    )
                    null.append(permuted["incremental_r2"])
                record["within_organ_permutation"] = {
                    "replicates": len(null),
                    "p95": float(np.quantile(null, 0.95)),
                    "median": float(np.median(null)),
                    "real_above_p95": bool(
                        fit["incremental_r2"] > float(np.quantile(null, 0.95))
                    ),
                }
            axis_result["outcomes"][outcome_name] = record
        maximum = max(
            abs(value)
            for row in axis_result["technical_proxy_partial_correlations"]
            for value in row
        )
        axis_result["maximum_absolute_technical_proxy_partial_correlation"] = maximum
        axis_result["technical_proxy_pass"] = bool(
            maximum
            <= screen["technical_proxy_gate"][
                "maximum_absolute_organ_partial_correlation"
            ]
        )
        results[name] = axis_result

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    report = {
        "schema_version": 1,
        "status": "complete",
        "seed": args.seed,
        "protocol_sha256": sha256_file(protocol_path),
        "inventory": inventory,
        "results": results,
        "claim_boundary": (
            "training-donor development screen; no calibration or ARCHS4 access, "
            "no neural fitting, no study-universality claim"
        ),
    }
    report_path = output_dir / "tier1_training_report.json"
    atomic_json(report_path, report)
    (output_dir / "IMMUTABLE_SHA256SUMS").write_text(
        f"{sha256_file(report_path)}  {report_path.name}\n"
    )
    (output_dir / "COMPLETE").touch()


if __name__ == "__main__":
    main()
