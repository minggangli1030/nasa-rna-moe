#!/usr/bin/env python3
"""Extract the frozen K8 GTEx cohort as canonical-universe TPM.

This is a development-data extractor, not an external-evaluation scorer. It
accepts only the frozen GTEx-to-ARCHS4 development protocol and exact sealed
cohort. ARCHS4 expression is neither an input nor an allowed side effect.
"""

from __future__ import annotations

import argparse
import gzip
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from extract_stage1_k4_gtex import (
    _parse_selected_counts,
    _read_gct_header,
    _read_gencode_gene_map,
)
from stage1_k4_gtex_common import atomic_json, sha256_file, sha256_lines


REQUIRED_STATUS = "frozen_gtex_to_archs4_development_contract"
REQUIRED_COHORT_COLUMNS = {
    "sample_id",
    "donor_id",
    "organ",
    "tissue_site",
    "matrix_column_index",
}


def _load_protocol(path: Path, expected_sha256: str) -> dict[str, Any]:
    if sha256_file(path) != expected_sha256:
        raise ValueError("GTEx-to-ARCHS4 protocol SHA256 mismatch")
    protocol = json.loads(path.read_text())
    if protocol.get("status") != REQUIRED_STATUS:
        raise ValueError("protocol is not frozen for GTEx development")
    if protocol.get("firewalls", {}).get(
        "archs4_lockbox_expression_access_before_candidate_freeze"
    ) is not False:
        raise ValueError("protocol does not close the ARCHS4 expression lockbox")
    return protocol


def _load_genes(path: Path, expected_sha256: str) -> list[str]:
    if sha256_file(path) != expected_sha256:
        raise ValueError("canonical gene list differs from frozen protocol")
    genes = [line.strip() for line in path.read_text().splitlines()]
    if not genes or any(not gene for gene in genes) or len(set(genes)) != len(genes):
        raise ValueError("canonical gene list is empty, duplicated, or malformed")
    return genes


def _load_lengths(path: Path, expected_sha256: str) -> pd.DataFrame:
    if sha256_file(path) != expected_sha256:
        raise ValueError("exon-length table differs from frozen protocol")
    lengths = pd.read_csv(path)
    if list(lengths.columns) != ["gene_symbol", "exon_length"]:
        raise ValueError("exon-length table columns changed")
    if lengths["gene_symbol"].duplicated().any():
        raise ValueError("exon-length table repeats gene symbols")
    if (lengths["exon_length"] <= 0).any():
        raise ValueError("exon-length table contains nonpositive lengths")
    return lengths


def extract(args: argparse.Namespace) -> dict[str, Any]:
    protocol_path = Path(args.protocol)
    protocol = _load_protocol(protocol_path, args.expected_protocol_sha256)
    development = protocol["gtex_development"]
    expression_contract = protocol["expression_contract"]

    counts_path = Path(args.counts_gct)
    if counts_path.stat().st_size != int(development["counts_object_size"]):
        raise ValueError("GTEx counts object size mismatch")
    if sha256_file(counts_path) != development["counts_object_sha256"]:
        raise ValueError("GTEx counts object SHA256 mismatch")

    cohort_path = Path(args.sealed_cohort)
    if sha256_file(cohort_path) != development["sealed_cohort_sha256"]:
        raise ValueError("sealed GTEx cohort differs from frozen protocol")
    cohort = pd.read_parquet(cohort_path)
    missing_columns = sorted(REQUIRED_COHORT_COLUMNS - set(cohort.columns))
    if missing_columns:
        raise ValueError(f"sealed cohort lacks columns: {missing_columns}")
    if cohort["sample_id"].duplicated().any():
        raise ValueError("sealed cohort repeats sample IDs")
    organs = tuple(protocol["organ_selection"]["ordered_organs"])
    if set(cohort["organ"].astype(str)) != set(organs):
        raise ValueError("sealed cohort organ set differs from frozen protocol")
    if len(cohort) != int(development["sealed_samples"]):
        raise ValueError("sealed cohort sample count differs from frozen protocol")
    if int(cohort["donor_id"].nunique()) != int(development["sealed_donors"]):
        raise ValueError("sealed cohort donor count differs from frozen protocol")
    if sha256_lines(cohort["sample_id"].astype(str)) != development[
        "sealed_sample_ids_sha256"
    ]:
        raise ValueError("sealed cohort sample order differs from frozen protocol")

    expected_rows, matrix_samples, header_ids = _read_gct_header(counts_path)
    if expected_rows != int(development["matrix_gene_rows"]):
        raise ValueError("GCT gene-row count differs from frozen protocol")
    if matrix_samples != int(development["matrix_sample_columns"]):
        raise ValueError("GCT sample-column count differs from frozen protocol")
    if sha256_lines(header_ids) != development["matrix_header_sample_ids_sha256"]:
        raise ValueError("GCT sample header differs from frozen protocol")
    selected_columns = cohort["matrix_column_index"].to_numpy(dtype=np.int64)
    if np.any(selected_columns < 0) or np.any(selected_columns >= matrix_samples):
        raise ValueError("sealed cohort contains an invalid GCT matrix column")
    indexed_ids = np.asarray(header_ids, dtype=object)[selected_columns].tolist()
    if indexed_ids != cohort["sample_id"].astype(str).tolist():
        raise ValueError("sealed cohort matrix indices do not reproduce sample IDs")

    genes_path = Path(args.genes)
    genes = _load_genes(
        genes_path, expression_contract["canonical_genes_sha256"]
    )
    if len(genes) != int(protocol["strict_model_family"]["gene_count"]):
        raise ValueError("canonical gene count differs from frozen model contract")
    axis_path = Path(args.axis_definitions)
    if sha256_file(axis_path) != expression_contract["axis_definitions_sha256"]:
        raise ValueError("axis definitions differ from frozen protocol")
    with np.load(axis_path, allow_pickle=False) as definitions:
        definition_genes = definitions["gene_names"].astype(str).tolist()
        score_indices = np.asarray(definitions["score_gene_indices"], dtype=np.int64)
    if definition_genes != genes:
        raise ValueError("axis definitions and canonical gene list differ")
    if np.any(score_indices < 0) or np.any(score_indices >= len(genes)):
        raise ValueError("score-gene indices are out of range")

    lengths_path = Path(args.exon_lengths)
    lengths = _load_lengths(
        lengths_path, expression_contract["exon_lengths_sha256"]
    )
    length_map = dict(
        zip(lengths["gene_symbol"].astype(str), lengths["exon_length"].astype(float))
    )
    missing_lengths = sorted(set(genes) - set(length_map))
    if missing_lengths:
        raise ValueError(f"canonical genes lack exon lengths: {missing_lengths[:5]}")

    v47_path = Path(args.gencode_v47_gtf)
    v49_path = Path(args.gencode_v49_gtf)
    gencode_hashes = expression_contract["gencode_gtf_sha256"]
    if sha256_file(v47_path) != gencode_hashes["v47"]:
        raise ValueError("GENCODE V47 GTF differs from frozen protocol")
    if sha256_file(v49_path) != gencode_hashes["v49"]:
        raise ValueError("GENCODE V49 GTF differs from frozen protocol")
    v47_symbols = _read_gencode_gene_map(v47_path)
    v49_symbols = _read_gencode_gene_map(v49_path)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    scratch = output_dir / ".scratch"
    scratch.mkdir()
    n_samples, n_genes = len(cohort), len(genes)
    gene_index = {gene: index for index, gene in enumerate(genes)}
    length_index = {
        gene: index for index, gene in enumerate(lengths["gene_symbol"].astype(str))
    }
    canonical_counts = np.memmap(
        scratch / "canonical_counts.f32",
        mode="w+",
        dtype=np.float32,
        shape=(n_genes, n_samples),
    )
    canonical_counts[:] = 0
    qc_positive = np.memmap(
        scratch / "length_gene_positive.u8",
        mode="w+",
        dtype=np.uint8,
        shape=(len(lengths), n_samples),
    )
    qc_positive[:] = 0
    observed_canonical: set[str] = set()
    canonical_source_rows: dict[str, int] = {}
    stable_id_renames: dict[str, tuple[str, str]] = {}
    seen_symbols: dict[str, int] = {}
    v47_description_mismatches = 0
    expected_fields = matrix_samples + 2
    rows_read = 0

    with gzip.open(counts_path, "rt") as handle:
        for _ in range(3):
            handle.readline()
        for line in handle:
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 2:
                raise ValueError("malformed GCT data row")
            gene_id, symbol = fields[0].strip(), fields[1].strip()
            stable_id = gene_id.split(".", 1)[0]
            v47_symbol = v47_symbols.get(stable_id)
            mapped_symbol = v49_symbols.get(stable_id, symbol)
            if v47_symbol is not None and v47_symbol != symbol:
                v47_description_mismatches += 1
            if mapped_symbol != symbol:
                stable_id_renames[stable_id] = (symbol, mapped_symbol)
            values = _parse_selected_counts(
                fields, selected_columns, expected_fields=expected_fields
            )
            seen_symbols[symbol] = seen_symbols.get(symbol, 0) + 1
            qc_symbol = mapped_symbol if mapped_symbol in length_index else symbol
            if qc_symbol in length_index:
                qc_positive[length_index[qc_symbol]] |= (values > 0).astype(np.uint8)
            target_symbol = mapped_symbol if mapped_symbol in gene_index else symbol
            if target_symbol in gene_index:
                canonical_counts[gene_index[target_symbol]] += values
                observed_canonical.add(target_symbol)
                canonical_source_rows[target_symbol] = (
                    canonical_source_rows.get(target_symbol, 0) + 1
                )
            rows_read += 1
    if rows_read != expected_rows:
        raise ValueError(f"GCT gene-row count mismatch: {rows_read} != {expected_rows}")

    missing_canonical = sorted(set(genes) - observed_canonical)
    expected_missing = sorted(
        expression_contract["expected_structurally_absent_canonical_genes"]
    )
    if missing_canonical != expected_missing:
        raise ValueError("GTEx structurally absent canonical gene set changed")
    missing_score = sorted(set(np.asarray(genes)[score_indices]) & set(missing_canonical))
    expected_missing_score = sorted(
        expression_contract["externally_unavailable_score_genes"]
    )
    if missing_score != expected_missing_score:
        raise ValueError("GTEx unavailable score-gene set changed")
    if missing_canonical and expression_contract["missing_non_score_genes"] != "zero_fill":
        raise ValueError("GTEx matrix lacks genes and zero-fill is not frozen")

    nonzero = np.zeros(n_samples, dtype=np.int32)
    for start in range(0, len(lengths), 1024):
        nonzero += np.asarray(qc_positive[start : start + 1024]).sum(
            axis=0, dtype=np.int32
        )
    minimum = int(expression_contract["minimum_nonzero_length_mapped_genes"])
    failed = np.flatnonzero(nonzero < minimum)
    if len(failed):
        failed_ids = cohort.iloc[failed]["sample_id"].astype(str).tolist()
        raise ValueError(f"GTEx samples fail frozen expression QC: {failed_ids[:5]}")

    lengths_kb = np.asarray([length_map[gene] / 1000.0 for gene in genes])
    expression_path = output_dir / "expression.parquet"
    writer: pq.ParquetWriter | None = None
    denominators = np.empty(n_samples, dtype=np.float64)
    row_group_size = int(args.row_group_size)
    if row_group_size <= 0:
        raise ValueError("row-group size must be positive")
    try:
        for start in range(0, n_samples, row_group_size):
            stop = min(n_samples, start + row_group_size)
            rates = (
                np.asarray(canonical_counts[:, start:stop], dtype=np.float64)
                / lengths_kb[:, None]
            )
            denominator = rates.sum(axis=0)
            if np.any(denominator <= 0) or not np.isfinite(denominator).all():
                raise ValueError("GTEx canonical TPM denominator is invalid")
            denominators[start:stop] = denominator
            tpm = (rates * (1_000_000.0 / denominator)[None, :]).T.astype(
                np.float32
            )
            batch = pa.Table.from_arrays(
                [
                    pa.array(cohort.iloc[start:stop]["sample_id"].astype(str)),
                    *[pa.array(tpm[:, index]) for index in range(n_genes)],
                ],
                names=["sample_id", *genes],
            )
            if writer is None:
                writer = pq.ParquetWriter(expression_path, batch.schema)
            writer.write_table(batch, row_group_size=len(batch))
    finally:
        if writer is not None:
            writer.close()
    del canonical_counts
    del qc_positive
    shutil.rmtree(scratch)

    report = {
        "schema_version": 1,
        "status": "complete",
        "development_data": True,
        "external_evaluation": False,
        "expression_values_read": True,
        "archs4_expression_accessed": False,
        "expression_space": "tpm",
        "normalization": "canonical-universe TPM from aggregated RNASeQC counts",
        "log_transform_applied": False,
        "samples": n_samples,
        "donors": int(cohort["donor_id"].nunique()),
        "genes": n_genes,
        "score_genes": int(len(score_indices)),
        "externally_available_score_genes": int(
            len(score_indices) - len(missing_score)
        ),
        "gct_rows": rows_read,
        "unique_gct_symbols": len(seen_symbols),
        "duplicate_symbol_count": int(
            sum(value > 1 for value in seen_symbols.values())
        ),
        "canonical_targets_with_multiple_source_rows": int(
            sum(value > 1 for value in canonical_source_rows.values())
        ),
        "stable_id_symbol_renames": len(stable_id_renames),
        "stable_id_symbol_rename_examples": [
            {
                "stable_id": stable_id,
                "v47_or_gct_symbol": values[0],
                "v49_symbol": values[1],
            }
            for stable_id, values in sorted(stable_id_renames.items())[:50]
        ],
        "v47_description_mismatches": v47_description_mismatches,
        "missing_canonical_genes": missing_canonical,
        "missing_score_genes": missing_score,
        "minimum_nonzero_length_mapped_genes": minimum,
        "observed_nonzero_length_mapped_genes": {
            "minimum": int(nonzero.min()),
            "median": float(np.median(nonzero)),
            "maximum": int(nonzero.max()),
        },
        "canonical_rate_denominator": {
            "minimum": float(denominators.min()),
            "maximum": float(denominators.max()),
        },
        "gene_order_sha256": sha256_lines(genes),
        "sample_order_sha256": sha256_lines(cohort["sample_id"].astype(str)),
        "hashes": {
            "protocol_sha256": sha256_file(protocol_path),
            "counts_object_sha256": sha256_file(counts_path),
            "sealed_cohort_sha256": sha256_file(cohort_path),
            "canonical_genes_sha256": sha256_file(genes_path),
            "axis_definitions_sha256": sha256_file(axis_path),
            "exon_lengths_sha256": sha256_file(lengths_path),
            "gencode_v47_gtf_sha256": sha256_file(v47_path),
            "gencode_v49_gtf_sha256": sha256_file(v49_path),
            "expression_sha256": sha256_file(expression_path),
        },
    }
    atomic_json(output_dir / "extraction_report.json", report)
    (output_dir / "EXTRACTION_COMPLETE").write_text(
        "GTEx K8 development extraction complete; ARCHS4 expression sealed.\n"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--counts-gct", required=True)
    parser.add_argument("--sealed-cohort", required=True)
    parser.add_argument("--genes", required=True)
    parser.add_argument("--axis-definitions", required=True)
    parser.add_argument("--exon-lengths", required=True)
    parser.add_argument("--gencode-v47-gtf", required=True)
    parser.add_argument("--gencode-v49-gtf", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--row-group-size", type=int, default=16)
    print(json.dumps(extract(parser.parse_args()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
