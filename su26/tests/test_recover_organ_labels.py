"""Unit tests for the Stage 1 organ label-recovery analyzer.

These exercise characteristics parsing, ontology normalization, disease/cell-source
separation, tier assignment, and the end-to-end recover() outputs with synthetic
metadata only (no H5, no expression data). They run against the real frozen ontology
map so the map itself is validated.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evaluation"))

import recover_organ_labels as rol  # noqa: E402

ONTOLOGY_PATH = Path(__file__).resolve().parents[1] / "data" / "ontology" / "uberon_organ_map.json"


@pytest.fixture(scope="module")
def ontology():
    return rol.load_ontology(ONTOLOGY_PATH)


def classify(ontology, source="", title="", characteristics="", sc_prob=0.0):
    return rol.classify_row(source, title, characteristics, sc_prob, ontology, 0.5)


def test_parse_characteristics_splits_tab_and_colon():
    kv = rol.parse_characteristics("tissue: liver\tage: 55\tsex: M")
    assert kv == {"tissue": "liver", "age": "55", "sex": "M"}


def test_parse_characteristics_first_key_wins_and_skips_bad_tokens():
    kv = rol.parse_characteristics("tissue: liver\tno_colon_here\ttissue: kidney")
    assert kv["tissue"] == "liver"
    assert "no_colon_here" not in kv


def test_parse_characteristics_splits_archs4_comma_encoding():
    kv = rol.parse_characteristics(
        "tissue: liver,disease state: normal,age: 55,description: left, lateral"
    )
    assert kv == {
        "tissue": "liver",
        "disease state": "normal",
        "age": "55",
        "description": "left, lateral",
    }


def test_characteristics_tissue_is_high_confidence(ontology):
    r = classify(ontology, source="patient 12", characteristics="tissue: liver\tage: 40")
    assert r["organ"] == "liver"
    assert r["uberon_id"] == "UBERON:0002107"
    assert r["tier"] == "high_confidence"
    assert r["evidence"] == "characteristics_tissue"


def test_source_name_only_is_high_confidence(ontology):
    r = classify(ontology, source="brain", characteristics="library type: single-end")
    assert r["organ"] == "brain"
    assert r["tier"] == "high_confidence"
    assert r["evidence"] == "source_name"


def test_title_only_is_downgraded_to_ambiguous(ontology):
    r = classify(ontology, source="sample A", title="human colon replicate 2")
    assert r["organ"] == "colon"
    assert r["tier"] == "ambiguous"
    assert "weak_title_only_evidence" in r["all_reasons"]


def test_cell_line_flag_routes_to_ambiguous(ontology):
    r = classify(ontology, source="liver", characteristics="cell line: HepG2")
    assert r["organ"] == "liver"
    assert r["flag_cell_source"] is True
    assert r["tier"] == "ambiguous"
    assert "cell_source" in r["all_reasons"]


def test_tumor_flag_routes_to_ambiguous(ontology):
    r = classify(ontology, source="lung", characteristics="tissue: lung\tdiagnosis: adenocarcinoma")
    assert r["organ"] == "lung"
    assert r["flag_tumor"] is True
    assert r["tier"] == "ambiguous"


def test_single_cell_probability_flag(ontology):
    r = classify(ontology, source="brain", sc_prob=0.9)
    assert r["flag_single_cell"] is True
    assert r["tier"] == "ambiguous"


def test_cross_field_conflict_is_ambiguous(ontology):
    r = classify(ontology, source="liver", title="kidney sample")
    assert r["tier"] == "ambiguous"
    assert "cross_field_conflict" in r["all_reasons"]
    assert r["all_matched_organs"] == "kidney|liver"


def test_multiple_organs_in_characteristics_is_ambiguous(ontology):
    r = classify(ontology, characteristics="tissue: liver and kidney")
    assert r["organ"] == ""
    assert r["tier"] == "ambiguous"
    assert r["evidence"] == "conflict_characteristics"


def test_no_match_is_unlabeled(ontology):
    r = classify(ontology, source="whole blood", characteristics="cell type: PBMC")
    assert r["organ"] == ""
    assert r["tier"] == "unlabeled"
    assert r["review_reason"] == "no_anatomy_match"


def test_adjacent_anatomy_routes_to_ambiguous(ontology):
    # liver label but a bile-duct (adjacent) mention should flag boundary tissue.
    r = classify(ontology, source="liver", title="liver and bile duct region")
    assert r["organ"] == "liver"
    assert "adjacent_anatomy" in r["all_reasons"]
    assert r["tier"] == "ambiguous"


def test_disease_nontumor_routes_to_ambiguous(ontology):
    r = classify(ontology, source="liver", characteristics="tissue: liver\tcondition: cirrhosis")
    assert r["flag_disease"] is True
    assert r["flag_tumor"] is False
    assert r["tier"] == "ambiguous"
    assert "disease_nontumor" in r["all_reasons"]


@pytest.mark.parametrize(
    ("source", "title", "characteristics", "expected_flag"),
    [
        ("brain", "Human_GBM_RNA", "tissue: brain", "flag_tumor"),
        (
            "adipose-derived mesenchymal stem cells",
            "control",
            "tissue: adipose-derived mesenchymal stem cells",
            "flag_cell_source",
        ),
        ("liver", "snRNA-seq_human_healthy_rep1", "tissue: liver", "flag_assay_mismatch"),
        ("liver", "mice wt rep1", "tissue: liver,strain: C57/BL", "flag_nonhuman"),
        (
            "skin",
            "control",
            "tissue: skin,disease: thyroid-associated ophthalmopathy",
            "flag_disease",
        ),
    ],
)
def test_round1_review_failure_modes_are_excluded(
    ontology, source, title, characteristics, expected_flag
):
    result = classify(
        ontology,
        source=source,
        title=title,
        characteristics=characteristics,
    )
    assert result[expected_flag] is True
    assert result["tier"] == "ambiguous"


def test_recover_end_to_end(tmp_path, ontology):
    rows = [
        # high-confidence characteristics
        ("GSM1", "GSE1", "patient", "liver donor", "tissue: liver", 0.01),
        # high-confidence source_name
        ("GSM2", "GSE2", "brain", "b1", "library type: single-end", 0.02),
        # cell line -> ambiguous
        ("GSM3", "GSE3", "liver", "hep", "cell line: HepG2", 0.03),
        # tumor -> ambiguous
        ("GSM4", "GSE4", "lung", "l1", "tissue: lung\tdx: carcinoma", 0.02),
        # unlabeled
        ("GSM5", "GSE5", "whole blood", "w1", "cell type: PBMC", 0.05),
        # single cell -> ambiguous
        ("GSM6", "GSE6", "brain", "sc", "tissue: brain", 0.95),
    ]
    meta = pd.DataFrame(
        rows,
        columns=["geo_accession", "series_id", "source_name_ch1", "title",
                 "characteristics_ch1", "singlecellprobability"],
    )
    meta_path = tmp_path / "meta.parquet"
    meta.to_parquet(meta_path, index=False)

    args = rol.argparse.Namespace(
        metadata=str(meta_path),
        ontology=str(ONTOLOGY_PATH),
        output_dir=str(tmp_path / "out"),
        single_cell_threshold=0.5,
        min_training_rows=1,
        min_series=1,
        per_reason=25,
    )
    report = rol.recover(args)

    assert report["n_samples"] == 6
    assert report["tier_counts"]["high_confidence"] == 2
    assert report["tier_counts"]["unlabeled"] == 1
    assert report["tier_counts"]["ambiguous"] == 3

    out = Path(args.output_dir)
    assert (out / "recovered_labels.parquet").exists()
    assert (out / "tier_summary.csv").exists()
    assert (out / "pi_ambiguity_sheet.csv").exists()
    assert (out / "recovery_report.json").exists()

    summary = pd.read_csv(out / "tier_summary.csv")
    assert set(["brain", "liver"]).issubset(set(summary["organ"]))
    sheet = pd.read_csv(out / "pi_ambiguity_sheet.csv")
    assert len(sheet) == 3  # the three ambiguous rows


def test_recover_is_deterministic(tmp_path, ontology):
    meta = pd.DataFrame(
        [("GSM1", "GSE1", "liver", "t", "tissue: liver", 0.0)],
        columns=["geo_accession", "series_id", "source_name_ch1", "title",
                 "characteristics_ch1", "singlecellprobability"],
    )
    meta_path = tmp_path / "meta.parquet"
    meta.to_parquet(meta_path, index=False)
    hashes = []
    for i in range(2):
        args = rol.argparse.Namespace(
            metadata=str(meta_path), ontology=str(ONTOLOGY_PATH),
            output_dir=str(tmp_path / f"out{i}"), single_cell_threshold=0.5,
            min_training_rows=1, min_series=1, per_reason=25,
        )
        report = rol.recover(args)
        hashes.append(report["high_confidence_sample_id_sha256"])
    assert hashes[0] == hashes[1]
    assert hashes[0] != ""
