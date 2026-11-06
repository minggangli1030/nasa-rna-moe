from __future__ import annotations

import gzip
import json
from argparse import Namespace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
EVALUATION = ROOT / "evaluation"
import sys

if str(EVALUATION) not in sys.path:
    sys.path.insert(0, str(EVALUATION))

from extract_gtex_to_archs4_training_expression import extract  # noqa: E402
from stage1_k4_gtex_common import sha256_file, sha256_lines  # noqa: E402


def _write_gtf(path: Path) -> None:
    with gzip.open(path, "wt") as handle:
        handle.write(
            'chr1\ttest\tgene\t1\t10\t.\t+\t.\tgene_id "ENSG1.1"; '
            'gene_name "GENE1";\n'
        )
        handle.write(
            'chr1\ttest\tgene\t20\t30\t.\t+\t.\tgene_id "ENSG2.1"; '
            'gene_name "GENE2";\n'
        )


def _fixture(tmp_path: Path) -> Namespace:
    counts = tmp_path / "counts.gct.gz"
    with gzip.open(counts, "wt") as handle:
        handle.write("#1.2\n")
        handle.write("2\t2\n")
        handle.write("Name\tDescription\tS1\tS2\n")
        handle.write("ENSG1.1\tGENE1\t10\t30\n")
        handle.write("ENSG2.1\tGENE2\t20\t10\n")

    cohort = pd.DataFrame(
        {
            "sample_id": ["S1", "S2"],
            "donor_id": ["D1", "D2"],
            "organ": ["brain", "liver"],
            "tissue_site": ["Brain", "Liver"],
            "matrix_column_index": [0, 1],
        }
    )
    cohort_path = tmp_path / "cohort.parquet"
    cohort.to_parquet(cohort_path, index=False)

    genes = tmp_path / "genes.txt"
    genes.write_text("GENE1\nGENE2\n")
    lengths = tmp_path / "lengths.csv"
    lengths.write_text("gene_symbol,exon_length\nGENE1,1000\nGENE2,2000\n")
    axes = tmp_path / "axes.npz"
    np.savez_compressed(
        axes,
        gene_names=np.asarray(["GENE1", "GENE2"]),
        score_gene_indices=np.asarray([0], dtype=np.int64),
    )
    v47 = tmp_path / "v47.gtf.gz"
    v49 = tmp_path / "v49.gtf.gz"
    _write_gtf(v47)
    _write_gtf(v49)

    protocol = {
        "status": "frozen_gtex_to_archs4_development_contract",
        "firewalls": {
            "archs4_lockbox_expression_access_before_candidate_freeze": False
        },
        "organ_selection": {"ordered_organs": ["brain", "liver"]},
        "gtex_development": {
            "counts_object_size": counts.stat().st_size,
            "counts_object_sha256": sha256_file(counts),
            "sealed_cohort_sha256": sha256_file(cohort_path),
            "sealed_samples": 2,
            "sealed_donors": 2,
            "sealed_sample_ids_sha256": sha256_lines(["S1", "S2"]),
            "matrix_header_sample_ids_sha256": sha256_lines(["S1", "S2"]),
            "matrix_gene_rows": 2,
            "matrix_sample_columns": 2,
        },
        "strict_model_family": {"gene_count": 2},
        "expression_contract": {
            "canonical_genes_sha256": sha256_file(genes),
            "axis_definitions_sha256": sha256_file(axes),
            "exon_lengths_sha256": sha256_file(lengths),
            "gencode_gtf_sha256": {
                "v47": sha256_file(v47),
                "v49": sha256_file(v49),
            },
            "expected_structurally_absent_canonical_genes": [],
            "externally_unavailable_score_genes": [],
            "missing_non_score_genes": "zero_fill",
            "minimum_nonzero_length_mapped_genes": 1,
        },
    }
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(json.dumps(protocol))
    return Namespace(
        protocol=str(protocol_path),
        expected_protocol_sha256=sha256_file(protocol_path),
        counts_gct=str(counts),
        sealed_cohort=str(cohort_path),
        genes=str(genes),
        axis_definitions=str(axes),
        exon_lengths=str(lengths),
        gencode_v47_gtf=str(v47),
        gencode_v49_gtf=str(v49),
        output_dir=str(tmp_path / "output"),
        row_group_size=1,
    )


def test_extracts_unlogged_canonical_tpm(tmp_path: Path) -> None:
    args = _fixture(tmp_path)
    report = extract(args)
    expression = pd.read_parquet(Path(args.output_dir) / "expression.parquet")

    assert report["status"] == "complete"
    assert report["archs4_expression_accessed"] is False
    assert report["expression_space"] == "tpm"
    assert report["log_transform_applied"] is False
    assert expression["sample_id"].tolist() == ["S1", "S2"]
    assert np.allclose(expression[["GENE1", "GENE2"]].sum(axis=1), 1_000_000)
    assert expression.loc[0, "GENE1"] == pytest.approx(500_000)
    assert expression.loc[1, "GENE1"] == pytest.approx(857_142.875)


def test_rejects_open_archs4_lockbox(tmp_path: Path) -> None:
    args = _fixture(tmp_path)
    protocol_path = Path(args.protocol)
    protocol = json.loads(protocol_path.read_text())
    protocol["firewalls"][
        "archs4_lockbox_expression_access_before_candidate_freeze"
    ] = True
    protocol_path.write_text(json.dumps(protocol))
    args.expected_protocol_sha256 = sha256_file(protocol_path)

    with pytest.raises(ValueError, match="does not close"):
        extract(args)


def test_rejects_unbound_cohort(tmp_path: Path) -> None:
    args = _fixture(tmp_path)
    cohort = pd.read_parquet(args.sealed_cohort)
    cohort.loc[0, "donor_id"] = "CHANGED"
    cohort.to_parquet(args.sealed_cohort, index=False)

    with pytest.raises(ValueError, match="cohort differs"):
        extract(args)
