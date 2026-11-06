#!/usr/bin/env python3
"""Deterministic, manifest-driven ExpressionPerformer training.

The trainer deliberately has no fallback random split.  Every training and
validation sample must be named by an explicit manifest row and split label.
It is suitable for the small CPU micro-overfit rung as well as fixed-budget
pooled, organ-specialist, and matched-random-shard runs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import tempfile
import time
from collections import Counter
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import torch
import torch.nn.functional as F
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader, Dataset, Sampler


# train_single is a script rather than a package module.  Adding only its own
# directory keeps both ``python core/train_manifest.py`` and test imports safe.
CORE_DIR = Path(__file__).resolve().parent
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))
os.environ.setdefault(
    "MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "nasa-rna-moe-matplotlib")
)
from train_single import ExpressionPerformer  # noqa: E402


ROLES = ("pooled", "organ", "random")
SAMPLING_MODES = ("natural", "organ_balanced", "organ_sample_balanced")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_lines(values: Iterable[Any]) -> str:
    payload = "".join(f"{value}\n" for value in values)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sha256_json(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def stable_seed(seed: int, *labels: Any) -> int:
    payload = ":".join([str(seed), *(str(label) for label in labels)])
    digest = hashlib.sha256(payload.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "little", signed=False)


def deterministic_mask_indices(
    sample_id: str, num_genes: int, mask_ratio: float, seed: int
) -> np.ndarray:
    """Frozen evaluator-compatible ``organ-moe-mask-v1`` sample mask."""
    if num_genes <= 0 or not 0 < mask_ratio < 1:
        raise ValueError("num_genes must be positive and mask_ratio must be in (0, 1)")
    payload = f"organ-moe-mask-v1\0{seed}\0{sample_id}".encode("utf-8")
    sample_seed = int.from_bytes(hashlib.sha256(payload).digest()[:8], "little")
    rng = np.random.default_rng(sample_seed)
    num_mask = max(1, int(num_genes * mask_ratio))
    if num_mask < 1 or num_mask >= num_genes:
        raise ValueError("mask count must be between 1 and num_genes - 1")
    return np.sort(rng.choice(num_genes, num_mask, replace=False).astype(np.int64))


def seed_everything(seed: int, deterministic: bool = True) -> None:
    """Seed every RNG used by this trainer."""
    os.environ["PYTHONHASHSEED"] = str(seed)
    if deterministic:
        os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    random.seed(seed)
    np.random.seed(seed % (2**32))
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    if deterministic:
        torch.use_deterministic_algorithms(True)
        if hasattr(torch.backends, "cudnn"):
            torch.backends.cudnn.benchmark = False
            torch.backends.cudnn.deterministic = True


def seed_data_worker(worker_id: int) -> None:
    worker_seed = torch.initial_seed() % (2**32)
    random.seed(worker_seed)
    np.random.seed(worker_seed)


def read_manifest(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"manifest does not exist: {path}")
    if path.suffix.lower() in {".parquet", ".pq"}:
        frame = pd.read_parquet(path)
    elif path.suffix.lower() in {".csv", ".tsv"}:
        frame = pd.read_csv(path, sep="\t" if path.suffix.lower() == ".tsv" else ",")
    else:
        raise ValueError("manifest must be CSV, TSV, or Parquet")
    return frame


@dataclass(frozen=True)
class ManifestSelection:
    train: pd.DataFrame
    validation: pd.DataFrame
    selector: dict[str, str]


def _require_text_column(frame: pd.DataFrame, column: str) -> None:
    if column not in frame.columns:
        raise ValueError(f"manifest is missing required column {column!r}")
    if frame[column].isna().any():
        raise ValueError(f"manifest column {column!r} contains missing values")


def select_manifest_rows(
    manifest: pd.DataFrame,
    *,
    role: str,
    train_split: str,
    validation_split: str,
    organ: str | None = None,
    random_shard: str | None = None,
    sample_id_column: str = "sample_id",
    split_column: str = "split",
    organ_column: str = "organ",
    group_column: str = "series_group_id",
    random_shard_column: str = "random_shard",
    train_filter_column: str | None = None,
) -> ManifestSelection:
    """Select exact role/split rows; never infer or generate a split."""
    if role not in ROLES:
        raise ValueError(f"role must be one of {ROLES}, got {role!r}")
    if str(train_split) == str(validation_split):
        raise ValueError("train and validation split labels must differ")

    frame = manifest.copy()
    for column in (sample_id_column, split_column):
        _require_text_column(frame, column)
        frame[column] = frame[column].astype(str)
    if frame[sample_id_column].duplicated().any():
        duplicate = frame.loc[frame[sample_id_column].duplicated(), sample_id_column].iloc[0]
        raise ValueError(f"manifest contains duplicate sample ID {duplicate!r}")

    selector: dict[str, str] = {"role": role}
    train_role_mask = pd.Series(True, index=frame.index)
    validation_role_mask = pd.Series(True, index=frame.index)
    if role == "pooled":
        if organ is not None or random_shard is not None:
            raise ValueError("pooled role does not accept an organ or random shard selector")
    elif role == "organ":
        if not organ:
            raise ValueError("organ role requires --organ")
        _require_text_column(frame, organ_column)
        train_role_mask = frame[organ_column].astype(str).eq(str(organ))
        validation_role_mask = train_role_mask
        selector["organ"] = str(organ)
    else:
        if random_shard is None:
            raise ValueError("random role requires --random-shard")
        if random_shard_column not in frame.columns:
            raise ValueError(
                f"manifest is missing required column {random_shard_column!r}"
            )
        # Unselected natural-frequency training rows may intentionally have no
        # shard.  They are excluded by the explicit shard equality below.
        shard_values = frame[random_shard_column].fillna("").astype(str)
        train_role_mask = shard_values.eq(str(random_shard))
        validation_role_mask = train_role_mask
        selector["random_shard"] = str(random_shard)
        selector["random_shard_column"] = random_shard_column

    train_filter_mask = pd.Series(True, index=frame.index)
    if train_filter_column is not None:
        if train_filter_column not in frame.columns:
            raise ValueError(
                f"manifest is missing train filter column {train_filter_column!r}"
            )
        values = frame[train_filter_column]
        if pd.api.types.is_bool_dtype(values.dtype):
            train_filter_mask = values.fillna(False).astype(bool)
        else:
            normalized = values.fillna("false").astype(str).str.strip().str.lower()
            allowed = {"true", "false", "1", "0", "yes", "no", "y", "n"}
            invalid = sorted(set(normalized) - allowed)
            if invalid:
                raise ValueError(
                    f"train filter column {train_filter_column!r} has invalid values: {invalid[:3]}"
                )
            train_filter_mask = normalized.isin({"true", "1", "yes", "y"})
        selector["train_filter_column"] = train_filter_column
        selector["train_filter_value"] = "truthy"

    train = frame.loc[
        train_role_mask
        & train_filter_mask
        & frame[split_column].eq(str(train_split))
    ].copy()
    validation = frame.loc[
        validation_role_mask & frame[split_column].eq(str(validation_split))
    ].copy()
    if train.empty:
        raise ValueError(f"role selection has no rows in train split {train_split!r}")
    if validation.empty:
        raise ValueError(
            f"role selection has no rows in validation split {validation_split!r}"
        )

    train = train.sort_values(sample_id_column).reset_index(drop=True)
    validation = validation.sort_values(sample_id_column).reset_index(drop=True)
    train_ids = set(train[sample_id_column])
    validation_ids = set(validation[sample_id_column])
    overlap = train_ids & validation_ids
    if overlap:
        raise ValueError(f"train/validation sample overlap: {sorted(overlap)[:3]}")

    if group_column in frame.columns:
        _require_text_column(train, group_column)
        _require_text_column(validation, group_column)
        train_groups = set(train[group_column].astype(str))
        validation_groups = set(validation[group_column].astype(str))
        group_overlap = train_groups & validation_groups
        if group_overlap:
            raise ValueError(
                "connected study groups cross train/validation splits: "
                f"{sorted(group_overlap)[:3]}"
            )
    return ManifestSelection(train=train, validation=validation, selector=selector)


@dataclass(frozen=True)
class ExpressionInfo:
    sample_id_column: str
    sample_ids: tuple[str, ...]
    gene_columns: tuple[str, ...]


def validate_expression_metadata(
    expression_path: str | Path,
    gene_columns: Sequence[str],
    *,
    metadata_path: str | Path | None = None,
    assume_expression_space: str | None = None,
) -> dict[str, Any]:
    """Require an extractor declaration that the input is unlogged TPM."""
    expression_path = Path(expression_path)
    report_path = (
        Path(metadata_path)
        if metadata_path is not None
        else expression_path.parent / "extraction_report.json"
    )
    expected_gene_hash = sha256_lines(gene_columns)
    if not report_path.exists():
        if assume_expression_space != "tpm":
            raise FileNotFoundError(
                f"expression metadata is required at {report_path}; for a synthetic test "
                "only, pass --assume-expression-space tpm"
            )
        return {
            "metadata_path": None,
            "metadata_sha256": None,
            "expression_space": "tpm",
            "model_value_space": "log1p_tpm",
            "space_source": "explicit_assumption",
            "gene_order_sha256": expected_gene_hash,
        }

    report = json.loads(report_path.read_text())
    if report.get("status") not in (None, "complete"):
        raise ValueError(
            f"expression metadata {report_path} has non-complete status {report.get('status')!r}"
        )
    output = report.get("output") if isinstance(report.get("output"), dict) else {}
    expression_space = report.get("expression_space", output.get("expression_space"))
    if expression_space is None:
        raise ValueError(
            f"expression metadata {report_path} does not declare expression_space"
        )
    if str(expression_space).lower() != "tpm":
        raise ValueError(
            "manifest training requires unlogged TPM input, but expression metadata "
            f"declares {expression_space!r}"
        )
    declared_gene_hash = report.get(
        "gene_order_sha256", output.get("gene_order_sha256")
    )
    if declared_gene_hash is not None and declared_gene_hash != expected_gene_hash:
        raise ValueError(
            "expression metadata gene_order_sha256 does not match parquet column order"
        )
    return {
        "metadata_path": str(report_path.resolve()),
        "metadata_sha256": sha256_file(report_path),
        "expression_space": "tpm",
        "model_value_space": "log1p_tpm",
        "space_source": "extractor_metadata",
        "gene_order_sha256": expected_gene_hash,
    }


def inspect_expression_parquet(
    path: str | Path, sample_id_column: str = "sample_id"
) -> tuple[pq.ParquetFile, ExpressionInfo]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"expression parquet does not exist: {path}")
    parquet = pq.ParquetFile(path)
    names = parquet.schema_arrow.names
    if sample_id_column not in names:
        raise ValueError(
            f"expression parquet must contain explicit {sample_id_column!r} column"
        )
    gene_columns = [name for name in names if name != sample_id_column]
    if not gene_columns:
        raise ValueError("expression parquet has no gene columns")
    if len(set(gene_columns)) != len(gene_columns):
        raise ValueError("expression parquet contains duplicate gene columns")
    gene_set = set(gene_columns)
    for field in parquet.schema_arrow:
        if field.name not in gene_set:
            continue
        column = field.name
        field_type = field.type
        if not (pa.types.is_integer(field_type) or pa.types.is_floating(field_type)):
            raise ValueError(f"gene column {column!r} is not numeric ({field_type})")

    id_values = parquet.read(columns=[sample_id_column]).column(0).to_pylist()
    if any(value is None for value in id_values):
        raise ValueError("expression parquet contains a missing sample ID")
    sample_ids = tuple(str(value) for value in id_values)
    if len(set(sample_ids)) != len(sample_ids):
        duplicate = next(value for value, count in Counter(sample_ids).items() if count > 1)
        raise ValueError(f"expression parquet contains duplicate sample ID {duplicate!r}")
    return parquet, ExpressionInfo(
        sample_id_column=sample_id_column,
        sample_ids=sample_ids,
        gene_columns=tuple(gene_columns),
    )


def load_expression_rows(
    path: str | Path,
    wanted_sample_ids: Sequence[str],
    sample_id_column: str = "sample_id",
) -> tuple[np.ndarray, ExpressionInfo]:
    """Load exact requested rows in requested order and preserve gene order."""
    parquet, info = inspect_expression_parquet(path, sample_id_column)
    wanted = [str(value) for value in wanted_sample_ids]
    if len(set(wanted)) != len(wanted):
        raise ValueError("requested expression sample IDs contain duplicates")
    row_for_id = {sample_id: row for row, sample_id in enumerate(info.sample_ids)}
    missing = [sample_id for sample_id in wanted if sample_id not in row_for_id]
    if missing:
        raise ValueError(
            f"expression parquet is missing {len(missing)} requested sample IDs: {missing[:3]}"
        )

    starts = [0]
    for row_group in range(parquet.metadata.num_row_groups):
        starts.append(starts[-1] + parquet.metadata.row_group(row_group).num_rows)
    requested_rows = [row_for_id[sample_id] for sample_id in wanted]
    if not wanted:
        return np.empty((0, len(info.gene_columns)), dtype=np.float32), info
    boundaries = np.asarray(starts, dtype=np.int64)
    row_groups = sorted(
        {
            int(np.searchsorted(boundaries, global_row, side="right") - 1)
            for global_row in requested_rows
        }
    )
    # Reading each of ~15k columns separately for every selected row group is
    # pathologically slow. Arrow can decode the selected row groups in parallel,
    # and pandas consolidates the homogeneous gene columns in native code.
    table = parquet.read_row_groups(
        row_groups,
        columns=[sample_id_column, *info.gene_columns],
        use_threads=True,
    )
    loaded_ids = [
        str(value)
        for value in table.column(sample_id_column).combine_chunks().to_pylist()
    ]
    loaded_row = {sample_id: index for index, sample_id in enumerate(loaded_ids)}
    missing_loaded = [sample_id for sample_id in wanted if sample_id not in loaded_row]
    if missing_loaded:
        raise RuntimeError(
            "selected parquet row groups did not contain requested sample IDs: "
            f"{missing_loaded[:3]}"
        )
    gene_frame = table.select(list(info.gene_columns)).to_pandas()
    all_values = gene_frame.to_numpy(dtype=np.float32, copy=False)
    order = np.asarray([loaded_row[sample_id] for sample_id in wanted], dtype=np.int64)
    output = np.ascontiguousarray(all_values[order], dtype=np.float32)
    if not np.isfinite(output).all():
        raise ValueError("selected expression matrix contains NaN or infinite values")
    return output, info


class DeterministicMaskedExpressionDataset(Dataset):
    """Expression rows with masks keyed by seed, sample ID, and draw number."""

    def __init__(
        self,
        expression: np.ndarray,
        sample_ids: Sequence[str],
        *,
        normalization: str,
        mask_ratio: float,
        mask_token: float,
        seed: int,
        phase: str,
        fixed_masks: bool,
    ):
        values = np.asarray(expression, dtype=np.float32)
        if values.ndim != 2 or values.shape[0] != len(sample_ids):
            raise ValueError("expression must be a 2D matrix aligned to sample_ids")
        if normalization == "log1p_tpm":
            if np.any(values < 0):
                raise ValueError("TPM expression must be nonnegative before log1p")
            values = np.log1p(values).astype(np.float32, copy=False)
        elif normalization not in {"tpm", "raw_counts"}:
            raise ValueError(f"unsupported normalization {normalization!r}")
        if not 0 < mask_ratio <= 1:
            raise ValueError("mask_ratio must be in (0, 1]")
        self.expression = values
        self.sample_ids = tuple(str(value) for value in sample_ids)
        self.mask_token = float(mask_token)
        self.mask_ratio = float(mask_ratio)
        self.seed = int(seed)
        self.phase = str(phase)
        self.fixed_masks = bool(fixed_masks)
        self.num_genes = int(values.shape[1])
        self.num_mask = max(1, int(self.num_genes * mask_ratio))

    def __len__(self) -> int:
        return len(self.sample_ids)

    def mask_indices(self, index: int, draw_number: int = 0) -> np.ndarray:
        sample_id = self.sample_ids[index]
        if self.fixed_masks:
            return deterministic_mask_indices(
                sample_id, self.num_genes, self.mask_ratio, self.seed
            )
        draw_key = 0 if self.fixed_masks else int(draw_number)
        rng = np.random.default_rng(
            stable_seed(self.seed, "mask", self.phase, sample_id, draw_key)
        )
        return np.sort(
            rng.choice(self.num_genes, self.num_mask, replace=False).astype(np.int64)
        )

    def __getitem__(self, key):
        if isinstance(key, (tuple, list)):
            index, draw_number = int(key[0]), int(key[1])
        else:
            index, draw_number = int(key), 0
        truth = self.expression[index]
        mask_indices = self.mask_indices(index, draw_number)
        masked = truth.copy()
        masked[mask_indices] = self.mask_token
        return (
            torch.from_numpy(masked),
            torch.from_numpy(truth.copy()),
            torch.from_numpy(mask_indices),
        )


class _ShuffledCycle:
    def __init__(self, values: Sequence[Any], rng: np.random.Generator):
        if not values:
            raise ValueError("cannot cycle over an empty sequence")
        self.values = list(values)
        self.rng = rng
        self.order: list[Any] = []
        self.position = 0

    def next(self):
        if self.position >= len(self.order):
            order = list(self.values)
            self.rng.shuffle(order)
            self.order = order
            self.position = 0
        value = self.order[self.position]
        self.position += 1
        return value


class DeterministicBudgetBatchSampler(Sampler[list[tuple[int, int]]]):
    """Precompute exactly ``max_updates`` deterministic, auditable batches."""

    def __init__(
        self,
        sample_ids: Sequence[str],
        *,
        batch_size: int,
        max_updates: int,
        seed: int,
        sampling_mode: str = "natural",
        organs: Sequence[str] | None = None,
        group_ids: Sequence[str] | None = None,
    ):
        if not sample_ids:
            raise ValueError("training selection is empty")
        if batch_size <= 0 or max_updates <= 0:
            raise ValueError("batch_size and max_updates must be positive")
        if sampling_mode not in SAMPLING_MODES:
            raise ValueError(f"sampling_mode must be one of {SAMPLING_MODES}")
        self.sample_ids = tuple(str(value) for value in sample_ids)
        self.batch_size = int(batch_size)
        self.max_updates = int(max_updates)
        self.seed = int(seed)
        self.sampling_mode = sampling_mode
        self.organs = None if organs is None else tuple(str(value) for value in organs)
        self.group_ids = None if group_ids is None else tuple(str(value) for value in group_ids)
        if sampling_mode in {"organ_balanced", "organ_sample_balanced"}:
            if self.organs is None or self.group_ids is None:
                raise ValueError(
                    f"{sampling_mode} sampling requires organ and group labels"
                )
            if len(self.organs) != len(self.sample_ids) or len(self.group_ids) != len(self.sample_ids):
                raise ValueError("organ/group labels must align with sample IDs")
        self.flat_indices = tuple(self._build_indices())
        self.batches = tuple(
            tuple(
                (sample_index, draw_number)
                for draw_number, sample_index in enumerate(
                    self.flat_indices[start : start + self.batch_size], start=start
                )
            )
            for start in range(0, len(self.flat_indices), self.batch_size)
        )
        if len(self.batches) != self.max_updates:
            raise AssertionError("sampler did not create the requested update budget")

    def _build_indices(self) -> list[int]:
        total_draws = self.batch_size * self.max_updates
        rng = np.random.default_rng(self.seed)
        if self.sampling_mode == "natural":
            result: list[int] = []
            while len(result) < total_draws:
                result.extend(rng.permutation(len(self.sample_ids)).tolist())
            return result[:total_draws]

        assert self.organs is not None and self.group_ids is not None
        if self.sampling_mode == "organ_sample_balanced":
            organ_to_indices: dict[str, list[int]] = {}
            for index, organ in enumerate(self.organs):
                organ_to_indices.setdefault(organ, []).append(index)
            organ_cycle = _ShuffledCycle(sorted(organ_to_indices), rng)
            sample_cycles = {
                organ: _ShuffledCycle(indices, rng)
                for organ, indices in organ_to_indices.items()
            }
            result = []
            for _ in range(total_draws):
                organ = organ_cycle.next()
                result.append(int(sample_cycles[organ].next()))
            return result

        organ_to_groups: dict[str, dict[str, list[int]]] = {}
        for index, (organ, group) in enumerate(zip(self.organs, self.group_ids)):
            organ_to_groups.setdefault(organ, {}).setdefault(group, []).append(index)
        organ_cycle = _ShuffledCycle(sorted(organ_to_groups), rng)
        group_cycles = {
            organ: _ShuffledCycle(sorted(groups), rng)
            for organ, groups in organ_to_groups.items()
        }
        sample_cycles = {
            (organ, group): _ShuffledCycle(indices, rng)
            for organ, groups in organ_to_groups.items()
            for group, indices in groups.items()
        }
        result = []
        for _ in range(total_draws):
            organ = organ_cycle.next()
            group = group_cycles[organ].next()
            result.append(int(sample_cycles[(organ, group)].next()))
        return result

    def __iter__(self):
        yield from self.batches

    def __len__(self) -> int:
        return self.max_updates


def build_exposure_frame(
    selected_train: pd.DataFrame,
    sampler: DeterministicBudgetBatchSampler,
    *,
    sample_id_column: str = "sample_id",
    organ_column: str = "organ",
    group_column: str = "series_group_id",
) -> pd.DataFrame:
    counts = np.bincount(
        np.asarray(sampler.flat_indices, dtype=np.int64), minlength=len(selected_train)
    )
    output = pd.DataFrame({
        "sample_id": selected_train[sample_id_column].astype(str).to_numpy(),
        "exposure_count": counts.astype(np.int64),
    })
    if organ_column in selected_train.columns:
        output["organ"] = selected_train[organ_column].astype(str).to_numpy()
    if group_column in selected_train.columns:
        output["series_group_id"] = selected_train[group_column].astype(str).to_numpy()
    return output


def summarize_exposures(exposures: pd.DataFrame) -> dict[str, Any]:
    counts = exposures["exposure_count"].to_numpy(dtype=np.int64)
    summary: dict[str, Any] = {
        "total_exposures": int(counts.sum()),
        "selected_unique_samples": int(len(counts)),
        "effective_unique_samples": int((counts > 0).sum()),
        "zero_exposure_samples": int((counts == 0).sum()),
        "repeated_exposures": int(np.maximum(counts - 1, 0).sum()),
        "minimum_sample_exposures": int(counts.min()),
        "maximum_sample_exposures": int(counts.max()),
    }
    if "organ" in exposures.columns:
        per_organ = []
        for organ, subset in exposures.groupby("organ", sort=True):
            organ_counts = subset["exposure_count"].to_numpy(dtype=np.int64)
            per_organ.append({
                "organ": str(organ),
                "total_exposures": int(organ_counts.sum()),
                "selected_unique_samples": int(len(organ_counts)),
                "effective_unique_samples": int((organ_counts > 0).sum()),
                "repeated_exposures": int(np.maximum(organ_counts - 1, 0).sum()),
            })
        summary["per_organ"] = per_organ
    if "series_group_id" in exposures.columns:
        group_totals = (
            exposures.groupby([column for column in ("organ", "series_group_id") if column in exposures])[
                "exposure_count"
            ]
            .sum()
            .reset_index()
        )
        summary["n_selected_groups"] = int(len(group_totals))
        summary["group_exposure_minimum"] = int(group_totals["exposure_count"].min())
        summary["group_exposure_maximum"] = int(group_totals["exposure_count"].max())
    return summary


def _masked_mse(prediction: torch.Tensor, truth: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    return F.mse_loss(prediction.gather(1, mask), truth.gather(1, mask))


def balanced_validation_weights(
    frame: pd.DataFrame,
    *,
    organ_column: str = "organ",
    group_column: str = "series_group_id",
) -> np.ndarray:
    """Equalize organs, then studies within organ, then samples within study."""
    for column in (organ_column, group_column):
        _require_text_column(frame, column)
    organs = frame[organ_column].astype(str).to_numpy()
    groups = frame[group_column].astype(str).to_numpy()
    labels = sorted(set(organs))
    if not labels:
        raise ValueError("validation frame is empty")
    weights = np.zeros(len(frame), dtype=np.float64)
    for organ in labels:
        organ_mask = organs == organ
        organ_groups = sorted(set(groups[organ_mask]))
        for group in organ_groups:
            rows = organ_mask & (groups == group)
            weights[rows] = 1.0 / (len(labels) * len(organ_groups) * int(rows.sum()))
    if not np.isclose(weights.sum(), 1.0):
        raise AssertionError("balanced validation weights do not sum to one")
    return weights


def evaluate_model(
    model: torch.nn.Module,
    loader: DataLoader,
    device: torch.device,
    *,
    validation_seed: int,
    sample_weights: np.ndarray | None = None,
) -> float:
    was_training = model.training
    model.eval()
    weighted_error = 0.0
    n_samples = 0
    if sample_weights is not None:
        sample_weights = np.asarray(sample_weights, dtype=np.float64)
        if sample_weights.shape != (len(loader.dataset),):
            raise ValueError("validation sample weights must align to the dataset")
        if np.any(sample_weights < 0) or not np.isclose(sample_weights.sum(), 1.0):
            raise ValueError("validation sample weights must be nonnegative and sum to one")
    cuda_devices = []
    if device.type == "cuda":
        cuda_devices = [device.index if device.index is not None else torch.cuda.current_device()]
    rng_context = torch.random.fork_rng(devices=cuda_devices, enabled=True)
    with rng_context:
        torch.manual_seed(validation_seed)
        if device.type == "cuda":
            torch.cuda.manual_seed_all(validation_seed)
        with torch.no_grad():
            for masked, truth, mask in loader:
                masked = masked.to(device)
                truth = truth.to(device)
                mask = mask.to(device)
                prediction = model(masked)
                error = prediction.gather(1, mask) - truth.gather(1, mask)
                row_mse = error.square().mean(dim=1).detach().cpu().numpy()
                if sample_weights is None:
                    weighted_error += float(row_mse.sum())
                else:
                    batch_weights = sample_weights[n_samples:n_samples + len(row_mse)]
                    weighted_error += float(np.dot(row_mse, batch_weights))
                n_samples += len(row_mse)
    model.train(was_training)
    if n_samples == 0:
        raise ValueError("validation loader produced no masked values")
    if sample_weights is not None and n_samples != len(sample_weights):
        raise AssertionError("validation loader order/count differs from sample weights")
    return weighted_error if sample_weights is not None else weighted_error / n_samples


def export_split_predictions(
    model: torch.nn.Module,
    *,
    expression_path: str | Path,
    expression_info: ExpressionInfo,
    manifest: pd.DataFrame,
    split: str | Sequence[str],
    split_column: str,
    sample_id_column: str,
    normalization: str,
    mask_ratio: float,
    mask_token: float,
    mask_seed: int,
    batch_size: int,
    num_workers: int,
    device: torch.device,
    output_path: str | Path,
    checkpoint_path: str | Path,
    model_role: str,
    model_selector: dict[str, str],
    training_seed: int,
    train_sample_ids_sha256: str,
    expression_file_sha256: str,
) -> dict[str, Any]:
    """Export full-gene predictions under frozen evaluator-compatible masks."""
    _require_text_column(manifest, sample_id_column)
    _require_text_column(manifest, split_column)
    splits = [str(split)] if isinstance(split, str) else [str(value) for value in split]
    if not splits or len(set(splits)) != len(splits):
        raise ValueError("prediction export splits must be nonempty and unique")
    rows = manifest.loc[manifest[split_column].astype(str).isin(splits)].copy()
    if rows.empty:
        raise ValueError(f"prediction export splits {splits!r} are empty")
    if rows[sample_id_column].duplicated().any():
        raise ValueError(f"prediction export splits {splits!r} have duplicate sample IDs")
    rows = rows.sort_values(sample_id_column).reset_index(drop=True)
    sample_ids = rows[sample_id_column].astype(str).tolist()
    expression, loaded_info = load_expression_rows(
        expression_path, sample_ids, sample_id_column=sample_id_column
    )
    if loaded_info.gene_columns != expression_info.gene_columns:
        raise AssertionError("gene order changed while loading prediction export")
    dataset = DeterministicMaskedExpressionDataset(
        expression,
        sample_ids,
        normalization=normalization,
        mask_ratio=mask_ratio,
        mask_token=mask_token,
        seed=mask_seed,
        phase=f"export:{','.join(splits)}",
        fixed_masks=True,
    )
    loader_generator = torch.Generator().manual_seed(
        stable_seed(mask_seed, "export_loader", *splits) % (2**63 - 1)
    )
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        worker_init_fn=seed_data_worker,
        generator=loader_generator,
    )
    predictions: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    masks: list[np.ndarray] = []
    model.eval()
    with torch.no_grad():
        for masked, truth, mask in loader:
            prediction = model(masked.to(device)).detach().cpu().numpy().astype(np.float32)
            predictions.append(prediction)
            targets.append(truth.numpy().astype(np.float32, copy=False))
            masks.append(mask.numpy().astype(np.int64, copy=False))
    prediction_matrix = np.concatenate(predictions, axis=0)
    target_matrix = np.concatenate(targets, axis=0)
    mask_matrix = np.concatenate(masks, axis=0)
    output_path = Path(output_path)
    temporary = output_path.with_name(output_path.name + ".tmp.npz")
    np.savez_compressed(
        temporary,
        sample_ids=np.asarray(sample_ids, dtype=str),
        genes=np.asarray(expression_info.gene_columns, dtype=str),
        predictions=prediction_matrix,
        targets=target_matrix,
        mask_indices=mask_matrix,
        value_space=np.asarray("log1p_tpm"),
        input_expression_space=np.asarray("tpm"),
        mask_algorithm=np.asarray("organ-moe-mask-v1"),
        mask_seed=np.asarray(mask_seed, dtype=np.int64),
        mask_ratio=np.asarray(mask_ratio, dtype=np.float64),
        mask_token=np.asarray(mask_token, dtype=np.float64),
        splits=np.asarray(splits, dtype=str),
        checkpoint_sha256=np.asarray(sha256_file(checkpoint_path)),
        model_role=np.asarray(model_role),
        model_selector_json=np.asarray(json.dumps(model_selector, sort_keys=True)),
        training_seed=np.asarray(training_seed, dtype=np.int64),
        train_sample_ids_sha256=np.asarray(train_sample_ids_sha256),
        expression_file_sha256=np.asarray(expression_file_sha256),
        sample_ids_sha256=np.asarray(sha256_lines(sample_ids)),
        gene_order_sha256=np.asarray(sha256_lines(expression_info.gene_columns)),
    )
    os.replace(temporary, output_path)
    return {
        "splits": splits,
        "path": str(output_path.resolve()),
        "sha256": sha256_file(output_path),
        "n_samples": len(sample_ids),
        "sample_ids_sha256": sha256_lines(sample_ids),
        "mask_indices_sha256": hashlib.sha256(mask_matrix.tobytes()).hexdigest(),
        "value_space": "log1p_tpm",
        "mask_algorithm": "organ-moe-mask-v1",
        "mask_seed": int(mask_seed),
        "model_role": model_role,
        "model_selector": model_selector,
        "training_seed": int(training_seed),
        "train_sample_ids_sha256": train_sample_ids_sha256,
        "expression_file_sha256": expression_file_sha256,
    }


def _json_ready(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def _write_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(_json_ready(value), indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _save_checkpoint(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(payload, temporary)
    os.replace(temporary, path)


def _resolve_device(requested: str) -> torch.device:
    if requested == "auto":
        return torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    device = torch.device(requested)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError(f"CUDA device requested but CUDA is unavailable: {requested}")
    return device


def _getattr(args: argparse.Namespace, name: str, default: Any) -> Any:
    return getattr(args, name, default)


def run_training(args: argparse.Namespace) -> dict[str, Any]:
    """Run one exact-ID, exact-update-budget training job."""
    expression_path = Path(args.expression_parquet)
    manifest_path = Path(args.manifest)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output_dir}")
    if args.normalization != "log1p_tpm":
        raise ValueError(
            "manifest training requires exactly one TPM -> log1p transform; "
            "--normalization must be log1p_tpm"
        )
    if not bool(_getattr(args, "deterministic", True)):
        raise ValueError("manifest training does not permit nondeterministic execution")

    seed = int(args.seed)
    validation_mask_seed = int(_getattr(args, "validation_mask_seed", 42))
    seed_everything(seed, deterministic=True)
    device = _resolve_device(_getattr(args, "device", "auto"))
    torch_threads = int(_getattr(args, "torch_threads", 0))
    if device.type == "cpu" and torch_threads > 0:
        torch.set_num_threads(torch_threads)

    sample_id_column = _getattr(args, "sample_id_column", "sample_id")
    split_column = _getattr(args, "split_column", "split")
    organ_column = _getattr(args, "organ_column", "organ")
    group_column = _getattr(args, "group_column", "series_group_id")
    random_shard_column = _getattr(args, "random_shard_column", "random_shard")
    train_filter_column = _getattr(args, "train_filter_column", None)
    manifest = read_manifest(manifest_path)
    selection = select_manifest_rows(
        manifest,
        role=args.role,
        train_split=args.train_split,
        validation_split=args.validation_split,
        organ=_getattr(args, "organ", None),
        random_shard=_getattr(args, "random_shard", None),
        sample_id_column=sample_id_column,
        split_column=split_column,
        organ_column=organ_column,
        group_column=group_column,
        random_shard_column=random_shard_column,
        train_filter_column=train_filter_column,
    )
    if args.sampling_mode == "organ_balanced":
        for column in (organ_column, group_column):
            _require_text_column(selection.train, column)

    train_ids = selection.train[sample_id_column].astype(str).tolist()
    validation_ids = selection.validation[sample_id_column].astype(str).tolist()
    all_selected_ids = train_ids + validation_ids
    expression, expression_info = load_expression_rows(
        expression_path, all_selected_ids, sample_id_column=sample_id_column
    )
    expression_space = validate_expression_metadata(
        expression_path,
        expression_info.gene_columns,
        metadata_path=_getattr(args, "expression_metadata", None),
        assume_expression_space=_getattr(args, "assume_expression_space", None),
    )
    train_expression = expression[: len(train_ids)]
    validation_expression = expression[len(train_ids) :]

    train_dataset = DeterministicMaskedExpressionDataset(
        train_expression,
        train_ids,
        normalization=args.normalization,
        mask_ratio=args.mask_ratio,
        mask_token=args.mask_token,
        seed=seed,
        phase="train",
        fixed_masks=False,
    )
    validation_dataset = DeterministicMaskedExpressionDataset(
        validation_expression,
        validation_ids,
        normalization=args.normalization,
        mask_ratio=args.mask_ratio,
        mask_token=args.mask_token,
        seed=validation_mask_seed,
        phase="validation",
        fixed_masks=True,
    )
    sampler_seed = stable_seed(seed, "sampler")
    sampler = DeterministicBudgetBatchSampler(
        train_ids,
        batch_size=args.batch_size,
        max_updates=args.max_updates,
        seed=sampler_seed,
        sampling_mode=args.sampling_mode,
        organs=(
            selection.train[organ_column].astype(str).tolist()
            if args.sampling_mode == "organ_balanced"
            else None
        ),
        group_ids=(
            selection.train[group_column].astype(str).tolist()
            if args.sampling_mode == "organ_balanced"
            else None
        ),
    )
    loader_generator = torch.Generator()
    loader_generator.manual_seed(stable_seed(seed, "data_loader") % (2**63 - 1))
    train_loader = DataLoader(
        train_dataset,
        batch_sampler=sampler,
        num_workers=args.num_workers,
        worker_init_fn=seed_data_worker,
        generator=loader_generator,
    )
    validation_loader = DataLoader(
        validation_dataset,
        batch_size=_getattr(args, "validation_batch_size", args.batch_size),
        shuffle=False,
        num_workers=args.num_workers,
        worker_init_fn=seed_data_worker,
        generator=loader_generator,
    )
    validation_weights = balanced_validation_weights(
        selection.validation,
        organ_column=organ_column,
        group_column=group_column,
    )

    exposures = build_exposure_frame(
        selection.train,
        sampler,
        sample_id_column=sample_id_column,
        organ_column=organ_column,
        group_column=group_column,
    )
    exposure_path = output_dir / "sampling_exposures.csv"
    exposures.to_csv(exposure_path, index=False)
    exposure_summary = summarize_exposures(exposures)

    ffn_dim = int(args.ffn_dim) if int(args.ffn_dim) > 0 else int(args.hidden_dim) * 4
    if args.hidden_dim % args.num_heads != 0:
        raise ValueError("hidden_dim must be divisible by num_heads")
    model_config = {
        "num_genes": len(expression_info.gene_columns),
        "hidden_dim": int(args.hidden_dim),
        "ffn_dim": ffn_dim,
        "num_heads": int(args.num_heads),
        "num_layers": int(args.num_layers),
        "ree_base": float(args.ree_base),
        "feature_type": args.feature_type,
        "compute_type": args.compute_type,
        "gradient_checkpointing": bool(args.gradient_checkpointing),
        "mask_ratio": float(args.mask_ratio),
        "mask_token": float(args.mask_token),
        "normalization": args.normalization,
        "input_expression_space": "tpm",
        "model_value_space": "log1p_tpm",
        "expression_parquet": str(expression_path),
        "gene_list": list(expression_info.gene_columns),
    }
    training_config = {
        "learning_rate": float(args.learning_rate),
        "weight_decay": float(args.weight_decay),
        "batch_size": int(args.batch_size),
        "max_updates": int(args.max_updates),
        "validation_interval": int(args.validation_interval),
        "sampling_mode": args.sampling_mode,
        "seed": seed,
        "device": str(device),
    }
    selected_manifest_records = [
        "|".join(
            str(row.get(column, ""))
            for column in (sample_id_column, organ_column, group_column, split_column)
        )
        for row in pd.concat([selection.train, selection.validation]).to_dict("records")
    ]
    run_metadata: dict[str, Any] = {
        "schema_version": 1,
        "status": "running",
        "role": args.role,
        "selector": selection.selector,
        "splits": {
            "train": str(args.train_split),
            "validation": str(args.validation_split),
        },
        "train_filter": {
            "column": train_filter_column,
            "applied_to": "train_only" if train_filter_column else None,
            "selected_sample_ids_sha256": sha256_lines(train_ids),
        },
        "counts": {
            "train_samples": len(train_ids),
            "validation_samples": len(validation_ids),
            "genes": len(expression_info.gene_columns),
        },
        "hashes": {
            "expression_file_sha256": sha256_file(expression_path),
            "manifest_file_sha256": sha256_file(manifest_path),
            "expression_all_sample_ids_sha256": sha256_lines(expression_info.sample_ids),
            "train_sample_ids_sha256": sha256_lines(train_ids),
            "train_filter_sample_ids_sha256": sha256_lines(train_ids),
            "validation_sample_ids_sha256": sha256_lines(validation_ids),
            "selected_manifest_rows_sha256": sha256_lines(selected_manifest_records),
            "gene_order_sha256": sha256_lines(expression_info.gene_columns),
            "sampling_exposures_sha256": sha256_file(exposure_path),
        },
        "rng": {
            "seed": seed,
            "sampler_seed": sampler_seed,
            "data_loader_seed": stable_seed(seed, "data_loader"),
            "training_mask_seed": seed,
            "fixed_validation_mask_seed": validation_mask_seed,
            "validation_model_rng_seed": stable_seed(
                validation_mask_seed, "validation_model_rng"
            ),
            "python_numpy_torch_seeded": True,
            "deterministic_algorithms": True,
        },
        "sampling": {
            "mode": args.sampling_mode,
            "fixed_update_budget": int(args.max_updates),
            "batch_size": int(args.batch_size),
            "selected_id_union_preserved": True,
            **exposure_summary,
        },
        "checkpoint_selection": {
            "metric": "masked_mse",
            "weighting": "equal_organ_equal_connected_study_equal_sample_within_study",
            "validation_weight_sha256": hashlib.sha256(
                np.ascontiguousarray(validation_weights, dtype="<f8").tobytes()
            ).hexdigest(),
        },
        "model": model_config,
        "training": training_config,
        "paths": {
            "expression_parquet": str(expression_path.resolve()),
            "manifest": str(manifest_path.resolve()),
            "output_dir": str(output_dir.resolve()),
        },
        "expression_space": expression_space,
    }
    run_metadata["hashes"]["model_config_sha256"] = sha256_json(model_config)
    run_metadata["hashes"]["training_config_sha256"] = sha256_json(training_config)
    _write_json(output_dir / "run_metadata.json", run_metadata)

    model = ExpressionPerformer(
        num_genes=model_config["num_genes"],
        hidden_dim=model_config["hidden_dim"],
        n_heads=model_config["num_heads"],
        n_layers=model_config["num_layers"],
        ffn_dim=model_config["ffn_dim"],
        ree_base=model_config["ree_base"],
        mask_token_id=model_config["mask_token"],
        feature_type=model_config["feature_type"],
        compute_type=model_config["compute_type"],
        gradient_checkpointing=model_config["gradient_checkpointing"],
    ).to(device)
    optimizer = AdamW(
        model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay
    )
    scheduler = CosineAnnealingLR(optimizer, T_max=max(1, args.max_updates))
    amp_enabled = bool(args.use_amp and device.type == "cuda")
    scaler = torch.amp.GradScaler("cuda", enabled=amp_enabled)
    validation_seed = (
        stable_seed(validation_mask_seed, "validation_model_rng") % (2**63 - 1)
    )
    total_params = sum(parameter.numel() for parameter in model.parameters())
    history: list[dict[str, Any]] = []
    best_validation_loss = float("inf")
    best_update = 0

    def checkpoint_payload(kind: str, update: int, train_loss: float | None, val_loss: float):
        payload = {
            "schema_version": 1,
            "checkpoint_kind": kind,
            "model_state_dict": model.state_dict(),
            "update": int(update),
            "train_loss": train_loss,
            "val_loss": float(val_loss),
            "config": model_config,
            "training_config": training_config,
            "run_metadata": run_metadata,
            "total_params": total_params,
        }
        if kind == "last":
            payload["optimizer_state_dict"] = optimizer.state_dict()
            payload["scheduler_state_dict"] = scheduler.state_dict()
        return payload

    initial_validation = evaluate_model(
        model,
        validation_loader,
        device,
        validation_seed=validation_seed,
        sample_weights=validation_weights,
    )
    history.append({"update": 0, "train_loss": None, "validation_loss": initial_validation})

    validation_interval = max(1, int(args.validation_interval))
    window_losses: list[float] = []
    start_time = time.time()
    for update, (masked, truth, mask) in enumerate(train_loader, start=1):
        model.train()
        masked = masked.to(device)
        truth = truth.to(device)
        mask = mask.to(device)
        optimizer.zero_grad(set_to_none=True)
        amp_context = (
            torch.amp.autocast("cuda", enabled=True) if amp_enabled else nullcontext()
        )
        with amp_context:
            prediction = model(masked)
            loss = _masked_mse(prediction, truth, mask)
        if not torch.isfinite(loss):
            raise FloatingPointError(f"non-finite training loss at update {update}")
        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()
        scheduler.step()
        window_losses.append(float(loss.detach().item()))

        should_validate = update % validation_interval == 0 or update == args.max_updates
        if should_validate:
            mean_train_loss = float(np.mean(window_losses))
            validation_loss = evaluate_model(
                model,
                validation_loader,
                device,
                validation_seed=validation_seed,
                sample_weights=validation_weights,
            )
            history.append({
                "update": update,
                "train_loss": mean_train_loss,
                "validation_loss": validation_loss,
                "learning_rate": float(scheduler.get_last_lr()[0]),
            })
            payload = checkpoint_payload("last", update, mean_train_loss, validation_loss)
            _save_checkpoint(output_dir / "last_model.pt", payload)
            if validation_loss < best_validation_loss:
                best_validation_loss = validation_loss
                best_update = update
                _save_checkpoint(
                    output_dir / "best_model.pt",
                    checkpoint_payload("best", update, mean_train_loss, validation_loss),
                )
            if int(_getattr(args, "log_every", validation_interval)) > 0:
                print(
                    f"update={update}/{args.max_updates} "
                    f"train_loss={mean_train_loss:.6f} val_loss={validation_loss:.6f}",
                    flush=True,
                )
            window_losses = []

    if history[-1]["update"] != args.max_updates:
        raise AssertionError("training ended before the exact update budget")
    _write_json(output_dir / "training_history.json", history)
    run_metadata.update({
        "status": "complete",
        "elapsed_seconds": time.time() - start_time,
        "best_validation_loss": best_validation_loss,
        "best_update": best_update,
        "completed_updates": int(args.max_updates),
    })
    run_metadata["hashes"].update({
        "best_checkpoint_sha256": sha256_file(output_dir / "best_model.pt"),
        "last_checkpoint_sha256": sha256_file(output_dir / "last_model.pt"),
        "training_history_sha256": sha256_file(output_dir / "training_history.json"),
    })
    export_splits = list(_getattr(args, "export_splits", []) or [])
    if export_splits:
        checkpoint_kind = _getattr(args, "export_checkpoint", "best")
        checkpoint_path = output_dir / f"{checkpoint_kind}_model.pt"
        try:
            checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
        except TypeError:  # pragma: no cover - older Torch
            checkpoint = torch.load(checkpoint_path, map_location=device)
        model.load_state_dict(checkpoint["model_state_dict"])
        export = export_split_predictions(
            model,
            expression_path=expression_path,
            expression_info=expression_info,
            manifest=manifest,
            split=export_splits,
            split_column=split_column,
            sample_id_column=sample_id_column,
            normalization=args.normalization,
            mask_ratio=args.mask_ratio,
            mask_token=args.mask_token,
            mask_seed=int(_getattr(args, "export_mask_seed", 42)),
            batch_size=int(_getattr(args, "export_batch_size", args.validation_batch_size)),
            num_workers=args.num_workers,
            device=device,
            output_path=output_dir / "predictions.npz",
            checkpoint_path=checkpoint_path,
            model_role=args.role,
            model_selector=selection.selector,
            training_seed=seed,
            train_sample_ids_sha256=sha256_lines(train_ids),
            expression_file_sha256=run_metadata["hashes"]["expression_file_sha256"],
        )
        run_metadata["prediction_export"] = export
    _write_json(output_dir / "run_metadata.json", run_metadata)
    return {
        "history": history,
        "run_metadata": run_metadata,
        "best_checkpoint": output_dir / "best_model.pt",
        "last_checkpoint": output_dir / "last_model.pt",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expression-parquet", required=True)
    parser.add_argument(
        "--expression-metadata",
        help="Extractor report (default: extraction_report.json beside expression parquet)",
    )
    parser.add_argument(
        "--assume-expression-space",
        choices=("tpm",),
        help="Explicit synthetic-test escape hatch when no extractor report exists",
    )
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--role", choices=ROLES, required=True)
    parser.add_argument("--organ")
    parser.add_argument("--random-shard")
    parser.add_argument("--train-split", required=True)
    parser.add_argument(
        "--validation-split", "--val-split", dest="validation_split", required=True
    )
    parser.add_argument("--sample-id-column", default="sample_id")
    parser.add_argument("--split-column", default="split")
    parser.add_argument("--organ-column", default="organ")
    parser.add_argument("--group-column", default="series_group_id")
    parser.add_argument("--random-shard-column", default="random_shard")
    parser.add_argument(
        "--train-filter-column",
        help="Optional boolean/truthy eligibility column applied to training rows only",
    )
    parser.add_argument("--sampling-mode", choices=SAMPLING_MODES, default="natural")

    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--validation-mask-seed",
        type=int,
        default=42,
        help="Frozen across model/training seeds for comparable validation loss",
    )
    parser.add_argument("--max-updates", type=int, required=True)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--validation-batch-size", type=int, default=8)
    parser.add_argument("--validation-interval", type=int, default=50)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--normalization", choices=("tpm", "log1p_tpm", "raw_counts"), default="log1p_tpm")
    parser.add_argument("--mask-ratio", type=float, default=0.30)
    parser.add_argument("--mask-token", type=float, default=-10.0)

    parser.add_argument("--hidden-dim", type=int, default=768)
    parser.add_argument("--ffn-dim", type=int, default=0, help="0 derives 4 * hidden_dim")
    parser.add_argument("--num-heads", type=int, default=8)
    parser.add_argument("--num-layers", type=int, default=4)
    parser.add_argument("--ree-base", type=float, default=100.0)
    parser.add_argument("--feature-type", default="sqr")
    parser.add_argument("--compute-type", choices=("iter", "ps", "parallel_ps"), default="iter")
    parser.add_argument(
        "--gradient-checkpointing", action=argparse.BooleanOptionalAction, default=True
    )
    parser.add_argument("--use-amp", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--deterministic",
        action="store_true",
        default=True,
        help="Required; retained as an explicit provenance flag",
    )
    parser.add_argument("--device", default="auto", help="auto, cpu, cuda, or cuda:N")
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--torch-threads", type=int, default=0)
    parser.add_argument("--log-every", type=int, default=50)
    parser.add_argument(
        "--export-split",
        dest="export_splits",
        action="append",
        default=[],
        help="Manifest split to export with frozen masks; repeat for multiple splits",
    )
    parser.add_argument("--export-checkpoint", choices=("best", "last"), default="best")
    parser.add_argument("--export-mask-seed", type=int, default=42)
    parser.add_argument("--export-batch-size", type=int, default=8)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = run_training(args)
    print(json.dumps({
        "status": "complete",
        "best_checkpoint": str(result["best_checkpoint"]),
        "last_checkpoint": str(result["last_checkpoint"]),
        "best_validation_loss": result["run_metadata"]["best_validation_loss"],
        "best_update": result["run_metadata"]["best_update"],
    }, indent=2))


if __name__ == "__main__":
    main()
