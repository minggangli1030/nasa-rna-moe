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

from refit_gtex_to_archs4_router import refit  # noqa: E402
from train_manifest import sha256_file, sha256_lines  # noqa: E402


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _fixture(tmp_path: Path) -> Namespace:
    rows = []
    values = []
    for class_index, organ in enumerate(("brain", "liver")):
        for index in range(12):
            split = "train" if index < 8 else "calibration"
            sample = f"{organ}-{index}"
            rows.append(
                {
                    "sample_id": sample,
                    "donor_id": f"d-{organ}-{index}",
                    "split": split,
                    "organ": organ,
                    "series_group_id": f"d-{organ}-{index}",
                    "balanced_train": True,
                }
            )
            values.append(
                {
                    "sample_id": sample,
                    "G1": float(index + 1),
                    "G2": float(class_index * 100 + index + 1),
                    "G3": float((1 - class_index) * 50 + index),
                    "G4": float(index % 3),
                }
            )
    manifest_path = tmp_path / "manifest.parquet"
    pd.DataFrame(rows).to_parquet(manifest_path, index=False)
    manifest_report_path = tmp_path / "manifest_report.json"
    _write_json(
        manifest_report_path,
        {
            "status": "complete",
            "test_accessed": False,
            "archs4_expression_accessed": False,
            "hashes": {"manifest_sha256": sha256_file(manifest_path)},
        },
    )
    expression_path = tmp_path / "expression.parquet"
    pd.DataFrame(values).to_parquet(expression_path, index=False)
    expression_report_path = tmp_path / "extraction_report.json"
    _write_json(
        expression_report_path,
        {
            "status": "complete",
            "archs4_expression_accessed": False,
            "expression_space": "tpm",
            "gene_order_sha256": sha256_lines(["G1", "G2", "G3", "G4"]),
            "hashes": {"expression_sha256": sha256_file(expression_path)},
        },
    )
    axes = tmp_path / "axes.npz"
    np.savez_compressed(
        axes,
        gene_names=np.asarray(["G1", "G2", "G3", "G4"]),
        score_gene_indices=np.asarray([0], dtype=np.int64),
        probe_gene_indices=np.asarray([3], dtype=np.int64),
    )
    protocol_path = tmp_path / "protocol.json"
    _write_json(
        protocol_path,
        {
            "status": "frozen_gtex_to_archs4_development_contract",
            "firewalls": {
                "archs4_lockbox_expression_access_before_candidate_freeze": False
            },
            "organ_selection": {"ordered_organs": ["brain", "liver"]},
            "expression_contract": {
                "axis_definitions_sha256": sha256_file(axes)
            },
            "strict_model_family": {"gene_count": 4},
        },
    )
    return Namespace(
        protocol=str(protocol_path),
        expected_protocol_sha256=sha256_file(protocol_path),
        expression_parquet=str(expression_path),
        expression_metadata=str(expression_report_path),
        manifest=str(manifest_path),
        manifest_report=str(manifest_report_path),
        axis_definitions=str(axes),
        output_dir=str(tmp_path / "router"),
        router_seed=271828,
        mask_token=-10.0,
        train_split="train",
        calibration_split="calibration",
        train_filter_column="balanced_train",
        split_column="split",
        sample_id_column="sample_id",
        organ_column="organ",
        group_column="series_group_id",
        mechanical_only=True,
    )


def test_refit_router_is_metric_free_and_target_hidden(tmp_path: Path) -> None:
    args = _fixture(tmp_path)
    report = refit(args)
    with np.load(Path(args.output_dir) / "gtex_k8_target_hidden_router.npz") as router:
        assert router["classes"].astype(str).tolist() == ["brain", "liver"]
        assert router["score_gene_indices"].tolist() == [0]
        assert router["coefficients"].shape == (1, 4)

    assert report["status"] == "complete"
    assert report["mechanical_only"] is True
    assert report["performance_metrics_generated"] is False
    assert report["internal_efficacy_scoring"] is False
    assert report["archs4_expression_accessed"] is False
    assert report["target_hiding"]["score_genes_masked_for_every_row"] is True


def test_refit_router_rejects_open_lockbox(tmp_path: Path) -> None:
    args = _fixture(tmp_path)
    protocol_path = Path(args.protocol)
    protocol = json.loads(protocol_path.read_text())
    protocol["firewalls"][
        "archs4_lockbox_expression_access_before_candidate_freeze"
    ] = True
    _write_json(protocol_path, protocol)
    args.expected_protocol_sha256 = sha256_file(protocol_path)

    with pytest.raises(ValueError, match="not closed"):
        refit(args)
