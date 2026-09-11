#!/usr/bin/env python3
"""Variance decomposition after train-cohort per-gene standardization."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from evaluation.evaluate_training_variance_decomposition import (
    decompose,
    sha256_file,
    squared_distance,
)


def selected_batches(
    parquet: pq.ParquetFile,
    metadata: dict[str, tuple[str, str]],
    batch_size: int,
):
    for batch in parquet.iter_batches(batch_size=batch_size):
        frame = batch.to_pandas()
        keep = frame["sample_id"].astype(str).isin(metadata)
        if not keep.any():
            continue
        selected = frame.loc[keep]
        sample_ids = selected.pop("sample_id").astype(str).tolist()
        raw = selected.to_numpy(dtype=np.float64, copy=False)
        if np.any(raw < 0) or not np.isfinite(raw).all():
            raise ValueError("expression must be finite nonnegative TPM")
        yield sample_ids, np.log1p(raw)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expression", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--batch-size", type=int, default=128)
    args = parser.parse_args()

    manifest = pd.read_parquet(args.manifest)
    required = {"sample_id", "donor_id", "organ", "split"}
    if not required.issubset(manifest.columns):
        raise ValueError(f"manifest lacks {sorted(required - set(manifest.columns))}")
    training = manifest.loc[manifest["split"].astype(str).eq("train")].copy()
    if "balanced_train" in training:
        training = training.loc[training["balanced_train"].astype(bool)].copy()
    if training["sample_id"].duplicated().any() or training.empty:
        raise ValueError("training sample IDs must be unique and nonempty")
    metadata = {
        str(row.sample_id): (str(row.organ), str(row.donor_id))
        for row in training.itertuples(index=False)
    }

    parquet = pq.ParquetFile(args.expression)
    columns = parquet.schema_arrow.names
    if not columns or columns[0] != "sample_id":
        raise ValueError("expression parquet must start with sample_id")
    source_gene_count = len(columns) - 1
    if source_gene_count <= 0:
        raise ValueError("expression parquet has no gene columns")

    # Pass 1: training-only population mean and SD in log1p(TPM) space.
    gene_sum = np.zeros(source_gene_count, dtype=np.float64)
    gene_sum_squares = np.zeros(source_gene_count, dtype=np.float64)
    first_seen: set[str] = set()
    for sample_ids, values in selected_batches(parquet, metadata, args.batch_size):
        duplicates = first_seen.intersection(sample_ids)
        if duplicates:
            raise ValueError(f"duplicate expression sample {next(iter(duplicates))}")
        first_seen.update(sample_ids)
        gene_sum += values.sum(axis=0)
        gene_sum_squares += np.square(values).sum(axis=0)
    missing = set(metadata) - first_seen
    if missing:
        raise ValueError(f"expression is missing {len(missing)} training samples")
    n_rows = len(first_seen)
    mean = gene_sum / n_rows
    variance = np.maximum(gene_sum_squares / n_rows - np.square(mean), 0.0)
    scale = np.sqrt(variance)
    active = scale > 1e-12
    zero_variance_genes = int((~active).sum())
    mean = mean[active]
    scale = scale[active]
    n_genes = int(active.sum())
    if n_genes == 0:
        raise ValueError("all genes have zero training variance")

    # Pass 2: exact decomposition after standardization by the training statistics.
    standardized_gene_sum = np.zeros(n_genes, dtype=np.float64)
    organ_sums: dict[str, np.ndarray] = defaultdict(lambda: np.zeros(n_genes, dtype=np.float64))
    organ_sum_squares: dict[str, float] = defaultdict(float)
    donor_sums: dict[tuple[str, str], np.ndarray] = defaultdict(lambda: np.zeros(n_genes, dtype=np.float64))
    organ_counts: dict[str, int] = defaultdict(int)
    donor_counts: dict[tuple[str, str], int] = defaultdict(int)
    total_sum = 0.0
    total_sum_squares = 0.0
    second_seen: set[str] = set()
    for sample_ids, values in selected_batches(parquet, metadata, args.batch_size):
        standardized = (values[:, active] - mean) / scale
        standardized_gene_sum += standardized.sum(axis=0)
        total_sum += float(standardized.sum())
        total_sum_squares += float(np.square(standardized).sum())
        for index, sample_id in enumerate(sample_ids):
            if sample_id in second_seen:
                raise ValueError(f"duplicate expression sample {sample_id}")
            second_seen.add(sample_id)
            organ, donor = metadata[sample_id]
            row = standardized[index]
            organ_sums[organ] += row
            organ_sum_squares[organ] += float(np.dot(row, row))
            organ_counts[organ] += 1
            donor_sums[(organ, donor)] += row
            donor_counts[(organ, donor)] += 1
    if second_seen != first_seen:
        raise ValueError("two-pass sample membership changed")

    components = decompose(
        n_rows=n_rows,
        n_genes=n_genes,
        total_sum=total_sum,
        total_sum_squares=total_sum_squares,
        gene_sum=standardized_gene_sum,
        organ_sums=dict(organ_sums),
        organ_counts=dict(organ_counts),
        donor_sums=dict(donor_sums),
        donor_counts=dict(donor_counts),
    )
    total = components["total"]
    fractions = {
        key: value / total
        for key, value in components.items()
        if key not in {"total", "identity_relative_error"}
    }
    fractions["within_tissue_total"] = (
        components["between_donor_within_tissue"]
        + components["residual_within_donor_tissue"]
    ) / total

    per_organ = {}
    for organ in sorted(organ_sums):
        count = organ_counts[organ]
        organ_total_sum = float(organ_sums[organ].sum())
        organ_gene_mean = organ_sums[organ] / count
        organ_grand = organ_total_sum / (count * n_genes)
        ss_gene = count * squared_distance(
            organ_gene_mean, np.full(n_genes, organ_grand)
        )
        keys = [key for key in donor_sums if key[0] == organ]
        ss_donor = sum(
            donor_counts[key]
            * squared_distance(donor_sums[key] / donor_counts[key], organ_gene_mean)
            for key in keys
        )
        donor_explained = sum(
            float(np.dot(donor_sums[key], donor_sums[key])) / donor_counts[key]
            for key in keys
        )
        ss_residual = organ_sum_squares[organ] - donor_explained
        if ss_residual < 0 and abs(ss_residual) <= 1e-10 * max(organ_sum_squares[organ], 1.0):
            ss_residual = 0.0
        ss_total = organ_sum_squares[organ] - (
            organ_total_sum * organ_total_sum / (count * n_genes)
        )
        reconstructed = ss_gene + ss_donor + ss_residual
        relative_error = abs(reconstructed - ss_total) / max(ss_total, 1e-300)
        if relative_error >= 1e-6:
            raise AssertionError(f"per-organ identity failed for {organ}: {relative_error:.3e}")
        per_organ[organ] = {
            "samples": count,
            "within_tissue_fraction": (ss_donor + ss_residual) / ss_total,
            "between_donor_fraction": ss_donor / ss_total,
            "residual_fraction": ss_residual / ss_total,
            "identity_relative_error": relative_error,
        }

    report = {
        "status": "complete_descriptive_standardized_diagnostic",
        "interpretation_boundary": (
            "This sizes loss reweighting under per-gene standardization; it does not "
            "measure perturbation-state variance or downstream benefit."
        ),
        "conventions": {
            "input_expression_space": "TPM",
            "base_space": "log1p_TPM_unstandardized",
            "evaluated_space": "training_cohort_per_gene_population_z_score",
            "standardization_fit_scope": "manifest training rows only",
            "gene_set": "full_training_panel",
            "aggregation": "sample_level",
            "donor_nesting": "donor_within_tissue",
        },
        "counts": {
            "samples": n_rows,
            "genes": n_genes,
            "source_genes": source_gene_count,
            "organs": len(organ_sums),
            "unique_donors": int(training["donor_id"].astype(str).nunique()),
            "donor_tissue_groups": len(donor_sums),
            "zero_variance_genes_excluded": zero_variance_genes,
        },
        "components": components,
        "fractions_of_total": fractions,
        "per_organ_diagnostic": per_organ,
        "inputs": {
            "expression": str(args.expression),
            "manifest": str(args.manifest),
            "expression_sha256": sha256_file(args.expression),
            "manifest_sha256": sha256_file(args.manifest),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"counts": report["counts"], "fractions": fractions}, indent=2))


if __name__ == "__main__":
    main()
