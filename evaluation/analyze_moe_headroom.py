#!/usr/bin/env python3
"""Evaluate interspecies expert and convex-mixture headroom.

The cache phase performs model inference in the exact input space used for
training. The analysis phase compares individual experts, out-of-fold fixed
blends, species-conditioned routers, and hard/soft per-sample oracles on one
shared finite cohort and one shared mask artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from evaluate_osdr import load_canonical_genes, load_checkpoint
from headroom_metrics import (
    apply_sample_weights,
    balanced_group_mean,
    crossfit_best_expert,
    crossfit_fixed_mse_blend,
    crossfit_species_mse_router,
    make_crossfit_folds,
    masked_values,
    mse_rows,
    paired_bootstrap_ci,
    pearson_rows,
    soft_oracle_mse_weights,
)


CACHE_SCHEMA_VERSION = 2
EXPERT_NAMES = ("human", "mouse", "mixed")
DEFAULT_MASK_TOKEN = -10.0
META_COLUMNS = {
    "species", "study_id", "series_id", "sample_id", "spaceflight", "fold",
    "series_group_id", "series_seen_in_any_reference", "geo_accession",
    "__index_level_0__",
}


def _sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_arrays(*arrays: np.ndarray) -> str:
    digest = hashlib.sha256()
    for array in arrays:
        contiguous = np.ascontiguousarray(array)
        digest.update(str(contiguous.shape).encode("ascii"))
        digest.update(contiguous.dtype.str.encode("ascii"))
        digest.update(contiguous.view(np.uint8))
    return digest.hexdigest()


def _finite_stats(values: np.ndarray) -> dict[str, float]:
    return {
        "min": float(values.min()),
        "median": float(np.median(values)),
        "mean": float(values.mean()),
        "p99": float(np.quantile(values, 0.99)),
        "max": float(values.max()),
        "median_row_sum": float(np.median(values.sum(axis=1))),
    }


def prepare_expression(values: np.ndarray, input_space: str) -> tuple[np.ndarray, dict]:
    """Validate and transform an expression matrix to model-space log1p(TPM)."""
    values = np.asarray(values, dtype=np.float32)
    if values.ndim != 2 or values.shape[0] == 0 or values.shape[1] == 0:
        raise ValueError("expression matrix must be a non-empty rank-2 array")
    if not np.isfinite(values).all():
        bad = ~np.isfinite(values)
        raise ValueError(
            f"expression matrix contains {int(bad.sum()):,} nonfinite values in "
            f"{int(np.any(bad, axis=1).sum()):,} samples; rebuild the dataset"
        )
    if float(values.min()) < -1e-6:
        raise ValueError(f"expression matrix contains negative values (min={values.min():.6g})")
    values = np.maximum(values, 0.0)
    before = _finite_stats(values)

    if input_space == "tpm":
        if before["max"] < 50.0 or before["median_row_sum"] < 1_000.0:
            raise ValueError(
                "--input-space=tpm does not look like TPM; values may already be log1p-transformed"
            )
        model_values = np.log1p(values).astype(np.float32, copy=False)
    elif input_space == "log1p_tpm":
        if before["max"] > 50.0 or before["p99"] > 30.0:
            raise ValueError(
                "--input-space=log1p_tpm has raw-scale values; pass --input-space=tpm"
            )
        model_values = values
    else:
        raise ValueError(f"unsupported input space: {input_space!r}")

    if not np.isfinite(model_values).all():
        raise ValueError("input transform produced nonfinite values")
    return model_values, {"input": before, "model": _finite_stats(model_values)}


def _build_common_space(canonical_genes, gene_lists):
    canonical_to_idx = {gene: i for i, gene in enumerate(canonical_genes)}
    common_set = set(canonical_genes).intersection(
        *(set(gene_list) for gene_list in gene_lists.values())
    )
    common_genes = [gene for gene in canonical_genes if gene in common_set]
    if not common_genes:
        raise ValueError("expert checkpoints have no genes in the canonical evaluation space")
    common_in_canonical = np.array(
        [canonical_to_idx[gene] for gene in common_genes], dtype=np.int64
    )
    common_in_native = {}
    for name, gene_list in gene_lists.items():
        native = {gene: i for i, gene in enumerate(gene_list)}
        common_in_native[name] = np.array(
            [native[gene] for gene in common_genes], dtype=np.int64
        )
    return common_genes, common_in_canonical, common_in_native


def _native_gene_idx_in_canonical(gene_list, canonical_genes):
    canonical_to_idx = {gene: i for i, gene in enumerate(canonical_genes)}
    missing = [gene for gene in gene_list if gene not in canonical_to_idx]
    if missing:
        raise ValueError(f"checkpoint gene list has noncanonical genes: {missing[:5]}")
    return np.array([canonical_to_idx[gene] for gene in gene_list], dtype=np.int64)


def _load_coverage(
    path: str | None,
    sample_ids: np.ndarray,
    canonical_genes: list[str],
) -> np.ndarray:
    if path is None:
        return np.ones((len(sample_ids), len(canonical_genes)), dtype=bool)
    z = np.load(path, allow_pickle=False)
    required = {"coverage", "genes", "sample_ids"}
    if not required.issubset(z.files):
        raise ValueError(f"coverage artifact must contain {sorted(required)}")
    artifact_samples = z["sample_ids"].astype(str)
    if not np.array_equal(artifact_samples, sample_ids.astype(str)):
        raise ValueError("coverage sample order does not match the evaluation parquet")
    artifact_genes = z["genes"].astype(str).tolist()
    gene_to_idx = {gene: i for i, gene in enumerate(artifact_genes)}
    missing = [gene for gene in canonical_genes if gene not in gene_to_idx]
    if missing:
        raise ValueError(f"coverage artifact is missing canonical genes: {missing[:5]}")
    coverage = np.asarray(z["coverage"], dtype=bool)
    if coverage.shape != (len(sample_ids), len(artifact_genes)):
        raise ValueError("coverage matrix shape does not match its sample/gene labels")
    return coverage[:, [gene_to_idx[gene] for gene in canonical_genes]]


def _make_or_load_mask(
    args,
    out_dir: Path,
    sample_ids: np.ndarray,
    common_genes: list[str],
    coverage_common: np.ndarray,
) -> np.ndarray:
    if args.mask_artifact:
        z = np.load(args.mask_artifact, allow_pickle=False)
        if not {"mask_idx_common", "common_genes", "sample_ids"}.issubset(z.files):
            raise ValueError("mask artifact is missing required arrays")
        if not np.array_equal(z["sample_ids"].astype(str), sample_ids.astype(str)):
            raise ValueError("mask artifact sample order differs from this dataset")
        if z["common_genes"].astype(str).tolist() != list(common_genes):
            raise ValueError("mask artifact gene order differs from checkpoint common space")
        mask_idx = np.asarray(z["mask_idx_common"], dtype=np.int64)
    else:
        available_per_sample = coverage_common.sum(axis=1)
        min_available = int(available_per_sample.min())
        num_mask = max(3, int(min_available * args.mask_ratio))
        if num_mask > min_available:
            raise ValueError("not enough covered genes to construct the requested mask")
        rng = np.random.default_rng(args.seed)
        mask_idx = np.stack([
            rng.choice(np.flatnonzero(coverage_common[i]), num_mask, replace=False)
            for i in range(len(sample_ids))
        ]).astype(np.int64)

    if mask_idx.shape[0] != len(sample_ids) or mask_idx.ndim != 2:
        raise ValueError("mask artifact has an invalid shape")
    if mask_idx.min() < 0 or mask_idx.max() >= len(common_genes):
        raise ValueError("mask artifact contains an out-of-range gene index")
    if not np.all(coverage_common[np.arange(len(sample_ids))[:, None], mask_idx]):
        raise ValueError("mask artifact targets genes absent from at least one sample")

    mask_path = out_dir / "mask_artifact.npz"
    np.savez_compressed(
        mask_path,
        schema_version=np.int64(CACHE_SCHEMA_VERSION),
        mask_idx_common=mask_idx,
        common_genes=np.asarray(common_genes, dtype="U"),
        sample_ids=sample_ids.astype("U"),
        mask_ratio=np.float64(args.mask_ratio),
        seed=np.int64(args.seed),
    )
    print(f"[mask] {mask_idx.shape[1]:,} genes/sample; hash={_sha256_arrays(mask_idx)[:16]}")
    return mask_idx


def _expert_predict_common(
    model,
    x_canonical,
    coverage_canonical,
    native_idx_in_canonical,
    common_in_native,
    mask_idx_common,
    batch_size,
    mask_token,
    device,
    name,
):
    n_samples = x_canonical.shape[0]
    pred_common = np.empty((n_samples, len(common_in_native)), dtype=np.float32)
    mask_idx_native = common_in_native[mask_idx_common]
    common_in_native_t = torch.from_numpy(common_in_native).to(device)
    started = time.time()
    for start in range(0, n_samples, batch_size):
        end = min(start + batch_size, n_samples)
        x_native = x_canonical[start:end][:, native_idx_in_canonical].copy()
        native_coverage = coverage_canonical[start:end][:, native_idx_in_canonical]
        x_native[~native_coverage] = mask_token
        rows = np.arange(end - start)[:, None]
        x_native[rows, mask_idx_native[start:end]] = mask_token
        with torch.no_grad():
            pred_native = model(torch.from_numpy(x_native).to(device, non_blocking=True))
        batch_pred = pred_native.index_select(1, common_in_native_t).cpu().numpy()
        if not np.isfinite(batch_pred).all():
            raise ValueError(f"{name} produced nonfinite predictions for rows {start}:{end}")
        pred_common[start:end] = batch_pred
        if start == 0 or end == n_samples or (start // batch_size) % 25 == 0:
            elapsed = time.time() - started
            eta = elapsed / end * (n_samples - end)
            print(f"  [{name}] {end}/{n_samples} elapsed={elapsed:.0f}s ETA={eta:.0f}s", flush=True)
    return pred_common


def cache_predictions(args, cache_path: Path, out_dir: Path):
    print("=" * 72)
    print("CACHE PHASE: validated model-space inference")
    print("=" * 72)
    canonical_genes = load_canonical_genes()
    frame = pd.read_parquet(args.eval_parquet)
    missing = [gene for gene in canonical_genes if gene not in frame.columns]
    if missing:
        raise ValueError(f"evaluation parquet is missing canonical genes: {missing[:5]}")
    sample_ids = (
        frame["sample_id"].astype(str).to_numpy()
        if "sample_id" in frame.columns else frame.index.astype(str).to_numpy()
    )
    if len(set(sample_ids)) != len(sample_ids):
        raise ValueError("evaluation sample IDs are not unique")
    x_canonical, value_stats = prepare_expression(
        frame[canonical_genes].to_numpy(dtype=np.float32), args.input_space
    )
    coverage_canonical = _load_coverage(args.coverage_npz, sample_ids, canonical_genes)
    print(f"[data] {x_canonical.shape[0]:,} samples x {x_canonical.shape[1]:,} genes")
    print(f"[data] input={args.input_space}; model stats={value_stats['model']}")

    device = torch.device(
        "cuda:0" if args.device == "auto" and torch.cuda.is_available()
        else "cpu" if args.device == "auto" else args.device
    )
    print(f"[device] {device}")
    expert_paths = {
        "human": Path(args.human_ckpt),
        "mouse": Path(args.mouse_ckpt),
        "mixed": Path(args.mixed_ckpt),
    }
    models, configs, gene_lists, checkpoint_info = {}, {}, {}, {}
    mask_tokens = set()
    for name, path in expert_paths.items():
        if not path.exists():
            raise FileNotFoundError(path)
        print(f"[load] {name}: {path}")
        model, config, gene_list = load_checkpoint(path, device)
        if not gene_list:
            raise ValueError(f"{name} checkpoint gene order could not be recovered")
        if config.get("normalization") != "log1p_tpm":
            raise ValueError(
                f"{name} checkpoint expects {config.get('normalization')!r}; "
                "this evaluator currently requires log1p_tpm experts"
            )
        mask_token = float(config.get("mask_token", DEFAULT_MASK_TOKEN))
        mask_tokens.add(mask_token)
        models[name], configs[name], gene_lists[name] = model, config, gene_list
        payload = torch.load(path, map_location="cpu", weights_only=False)
        checkpoint_info[name] = {
            "path": str(path.resolve()),
            "sha256": _sha256_file(path),
            "epoch": int(payload.get("epoch", -1)),
            "val_loss": float(payload.get("val_loss", float("nan"))),
            "num_genes": int(model.num_genes),
        }
        del payload
    if len(mask_tokens) != 1:
        raise ValueError(f"experts use different mask tokens: {sorted(mask_tokens)}")
    mask_token = mask_tokens.pop()

    common_genes, common_in_canonical, common_in_native = _build_common_space(
        canonical_genes, gene_lists
    )
    coverage_common = coverage_canonical[:, common_in_canonical]
    mask_idx_common = _make_or_load_mask(
        args, out_dir, sample_ids, common_genes, coverage_common
    )
    gt_common = x_canonical[:, common_in_canonical]
    predictions = {}
    for name in EXPERT_NAMES:
        native_idx = _native_gene_idx_in_canonical(gene_lists[name], canonical_genes)
        predictions[name] = _expert_predict_common(
            models[name], x_canonical, coverage_canonical, native_idx,
            common_in_native[name], mask_idx_common, args.batch_size,
            mask_token, device, name,
        )
        models[name] = None
        if device.type == "cuda":
            torch.cuda.empty_cache()

    save = {
        "schema_version": np.int64(CACHE_SCHEMA_VERSION),
        "common_genes": np.asarray(common_genes, dtype="U"),
        "mask_idx_common": mask_idx_common,
        "gt_common": gt_common,
        "pred_human": predictions["human"],
        "pred_mouse": predictions["mouse"],
        "pred_mixed": predictions["mixed"],
        "sample_ids": sample_ids.astype("U"),
        "input_space": np.asarray(args.input_space),
        "mask_ratio": np.float64(args.mask_ratio),
        "seed": np.int64(args.seed),
        "mask_sha256": np.asarray(_sha256_arrays(mask_idx_common)),
        "value_stats_json": np.asarray(json.dumps(value_stats, sort_keys=True)),
        "checkpoint_info_json": np.asarray(json.dumps(checkpoint_info, sort_keys=True)),
        "eval_parquet": np.asarray(str(Path(args.eval_parquet).resolve())),
    }
    for column in ("species", "study_id", "series_id", "series_group_id", "fold"):
        if column in frame.columns:
            save[column] = frame[column].astype(str).to_numpy(dtype="U")
    np.savez_compressed(cache_path, **save)
    print(f"[save] {cache_path} ({cache_path.stat().st_size / 2**20:.1f} MiB)")


def _load_baseline_mean(
    path: str | None, common_genes: list[str]
) -> tuple[np.ndarray | None, dict[str, np.ndarray], dict | None]:
    if path is None:
        return None, {}, None
    z = np.load(path, allow_pickle=False)
    if not {"genes", "mean"}.issubset(z.files):
        raise ValueError("baseline mean artifact must contain genes and mean")
    genes = z["genes"].astype(str).tolist()
    means = np.asarray(z["mean"], dtype=np.float64)
    if means.shape != (len(genes),) or not np.isfinite(means).all():
        raise ValueError("baseline mean artifact is invalid")
    gene_to_idx = {gene: i for i, gene in enumerate(genes)}
    missing = [gene for gene in common_genes if gene not in gene_to_idx]
    if missing:
        raise ValueError(f"baseline mean is missing common genes: {missing[:5]}")
    aligned = means[[gene_to_idx[gene] for gene in common_genes]]
    species_means = {}
    for species in ("human", "mouse"):
        key = f"mean_{species}"
        if key in z.files:
            values = np.asarray(z[key], dtype=np.float64)
            if values.shape != (len(genes),) or not np.isfinite(values).all():
                raise ValueError(f"baseline {key} is invalid")
            species_means[species] = values[[gene_to_idx[gene] for gene in common_genes]]
    metadata = {
        key: z[key].item() if np.asarray(z[key]).ndim == 0 else z[key].tolist()
        for key in z.files
        if key not in {"genes", "mean", "mean_human", "mean_mouse"}
    }
    return aligned, species_means, metadata


def _macro_gene_pearson(pred_masked, true_masked, mask_idx):
    correlations = []
    for gene in np.unique(mask_idx):
        rows, positions = np.where(mask_idx == gene)
        if len(rows) < 3:
            continue
        value = pearson_rows(
            pred_masked[rows, positions][None, :],
            true_masked[rows, positions][None, :],
        )[0]
        if np.isfinite(value):
            correlations.append(value)
    if not correlations:
        return float("nan"), 0
    return float(np.mean(correlations)), len(correlations)


def _condition_arrays(pred_masked, true_masked, baseline_masked):
    pearson = pearson_rows(pred_masked, true_masked)
    mse = mse_rows(pred_masked, true_masked)
    mae = np.mean(np.abs(pred_masked - true_masked), axis=1)
    result = {"pearson": pearson, "mse": mse, "mae": mae}
    if baseline_masked is not None:
        result["residual_pearson"] = pearson_rows(
            pred_masked - baseline_masked,
            true_masked - baseline_masked,
        )
    return result


def _summarize_condition(name, pred_masked, true_masked, baseline_masked, mask_idx):
    arrays = _condition_arrays(pred_masked, true_masked, baseline_masked)
    if np.isnan(arrays["pearson"]).any():
        raise ValueError(f"{name} has undefined Pearson rows on the shared evaluation cohort")
    macro, macro_n = _macro_gene_pearson(pred_masked, true_masked, mask_idx)
    summary = {
        "name": name,
        "pearson_mean": float(arrays["pearson"].mean()),
        "pearson_median": float(np.median(arrays["pearson"])),
        "mse_mean": float(arrays["mse"].mean()),
        "mse_median": float(np.median(arrays["mse"])),
        "mae_mean": float(arrays["mae"].mean()),
        "macro_gene_pearson": macro,
        "macro_gene_n": macro_n,
        "n_samples": int(len(true_masked)),
    }
    if baseline_masked is not None:
        baseline_sse = float(np.sum((true_masked - baseline_masked) ** 2))
        model_sse = float(np.sum((true_masked - pred_masked) ** 2))
        summary["residual_pearson_mean"] = float(arrays["residual_pearson"].mean())
        summary["r2_vs_gene_mean"] = 1.0 - model_sse / baseline_sse
    return summary, arrays


def _comparison(name, candidate, reference, groups, strata, seed, n_bootstrap):
    pearson_diff = candidate["pearson"] - reference["pearson"]
    mse_improvement = reference["mse"] - candidate["mse"]
    result = {
        "name": name,
        "estimand": "species-balanced study-macro mean" if strata is not None else "study-macro mean",
        "pearson_gain_mean": balanced_group_mean(pearson_diff, groups, strata),
        "pearson_gain_ci95": paired_bootstrap_ci(
            pearson_diff, seed, n_bootstrap, groups=groups, strata=strata
        ),
        "mse_improvement_mean": balanced_group_mean(mse_improvement, groups, strata),
        "mse_improvement_ci95": paired_bootstrap_ci(
            mse_improvement, seed + 1, n_bootstrap, groups=groups, strata=strata
        ),
    }
    if "residual_pearson" in candidate and "residual_pearson" in reference:
        residual_diff = candidate["residual_pearson"] - reference["residual_pearson"]
        result["residual_pearson_gain_mean"] = balanced_group_mean(
            residual_diff, groups, strata
        )
        result["residual_pearson_gain_ci95"] = paired_bootstrap_ci(
            residual_diff, seed + 2, n_bootstrap, groups=groups, strata=strata
        )
    return result


def analyze(args, cache_path: Path, out_dir: Path):
    print("=" * 72)
    print("ANALYSIS PHASE: cross-fitted blends and routing ceilings")
    print("=" * 72)
    z = np.load(cache_path, allow_pickle=False)
    if "schema_version" not in z.files or int(z["schema_version"]) != CACHE_SCHEMA_VERSION:
        raise ValueError(
            "legacy prediction cache rejected; delete it and rerun inference with the corrected evaluator"
        )
    common_genes = z["common_genes"].astype(str).tolist()
    mask_idx = np.asarray(z["mask_idx_common"], dtype=np.int64)
    true_full = np.asarray(z["gt_common"], dtype=np.float32)
    pred_full = np.stack([
        z["pred_human"], z["pred_mouse"], z["pred_mixed"]
    ]).astype(np.float32)
    if not np.isfinite(true_full).all() or not np.isfinite(pred_full).all():
        raise ValueError("cache contains nonfinite targets or predictions")
    source_mask_sha256 = str(z["mask_sha256"])
    if _sha256_arrays(mask_idx) != source_mask_sha256:
        raise ValueError("mask hash mismatch; cache is corrupted")

    sample_ids = z["sample_ids"].astype(str)
    species = z["species"].astype(str) if "species" in z.files else None
    metadata_arrays = {
        key: z[key].astype(str)
        for key in ("series_group_id", "series_id", "study_id", "fold")
        if key in z.files
    }
    sample_ids_file = getattr(args, "sample_ids_file", None)
    if sample_ids_file:
        requested = [line.strip() for line in Path(sample_ids_file).read_text().splitlines()
                     if line.strip()]
        if len(requested) != len(set(requested)):
            raise ValueError("sample filter contains duplicate IDs")
        index = {sample_id: i for i, sample_id in enumerate(sample_ids)}
        missing = [sample_id for sample_id in requested if sample_id not in index]
        if missing:
            raise ValueError(f"sample filter IDs are absent from prediction cache: {missing[:5]}")
        keep = np.array([index[sample_id] for sample_id in requested], dtype=np.int64)
        sample_ids = sample_ids[keep]
        true_full = true_full[keep]
        pred_full = pred_full[:, keep]
        mask_idx = mask_idx[keep]
        if species is not None:
            species = species[keep]
        metadata_arrays = {key: values[keep] for key, values in metadata_arrays.items()}
        print(f"[subset] retained {len(keep):,} samples from {sample_ids_file}")

    group_key = args.group_column
    if group_key and group_key not in metadata_arrays:
        raise ValueError(
            f"required group column {group_key!r} is absent from the prediction cache"
        )
    groups = metadata_arrays[group_key] if group_key else None
    if groups is not None and np.any((groups == "") | (groups == "nan")):
        raise ValueError(f"required group column {group_key!r} contains missing values")
    if groups is not None and species is not None:
        mixed_groups = [
            group for group in np.unique(groups)
            if len(np.unique(species[groups == group])) != 1
        ]
        if mixed_groups:
            raise ValueError(f"group IDs span multiple species: {mixed_groups[:5]}")

    true_masked = masked_values(true_full, mask_idx).astype(np.float64)
    pred_masked = np.stack([
        masked_values(pred_full[i], mask_idx) for i in range(3)
    ]).astype(np.float64)
    if np.any(np.std(true_masked, axis=1) < 1e-12):
        raise ValueError("at least one sample has a constant masked target; revise the mask artifact")

    baseline_mean, species_baseline_means, baseline_metadata = _load_baseline_mean(
        args.baseline_mean_npz, common_genes
    )
    global_baseline_masked = (
        np.broadcast_to(baseline_mean, true_full.shape)[
            np.arange(len(true_full))[:, None], mask_idx
        ] if baseline_mean is not None else None
    )
    baseline_masked = global_baseline_masked
    residual_baseline = "global_training_gene_mean"
    species_baseline_masked = None
    if species is not None and species_baseline_means:
        missing_species = sorted(set(species) - set(species_baseline_means))
        if missing_species:
            raise ValueError(f"baseline artifact lacks species means: {missing_species}")
        species_baseline_full = np.stack([
            species_baseline_means[label] for label in species
        ])
        species_baseline_masked = species_baseline_full[
            np.arange(len(true_full))[:, None], mask_idx
        ]
        baseline_masked = species_baseline_masked
        residual_baseline = "species_training_gene_mean"
    if baseline_masked is None:
        print("[warn] no disjoint training-derived gene mean supplied; residual metrics are omitted")

    strata = species if species is not None else None
    fold_ids = make_crossfit_folds(
        len(sample_ids), args.cv_folds, args.seed,
        strata=strata, groups=groups,
    )
    fixed = crossfit_fixed_mse_blend(pred_masked, true_masked, fold_ids)
    best_single_mse_crossfit = crossfit_best_expert(
        pred_masked, true_masked, fold_ids, "mse"
    )
    best_single_pearson_crossfit = crossfit_best_expert(
        pred_masked, true_masked, fold_ids, "pearson"
    )
    soft_weights = soft_oracle_mse_weights(pred_masked, true_masked)
    soft_oracle = apply_sample_weights(pred_masked, soft_weights)

    per_expert_pearson = np.stack([
        pearson_rows(pred_masked[i], true_masked) for i in range(3)
    ])
    per_expert_mse = np.stack([
        mse_rows(pred_masked[i], true_masked) for i in range(3)
    ])
    hard_pearson_choice = np.argmax(per_expert_pearson, axis=0)
    hard_mse_choice = np.argmin(per_expert_mse, axis=0)
    rows = np.arange(len(sample_ids))
    hard_pearson = pred_masked[hard_pearson_choice, rows]
    hard_mse = pred_masked[hard_mse_choice, rows]

    condition_predictions = {
        "human": pred_masked[0],
        "mouse": pred_masked[1],
        "mixed": pred_masked[2],
        "uniform": pred_masked.mean(axis=0),
        "best_single_mse_crossfit": best_single_mse_crossfit.pred_masked,
        "best_single_pearson_crossfit": best_single_pearson_crossfit.pred_masked,
        "fixed_blend_mse_crossfit": fixed.pred_masked,
    }
    species_router_details = None
    if species is not None and len(np.unique(species)) > 1:
        species_router = crossfit_species_mse_router(
            pred_masked, true_masked, fold_ids, species
        )
        condition_predictions["metadata_species_hard_mse_crossfit"] = species_router.hard_pred_masked
        condition_predictions["metadata_species_soft_mse_crossfit"] = species_router.soft_pred_masked
        species_router_details = {
            "hard_experts_by_fold": species_router.hard_experts,
            "soft_weights_by_fold": species_router.soft_weights,
        }
    condition_predictions.update({
        "hard_oracle_pearson": hard_pearson,
        "hard_oracle_mse": hard_mse,
        "soft_oracle_mse": soft_oracle,
    })
    if global_baseline_masked is not None:
        condition_predictions["training_gene_mean_global"] = global_baseline_masked
    if species_baseline_masked is not None:
        condition_predictions["training_gene_mean_species"] = species_baseline_masked

    summaries, arrays = {}, {}
    for name, prediction in condition_predictions.items():
        summaries[name], arrays[name] = _summarize_condition(
            name, prediction, true_masked, baseline_masked, mask_idx
        )
        summaries[name]["primary_pearson_study_macro"] = balanced_group_mean(
            arrays[name]["pearson"], groups, strata
        )
        summaries[name]["primary_mse_study_macro"] = balanced_group_mean(
            arrays[name]["mse"], groups, strata
        )
        if "residual_pearson" in arrays[name]:
            summaries[name]["primary_residual_pearson_study_macro"] = balanced_group_mean(
                arrays[name]["residual_pearson"], groups, strata
            )

    best_pearson_name = max(
        EXPERT_NAMES,
        key=lambda name: summaries[name]["primary_pearson_study_macro"],
    )
    best_mse_name = min(
        EXPERT_NAMES,
        key=lambda name: summaries[name]["primary_mse_study_macro"],
    )
    comparisons = [
        _comparison(
            "fixed_blend_vs_pooled_mixed",
            arrays["fixed_blend_mse_crossfit"], arrays["mixed"],
            groups, strata, args.seed + 50, args.bootstrap_reps,
        ),
        _comparison(
            "fixed_blend_vs_best_single_mse",
            arrays["fixed_blend_mse_crossfit"], arrays["best_single_mse_crossfit"],
            groups, strata, args.seed + 100, args.bootstrap_reps,
        ),
        _comparison(
            "hard_pearson_oracle_vs_best_single_pearson",
            arrays["hard_oracle_pearson"], arrays["best_single_pearson_crossfit"],
            groups, strata, args.seed + 200, args.bootstrap_reps,
        ),
        _comparison(
            "soft_mse_oracle_vs_fixed_blend",
            arrays["soft_oracle_mse"], arrays["fixed_blend_mse_crossfit"],
            groups, strata, args.seed + 300, args.bootstrap_reps,
        ),
        _comparison(
            "hard_mse_oracle_vs_fixed_blend",
            arrays["hard_oracle_mse"], arrays["fixed_blend_mse_crossfit"],
            groups, strata, args.seed + 350, args.bootstrap_reps,
        ),
    ]
    if species_router_details is not None:
        comparisons.extend([
            _comparison(
                "species_hard_vs_fixed_blend",
                arrays["metadata_species_hard_mse_crossfit"], arrays["fixed_blend_mse_crossfit"],
                groups, strata, args.seed + 400, args.bootstrap_reps,
            ),
            _comparison(
                "species_soft_vs_fixed_blend",
                arrays["metadata_species_soft_mse_crossfit"], arrays["fixed_blend_mse_crossfit"],
                groups, strata, args.seed + 500, args.bootstrap_reps,
            ),
            _comparison(
                "species_hard_vs_pooled_mixed",
                arrays["metadata_species_hard_mse_crossfit"], arrays["mixed"],
                groups, strata, args.seed + 550, args.bootstrap_reps,
            ),
            _comparison(
                "species_soft_vs_pooled_mixed",
                arrays["metadata_species_soft_mse_crossfit"], arrays["mixed"],
                groups, strata, args.seed + 600, args.bootstrap_reps,
            ),
        ])
        if species_baseline_masked is not None:
            comparisons.append(
                _comparison(
                    "species_soft_vs_species_training_gene_mean",
                    arrays["metadata_species_soft_mse_crossfit"],
                    arrays["training_gene_mean_species"],
                    groups, strata, args.seed + 650, args.bootstrap_reps,
                )
            )

    by_species = None
    if species is not None:
        by_species = {}
        for label in sorted(np.unique(species)):
            keep = species == label
            by_species[label] = {
                name: {
                    "n_samples": int(keep.sum()),
                    "pearson_mean": float(values["pearson"][keep].mean()),
                    "mse_mean": float(values["mse"][keep].mean()),
                    "pearson_study_macro": balanced_group_mean(
                        values["pearson"][keep], groups[keep] if groups is not None else None
                    ),
                    "mse_study_macro": balanced_group_mean(
                        values["mse"][keep], groups[keep] if groups is not None else None
                    ),
                }
                for name, values in arrays.items()
            }

    print(
        f"\n{'condition':<38} {'Pearson*':>9} {'resid_r*':>9} "
        f"{'MSE':>10} {'R2/mean':>9} {'gene_r':>9}"
    )
    print("-" * 89)
    for name, summary in summaries.items():
        print(
            f"{name:<38} {summary['primary_pearson_study_macro']:>9.4f} "
            f"{summary.get('primary_residual_pearson_study_macro', float('nan')):>9.4f} "
            f"{summary['primary_mse_study_macro']:>10.5f} "
            f"{summary.get('r2_vs_gene_mean', float('nan')):>9.4f} "
            f"{summary['macro_gene_pearson']:>9.4f}"
        )
    print("* species-balanced study-macro estimate")
    print("\nPaired gains (positive is better):")
    for comparison in comparisons:
        print(
            f"  {comparison['name']}: Pearson {comparison['pearson_gain_mean']:+.5f} "
            f"CI{tuple(round(x, 5) for x in comparison['pearson_gain_ci95'])}; "
            f"MSE {comparison['mse_improvement_mean']:+.6f} "
            f"CI{tuple(round(x, 6) for x in comparison['mse_improvement_ci95'])}"
            + (
                f"; residual-r {comparison['residual_pearson_gain_mean']:+.5f} "
                f"CI{tuple(round(x, 5) for x in comparison['residual_pearson_gain_ci95'])}"
                if "residual_pearson_gain_mean" in comparison else ""
            )
        )

    report = {
        "schema_version": CACHE_SCHEMA_VERSION,
        "run_label": args.run_label,
        "n_samples": int(len(sample_ids)),
        "n_common_genes": int(len(common_genes)),
        "n_masked_genes": int(mask_idx.shape[1]),
        "input_space": str(z["input_space"]),
        "mask_ratio": float(z["mask_ratio"]),
        "mask_sha256": _sha256_arrays(mask_idx),
        "source_cache_mask_sha256": source_mask_sha256,
        "sample_filter": str(Path(sample_ids_file).resolve()) if sample_ids_file else None,
        "group_column": group_key,
        "primary_estimand": "species-balanced study-macro mean",
        "cv_folds": args.cv_folds,
        "checkpoint_info": json.loads(str(z["checkpoint_info_json"])),
        "value_stats": json.loads(str(z["value_stats_json"])),
        "baseline_mean": baseline_metadata,
        "residual_baseline": residual_baseline if baseline_masked is not None else None,
        "best_single_pearson": best_pearson_name,
        "best_single_mse": best_mse_name,
        "conditions": summaries,
        "comparisons": comparisons,
        "fixed_blend_weights_by_fold": fixed.fold_weights,
        "best_single_mse_expert_by_fold": [
            EXPERT_NAMES[i] for i in best_single_mse_crossfit.expert_by_fold
        ],
        "best_single_pearson_expert_by_fold": [
            EXPERT_NAMES[i] for i in best_single_pearson_crossfit.expert_by_fold
        ],
        "species_router": species_router_details,
        "oracle": {
            "hard_pearson_choice_counts": dict(Counter(
                EXPERT_NAMES[i] for i in hard_pearson_choice.tolist()
            )),
            "hard_mse_choice_counts": dict(Counter(
                EXPERT_NAMES[i] for i in hard_mse_choice.tolist()
            )),
            "soft_mse_mean_weights": dict(zip(EXPERT_NAMES, soft_weights.mean(axis=0).tolist())),
        },
        "by_species": by_species,
    }
    report_path = out_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    fold_frame = pd.DataFrame({"sample_id": sample_ids, "fold": fold_ids})
    if species is not None:
        fold_frame["species"] = species
    if groups is not None:
        fold_frame[group_key] = groups
    fold_frame.to_csv(out_dir / "fold_assignments.csv", index=False)
    per_sample = fold_frame.copy()
    for name, values in arrays.items():
        per_sample[f"{name}__pearson"] = values["pearson"]
        per_sample[f"{name}__mse"] = values["mse"]
        per_sample[f"{name}__mae"] = values["mae"]
        if "residual_pearson" in values:
            per_sample[f"{name}__residual_pearson"] = values["residual_pearson"]
    per_sample["hard_oracle_pearson_choice"] = [
        EXPERT_NAMES[i] for i in hard_pearson_choice
    ]
    per_sample["hard_oracle_mse_choice"] = [EXPERT_NAMES[i] for i in hard_mse_choice]
    for expert_idx, expert_name in enumerate(EXPERT_NAMES):
        per_sample[f"soft_oracle_mse_weight_{expert_name}"] = soft_weights[:, expert_idx]
    per_sample.to_parquet(out_dir / "per_sample_metrics.parquet", index=False)
    print(f"\n[save] {report_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-parquet", "--osdr-parquet", dest="eval_parquet", required=True)
    parser.add_argument("--input-space", choices=("tpm", "log1p_tpm"))
    parser.add_argument("--human-ckpt", required=True)
    parser.add_argument("--mouse-ckpt", required=True)
    parser.add_argument("--mixed-ckpt", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-label", default="interspecies")
    parser.add_argument("--coverage-npz")
    parser.add_argument("--mask-artifact", help="Reuse an existing corrected mask artifact.")
    parser.add_argument("--cache-path", help="Use an external corrected predictions.npz cache.")
    parser.add_argument("--sample-ids-file",
                        help="Analyze an ordered subset of samples already present in the cache.")
    parser.add_argument("--baseline-mean-npz",
                        help="Training-derived model-space gene means; never final-test means.")
    parser.add_argument("--group-column", default="series_id")
    parser.add_argument("--mask-ratio", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cv-folds", type=int, default=5)
    parser.add_argument("--bootstrap-reps", type=int, default=2000)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--cache-only", action="store_true")
    parser.add_argument("--analyze-only", action="store_true")
    args = parser.parse_args()
    if not 0.0 < args.mask_ratio < 1.0:
        parser.error("--mask-ratio must be between 0 and 1")
    if not args.analyze_only and args.input_space is None:
        parser.error("--input-space is required for cache generation")
    if args.cache_only and args.analyze_only:
        parser.error("--cache-only and --analyze-only are mutually exclusive")

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_path = Path(args.cache_path) if args.cache_path else out_dir / "predictions.npz"
    if args.analyze_only and not cache_path.exists():
        raise FileNotFoundError(cache_path)
    if not args.analyze_only:
        cache_predictions(args, cache_path, out_dir)
    if not args.cache_only:
        analyze(args, cache_path, out_dir)


if __name__ == "__main__":
    main()
