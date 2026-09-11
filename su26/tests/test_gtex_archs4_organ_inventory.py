from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
for source_dir in (ROOT / "core", ROOT / "evaluation"):
    if str(source_dir) not in sys.path:
        sys.path.insert(0, str(source_dir))

from audit_gtex_archs4_organ_inventory import audit  # noqa: E402
from train_manifest import sha256_file  # noqa: E402


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _fixture(tmp_path: Path) -> dict[str, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    current_rows = [
        {
            "geo_accession": "GSM-old-id",
            "series_id": "GSE100",
            "organ": "brain",
            "tier": "high_confidence",
            "submission_date": "2024-01-01",
        },
        {
            "geo_accession": "GSM-old-series",
            "series_id": "GSE100",
            "organ": "brain",
            "tier": "high_confidence",
            "submission_date": "2024-01-01",
        },
        {
            "geo_accession": "GSM-brain-1",
            "series_id": "GSE201",
            "organ": "brain",
            "tier": "high_confidence",
            "submission_date": "2024-01-01",
        },
        {
            "geo_accession": "GSM-brain-2",
            "series_id": "GSE202",
            "organ": "brain",
            "tier": "high_confidence",
            "submission_date": "2024-01-02",
        },
        {
            "geo_accession": "GSM-lung-1",
            "series_id": "GSE301",
            "organ": "lung",
            "tier": "high_confidence",
            "submission_date": "2024-01-01",
        },
        {
            "geo_accession": "GSM-lung-2",
            "series_id": "GSE302",
            "organ": "lung",
            "tier": "high_confidence",
            "submission_date": "2024-01-02",
        },
        {
            "geo_accession": "GSM-kidney-1",
            "series_id": "GSE401",
            "organ": "kidney",
            "tier": "high_confidence",
            "submission_date": "2024-01-01",
        },
    ]
    current = pd.DataFrame(current_rows)[["geo_accession", "series_id"]]
    recovered = pd.DataFrame(current_rows)
    historical = pd.DataFrame(
        [{"geo_accession": "GSM-old-id", "series_id": "GSE100"}]
    )
    current_path = tmp_path / "current.parquet"
    recovered_path = tmp_path / "recovered.parquet"
    historical_path = tmp_path / "historical.parquet"
    current.to_parquet(current_path, index=False)
    recovered.to_parquet(recovered_path, index=False)
    historical.to_parquet(historical_path, index=False)

    ontology_path = tmp_path / "ontology.json"
    _write_json(
        ontology_path,
        {
            "organs": {
                "brain": {"uberon_id": "U1", "synonyms": ["brain"]},
                "kidney": {"uberon_id": "U2", "synonyms": ["kidney"]},
                "lung": {"uberon_id": "U3", "synonyms": ["lung"]},
            }
        },
    )
    recovery_source = tmp_path / "recover.py"
    recovery_source.write_text("# frozen synthetic recovery\n")
    recovery_report = tmp_path / "recovery_report.json"
    _write_json(
        recovery_report,
        {
            "n_samples": len(recovered),
            "ontology_sha256": sha256_file(ontology_path),
        },
    )
    gtex_report = tmp_path / "gtex_report.json"
    _write_json(
        gtex_report,
        {
            "metadata_only": True,
            "expression_values_read": False,
            "archs4_expression_accessed": False,
            "by_organ": {
                "brain": {"samples": 10, "donors": 10},
                "lung": {"samples": 10, "donors": 10},
            },
            "inventory_by_organ": {
                "brain": {"samples": 10, "donors": 10},
                "kidney": {"samples": 1, "donors": 1},
                "lung": {"samples": 10, "donors": 10},
            },
        },
    )
    protocol = tmp_path / "protocol.json"
    _write_json(
        protocol,
        {
            "organ_selection": {
                "outcome_independent": True,
                "ordered_candidate_organs": ["brain", "lung"],
                "minimum_gtex_header_present_donors": 2,
                "minimum_post_firewall_archs4_samples": 2,
                "minimum_post_firewall_archs4_connected_studies": 2,
            },
            "archs4_inventory_sources": {
                "current_human_metadata_sha256": sha256_file(current_path),
                "historical_v11_metadata_sha256": sha256_file(historical_path),
                "ontology_sha256": sha256_file(ontology_path),
                "label_recovery_source_sha256": sha256_file(recovery_source),
                "temporal_cutoff": "2021-11-13",
            },
        },
    )
    return {
        "current": current_path,
        "recovered": recovered_path,
        "historical": historical_path,
        "ontology": ontology_path,
        "recovery_source": recovery_source,
        "recovery_report": recovery_report,
        "gtex_report": gtex_report,
        "protocol": protocol,
    }


def _args(fixture: dict[str, Path], output: Path) -> SimpleNamespace:
    return SimpleNamespace(
        protocol=str(fixture["protocol"]),
        expected_protocol_sha256=sha256_file(fixture["protocol"]),
        gtex_cohort_report=str(fixture["gtex_report"]),
        current_metadata=str(fixture["current"]),
        historical_metadata=str(fixture["historical"]),
        ontology=str(fixture["ontology"]),
        recovery_source=str(fixture["recovery_source"]),
        recovered_labels=str(fixture["recovered"]),
        recovery_report=str(fixture["recovery_report"]),
        output_dir=str(output),
    )


def test_inventory_applies_historical_firewall_and_selects_by_threshold(tmp_path):
    fixture = _fixture(tmp_path)
    report = audit(_args(fixture, tmp_path / "output"))

    assert report["status"] == "complete"
    assert report["metadata_only"] is True
    assert report["expression_values_read"] is False
    assert report["archs4_expression_accessed"] is False
    assert report["selected_organs"] == ["brain", "lung"]
    assert report["selected_k"] == 2
    rows = {row["organ"]: row for row in report["inventory"]}
    assert rows["brain"]["post_firewall_archs4_samples"] == 2
    assert rows["brain"]["post_firewall_archs4_connected_studies"] == 2
    assert rows["kidney"]["passes_gtex_donors"] is False
    assert rows["kidney"]["selected"] is False
    assert report["firewall"]["historical_accessions"] == 1
    assert (tmp_path / "output/INVENTORY_COMPLETE").is_file()


def test_inventory_fails_if_recovered_rows_are_not_aligned(tmp_path):
    fixture = _fixture(tmp_path)
    recovered = pd.read_parquet(fixture["recovered"])
    recovered = recovered.iloc[::-1].reset_index(drop=True)
    recovered.to_parquet(fixture["recovered"], index=False)
    with pytest.raises(ValueError, match="row-aligned"):
        audit(_args(fixture, tmp_path / "output"))


def test_inventory_fails_if_source_hash_or_expected_selection_changes(tmp_path):
    fixture = _fixture(tmp_path)
    current = pd.read_parquet(fixture["current"])
    current.loc[0, "series_id"] = "GSE999"
    current.to_parquet(fixture["current"], index=False)
    with pytest.raises(ValueError, match="source SHA256"):
        audit(_args(fixture, tmp_path / "source-output"))

    fixture = _fixture(tmp_path / "selection")
    protocol = json.loads(fixture["protocol"].read_text())
    protocol["organ_selection"]["ordered_candidate_organs"] = ["brain"]
    _write_json(fixture["protocol"], protocol)
    with pytest.raises(ValueError, match="differs from candidate organ set"):
        audit(_args(fixture, tmp_path / "selection-output"))
