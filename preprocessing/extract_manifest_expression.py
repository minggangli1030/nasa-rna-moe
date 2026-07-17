#!/usr/bin/env python3
"""Extract an exact Stage 1 manifest from human ARCHS4 into TPM space.

The extractor is intentionally not a dataset sampler.  Manifest row order, organ
labels, connected-study groups, and split assignments are treated as frozen input.
Every requested sample must occur exactly once in the H5 file. Canonical genes absent
from an older ARCHS4 release are zero-filled, matching the established Stage 0 reindex
policy, and the exact missing list is recorded in provenance.

Output directory contract
-------------------------
``expression.parquet``
    Sample-major float32 matrix.  ``sample_id`` is the first column, followed by
    canonical genes in the exact supplied order.  Values are raw ``TPM``;
    ``log1p`` is deliberately deferred to the trainer, as in Stage 0.
``manifest.parquet``
    The validated input manifest in its original row and column order.
``genes.txt``
    One canonical gene per line, in expression-column order.
``extraction_report.json``
    Input, assignment, source-metadata, expression, and output hashes plus QC and
    leakage checks.  A failed-QC report is still written, but no expression file
    is published and no sample is silently removed.

ARCHS4 v11 stores expression as genes x samples.  Repeated H5 gene symbols are
summed, matching the established preprocessing pipeline; duplicate canonical-list
or exon-length entries are errors.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import h5py
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


SCHEMA_VERSION = 1
REQUIRED_MANIFEST_COLUMNS = ("sample_id", "organ", "series_group_id", "split")
OUTPUT_NAMES = (
    "expression.parquet",
    "manifest.parquet",
    "genes.txt",
    "extraction_report.json",
)
DEFAULT_CANONICAL_GENES = Path("data/ensembl/canonical_genes_shared.txt")
DEFAULT_HUMAN_EXON_LENGTHS = Path("data/gencode/gencode_v49_gene_exon_lengths.csv")
AUTO_HASH_SOURCE_MAX_BYTES = 64 * 1024 * 1024


class ExtractionError(ValueError):
    """Raised when an exact manifest extraction cannot be completed safely."""


def _decode(value: Any) -> str:
    if isinstance(value, (bytes, np.bytes_)):
        return value.decode("utf-8", "strict").strip()
    return str(value).strip()


def _sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_lines(values: Iterable[Any]) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(str(value).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _sha256_json(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _source_h5_hash(
    path: Path,
    supplied_sha256: str | None,
    force_hash: bool,
) -> tuple[str | None, str, str | None]:
    """Resolve a source hash without silently adding a second 17-GB H5 pass."""
    if supplied_sha256 is not None:
        value = supplied_sha256.strip().lower()
        try:
            valid = len(value) == 64 and int(value, 16) >= 0
        except ValueError:
            valid = False
        if not valid:
            raise ExtractionError("source_h5_sha256 must be exactly 64 hexadecimal characters")
        return value, "supplied", None
    size = path.stat().st_size
    if force_hash or size <= AUTO_HASH_SOURCE_MAX_BYTES:
        return _sha256_file(path), "computed", None
    reason = (
        "full-file SHA256 not computed by default because the source H5 exceeds "
        f"{AUTO_HASH_SOURCE_MAX_BYTES} bytes; ordered H5 metadata hashes and the "
        "selected_aggregated_counts_sha256 bind all extracted content. Pass "
        "--hash-source-h5 or --source-h5-sha256 to record the full-file hash."
    )
    return None, "not_computed_large_source", reason


def _matrix_digest(genes: list[str], sample_ids: list[str]) -> Any:
    digest = hashlib.sha256()
    digest.update(json.dumps(genes, separators=(",", ":")).encode("utf-8"))
    digest.update(json.dumps(sample_ids, separators=(",", ":")).encode("utf-8"))
    return digest


def _read_text_dataset(dataset: h5py.Dataset, label: str) -> list[str]:
    values = dataset[:]
    if values.ndim != 1:
        raise ExtractionError(f"{label} must be one-dimensional, got shape {values.shape}")
    decoded = [_decode(value) for value in values]
    empty = [index for index, value in enumerate(decoded) if not value]
    if empty:
        raise ExtractionError(f"{label} contains empty values at indices {empty[:10]}")
    return decoded


def _check_unique(values: list[str], label: str) -> None:
    counts = Counter(values)
    duplicates = sorted(value for value, count in counts.items() if count > 1)
    if duplicates:
        raise ExtractionError(
            f"{label} contains duplicate values ({len(duplicates)} unique duplicates): "
            f"{duplicates[:10]}"
        )


def _csv_header(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        try:
            return next(csv.reader(handle))
        except StopIteration as exc:
            raise ExtractionError(f"manifest CSV is empty: {path}") from exc


def load_manifest(path: Path) -> pd.DataFrame:
    """Load and validate the frozen Stage 1 manifest without changing row order."""
    if not path.is_file():
        raise FileNotFoundError(f"manifest not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".csv":
        header = _csv_header(path)
        _check_unique(header, "manifest column names")
        dtype = {column: "string" for column in REQUIRED_MANIFEST_COLUMNS if column in header}
        frame = pd.read_csv(path, dtype=dtype)
    elif suffix in {".parquet", ".pq"}:
        names = pq.read_schema(path).names
        _check_unique(names, "manifest column names")
        frame = pd.read_parquet(path)
    else:
        raise ExtractionError("manifest must be CSV or parquet")

    if frame.empty:
        raise ExtractionError("manifest has no rows")
    missing_columns = [column for column in REQUIRED_MANIFEST_COLUMNS if column not in frame]
    if missing_columns:
        raise ExtractionError(f"manifest is missing required columns: {missing_columns}")

    frame = frame.copy()
    for column in REQUIRED_MANIFEST_COLUMNS:
        missing = frame[column].isna()
        if missing.any():
            rows = np.flatnonzero(missing.to_numpy()).tolist()
            raise ExtractionError(f"manifest {column!r} is missing at rows {rows[:10]}")
        frame[column] = frame[column].astype(str).str.strip()
        empty = frame[column].eq("")
        if empty.any():
            rows = np.flatnonzero(empty.to_numpy()).tolist()
            raise ExtractionError(f"manifest {column!r} is empty at rows {rows[:10]}")

    sample_ids = frame["sample_id"].tolist()
    _check_unique(sample_ids, "manifest sample_id")

    split_counts = frame.groupby("series_group_id", sort=False)["split"].nunique()
    leaking_groups = split_counts[split_counts > 1].index.astype(str).tolist()
    if leaking_groups:
        raise ExtractionError(
            "connected-study leakage: series_group_id occurs in multiple splits: "
            f"{leaking_groups[:10]}"
        )

    # A study may legitimately profile multiple organs.  It is a useful
    # within-study control as long as the entire connected study remains in one
    # split.  Organ identity is therefore validated per sample, not per study.
    return frame


def load_canonical_genes(path: Path) -> list[str]:
    """Load a canonical gene sequence, preserving its declared order exactly."""
    if not path.is_file():
        raise FileNotFoundError(f"canonical gene list not found: {path}")
    suffix = path.suffix.lower()
    if suffix == ".json":
        payload = json.loads(path.read_text())
        if not isinstance(payload, list):
            raise ExtractionError("canonical gene JSON must contain a list")
        genes = [_decode(value) for value in payload]
    elif suffix in {".csv", ".tsv"}:
        frame = pd.read_csv(path, sep="\t" if suffix == ".tsv" else ",", dtype=str)
        if "gene_symbol" not in frame:
            raise ExtractionError("canonical gene table requires a gene_symbol column")
        if frame["gene_symbol"].isna().any():
            raise ExtractionError("canonical gene table contains missing gene_symbol values")
        genes = frame["gene_symbol"].str.strip().tolist()
    else:
        genes = [line.strip() for line in path.read_text().splitlines() if line.strip()]

    if not genes:
        raise ExtractionError("canonical gene list is empty")
    empty = [index for index, gene in enumerate(genes) if not gene]
    if empty:
        raise ExtractionError(f"canonical gene list has empty entries at indices {empty[:10]}")
    _check_unique(genes, "canonical gene list")
    return genes


def load_human_exon_lengths(
    path: Path, canonical_genes: list[str]
) -> tuple[np.ndarray, pd.Series]:
    """Return canonical-ordered lengths and the full validated human length table."""
    if not path.is_file():
        raise FileNotFoundError(f"human exon-length table not found: {path}")
    frame = pd.read_csv(path)
    required = {"gene_symbol", "exon_length"}
    missing_columns = sorted(required - set(frame.columns))
    if missing_columns:
        raise ExtractionError(f"human exon-length table is missing columns: {missing_columns}")
    if frame["gene_symbol"].isna().any():
        raise ExtractionError("human exon-length table contains missing gene symbols")
    symbols = frame["gene_symbol"].astype(str).str.strip().tolist()
    _check_unique(symbols, "human exon-length gene_symbol")
    lengths = pd.to_numeric(frame["exon_length"], errors="coerce")
    invalid = ~np.isfinite(lengths.to_numpy(dtype=float)) | lengths.le(0).to_numpy()
    if invalid.any():
        rows = np.flatnonzero(invalid).tolist()
        raise ExtractionError(f"human exon lengths must be finite and positive; bad rows {rows[:10]}")

    by_gene = pd.Series(lengths.to_numpy(dtype=np.float64), index=symbols)
    missing_genes = [gene for gene in canonical_genes if gene not in by_gene.index]
    if missing_genes:
        raise ExtractionError(
            f"human exon-length table is missing {len(missing_genes)} canonical genes: "
            f"{missing_genes[:10]}"
        )
    return by_gene.loc[canonical_genes].to_numpy(dtype=np.float64), by_gene


def _manifest_counts(frame: pd.DataFrame) -> dict[str, Any]:
    by_organ = frame["organ"].value_counts(sort=False).sort_index()
    by_split = frame["split"].value_counts(sort=False).sort_index()
    grouped = (
        frame.groupby(["organ", "split"], sort=True)
        .agg(n_samples=("sample_id", "size"), n_series_groups=("series_group_id", "nunique"))
        .reset_index()
    )
    rows = [
        {
            "organ": str(row.organ),
            "split": str(row.split),
            "n_samples": int(row.n_samples),
            "n_series_groups": int(row.n_series_groups),
        }
        for row in grouped.itertuples(index=False)
    ]
    return {
        "by_organ": {str(key): int(value) for key, value in by_organ.items()},
        "by_split": {str(key): int(value) for key, value in by_split.items()},
        "by_organ_and_split": rows,
        "n_series_groups": int(frame["series_group_id"].nunique()),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _publish(staging_dir: Path, output_dir: Path, names: Iterable[str]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        os.replace(staging_dir / name, output_dir / name)


def _assert_targets_absent(output_dir: Path) -> None:
    existing = [str(output_dir / name) for name in OUTPUT_NAMES if (output_dir / name).exists()]
    if existing:
        raise FileExistsError(
            "refusing to overwrite Stage 1 extraction artifacts; use a new output directory: "
            f"{existing}"
        )


def _normalization_failure_reasons(
    canonical_counts: np.ndarray,
    qc_counts: np.ndarray,
    lengths_kb: np.ndarray,
    qc_min_nonzero: int,
) -> tuple[np.ndarray, np.ndarray, list[list[str]], np.ndarray]:
    """Apply Stage-0-parity QC, then canonical TPM, retaining every failure reason."""
    n_samples = canonical_counts.shape[1]
    reasons: list[list[str]] = [[] for _ in range(n_samples)]
    qc_finite = np.isfinite(qc_counts)
    qc_nonnegative = qc_counts >= 0
    nonzero = np.sum(qc_finite & (qc_counts > 0), axis=0).astype(np.int64)

    for index in range(n_samples):
        if not qc_finite[:, index].all():
            reasons[index].append("nonfinite_source_count")
        if not qc_nonnegative[:, index][qc_finite[:, index]].all():
            reasons[index].append("negative_source_count")
        if int(nonzero[index]) < qc_min_nonzero:
            reasons[index].append(
                f"qc_nonzero_genes_below_threshold:{int(nonzero[index])}<{qc_min_nonzero}"
            )

    canonical_finite = np.isfinite(canonical_counts)
    canonical_nonnegative = canonical_counts >= 0
    safe_counts = np.where(
        canonical_finite & canonical_nonnegative, canonical_counts, 0.0
    )
    rate = safe_counts / lengths_kb[:, None]
    denominators = rate.sum(axis=0, dtype=np.float64)
    valid_denominator = np.isfinite(denominators) & (denominators > 0)
    for index in np.flatnonzero(~valid_denominator):
        reasons[int(index)].append("nonpositive_or_nonfinite_tpm_denominator")

    tpm = np.zeros_like(rate, dtype=np.float64)
    if valid_denominator.any():
        tpm[:, valid_denominator] = (
            rate[:, valid_denominator] / denominators[valid_denominator]
        ) * 1_000_000.0
    tpm_float32 = tpm.T.astype("<f4", copy=False)
    output_finite = np.isfinite(tpm_float32).all(axis=1)
    for index in np.flatnonzero(~output_finite):
        reasons[int(index)].append("nonfinite_tpm")

    return tpm_float32, tpm.T, reasons, nonzero


def extract_manifest_expression(
    manifest_path: Path,
    human_h5_path: Path,
    canonical_genes_path: Path,
    human_exon_lengths_path: Path,
    output_dir: Path,
    *,
    batch_size: int = 128,
    parquet_row_group_size: int = 256,
    qc_min_nonzero: int = 14_000,
    compression: str = "zstd",
    source_h5_sha256: str | None = None,
    hash_source_h5: bool = False,
) -> dict[str, Any]:
    """Execute an exact, deterministic Stage 1 manifest extraction."""
    manifest_path = Path(manifest_path)
    human_h5_path = Path(human_h5_path)
    canonical_genes_path = Path(canonical_genes_path)
    human_exon_lengths_path = Path(human_exon_lengths_path)
    output_dir = Path(output_dir)
    if batch_size <= 0 or parquet_row_group_size <= 0:
        raise ExtractionError("batch sizes must be positive")
    if qc_min_nonzero < 0:
        raise ExtractionError("qc_min_nonzero must be nonnegative")
    if not human_h5_path.is_file():
        raise FileNotFoundError(f"human ARCHS4 H5 not found: {human_h5_path}")
    _assert_targets_absent(output_dir)

    manifest = load_manifest(manifest_path)
    canonical_genes = load_canonical_genes(canonical_genes_path)
    exon_lengths_bp, all_human_exon_lengths = load_human_exon_lengths(
        human_exon_lengths_path, canonical_genes
    )
    lengths_kb = exon_lengths_bp / 1000.0
    sample_ids = manifest["sample_id"].tolist()
    resolved_h5_sha256, h5_hash_method, h5_hash_reason = _source_h5_hash(
        human_h5_path, source_h5_sha256, hash_source_h5
    )
    gene_order_sha256 = _sha256_lines(canonical_genes)
    sample_order_sha256 = _sha256_lines(sample_ids)

    assignment_rows = manifest[
        ["sample_id", "organ", "series_group_id", "split"]
    ].to_dict("records")
    multi_organ_group_count = int(
        (manifest.groupby("series_group_id", sort=False)["organ"].nunique() > 1).sum()
    )
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "extracting",
        "expression_space": "tpm",
        "gene_order_sha256": gene_order_sha256,
        "sample_order_sha256": sample_order_sha256,
        "source_h5_sha256": resolved_h5_sha256,
        "source_h5_sha256_method": h5_hash_method,
        "source_h5_sha256_reason": h5_hash_reason,
        "output_parquet_sha256": None,
        "contract": {
            "source_orientation": "genes_x_samples",
            "output_orientation": "samples_x_genes",
            "expression_space": "tpm_float32",
            "normalization_order": [
                "sum_repeated_h5_gene_symbols",
                "qc_on_all_h5_gene_symbols_with_human_exon_lengths",
                "restrict_and_order_canonical_genes_zero_fill_missing_h5_symbols",
                "divide_by_human_exon_length_kb",
                "scale_each_sample_to_1e6_tpm",
            ],
            "tpm_applications": 1,
            "log1p_applications": 0,
            "log1p_owner": "trainer",
            "split_source": "input_manifest",
            "random_sampling_or_split": False,
            "silent_sample_drops": False,
        },
        "inputs": {
            "manifest_path": str(manifest_path.resolve()),
            "manifest_file_sha256": _sha256_file(manifest_path),
            "human_h5_path": str(human_h5_path.resolve()),
            "human_h5_size_bytes": int(human_h5_path.stat().st_size),
            "human_h5_mtime_ns": int(human_h5_path.stat().st_mtime_ns),
            "canonical_genes_path": str(canonical_genes_path.resolve()),
            "canonical_genes_file_sha256": _sha256_file(canonical_genes_path),
            "human_exon_lengths_path": str(human_exon_lengths_path.resolve()),
            "human_exon_lengths_file_sha256": _sha256_file(human_exon_lengths_path),
            "extractor_sha256": _sha256_file(Path(__file__)),
        },
        "manifest": {
            "n_samples": len(manifest),
            "ordered_sample_id_sha256": sample_order_sha256,
            "sorted_sample_id_sha256": _sha256_lines(sorted(sample_ids)),
            "assignment_sha256": _sha256_json(assignment_rows),
            "columns": manifest.columns.astype(str).tolist(),
            "counts": _manifest_counts(manifest),
            "connected_group_split_overlap_count": 0,
            "multi_organ_connected_group_count": multi_organ_group_count,
        },
        "genes": {
            "n_genes": len(canonical_genes),
            "ordered_gene_sha256": gene_order_sha256,
            "ordered_gene_length_sha256": _sha256_json(
                [[gene, float(length)] for gene, length in zip(canonical_genes, exon_lengths_bp)]
            ),
        },
        "qc": {
            "qc_min_nonzero_genes": qc_min_nonzero,
            "qc_gene_universe": (
                "all_h5_gene_symbols_with_human_exon_lengths_after_duplicate_sum_"
                "before_canonical_reindex"
            ),
            "canonical_tpm_gene_universe": "ordered_canonical_gene_list",
            "canonical_tpm_n_genes": len(canonical_genes),
            "n_failures": 0,
            "failures": [],
        },
    }

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{output_dir.name}.extract-", dir=output_dir.parent
    ) as temporary:
        staging_dir = Path(temporary)
        matrix_path = staging_dir / "expression.values.f4"

        with h5py.File(human_h5_path, "r") as handle:
            required_h5 = ("data/expression", "meta/samples/geo_accession")
            missing_h5 = [key for key in required_h5 if key not in handle]
            if missing_h5:
                raise ExtractionError(f"human H5 is missing datasets: {missing_h5}")
            if "meta/genes/gene_symbol" in handle:
                gene_key = "meta/genes/gene_symbol"
            elif "meta/genes/symbol" in handle:
                gene_key = "meta/genes/symbol"
            else:
                raise ExtractionError(
                    "human H5 is missing meta/genes/gene_symbol and meta/genes/symbol"
                )

            expression = handle["data/expression"]
            if expression.ndim != 2:
                raise ExtractionError(
                    f"data/expression must be two-dimensional, got shape {expression.shape}"
                )
            h5_gene_symbols = _read_text_dataset(handle[gene_key], gene_key)
            h5_sample_ids = _read_text_dataset(
                handle["meta/samples/geo_accession"], "meta/samples/geo_accession"
            )
            if expression.shape != (len(h5_gene_symbols), len(h5_sample_ids)):
                raise ExtractionError(
                    "H5 expression/metadata shape mismatch: "
                    f"expression={expression.shape}, genes={len(h5_gene_symbols)}, "
                    f"samples={len(h5_sample_ids)}"
                )
            _check_unique(h5_sample_ids, "H5 geo_accession")

            sample_to_index = {sample_id: index for index, sample_id in enumerate(h5_sample_ids)}
            missing_samples = [sample_id for sample_id in sample_ids if sample_id not in sample_to_index]
            if missing_samples:
                raise ExtractionError(
                    f"human H5 is missing {len(missing_samples)} manifest sample IDs: "
                    f"{missing_samples[:10]}"
                )
            source_sample_indices = np.asarray(
                [sample_to_index[sample_id] for sample_id in sample_ids], dtype=np.int64
            )

            canonical_set = set(canonical_genes)
            positions: dict[str, list[int]] = {gene: [] for gene in canonical_genes}
            for index, symbol in enumerate(h5_gene_symbols):
                if symbol in canonical_set:
                    positions[symbol].append(index)
            missing_genes = [gene for gene in canonical_genes if not positions[gene]]
            present_genes = [gene for gene in canonical_genes if positions[gene]]
            if not present_genes:
                raise ExtractionError("human H5 resolves none of the canonical genes")
            present_output_rows = np.asarray(
                [index for index, gene in enumerate(canonical_genes) if positions[gene]],
                dtype=np.int64,
            )
            repeated = {
                gene: rows for gene, rows in positions.items() if len(rows) > 1
            }
            flat_gene_rows = np.asarray(
                [row for gene in present_genes for row in positions[gene]], dtype=np.int64
            )
            reduce_starts = np.cumsum(
                np.asarray(
                    [0] + [len(positions[gene]) for gene in present_genes[:-1]],
                    dtype=np.int64,
                )
            )

            # Match Stage 0: the 14k nonzero gate is applied after aggregating
            # duplicate symbols but before canonical reindex, over all H5 symbols
            # that have a human exon length.  Only the TPM denominator below is
            # restricted to the canonical universe.
            length_gene_set = set(all_human_exon_lengths.index)
            qc_positions: dict[str, list[int]] = {}
            for index, symbol in enumerate(h5_gene_symbols):
                if symbol in length_gene_set:
                    qc_positions.setdefault(symbol, []).append(index)
            if not qc_positions:
                raise ExtractionError("no H5 gene symbols have human exon lengths")
            qc_genes = sorted(qc_positions)
            if qc_min_nonzero > len(qc_genes):
                raise ExtractionError(
                    f"qc_min_nonzero={qc_min_nonzero} exceeds pre-canonical QC gene "
                    f"universe size {len(qc_genes)}"
                )
            qc_flat_gene_rows = np.asarray(
                [row for gene in qc_genes for row in qc_positions[gene]], dtype=np.int64
            )
            qc_reduce_starts = np.cumsum(
                np.asarray(
                    [0] + [len(qc_positions[gene]) for gene in qc_genes[:-1]],
                    dtype=np.int64,
                )
            )
            report["qc"]["qc_gene_universe_n_genes"] = len(qc_genes)
            report["qc"]["qc_gene_universe_sha256"] = _sha256_lines(qc_genes)

            h5_sample_hash = _sha256_lines(h5_sample_ids)
            h5_gene_hash = _sha256_lines(h5_gene_symbols)
            report["source_h5"] = {
                "expression_dataset": "data/expression",
                "gene_symbol_dataset": gene_key,
                "sample_id_dataset": "meta/samples/geo_accession",
                "expression_shape": [int(value) for value in expression.shape],
                "expression_dtype": str(expression.dtype),
                "ordered_h5_sample_id_sha256": h5_sample_hash,
                "ordered_h5_gene_symbol_sha256": h5_gene_hash,
                "source_schema_sha256": _sha256_json(
                    {
                        "shape": [int(value) for value in expression.shape],
                        "dtype": str(expression.dtype),
                        "sample_id_sha256": h5_sample_hash,
                        "gene_symbol_sha256": h5_gene_hash,
                    }
                ),
                "n_repeated_canonical_gene_symbols": len(repeated),
                "repeated_canonical_gene_rows": {
                    gene: [int(row) for row in rows] for gene, rows in repeated.items()
                },
                "repeated_gene_policy": "sum",
                "n_missing_canonical_genes": len(missing_genes),
                "missing_canonical_genes": missing_genes,
                "missing_canonical_gene_sha256": _sha256_lines(missing_genes),
                "missing_canonical_gene_policy": "zero_fill_stage0_parity",
                "all_manifest_samples_resolved_exactly_once": True,
                "all_canonical_genes_resolved": not missing_genes,
            }

            values = np.memmap(
                matrix_path,
                mode="w+",
                dtype="<f4",
                shape=(len(sample_ids), len(canonical_genes)),
                order="F",
            )
            counts_digest = _matrix_digest(canonical_genes, sample_ids)
            expression_digest = _matrix_digest(canonical_genes, sample_ids)
            qc_failures: list[dict[str, Any]] = []
            nonzero_counts: list[int] = []

            for start in range(0, len(sample_ids), batch_size):
                stop = min(start + batch_size, len(sample_ids))
                requested_indices = source_sample_indices[start:stop]
                sort_order = np.argsort(requested_indices, kind="stable")
                sorted_indices = requested_indices[sort_order]
                raw_sorted = np.asarray(expression[:, sorted_indices])
                restore_order = np.argsort(sort_order, kind="stable")
                raw = raw_sorted[:, restore_order]
                selected = np.asarray(raw[flat_gene_rows, :], dtype=np.float64)
                present_counts = np.add.reduceat(selected, reduce_starts, axis=0)
                counts = np.zeros(
                    (len(canonical_genes), stop - start), dtype=np.float64
                )
                counts[present_output_rows, :] = present_counts
                qc_selected = np.asarray(raw[qc_flat_gene_rows, :], dtype=np.float64)
                qc_counts = np.add.reduceat(qc_selected, qc_reduce_starts, axis=0)
                counts_sample_major = np.ascontiguousarray(counts.T, dtype="<f8")
                counts_digest.update(counts_sample_major.tobytes())

                tpm_float32, tpm, reasons, nonzero = _normalization_failure_reasons(
                    counts, qc_counts, lengths_kb, qc_min_nonzero
                )
                nonzero_counts.extend(int(value) for value in nonzero)
                for local_index, sample_reasons in enumerate(reasons):
                    if not sample_reasons:
                        # Validate the precise normalization invariant before publishing.
                        tpm_sum = float(tpm[local_index].sum(dtype=np.float64))
                        if not np.isclose(tpm_sum, 1_000_000.0, rtol=1e-10, atol=1e-4):
                            sample_reasons.append(f"invalid_tpm_sum:{tpm_sum:.12g}")
                    if sample_reasons:
                        row_index = start + local_index
                        row = manifest.iloc[row_index]
                        qc_failures.append(
                            {
                                "manifest_row": int(row_index),
                                "sample_id": str(row["sample_id"]),
                                "organ": str(row["organ"]),
                                "series_group_id": str(row["series_group_id"]),
                                "split": str(row["split"]),
                                "qc_nonzero_genes": int(nonzero[local_index]),
                                "reasons": sample_reasons,
                            }
                        )
                values[start:stop, :] = tpm_float32
                expression_digest.update(np.ascontiguousarray(tpm_float32, dtype="<f4").tobytes())

            values.flush()

        report["source_h5"]["selected_aggregated_counts_sha256"] = counts_digest.hexdigest()
        report["qc"].update(
            {
                "n_failures": len(qc_failures),
                "failures": qc_failures,
                "qc_nonzero_genes_min": int(min(nonzero_counts)),
                "qc_nonzero_genes_median": float(np.median(nonzero_counts)),
                "qc_nonzero_genes_max": int(max(nonzero_counts)),
            }
        )
        if qc_failures:
            report["status"] = "failed_qc"
            report["expression"] = {
                "n_requested_samples": len(sample_ids),
                "n_published_samples": 0,
                "staging_expression_sha256": expression_digest.hexdigest(),
            }
            output_dir.mkdir(parents=True, exist_ok=True)
            _write_json(output_dir / "extraction_report.json", report)
            raise ExtractionError(
                f"{len(qc_failures)} manifest samples failed QC; no expression artifact "
                f"was published. See {output_dir / 'extraction_report.json'}"
            )

        genes_path = staging_dir / "genes.txt"
        genes_path.write_text("\n".join(canonical_genes) + "\n")

        expression_path = staging_dir / "expression.parquet"
        schema_metadata = {
            b"stage1_schema_version": str(SCHEMA_VERSION).encode(),
            b"expression_space": b"tpm_float32",
            b"ordered_gene_sha256": report["genes"]["ordered_gene_sha256"].encode(),
            b"ordered_sample_id_sha256": report["manifest"][
                "ordered_sample_id_sha256"
            ].encode(),
            b"expression_sha256": expression_digest.hexdigest().encode(),
        }
        arrays: list[pa.Array] = [pa.array(sample_ids, type=pa.string())]
        arrays.extend(
            pa.array(values[:, gene_index], type=pa.float32(), from_pandas=False)
            for gene_index in range(len(canonical_genes))
        )
        expression_table = pa.Table.from_arrays(
            arrays, names=["sample_id", *canonical_genes]
        ).replace_schema_metadata(schema_metadata)
        pq.write_table(
            expression_table,
            expression_path,
            compression=compression,
            use_dictionary=False,
            row_group_size=parquet_row_group_size,
            write_statistics=True,
        )
        del expression_table, arrays, values
        matrix_path.unlink()

        manifest_path_out = staging_dir / "manifest.parquet"
        manifest.to_parquet(
            manifest_path_out,
            index=False,
            compression=compression,
        )

        output_schema = pq.read_schema(expression_path)
        expected_columns = ["sample_id", *canonical_genes]
        if output_schema.names != expected_columns:
            raise AssertionError("written expression schema does not match canonical order")
        output_ids = [
            str(value)
            for value in pq.read_table(expression_path, columns=["sample_id"])
            .column("sample_id")
            .to_pylist()
        ]
        if output_ids != sample_ids:
            raise AssertionError("written expression sample order differs from manifest")
        output_manifest = pd.read_parquet(manifest_path_out)
        if output_manifest.columns.tolist() != manifest.columns.tolist():
            raise AssertionError("written manifest columns differ from input manifest")
        for column in REQUIRED_MANIFEST_COLUMNS:
            if output_manifest[column].astype(str).tolist() != manifest[column].tolist():
                raise AssertionError(f"written manifest changed {column}")

        report["status"] = "complete"
        report["expression"] = {
            "n_requested_samples": len(sample_ids),
            "n_published_samples": len(sample_ids),
            "n_genes": len(canonical_genes),
            "dtype": "float32",
            "space": "tpm",
            "expression_sha256": expression_digest.hexdigest(),
            "sample_order_matches_manifest": True,
            "gene_order_matches_canonical_file": True,
        }
        report["outputs"] = {
            "expression_path": str((output_dir / "expression.parquet").resolve()),
            "expression_parquet_sha256": _sha256_file(expression_path),
            "manifest_path": str((output_dir / "manifest.parquet").resolve()),
            "manifest_parquet_sha256": _sha256_file(manifest_path_out),
            "genes_path": str((output_dir / "genes.txt").resolve()),
            "genes_file_sha256": _sha256_file(genes_path),
            "report_path": str((output_dir / "extraction_report.json").resolve()),
        }
        report["output_parquet_sha256"] = report["outputs"]["expression_parquet_sha256"]
        _write_json(staging_dir / "extraction_report.json", report)
        _publish(staging_dir, output_dir, OUTPUT_NAMES)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract exact manifest IDs from human ARCHS4 into the frozen canonical "
            "TPM gene space; performs no sampling or split generation.  The trainer "
            "is responsible for applying log1p exactly once."
        )
    )
    parser.add_argument("--manifest", type=Path, required=True, help="Frozen CSV/parquet manifest")
    parser.add_argument("--human-h5", type=Path, required=True, help="ARCHS4 human v11 H5")
    parser.add_argument(
        "--canonical-genes",
        type=Path,
        default=DEFAULT_CANONICAL_GENES,
        help=f"Ordered gene list (default: {DEFAULT_CANONICAL_GENES})",
    )
    parser.add_argument(
        "--human-exon-lengths",
        type=Path,
        default=DEFAULT_HUMAN_EXON_LENGTHS,
        help=f"Human exon-length CSV (default: {DEFAULT_HUMAN_EXON_LENGTHS})",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=128, help="H5 samples per read")
    parser.add_argument(
        "--parquet-row-group-size", type=int, default=256, help="Rows per output parquet group"
    )
    parser.add_argument(
        "--qc-min-nonzero",
        type=int,
        default=14_000,
        help=(
            "Minimum positive pre-canonical genes with human exon lengths per requested "
            "sample (Stage-0 parity; default: 14000)"
        ),
    )
    parser.add_argument("--compression", default="zstd")
    source_hash = parser.add_mutually_exclusive_group()
    source_hash.add_argument(
        "--source-h5-sha256",
        help="Previously computed 64-character SHA256 for the full source H5",
    )
    source_hash.add_argument(
        "--hash-source-h5",
        action="store_true",
        help="Compute a full source-H5 SHA256 (adds a complete read of the large file)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = extract_manifest_expression(
        manifest_path=args.manifest,
        human_h5_path=args.human_h5,
        canonical_genes_path=args.canonical_genes,
        human_exon_lengths_path=args.human_exon_lengths,
        output_dir=args.output_dir,
        batch_size=args.batch_size,
        parquet_row_group_size=args.parquet_row_group_size,
        qc_min_nonzero=args.qc_min_nonzero,
        compression=args.compression,
        source_h5_sha256=args.source_h5_sha256,
        hash_source_h5=args.hash_source_h5,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
