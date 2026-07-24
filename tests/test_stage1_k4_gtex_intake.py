import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))

from build_stage1_k4_gtex_intake import build_gtex_intake


ORGANS = ("adipose", "brain", "liver", "skeletal_muscle", "skin")
TISSUES = {
    "adipose": ("Adipose Tissue", "Adipose - Subcutaneous"),
    "brain": ("Brain", "Brain - Cortex"),
    "liver": ("Liver", "Liver"),
    "skeletal_muscle": ("Muscle", "Muscle - Skeletal"),
    "skin": ("Skin", "Skin - Sun Exposed (Lower leg)"),
}


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_fixture(tmp_path: Path):
    rows = []
    for index, organ in enumerate(ORGANS):
        broad, detailed = TISSUES[organ]
        donor = "GTEX-OVERLAP" if organ == "adipose" else f"GTEX-D{index}"
        rows.append({
            "SAMPID": f"{donor}-0126-SM-A{index}",
            "SMATSSCR": "",
            "SMPTHNTS": "",
            "SMRIN": "7.0",
            "SMTS": broad,
            "SMTSD": detailed,
            "SMUBRID": "UBERON:test",
            "SMTSISCH": "",
            "SMTSPAX": "",
            "SMGEBTCHT": "TruSeq.v1",
            "ANALYTE_TYPE": "RNA:Total RNA",
        })
    rows.extend([
        {
            **rows[1],
            "SAMPID": "GTEX-D1-0226-SM-B1",
            "SMTSD": "Brain - Spinal cord (cervical c-1)",
        },
        {
            **rows[4],
            "SAMPID": "GTEX-D4-0226-SM-B2",
            "SMTSD": "Cells - Cultured fibroblasts",
        },
        {
            **rows[2],
            "SAMPID": "BMS-X-0126-SM-B3",
        },
        {
            **rows[3],
            "SAMPID": "GTEX-D3-0226-SM-B4",
            "SMGEBTCHT": "NEBNext Small RNA Library Prep Set for Illumina",
        },
    ])
    sample_path = tmp_path / "samples.txt"
    pd.DataFrame(rows).to_csv(sample_path, sep="\t", index=False)

    subjects = []
    for donor in ["GTEX-OVERLAP", "GTEX-D1", "GTEX-D2", "GTEX-D3", "GTEX-D4"]:
        subjects.append({
            "SUBJID": donor,
            "SEX": "1",
            "AGE": "50-59",
            "DTHHRDY": "2",
        })
    subject_path = tmp_path / "subjects.txt"
    pd.DataFrame(subjects).to_csv(subject_path, sep="\t", index=False)

    sample_dd = tmp_path / "sample-dd.xlsx"
    subject_dd = tmp_path / "subject-dd.xlsx"
    sample_dd.write_bytes(b"sample dictionary")
    subject_dd.write_bytes(b"subject dictionary")

    historical_path = tmp_path / "historical.csv"
    pd.DataFrame([{
        "sample_id": "GSM1",
        "organ": "adipose",
        "series_group_id": "GSE1",
        "source_name": "adipose",
        "title": "GTEx tissue",
        "characteristics": "donor_id: ENCDOOVERLAP",
    }]).to_csv(historical_path, index=False)

    metadata_files = {}
    for label, path in {
        "sample_attributes": sample_path,
        "sample_dictionary": sample_dd,
        "subject_phenotypes": subject_path,
        "subject_dictionary": subject_dd,
    }.items():
        metadata_files[label] = {
            "file_size": path.stat().st_size,
            "sha256": _digest(path),
        }
    expected_before = {
        "samples": 5,
        "donors": 5,
        "by_organ": {
            organ: {"samples": 1, "donors": 1} for organ in ORGANS
        },
    }
    expected_after = {
        "samples": 4,
        "donors": 4,
        "by_organ": {
            organ: {
                "samples": 0 if organ == "adipose" else 1,
                "donors": 0 if organ == "adipose" else 1,
            }
            for organ in ORGANS
        },
    }
    protocol = {
        "protocol_name": "fixture",
        "metadata_only": True,
        "expression_values_read": False,
        "expression_file_downloaded": False,
        "external_lockbox_frozen": False,
        "ready_for_expression_access": False,
        "evidence_role": "secondary_donor_controlled_validation",
        "source_contract": {
            "release": {"analysis_release": "fixture"},
            "metadata_files": metadata_files,
            "expression_object_catalog_binding": {"downloaded": False},
        },
        "sample_selection_contract": {
            "required_analyte_type": "RNA:Total RNA",
            "required_expression_batch_type": "TruSeq.v1",
            "tissue_site_to_organ": {
                organ: [TISSUES[organ][1]] for organ in ORGANS
            },
        },
        "historical_overlap_contract": {
            "historical_manifest_sha256": _digest(historical_path),
            "expected_gtex_derived_rows": 1,
            "expected_series_group_ids": ["GSE1"],
            "encode_to_gtex_donor_crosswalk": {
                "ENCDOOVERLAP": "GTEX-OVERLAP"
            },
        },
        "expected_metadata_counts": {
            "before_overlap_exclusion": expected_before,
            "after_overlap_exclusion": expected_after,
        },
        "aggregation_contract": {"primary_unit": "donor within organ"},
        "health_interpretation": {"allowed_description": "fixture"},
        "expression_contract_status": {"status": "draft"},
        "remaining_gates": ["stay sealed"],
    }
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(json.dumps(protocol))
    return {
        "sample_attributes": sample_path,
        "sample_dictionary": sample_dd,
        "subject_phenotypes": subject_path,
        "subject_dictionary": subject_dd,
        "historical_manifest": historical_path,
        "protocol": protocol_path,
    }


def _args(paths: dict[str, Path], output: Path) -> argparse.Namespace:
    return argparse.Namespace(
        **{key: str(value) for key, value in paths.items()},
        expected_protocol_sha256=_digest(paths["protocol"]),
        code_commit="a" * 40,
        output_dir=str(output),
    )


def test_gtex_intake_excludes_overlapping_donor_and_keeps_expression_sealed(tmp_path):
    paths = _write_fixture(tmp_path)
    report = build_gtex_intake(_args(paths, tmp_path / "output"))
    assert report["counts"]["before_overlap_exclusion"]["samples"] == 5
    assert report["counts"]["after_overlap_exclusion"]["samples"] == 4
    assert report["counts"]["excluded_donors"] == 1
    assert report["ready_for_expression_access"] is False
    assert report["expression_values_read"] is False
    cohort = pd.read_csv(tmp_path / "output" / "gtex_v11_provisional_cohort.csv")
    assert "GTEX-OVERLAP" not in set(cohort["donor_id"])
    assert set(cohort["organ"]) == set(ORGANS) - {"adipose"}


def test_gtex_intake_rejects_metadata_hash_change(tmp_path):
    paths = _write_fixture(tmp_path)
    paths["sample_attributes"].write_text("changed")
    with pytest.raises(ValueError, match="size mismatch|SHA256 mismatch"):
        build_gtex_intake(_args(paths, tmp_path / "output"))
