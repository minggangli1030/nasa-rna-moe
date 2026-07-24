from __future__ import annotations

import gzip
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

from build_gtex_to_archs4_cohort import build  # noqa: E402
from train_manifest import sha256_file  # noqa: E402


ORGANS = ("brain", "lung")
MAPPING = {
    "brain": {
        "broad_tissue": "Brain",
        "sites": ["Brain - Cortex"],
    },
    "lung": {
        "broad_tissue": "Lung",
        "sites": ["Lung"],
    },
}
OVERLAP = ("GTEX-OVER1", "GTEX-OVER2", "GTEX-OVER3", "GTEX-OVER4")


def _sample(donor: str, suffix: str) -> str:
    return f"{donor}-{suffix}-SM-X"


def _write_fixture(tmp_path: Path) -> dict[str, Path]:
    rows = []
    header = []
    for donor_index in range(12):
        donor = f"GTEX-D{donor_index:03d}"
        for suffix, broad, site in (
            ("B", "Brain", "Brain - Cortex"),
            ("L", "Lung", "Lung"),
        ):
            sample = _sample(donor, suffix)
            header.append(sample)
            rows.append(
                {
                    "SAMPID": sample,
                    "SMTS": broad,
                    "SMTSD": site,
                    "SMAFRZE": "RNASEQ",
                    "ANALYTE_TYPE": "RNA:Total RNA",
                    "SMGEBTCHT": "TruSeq.v1",
                }
            )
    for donor in OVERLAP:
        for suffix, broad, site in (
            ("B", "Brain", "Brain - Cortex"),
            ("L", "Lung", "Lung"),
        ):
            sample = _sample(donor, suffix)
            header.append(sample)
            rows.append(
                {
                    "SAMPID": sample,
                    "SMTS": broad,
                    "SMTSD": site,
                    "SMAFRZE": "RNASEQ",
                    "ANALYTE_TYPE": "RNA:Total RNA",
                    "SMGEBTCHT": "TruSeq.v1",
                }
            )
    excluded = _sample("GTEX-D999", "F")
    header.append(excluded)
    rows.append(
        {
            "SAMPID": excluded,
            "SMTS": "Skin",
            "SMTSD": "Cells - Cultured fibroblasts",
            "SMAFRZE": "RNASEQ",
            "ANALYTE_TYPE": "RNA:Total RNA",
            "SMGEBTCHT": "TruSeq.v1",
        }
    )
    attributes = tmp_path / "attributes.tsv"
    pd.DataFrame(rows).to_csv(attributes, sep="\t", index=False)
    counts = tmp_path / "counts.gct.gz"
    with gzip.open(counts, "wt") as handle:
        handle.write("#1.2\n")
        handle.write(f"1\t{len(header)}\n")
        handle.write("Name\tDescription\t" + "\t".join(header) + "\n")
        handle.write("ENSG1.1\tGENE1\t" + "\t".join(["1"] * len(header)) + "\n")
    protocol = {
        "schema_version": 1,
        "status": "draft_pending_reproducible_inventory_and_source_hashes",
        "organ_selection": {
            "ordered_candidate_organs": list(ORGANS),
            "minimum_gtex_header_present_donors": 10,
        },
        "gtex_development": {
            "sample_attributes_sha256": sha256_file(attributes),
            "counts_object_sha256": sha256_file(counts),
            "counts_object_size": counts.stat().st_size,
            "required_analyte_type": "RNA:Total RNA",
            "required_expression_batch_type": "TruSeq.v1",
            "exclude_historical_entex_donors_globally": list(OVERLAP),
        },
        "gtex_tissue_mapping": MAPPING,
        "firewalls": {
            "archs4_lockbox_expression_access_before_candidate_freeze": False,
            "gtex_is_external_evidence_for_new_candidate": False,
        },
    }
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(json.dumps(protocol, indent=2) + "\n")
    return {
        "attributes": attributes,
        "counts": counts,
        "protocol": protocol_path,
    }


def _args(fixture: dict[str, Path], output: Path) -> SimpleNamespace:
    return SimpleNamespace(
        sample_attributes=str(fixture["attributes"]),
        counts_gct=str(fixture["counts"]),
        protocol=str(fixture["protocol"]),
        expected_protocol_sha256=sha256_file(fixture["protocol"]),
        output_dir=str(output),
    )


def test_cohort_uses_header_only_exact_tissues_and_global_overlap_exclusion(tmp_path):
    fixture = _write_fixture(tmp_path)
    report = build(_args(fixture, tmp_path / "output"))
    cohort = pd.read_parquet(
        tmp_path / "output/gtex_development_cohort.parquet"
    )

    assert report["status"] == "provisional_complete"
    assert report["metadata_only"] is True
    assert report["expression_values_read"] is False
    assert report["gct_rows_read"] == 0
    assert report["archs4_expression_accessed"] is False
    assert report["samples"] == 24
    assert report["donors"] == 12
    assert report["by_organ"]["brain"]["donors"] == 12
    assert report["by_organ"]["lung"]["donors"] == 12
    assert set(cohort["organ"]) == set(ORGANS)
    assert not set(cohort["donor_id"]) & set(OVERLAP)
    assert not cohort["tissue_site"].str.contains("fibroblast").any()
    assert cohort["matrix_column_index"].is_unique
    assert (tmp_path / "output/COHORT_METADATA_COMPLETE").is_file()


def test_cohort_is_row_order_invariant(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    f1 = _write_fixture(first)
    f2 = _write_fixture(second)
    attrs = pd.read_csv(f2["attributes"], sep="\t")
    attrs.sample(frac=1.0, random_state=17).to_csv(
        f2["attributes"], sep="\t", index=False
    )
    protocol = json.loads(f2["protocol"].read_text())
    protocol["gtex_development"]["sample_attributes_sha256"] = sha256_file(
        f2["attributes"]
    )
    f2["protocol"].write_text(json.dumps(protocol, indent=2) + "\n")

    build(_args(f1, first / "output"))
    build(_args(f2, second / "output"))
    one = pd.read_parquet(first / "output/gtex_development_cohort.parquet")
    two = pd.read_parquet(second / "output/gtex_development_cohort.parquet")
    pd.testing.assert_frame_equal(one, two)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("protocol_hash", "protocol SHA256"),
        ("attributes_hash", "attributes SHA256"),
        ("counts_hash", "counts object"),
        ("broad_tissue", "unexpected broad tissue"),
        ("flag", "not all RNASEQ"),
        ("open_lockbox", "development/lockbox roles"),
    ],
)
def test_cohort_fails_closed_on_source_and_contract_changes(
    tmp_path, mutation, message
):
    fixture = _write_fixture(tmp_path)
    args = _args(fixture, tmp_path / "output")
    if mutation == "protocol_hash":
        args.expected_protocol_sha256 = "0" * 64
    elif mutation in {"attributes_hash", "broad_tissue", "flag"}:
        frame = pd.read_csv(fixture["attributes"], sep="\t")
        if mutation == "attributes_hash":
            frame.loc[0, "SMTS"] = "Changed"
        elif mutation == "broad_tissue":
            frame.loc[0, "SMTS"] = "Lung"
        else:
            frame.loc[0, "SMAFRZE"] = "EXCLUDE"
        frame.to_csv(fixture["attributes"], sep="\t", index=False)
        if mutation != "attributes_hash":
            protocol = json.loads(fixture["protocol"].read_text())
            protocol["gtex_development"]["sample_attributes_sha256"] = sha256_file(
                fixture["attributes"]
            )
            fixture["protocol"].write_text(json.dumps(protocol, indent=2) + "\n")
            args.expected_protocol_sha256 = sha256_file(fixture["protocol"])
    elif mutation == "counts_hash":
        with gzip.open(fixture["counts"], "at") as handle:
            handle.write("extra\n")
    elif mutation == "open_lockbox":
        protocol = json.loads(fixture["protocol"].read_text())
        protocol["firewalls"][
            "archs4_lockbox_expression_access_before_candidate_freeze"
        ] = True
        fixture["protocol"].write_text(json.dumps(protocol, indent=2) + "\n")
        args.expected_protocol_sha256 = sha256_file(fixture["protocol"])
    with pytest.raises(ValueError, match=message):
        build(args)
