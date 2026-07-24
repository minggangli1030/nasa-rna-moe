#!/usr/bin/env python3
"""Freeze a GTEx GCT header, then extract the one-time canonical TPM matrix.

The ``freeze-header`` command reads only the three GCT preamble/header lines.
The ``extract`` command is permitted only against the resulting sealed cohort
artifact and performs the frozen count aggregation, QC, and TPM conversion.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import json
import os
import re
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from stage1_k4_gtex_common import (
    ORGANS,
    atomic_json,
    load_frozen_protocol,
    sha256_file,
    sha256_lines,
)

GENE_ID_RE = re.compile(r'gene_id "([^"]+)"')
GENE_NAME_RE = re.compile(r'gene_name "([^"]+)"')


def _verify_counts_object(path: Path, source: dict) -> dict[str, str]:
    if path.stat().st_size != int(source["file_size"]):
        raise ValueError("GTEx counts object size mismatch")
    actual_sha256 = sha256_file(path)
    if "sha256" in source:
        if actual_sha256 != source["sha256"]:
            raise ValueError("GTEx counts object SHA256 mismatch")
    else:
        try:
            import google_crc32c
        except ImportError as error:
            raise RuntimeError(
                "google-crc32c is required to verify the prebound composite "
                "GTEx object CRC32C"
            ) from error
        checksum = google_crc32c.Checksum()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
                checksum.update(chunk)
        actual_crc32c = base64.b64encode(checksum.digest()).decode("ascii")
        if actual_crc32c != source["crc32c_base64"]:
            raise ValueError("GTEx counts object CRC32C mismatch")
    return {"sha256": actual_sha256}


def _read_gct_header(path: Path) -> tuple[int, int, list[str]]:
    with gzip.open(path, "rt") as handle:
        version = handle.readline().rstrip("\n")
        dimensions = handle.readline().rstrip("\n").split("\t")
        header = handle.readline().rstrip("\n").split("\t")
    if version != "#1.2":
        raise ValueError(f"unsupported GCT version: {version!r}")
    if len(dimensions) != 2:
        raise ValueError("invalid GCT dimensions line")
    gene_rows, sample_count = map(int, dimensions)
    if header[:2] != ["Name", "Description"]:
        raise ValueError("GCT header must start with Name and Description")
    sample_ids = header[2:]
    if len(sample_ids) != sample_count or len(set(sample_ids)) != sample_count:
        raise ValueError("GCT sample header count or uniqueness mismatch")
    return gene_rows, sample_count, sample_ids


def _read_gencode_gene_map(path: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    with gzip.open(path, "rt") as handle:
        for line in handle:
            if line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t", 8)
            if len(fields) != 9 or fields[2] != "gene":
                continue
            gene_id = GENE_ID_RE.search(fields[8])
            gene_name = GENE_NAME_RE.search(fields[8])
            if gene_id is None or gene_name is None:
                raise ValueError("GENCODE gene record lacks gene_id or gene_name")
            stable_id = gene_id.group(1).split(".", 1)[0]
            symbol = gene_name.group(1)
            previous = mapping.get(stable_id)
            if previous is not None and previous != symbol:
                raise ValueError(
                    f"GENCODE stable ID maps to conflicting symbols: {stable_id}"
                )
            mapping[stable_id] = symbol
    if not mapping:
        raise ValueError("GENCODE GTF contains no gene mappings")
    return mapping


def freeze_header(args: argparse.Namespace) -> dict:
    protocol = load_frozen_protocol(args.protocol, args.expected_protocol_sha256)
    counts = Path(args.counts_gct)
    source = protocol["source"]["counts_object"]
    verified = _verify_counts_object(counts, source)
    expected_cohort_hash = protocol["source"].get("provisional_cohort_sha256")
    if expected_cohort_hash and sha256_file(args.provisional_cohort) != expected_cohort_hash:
        raise ValueError("provisional GTEx cohort differs from frozen protocol")
    cohort = pd.read_csv(args.provisional_cohort, keep_default_na=False)
    required = {"sample_id", "donor_id", "organ", "tissue_site"}
    missing = sorted(required - set(cohort.columns))
    if missing:
        raise ValueError(f"provisional cohort lacks columns: {missing}")
    if cohort["sample_id"].duplicated().any():
        raise ValueError("provisional cohort repeats sample IDs")
    if set(cohort["organ"].astype(str)) != set(ORGANS):
        raise ValueError("provisional cohort does not cover all organs")

    gene_rows, matrix_samples, header_ids = _read_gct_header(counts)
    header_set = set(header_ids)
    cohort_set = set(cohort["sample_id"].astype(str))
    absent = sorted(cohort_set - header_set)
    attributes_path = Path(args.sample_attributes)
    expected_attributes_hash = protocol["source"]["sample_attributes_sha256"]
    if sha256_file(attributes_path) != expected_attributes_hash:
        raise ValueError("GTEx sample attributes differ from frozen protocol")
    attributes = pd.read_csv(
        attributes_path,
        sep="\t",
        dtype=str,
        keep_default_na=False,
        low_memory=False,
    )
    if not {"SAMPID", "SMAFRZE"}.issubset(attributes.columns):
        raise ValueError("GTEx sample attributes lack SAMPID or SMAFRZE")
    if attributes["SAMPID"].duplicated().any():
        raise ValueError("GTEx sample attributes repeat SAMPID")
    flags = attributes.set_index("SAMPID")["SMAFRZE"]
    missing_flags = sorted(cohort_set - set(flags.index.astype(str)))
    if missing_flags:
        raise ValueError(f"cohort samples lack GTEx inclusion flags: {missing_flags[:5]}")
    present = sorted(cohort_set & header_set)
    bad_present = [sample for sample in present if flags[sample] != "RNASEQ"]
    bad_absent = [sample for sample in absent if flags[sample] != "EXCLUDE"]
    if bad_present:
        raise ValueError(
            f"header-present samples are not marked RNASEQ: {bad_present[:5]}"
        )
    if bad_absent:
        raise ValueError(
            f"header-absent samples are not officially EXCLUDE: {bad_absent[:5]}"
        )
    sealed = cohort[cohort["sample_id"].isin(header_set)].copy()
    sealed = sealed.sort_values("sample_id").reset_index(drop=True)
    sealed["matrix_column_index"] = [
        header_ids.index(sample_id) for sample_id in sealed["sample_id"].astype(str)
    ]
    exclusions = cohort[~cohort["sample_id"].isin(header_set)].copy()
    exclusions = exclusions.sort_values("sample_id").reset_index(drop=True)
    exclusions["official_matrix_flag"] = exclusions["sample_id"].map(flags)
    exclusions["matrix_membership_decision"] = "exclude_official_SMAFRZE_EXCLUDE"
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    sealed_path = output_dir / "sealed_cohort.parquet"
    exclusions_path = output_dir / "matrix_membership_exclusions.parquet"
    sealed.to_parquet(sealed_path, index=False)
    exclusions.to_parquet(exclusions_path, index=False)
    report = {
        "schema_version": 1,
        "status": "header_frozen",
        "expression_values_read": False,
        "counts_object_sha256": verified["sha256"],
        "protocol_sha256": sha256_file(args.protocol),
        "provisional_cohort_sha256": sha256_file(args.provisional_cohort),
        "sample_attributes_sha256": sha256_file(attributes_path),
        "sealed_cohort_sha256": sha256_file(sealed_path),
        "matrix_membership_exclusions_sha256": sha256_file(exclusions_path),
        "matrix_gene_rows": gene_rows,
        "matrix_sample_columns": matrix_samples,
        "provisional_samples": len(cohort),
        "selected_samples": len(sealed),
        "selected_donors": int(sealed["donor_id"].nunique()),
        "selected_sample_ids_sha256": sha256_lines(sealed["sample_id"]),
        "matrix_header_sample_ids_sha256": sha256_lines(header_ids),
        "matrix_membership_exclusions": {
            "samples": len(exclusions),
            "official_flag": "SMAFRZE=EXCLUDE",
            "by_organ": {
                str(key): int(value)
                for key, value in exclusions["organ"].value_counts().sort_index().items()
            },
        },
    }
    atomic_json(output_dir / "header_report.json", report)
    (output_dir / "HEADER_FROZEN").write_text("expression values not read\n")
    return report


def _parse_selected_counts(
    fields: list[str], selected_columns: np.ndarray, *, expected_fields: int
) -> np.ndarray:
    if len(fields) != expected_fields:
        raise ValueError("GCT data row field count mismatch")
    try:
        values = np.fromiter(
            (float(fields[int(index) + 2]) for index in selected_columns),
            dtype=np.float32,
            count=len(selected_columns),
        )
    except ValueError as error:
        raise ValueError("GCT contains a nonnumeric selected count") from error
    if np.any(values < 0) or not np.isfinite(values).all():
        raise ValueError("GCT contains invalid selected counts")
    return values


def extract(args: argparse.Namespace) -> dict:
    protocol = load_frozen_protocol(args.protocol, args.expected_protocol_sha256)
    header_dir = Path(args.header_dir)
    header_report_path = header_dir / "header_report.json"
    sealed_path = header_dir / "sealed_cohort.parquet"
    if not (header_dir / "HEADER_FROZEN").is_file():
        raise ValueError("GTEx header was not frozen")
    header_report = json.loads(header_report_path.read_text())
    if header_report.get("status") != "header_frozen":
        raise ValueError("GTEx header report is not frozen")
    if header_report.get("protocol_sha256") != sha256_file(args.protocol):
        raise ValueError("GTEx header report protocol mismatch")
    if header_report.get("sealed_cohort_sha256") != sha256_file(sealed_path):
        raise ValueError("sealed GTEx cohort hash mismatch")

    counts = Path(args.counts_gct)
    if header_report["counts_object_sha256"] != sha256_file(counts):
        raise ValueError("counts object differs from frozen header source")
    genes = [line.strip() for line in Path(args.genes).read_text().splitlines()]
    expected_artifacts = protocol["model"].get("candidate_artifact_sha256", {})
    if expected_artifacts.get("canonical_genes") and (
        sha256_file(args.genes) != expected_artifacts["canonical_genes"]
    ):
        raise ValueError("canonical gene list differs from frozen protocol")
    if not genes or len(set(genes)) != len(genes):
        raise ValueError("canonical gene list is empty or duplicated")
    lengths = pd.read_csv(args.exon_lengths)
    if protocol["expression"].get("exon_lengths_sha256") and (
        sha256_file(args.exon_lengths)
        != protocol["expression"]["exon_lengths_sha256"]
    ):
        raise ValueError("exon-length table differs from frozen protocol")
    if list(lengths.columns) != ["gene_symbol", "exon_length"]:
        raise ValueError("exon-length table columns changed")
    if lengths["gene_symbol"].duplicated().any():
        raise ValueError("exon-length table repeats gene symbols")
    if (lengths["exon_length"] <= 0).any():
        raise ValueError("exon-length table contains nonpositive lengths")
    length_map = dict(
        zip(lengths["gene_symbol"].astype(str), lengths["exon_length"].astype(float))
    )
    missing_lengths = sorted(set(genes) - set(length_map))
    if missing_lengths:
        raise ValueError(f"canonical genes lack exon lengths: {missing_lengths[:5]}")

    cohort = pd.read_parquet(sealed_path)
    selected_columns = cohort["matrix_column_index"].to_numpy(dtype=np.int64)
    n_samples, n_genes = len(cohort), len(genes)
    gene_index = {gene: index for index, gene in enumerate(genes)}
    length_index = {
        gene: index for index, gene in enumerate(lengths["gene_symbol"].astype(str))
    }
    gencode_v47_path = Path(args.gencode_v47_gtf)
    gencode_v49_path = Path(args.gencode_v49_gtf)
    gencode_contract = protocol["expression"]["gencode_gtf_sha256"]
    if sha256_file(gencode_v47_path) != gencode_contract["v47"]:
        raise ValueError("GENCODE V47 GTF differs from frozen protocol")
    if sha256_file(gencode_v49_path) != gencode_contract["v49"]:
        raise ValueError("GENCODE V49 GTF differs from frozen protocol")
    v47_symbols = _read_gencode_gene_map(gencode_v47_path)
    v49_symbols = _read_gencode_gene_map(gencode_v49_path)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    scratch = output_dir / ".scratch"
    scratch.mkdir()
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
    seen_symbols: dict[str, int] = {}
    observed_canonical: set[str] = set()
    canonical_source_rows: dict[str, int] = {}
    stable_id_renames: dict[str, tuple[str, str]] = {}
    v47_description_mismatches = 0

    expected_rows, matrix_samples, header_ids = _read_gct_header(counts)
    if matrix_samples != int(header_report["matrix_sample_columns"]):
        raise ValueError("GCT matrix dimensions changed after header freeze")
    if sha256_lines(header_ids) != header_report["matrix_header_sample_ids_sha256"]:
        raise ValueError("GCT sample header changed after header freeze")
    expected_fields = matrix_samples + 2
    rows_read = 0
    with gzip.open(counts, "rt") as handle:
        for _ in range(3):
            handle.readline()
        for line in handle:
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 2:
                raise ValueError("malformed GCT data row")
            gene_id = fields[0].strip()
            symbol = fields[1].strip()
            stable_id = gene_id.split(".", 1)[0]
            v47_symbol = v47_symbols.get(stable_id)
            v49_symbol = v49_symbols.get(stable_id)
            if v47_symbol is not None and v47_symbol != symbol:
                v47_description_mismatches += 1
            mapped_symbol = v49_symbol if v49_symbol is not None else symbol
            if mapped_symbol != symbol:
                stable_id_renames[stable_id] = (symbol, mapped_symbol)
            values = _parse_selected_counts(
                fields, selected_columns, expected_fields=expected_fields
            )
            seen_symbols[symbol] = seen_symbols.get(symbol, 0) + 1
            qc_symbol = (
                mapped_symbol if mapped_symbol in length_index else symbol
            )
            if qc_symbol in length_index:
                row = length_index[qc_symbol]
                qc_positive[row] |= (values > 0).astype(np.uint8)
            target_symbol = (
                mapped_symbol if mapped_symbol in gene_index else symbol
            )
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
    with np.load(args.axis_definitions, allow_pickle=False) as definitions:
        score_indices = np.asarray(definitions["score_gene_indices"], dtype=np.int64)
        definition_genes = definitions["gene_names"].astype(str).tolist()
    if expected_artifacts.get("axis_definitions") and (
        sha256_file(args.axis_definitions) != expected_artifacts["axis_definitions"]
    ):
        raise ValueError("axis definitions differ from frozen protocol")
    if definition_genes != genes:
        raise ValueError("axis definitions and canonical gene list differ")
    missing_score = sorted(set(np.asarray(genes)[score_indices]) & set(missing_canonical))
    if missing_score:
        raise ValueError(f"GTEx matrix lacks frozen score genes: {missing_score[:5]}")
    if missing_canonical and protocol["expression"]["missing_non_score_genes"] != "zero_fill":
        raise ValueError("GTEx matrix lacks canonical genes and zero-fill is not frozen")

    nonzero = np.zeros(n_samples, dtype=np.int32)
    for start in range(0, len(lengths), 1024):
        nonzero += np.asarray(qc_positive[start : start + 1024]).sum(
            axis=0, dtype=np.int32
        )
    minimum = int(protocol["expression"]["minimum_nonzero_length_mapped_genes"])
    failed = np.flatnonzero(nonzero < minimum)
    if len(failed):
        failed_ids = cohort.iloc[failed]["sample_id"].astype(str).tolist()
        raise ValueError(f"GTEx samples fail frozen expression QC: {failed_ids[:5]}")

    lengths_kb = np.asarray([length_map[gene] / 1000.0 for gene in genes])
    expression_path = output_dir / "expression.parquet"
    writer: pq.ParquetWriter | None = None
    denominators = np.empty(n_samples, dtype=np.float64)
    row_group_size = int(args.row_group_size)
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
        "expression_values_read": True,
        "one_time_external_extraction": True,
        "expression_space": "tpm",
        "normalization": "canonical-universe TPM from aggregated RNASeQC counts",
        "log_transform_applied": False,
        "counts_object_sha256": sha256_file(counts),
        "protocol_sha256": sha256_file(args.protocol),
        "header_report_sha256": sha256_file(header_report_path),
        "sealed_cohort_sha256": sha256_file(sealed_path),
        "canonical_genes_sha256": sha256_file(args.genes),
        "axis_definitions_sha256": sha256_file(args.axis_definitions),
        "exon_lengths_sha256": sha256_file(args.exon_lengths),
        "gencode_v47_gtf_sha256": sha256_file(gencode_v47_path),
        "gencode_v49_gtf_sha256": sha256_file(gencode_v49_path),
        "expression_sha256": sha256_file(expression_path),
        "gene_order_sha256": sha256_lines(genes),
        "sample_order_sha256": sha256_lines(cohort["sample_id"]),
        "samples": n_samples,
        "donors": int(cohort["donor_id"].nunique()),
        "genes": n_genes,
        "score_genes": len(score_indices),
        "gct_rows": rows_read,
        "unique_gct_symbols": len(seen_symbols),
        "duplicate_symbol_count": int(sum(value > 1 for value in seen_symbols.values())),
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
    }
    atomic_json(output_dir / "extraction_report.json", report)
    (output_dir / "EXTRACTION_COMPLETE").write_text("one-time GTEx extraction complete\n")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    header = subparsers.add_parser("freeze-header")
    header.add_argument("--protocol", required=True)
    header.add_argument("--expected-protocol-sha256", required=True)
    header.add_argument("--counts-gct", required=True)
    header.add_argument("--provisional-cohort", required=True)
    header.add_argument("--sample-attributes", required=True)
    header.add_argument("--output-dir", required=True)
    extraction = subparsers.add_parser("extract")
    extraction.add_argument("--protocol", required=True)
    extraction.add_argument("--expected-protocol-sha256", required=True)
    extraction.add_argument("--counts-gct", required=True)
    extraction.add_argument("--header-dir", required=True)
    extraction.add_argument("--genes", required=True)
    extraction.add_argument("--axis-definitions", required=True)
    extraction.add_argument("--exon-lengths", required=True)
    extraction.add_argument("--gencode-v47-gtf", required=True)
    extraction.add_argument("--gencode-v49-gtf", required=True)
    extraction.add_argument("--output-dir", required=True)
    extraction.add_argument("--row-group-size", type=int, default=16)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    report = freeze_header(args) if args.command == "freeze-header" else extract(args)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
