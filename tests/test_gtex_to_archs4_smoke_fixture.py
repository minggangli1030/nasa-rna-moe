from __future__ import annotations

import json
import sys
from argparse import Namespace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
for source in (ROOT / "core", ROOT / "evaluation"):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))

from build_gtex_to_archs4_smoke_fixture import build  # noqa: E402
from train_manifest import sha256_file, sha256_lines  # noqa: E402


ORGANS = (
    "adipose",
    "brain",
    "colon",
    "heart",
    "liver",
    "lung",
    "skeletal_muscle",
    "skin",
)


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _fixture(tmp_path: Path) -> Namespace:
    rows = []
    for split_index, split in enumerate(("train", "calibration")):
        for organ_index, organ in enumerate(ORGANS):
            for label in range(8):
                donor = f"{split}-d-{organ_index}-{label}"
                rows.append(
                    {
                        "sample_id": f"{donor}-s",
                        "donor_id": donor,
                        "utility_split": split,
                        "split": split,
                        "balanced_train": True,
                        "organ": organ,
                        "tissue_site": organ,
                        "series_group_id": donor,
                        "organ_k8": organ_index,
                        "random_k8_p17": label,
                        "random_k8_p42": (label + organ_index) % 8,
                        "random_k8_p101": (label + 2 * organ_index) % 8,
                        "pooled_adapter": 0,
                    }
                )
    manifest = pd.DataFrame(rows)
    manifest_path = tmp_path / "manifest.parquet"
    manifest.to_parquet(manifest_path, index=False)
    manifest_report_path = tmp_path / "manifest_report.json"
    _write_json(
        manifest_report_path,
        {
            "status": "complete",
            "archs4_expression_accessed": False,
            "config": {
                "organ_axis": "organ_k8",
                "random_axes": [
                    "random_k8_p17",
                    "random_k8_p42",
                    "random_k8_p101",
                ],
            },
            "hashes": {"manifest_sha256": sha256_file(manifest_path)},
        },
    )

    expression = pd.DataFrame(
        {
            "sample_id": manifest["sample_id"],
            "G1": np.arange(len(manifest), dtype=np.float32) + 1,
            "G2": np.arange(len(manifest), dtype=np.float32) + 2,
        }
    )
    expression_path = tmp_path / "expression.parquet"
    expression.to_parquet(expression_path, index=False)
    expression_report_path = tmp_path / "expression_report.json"
    _write_json(
        expression_report_path,
        {
            "status": "complete",
            "archs4_expression_accessed": False,
            "expression_space": "tpm",
            "gene_order_sha256": sha256_lines(["G1", "G2"]),
            "hashes": {"expression_sha256": sha256_file(expression_path)},
        },
    )

    axes = tmp_path / "axes.npz"
    np.savez_compressed(
        axes,
        gene_names=np.asarray(["G1", "G2"]),
        score_gene_indices=np.asarray([0], dtype=np.int64),
        probe_gene_indices=np.asarray([1], dtype=np.int64),
    )
    protocol_path = tmp_path / "protocol.json"
    _write_json(
        protocol_path,
        {
            "status": "frozen_gtex_to_archs4_development_contract",
            "firewalls": {
                "archs4_lockbox_expression_access_before_candidate_freeze": False
            },
            "expression_contract": {
                "axis_definitions_sha256": sha256_file(axes)
            },
        },
    )
    return Namespace(
        protocol=str(protocol_path),
        expected_protocol_sha256=sha256_file(protocol_path),
        manifest=str(manifest_path),
        manifest_report=str(manifest_report_path),
        expression=str(expression_path),
        expression_report=str(expression_report_path),
        axis_definitions=str(axes),
        minimum_rows_per_split=32,
        output_dir=str(tmp_path / "output"),
    )


def test_smoke_fixture_preserves_axis_and_split_coverage(tmp_path: Path) -> None:
    args = _fixture(tmp_path)
    report = build(args)
    manifest = pd.read_parquet(Path(args.output_dir) / "smoke_manifest.parquet")
    expression = pd.read_parquet(Path(args.output_dir) / "smoke_expression.parquet")

    assert report["status"] == "complete"
    assert report["mechanical_only"] is True
    assert report["efficacy_scoring_performed"] is False
    assert report["archs4_expression_accessed"] is False
    assert set(manifest["organ_k8"]) == set(range(8))
    for axis in ("random_k8_p17", "random_k8_p42", "random_k8_p101"):
        for split in ("train", "calibration"):
            assert set(manifest.loc[manifest["split"].eq(split), axis]) == set(
                range(8)
            )
    assert expression["sample_id"].tolist() == manifest["sample_id"].tolist()
    assert manifest.groupby("donor_id")["split"].nunique().max() == 1


def test_smoke_fixture_rejects_expression_hash_mismatch(tmp_path: Path) -> None:
    args = _fixture(tmp_path)
    expression = pd.read_parquet(args.expression)
    expression.loc[0, "G1"] = 999
    expression.to_parquet(args.expression, index=False)

    with pytest.raises(ValueError, match="expression differs"):
        build(args)
