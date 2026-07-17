#!/usr/bin/env python3
"""Export ARCHS4 per-sample metadata to a portable parquet (read-only over the H5).

This is the enabling step for the Stage 1 label-recovery track. It scans only the
``meta/samples`` text/QC fields — not the multi-gigabyte expression matrix — so it is
safe to run alongside a live GPU training job and produces a few-hundred-MB artifact
that every downstream label step (normalization, tiering, ambiguity review) can read
without touching the H5 again.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import h5py
except ImportError:  # Keep the module importable for tests that only need helpers.
    h5py = None


# Text fields kept verbatim for label recovery and provenance.
TEXT_FIELDS = (
    "geo_accession",
    "series_id",
    "source_name_ch1",
    "title",
    "characteristics_ch1",
    "molecule_ch1",
    "organism_ch1",
    "library_strategy",
    "library_source",
    "library_selection",
    "platform_id",
    "instrument_model",
    "last_update_date",
    "submission_date",
    "taxid_ch1",
)
# Numeric QC fields parsed to float (missing/NA -> NaN).
NUMERIC_FIELDS = (
    "singlecellprobability",
    "readsaligned",
    "readstotal",
)


def _decode(value) -> str:
    return value.decode("utf-8", "ignore") if isinstance(value, bytes) else str(value)


def _to_float(value) -> float:
    text = _decode(value).strip()
    if text in ("", "NA", "N/A", "nan", "NaN", "None"):
        return float("nan")
    try:
        return float(text)
    except ValueError:
        return float("nan")


def _sha256_lines(values) -> str:
    payload = "\n".join(values) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def export(args) -> dict:
    if h5py is None:
        raise RuntimeError("h5py is required to export ARCHS4 sample metadata")
    columns: dict[str, list] = {name: [] for name in TEXT_FIELDS + NUMERIC_FIELDS}
    with h5py.File(args.human_h5, "r") as handle:
        samples = handle["meta/samples"]
        available = set(samples.keys())
        missing = [f for f in TEXT_FIELDS + NUMERIC_FIELDS if f not in available]
        if "geo_accession" in missing:
            raise KeyError("meta/samples is missing geo_accession; cannot export")
        n_samples = len(samples["geo_accession"])
        info = handle.get("meta/info")
        source_info = {}
        if info is not None:
            for key in ("version", "creation-date"):
                if key in info:
                    source_info[key] = _decode(info[key][()])
        for start in range(0, n_samples, args.chunk_size):
            stop = min(start + args.chunk_size, n_samples)
            raw = {}
            for name in TEXT_FIELDS + NUMERIC_FIELDS:
                if name in available:
                    raw[name] = samples[name][start:stop]
            for name in TEXT_FIELDS:
                if name in raw:
                    columns[name].extend(_decode(v).strip() for v in raw[name])
                else:
                    columns[name].extend([""] * (stop - start))
            for name in NUMERIC_FIELDS:
                if name in raw:
                    columns[name].extend(_to_float(v) for v in raw[name])
                else:
                    columns[name].extend([float("nan")] * (stop - start))

    frame = pd.DataFrame(columns)
    for name in NUMERIC_FIELDS:
        frame[name] = pd.to_numeric(frame[name], errors="coerce")
    # Preserve native H5 order; record it so downstream joins stay reproducible.
    frame.insert(0, "h5_row", np.arange(len(frame), dtype=np.int64))

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output, index=False)

    report = {
        "schema_version": 1,
        "human_h5": str(Path(args.human_h5).resolve()),
        "n_samples": int(len(frame)),
        "text_fields": list(TEXT_FIELDS),
        "numeric_fields": list(NUMERIC_FIELDS),
        "missing_fields": missing,
        "geo_accession_sha256": _sha256_lines(frame["geo_accession"].tolist()),
        "source": {"n_samples": int(n_samples), **source_info},
        "output_parquet": str(output.resolve()),
        "note": (
            "Read-only ARCHS4 meta/samples snapshot for the Stage 1 label-recovery "
            "track. Expression matrix was not read."
        ),
    }
    report_path = output.with_name(output.stem + "_report.json")
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--human-h5", required=True)
    parser.add_argument(
        "--output",
        default="artifacts/stage1_label_recovery/human_sample_metadata.parquet",
    )
    parser.add_argument("--chunk-size", type=int, default=20_000)
    args = parser.parse_args()
    report = export(args)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
