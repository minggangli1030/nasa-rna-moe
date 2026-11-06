from __future__ import annotations

import json
import shutil
import sys
from argparse import Namespace
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))
sys.path.insert(0, str(ROOT / "evaluation"))

import verify_stage1_k4_development_data as firewall  # noqa: E402
from train_manifest import sha256_file, sha256_lines  # noqa: E402


def test_verifies_physically_development_only_expression(tmp_path, monkeypatch):
    source = tmp_path / "source.parquet"
    frame = pd.DataFrame(
        {
            "sample_id": ["s1", "s2", "s3"],
            "utility_split": ["train", "train", "calibration"],
            "split": ["train", "train", "calibration"],
            "organ": ["brain", "liver", "skin"],
            "series_group_id": ["g1", "g2", "g3"],
        }
    )
    frame.to_parquet(source, index=False)
    data_root = tmp_path / "development"
    data_root.mkdir()
    shutil.copyfile(source, data_root / "manifest.parquet")
    genes = ["gene1", "gene2"]
    (data_root / "genes.txt").write_text("\n".join(genes) + "\n")
    pq.write_table(
        pa.table(
            {
                "sample_id": frame["sample_id"].tolist(),
                "gene1": [1.0, 2.0, 3.0],
                "gene2": [4.0, 5.0, 6.0],
            }
        ),
        data_root / "expression.parquet",
    )
    monkeypatch.setattr(firewall, "EXPECTED_SOURCE_PARTITION_SHA256", sha256_file(source))
    monkeypatch.setattr(firewall, "EXPECTED_EXTRACTOR_SHA256", "e" * 64)
    monkeypatch.setattr(firewall, "EXPECTED_CANONICAL_GENES_SHA256", "g" * 64)
    monkeypatch.setattr(firewall, "EXPECTED_EXON_LENGTHS_SHA256", "l" * 64)
    monkeypatch.setattr(firewall, "EXPECTED_FIT_ROWS", 3)
    monkeypatch.setattr(firewall, "EXPECTED_TRAIN_ROWS", 2)
    monkeypatch.setattr(firewall, "EXPECTED_CALIBRATION_ROWS", 1)
    monkeypatch.setattr(firewall, "EXPECTED_GENES", 2)
    extraction = {
        "status": "complete",
        "expression_space": "tpm",
        "expression": {
            "n_requested_samples": 3,
            "n_published_samples": 3,
            "n_genes": 2,
            "sample_order_matches_manifest": True,
        },
        "inputs": {
            "manifest_file_sha256": sha256_file(source),
            "extractor_sha256": "e" * 64,
            "canonical_genes_file_sha256": "g" * 64,
            "human_exon_lengths_file_sha256": "l" * 64,
        },
        "contract": {
            "random_sampling_or_split": False,
            "silent_sample_drops": False,
            "log1p_applications": 0,
            "tpm_applications": 1,
        },
        "source_h5": {
            "all_manifest_samples_resolved_exactly_once": True,
            "selected_aggregated_counts_sha256": "c" * 64,
        },
        "outputs": {
            "expression_parquet_sha256": sha256_file(
                data_root / "expression.parquet"
            ),
            "manifest_parquet_sha256": sha256_file(data_root / "manifest.parquet"),
            "genes_file_sha256": sha256_file(data_root / "genes.txt"),
        },
    }
    (data_root / "extraction_report.json").write_text(json.dumps(extraction))

    report = firewall.verify(
        Namespace(data_root=str(data_root), source_partition_manifest=str(source))
    )

    assert report["status"] == "complete"
    assert report["test_rows_present"] is False
    assert report["hashes"]["ordered_sample_ids_sha256"] == sha256_lines(
        ["s1", "s2", "s3"]
    )
    assert (data_root / "FIREWALL_VERIFIED").is_file()
