#!/usr/bin/env python3
"""Audit the expression-blind organ intersection for GTEx-to-ARCHS4 training.

The audit binds exact GTEx cohort counts to the current and historical ARCHS4
metadata catalogs, applies the historical accession/series firewall, and selects
organs using only the protocol's sample/donor/study thresholds.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = ROOT / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from attach_archs4_series import _series_tokens, connected_series_groups  # noqa: E402
from train_manifest import sha256_file, sha256_lines  # noqa: E402


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def audit(args: argparse.Namespace) -> dict[str, Any]:
    protocol_path = Path(args.protocol)
    if sha256_file(protocol_path) != args.expected_protocol_sha256:
        raise ValueError("GTEx-to-ARCHS4 protocol SHA256 mismatch")
    protocol = json.loads(protocol_path.read_text())
    if protocol.get("organ_selection", {}).get("outcome_independent") is not True:
        raise ValueError("protocol organ selection is not outcome-independent")
    sources = protocol["archs4_inventory_sources"]

    current_path = Path(args.current_metadata)
    historical_path = Path(args.historical_metadata)
    ontology_path = Path(args.ontology)
    recovery_source_path = Path(args.recovery_source)
    expected_hashes = {
        current_path: sources["current_human_metadata_sha256"],
        historical_path: sources["historical_v11_metadata_sha256"],
        ontology_path: sources["ontology_sha256"],
        recovery_source_path: sources["label_recovery_source_sha256"],
    }
    for path, expected in expected_hashes.items():
        if sha256_file(path) != expected:
            raise ValueError(f"inventory source SHA256 mismatch: {path.name}")

    recovery_report_path = Path(args.recovery_report)
    recovery_report = json.loads(recovery_report_path.read_text())
    if recovery_report.get("ontology_sha256") != sources["ontology_sha256"]:
        raise ValueError("label-recovery report uses a different ontology")
    current = pd.read_parquet(
        current_path, columns=["geo_accession", "series_id"]
    )
    recovered_path = Path(args.recovered_labels)
    recovered = pd.read_parquet(
        recovered_path,
        columns=[
            "geo_accession",
            "series_id",
            "organ",
            "tier",
            "submission_date",
        ],
    )
    if len(recovered) != len(current) or recovery_report.get("n_samples") != len(
        current
    ):
        raise ValueError("recovered labels do not cover the current ARCHS4 metadata")
    if not recovered[["geo_accession", "series_id"]].astype(str).equals(
        current[["geo_accession", "series_id"]].astype(str)
    ):
        raise ValueError("recovered labels are not row-aligned to current metadata")

    historical = pd.read_parquet(
        historical_path, columns=["geo_accession", "series_id"]
    )
    historical_ids = set(historical["geo_accession"].astype(str))
    historical_tokens: set[str] = set()
    for value in historical["series_id"].astype(str):
        historical_tokens.update(_series_tokens(value))

    high_confidence = recovered[recovered["tier"].eq("high_confidence")].copy()
    high_confidence = high_confidence[
        ~high_confidence["geo_accession"].astype(str).isin(historical_ids)
    ].copy()
    series_overlap = high_confidence["series_id"].astype(str).map(
        lambda value: bool(_series_tokens(value) & historical_tokens)
    )
    high_confidence = high_confidence.loc[~series_overlap].copy()
    high_confidence["series_group_id"] = connected_series_groups(
        high_confidence["series_id"].astype(str).tolist()
    )
    dates = pd.to_datetime(
        high_confidence["submission_date"], errors="coerce", utc=True
    )
    cutoff = pd.Timestamp(sources["temporal_cutoff"], tz="UTC")
    high_confidence = high_confidence.loc[dates > cutoff].copy()
    if high_confidence["geo_accession"].duplicated().any():
        raise ValueError("post-firewall ARCHS4 candidates repeat accessions")

    gtex_report_path = Path(args.gtex_cohort_report)
    gtex_report = json.loads(gtex_report_path.read_text())
    if (
        gtex_report.get("metadata_only") is not True
        or gtex_report.get("expression_values_read") is not False
        or gtex_report.get("archs4_expression_accessed") is not False
    ):
        raise ValueError("GTEx cohort report violates metadata-only inventory")
    gtex_counts = gtex_report.get("inventory_by_organ", gtex_report["by_organ"])

    selection = protocol["organ_selection"]
    min_gtex = int(selection["minimum_gtex_header_present_donors"])
    min_samples = int(selection["minimum_post_firewall_archs4_samples"])
    min_studies = int(
        selection["minimum_post_firewall_archs4_connected_studies"]
    )
    ontology = json.loads(ontology_path.read_text())
    ontology_organs = tuple(ontology["organs"])
    rows = []
    selected_organs = []
    for organ in ontology_organs:
        subset = high_confidence[high_confidence["organ"].eq(organ)]
        gtex = gtex_counts.get(organ, {"samples": 0, "donors": 0})
        row = {
            "organ": organ,
            "gtex_samples": int(gtex.get("samples", 0)),
            "gtex_donors": int(gtex.get("donors", 0)),
            "post_firewall_archs4_samples": int(len(subset)),
            "post_firewall_archs4_connected_studies": int(
                subset["series_group_id"].nunique()
            ),
        }
        row["passes_gtex_donors"] = row["gtex_donors"] >= min_gtex
        row["passes_archs4_samples"] = (
            row["post_firewall_archs4_samples"] >= min_samples
        )
        row["passes_archs4_studies"] = (
            row["post_firewall_archs4_connected_studies"] >= min_studies
        )
        row["selected"] = bool(
            row["passes_gtex_donors"]
            and row["passes_archs4_samples"]
            and row["passes_archs4_studies"]
        )
        if row["selected"]:
            selected_organs.append(organ)
        rows.append(row)
    expected_order = list(selection["ordered_candidate_organs"])
    selected_in_expected_order = [
        organ for organ in expected_order if organ in selected_organs
    ]
    if set(selected_organs) != set(expected_order):
        raise ValueError(
            "outcome-free inventory selection differs from candidate organ set: "
            f"observed={sorted(selected_organs)} expected={sorted(expected_order)}"
        )

    inventory = pd.DataFrame(rows)
    inventory["selection_order"] = inventory["organ"].map(
        {organ: index for index, organ in enumerate(expected_order)}
    )
    inventory = inventory.sort_values(
        ["selected", "selection_order", "organ"],
        ascending=[False, True, True],
        na_position="last",
    ).drop(columns="selection_order")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    inventory_path = output_dir / "organ_inventory.csv"
    inventory.to_csv(inventory_path, index=False, lineterminator="\n")
    report = {
        "schema_version": 1,
        "status": "complete",
        "metadata_only": True,
        "expression_values_read": False,
        "efficacy_scoring_performed": False,
        "archs4_expression_accessed": False,
        "selection_rule": {
            "minimum_gtex_header_present_donors": min_gtex,
            "minimum_post_firewall_archs4_samples": min_samples,
            "minimum_post_firewall_archs4_connected_studies": min_studies,
        },
        "selected_organs": selected_in_expected_order,
        "selected_k": len(selected_in_expected_order),
        "inventory": inventory.to_dict("records"),
        "firewall": {
            "historical_accessions": len(historical_ids),
            "historical_series_tokens": len(historical_tokens),
            "temporal_cutoff": sources["temporal_cutoff"],
            "post_firewall_high_confidence_samples": int(len(high_confidence)),
            "post_firewall_connected_studies": int(
                high_confidence["series_group_id"].nunique()
            ),
        },
        "hashes": {
            "protocol_sha256": sha256_file(protocol_path),
            "gtex_cohort_report_sha256": sha256_file(gtex_report_path),
            "current_metadata_sha256": sha256_file(current_path),
            "historical_metadata_sha256": sha256_file(historical_path),
            "ontology_sha256": sha256_file(ontology_path),
            "recovery_source_sha256": sha256_file(recovery_source_path),
            "recovery_report_sha256": sha256_file(recovery_report_path),
            "recovered_labels_sha256": sha256_file(recovered_path),
            "historical_accession_sha256": sha256_lines(
                historical["geo_accession"].astype(str)
            ),
            "inventory_sha256": sha256_file(inventory_path),
        },
        "next_gate": (
            "Freeze the exact K8 GTEx cohort/protocol and complete manual ARCHS4 "
            "study/sample review before any ARCHS4 expression access."
        ),
    }
    _atomic_json(output_dir / "inventory_report.json", report)
    (output_dir / "INVENTORY_COMPLETE").write_text(
        "Metadata-only GTEx/ARCHS4 organ inventory complete.\n"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--gtex-cohort-report", required=True)
    parser.add_argument("--current-metadata", required=True)
    parser.add_argument("--historical-metadata", required=True)
    parser.add_argument("--ontology", required=True)
    parser.add_argument("--recovery-source", required=True)
    parser.add_argument("--recovered-labels", required=True)
    parser.add_argument("--recovery-report", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
