from __future__ import annotations

import json
import sys
from argparse import Namespace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))
sys.path.insert(0, str(ROOT / "evaluation"))

from freeze_organ_k_router import (  # noqa: E402
    SPECIALIST_ORDER,
    collapse_k5_probabilities,
    connected_study_folds,
    freeze,
    mask_score_genes,
    nested_router_labels,
    subset_router_labels,
)
from train_manifest import sha256_file, sha256_lines  # noqa: E402


SCORE_INDICES = np.asarray([2, 7, 11], dtype=np.int64)


def _write_partition_report(
    path: Path,
    partition: Path,
    expression: Path,
    source_manifest: Path,
    definitions: Path,
) -> None:
    path.write_text(json.dumps({
        "schema_version": 1,
        "status": "complete",
        "test_accessed": False,
        "hashes": {
            "partition_manifest_sha256": sha256_file(partition),
            "expression_parquet_sha256": sha256_file(expression),
            "source_manifest_sha256": sha256_file(source_manifest),
            "axis_definitions_sha256": sha256_file(definitions),
        },
    }))


def _fixture(root: Path) -> dict[str, Path | list[str]]:
    rng = np.random.default_rng(8128)
    genes = [f"g{index:02d}" for index in range(15)]
    rows: list[dict] = []
    expression_rows: list[dict] = []

    def add_row(sample_id: str, organ: str, group: str, split: str, rep: int) -> None:
        values = rng.gamma(shape=2.0, scale=0.7, size=len(genes)).astype(np.float32)
        # Put learnable organ signal outside the frozen score panel.
        signal_columns = [0, 1, 3, 4, 5]
        values[signal_columns[SPECIALIST_ORDER.index(organ)]] += 5.0
        expression_rows.append({
            "sample_id": sample_id,
            **{gene: value for gene, value in zip(genes, values)},
        })
        rows.append({
            "sample_id": sample_id,
            "organ": organ,
            "series_group_id": group,
            "split": split,
            "balanced_train": split == "train",
            "rep": rep,
        })

    for organ in SPECIALIST_ORDER:
        for group_index in range(10):
            for rep in range(2):
                add_row(
                    f"cal_{organ}_{group_index:02d}_{rep}",
                    organ,
                    f"cal_group_{organ}_{group_index:02d}",
                    "calibration",
                    rep,
                )
        for rep in range(2):
            add_row(
                f"train_{organ}_{rep}", organ, f"train_group_{organ}", "train", rep
            )
        for rep in range(2):
            add_row(
                f"test_{organ}_{rep}", organ, f"test_group_{organ}", "test", rep
            )

    source = pd.DataFrame(rows).drop(columns=["rep"])
    source_manifest = root / "source_manifest.parquet"
    source.to_parquet(source_manifest, index=False)
    expression_frame = pd.DataFrame(expression_rows)
    expression = root / "expression.parquet"
    expression_frame.to_parquet(expression, index=False, row_group_size=7)
    expression_metadata = root / "extraction_report.json"
    expression_metadata.write_text(json.dumps({
        "status": "complete",
        "expression_space": "tpm",
        "gene_order_sha256": sha256_lines(genes),
    }))

    definitions = root / "axis_definitions.npz"
    np.savez_compressed(
        definitions,
        gene_names=np.asarray(genes, dtype=str),
        score_gene_indices=SCORE_INDICES,
    )
    organ_index = {organ: index for index, organ in enumerate(SPECIALIST_ORDER)}
    partition = source.loc[source["split"].isin(["train", "calibration"])].copy()
    partition["utility_split"] = partition.pop("split")
    partition["organ_k5"] = partition["organ"].map(organ_index).astype(np.int64)
    partition["random_k5"] = np.arange(len(partition), dtype=np.int64) % 5
    partition = pd.concat(
        [
            partition.loc[partition["utility_split"] == "train"],
            partition.loc[partition["utility_split"] == "calibration"],
        ],
        ignore_index=True,
    )
    partition_manifest = root / "train_cal_partitions.parquet"
    partition.to_parquet(partition_manifest, index=False)
    partition_report = root / "partition_report.json"
    _write_partition_report(
        partition_report,
        partition_manifest,
        expression,
        source_manifest,
        definitions,
    )
    return {
        "genes": genes,
        "expression": expression,
        "expression_metadata": expression_metadata,
        "source_manifest": source_manifest,
        "definitions": definitions,
        "partition_manifest": partition_manifest,
        "partition_report": partition_report,
    }


def _args(fixture: dict, output: Path) -> Namespace:
    return Namespace(
        expression_parquet=str(fixture["expression"]),
        expression_metadata=str(fixture["expression_metadata"]),
        source_manifest=str(fixture["source_manifest"]),
        axis_definitions=str(fixture["definitions"]),
        partition_manifest=str(fixture["partition_manifest"]),
        partition_report=str(fixture["partition_report"]),
        output_dir=str(output),
        router_seed=314159,
        mask_token=-10.0,
        train_split="train",
        calibration_split="calibration",
        train_filter_column="balanced_train",
        source_split_column="split",
        sample_id_column="sample_id",
        organ_column="organ",
        group_column="series_group_id",
    )


def test_masking_hides_every_score_gene_without_mutating_input():
    expression = np.arange(30, dtype=np.float32).reshape(3, 10)
    original = expression.copy()
    score = np.asarray([1, 4, 8], dtype=np.int64)
    masked = mask_score_genes(expression, score, -10.0)
    assert np.array_equal(expression, original)
    assert np.all(masked[:, score] == -10.0)
    context = np.asarray([index for index in range(10) if index not in score])
    assert np.array_equal(masked[:, context], expression[:, context])


def test_uneven_real_like_groups_put_every_organ_in_every_fold():
    # Mirrors the real calibration's unequal group support and highly variable
    # study sizes.  A plain StratifiedGroupKFold can leave strata empty here.
    n_groups_by_organ = [15, 17, 9, 11, 12]
    organs: list[str] = []
    groups: list[str] = []
    for organ_index, (organ, n_groups) in enumerate(
        zip(SPECIALIST_ORDER, n_groups_by_organ)
    ):
        for group_index in range(n_groups):
            size = 1 + ((group_index * 7 + organ_index * 3) % 23)
            organs.extend([organ] * size)
            groups.extend([f"{organ}_study_{group_index:02d}"] * size)
    organs_array = np.asarray(organs, dtype=str)
    groups_array = np.asarray(groups, dtype=str)
    first, reports = connected_study_folds(
        organs_array, groups_array, seed=271828
    )
    second, _ = connected_study_folds(
        organs_array, groups_array, seed=271828
    )
    assert np.array_equal(first, second)
    for group in np.unique(groups_array):
        assert len(np.unique(first[groups_array == group])) == 1
    for fold in range(5):
        assert set(organs_array[first == fold]) == set(SPECIALIST_ORDER)
        assert reports[fold]["all_organs_present"] is True
        assert all(count > 0 for count in reports[fold]["held_organ_counts"].values())


def test_router_artifact_is_deterministic_group_disjoint_and_well_formed(tmp_path):
    fixture = _fixture(tmp_path)
    first_report = freeze(_args(fixture, tmp_path / "first"))
    second_report = freeze(_args(fixture, tmp_path / "second"))
    first_path = tmp_path / "first" / "organ_k_router.npz"
    second_path = tmp_path / "second" / "organ_k_router.npz"
    assert sha256_file(first_path) == sha256_file(second_path)
    assert first_report["test_accessed"] is False
    assert first_report["test_features_loaded"] is False
    assert first_report["train_features_loaded"] is False
    assert first_report["data_access"]["loaded_expression_split"] == "calibration"

    with np.load(first_path, allow_pickle=False) as first, np.load(
        second_path, allow_pickle=False
    ) as second:
        assert set(first.files) == set(second.files)
        for name in first.files:
            assert np.array_equal(first[name], second[name]), name

        groups = first["calibration_series_group_id"].astype(str)
        folds = first["crossfit_fold"]
        assert set(folds.tolist()) == set(range(5))
        for group in np.unique(groups):
            assert len(np.unique(folds[groups == group])) == 1

        organs = first["calibration_organs"].astype(str)
        subset_ids = first["subset_ids"]
        subset_k = first["subset_k"]
        subset_mask = first["subset_selected_mask"]
        subset_predicted = first["subset_crossfit_predicted_class"].astype(str)
        k5_classes = first["k5_crossfit_classes"].astype(str)
        k5_probabilities = first["k5_crossfit_probabilities"]
        inner_probabilities = first["outer_inner_k5_probabilities"]
        inner_valid = first["outer_inner_valid_mask"]
        assert np.array_equal(subset_ids, np.arange(1, 32))
        assert subset_mask.shape == (31, 5)
        assert subset_predicted.shape == (31, len(organs))
        assert np.array_equal(subset_k, subset_mask.sum(axis=1))
        assert len({tuple(row) for row in subset_mask.tolist()}) == 31
        assert k5_probabilities.shape == (len(organs), 5)
        assert np.allclose(k5_probabilities.sum(axis=1), 1.0)
        assert inner_probabilities.shape == (5, len(organs), 5)
        assert inner_valid.shape == (5, len(organs))
        for fold in range(5):
            assert np.array_equal(inner_valid[fold], folds != fold)
            assert np.allclose(
                inner_probabilities[fold, inner_valid[fold]].sum(axis=1), 1.0
            )
            assert np.all(inner_probabilities[fold, ~inner_valid[fold]] == 0.0)
        for row, subset_id in enumerate(subset_ids):
            expected_mask = (
                (int(subset_id) >> np.arange(len(SPECIALIST_ORDER))) & 1
            ).astype(bool)
            assert np.array_equal(subset_mask[row], expected_mask)
            labels = subset_router_labels(organs, expected_mask)
            assert set(subset_predicted[row]) <= set(np.unique(labels))
            _, _, collapsed_predicted = collapse_k5_probabilities(
                k5_probabilities, k5_classes, expected_mask
            )
            assert np.array_equal(subset_predicted[row], collapsed_predicted)
        for k in range(1, 6):
            classes = first[f"k{k}_classes"].astype(str)
            probabilities = first[f"k{k}_crossfit_probabilities"]
            predicted = first[f"k{k}_crossfit_predicted_class"].astype(str)
            expected = np.unique(nested_router_labels(organs, k))
            assert np.array_equal(classes, expected)
            assert probabilities.shape == (len(organs), len(classes))
            assert np.allclose(probabilities.sum(axis=1), 1.0)
            assert set(predicted) <= set(classes)
            nested_subset_row = int(np.flatnonzero(subset_ids == (1 << k) - 1)[0])
            assert np.array_equal(predicted, subset_predicted[nested_subset_row])
        assert first["k5_full_coefficients"].shape == (5, len(fixture["genes"]))
        assert first["k5_full_intercepts"].shape == (5,)
        assert np.allclose(first["k5_full_scaler_mean"][SCORE_INDICES], -10.0)
        assert np.isfinite(first["k5_full_scaler_mean"]).all()
        assert np.isfinite(first["k5_full_coefficients"]).all()


def test_partition_with_test_row_is_rejected_before_expression_fit(tmp_path):
    fixture = _fixture(tmp_path)
    partition_path = Path(fixture["partition_manifest"])
    partition = pd.read_parquet(partition_path)
    source = pd.read_parquet(fixture["source_manifest"])
    test_row = source.loc[source["split"] == "test"].iloc[[0]].copy()
    test_row["utility_split"] = test_row.pop("split")
    test_row["organ_k5"] = 0
    test_row["random_k5"] = 0
    partition = pd.concat([partition, test_row[partition.columns]], ignore_index=True)
    partition.to_parquet(partition_path, index=False)
    _write_partition_report(
        Path(fixture["partition_report"]),
        partition_path,
        Path(fixture["expression"]),
        Path(fixture["source_manifest"]),
        Path(fixture["definitions"]),
    )
    with pytest.raises(ValueError, match="train/calibration rows only"):
        freeze(_args(fixture, tmp_path / "rejected"))


def test_all_subset_routers_ignore_calibration_score_targets(tmp_path):
    fixture = _fixture(tmp_path)
    freeze(_args(fixture, tmp_path / "score_before"))
    expression_path = Path(fixture["expression"])
    expression = pd.read_parquet(expression_path)
    source = pd.read_parquet(fixture["source_manifest"])
    calibration_ids = set(
        source.loc[source["split"] == "calibration", "sample_id"].astype(str)
    )
    calibration_rows = expression["sample_id"].astype(str).isin(calibration_ids)
    score_columns = [fixture["genes"][index] for index in SCORE_INDICES]
    expression.loc[calibration_rows, score_columns] = 999_999.0
    expression.to_parquet(expression_path, index=False, row_group_size=7)
    _write_partition_report(
        Path(fixture["partition_report"]),
        Path(fixture["partition_manifest"]),
        expression_path,
        Path(fixture["source_manifest"]),
        Path(fixture["definitions"]),
    )
    freeze(_args(fixture, tmp_path / "score_after"))
    with np.load(
        tmp_path / "score_before" / "organ_k_router.npz", allow_pickle=False
    ) as before, np.load(
        tmp_path / "score_after" / "organ_k_router.npz", allow_pickle=False
    ) as after:
        for name in before.files:
            assert np.array_equal(before[name], after[name]), name


def test_router_parameters_ignore_test_label_and_target_changes(tmp_path):
    fixture = _fixture(tmp_path)
    before_report = freeze(_args(fixture, tmp_path / "before"))

    source_path = Path(fixture["source_manifest"])
    expression_path = Path(fixture["expression"])
    source = pd.read_parquet(source_path)
    test_ids = source.loc[source["split"] == "test", "sample_id"].astype(str)
    source.loc[source["split"] == "test", "organ"] = "liver"
    source.loc[source["split"] == "test", "series_group_id"] = [
        f"mutated_test_group_{index}" for index in range(len(test_ids))
    ]
    source.to_parquet(source_path, index=False)
    expression = pd.read_parquet(expression_path)
    gene_columns = [column for column in expression.columns if column != "sample_id"]
    test_rows = expression["sample_id"].astype(str).isin(set(test_ids))
    expression.loc[test_rows, gene_columns] = 1_000_000.0
    expression.to_parquet(expression_path, index=False, row_group_size=7)
    _write_partition_report(
        Path(fixture["partition_report"]),
        Path(fixture["partition_manifest"]),
        expression_path,
        source_path,
        Path(fixture["definitions"]),
    )
    after_report = freeze(_args(fixture, tmp_path / "after"))

    with np.load(tmp_path / "before" / "organ_k_router.npz", allow_pickle=False) as before, np.load(
        tmp_path / "after" / "organ_k_router.npz", allow_pickle=False
    ) as after:
        for name in before.files:
            assert np.array_equal(before[name], after[name]), name
    assert after_report["data_access"]["n_loaded_expression_rows"] == 100
    assert (
        before_report["hashes"]["expression_parquet_sha256"]
        != after_report["hashes"]["expression_parquet_sha256"]
    )
