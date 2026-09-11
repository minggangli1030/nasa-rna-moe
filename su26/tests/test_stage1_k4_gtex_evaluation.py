from __future__ import annotations

import gzip
import json
import sys
from argparse import Namespace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))

from extract_stage1_k4_gtex import extract, freeze_header  # noqa: E402
from audit_stage1_k4_gtex_overlap import audit  # noqa: E402
import evaluate_stage1_k4_gtex as gtex_evaluator  # noqa: E402
from stage1_k4_gtex_common import (  # noqa: E402
    ORGANS,
    deterministic_random_assignments,
    donor_bootstrap_comparison,
    donor_organ_means,
    equal_organ_mean,
    holm_adjust,
    sha256_file,
)


def _protocol(counts: Path) -> dict:
    return {
        "schema_version": 1,
        "status": "frozen",
        "authorization": {"requested_by_user": True},
        "one_time_expression_access": True,
        "evidence_role": "secondary_donor_controlled_validation",
        "claim_limit": "fixture",
        "source": {
            "counts_object": {
                "file_size": counts.stat().st_size,
                "sha256": sha256_file(counts),
            },
            "sample_attributes_sha256": "",
        },
        "model": {
            "training_seeds": [17, 42, 101],
            "candidate_code_commit": "e8c0383fd1833f180f26af56f09e83a5b3f676d9",
            "candidate_manifest_sha256": "0" * 64,
        },
        "estimand": {"organ_order": list(ORGANS)},
        "expression": {
            "minimum_nonzero_length_mapped_genes": 2,
            "missing_non_score_genes": "zero_fill",
            "gencode_gtf_sha256": {"v47": "", "v49": ""},
        },
        "controls": {"assigned_random_algorithm": "fixture"},
    }


def test_header_freeze_and_duplicate_symbol_tpm_extraction(tmp_path):
    counts = tmp_path / "counts.gct.gz"
    samples = ["GTEX-A-0001-SM-X", "GTEX-B-0001-SM-Y"]
    with gzip.open(counts, "wt") as handle:
        handle.write("#1.2\n")
        handle.write("4\t2\n")
        handle.write("Name\tDescription\t" + "\t".join(samples) + "\n")
        handle.write("ENSG1\tA\t10\t0\n")
        handle.write("ENSG2\tA\t5\t5\n")
        handle.write("ENSG3\tB\t5\t5\n")
        handle.write("ENSG4\tC\t0\t10\n")
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(json.dumps(_protocol(counts), sort_keys=True))
    cohort_path = tmp_path / "cohort.csv"
    pd.DataFrame(
        {
            "sample_id": samples,
            "donor_id": ["GTEX-A", "GTEX-B"],
            "organ": ["brain", "liver"],
            "tissue_site": ["Brain - Cortex", "Liver"],
        }
    ).to_csv(cohort_path, index=False)
    # The real cohort covers all organs. Add three metadata-only fixture rows
    # using already-present matrix samples would violate sample uniqueness, so
    # this focused extractor fixture temporarily uses the full organ contract
    # through two sample rows plus three additional matrix columns.
    extra = [
        ("GTEX-C-0001-SM-Z", "GTEX-C", "adipose"),
        ("GTEX-D-0001-SM-Q", "GTEX-D", "skeletal_muscle"),
        ("GTEX-E-0001-SM-R", "GTEX-E", "skin"),
    ]
    samples = samples + [row[0] for row in extra]
    with gzip.open(counts, "wt") as handle:
        handle.write("#1.2\n4\t5\n")
        handle.write("Name\tDescription\t" + "\t".join(samples) + "\n")
        handle.write("ENSG1.1\tOLD_A\t10\t0\t1\t1\t1\n")
        handle.write("ENSG2\tA\t5\t5\t1\t1\t1\n")
        handle.write("ENSG3\tB\t5\t5\t1\t1\t1\n")
        handle.write("ENSG4\tC\t0\t10\t1\t1\t1\n")
    protocol_path.write_text(json.dumps(_protocol(counts), sort_keys=True))
    cohort = pd.DataFrame(
        [
            (samples[0], "GTEX-A", "brain", "Brain - Cortex"),
            (samples[1], "GTEX-B", "liver", "Liver"),
            *[(sample, donor, organ, organ) for sample, donor, organ in extra],
            ("GTEX-X-0001-SM-E", "GTEX-X", "brain", "Brain - Cortex"),
        ],
        columns=["sample_id", "donor_id", "organ", "tissue_site"],
    )
    cohort.to_csv(cohort_path, index=False)
    attributes = tmp_path / "attributes.txt"
    pd.DataFrame(
        {
            "SAMPID": [*samples, "GTEX-X-0001-SM-E"],
            "SMAFRZE": [*(["RNASEQ"] * len(samples)), "EXCLUDE"],
        }
    ).to_csv(attributes, sep="\t", index=False)
    v47 = tmp_path / "v47.gtf.gz"
    v49 = tmp_path / "v49.gtf.gz"
    with gzip.open(v47, "wt") as handle:
        for stable_id, symbol in (
            ("ENSG1", "OLD_A"),
            ("ENSG2", "A"),
            ("ENSG3", "B"),
            ("ENSG4", "C"),
        ):
            handle.write(
                f'chr1\ttest\tgene\t1\t2\t.\t+\t.\t'
                f'gene_id "{stable_id}.1"; gene_name "{symbol}";\n'
            )
    with gzip.open(v49, "wt") as handle:
        for stable_id, symbol in (
            ("ENSG1", "A"),
            ("ENSG2", "A"),
            ("ENSG3", "B"),
            ("ENSG4", "C"),
        ):
            handle.write(
                f'chr1\ttest\tgene\t1\t2\t.\t+\t.\t'
                f'gene_id "{stable_id}.2"; gene_name "{symbol}";\n'
            )
    protocol = json.loads(protocol_path.read_text())
    protocol["source"]["sample_attributes_sha256"] = sha256_file(attributes)
    protocol["expression"]["gencode_gtf_sha256"] = {
        "v47": sha256_file(v47),
        "v49": sha256_file(v49),
    }
    protocol_path.write_text(json.dumps(protocol, sort_keys=True))
    header_dir = tmp_path / "header"
    freeze_header(
        Namespace(
            protocol=str(protocol_path),
            expected_protocol_sha256=sha256_file(protocol_path),
            counts_gct=str(counts),
            provisional_cohort=str(cohort_path),
            sample_attributes=str(attributes),
            output_dir=str(header_dir),
        )
    )
    genes = tmp_path / "genes.txt"
    genes.write_text("A\nB\nC\n")
    lengths = tmp_path / "lengths.csv"
    pd.DataFrame(
        {"gene_symbol": ["A", "B", "C"], "exon_length": [1000, 2000, 1000]}
    ).to_csv(lengths, index=False)
    axes = tmp_path / "axes.npz"
    np.savez(
        axes,
        gene_names=np.asarray(["A", "B", "C"]),
        score_gene_indices=np.asarray([0, 1], dtype=np.int64),
    )
    output = tmp_path / "extract"
    report = extract(
        Namespace(
            protocol=str(protocol_path),
            expected_protocol_sha256=sha256_file(protocol_path),
            counts_gct=str(counts),
            header_dir=str(header_dir),
            genes=str(genes),
            axis_definitions=str(axes),
            exon_lengths=str(lengths),
            gencode_v47_gtf=str(v47),
            gencode_v49_gtf=str(v49),
            output_dir=str(output),
            row_group_size=2,
        )
    )
    expression = pd.read_parquet(output / "expression.parquet")
    first = expression.set_index("sample_id").loc["GTEX-A-0001-SM-X"]
    np.testing.assert_allclose(
        first[["A", "B", "C"]].to_numpy(dtype=float),
        np.asarray([15.0, 2.5, 0.0]) / 17.5 * 1_000_000,
        rtol=2e-7,
    )
    assert report["duplicate_symbol_count"] == 0
    assert report["canonical_targets_with_multiple_source_rows"] == 1
    assert report["stable_id_symbol_renames"] == 1
    assert report["missing_score_genes"] == []
    assert report["log_transform_applied"] is False
    header_report = json.loads((header_dir / "header_report.json").read_text())
    assert header_report["matrix_membership_exclusions"]["samples"] == 1


def test_random_assignments_are_donor_organ_atomic_and_balanced():
    rows = []
    for organ in ORGANS:
        for index in range(11):
            for replicate in range(2):
                rows.append(
                    {
                        "donor_id": f"D{index}",
                        "organ": organ,
                        "sample_id": f"{organ}-{index}-{replicate}",
                    }
                )
    frame = pd.DataFrame(rows)
    labels = deterministic_random_assignments(frame, 17)
    frame["label"] = labels
    assert (
        frame.groupby(["donor_id", "organ"])["label"].nunique().max() == 1
    )
    for organ in ORGANS:
        counts = (
            frame[frame["organ"] == organ]
            .drop_duplicates(["donor_id", "organ"])["label"]
            .value_counts()
        )
        assert counts.max() - counts.min() <= 1
    np.testing.assert_array_equal(labels, deterministic_random_assignments(frame, 17))


def test_donor_first_equal_organ_estimand_and_bootstrap():
    rows = []
    for organ_index, organ in enumerate(ORGANS):
        rows.extend(
            [
                {
                    "donor_id": "shared",
                    "organ": organ,
                    "control": 10.0 + organ_index,
                    "candidate": 8.0 + organ_index,
                },
                {
                    "donor_id": f"{organ}-only",
                    "organ": organ,
                    "control": 12.0 + organ_index,
                    "candidate": 10.0 + organ_index,
                },
            ]
        )
    # Repeating a sample from one donor must not change donor-level mass.
    rows.append(dict(rows[0]))
    donor = donor_organ_means(pd.DataFrame(rows), ["control", "candidate"])
    assert equal_organ_mean(donor, "control") == 13.0
    result = donor_bootstrap_comparison(
        donor, "control", "candidate", draws=250, seed=7
    )
    assert result["absolute_improvement"] == 2.0
    assert result["absolute_ci95"][0] > 0
    assert result["one_sided_p"] == 1 / 251


def test_holm_adjustment_is_monotone_in_sorted_p_values():
    adjusted = holm_adjust({"a": 0.01, "b": 0.03, "c": 0.2})
    assert adjusted == {"a": 0.03, "b": 0.06, "c": 0.2}


def test_full_historical_overlap_audit(tmp_path):
    source = tmp_path / "historical.parquet"
    pd.DataFrame(
        {
            "geo_accession": ["GSM1", "GSM2", "GSM3"],
            "title": ["GTEx tissue", "ordinary study", "derived from GTEx"],
            "characteristics_ch1": [
                "donor_id: ENCDOAAA",
                "donor_id: other",
                "donor_id: ENCDOBBB",
            ],
        }
    ).to_parquet(source, index=False)
    report = audit(
        Namespace(
            historical_metadata=str(source),
            expected_sha256=sha256_file(source),
            expected_rows=2,
            expected_encode_donor=["ENCDOAAA", "ENCDOBBB"],
            output=str(tmp_path / "report.json"),
        )
    )
    assert report["gtex_related_rows"] == 2
    assert report["encode_donor_ids"] == ["ENCDOAAA", "ENCDOBBB"]


def test_evaluator_applies_frozen_gate_family(tmp_path, monkeypatch):
    protocol_path = tmp_path / "protocol.json"
    unused = tmp_path / "unused"
    unused.write_bytes(b"x")
    protocol = _protocol(unused)
    protocol["source"]["counts_object"] = {"file_size": 1, "sha256": "0" * 64}
    protocol["estimand"] = {
        "organ_order": list(ORGANS),
        "primary_unit": "donor within organ",
    }
    protocol_path.write_text(json.dumps(protocol, sort_keys=True))
    rows = []
    for donor_index in range(20):
        for organ in ORGANS:
            row = {
                "sample_id": f"{donor_index}-{organ}",
                "donor_id": f"D{donor_index}",
                "organ": organ,
                "tissue_site": organ,
                "router_predicted_organ": organ,
                "router_correct": True,
                "pooled__mse": 1.0 + donor_index / 1000,
                "pooled__residual_pearson": 0.1,
            }
            for seed_offset, seed in enumerate((17, 42, 101)):
                jitter = seed_offset / 1000
                conditions = {
                    "true_k4": (0.90 + jitter, 0.20),
                    "blind_k4": (0.92 + jitter, 0.18),
                    "pooled_adapter": (0.96 + jitter, 0.12),
                }
                for partition in (17, 42, 101):
                    conditions[f"random_p{partition}_assigned"] = (
                        0.99 + jitter,
                        0.11,
                    )
                    conditions[f"random_p{partition}_mapped"] = (
                        0.97 + jitter,
                        0.11,
                    )
                for condition, (mse, correlation) in conditions.items():
                    row[f"seed{seed}__{condition}__mse"] = mse
                    row[
                        f"seed{seed}__{condition}__residual_pearson"
                    ] = correlation
            rows.append(row)
    score_dir = tmp_path / "scores"
    score_dir.mkdir()
    scores = score_dir / "gtex_sample_scores.parquet"
    frame = pd.DataFrame(rows)
    frame.to_parquet(scores, index=False)
    report = {
        "status": "complete",
        "protocol_sha256": sha256_file(protocol_path),
        "score_cache_sha256": sha256_file(scores),
        "full_predictions_serialized": False,
        "sample_order_sha256": gtex_evaluator.sha256_lines(frame["sample_id"]),
    }
    (score_dir / "score_report.json").write_text(json.dumps(report))
    (score_dir / "SCORING_COMPLETE").touch()
    monkeypatch.setattr(gtex_evaluator, "BOOTSTRAP_DRAWS", 200)
    result = gtex_evaluator.evaluate(
        Namespace(
            protocol=str(protocol_path),
            expected_protocol_sha256=sha256_file(protocol_path),
            score_dir=str(score_dir),
            output_dir=str(tmp_path / "evaluation"),
        )
    )
    assert result["decision"] == "full_external_pass"
    assert result["all_gates_pass"] is True
