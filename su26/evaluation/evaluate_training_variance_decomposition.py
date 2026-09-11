#!/usr/bin/env python3
"""Descriptive variance decomposition in the model's reconstruction-loss space."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def squared_distance(left: np.ndarray, right: np.ndarray) -> float:
    delta = left - right
    return float(np.dot(delta, delta))


def decompose(
    *,
    n_rows: int,
    n_genes: int,
    total_sum: float,
    total_sum_squares: float,
    gene_sum: np.ndarray,
    organ_sums: dict[str, np.ndarray],
    organ_counts: dict[str, int],
    donor_sums: dict[tuple[str, str], np.ndarray],
    donor_counts: dict[tuple[str, str], int],
) -> dict[str, float]:
    grand_mean = total_sum / (n_rows * n_genes)
    gene_mean = gene_sum / n_rows
    ss_total = total_sum_squares - (total_sum * total_sum) / (n_rows * n_genes)
    ss_gene = n_rows * squared_distance(gene_mean, np.full(n_genes, grand_mean))
    ss_tissue = sum(
        organ_counts[organ]
        * squared_distance(values / organ_counts[organ], gene_mean)
        for organ, values in organ_sums.items()
    )
    ss_donor = sum(
        donor_counts[key]
        * squared_distance(
            values / donor_counts[key],
            organ_sums[key[0]] / organ_counts[key[0]],
        )
        for key, values in donor_sums.items()
    )
    explained_donor = sum(
        float(np.dot(values, values)) / donor_counts[key]
        for key, values in donor_sums.items()
    )
    ss_residual = total_sum_squares - explained_donor
    if ss_residual < 0 and abs(ss_residual) <= 1e-10 * max(total_sum_squares, 1.0):
        ss_residual = 0.0
    reconstructed = ss_gene + ss_tissue + ss_donor + ss_residual
    relative_error = abs(reconstructed - ss_total) / max(ss_total, 1e-300)
    if relative_error >= 1e-6:
        raise AssertionError(f"variance identity failed: relative error {relative_error:.3e}")
    return {
        "between_gene": ss_gene,
        "between_tissue_within_gene": ss_tissue,
        "between_donor_within_tissue": ss_donor,
        "residual_within_donor_tissue": ss_residual,
        "total": ss_total,
        "identity_relative_error": relative_error,
    }


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
    gene_columns = columns[1:]
    n_genes = len(gene_columns)
    if n_genes == 0:
        raise ValueError("expression parquet has no gene columns")

    gene_sum = np.zeros(n_genes, dtype=np.float64)
    organ_sums: dict[str, np.ndarray] = defaultdict(lambda: np.zeros(n_genes, dtype=np.float64))
    organ_sum_squares: dict[str, float] = defaultdict(float)
    donor_sums: dict[tuple[str, str], np.ndarray] = defaultdict(lambda: np.zeros(n_genes, dtype=np.float64))
    organ_counts: dict[str, int] = defaultdict(int)
    donor_counts: dict[tuple[str, str], int] = defaultdict(int)
    total_sum = 0.0
    total_sum_squares = 0.0
    seen: set[str] = set()

    for batch in parquet.iter_batches(batch_size=args.batch_size):
        frame = batch.to_pandas()
        keep = frame["sample_id"].astype(str).isin(metadata)
        if not keep.any():
            continue
        selected = frame.loc[keep]
        sample_ids = selected.pop("sample_id").astype(str).tolist()
        raw = selected.to_numpy(dtype=np.float64, copy=False)
        if np.any(raw < 0) or not np.isfinite(raw).all():
            raise ValueError("expression must be finite nonnegative TPM")
        values = np.log1p(raw)
        gene_sum += values.sum(axis=0)
        total_sum += float(values.sum())
        total_sum_squares += float(np.square(values).sum())
        for index, sample_id in enumerate(sample_ids):
            if sample_id in seen:
                raise ValueError(f"duplicate expression sample {sample_id}")
            seen.add(sample_id)
            organ, donor = metadata[sample_id]
            organ_sums[organ] += values[index]
            organ_sum_squares[organ] += float(np.dot(values[index], values[index]))
            organ_counts[organ] += 1
            donor_sums[(organ, donor)] += values[index]
            donor_counts[(organ, donor)] += 1

    missing = set(metadata) - seen
    if missing:
        raise ValueError(f"expression is missing {len(missing)} training samples")

    components = decompose(
        n_rows=len(seen),
        n_genes=n_genes,
        total_sum=total_sum,
        total_sum_squares=total_sum_squares,
        gene_sum=gene_sum,
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
        ss_gene = count * squared_distance(organ_gene_mean, np.full(n_genes, organ_grand))
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
            raise AssertionError(
                f"per-organ variance identity failed for {organ}: {relative_error:.3e}"
            )
        per_organ[organ] = {
            "samples": count,
            "donor_tissue_groups": len(keys),
            "between_gene_ss": ss_gene,
            "between_donor_within_tissue_ss": ss_donor,
            "residual_within_donor_tissue_ss": ss_residual,
            "total_ss": ss_total,
            "within_tissue_fraction": (ss_donor + ss_residual) / ss_total,
            "between_donor_fraction": ss_donor / ss_total,
            "residual_fraction": ss_residual / ss_total,
            "identity_relative_error": relative_error,
            "grand_mean": organ_grand,
        }

    report = {
        "status": "complete_descriptive_diagnostic",
        "interpretation_boundary": (
            "Within-tissue variance includes donor biology, perturbation state, and "
            "technical noise; it is not itself a perturbation-state fraction."
        ),
        "conventions": {
            "input_expression_space": "TPM",
            "loss_space": "log1p_TPM_unstandardized",
            "gene_set": "full_training_panel",
            "aggregation": "sample_level",
            "donor_nesting": "donor_within_tissue",
            "cohort": "manifest split=train and balanced_train=true when present",
        },
        "counts": {
            "samples": len(seen),
            "genes": n_genes,
            "organs": len(organ_sums),
            "unique_donors": int(training["donor_id"].astype(str).nunique()),
            "donor_tissue_groups": len(donor_sums),
            "samples_by_organ": dict(sorted(organ_counts.items())),
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
