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

from build_organ_k_confirmation_partitions import (  # noqa: E402
    CANONICAL_ORGANS,
    PARTITION_AXES,
    PARTITION_REPORT_FILENAME,
    RANDOM_GROUP_AXES,
    RANDOM_GROUP_AXIS_SEEDS,
    SEALED_TEST_FILENAME,
    SEALED_TEST_REPORT_FILENAME,
    TRAIN_CAL_FILENAME,
    _assign_study_preserving_labels,
    _group_integrity_summary,
    build,
)
from train_manifest import sha256_file, sha256_lines  # noqa: E402


def _write_fixture(root: Path) -> tuple[Path, Path, Path, pd.DataFrame]:
    rows = []
    for organ_index, organ in enumerate(CANONICAL_ORGANS):
        # Deliberately rotate the frozen shards so the builder cannot appear to
        # recreate them from row position or organ identity.
        for sample_index in range(3):
            rows.append({
                "sample_id": f"z-train-{organ_index}-{sample_index}",
                "organ": organ,
                # The two selected rows deliberately share a connected study
                # but have different legacy random shards. This reproduces the
                # launch-audit defect while the new axes must remain atomic.
                "series_group_id": (
                    f"train-study-{organ_index}"
                    if sample_index < 2
                    else f"train-extra-study-{organ_index}"
                ),
                "split": "train",
                "balanced_train": sample_index < 2,
                "random_shard": f"random_{(organ_index + sample_index + 2) % 5}",
            })
        rows.append({
            "sample_id": f"m-cal-{organ_index}",
            "organ": organ,
            "series_group_id": f"cal-study-{organ_index}",
            "split": "calibration",
            "balanced_train": False,
            "random_shard": f"random_{(organ_index + 3) % 5}",
        })
        rows.append({
            "sample_id": f"a-test-{organ_index}",
            "organ": organ,
            "series_group_id": f"test-study-{organ_index}",
            "split": "test",
            "balanced_train": False,
            "random_shard": f"random_{(organ_index + 4) % 5}",
        })
    frame = pd.DataFrame(rows).sample(frac=1.0, random_state=71).reset_index(drop=True)
    manifest_path = root / "manifest.parquet"
    frame.to_parquet(manifest_path, index=False)

    definitions_path = root / "axis_definitions.npz"
    gene_names = np.asarray([f"gene_{index}" for index in range(10)])
    np.savez_compressed(
        definitions_path,
        probe_gene_indices=np.asarray([0, 4], dtype=np.int64),
        score_gene_indices=np.asarray([1, 3, 6], dtype=np.int64),
        context_gene_indices=np.asarray([2, 5, 7, 8, 9], dtype=np.int64),
        gene_names=gene_names,
    )
    selected_train = frame.loc[
        frame["split"].eq("train") & frame["balanced_train"]
    ].sort_values("sample_id")
    selected_calibration = frame.loc[frame["split"].eq("calibration")].sort_values(
        "sample_id"
    )
    utility_report = {
        "schema_version": 1,
        "status": "complete",
        "experiment": "target_hidden_utility_axis_partitions",
        "test_accessed": False,
        "counts": {
            "train": len(selected_train),
            "calibration": len(selected_calibration),
            "genes": len(gene_names),
        },
        "gene_partition": {
            "probe_genes": 2,
            "score_genes": 3,
            "context_genes": 5,
        },
        "hashes": {
            "manifest_sha256": sha256_file(manifest_path),
            "axis_definitions_sha256": sha256_file(definitions_path),
            "gene_order_sha256": sha256_lines(gene_names.tolist()),
            "train_sample_ids_sha256": sha256_lines(
                selected_train["sample_id"].tolist()
            ),
            "calibration_sample_ids_sha256": sha256_lines(
                selected_calibration["sample_id"].tolist()
            ),
        },
    }
    utility_report_path = root / "utility_partition_report.json"
    utility_report_path.write_text(json.dumps(utility_report, indent=2) + "\n")
    return manifest_path, utility_report_path, definitions_path, frame


def _args(
    root: Path,
    manifest: Path,
    report: Path,
    definitions: Path,
    *,
    emit_sealed_test: bool = False,
) -> Namespace:
    return Namespace(
        manifest=str(manifest),
        utility_partition_report=str(report),
        utility_axis_definitions=str(definitions),
        output_dir=str(root / "output"),
        train_split="train",
        validation_split="calibration",
        test_split="test",
        train_filter_column="balanced_train",
        emit_sealed_test=emit_sealed_test,
    )


def test_builds_exact_loader_order_and_maps_only_existing_assignments(tmp_path):
    manifest, utility_report, definitions, source = _write_fixture(tmp_path)
    args = _args(tmp_path, manifest, utility_report, definitions)
    report = build(args)
    artifact = pd.read_parquet(Path(args.output_dir) / TRAIN_CAL_FILENAME)

    expected_train = source.loc[
        source["split"].eq("train") & source["balanced_train"]
    ].sort_values("sample_id")
    expected_calibration = source.loc[source["split"].eq("calibration")].sort_values(
        "sample_id"
    )
    expected_ids = (
        expected_train["sample_id"].tolist()
        + expected_calibration["sample_id"].tolist()
    )
    assert artifact["sample_id"].tolist() == expected_ids
    assert artifact["utility_split"].tolist() == ["train"] * 10 + [
        "calibration"
    ] * 5
    assert set(artifact["split"]) == {"train", "calibration"}
    assert not set(source.loc[source["split"].eq("test"), "sample_id"]) & set(
        artifact["sample_id"]
    )

    organ_mapping = {name: index for index, name in enumerate(CANONICAL_ORGANS)}
    random_mapping = {f"random_{index}": index for index in range(5)}
    assert artifact["organ_k5"].tolist() == [
        organ_mapping[value] for value in artifact["organ"]
    ]
    assert artifact["random_k5"].tolist() == [
        random_mapping[value] for value in artifact["random_shard"]
    ]
    expected_random = pd.concat([expected_train, expected_calibration])[
        "random_shard"
    ].tolist()
    assert artifact["random_shard"].tolist() == expected_random
    assert sorted(artifact["organ_k5"].unique()) == list(range(5))
    assert sorted(artifact["random_k5"].unique()) == list(range(5))

    assert report["status"] == "complete"
    assert report["test_accessed"] is False
    assert report["test_expression_accessed"] is False
    assert report["test_targets_accessed"] is False
    assert report["sealed_test_assignment_emitted"] is False
    assert report["axes"] == list(PARTITION_AXES)
    assert report["gating_axes"] == ["organ_k5", *RANDOM_GROUP_AXES]
    assert report["non_gating_diagnostic_axes"] == ["random_k5"]
    assert report["counts"]["train"] == 10
    assert report["counts"]["calibration"] == 5
    assert set(report["counts"]["balanced_train_by_organ"].values()) == {2}
    assert set(report["counts"]["balanced_train_by_random_shard"].values()) == {2}
    # Legacy row-level shards split every two-row connected training study and
    # therefore remain visible only as a non-gating diagnostic.
    assert report["partitions"]["random_k5"]["gating_role"] == (
        "non_gating_diagnostic"
    )
    assert report["partitions"]["random_k5"]["train"]["group_integrity"][
        "passed"
    ] is False
    assert artifact.groupby("series_group_id")["random_k5"].nunique().max() == 2
    for axis in RANDOM_GROUP_AXES:
        assert sorted(artifact.loc[artifact["split"].eq("train"), axis].unique()) == list(
            range(5)
        )
        assert artifact.groupby(["split", "series_group_id"])[axis].nunique().max() == 1
        axis_report = report["partitions"][axis]
        assert axis_report["partition_seed"] == RANDOM_GROUP_AXIS_SEEDS[axis]
        assert axis_report["gating_role"] == "preregistered_matched_random_control"
        assert axis_report["group_preserving"] is True
        assert axis_report["train"]["group_integrity"]["passed"] is True
        assert axis_report["calibration"]["group_integrity"]["passed"] is True
        assert axis_report["train"]["total_sample_imbalance_max_minus_min"] == 0
        assert axis_report["train"]["maximum_per_organ_sample_imbalance"] == 2
        assert f"train_cal_{axis}_assignment_sha256" in report["hashes"]
    assert report["hashes"]["partition_manifest_sha256"] == sha256_file(
        Path(args.output_dir) / TRAIN_CAL_FILENAME
    )
    assert report["hashes"]["train_cal_partitions_sha256"] == report["hashes"][
        "partition_manifest_sha256"
    ]
    assert report["hashes"]["axis_definitions_sha256"] == sha256_file(definitions)
    written = json.loads(
        (Path(args.output_dir) / PARTITION_REPORT_FILENAME).read_text()
    )
    assert written == report
    assert (Path(args.output_dir) / "COMPLETE").is_file()
    assert not (Path(args.output_dir) / SEALED_TEST_FILENAME).exists()


def test_optional_test_assignments_are_separate_sealed_and_hashed(tmp_path):
    manifest, utility_report, definitions, source = _write_fixture(tmp_path)
    args = _args(
        tmp_path,
        manifest,
        utility_report,
        definitions,
        emit_sealed_test=True,
    )
    report = build(args)
    output = Path(args.output_dir)
    trainer = pd.read_parquet(output / TRAIN_CAL_FILENAME)
    sealed = pd.read_parquet(output / SEALED_TEST_FILENAME)
    sealed_report = json.loads((output / SEALED_TEST_REPORT_FILENAME).read_text())

    expected_test = source.loc[source["split"].eq("test")].sort_values("sample_id")
    assert sealed["sample_id"].tolist() == expected_test["sample_id"].tolist()
    assert set(sealed["utility_split"]) == {"test"}
    assert not set(sealed["sample_id"]) & set(trainer["sample_id"])
    assert sealed["random_shard"].tolist() == expected_test["random_shard"].tolist()
    assert set(RANDOM_GROUP_AXES) <= set(sealed.columns)
    for axis in RANDOM_GROUP_AXES:
        assert sealed.groupby("series_group_id")[axis].nunique().max() == 1
        assert sealed_report["partitions"][axis]["test"]["group_integrity"][
            "passed"
        ] is True
        assert (
            f"test_{axis}_assignment_sha256" in sealed_report["hashes"]
        )
    assert sealed_report["sealed"] is True
    assert sealed_report["test_accessed"] is False
    assert sealed_report["test_expression_accessed"] is False
    assert sealed_report["test_targets_accessed"] is False
    assert sealed_report["hashes"]["sealed_test_assignments_sha256"] == sha256_file(
        output / SEALED_TEST_FILENAME
    )
    assert report["sealed_test_assignment_emitted"] is True
    assert report["hashes"]["sealed_test_assignments_sha256"] == sha256_file(
        output / SEALED_TEST_FILENAME
    )
    assert report["hashes"]["sealed_test_report_sha256"] == sha256_file(
        output / SEALED_TEST_REPORT_FILENAME
    )


def test_group_axes_are_deterministic_seed_diverse_atomic_and_balanced():
    rows = []
    for organ_index, organ in enumerate(CANONICAL_ORGANS):
        for group_index in range(10):
            for replicate in range(2):
                rows.append({
                    "sample_id": f"s-{organ_index}-{group_index}-{replicate}",
                    "organ": organ,
                    "series_group_id": f"g-{organ_index}-{group_index}",
                })
    frame = pd.DataFrame(rows)
    shuffled = frame.sample(frac=1.0, random_state=901).reset_index(drop=True)
    group_maps: list[pd.Series] = []
    coassignment_signatures: set[bytes] = set()
    for seed in RANDOM_GROUP_AXIS_SEEDS.values():
        labels, summary = _assign_study_preserving_labels(
            frame,
            partition_seed=seed,
            split_name="train",
            require_all_labels=True,
        )
        shuffled_labels, shuffled_summary = _assign_study_preserving_labels(
            shuffled,
            partition_seed=seed,
            split_name="train",
            require_all_labels=True,
        )
        labeled = frame.assign(label=labels)
        shuffled_labeled = shuffled.assign(label=shuffled_labels)
        first = labeled.set_index("sample_id")["label"].sort_index()
        second = shuffled_labeled.set_index("sample_id")["label"].sort_index()
        pd.testing.assert_series_equal(first, second)
        assert summary["group_assignment_sha256"] == shuffled_summary[
            "group_assignment_sha256"
        ]
        assert labeled.groupby("series_group_id")["label"].nunique().max() == 1
        assert summary["group_integrity"]["passed"] is True
        assert summary["total_sample_imbalance_max_minus_min"] <= 2
        assert summary["maximum_per_organ_sample_imbalance"] <= 2
        group_map = labeled.groupby("series_group_id")["label"].first().sort_index()
        group_maps.append(group_map)
        values = group_map.to_numpy()
        coassignment_signatures.add(np.equal.outer(values, values).tobytes())
    # Diversity must change group co-membership, not merely permute shard names.
    assert len(coassignment_signatures) >= 2

    tampered = frame.copy()
    tampered["label"] = group_maps[0].reindex(
        tampered["series_group_id"]
    ).to_numpy()
    same_group = tampered.index[
        tampered["series_group_id"].eq(tampered.iloc[0]["series_group_id"])
    ]
    tampered.loc[same_group[-1], "label"] = (
        int(tampered.loc[same_group[-1], "label"]) + 1
    ) % 5
    with pytest.raises(ValueError, match="splits connected studies"):
        _group_integrity_summary(tampered, "label", fail_on_split=True)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("random", "random_shard values differ"),
        ("organ", "organ labels differ"),
        ("study", "connected studies cross source splits"),
    ],
)
def test_rejects_changed_labels_or_study_split_leakage(tmp_path, mutation, message):
    manifest, utility_report, definitions, frame = _write_fixture(tmp_path)
    if mutation == "random":
        row = frame.index[
            frame["split"].eq("calibration") & frame["organ"].eq("brain")
        ][0]
        frame.loc[row, "random_shard"] = "random_new"
    elif mutation == "organ":
        row = frame.index[
            frame["split"].eq("calibration") & frame["organ"].eq("brain")
        ][0]
        frame.loc[row, "organ"] = "lung"
    else:
        train_group = frame.loc[frame["split"].eq("train"), "series_group_id"].iloc[0]
        row = frame.index[frame["split"].eq("calibration")][0]
        frame.loc[row, "series_group_id"] = train_group
    frame.to_parquet(manifest, index=False)
    utility = json.loads(utility_report.read_text())
    utility["hashes"]["manifest_sha256"] = sha256_file(manifest)
    utility_report.write_text(json.dumps(utility, indent=2) + "\n")
    args = _args(tmp_path, manifest, utility_report, definitions)
    with pytest.raises(ValueError, match=message):
        build(args)


def test_rejects_source_or_definition_drift_from_utility_freeze(tmp_path):
    manifest, utility_report, definitions, _ = _write_fixture(tmp_path)
    utility = json.loads(utility_report.read_text())
    utility["hashes"]["calibration_sample_ids_sha256"] = "0" * 64
    utility_report.write_text(json.dumps(utility, indent=2) + "\n")
    args = _args(tmp_path, manifest, utility_report, definitions)
    with pytest.raises(ValueError, match="calibration sample order differs"):
        build(args)

    drift_root = tmp_path / "definition-drift"
    drift_root.mkdir()
    manifest, utility_report, definitions, _ = _write_fixture(drift_root)
    with np.load(definitions, allow_pickle=False) as archive:
        arrays = {name: archive[name].copy() for name in archive.files}
    arrays["score_gene_indices"] = np.asarray([1, 3, 7], dtype=np.int64)
    np.savez_compressed(definitions, **arrays)
    args = _args(drift_root, manifest, utility_report, definitions)
    with pytest.raises(ValueError, match="axis definitions hash differs"):
        build(args)
