#!/usr/bin/env python3
"""Compute exact-training-split global and species gene-mean baselines."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

from audit_holdout_overlap import load_archs4_series, parquet_sample_ids, reproduce_split


# Keep both sets identical to the model's parquet loader. A stray metadata column
# should fail as non-numeric rather than silently changing the model gene layout.
META_COLUMNS = {"geo_accession", "__index_level_0__", "sample_id"}
INDEX_COLUMNS = ("geo_accession", "__index_level_0__", "sample_id")


def _ordered_id_sha256(sample_ids: list[str]) -> str:
    return hashlib.sha256(("\n".join(sample_ids) + "\n").encode("utf-8")).hexdigest()


def compute_gene_mean(
    parquet_path: Path,
    input_space: str,
    train_subset: int | None = None,
    val_subset: int = 0,
    balanced_sampling: bool = False,
    human_h5: Path | None = None,
    mouse_h5: Path | None = None,
    seed: int = 42,
) -> tuple[list[str], dict[str, np.ndarray], dict[str, int], dict]:
    if input_space not in {"tpm", "log1p_tpm"}:
        raise ValueError(f"unsupported input space: {input_space}")
    parquet = pq.ParquetFile(parquet_path)
    genes = [name for name in parquet.schema_arrow.names if name not in META_COLUMNS]
    index_column = next(
        (column for column in INDEX_COLUMNS if column in parquet.schema_arrow.names), None
    )
    if not genes or index_column is None:
        raise ValueError("reference parquet lacks expression columns or a sample-ID column")

    all_sample_ids = parquet_sample_ids(parquet_path)
    if len(set(all_sample_ids)) != len(all_sample_ids):
        raise ValueError("reference parquet sample IDs are not unique")
    species_by_id = {}
    if human_h5 is not None:
        species_by_id.update({sample_id: "human" for sample_id in load_archs4_series(human_h5)})
    if mouse_h5 is not None:
        for sample_id in load_archs4_series(mouse_h5):
            if sample_id in species_by_id:
                raise ValueError(f"sample ID occurs in both species H5 files: {sample_id}")
            species_by_id[sample_id] = "mouse"
    if not species_by_id:
        species_by_id = {sample_id: "unknown" for sample_id in all_sample_ids}
    missing = [sample_id for sample_id in all_sample_ids if sample_id not in species_by_id]
    if missing:
        raise ValueError(f"reference samples are absent from species metadata: {missing[:5]}")

    if train_subset is None:
        train_ids = list(all_sample_ids)
        heldout_val_ids = []
        row_policy = "all_rows"
    else:
        train_ids, heldout_val_ids = reproduce_split(
            all_sample_ids,
            species_by_id,
            train_subset,
            val_subset,
            balanced_sampling,
            seed=seed,
        )
        row_policy = "exact_train_rows_only"
    train_set = set(train_ids)
    if not train_ids:
        raise ValueError("the reproduced training split is empty")

    totals = {"global": np.zeros(len(genes), dtype=np.float64)}
    counts = {"global": 0}
    for species in sorted(set(species_by_id[sample_id] for sample_id in train_ids)):
        totals[species] = np.zeros(len(genes), dtype=np.float64)
        counts[species] = 0

    selected_seen = set()
    for row_group in range(parquet.metadata.num_row_groups):
        table = parquet.read_row_group(
            row_group, columns=[index_column, *genes], use_threads=True
        )
        row_ids = np.asarray([
            str(value) for value in table.column(index_column).to_pylist()
        ])
        keep = np.asarray([sample_id in train_set for sample_id in row_ids])
        if not keep.any():
            continue
        selected_ids = row_ids[keep]
        selected_seen.update(selected_ids.tolist())
        values = np.column_stack([
            table.column(gene).combine_chunks().to_numpy(zero_copy_only=False)[keep]
            for gene in genes
        ]).astype(np.float32, copy=False)
        if not np.isfinite(values).all():
            raise ValueError(f"row group {row_group} contains nonfinite values")
        if float(values.min()) < -1e-6:
            raise ValueError(f"row group {row_group} contains negative expression")
        values = np.maximum(values, 0.0)
        if input_space == "tpm":
            values = np.log1p(values)

        totals["global"] += values.sum(axis=0, dtype=np.float64)
        counts["global"] += len(values)
        selected_species = np.asarray([species_by_id[sample_id] for sample_id in selected_ids])
        for species in np.unique(selected_species):
            species_values = values[selected_species == species]
            totals[species] += species_values.sum(axis=0, dtype=np.float64)
            counts[species] += len(species_values)
        print(f"[mean] row group {row_group + 1}/{parquet.metadata.num_row_groups}: "
              f"{counts['global']:,}/{len(train_ids):,} selected samples", flush=True)

    if selected_seen != train_set or counts["global"] != len(train_ids):
        missing_selected = sorted(train_set - selected_seen)
        raise ValueError(
            "failed to read the exact selected training rows: "
            f"read={counts['global']}, expected={len(train_ids)}, "
            f"missing={missing_selected[:5]}"
        )
    means = {name: total / counts[name] for name, total in totals.items() if counts[name] > 0}
    split = {
        "row_policy": row_policy,
        "seed": seed,
        "train_subset_requested": train_subset,
        "val_subset_requested": val_subset,
        "balanced_sampling": balanced_sampling,
        "n_parquet_rows": len(all_sample_ids),
        "n_train_rows": len(train_ids),
        "n_val_rows_excluded": len(heldout_val_ids),
        "ordered_train_sample_id_sha256": _ordered_id_sha256(train_ids),
        "ordered_val_sample_id_sha256": _ordered_id_sha256(heldout_val_ids),
        "train_rows_by_species": {
            species: count for species, count in counts.items() if species != "global"
        },
    }
    return genes, means, counts, split


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parquet", required=True)
    parser.add_argument("--input-space", choices=("tpm", "log1p_tpm"), required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--label", default="reference_gene_mean")
    parser.add_argument("--train-subset", type=int)
    parser.add_argument("--val-subset", type=int, default=0)
    parser.add_argument("--balanced-sampling", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--human-h5")
    parser.add_argument("--mouse-h5")
    args = parser.parse_args()

    parquet_path = Path(args.parquet)
    genes, means, counts, split = compute_gene_mean(
        parquet_path,
        args.input_space,
        train_subset=args.train_subset,
        val_subset=args.val_subset,
        balanced_sampling=args.balanced_sampling,
        human_h5=Path(args.human_h5) if args.human_h5 else None,
        mouse_h5=Path(args.mouse_h5) if args.mouse_h5 else None,
        seed=args.seed,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    source = {
        "path": str(parquet_path.resolve()),
        "size_bytes": parquet_path.stat().st_size,
        "input_space": args.input_space,
        "model_space": "log1p_tpm",
        "label": args.label,
        **split,
    }
    arrays = {
        "genes": np.asarray(genes, dtype="U"),
        "mean": means["global"].astype(np.float32),
        "n_samples": np.int64(counts["global"]),
        "source_json": np.asarray(json.dumps(source, sort_keys=True)),
    }
    for species in ("human", "mouse"):
        if species in means:
            arrays[f"mean_{species}"] = means[species].astype(np.float32)
            arrays[f"n_samples_{species}"] = np.int64(counts[species])
    np.savez_compressed(output, **arrays)
    print(f"[save] {output}: {counts} x {len(genes):,} genes")


if __name__ == "__main__":
    main()
