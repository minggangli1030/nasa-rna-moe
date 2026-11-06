#!/usr/bin/env python3
"""Attach ARCHS4 GEO series IDs to an existing held-out expression parquet."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

try:
    import h5py
except ImportError:  # Pure grouping helpers remain usable without the optional IO dependency.
    h5py = None


METADATA_COLUMNS = {"sample_id", "species", "series_id", "series_group_id"}


def _decode(value) -> str:
    return value.decode("utf-8", "ignore") if isinstance(value, bytes) else str(value)


def _series_tokens(value) -> set[str]:
    if value is None or pd.isna(value):
        return set()
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return set()
    return {token for token in text.replace(",", " ").split() if token}


def load_sample_to_series(h5_path: Path, wanted: set[str]) -> dict[str, str]:
    if h5py is None:
        raise RuntimeError("h5py is required to read ARCHS4 metadata")
    with h5py.File(h5_path, "r") as handle:
        accessions = handle["meta/samples/geo_accession"][:]
        series_ids = handle["meta/samples/series_id"][:]
    tokens_by_accession: dict[str, set[str]] = {}
    for accession_raw, series_raw in zip(accessions, series_ids):
        accession = _decode(accession_raw)
        if accession in wanted:
            tokens_by_accession.setdefault(accession, set()).update(
                _series_tokens(_decode(series_raw))
            )
    return {
        accession: " ".join(sorted(tokens))
        for accession, tokens in tokens_by_accession.items()
    }


def _sha256_text(values: list[str]) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(value.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def connected_series_groups(series_values: list[str]) -> list[str]:
    """Group samples transitively when raw series fields share any GSE token."""
    tokens = [_series_tokens(value) for value in series_values]
    missing = [index for index, sample_tokens in enumerate(tokens) if not sample_tokens]
    if missing:
        raise ValueError(f"samples have empty ARCHS4 series IDs at rows: {missing[:5]}")
    parent = list(range(len(tokens)))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left, right):
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    first_by_token = {}
    for index, sample_tokens in enumerate(tokens):
        for token in sample_tokens:
            if token in first_by_token:
                union(index, first_by_token[token])
            else:
                first_by_token[token] = index
    component_tokens = {}
    for index, sample_tokens in enumerate(tokens):
        component_tokens.setdefault(find(index), set()).update(sample_tokens)
    return ["|".join(sorted(component_tokens[find(index)])) for index in range(len(tokens))]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--human-h5", required=True)
    parser.add_argument("--mouse-h5", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--manifest")
    args = parser.parse_args()

    source = pd.read_parquet(args.input)
    if "species" not in source.columns:
        raise ValueError("holdout parquet must contain a species column")
    sample_ids = (
        source["sample_id"].astype(str)
        if "sample_id" in source.columns
        else source.index.to_series().astype(str)
    )
    if len(set(sample_ids)) != len(sample_ids):
        raise ValueError("holdout sample IDs are not unique")
    species_values = source["species"].astype(str)
    unexpected_species = sorted(set(species_values) - {"human", "mouse"})
    if unexpected_species:
        raise ValueError(f"holdout has unsupported species labels: {unexpected_species}")

    mapping = {}
    for species, h5_arg in (("human", args.human_h5), ("mouse", args.mouse_h5)):
        wanted = set(sample_ids[species_values.to_numpy() == species])
        found = load_sample_to_series(Path(h5_arg), wanted)
        missing = sorted(wanted - set(found))
        if missing:
            raise ValueError(f"{species} H5 is missing holdout accessions: {missing[:5]}")
        missing_series = sorted(accession for accession, series in found.items()
                                if not _series_tokens(series))
        if missing_series:
            raise ValueError(
                f"{species} H5 has empty series IDs for holdout accessions: "
                f"{missing_series[:5]}"
            )
        mapping.update(found)

    raw_series = [mapping[sample_id] for sample_id in sample_ids]
    gene_columns = [column for column in source.columns if column not in METADATA_COLUMNS]
    metadata = pd.DataFrame({
        "sample_id": sample_ids.to_numpy(),
        "species": species_values.to_numpy(),
        "series_id": raw_series,
        "series_group_id": connected_series_groups(raw_series),
    }, index=source.index)
    frame = pd.concat([metadata, source[gene_columns]], axis=1)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output, compression="zstd")

    manifest = {
        "schema_version": 1,
        "input_parquet": str(Path(args.input).resolve()),
        "output_parquet": str(output.resolve()),
        "input_space": "tpm",
        "model_space_transform": "log1p(max(tpm, 0))",
        "n_samples": len(frame),
        "n_genes": len(gene_columns),
        "gene_order_sha256": _sha256_text([str(column) for column in gene_columns]),
        "species_counts": frame["species"].value_counts().sort_index().to_dict(),
        "series_counts": frame.groupby("species")["series_id"].nunique().sort_index().to_dict(),
        "series_group_counts": frame.groupby("species")["series_group_id"].nunique().sort_index().to_dict(),
    }
    manifest_path = Path(args.manifest) if args.manifest else output.with_suffix(".manifest.json")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"[save] {output}: {len(frame):,} samples, {len(gene_columns):,} genes")
    print(f"[save] {manifest_path}: {manifest['series_counts']}")


if __name__ == "__main__":
    main()
