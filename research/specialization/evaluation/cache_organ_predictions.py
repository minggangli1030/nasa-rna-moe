#!/usr/bin/env python3
"""Build an aligned, deterministic cache for organ-MoE evaluation.

The cache interface is deliberately independent of the training code.  A manifest
CSV defines samples and connected-study splits, the extractor's parquet (or a generic
NPZ) supplies expression targets, and repeated ``--prediction NAME=PATH`` arguments
supply arbitrary frozen models.

NPZ inputs must contain ``sample_ids`` and ``genes`` plus one matrix key.  Expression
matrices may use ``values``, ``expression``, ``targets``, or ``gt``; prediction
matrices may use ``predictions``, ``prediction``, ``pred``, ``values``, or ``output``.
Prediction exports must also contain ``mask_indices``, ``mask_seed``,
``mask_algorithm``, and ``mask_ratio``.  Matrices and masks are aligned by identifiers
rather than assumed to share row/column order.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd


SCHEMA_VERSION = 1
REQUIRED_MANIFEST_COLUMNS = {"sample_id", "organ", "series_group_id", "split"}
EXPRESSION_KEYS = ("values", "expression", "targets", "gt")
PREDICTION_KEYS = ("predictions", "prediction", "pred", "values", "output")
VALID_VALUE_SPACES = {"tpm", "log1p_tpm"}
MASK_ALGORITHM = "organ-moe-mask-v1"


def _sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_array(values: np.ndarray) -> str:
    values = np.asarray(values)
    digest = hashlib.sha256()
    digest.update(str(values.shape).encode("utf-8"))
    if values.dtype.kind in {"U", "S", "O"}:
        digest.update(b"<unicode>\0")
        for value in values.astype(str).ravel(order="C"):
            digest.update(value.encode("utf-8"))
            digest.update(b"\0")
    else:
        contiguous = np.ascontiguousarray(values)
        digest.update(contiguous.dtype.str.encode("ascii"))
        digest.update(contiguous.tobytes(order="C"))
    return digest.hexdigest()


def _sha256_lines(values) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(str(value).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _pick_matrix(z: np.lib.npyio.NpzFile, candidates: tuple[str, ...], path: Path) -> np.ndarray:
    for key in candidates:
        if key in z.files:
            matrix = np.asarray(z[key])
            if matrix.ndim != 2:
                raise ValueError(f"{path}: {key!r} must be a rank-2 matrix")
            return matrix
    raise ValueError(f"{path}: expected one of matrix keys {list(candidates)}")


def _unique_index(values: np.ndarray, label: str, path: Path) -> dict[str, int]:
    strings = np.asarray(values).astype(str)
    if strings.ndim != 1:
        raise ValueError(f"{path}: {label} must be rank 1")
    if len(np.unique(strings)) != len(strings):
        duplicates = pd.Series(strings)[pd.Series(strings).duplicated()].unique().tolist()
        raise ValueError(f"{path}: duplicate {label}: {duplicates[:5]}")
    return {value: index for index, value in enumerate(strings)}


def _load_aligned_matrix(
    path: Path,
    matrix_keys: tuple[str, ...],
    sample_ids: np.ndarray,
    genes: np.ndarray | None,
) -> tuple[np.ndarray, np.ndarray, str | None]:
    with np.load(path, allow_pickle=False) as z:
        required = {"sample_ids", "genes"}
        missing = required - set(z.files)
        if missing:
            raise ValueError(f"{path}: missing required fields {sorted(missing)}")
        source_ids = z["sample_ids"].astype(str)
        source_genes = z["genes"].astype(str)
        matrix = _pick_matrix(z, matrix_keys, path)
        embedded_space = None
        if "value_space" in z.files:
            raw_space = np.asarray(z["value_space"])
            if raw_space.size != 1:
                raise ValueError(f"{path}: value_space must be a scalar")
            embedded_space = str(raw_space.item())

    if matrix.shape != (len(source_ids), len(source_genes)):
        raise ValueError(
            f"{path}: matrix shape {matrix.shape} does not match "
            f"({len(source_ids)}, {len(source_genes)}) identifiers"
        )
    sample_index = _unique_index(source_ids, "sample_ids", path)
    gene_index = _unique_index(source_genes, "genes", path)
    missing_samples = [sample for sample in sample_ids if sample not in sample_index]
    if missing_samples:
        raise ValueError(f"{path}: missing manifest samples {missing_samples[:5]}")

    if genes is None:
        target_genes = source_genes
    else:
        target_genes = np.asarray(genes).astype(str)
        missing_genes = [gene for gene in target_genes if gene not in gene_index]
        if missing_genes:
            raise ValueError(f"{path}: missing reference genes {missing_genes[:5]}")

    rows = np.fromiter((sample_index[value] for value in sample_ids), dtype=np.int64)
    cols = np.fromiter((gene_index[value] for value in target_genes), dtype=np.int64)
    aligned = np.asarray(matrix[np.ix_(rows, cols)], dtype=np.float32)
    if not np.isfinite(aligned).all():
        raise ValueError(f"{path}: aligned matrix contains non-finite values")
    return aligned, target_genes, embedded_space


def _load_aligned_expression(
    path: Path,
    sample_ids: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, str | None]:
    if path.suffix.lower() not in {".parquet", ".pq"}:
        return _load_aligned_matrix(
            path, EXPRESSION_KEYS, sample_ids=sample_ids, genes=None
        )
    frame = pd.read_parquet(path)
    if "sample_id" not in frame:
        raise ValueError(f"{path}: expression parquet requires a sample_id column")
    source_ids = frame["sample_id"].astype(str).to_numpy()
    sample_index = _unique_index(source_ids, "sample_ids", path)
    genes = np.asarray([str(column) for column in frame.columns if column != "sample_id"])
    _unique_index(genes, "genes", path)
    if not len(genes):
        raise ValueError(f"{path}: expression parquet contains no gene columns")
    missing_samples = [sample for sample in sample_ids if sample not in sample_index]
    if missing_samples:
        raise ValueError(f"{path}: missing manifest samples {missing_samples[:5]}")
    rows = np.fromiter((sample_index[value] for value in sample_ids), dtype=np.int64)
    try:
        matrix = frame.iloc[rows][genes.tolist()].to_numpy(dtype=np.float32)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{path}: gene columns must be numeric") from exc
    if not np.isfinite(matrix).all():
        raise ValueError(f"{path}: aligned expression contains non-finite values")
    # The canonical extractor contract is raw TPM.  The explicit declaration is
    # still checked by the caller so a parquet cannot be silently double-transformed.
    return matrix, genes, "tpm"


def _validate_declared_space(
    path: Path,
    declared: str,
    embedded: str | None,
) -> str:
    declared = str(declared).strip().lower()
    if declared not in VALID_VALUE_SPACES:
        raise ValueError(
            f"{path}: unsupported declared value space {declared!r}; "
            f"choose one of {sorted(VALID_VALUE_SPACES)}"
        )
    if embedded is not None and embedded.strip().lower() != declared:
        raise ValueError(
            f"{path}: embedded value_space {embedded!r} disagrees with "
            f"declared space {declared!r}"
        )
    return declared


def _to_log1p_tpm(values: np.ndarray, source_space: str, path: Path) -> tuple[np.ndarray, str]:
    """Convert TPM exactly once; checkpoint outputs already use log1p(TPM)."""
    values = np.asarray(values, dtype=np.float32)
    if source_space == "log1p_tpm":
        return values, "none"
    if np.any(values < 0):
        raise ValueError(f"{path}: TPM values must be nonnegative before log1p")
    return np.log1p(values).astype(np.float32, copy=False), "log1p"


def _load_aligned_prediction_masks(
    path: Path,
    sample_ids: np.ndarray,
    genes: np.ndarray,
    expected_seed: int,
    expected_fraction: float,
) -> np.ndarray:
    """Align and validate the exact mask used to generate a prediction export."""
    with np.load(path, allow_pickle=False) as z:
        required = {
            "sample_ids", "genes", "mask_indices", "mask_seed", "mask_algorithm",
            "mask_ratio",
        }
        missing = required - set(z.files)
        if missing:
            raise ValueError(
                f"{path}: prediction export lacks mask provenance {sorted(missing)}"
            )
        source_ids = np.asarray(z["sample_ids"]).astype(str)
        source_genes = np.asarray(z["genes"]).astype(str)
        source_masks = np.asarray(z["mask_indices"], dtype=np.int64)
        mask_seed = int(np.asarray(z["mask_seed"]).item())
        mask_algorithm = str(np.asarray(z["mask_algorithm"]).item())
        mask_ratio = float(np.asarray(z["mask_ratio"]).item())

    if mask_algorithm != MASK_ALGORITHM:
        raise ValueError(
            f"{path}: mask_algorithm {mask_algorithm!r} != {MASK_ALGORITHM!r}"
        )
    if mask_seed != expected_seed:
        raise ValueError(f"{path}: mask_seed {mask_seed} != requested {expected_seed}")
    if not math.isclose(mask_ratio, expected_fraction, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError(
            f"{path}: mask_ratio {mask_ratio} != requested {expected_fraction}"
        )
    if source_masks.ndim != 2 or source_masks.shape[0] != len(source_ids):
        raise ValueError(f"{path}: mask_indices must have one row per sample")
    if source_masks.size and (
        source_masks.min() < 0 or source_masks.max() >= len(source_genes)
    ):
        raise ValueError(f"{path}: mask_indices contains an out-of-range gene index")
    if any(len(np.unique(row)) != len(row) for row in source_masks):
        raise ValueError(f"{path}: mask_indices contains duplicate genes within a sample")

    sample_index = _unique_index(source_ids, "sample_ids", path)
    target_gene_index = _unique_index(np.asarray(genes).astype(str), "genes", path)
    _unique_index(source_genes, "genes", path)
    missing_samples = [sample for sample in sample_ids if sample not in sample_index]
    if missing_samples:
        raise ValueError(f"{path}: masks missing manifest samples {missing_samples[:5]}")
    masked_gene_names = source_genes[source_masks]
    missing_genes = sorted(
        {str(gene) for gene in masked_gene_names.ravel() if gene not in target_gene_index}
    )
    if missing_genes:
        raise ValueError(f"{path}: masks reference genes absent from cache {missing_genes[:5]}")
    aligned = np.empty((len(sample_ids), source_masks.shape[1]), dtype=np.int32)
    for row, sample_id in enumerate(sample_ids):
        source_row = sample_index[str(sample_id)]
        aligned[row] = np.sort(
            [target_gene_index[str(gene)] for gene in masked_gene_names[source_row]]
        )
    return aligned


def _load_prediction_provenance(path: Path) -> dict:
    required = {
        "model_role", "model_selector_json", "training_seed",
        "train_sample_ids_sha256", "checkpoint_sha256", "expression_file_sha256",
        "mask_token",
    }
    with np.load(path, allow_pickle=False) as z:
        missing = required - set(z.files)
        if missing:
            raise ValueError(
                f"{path}: prediction export lacks training provenance {sorted(missing)}"
            )
        try:
            selector = json.loads(str(np.asarray(z["model_selector_json"]).item()))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"{path}: invalid model_selector_json") from exc
        if not isinstance(selector, dict):
            raise ValueError(f"{path}: model_selector_json must contain an object")
        return {
            "model_role": str(np.asarray(z["model_role"]).item()),
            "model_selector": {str(key): str(value) for key, value in selector.items()},
            "training_seed": int(np.asarray(z["training_seed"]).item()),
            "train_sample_ids_sha256": str(
                np.asarray(z["train_sample_ids_sha256"]).item()
            ),
            "checkpoint_sha256": str(np.asarray(z["checkpoint_sha256"]).item()),
            "expression_file_sha256": str(
                np.asarray(z["expression_file_sha256"]).item()
            ),
            "mask_token": float(np.asarray(z["mask_token"]).item()),
        }


def _boolean_column(frame: pd.DataFrame, column: str) -> np.ndarray:
    if column not in frame:
        raise ValueError(f"manifest lacks training eligibility column {column!r}")
    values = frame[column]
    if pd.api.types.is_bool_dtype(values.dtype):
        return values.fillna(False).to_numpy(dtype=bool)
    normalized = values.fillna("false").astype(str).str.strip().str.lower()
    allowed = {"true", "false", "1", "0", "yes", "no", "y", "n"}
    invalid = sorted(set(normalized) - allowed)
    if invalid:
        raise ValueError(
            f"manifest training eligibility column {column!r} has invalid values: "
            f"{invalid[:3]}"
        )
    return normalized.isin({"true", "1", "yes", "y"}).to_numpy(dtype=bool)


def deterministic_mask_indices(
    sample_ids: np.ndarray,
    n_genes: int,
    seed: int,
    mask_fraction: float,
    mask_count: int | None = None,
) -> np.ndarray:
    """Create order-independent masks keyed by ``(seed, sample_id)``."""
    if n_genes < 1:
        raise ValueError("n_genes must be positive")
    if mask_count is None:
        if not 0.0 < mask_fraction < 1.0:
            raise ValueError("mask_fraction must be in (0, 1)")
        mask_count = max(1, int(n_genes * mask_fraction))
    if mask_count < 1 or mask_count >= n_genes:
        raise ValueError("mask_count must be between 1 and n_genes - 1")

    masks = np.empty((len(sample_ids), mask_count), dtype=np.int32)
    for row, sample_id in enumerate(np.asarray(sample_ids).astype(str)):
        payload = f"{MASK_ALGORITHM}\0{seed}\0{sample_id}".encode("utf-8")
        sample_seed = int.from_bytes(hashlib.sha256(payload).digest()[:8], "little")
        rng = np.random.default_rng(sample_seed)
        masks[row] = np.sort(rng.choice(n_genes, size=mask_count, replace=False))
    return masks


def _parse_prediction_specs(specs: list[str]) -> list[tuple[str, Path]]:
    parsed: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for spec in specs:
        if "=" not in spec:
            raise ValueError(f"prediction spec must be NAME=PATH, got {spec!r}")
        name, raw_path = spec.split("=", 1)
        name = name.strip()
        if not name or name in seen:
            raise ValueError(f"prediction model names must be unique and nonempty: {name!r}")
        if not (name == "pooled" or name.startswith("organ:") or name.startswith("random:")):
            raise ValueError(
                f"unsupported model name {name!r}; use pooled, organ:LABEL, or random:LABEL"
            )
        seen.add(name)
        parsed.append((name, Path(raw_path).expanduser()))
    if "pooled" not in seen:
        raise ValueError("one prediction must be named 'pooled'")
    if not any(name.startswith("organ:") for name in seen):
        raise ValueError("at least one organ:LABEL prediction is required")
    return parsed


def _validate_manifest(frame: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_MANIFEST_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"manifest lacks required columns: {sorted(missing)}")
    out = frame.copy()
    for column in REQUIRED_MANIFEST_COLUMNS:
        if out[column].isna().any():
            raise ValueError(f"manifest column {column!r} contains missing values")
        out[column] = out[column].astype(str)
    if out["sample_id"].duplicated().any():
        duplicates = out.loc[out["sample_id"].duplicated(), "sample_id"].unique().tolist()
        raise ValueError(f"manifest contains duplicate sample IDs: {duplicates[:5]}")
    split_counts = out.groupby("series_group_id", sort=False)["split"].nunique()
    straddling = split_counts[split_counts > 1]
    if not straddling.empty:
        raise ValueError(
            "connected study groups straddle splits: " + ", ".join(straddling.index[:5])
        )
    return out.reset_index(drop=True)


def build_cache(args: argparse.Namespace | SimpleNamespace) -> dict:
    manifest_path = Path(args.manifest_csv).expanduser()
    expression_arg = getattr(args, "expression", None)
    if expression_arg is None:
        expression_arg = getattr(args, "expression_npz", None)
    if expression_arg is None:
        raise ValueError("an expression parquet or NPZ path is required")
    expression_path = Path(expression_arg).expanduser()
    output_path = Path(args.output).expanduser()
    prediction_specs = _parse_prediction_specs(list(args.prediction))
    for path in [manifest_path, expression_path, *(path for _, path in prediction_specs)]:
        if not path.is_file():
            raise FileNotFoundError(path)

    manifest = _validate_manifest(pd.read_csv(manifest_path))
    train_filter_column = str(getattr(args, "train_filter_column", "balanced_train"))
    train_split = str(getattr(args, "train_split", "train"))
    random_shard_column = str(getattr(args, "random_shard_column", "random_shard"))
    train_eligible = _boolean_column(manifest, train_filter_column)
    train_split_rows = manifest["split"].eq(train_split).to_numpy()
    if np.any(train_eligible & ~train_split_rows):
        raise ValueError(
            f"manifest {train_filter_column!r} marks rows outside train split "
            f"{train_split!r} as eligible"
        )
    if not np.any(train_eligible):
        raise ValueError("manifest training eligibility mask is empty")
    if random_shard_column not in manifest:
        raise ValueError(f"manifest lacks random shard column {random_shard_column!r}")
    random_shards = manifest[random_shard_column].fillna("").astype(str).to_numpy()
    sample_ids = manifest["sample_id"].to_numpy(dtype=str)
    expression_raw, genes, expression_embedded_space = _load_aligned_expression(
        expression_path, sample_ids
    )
    expression_input_space = _validate_declared_space(
        expression_path,
        getattr(args, "expression_input_space", getattr(args, "value_space", "tpm")),
        expression_embedded_space,
    )
    expression, expression_transform = _to_log1p_tpm(
        expression_raw, expression_input_space, expression_path
    )
    expression_file_sha256 = _sha256_file(expression_path)
    prediction_input_space = str(
        getattr(args, "prediction_input_space", "log1p_tpm")
    ).strip().lower()
    if prediction_input_space != "log1p_tpm":
        raise ValueError(
            "frozen checkpoint predictions must be declared as log1p_tpm; "
            "convert prediction exports before caching"
        )

    model_names: list[str] = []
    predictions: list[np.ndarray] = []
    prediction_hashes: dict[str, str] = {}
    prediction_masks: dict[str, np.ndarray] = {}
    prediction_provenance: dict[str, dict] = {}
    for name, path in prediction_specs:
        matrix, prediction_genes, embedded_space = _load_aligned_matrix(
            path, PREDICTION_KEYS, sample_ids=sample_ids, genes=genes
        )
        _validate_declared_space(path, prediction_input_space, embedded_space)
        if not np.array_equal(prediction_genes, genes):
            raise RuntimeError(f"{path}: internal gene alignment failure")
        exported_targets, target_genes, target_space = _load_aligned_matrix(
            path, ("targets",), sample_ids=sample_ids, genes=genes
        )
        _validate_declared_space(path, "log1p_tpm", target_space)
        if not np.array_equal(target_genes, genes) or not np.array_equal(
            exported_targets, expression
        ):
            raise ValueError(
                f"{path}: exported targets do not exactly match cache expression"
            )
        model_names.append(name)
        predictions.append(matrix)
        prediction_hashes[name] = _sha256_file(path)
        prediction_masks[name] = _load_aligned_prediction_masks(
            path,
            sample_ids,
            genes,
            expected_seed=int(args.mask_seed),
            expected_fraction=float(args.mask_fraction),
        )
        provenance = _load_prediction_provenance(path)
        if provenance["expression_file_sha256"] != expression_file_sha256:
            raise ValueError(
                f"{path}: training expression hash does not match cache expression file"
            )
        if not math.isclose(
            provenance["mask_token"], float(args.mask_token), rel_tol=0.0, abs_tol=1e-12
        ):
            raise ValueError(f"{path}: mask_token does not match cache request")
        if name == "pooled":
            expected_role, selector_key, selector_value = "pooled", None, None
            expected_rows = train_eligible
        elif name.startswith("organ:"):
            selector_value = name.split(":", 1)[1]
            expected_role, selector_key = "organ", "organ"
            expected_rows = train_eligible & manifest["organ"].eq(selector_value).to_numpy()
        else:
            selector_value = name.split(":", 1)[1]
            expected_role, selector_key = "random", "random_shard"
            expected_rows = train_eligible & (random_shards == selector_value)
        if provenance["model_role"] != expected_role:
            raise ValueError(
                f"{path}: model role {provenance['model_role']!r} does not match "
                f"cache name {name!r}"
            )
        if selector_key is not None and provenance["model_selector"].get(selector_key) != selector_value:
            raise ValueError(
                f"{path}: model selector does not match cache name {name!r}"
            )
        expected_train_ids = sorted(
            manifest.loc[expected_rows, "sample_id"].astype(str).tolist()
        )
        if not expected_train_ids:
            raise ValueError(f"cache name {name!r} selects no eligible training IDs")
        expected_train_hash = _sha256_lines(expected_train_ids)
        if provenance["train_sample_ids_sha256"] != expected_train_hash:
            raise ValueError(
                f"{path}: train_sample_ids_sha256 does not match manifest role selection"
            )
        prediction_provenance[name] = {
            **provenance,
            "expected_train_sample_ids_sha256": expected_train_hash,
            "n_expected_train_samples": len(expected_train_ids),
        }

    training_seeds = {item["training_seed"] for item in prediction_provenance.values()}
    if len(training_seeds) != 1:
        raise ValueError(
            f"prediction exports disagree on training seed: {sorted(training_seeds)}"
        )
    training_seed = next(iter(training_seeds))

    masks = deterministic_mask_indices(
        sample_ids,
        n_genes=len(genes),
        seed=int(args.mask_seed),
        mask_fraction=float(args.mask_fraction),
        mask_count=getattr(args, "mask_count", None),
    )
    for name, exported_masks in prediction_masks.items():
        if not np.array_equal(exported_masks, masks):
            first = None
            if exported_masks.shape == masks.shape:
                mismatch = np.argwhere(exported_masks != masks)
                first = mismatch[0].tolist() if mismatch.size else None
            raise ValueError(
                f"prediction {name!r} mask_indices do not match regenerated "
                f"{MASK_ALGORITHM} masks; shapes={exported_masks.shape}/{masks.shape}, "
                f"first mismatch={first}"
            )
    prediction_stack = np.stack(predictions).astype(np.float32, copy=False)
    relevant_manifest = manifest[
        ["sample_id", "organ", "series_group_id", "split", train_filter_column,
         random_shard_column]
    ]
    manifest_payload = relevant_manifest.to_csv(index=False, lineterminator="\n").encode("utf-8")
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "value_space": "log1p_tpm",
        "value_space_contract": {
            "expression_input": expression_input_space,
            "expression_transform": expression_transform,
            "prediction_input": prediction_input_space,
            "cache_targets": "log1p_tpm",
            "cache_predictions": "log1p_tpm",
        },
        "mask_algorithm": MASK_ALGORITHM,
        "prediction_masks_verified": True,
        "mask_seed": int(args.mask_seed),
        "mask_fraction": float(args.mask_fraction),
        "mask_count": int(masks.shape[1]),
        "mask_token": float(args.mask_token),
        "n_samples": int(len(sample_ids)),
        "n_genes": int(len(genes)),
        "n_models": int(len(model_names)),
        "model_names": model_names,
        "training_seed": int(training_seed),
        "training_eligibility": {
            "column": train_filter_column,
            "train_split": train_split,
            "n_eligible": int(train_eligible.sum()),
            "eligible_sample_ids_sha256": _sha256_lines(sample_ids[train_eligible]),
        },
        "prediction_provenance": prediction_provenance,
        "model_bundle_sha256": _sha256_lines(
            f"{name}\t{prediction_provenance[name]['checkpoint_sha256']}\t"
            f"{prediction_provenance[name]['train_sample_ids_sha256']}"
            for name in model_names
        ),
        "source_files": {
            "manifest": str(manifest_path.resolve()),
            "expression": str(expression_path.resolve()),
            "predictions": {
                name: str(path.resolve()) for name, path in prediction_specs
            },
        },
        "source_sha256": {
            "manifest_file": _sha256_file(manifest_path),
            "manifest_evaluation_columns": hashlib.sha256(manifest_payload).hexdigest(),
            "expression_file": expression_file_sha256,
            "prediction_files": prediction_hashes,
            "prediction_mask_indices": {
                name: _sha256_array(values) for name, values in prediction_masks.items()
            },
        },
        "content_sha256": {
            "sample_ids": _sha256_array(sample_ids),
            "organs": _sha256_array(manifest["organ"].to_numpy(dtype=str)),
            "series_group_id": _sha256_array(
                manifest["series_group_id"].to_numpy(dtype=str)
            ),
            "split": _sha256_array(manifest["split"].to_numpy(dtype=str)),
            "train_eligible": _sha256_array(train_eligible),
            "random_shard": _sha256_array(random_shards),
            "genes": _sha256_array(genes),
            "expression": _sha256_array(expression),
            "predictions": _sha256_array(prediction_stack),
            "mask_idx": _sha256_array(masks),
            "model_names": _sha256_array(np.asarray(model_names, dtype=str)),
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(output_path.name + ".tmp.npz")
    np.savez_compressed(
        temporary,
        sample_ids=sample_ids.astype("U"),
        organs=manifest["organ"].to_numpy(dtype=str).astype("U"),
        series_group_id=manifest["series_group_id"].to_numpy(dtype=str).astype("U"),
        split=manifest["split"].to_numpy(dtype=str).astype("U"),
        train_eligible=train_eligible.astype(bool),
        random_shard=random_shards.astype("U"),
        genes=genes.astype("U"),
        gt=expression,
        mask_idx=masks,
        model_names=np.asarray(model_names, dtype="U"),
        predictions=prediction_stack,
        metadata_json=np.asarray(json.dumps(metadata, sort_keys=True), dtype="U"),
    )
    os.replace(temporary, output_path)
    metadata_path = output_path.with_suffix(output_path.suffix + ".json")
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-csv", required=True)
    parser.add_argument(
        "--expression", "--expression-npz", dest="expression", required=True,
        help="Extractor expression.parquet (raw TPM) or generic expression NPZ.",
    )
    parser.add_argument(
        "--prediction",
        action="append",
        required=True,
        metavar="NAME=PATH",
        help="Repeat for pooled, organ:LABEL, and random:LABEL models.",
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--train-filter-column", required=True)
    parser.add_argument("--train-split", default="train")
    parser.add_argument("--random-shard-column", default="random_shard")
    parser.add_argument("--mask-seed", type=int, default=42)
    parser.add_argument("--mask-fraction", type=float, default=0.30)
    parser.add_argument("--mask-count", type=int)
    parser.add_argument("--mask-token", type=float, default=-10.0)
    parser.add_argument(
        "--expression-input-space",
        choices=sorted(VALID_VALUE_SPACES),
        default="tpm",
        help="Space in the expression NPZ; TPM is transformed by log1p exactly once.",
    )
    parser.add_argument(
        "--prediction-input-space",
        choices=["log1p_tpm"],
        default="log1p_tpm",
        help="Frozen checkpoint exports are required to be in model-space log1p(TPM).",
    )
    args = parser.parse_args()
    report = build_cache(args)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
