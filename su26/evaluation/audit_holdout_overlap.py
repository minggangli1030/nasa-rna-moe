#!/usr/bin/env python3
"""Audit and optionally remove GEO-series overlap from an ARCHS4 holdout."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

try:
    import h5py
except ImportError:  # Split and token helpers do not require HDF5 support.
    h5py = None


# Keep this priority identical to core.train_single._read_parquet_index_ids.
INDEX_COLUMNS = ("geo_accession", "__index_level_0__", "sample_id")


def _decode(value) -> str:
    return value.decode("utf-8", "ignore") if isinstance(value, bytes) else str(value)


def load_archs4_series(h5_path: Path) -> dict[str, str]:
    if h5py is None:
        raise RuntimeError("h5py is required to read ARCHS4 metadata")
    with h5py.File(h5_path, "r") as handle:
        accessions = handle["meta/samples/geo_accession"][:]
        series_ids = handle["meta/samples/series_id"][:]
    tokens_by_accession: dict[str, set[str]] = {}
    for accession_raw, series_raw in zip(accessions, series_ids):
        accession = _decode(accession_raw)
        tokens_by_accession.setdefault(accession, set()).update(
            series_tokens(_decode(series_raw))
        )
    return {
        accession: " ".join(sorted(tokens))
        for accession, tokens in tokens_by_accession.items()
    }


def parquet_sample_ids(path: Path) -> list[str]:
    parquet = pq.ParquetFile(path)
    index_column = next(
        (column for column in INDEX_COLUMNS if column in parquet.schema_arrow.names), None
    )
    if index_column is None:
        raise ValueError(f"{path} has no recoverable sample-ID column")
    return [str(value) for value in parquet.read(columns=[index_column]).column(0).to_pylist()]


def series_tokens(value: str) -> set[str]:
    if value is None or pd.isna(value):
        return set()
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return set()
    return {token for token in text.replace(",", " ").split() if token}


def reproduce_split(
    sample_ids: list[str],
    species_by_id: dict[str, str],
    train_subset: int | None,
    val_subset: int | None,
    balanced_sampling: bool,
    seed: int = 42,
) -> tuple[list[str], list[str]]:
    """Mirror core.train_single.build_single_parquet_split without importing training."""
    rng = np.random.default_rng(seed)
    all_rows = [
        (i, species_by_id.get(sample_id, "unknown"))
        for i, sample_id in enumerate(sample_ids)
    ]
    by_species: dict[str, list[int]] = {}
    for row_idx, species in all_rows:
        by_species.setdefault(species, []).append(row_idx)
    known_species = {key: rows for key, rows in by_species.items() if key != "unknown"}

    if balanced_sampling and len(known_species) > 1:
        requested_total = None
        if train_subset is not None and val_subset is not None:
            requested_total = train_subset + val_subset
        elif train_subset is not None:
            requested_total = train_subset
        per_species = (
            requested_total // len(known_species)
            if requested_total is not None
            else min(len(rows) for rows in known_species.values())
        )
        selected_rows = []
        for rows in known_species.values():
            if len(rows) > per_species:
                take = rng.choice(len(rows), per_species, replace=False)
                selected_rows.extend(rows[i] for i in take)
            else:
                selected_rows.extend(rows)
        pool = selected_rows
    else:
        pool = [row for row, _ in all_rows]
        if train_subset is not None:
            requested_total = train_subset + val_subset if val_subset is not None else train_subset
            requested_total = min(requested_total, len(pool))
            take = rng.choice(len(pool), requested_total, replace=False)
            pool = [pool[i] for i in take]
    rng.shuffle(pool)
    train_count = int(0.8 * len(pool)) if train_subset is None else min(train_subset, len(pool))
    remaining = max(0, len(pool) - train_count)
    val_count = remaining if val_subset is None else min(val_subset, remaining)
    train_rows = pool[:train_count]
    val_rows = pool[train_count:train_count + val_count]
    return [sample_ids[i] for i in train_rows], [sample_ids[i] for i in val_rows]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--holdout", required=True)
    parser.add_argument("--human-h5", required=True)
    parser.add_argument("--mouse-h5", required=True)
    parser.add_argument(
        "--reference-split", action="append", required=True,
        help="label=path,train_count,val_count,balanced(0|1); repeat for every expert",
    )
    parser.add_argument("--annotated-output", required=True)
    parser.add_argument("--strict-output", required=True)
    parser.add_argument("--strict-ids-output", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    species_maps = {
        "human": load_archs4_series(Path(args.human_h5)),
        "mouse": load_archs4_series(Path(args.mouse_h5)),
    }
    shared_accessions = set(species_maps["human"]) & set(species_maps["mouse"])
    if shared_accessions:
        raise ValueError(
            "ARCHS4 H5 files contain accessions assigned to both species: "
            f"{sorted(shared_accessions)[:5]}"
        )
    accession_species = {
        accession: species for species, mapping in species_maps.items() for accession in mapping
    }
    per_reference = {}
    seen_series = {"human": set(), "mouse": set()}
    for specification in args.reference_split:
        if "=" not in specification:
            raise ValueError("--reference-split must use label=path,train,val,balanced syntax")
        label, settings = specification.split("=", 1)
        if not label or label in per_reference:
            raise ValueError(f"duplicate or empty reference label: {label!r}")
        raw_path, train_raw, val_raw, balanced_raw = settings.rsplit(",", 3)
        if balanced_raw not in {"0", "1"}:
            raise ValueError("reference balanced flag must be 0 or 1")
        all_sample_ids = parquet_sample_ids(Path(raw_path))
        if len(set(all_sample_ids)) != len(all_sample_ids):
            raise ValueError(f"{label} parquet sample IDs are not unique")
        missing_species = [sample_id for sample_id in all_sample_ids if sample_id not in accession_species]
        if missing_species:
            raise ValueError(f"{label} has IDs absent in ARCHS4 H5: {missing_species[:5]}")
        train_ids, val_ids = reproduce_split(
            all_sample_ids,
            accession_species,
            int(train_raw),
            int(val_raw),
            bool(int(balanced_raw)),
        )
        sample_ids = train_ids + val_ids
        series_by_species = {"human": set(), "mouse": set()}
        missing = []
        missing_series = []
        for sample_id in sample_ids:
            matches = [species for species, mapping in species_maps.items() if sample_id in mapping]
            if len(matches) != 1:
                missing.append(sample_id)
                continue
            species = matches[0]
            tokens = series_tokens(species_maps[species][sample_id])
            if not tokens:
                missing_series.append(sample_id)
                continue
            series_by_species[species].update(tokens)
        if missing:
            raise ValueError(f"{label} has IDs absent/ambiguous in ARCHS4 H5: {missing[:5]}")
        if missing_series:
            raise ValueError(f"{label} has samples without GEO series IDs: {missing_series[:5]}")
        for species in seen_series:
            seen_series[species].update(series_by_species[species])
        per_reference[label] = {
            "path": str(Path(raw_path).resolve()),
            "n_parquet_samples": len(all_sample_ids),
            "n_train_samples": len(train_ids),
            "n_val_samples": len(val_ids),
            "ordered_train_sample_id_sha256": hashlib.sha256(
                ("\n".join(train_ids) + "\n").encode("utf-8")
            ).hexdigest(),
            "ordered_val_sample_id_sha256": hashlib.sha256(
                ("\n".join(val_ids) + "\n").encode("utf-8")
            ).hexdigest(),
            "n_series_by_species": {
                species: len(series) for species, series in series_by_species.items()
            },
        }

    holdout = pd.read_parquet(args.holdout)
    required = {"sample_id", "species", "series_id"}
    if not required.issubset(holdout.columns):
        raise ValueError(f"holdout is missing metadata columns: {sorted(required - set(holdout.columns))}")
    if holdout["sample_id"].astype(str).duplicated().any():
        raise ValueError("holdout sample IDs are not unique")
    unexpected_species = sorted(set(holdout["species"].astype(str)) - {"human", "mouse"})
    if unexpected_species:
        raise ValueError(f"holdout has unsupported species labels: {unexpected_species}")
    empty_holdout_series = [
        sample_id for sample_id, raw_series in zip(
            holdout["sample_id"].astype(str), holdout["series_id"]
        ) if not series_tokens(raw_series)
    ]
    if empty_holdout_series:
        raise ValueError(f"holdout samples lack GEO series IDs: {empty_holdout_series[:5]}")

    all_seen_series = set().union(*seen_series.values())
    holdout["series_seen_in_any_reference"] = [
        bool(series_tokens(series_id) & all_seen_series)
        for series_id in holdout["series_id"].astype(str)
    ]
    strict = holdout[~holdout["series_seen_in_any_reference"]].copy()
    if strict.empty or strict["species"].nunique() != 2:
        raise ValueError("strict study-disjoint holdout lacks both species")

    annotated_output = Path(args.annotated_output)
    strict_output = Path(args.strict_output)
    strict_ids_output = Path(args.strict_ids_output)
    report_path = Path(args.report)
    for path in (annotated_output, strict_output, strict_ids_output, report_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    holdout.to_parquet(annotated_output, compression="zstd")
    strict.to_parquet(strict_output, compression="zstd")
    strict_ids_output.write_text(
        "\n".join(strict["sample_id"].astype(str)) + "\n"
    )

    report = {
        "schema_version": 1,
        "holdout": str(Path(args.holdout).resolve()),
        "references": per_reference,
        "reference_series_union": {
            **{species: len(series) for species, series in seen_series.items()},
            "global": len(all_seen_series),
        },
        "full_samples_by_species": holdout["species"].value_counts().sort_index().to_dict(),
        "full_series_by_species": holdout.groupby("species")["series_id"].nunique().sort_index().to_dict(),
        "overlapping_samples_by_species": (
            holdout[holdout["series_seen_in_any_reference"]]["species"]
            .value_counts().reindex(["human", "mouse"], fill_value=0).to_dict()
        ),
        "strict_samples_by_species": strict["species"].value_counts().sort_index().to_dict(),
        "strict_series_by_species": strict.groupby("species")["series_id"].nunique().sort_index().to_dict(),
        "strict_ordered_sample_id_sha256": hashlib.sha256(
            ("\n".join(strict["sample_id"].astype(str)) + "\n").encode("utf-8")
        ).hexdigest(),
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
