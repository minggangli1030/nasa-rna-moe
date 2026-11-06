#!/usr/bin/env python3
"""Export ARCHS4 sample metadata from a pinned remote HDF5 object.

The exporter opens the HDF5 file through HTTP range requests and reads only
``meta/info`` and ``meta/samples``.  It never indexes ``data/expression``.  The
remote object's length, ETag, and Last-Modified value are checked before and
after the scan so a mutable ``latest`` URL cannot silently change mid-export.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import fsspec
import h5py
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests

from export_archs4_sample_metadata import NUMERIC_FIELDS, TEXT_FIELDS, _decode, _to_float


def remote_identity(url: str, timeout_seconds: int = 60) -> dict[str, str | int]:
    response = requests.head(url, allow_redirects=True, timeout=timeout_seconds)
    response.raise_for_status()
    return {
        "resolved_url": response.url,
        "content_length": int(response.headers["content-length"]),
        "etag": str(response.headers.get("etag", "")).strip(),
        "last_modified": str(response.headers.get("last-modified", "")).strip(),
        "accept_ranges": str(response.headers.get("accept-ranges", "")).strip(),
    }


def validate_identity(actual: dict, expected: dict) -> None:
    for key in ("content_length", "etag", "last_modified"):
        if expected.get(key) in (None, ""):
            continue
        if str(actual.get(key)) != str(expected[key]):
            raise ValueError(
                f"remote ARCHS4 identity mismatch for {key}: "
                f"expected {expected[key]!r}, observed {actual.get(key)!r}"
            )
    if actual.get("accept_ranges", "").lower() != "bytes":
        raise ValueError("remote ARCHS4 object does not advertise byte ranges")


def export_remote_metadata(args: argparse.Namespace) -> dict:
    output = Path(args.output)
    report_path = Path(args.report) if args.report else output.with_name(
        output.stem + "_report.json"
    )
    if output.exists() or report_path.exists():
        raise FileExistsError("remote metadata output already exists")
    output.parent.mkdir(parents=True, exist_ok=True)

    expected = {
        "content_length": int(args.expected_content_length),
        "etag": args.expected_etag,
        "last_modified": args.expected_last_modified,
    }
    before = remote_identity(args.human_h5_url, args.http_timeout_seconds)
    validate_identity(before, expected)

    temporary = output.with_suffix(output.suffix + ".tmp")
    writer = None
    accession_hash = hashlib.sha256()
    n_samples = 0
    missing: list[str] = []
    source_info: dict[str, str] = {}
    expression_shape: list[int] = []
    try:
        remote = fsspec.open(
            before["resolved_url"],
            mode="rb",
            block_size=args.block_size,
            cache_type="readahead",
        ).open()
        with remote, h5py.File(remote, "r") as handle:
            samples = handle["meta/samples"]
            available = set(samples.keys())
            missing = [
                field
                for field in TEXT_FIELDS + NUMERIC_FIELDS
                if field not in available
            ]
            if "geo_accession" in missing:
                raise KeyError("remote meta/samples is missing geo_accession")
            n_samples = len(samples["geo_accession"])
            expression_shape = [int(value) for value in handle["data/expression"].shape]
            if expression_shape[1] != n_samples:
                raise ValueError("remote expression/sample metadata dimensions disagree")
            info = handle.get("meta/info")
            if info is not None:
                for key in ("version", "creation-date"):
                    if key in info:
                        source_info[key] = _decode(info[key][()])

            for start in range(0, n_samples, args.chunk_size):
                stop = min(start + args.chunk_size, n_samples)
                raw = {
                    name: samples[name][start:stop]
                    for name in TEXT_FIELDS + NUMERIC_FIELDS
                    if name in available
                }
                columns: dict[str, list] = {}
                for name in TEXT_FIELDS:
                    if name in raw:
                        columns[name] = [_decode(value).strip() for value in raw[name]]
                    else:
                        columns[name] = [""] * (stop - start)
                for name in NUMERIC_FIELDS:
                    if name in raw:
                        columns[name] = [_to_float(value) for value in raw[name]]
                    else:
                        columns[name] = [float("nan")] * (stop - start)
                frame = pd.DataFrame(columns)
                frame.insert(0, "h5_row", np.arange(start, stop, dtype=np.int64))
                for accession in frame["geo_accession"]:
                    accession_hash.update(str(accession).encode("utf-8"))
                    accession_hash.update(b"\n")
                table = pa.Table.from_pandas(frame, preserve_index=False)
                if writer is None:
                    writer = pq.ParquetWriter(
                        temporary,
                        table.schema,
                        compression="zstd",
                    )
                writer.write_table(table)
                print(f"metadata_rows={stop}/{n_samples}", flush=True)
    finally:
        if writer is not None:
            writer.close()

    after = remote_identity(args.human_h5_url, args.http_timeout_seconds)
    validate_identity(after, expected)
    if before != after:
        raise ValueError("remote ARCHS4 identity changed during metadata export")
    os.replace(temporary, output)

    report = {
        "schema_version": 1,
        "status": "complete",
        "metadata_only": True,
        "expression_values_read": False,
        "human_h5_url": args.human_h5_url,
        "remote_identity": after,
        "n_samples": int(n_samples),
        "expression_shape_metadata_only": expression_shape,
        "text_fields": list(TEXT_FIELDS),
        "numeric_fields": list(NUMERIC_FIELDS),
        "missing_fields": missing,
        "geo_accession_sha256": accession_hash.hexdigest(),
        "source": {"n_samples": int(n_samples), **source_info},
        "output_parquet": str(output.resolve()),
        "output_parquet_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--human-h5-url", required=True)
    parser.add_argument("--expected-content-length", type=int, required=True)
    parser.add_argument("--expected-etag", required=True)
    parser.add_argument("--expected-last-modified", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report")
    parser.add_argument("--chunk-size", type=int, default=20_000)
    parser.add_argument("--block-size", type=int, default=16 * 1024 * 1024)
    parser.add_argument("--http-timeout-seconds", type=int, default=60)
    args = parser.parse_args()
    report = export_remote_metadata(args)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
