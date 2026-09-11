from __future__ import annotations

import hashlib
import json
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import pytest
import pyarrow.parquet as pq

from preprocessing.extract_manifest_expression import (
    ExtractionError,
    extract_manifest_expression,
)


def _write_h5(
    path: Path,
    genes: list[str],
    samples: list[str],
    expression: np.ndarray,
) -> None:
    with h5py.File(path, "w") as handle:
        handle.create_dataset("data/expression", data=np.asarray(expression))
        handle.create_dataset(
            "meta/genes/gene_symbol", data=np.asarray(genes, dtype="S")
        )
        handle.create_dataset(
            "meta/samples/geo_accession", data=np.asarray(samples, dtype="S")
        )


def _base_inputs(tmp_path: Path) -> tuple[Path, Path, Path, pd.DataFrame, np.ndarray]:
    # H5 order deliberately differs from manifest and canonical-gene order.
    genes = ["B", "A", "B", "C"]
    samples = ["H2", "H1", "H3"]
    expression = np.asarray(
        [
            [10, 20, 30],  # B row 1
            [40, 50, 60],  # A
            [1, 2, 3],     # B row 2 (must be summed, not silently duplicated)
            [70, 80, 90],  # C
        ],
        dtype=np.float32,
    )
    h5_path = tmp_path / "human.h5"
    _write_h5(h5_path, genes, samples, expression)

    canonical_path = tmp_path / "genes.txt"
    canonical_path.write_text("C\nB\nA\n")
    exon_path = tmp_path / "lengths.csv"
    pd.DataFrame(
        {"gene_symbol": ["A", "B", "C"], "exon_length": [1000, 2000, 500]}
    ).to_csv(exon_path, index=False)
    manifest = pd.DataFrame(
        {
            "sample_id": ["H1", "H3", "H2"],
            "organ": ["brain", "skin", "brain"],
            "series_group_id": ["G1", "G2", "G3"],
            "split": ["train", "test", "calibration"],
            "label_evidence": ["source", "source", "title"],
        }
    )
    return h5_path, canonical_path, exon_path, manifest, expression


def _run(
    manifest_path: Path,
    h5_path: Path,
    canonical_path: Path,
    exon_path: Path,
    output_dir: Path,
    *,
    qc_min_nonzero: int = 1,
) -> dict:
    return extract_manifest_expression(
        manifest_path,
        h5_path,
        canonical_path,
        exon_path,
        output_dir,
        batch_size=2,
        parquet_row_group_size=2,
        qc_min_nonzero=qc_min_nonzero,
    )


@pytest.mark.parametrize("manifest_format", ["csv", "parquet"])
def test_exact_extraction_preserves_manifest_order_and_computes_tpm_once(
    tmp_path: Path, manifest_format: str
) -> None:
    h5_path, canonical_path, exon_path, manifest, source = _base_inputs(tmp_path)
    manifest_path = tmp_path / f"manifest.{manifest_format}"
    if manifest_format == "csv":
        manifest.to_csv(manifest_path, index=False)
    else:
        manifest.to_parquet(manifest_path, index=False)

    output_dir = tmp_path / "out"
    report = _run(manifest_path, h5_path, canonical_path, exon_path, output_dir)

    table = pq.read_table(output_dir / "expression.parquet")
    assert table.schema.names == ["sample_id", "C", "B", "A"]
    output = table.to_pandas()
    assert output["sample_id"].tolist() == ["H1", "H3", "H2"]
    assert pd.read_parquet(output_dir / "manifest.parquet").equals(manifest)
    assert (output_dir / "genes.txt").read_text() == "C\nB\nA\n"

    # Construct the expected values independently.  B's two H5 rows are summed,
    # canonical order is C/B/A, then human lengths and one TPM normalization are applied.
    h5_column = {"H2": 0, "H1": 1, "H3": 2}
    expected_rows = []
    for sample_id in manifest["sample_id"]:
        index = h5_column[sample_id]
        counts = np.asarray(
            [source[3, index], source[0, index] + source[2, index], source[1, index]],
            dtype=np.float64,
        )
        rate = counts / np.asarray([0.5, 2.0, 1.0])
        expected_rows.append(rate / rate.sum() * 1_000_000.0)
    expected = np.asarray(expected_rows, dtype=np.float32)
    actual = output[["C", "B", "A"]].to_numpy(dtype=np.float32)
    np.testing.assert_allclose(actual, expected, rtol=1e-6, atol=1e-5)
    np.testing.assert_allclose(actual.sum(axis=1), 1_000_000.0, rtol=2e-6)

    assert report["status"] == "complete"
    assert report["expression_space"] == "tpm"
    assert report["gene_order_sha256"] == report["genes"]["ordered_gene_sha256"]
    assert report["sample_order_sha256"] == report["manifest"]["ordered_sample_id_sha256"]
    assert report["source_h5_sha256"] == hashlib.sha256(h5_path.read_bytes()).hexdigest()
    assert report["output_parquet_sha256"] == report["outputs"]["expression_parquet_sha256"]
    assert report["contract"]["tpm_applications"] == 1
    assert report["contract"]["log1p_applications"] == 0
    assert report["contract"]["log1p_owner"] == "trainer"
    assert report["contract"]["random_sampling_or_split"] is False
    assert report["expression"]["sample_order_matches_manifest"] is True
    assert report["source_h5"]["repeated_canonical_gene_rows"] == {"B": [0, 2]}
    assert report["qc"]["failures"] == []


def test_expression_artifact_and_content_hash_are_deterministic(tmp_path: Path) -> None:
    h5_path, canonical_path, exon_path, manifest, _ = _base_inputs(tmp_path)
    manifest_path = tmp_path / "manifest.csv"
    manifest.to_csv(manifest_path, index=False)

    first = _run(manifest_path, h5_path, canonical_path, exon_path, tmp_path / "first")
    second = _run(manifest_path, h5_path, canonical_path, exon_path, tmp_path / "second")

    first_bytes = (tmp_path / "first/expression.parquet").read_bytes()
    second_bytes = (tmp_path / "second/expression.parquet").read_bytes()
    assert hashlib.sha256(first_bytes).hexdigest() == hashlib.sha256(second_bytes).hexdigest()
    assert first["expression"]["expression_sha256"] == second["expression"]["expression_sha256"]
    assert (
        first["source_h5"]["selected_aggregated_counts_sha256"]
        == second["source_h5"]["selected_aggregated_counts_sha256"]
    )


def test_qc_is_precanonical_but_tpm_denominator_is_canonical(tmp_path: Path) -> None:
    h5_path = tmp_path / "human.h5"
    _write_h5(
        h5_path,
        ["A", "EXTRA"],
        ["H1"],
        np.asarray([[10.0], [90.0]], dtype=np.float32),
    )
    canonical_path = tmp_path / "genes.txt"
    canonical_path.write_text("A\n")
    exon_path = tmp_path / "lengths.csv"
    pd.DataFrame(
        {"gene_symbol": ["A", "EXTRA"], "exon_length": [1000, 1000]}
    ).to_csv(exon_path, index=False)
    manifest_path = tmp_path / "manifest.csv"
    pd.DataFrame(
        {
            "sample_id": ["H1"],
            "organ": ["brain"],
            "series_group_id": ["G1"],
            "split": ["train"],
        }
    ).to_csv(manifest_path, index=False)

    report = _run(
        manifest_path,
        h5_path,
        canonical_path,
        exon_path,
        tmp_path / "out",
        qc_min_nonzero=2,
    )
    output = pd.read_parquet(tmp_path / "out/expression.parquet")
    # EXTRA counts toward Stage-0-parity QC, but never enters canonical TPM.
    assert output.loc[0, "A"] == pytest.approx(1_000_000.0)
    assert report["qc"]["qc_gene_universe_n_genes"] == 2
    assert report["qc"]["canonical_tpm_n_genes"] == 1
    assert report["qc"]["qc_nonzero_genes_min"] == 2


def test_rejects_duplicate_or_missing_manifest_sample_ids(tmp_path: Path) -> None:
    h5_path, canonical_path, exon_path, manifest, _ = _base_inputs(tmp_path)

    duplicate = pd.concat([manifest, manifest.iloc[[0]]], ignore_index=True)
    duplicate_path = tmp_path / "duplicate.csv"
    duplicate.to_csv(duplicate_path, index=False)
    with pytest.raises(ExtractionError, match="duplicate values"):
        _run(duplicate_path, h5_path, canonical_path, exon_path, tmp_path / "dup-out")

    missing = manifest.copy()
    missing.loc[0, "sample_id"] = "NOT_IN_H5"
    missing_path = tmp_path / "missing.csv"
    missing.to_csv(missing_path, index=False)
    with pytest.raises(ExtractionError, match="missing 1 manifest sample IDs"):
        _run(missing_path, h5_path, canonical_path, exon_path, tmp_path / "missing-out")


def test_rejects_connected_group_split_leakage_but_allows_multi_organ_study(
    tmp_path: Path,
) -> None:
    h5_path, canonical_path, exon_path, manifest, _ = _base_inputs(tmp_path)

    split_leak = manifest.copy()
    split_leak.loc[1, "series_group_id"] = "G1"
    split_path = tmp_path / "split-leak.csv"
    split_leak.to_csv(split_path, index=False)
    with pytest.raises(ExtractionError, match="connected-study leakage"):
        _run(split_path, h5_path, canonical_path, exon_path, tmp_path / "split-out")

    organ_leak = manifest.copy()
    organ_leak.loc[1, "series_group_id"] = "G1"
    organ_leak.loc[1, "split"] = "train"
    organ_path = tmp_path / "organ-leak.csv"
    organ_leak.to_csv(organ_path, index=False)
    report = _run(organ_path, h5_path, canonical_path, exon_path, tmp_path / "organ-out")
    assert report["manifest"]["multi_organ_connected_group_count"] == 1


def test_rejects_duplicate_canonical_definitions_and_zero_fills_missing_h5_genes(
    tmp_path: Path,
) -> None:
    h5_path, canonical_path, exon_path, manifest, _ = _base_inputs(tmp_path)
    manifest_path = tmp_path / "manifest.csv"
    manifest.to_csv(manifest_path, index=False)

    canonical_path.write_text("C\nB\nB\nA\n")
    with pytest.raises(ExtractionError, match="canonical gene list contains duplicate"):
        _run(manifest_path, h5_path, canonical_path, exon_path, tmp_path / "gene-dup-out")

    canonical_path.write_text("C\nB\nA\nMISSING\n")
    extra_lengths = pd.read_csv(exon_path)
    extra_lengths.loc[len(extra_lengths)] = ["MISSING", 1000]
    extra_lengths.to_csv(exon_path, index=False)
    output_dir = tmp_path / "gene-missing-out"
    report = _run(manifest_path, h5_path, canonical_path, exon_path, output_dir)
    output = pd.read_parquet(output_dir / "expression.parquet")
    assert output.columns.tolist() == ["sample_id", "C", "B", "A", "MISSING"]
    np.testing.assert_array_equal(output["MISSING"].to_numpy(), 0.0)
    assert report["source_h5"]["all_canonical_genes_resolved"] is False
    assert report["source_h5"]["missing_canonical_genes"] == ["MISSING"]
    assert report["source_h5"]["missing_canonical_gene_policy"] == "zero_fill_stage0_parity"


def test_rejects_duplicate_h5_sample_accessions(tmp_path: Path) -> None:
    h5_path, canonical_path, exon_path, manifest, source = _base_inputs(tmp_path)
    _write_h5(h5_path, ["B", "A", "B", "C"], ["H2", "H1", "H1"], source)
    manifest_path = tmp_path / "manifest.csv"
    manifest.to_csv(manifest_path, index=False)
    with pytest.raises(ExtractionError, match="H5 geo_accession contains duplicate"):
        _run(manifest_path, h5_path, canonical_path, exon_path, tmp_path / "out")


def test_qc_failure_is_explicit_and_publishes_no_expression(tmp_path: Path) -> None:
    h5_path, canonical_path, exon_path, manifest, source = _base_inputs(tmp_path)
    # H1 is manifest row zero and H5 column one.
    source[:, 1] = 0
    _write_h5(h5_path, ["B", "A", "B", "C"], ["H2", "H1", "H3"], source)
    manifest_path = tmp_path / "manifest.csv"
    manifest.to_csv(manifest_path, index=False)
    output_dir = tmp_path / "out"

    with pytest.raises(ExtractionError, match="1 manifest samples failed QC"):
        _run(manifest_path, h5_path, canonical_path, exon_path, output_dir)

    assert not (output_dir / "expression.parquet").exists()
    assert not (output_dir / "manifest.parquet").exists()
    report = json.loads((output_dir / "extraction_report.json").read_text())
    assert report["status"] == "failed_qc"
    assert report["qc"]["n_failures"] == 1
    failure = report["qc"]["failures"][0]
    assert failure["sample_id"] == "H1"
    assert failure["organ"] == "brain"
    assert failure["series_group_id"] == "G1"
    assert failure["split"] == "train"
    assert failure["qc_nonzero_genes"] == 0
    assert "qc_nonzero_genes_below_threshold:0<1" in failure["reasons"]
    assert "nonpositive_or_nonfinite_tpm_denominator" in failure["reasons"]
