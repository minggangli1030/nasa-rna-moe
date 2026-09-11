import json
from pathlib import Path

import pandas as pd
import pytest

from evaluation.build_archs4_downstream_metadata_catalog import (
    build_catalog,
    canonical_lines_sha256,
    series_tokens,
    sha256_file,
    validate_exclusion_ledger,
)


ROOT = Path(__file__).resolve().parents[1]


def _protocol(manifest: Path, groups: list[str]) -> dict:
    tokens = sorted({token for group in groups for token in series_tokens(group)})
    return {
        "access_mode": "metadata_only_no_expression",
        "stage1_exclusion_firewall": {
            "manifest_sha256": sha256_file(manifest),
            "connected_study_groups": len(groups),
            "connected_study_group_sha256": canonical_lines_sha256(groups),
            "geo_series_tokens": len(tokens),
            "geo_series_token_sha256": canonical_lines_sha256(tokens),
        },
        "gtex_overlap_firewall": {
            "search_fields": [
                "geo_accession",
                "series_id",
                "source_name_ch1",
                "title",
                "characteristics_ch1",
            ]
        },
        "target_organs": ["adipose", "brain", "colon", "heart", "liver", "lung", "skeletal_muscle", "skin"],
        "organ_mapping": {
            "single_cell_threshold": 0.5,
            "ontology_sha256": sha256_file(ROOT / "data/ontology/uberon_organ_map.json"),
        },
    }


def test_real_stage1_firewall_binds_all_original_groups_and_tokens():
    protocol = json.loads(
        (ROOT / "artifacts/final_evaluation/archs4_downstream_benchmark/metadata_smoke_protocol.json").read_text()
    )
    ledger = validate_exclusion_ledger(
        ROOT / "artifacts/stage1_gtex_to_archs4/lockbox_run_73f9bd1/membership/lockbox_manifest.csv",
        protocol,
    )
    assert len(ledger["groups"]) == 64
    assert len(ledger["tokens"]) == 72
    assert "GSE277232" in ledger["tokens"]
    assert "GSE227136" in ledger["tokens"]


def test_catalog_excludes_prior_studies_and_explicit_gtex(tmp_path):
    manifest = tmp_path / "manifest.csv"
    pd.DataFrame({"series_id": ["GSE1,GSE2"]}).to_csv(manifest, index=False)
    protocol = _protocol(manifest, ["GSE1,GSE2"])
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(json.dumps(protocol))

    metadata = pd.DataFrame(
        {
            "geo_accession": ["GSM1", "GSM2", "GSM3", "GSM4"],
            "series_id": ["GSE2", "GSE3", "GSE4", "GSE5"],
            "source_name_ch1": ["lung tissue", "lung tissue", "lung tissue", "kidney tissue"],
            "title": ["control", "GTEx donor GTEX-ABCD", "control", "control"],
            "characteristics_ch1": ["tissue: lung"] * 3 + ["tissue: kidney"],
            "singlecellprobability": [0.0, 0.0, 0.0, 0.0],
        }
    )
    metadata_path = tmp_path / "metadata.csv"
    metadata.to_csv(metadata_path, index=False)
    output = tmp_path / "out"
    report = build_catalog(
        metadata_path,
        manifest,
        ROOT / "data/ontology/uberon_organ_map.json",
        protocol_path,
        output,
    )
    catalog = pd.read_parquet(output / "sample_catalog.parquet")
    assert report["expression_accessed"] is False
    assert report["n_eligible_samples"] == 1
    assert catalog.set_index("geo_accession").loc["GSM1", "catalog_decision"] == "stage1_series_overlap"
    assert catalog.set_index("geo_accession").loc["GSM2", "catalog_decision"] == "explicit_gtex_overlap"
    assert catalog.set_index("geo_accession").loc["GSM3", "catalog_decision"] == "eligible_metadata_only"
    assert catalog.set_index("geo_accession").loc["GSM4", "catalog_decision"] == "outside_target_organs"
    assert (output / "IMMUTABLE_SHA256SUMS").exists()


def test_exclusion_ledger_fails_closed_on_manifest_change(tmp_path):
    manifest = tmp_path / "manifest.csv"
    pd.DataFrame({"series_id": ["GSE1"]}).to_csv(manifest, index=False)
    protocol = _protocol(manifest, ["GSE1"])
    pd.DataFrame({"series_id": ["GSE999"]}).to_csv(manifest, index=False)
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        validate_exclusion_ledger(manifest, protocol)
