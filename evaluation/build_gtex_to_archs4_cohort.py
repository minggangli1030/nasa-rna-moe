#!/usr/bin/env python3
"""Build the exact-header GTEx development cohort for clean organ training.

Only GTEx metadata and the three-line RNASeQC GCT preamble/header are read. The
program never opens a gene-expression row and never accepts an ARCHS4 expression
artifact.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import re
from pathlib import Path
from typing import Any

import pandas as pd

from stage1_k4_gtex_common import sha256_file, sha256_lines


ALLOWED_PROTOCOL_STATUS = {
    "draft_pending_reproducible_inventory_and_source_hashes",
    "frozen_gtex_to_archs4_development_contract",
}
REQUIRED_COLUMNS = {
    "SAMPID",
    "SMTS",
    "SMTSD",
    "SMAFRZE",
    "ANALYTE_TYPE",
    "SMGEBTCHT",
}
SAMPLE_RE = re.compile(r"^(?P<donor>GTEX-[A-Z0-9]+)(?:-[A-Za-z0-9]+)+-SM-[A-Za-z0-9]+$")


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _atomic_parquet(frame: pd.DataFrame, path: Path) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_parquet(temporary, index=False)
    os.replace(temporary, path)


def _read_header(path: Path) -> tuple[int, int, list[str]]:
    with gzip.open(path, "rt") as handle:
        version = handle.readline().rstrip("\n")
        dimensions = handle.readline().rstrip("\n").split("\t")
        header = handle.readline().rstrip("\n").split("\t")
    if version != "#1.2":
        raise ValueError("GTEx counts object has an unsupported GCT version")
    if len(dimensions) != 2:
        raise ValueError("GTEx counts object has an invalid dimensions line")
    gene_rows, sample_count = map(int, dimensions)
    if header[:2] != ["Name", "Description"]:
        raise ValueError("GTEx counts header lacks Name and Description")
    sample_ids = header[2:]
    if len(sample_ids) != sample_count or len(set(sample_ids)) != sample_count:
        raise ValueError("GTEx counts sample header count or uniqueness mismatch")
    return gene_rows, sample_count, sample_ids


def _site_lookup(
    organs: tuple[str, ...], mapping: dict[str, Any]
) -> tuple[dict[str, str], dict[str, str]]:
    if tuple(mapping) != organs:
        raise ValueError("GTEx tissue mapping order differs from organ order")
    site_to_organ: dict[str, str] = {}
    expected_broad: dict[str, str] = {}
    for organ in organs:
        spec = mapping[organ]
        broad = str(spec["broad_tissue"])
        sites = [str(value) for value in spec["sites"]]
        if not broad or not sites or len(set(sites)) != len(sites):
            raise ValueError(f"invalid GTEx tissue mapping for {organ}")
        expected_broad[organ] = broad
        for site in sites:
            if site in site_to_organ:
                raise ValueError(f"GTEx site is mapped twice: {site}")
            site_to_organ[site] = organ
    return site_to_organ, expected_broad


def build(args: argparse.Namespace) -> dict[str, Any]:
    protocol_path = Path(args.protocol)
    if sha256_file(protocol_path) != args.expected_protocol_sha256:
        raise ValueError("GTEx-to-ARCHS4 protocol SHA256 mismatch")
    protocol = json.loads(protocol_path.read_text())
    status = protocol.get("status")
    if status not in ALLOWED_PROTOCOL_STATUS:
        raise ValueError("protocol is neither a recognized draft nor frozen")
    firewalls = protocol.get("firewalls", {})
    if (
        firewalls.get("archs4_lockbox_expression_access_before_candidate_freeze")
        is not False
        or firewalls.get("gtex_is_external_evidence_for_new_candidate") is not False
    ):
        raise ValueError("protocol does not enforce the development/lockbox roles")

    development = protocol["gtex_development"]
    attributes_path = Path(args.sample_attributes)
    counts_path = Path(args.counts_gct)
    if sha256_file(attributes_path) != development["sample_attributes_sha256"]:
        raise ValueError("GTEx sample attributes SHA256 mismatch")
    if counts_path.stat().st_size != int(development["counts_object_size"]):
        raise ValueError("GTEx counts object size mismatch")
    if sha256_file(counts_path) != development["counts_object_sha256"]:
        raise ValueError("GTEx counts object SHA256 mismatch")

    gene_rows, matrix_samples, header_ids = _read_header(counts_path)
    header_index = {sample_id: index for index, sample_id in enumerate(header_ids)}
    attributes = pd.read_csv(
        attributes_path,
        sep="\t",
        dtype=str,
        keep_default_na=False,
        low_memory=False,
    )
    missing = sorted(REQUIRED_COLUMNS - set(attributes.columns))
    if missing:
        raise ValueError(f"GTEx sample attributes lack columns: {missing}")
    if attributes["SAMPID"].duplicated().any():
        raise ValueError("GTEx sample attributes repeat SAMPID")

    organs = tuple(protocol["organ_selection"]["ordered_candidate_organs"])
    if len(organs) < 2 or len(set(organs)) != len(organs):
        raise ValueError("protocol candidate organ order is invalid")
    site_to_organ, expected_broad = _site_lookup(
        organs, protocol["gtex_tissue_mapping"]
    )
    selected = attributes[
        attributes["SAMPID"].isin(header_index)
        & attributes["SAMPID"].str.startswith("GTEX-")
        & attributes["ANALYTE_TYPE"].eq(development["required_analyte_type"])
        & attributes["SMGEBTCHT"].eq(
            development["required_expression_batch_type"]
        )
        & attributes["SMTSD"].isin(site_to_organ)
    ].copy()
    selected["organ"] = selected["SMTSD"].map(site_to_organ)
    broad_mismatch = selected[
        selected.apply(
            lambda row: row["SMTS"] != expected_broad[str(row["organ"])], axis=1
        )
    ]
    if not broad_mismatch.empty:
        raise ValueError("GTEx detailed tissue has an unexpected broad tissue")
    if not selected["SMAFRZE"].eq("RNASEQ").all():
        raise ValueError("header-present selected GTEx samples are not all RNASEQ")

    donors = []
    for sample_id in selected["SAMPID"].astype(str):
        match = SAMPLE_RE.fullmatch(sample_id)
        if match is None:
            raise ValueError(f"unexpected GTEx sample ID: {sample_id}")
        donors.append(match.group("donor"))
    selected["donor_id"] = donors
    excluded_donors = set(
        str(value) for value in development["exclude_historical_entex_donors_globally"]
    )
    overlap_mask = selected["donor_id"].isin(excluded_donors)
    observed_overlap = set(selected.loc[overlap_mask, "donor_id"])
    missing_overlap = sorted(excluded_donors - observed_overlap)
    if missing_overlap:
        raise ValueError(
            f"one or more frozen EN-TEx overlap donors are absent: {missing_overlap}"
        )
    selected = selected.loc[~overlap_mask].copy()
    selected["matrix_column_index"] = selected["SAMPID"].map(header_index).astype(int)
    cohort = selected.rename(
        columns={
            "SAMPID": "sample_id",
            "SMTS": "broad_tissue",
            "SMTSD": "tissue_site",
        }
    )[
        [
            "sample_id",
            "donor_id",
            "organ",
            "broad_tissue",
            "tissue_site",
            "matrix_column_index",
        ]
    ]
    organ_order = {organ: index for index, organ in enumerate(organs)}
    cohort["_organ_order"] = cohort["organ"].map(organ_order)
    cohort = (
        cohort.sort_values(
            ["_organ_order", "tissue_site", "donor_id", "sample_id"],
            kind="mergesort",
        )
        .drop(columns="_organ_order")
        .reset_index(drop=True)
    )
    if cohort["sample_id"].duplicated().any():
        raise ValueError("GTEx development cohort repeats sample IDs")
    if set(cohort["organ"]) != set(organs):
        raise ValueError("GTEx development cohort does not cover every candidate organ")

    counts = {}
    for organ in organs:
        subset = cohort[cohort["organ"].eq(organ)]
        counts[organ] = {
            "samples": int(len(subset)),
            "donors": int(subset["donor_id"].nunique()),
            "tissue_sites": {
                str(key): int(value)
                for key, value in subset["tissue_site"]
                .value_counts()
                .sort_index()
                .items()
            },
        }
        minimum = int(
            protocol["organ_selection"]["minimum_gtex_header_present_donors"]
        )
        if counts[organ]["donors"] < minimum:
            raise ValueError(f"GTEx {organ} donor count falls below {minimum}")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    cohort_path = output_dir / "gtex_development_cohort.parquet"
    _atomic_parquet(cohort, cohort_path)
    report = {
        "schema_version": 1,
        "status": (
            "provisional_complete"
            if status.startswith("draft_")
            else "frozen_complete"
        ),
        "protocol_status": status,
        "metadata_only": True,
        "expression_values_read": False,
        "gct_rows_read": 0,
        "archs4_expression_accessed": False,
        "samples": int(len(cohort)),
        "donors": int(cohort["donor_id"].nunique()),
        "organ_order": list(organs),
        "by_organ": counts,
        "excluded_historical_entex_donors": sorted(excluded_donors),
        "gct_dimensions": {
            "gene_rows": int(gene_rows),
            "sample_columns": int(matrix_samples),
        },
        "hashes": {
            "protocol_sha256": sha256_file(protocol_path),
            "sample_attributes_sha256": sha256_file(attributes_path),
            "counts_object_sha256": sha256_file(counts_path),
            "matrix_header_sample_ids_sha256": sha256_lines(header_ids),
            "cohort_sha256": sha256_file(cohort_path),
            "cohort_sample_ids_sha256": sha256_lines(cohort["sample_id"]),
        },
    }
    _atomic_json(output_dir / "cohort_report.json", report)
    (output_dir / "COHORT_METADATA_COMPLETE").write_text(
        "GTEx development cohort built from metadata and GCT header only.\n"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-attributes", required=True)
    parser.add_argument("--counts-gct", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    print(json.dumps(build(args), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
