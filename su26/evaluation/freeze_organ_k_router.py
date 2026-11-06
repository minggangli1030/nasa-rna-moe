#!/usr/bin/env python3
"""Freeze calibration-only routers for the preregistered organ-K search.

The artifact produced here has two jobs:

* provide connected-study out-of-fold routes for every nonempty specialist
  subset, while retaining probabilities for the nested K=1..5 search; and
* freeze a full-calibration K=5 linear router that can later be applied to a
  separately authorized test cache without refitting.

No train or test expression row is loaded.  Every score-panel gene is replaced
by the mask token before a scaler or classifier sees the calibration features.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
import zipfile
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as pads
import pyarrow.parquet as pq
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = ROOT / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from train_manifest import (  # noqa: E402
    read_manifest,
    select_manifest_rows,
    sha256_file,
    sha256_json,
    sha256_lines,
    validate_expression_metadata,
)
try:  # Support both package import and direct script execution.
    from .headroom_metrics import make_crossfit_folds
except ImportError:  # pragma: no cover - exercised by the CLI entry point
    from headroom_metrics import make_crossfit_folds


SCHEMA_VERSION = 1
N_SPLITS = 5
SPECIALIST_ORDER = (
    "brain",
    "skin",
    "skeletal_muscle",
    "adipose",
    "liver",
)


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


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


def _write_deterministic_npz(path: Path, arrays: dict[str, np.ndarray]) -> None:
    """Write an ``np.load`` compatible archive without wall-clock ZIP fields."""
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        with zipfile.ZipFile(
            handle, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archive:
            for name in sorted(arrays):
                value = np.asarray(arrays[name])
                if value.dtype.kind == "O":
                    raise ValueError(f"artifact array {name!r} may not use object dtype")
                payload = io.BytesIO()
                np.lib.format.write_array(payload, value, allow_pickle=False)
                member = zipfile.ZipInfo(f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
                member.compress_type = zipfile.ZIP_DEFLATED
                member.external_attr = 0o600 << 16
                archive.writestr(
                    member,
                    payload.getvalue(),
                    compress_type=zipfile.ZIP_DEFLATED,
                    compresslevel=9,
                )
    os.replace(temporary, path)


def mask_score_genes(
    expression: np.ndarray,
    score_gene_indices: np.ndarray,
    mask_token: float,
) -> np.ndarray:
    """Return a copy with every score-panel feature hidden for every row."""
    features = np.asarray(expression, dtype=np.float32)
    indices = np.asarray(score_gene_indices, dtype=np.int64)
    if features.ndim != 2:
        raise ValueError("router expression must be a rank-2 matrix")
    if indices.ndim != 1 or len(indices) < 1:
        raise ValueError("score_gene_indices must be a nonempty rank-1 array")
    if len(np.unique(indices)) != len(indices):
        raise ValueError("score_gene_indices contains duplicates")
    if int(indices.min()) < 0 or int(indices.max()) >= features.shape[1]:
        raise ValueError("score_gene_indices is outside the expression gene axis")
    masked = features.copy()
    masked[:, indices] = float(mask_token)
    return masked


def nested_router_labels(organs: np.ndarray, k: int) -> np.ndarray:
    """Map non-specialized organs to the pooled-fallback ``other`` class."""
    if k not in range(1, len(SPECIALIST_ORDER) + 1):
        raise ValueError("organ K must be between one and five")
    values = np.asarray(organs).astype(str)
    unknown = sorted(set(values) - set(SPECIALIST_ORDER))
    if unknown:
        raise ValueError(f"unexpected organ labels: {unknown}")
    selected_mask = np.arange(len(SPECIALIST_ORDER)) < k
    return subset_router_labels(values, selected_mask)


def subset_router_labels(organs: np.ndarray, selected_mask: np.ndarray) -> np.ndarray:
    """Map one explicit nonempty specialist subset to organ/``other`` labels."""
    values = np.asarray(organs).astype(str)
    mask = np.asarray(selected_mask, dtype=bool)
    if mask.shape != (len(SPECIALIST_ORDER),) or not np.any(mask):
        raise ValueError("selected_mask must select a nonempty subset of five organs")
    unknown = sorted(set(values) - set(SPECIALIST_ORDER))
    if unknown:
        raise ValueError(f"unexpected organ labels: {unknown}")
    selected = {
        organ for organ, include in zip(SPECIALIST_ORDER, mask) if bool(include)
    }
    if len(selected) == len(SPECIALIST_ORDER):
        return values.copy()
    return np.asarray(
        [organ if organ in selected else "other" for organ in values], dtype=str
    )


def collapse_k5_probabilities(
    probabilities: np.ndarray,
    class_names: np.ndarray,
    selected_mask: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Collapse one five-organ router into a selected-specialist/other router.

    This keeps the learned routing function fixed while changing only which
    specialists are deployed.  Probability mass for every undeployed organ is
    summed into the pooled-fallback ``other`` class.
    """
    values = np.asarray(probabilities, dtype=np.float64)
    names = np.asarray(class_names).astype(str)
    mask = np.asarray(selected_mask, dtype=bool)
    if values.ndim != 2 or values.shape[1] != len(names):
        raise ValueError("K5 probabilities and class names do not align")
    if len(names) != len(SPECIALIST_ORDER) or set(names) != set(SPECIALIST_ORDER):
        raise ValueError("K5 class names differ from the five specialist organs")
    if mask.shape != (len(SPECIALIST_ORDER),) or not np.any(mask):
        raise ValueError("selected_mask must select a nonempty subset of five organs")
    if not np.isfinite(values).all() or np.any(values < -1e-12):
        raise ValueError("K5 probabilities contain invalid values")
    if not np.allclose(values.sum(axis=1), 1.0, atol=1e-8):
        raise ValueError("K5 probabilities do not sum to one")

    selected = {
        organ for organ, include in zip(SPECIALIST_ORDER, mask) if bool(include)
    }
    mapped_names = np.asarray(
        sorted(selected | ({"other"} if len(selected) < len(SPECIALIST_ORDER) else set())),
        dtype=str,
    )
    mapped_index = {name: index for index, name in enumerate(mapped_names)}
    collapsed = np.zeros((len(values), len(mapped_names)), dtype=np.float64)
    for column, name in enumerate(names):
        destination = name if name in selected else "other"
        collapsed[:, mapped_index[destination]] += values[:, column]
    predicted = mapped_names[np.argmax(collapsed, axis=1)]
    return mapped_names, collapsed, predicted


def _classifier_sample_weights(labels: np.ndarray, groups: np.ndarray) -> np.ndarray:
    """Equalize connected studies within class; sklearn balances the classes."""
    labels = np.asarray(labels).astype(str)
    groups = np.asarray(groups).astype(str)
    weights = np.zeros(len(labels), dtype=np.float64)
    for label in np.unique(labels):
        label_rows = labels == label
        n_label = int(label_rows.sum())
        label_groups = np.unique(groups[label_rows])
        for group in label_groups:
            rows = label_rows & (groups == group)
            weights[rows] = n_label / (len(label_groups) * int(rows.sum()))
    if not np.all(weights > 0):
        raise RuntimeError("router sample weighting left a nonpositive row")
    return weights / weights.mean()


def _router_pipeline(seed: int):
    return make_pipeline(
        StandardScaler(),
        LogisticRegression(
            C=1.0,
            solver="lbfgs",
            class_weight="balanced",
            max_iter=2000,
            random_state=int(seed),
        ),
    )


def _fit_router(
    features: np.ndarray,
    labels: np.ndarray,
    groups: np.ndarray,
    *,
    seed: int,
):
    model = _router_pipeline(seed)
    weights = _classifier_sample_weights(labels, groups)
    model.fit(
        np.asarray(features, dtype=np.float32),
        np.asarray(labels).astype(str),
        logisticregression__sample_weight=weights,
    )
    return model, weights


def connected_study_folds(
    organs: np.ndarray,
    groups: np.ndarray,
    *,
    seed: int,
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    """Create one shared five-fold split stratified on the original five organs."""
    organs = np.asarray(organs).astype(str)
    groups = np.asarray(groups).astype(str)
    if organs.shape != groups.shape or organs.ndim != 1:
        raise ValueError("organs and groups must be aligned rank-1 arrays")
    for group in np.unique(groups):
        group_organs = np.unique(organs[groups == group])
        if len(group_organs) != 1:
            raise ValueError(
                f"connected study {group!r} spans organ strata {group_organs.tolist()}"
            )
    for organ in SPECIALIST_ORDER:
        count = len(np.unique(groups[organs == organ]))
        if count < N_SPLITS:
            raise ValueError(
                f"organ {organ!r} has only {count} connected studies; need {N_SPLITS}"
            )
    fold_for_row = make_crossfit_folds(
        len(organs),
        N_SPLITS,
        seed=int(seed),
        strata=organs,
        groups=groups,
    )
    reports: list[dict[str, Any]] = []
    for fold in range(N_SPLITS):
        held_rows = np.flatnonzero(fold_for_row == fold)
        fit_rows = np.flatnonzero(fold_for_row != fold)
        fit_groups = np.unique(groups[fit_rows])
        held_groups = np.unique(groups[held_rows])
        overlap = set(fit_groups) & set(held_groups)
        if overlap:
            raise RuntimeError(
                f"connected-study crossfit leakage in fold {fold}: {sorted(overlap)[:3]}"
            )
        held_organ_counts = {
            organ: int(np.sum(organs[held_rows] == organ))
            for organ in SPECIALIST_ORDER
        }
        if not all(count > 0 for count in held_organ_counts.values()):
            raise RuntimeError(
                f"crossfit fold {fold} lacks an organ stratum: {held_organ_counts}"
            )
        reports.append({
            "fold": fold,
            "n_fit_samples": int(len(fit_rows)),
            "n_held_samples": int(len(held_rows)),
            "n_fit_groups": int(len(fit_groups)),
            "n_held_groups": int(len(held_groups)),
            "fit_group_sha256": _sha256_array(fit_groups),
            "held_group_sha256": _sha256_array(held_groups),
            "held_organ_counts": held_organ_counts,
            "all_organs_present": True,
            "group_disjoint": True,
        })
    if np.any(fold_for_row < 0):
        raise RuntimeError("crossfit did not hold out every calibration row exactly once")
    return fold_for_row, reports


def _read_partition(path: Path) -> tuple[pd.DataFrame, str]:
    frame = read_manifest(path)
    if "split" in frame.columns and "utility_split" in frame.columns:
        left = frame["split"].astype(str)
        right = frame["utility_split"].astype(str)
        if not left.equals(right):
            raise ValueError("partition split and utility_split columns disagree")
        split_column = "split"
    elif "split" in frame.columns:
        split_column = "split"
    elif "utility_split" in frame.columns:
        split_column = "utility_split"
    else:
        raise ValueError("partition manifest lacks split or utility_split")
    return frame, split_column


def _report_manifest_hash(report: dict[str, Any]) -> str:
    hashes = report.get("hashes")
    if not isinstance(hashes, dict):
        raise ValueError("partition report lacks a hashes dictionary")
    values = [
        hashes[name]
        for name in ("partition_manifest_sha256", "train_cal_partitions_sha256")
        if hashes.get(name) is not None
    ]
    if not values:
        raise ValueError(
            "partition report must bind partition_manifest_sha256 or "
            "train_cal_partitions_sha256"
        )
    if len(set(map(str, values))) != 1:
        raise ValueError("partition report contains conflicting manifest hashes")
    return str(values[0])


def _verify_optional_file_hashes(
    report: dict[str, Any], bindings: Iterable[tuple[tuple[str, ...], Path]]
) -> None:
    hashes = report.get("hashes", {})
    for names, path in bindings:
        declared = [str(hashes[name]) for name in names if hashes.get(name) is not None]
        if declared and any(value != sha256_file(path) for value in declared):
            raise ValueError(
                f"partition report hash does not match {path} ({', '.join(names)})"
            )


def _expression_schema(path: Path, sample_id_column: str) -> list[str]:
    parquet = pq.ParquetFile(path)
    names = parquet.schema_arrow.names
    if sample_id_column not in names:
        raise ValueError(f"expression parquet lacks {sample_id_column!r}")
    genes = [name for name in names if name != sample_id_column]
    if not genes or len(genes) != len(set(genes)):
        raise ValueError("expression parquet must have unique gene columns")
    for gene in genes:
        field_type = parquet.schema_arrow.field(gene).type
        if not (pa.types.is_integer(field_type) or pa.types.is_floating(field_type)):
            raise ValueError(f"expression gene {gene!r} is not numeric")
    return genes


def _load_calibration_expression_only(
    path: Path,
    sample_ids: np.ndarray,
    gene_columns: list[str],
    *,
    sample_id_column: str,
) -> np.ndarray:
    """Materialize only rows selected by the calibration sample-ID predicate."""
    wanted = np.asarray(sample_ids).astype(str)
    if len(wanted) != len(np.unique(wanted)):
        raise ValueError("calibration sample IDs contain duplicates")
    dataset = pads.dataset(path, format="parquet")
    table = dataset.to_table(
        columns=[sample_id_column, *gene_columns],
        filter=pads.field(sample_id_column).isin(wanted.tolist()),
    )
    loaded_ids = np.asarray(table[sample_id_column].to_pylist()).astype(str)
    if len(loaded_ids) != len(wanted) or len(np.unique(loaded_ids)) != len(loaded_ids):
        missing = sorted(set(wanted) - set(loaded_ids))
        raise ValueError(
            "calibration-only expression scan did not return exactly one row per sample; "
            f"missing={missing[:3]}"
        )
    row_for_id = {sample_id: row for row, sample_id in enumerate(loaded_ids)}
    if set(row_for_id) != set(wanted):
        extra = sorted(set(row_for_id) - set(wanted))
        raise RuntimeError(f"expression scan returned non-calibration rows: {extra[:3]}")
    columns = [
        table[gene].combine_chunks().to_numpy(zero_copy_only=False)
        for gene in gene_columns
    ]
    unordered = np.column_stack(columns).astype(np.float32, copy=False)
    values = unordered[[row_for_id[sample_id] for sample_id in wanted]]
    if not np.isfinite(values).all() or np.any(values < 0):
        raise ValueError("calibration TPM expression contains invalid values")
    return values


def _aligned_calibration_rows(args: argparse.Namespace) -> tuple[pd.DataFrame, dict]:
    source = read_manifest(args.source_manifest)
    selection = select_manifest_rows(
        source,
        role="pooled",
        train_split=args.train_split,
        validation_split=args.calibration_split,
        train_filter_column=args.train_filter_column,
        sample_id_column=args.sample_id_column,
        split_column=args.source_split_column,
        organ_column=args.organ_column,
        group_column=args.group_column,
    )
    source_calibration = selection.validation[
        [args.sample_id_column, args.organ_column, args.group_column]
    ].copy()
    source_calibration = source_calibration.sort_values(args.sample_id_column).reset_index(drop=True)

    partition, partition_split_column = _read_partition(Path(args.partition_manifest))
    required = {args.sample_id_column, args.organ_column, args.group_column}
    missing = sorted(required - set(partition.columns))
    if missing:
        raise ValueError(f"partition manifest lacks required columns: {missing}")
    split_values = partition[partition_split_column].astype(str)
    unexpected = sorted(set(split_values) - {args.train_split, args.calibration_split})
    if unexpected:
        raise ValueError(
            "confirmation partition may contain train/calibration rows only; "
            f"found {unexpected}"
        )
    partition_calibration = partition.loc[
        split_values == args.calibration_split,
        [args.sample_id_column, args.organ_column, args.group_column],
    ].copy()
    partition_calibration = partition_calibration.sort_values(
        args.sample_id_column
    ).reset_index(drop=True)
    if partition_calibration.empty:
        raise ValueError("partition manifest has no calibration rows")
    for column in (args.sample_id_column, args.organ_column, args.group_column):
        if partition_calibration[column].isna().any():
            raise ValueError(f"partition calibration column {column!r} has missing values")
        partition_calibration[column] = partition_calibration[column].astype(str)
        source_calibration[column] = source_calibration[column].astype(str)
    if partition_calibration[args.sample_id_column].duplicated().any():
        raise ValueError("partition calibration sample IDs are not unique")
    if not partition_calibration.equals(source_calibration):
        raise ValueError(
            "partition calibration rows do not exactly match the frozen source-manifest "
            "calibration selection"
        )
    return partition_calibration, {
        "source_train_samples_selected_but_not_loaded": int(len(selection.train)),
        "partition_train_rows_not_loaded": int(np.sum(split_values == args.train_split)),
        "partition_split_column": partition_split_column,
    }


def freeze(args: argparse.Namespace) -> dict[str, Any]:
    expression_path = Path(args.expression_parquet)
    expression_metadata_path = Path(args.expression_metadata)
    source_manifest_path = Path(args.source_manifest)
    axis_definitions_path = Path(args.axis_definitions)
    partition_manifest_path = Path(args.partition_manifest)
    partition_report_path = Path(args.partition_report)
    for path in (
        expression_path,
        expression_metadata_path,
        source_manifest_path,
        axis_definitions_path,
        partition_manifest_path,
        partition_report_path,
    ):
        if not path.exists():
            raise FileNotFoundError(path)

    partition_report = json.loads(partition_report_path.read_text())
    if partition_report.get("status") not in (None, "complete"):
        raise ValueError("partition report is not complete")
    if partition_report.get("test_accessed") is not False:
        raise ValueError("partition report must explicitly declare test_accessed=false")
    if _report_manifest_hash(partition_report) != sha256_file(partition_manifest_path):
        raise ValueError("partition manifest SHA256 does not match its report")
    _verify_optional_file_hashes(partition_report, (
        (("expression_sha256", "expression_parquet_sha256"), expression_path),
        (("source_manifest_sha256", "manifest_sha256"), source_manifest_path),
        (("axis_definitions_sha256",), axis_definitions_path),
    ))

    calibration, selection_info = _aligned_calibration_rows(args)
    sample_ids = calibration[args.sample_id_column].to_numpy(dtype=str)
    organs = calibration[args.organ_column].to_numpy(dtype=str)
    groups = calibration[args.group_column].to_numpy(dtype=str)
    reported_calibration_hash = partition_report.get("hashes", {}).get(
        "calibration_sample_ids_sha256"
    )
    if (
        reported_calibration_hash is not None
        and str(reported_calibration_hash) != sha256_lines(sample_ids.tolist())
    ):
        raise ValueError("calibration sample order differs from the partition report")
    if set(organs) != set(SPECIALIST_ORDER):
        raise ValueError(
            f"calibration must contain exactly {list(SPECIALIST_ORDER)}, found {sorted(set(organs))}"
        )

    genes = _expression_schema(expression_path, args.sample_id_column)
    expression_metadata = validate_expression_metadata(
        expression_path, genes, metadata_path=expression_metadata_path
    )
    with np.load(axis_definitions_path, allow_pickle=False) as definitions:
        if "score_gene_indices" not in definitions.files or "gene_names" not in definitions.files:
            raise ValueError("axis definitions lacks score_gene_indices or gene_names")
        score_gene_indices = np.asarray(definitions["score_gene_indices"], dtype=np.int64)
        definition_genes = np.asarray(definitions["gene_names"]).astype(str)
    if list(definition_genes) != genes:
        raise ValueError("axis-definition gene order differs from expression parquet")

    # The only expression scan in this program is explicitly filtered to these
    # calibration IDs.  Train and test expression values are never materialized.
    calibration_tpm = _load_calibration_expression_only(
        expression_path,
        sample_ids,
        genes,
        sample_id_column=args.sample_id_column,
    )
    calibration_log1p = np.log1p(calibration_tpm).astype(np.float32, copy=False)
    features = mask_score_genes(
        calibration_log1p, score_gene_indices, args.mask_token
    )
    if not np.all(features[:, score_gene_indices] == np.float32(args.mask_token)):
        raise RuntimeError("score-panel target-hiding assertion failed")

    fold_for_row, fold_reports = connected_study_folds(
        organs, groups, seed=args.router_seed
    )
    arrays: dict[str, np.ndarray] = {
        "calibration_sample_ids": sample_ids,
        "calibration_organs": organs,
        "calibration_series_group_id": groups,
        "crossfit_fold": fold_for_row,
        "gene_names": np.asarray(genes, dtype=str),
        "score_gene_indices": score_gene_indices,
        "score_gene_names": np.asarray(genes, dtype=str)[score_gene_indices],
        "mask_token": np.asarray(float(args.mask_token), dtype=np.float64),
        "specialist_order": np.asarray(SPECIALIST_ORDER, dtype=str),
    }
    # Fit one five-organ routing function per outer fold.  Every K/subset below
    # is a deterministic probability collapse of this common router, so changing
    # K changes deployment coverage rather than silently changing model capacity.
    full_labels = organs.copy()
    full_classes = np.unique(full_labels)
    if set(full_classes) != set(SPECIALIST_ORDER):
        raise RuntimeError("five-organ router class family is incomplete")
    crossfit_probabilities = np.empty(
        (len(organs), len(full_classes)), dtype=np.float64
    )
    outer_inner_probabilities = np.zeros(
        (N_SPLITS, len(organs), len(full_classes)), dtype=np.float64
    )
    outer_inner_valid_mask = np.zeros((N_SPLITS, len(organs)), dtype=bool)
    nested_reports: list[dict[str, Any]] = []
    for outer_fold in range(N_SPLITS):
        outer_held = fold_for_row == outer_fold
        outer_fit = ~outer_held
        model, _ = _fit_router(
            features[outer_fit], full_labels[outer_fit], groups[outer_fit],
            seed=args.router_seed + outer_fold,
        )
        classes = model.named_steps["logisticregression"].classes_.astype(str)
        if not np.array_equal(classes, full_classes):
            raise RuntimeError("outer router class order changed between folds")
        crossfit_probabilities[outer_held] = model.predict_proba(
            features[outer_held]
        )

        fit_rows = np.flatnonzero(outer_fit)
        inner_folds = make_crossfit_folds(
            len(fit_rows),
            N_SPLITS - 1,
            seed=int(args.router_seed) + 10_000 + outer_fold,
            strata=organs[outer_fit],
            groups=groups[outer_fit],
        )
        inner_rows_report: list[dict[str, Any]] = []
        for inner_fold in range(N_SPLITS - 1):
            inner_held_local = inner_folds == inner_fold
            inner_fit_local = ~inner_held_local
            inner_held = fit_rows[inner_held_local]
            inner_fit = fit_rows[inner_fit_local]
            if set(groups[inner_fit]) & set(groups[inner_held]):
                raise RuntimeError(
                    f"nested router group leakage outer={outer_fold}, "
                    f"inner={inner_fold}"
                )
            if set(organs[inner_fit]) != set(SPECIALIST_ORDER):
                raise ValueError(
                    f"nested router fit lacks an organ outer={outer_fold}, "
                    f"inner={inner_fold}"
                )
            if set(organs[inner_held]) != set(SPECIALIST_ORDER):
                raise ValueError(
                    f"nested router held fold lacks an organ outer={outer_fold}, "
                    f"inner={inner_fold}"
                )
            inner_model, _ = _fit_router(
                features[inner_fit],
                full_labels[inner_fit],
                groups[inner_fit],
                seed=args.router_seed + 100 * (outer_fold + 1) + inner_fold,
            )
            inner_classes = inner_model.named_steps[
                "logisticregression"
            ].classes_.astype(str)
            if not np.array_equal(inner_classes, full_classes):
                raise RuntimeError("inner router class order changed between folds")
            outer_inner_probabilities[outer_fold, inner_held] = (
                inner_model.predict_proba(features[inner_held])
            )
            outer_inner_valid_mask[outer_fold, inner_held] = True
            inner_rows_report.append({
                "inner_fold": int(inner_fold),
                "n_fit_samples": int(len(inner_fit)),
                "n_held_samples": int(len(inner_held)),
                "fit_group_sha256": _sha256_array(np.unique(groups[inner_fit])),
                "held_group_sha256": _sha256_array(np.unique(groups[inner_held])),
                "all_organs_present_in_fit_and_held": True,
                "group_disjoint": True,
            })
        if not np.array_equal(outer_inner_valid_mask[outer_fold], outer_fit):
            raise RuntimeError(
                f"nested router did not predict exactly outer-fit rows {outer_fold}"
            )
        nested_reports.append({
            "outer_fold": int(outer_fold),
            "outer_fit_sample_ids_sha256": _sha256_array(sample_ids[outer_fit]),
            "outer_held_sample_ids_sha256": _sha256_array(sample_ids[outer_held]),
            "inner_folds": inner_rows_report,
        })
    if not np.allclose(crossfit_probabilities.sum(axis=1), 1.0, atol=1e-10):
        raise RuntimeError("outer crossfit K5 probabilities do not sum to one")
    for outer_fold in range(N_SPLITS):
        valid = outer_inner_valid_mask[outer_fold]
        if not np.allclose(
            outer_inner_probabilities[outer_fold, valid].sum(axis=1),
            1.0,
            atol=1e-10,
        ):
            raise RuntimeError(
                f"inner crossfit K5 probabilities do not sum to one: {outer_fold}"
            )

    subset_ids = np.arange(1, 1 << len(SPECIALIST_ORDER), dtype=np.int64)
    subset_selected_mask = (
        (subset_ids[:, None] >> np.arange(len(SPECIALIST_ORDER), dtype=np.int64)) & 1
    ).astype(bool)
    subset_k = subset_selected_mask.sum(axis=1).astype(np.int64)
    label_width = max(len(label) for label in (*SPECIALIST_ORDER, "other"))
    subset_predicted = np.empty(
        (len(subset_ids), len(organs)), dtype=f"<U{label_width}"
    )
    nested_subset_id_by_k = {k: (1 << k) - 1 for k in range(1, 6)}
    nested_k_by_subset_id = {
        subset_id: k for k, subset_id in nested_subset_id_by_k.items()
    }
    k_reports: dict[str, Any] = {}
    subset_reports: dict[str, Any] = {}
    for subset_row, (subset_id, selected_mask) in enumerate(
        zip(subset_ids.tolist(), subset_selected_mask)
    ):
        classes, probabilities, predicted = collapse_k5_probabilities(
            crossfit_probabilities, full_classes, selected_mask
        )
        subset_predicted[subset_row] = predicted
        selected_specialists = [
            organ
            for organ, include in zip(SPECIALIST_ORDER, selected_mask)
            if bool(include)
        ]
        subset_reports[str(subset_id)] = {
            "subset_id": int(subset_id),
            "k": int(np.sum(selected_mask)),
            "selected_specialists": selected_specialists,
            "fallback_class": None if np.all(selected_mask) else "other",
            "classes": classes.tolist(),
            "derivation": "collapse common five-organ crossfit probabilities",
            "predicted_class_sha256": _sha256_array(predicted),
        }
        if subset_id in nested_k_by_subset_id:
            k = nested_k_by_subset_id[subset_id]
            prefix = f"k{k}"
            arrays[f"{prefix}_classes"] = classes
            arrays[f"{prefix}_crossfit_probabilities"] = probabilities
            arrays[f"{prefix}_crossfit_predicted_class"] = predicted
            k_reports[prefix] = {
                **subset_reports[str(subset_id)],
                "probability_sha256": _sha256_array(probabilities),
            }
    arrays.update({
        "subset_ids": subset_ids,
        "subset_k": subset_k,
        "subset_selected_mask": subset_selected_mask,
        "subset_crossfit_predicted_class": subset_predicted,
        "k5_crossfit_classes": full_classes,
        "k5_crossfit_probabilities": crossfit_probabilities,
        "outer_inner_k5_probabilities": outer_inner_probabilities,
        "outer_inner_valid_mask": outer_inner_valid_mask,
    })

    full_model, full_weights = _fit_router(
        features, full_labels, groups, seed=args.router_seed
    )
    scaler = full_model.named_steps["standardscaler"]
    classifier = full_model.named_steps["logisticregression"]
    arrays.update({
        "k5_full_classes": classifier.classes_.astype(str),
        "k5_full_scaler_mean": scaler.mean_.astype(np.float64),
        "k5_full_scaler_scale": scaler.scale_.astype(np.float64),
        "k5_full_scaler_var": scaler.var_.astype(np.float64),
        "k5_full_coefficients": classifier.coef_.astype(np.float64),
        "k5_full_intercepts": classifier.intercept_.astype(np.float64),
        "k5_full_n_iter": classifier.n_iter_.astype(np.int64),
    })

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / "organ_k_router.npz"
    _write_deterministic_npz(artifact_path, arrays)
    config = {
        "specialist_order": list(SPECIALIST_ORDER),
        "k_values": list(range(1, len(SPECIALIST_ORDER) + 1)),
        "subset_ids": "integer bit masks 1..31 over specialist_order columns",
        "subset_family": "all 31 nonempty subsets of the five organ specialists",
        "fallback_for_k_below_5": (
            "sum undeployed-organ probability into other; other -> pooled"
        ),
        "subset_router_policy": (
            "fit one common five-organ router per fold and deterministically collapse "
            "its probabilities for every deployed subset"
        ),
        "n_crossfit_folds": N_SPLITS,
        "n_inner_folds_per_outer_fold": N_SPLITS - 1,
        "router_seed": int(args.router_seed),
        "mask_token": float(args.mask_token),
        "normalization": "log1p_tpm",
        "pipeline": ["StandardScaler", "LogisticRegression"],
        "logistic_regression": {
            "C": 1.0,
            "solver": "lbfgs",
            "objective": (
                "one five-class organ model per fit; smaller subsets collapse "
                "the five-class probabilities without refitting"
            ),
            "class_weight": "balanced",
            "max_iter": 2000,
            "sample_weight": "equal connected-study mass within mapped class",
        },
    }
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "complete",
        "experiment": "calibration_only_nested_organ_k_router_freeze",
        "test_accessed": False,
        "test_features_loaded": False,
        "train_features_loaded": False,
        "data_access": {
            "loaded_expression_split": "calibration",
            "n_loaded_expression_rows": int(len(sample_ids)),
            "n_calibration_samples": int(len(sample_ids)),
            "n_calibration_groups": int(len(np.unique(groups))),
            **selection_info,
        },
        "target_hiding": {
            "score_genes_masked_for_every_sample": True,
            "n_score_genes": int(len(score_gene_indices)),
            "score_gene_indices_sha256": _sha256_array(score_gene_indices),
            "masked_feature_sha256": _sha256_array(features),
        },
        "crossfit": {
            "method": (
                "deterministic make_crossfit_folds on connected studies, "
                "stratified by the original five-organ labels"
            ),
            "shared_across_k": True,
            "shared_across_all_subsets": True,
            "every_held_fold_contains_all_five_organs": True,
            "n_splits": N_SPLITS,
            "group_column": args.group_column,
            "fold_for_row_sha256": _sha256_array(fold_for_row),
            "folds": fold_reports,
            "strict_nested_selection": {
                "enabled": True,
                "policy": (
                    "for outer fold j, subset selection may use only four-fold "
                    "inner-OOF K5 predictions trained without outer fold j; the outer "
                    "held score uses a K5 router trained on the other four outer folds"
                ),
                "outer_inner_probabilities_sha256": _sha256_array(
                    outer_inner_probabilities
                ),
                "outer_inner_valid_mask_sha256": _sha256_array(
                    outer_inner_valid_mask
                ),
                "outer_folds": nested_reports,
            },
        },
        "config": config,
        "k_models": k_reports,
        "exhaustive_subsets": {
            "n_subsets": int(len(subset_ids)),
            "id_encoding": (
                "integer bit mask; bit i selects specialist_order[i]"
            ),
            "routing_derivation": (
                "deterministic collapse of common target-hidden K5 probabilities; "
                "no subset-specific router is fit"
            ),
            "subset_ids_sha256": _sha256_array(subset_ids),
            "subset_k_sha256": _sha256_array(subset_k),
            "subset_selected_mask_sha256": _sha256_array(subset_selected_mask),
            "crossfit_predicted_class_sha256": _sha256_array(subset_predicted),
            "models": subset_reports,
        },
        "full_calibration_k5": {
            "classes": classifier.classes_.astype(str).tolist(),
            "n_features": int(classifier.n_features_in_),
            "scaler_mean_sha256": _sha256_array(scaler.mean_),
            "scaler_scale_sha256": _sha256_array(scaler.scale_),
            "coefficient_sha256": _sha256_array(classifier.coef_),
            "intercept_sha256": _sha256_array(classifier.intercept_),
            "sample_weight_sha256": _sha256_array(full_weights),
        },
        "hashes": {
            "expression_parquet_sha256": sha256_file(expression_path),
            "expression_metadata_sha256": sha256_file(expression_metadata_path),
            "source_manifest_sha256": sha256_file(source_manifest_path),
            "partition_manifest_sha256": sha256_file(partition_manifest_path),
            "partition_report_sha256": sha256_file(partition_report_path),
            "axis_definitions_sha256": sha256_file(axis_definitions_path),
            "gene_order_sha256": sha256_lines(genes),
            "calibration_sample_ids_sha256": _sha256_array(sample_ids),
            "calibration_organs_sha256": _sha256_array(organs),
            "calibration_groups_sha256": _sha256_array(groups),
            "resolved_config_sha256": sha256_json(config),
            "router_artifact_sha256": sha256_file(artifact_path),
            "router_source_sha256": sha256_file(Path(__file__)),
        },
        "expression_contract": expression_metadata,
        "artifact": str(artifact_path.resolve()),
    }
    _atomic_json(output_dir / "router_report.json", report)
    (output_dir / "COMPLETE").touch()
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expression-parquet", required=True)
    parser.add_argument("--expression-metadata", required=True)
    parser.add_argument("--source-manifest", required=True)
    parser.add_argument("--axis-definitions", required=True)
    parser.add_argument("--partition-manifest", required=True)
    parser.add_argument("--partition-report", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--router-seed", type=int, default=271828)
    parser.add_argument("--mask-token", type=float, default=-10.0)
    parser.add_argument("--train-split", default="train")
    parser.add_argument("--calibration-split", default="calibration")
    parser.add_argument("--train-filter-column", default="balanced_train")
    parser.add_argument("--source-split-column", default="split")
    parser.add_argument("--sample-id-column", default="sample_id")
    parser.add_argument("--organ-column", default="organ")
    parser.add_argument("--group-column", default="series_group_id")
    return parser


def main() -> None:
    report = freeze(build_parser().parse_args())
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
