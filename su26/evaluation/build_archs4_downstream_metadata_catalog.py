#!/usr/bin/env python3
"""Build the ARCHS4 downstream benchmark catalog without reading expression.

The catalog is deliberately restricted to an exported sample-metadata table.  It
validates the complete pre-QC Stage-1 lockbox exclusion ledger, excludes every GEO
series token in those connected study groups, removes explicit GTEx overlap, and
applies the existing frozen organ-label recovery rules.  It cannot accept an H5 path
and therefore cannot access ``data/expression`` by construction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from evaluation.recover_organ_labels import classify_row, load_ontology, parse_characteristics
except ModuleNotFoundError:  # Support direct ``python evaluation/<script>.py`` execution.
    from recover_organ_labels import classify_row, load_ontology, parse_characteristics


REQUIRED_COLUMNS = (
    "geo_accession",
    "series_id",
    "source_name_ch1",
    "title",
    "characteristics_ch1",
)
GTEX_DONOR_RE = re.compile(r"\bGTEX[-_ ][A-Z0-9]+", re.IGNORECASE)
GSE_RE = re.compile(r"\bGSE\d+\b", re.IGNORECASE)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_lines_sha256(values: list[str]) -> str:
    payload = "\n".join(sorted(set(values))) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def series_tokens(value: object) -> set[str]:
    return {token.upper() for token in GSE_RE.findall(str(value))}


def validate_exclusion_ledger(manifest_path: str | Path, protocol: dict) -> dict:
    expected = protocol["stage1_exclusion_firewall"]
    manifest_path = Path(manifest_path)
    actual_file_hash = sha256_file(manifest_path)
    if actual_file_hash != expected["manifest_sha256"]:
        raise ValueError("Stage-1 exclusion manifest SHA256 mismatch")

    manifest = pd.read_csv(manifest_path, dtype=str)
    if "series_id" not in manifest.columns:
        raise KeyError("Stage-1 manifest is missing series_id")
    groups = sorted(set(manifest["series_id"].dropna().astype(str)))
    tokens = sorted({token for group in groups for token in series_tokens(group)})
    checks = {
        "connected_study_groups": len(groups),
        "connected_study_group_sha256": canonical_lines_sha256(groups),
        "geo_series_tokens": len(tokens),
        "geo_series_token_sha256": canonical_lines_sha256(tokens),
    }
    for key, actual in checks.items():
        if actual != expected[key]:
            raise ValueError(f"Stage-1 exclusion firewall mismatch for {key}")
    return {"groups": groups, "tokens": tokens, "checks": checks}


def read_metadata(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() == ".parquet":
        frame = pd.read_parquet(path)
    elif path.suffix.lower() in {".csv", ".tsv"}:
        frame = pd.read_csv(path, sep="\t" if path.suffix.lower() == ".tsv" else ",")
    else:
        raise ValueError("metadata input must be parquet, csv, or tsv")
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise KeyError(f"metadata is missing required columns: {missing}")
    if "singlecellprobability" not in frame.columns:
        frame["singlecellprobability"] = np.nan
    return frame


def explicit_gtex_overlap(row: pd.Series, fields: list[str]) -> bool:
    text = " | ".join(str(row.get(field, "")) for field in fields)
    return bool(re.search(r"\bGTEx\b", text, re.IGNORECASE) or GTEX_DONOR_RE.search(text))


def build_catalog(
    metadata_path: str | Path,
    stage1_manifest_path: str | Path,
    ontology_path: str | Path,
    protocol_path: str | Path,
    output_dir: str | Path,
) -> dict:
    protocol = json.loads(Path(protocol_path).read_text())
    if protocol.get("access_mode") != "metadata_only_no_expression":
        raise ValueError("protocol does not enforce metadata-only access")
    if sha256_file(ontology_path) != protocol["organ_mapping"]["ontology_sha256"]:
        raise ValueError("organ ontology SHA256 mismatch")
    ledger = validate_exclusion_ledger(stage1_manifest_path, protocol)
    excluded_tokens = set(ledger["tokens"])

    metadata = read_metadata(metadata_path).copy()
    ontology = load_ontology(ontology_path)
    target_organs = set(protocol["target_organs"])
    gtex_fields = protocol["gtex_overlap_firewall"]["search_fields"]

    records = []
    for row in metadata.itertuples(index=False):
        row_dict = row._asdict()
        tokens = series_tokens(row_dict["series_id"])
        prior_overlap = bool(tokens & excluded_tokens)
        gtex_overlap = explicit_gtex_overlap(pd.Series(row_dict), gtex_fields)
        result = classify_row(
            row_dict["source_name_ch1"],
            row_dict["title"],
            row_dict["characteristics_ch1"],
            row_dict["singlecellprobability"],
            ontology,
            float(protocol["organ_mapping"]["single_cell_threshold"]),
        )
        organ = result["organ"]
        eligible = (
            not prior_overlap
            and not gtex_overlap
            and result["tier"] == "high_confidence"
            and organ in target_organs
        )
        if prior_overlap:
            reason = "stage1_series_overlap"
        elif gtex_overlap:
            reason = "explicit_gtex_overlap"
        elif organ not in target_organs:
            reason = "outside_target_organs"
        elif result["tier"] != "high_confidence":
            reason = f"organ_{result['tier']}"
        else:
            reason = "eligible_metadata_only"
        records.append(
            {
                **row_dict,
                **result,
                "series_tokens": "|".join(sorted(tokens)),
                "prior_stage1_overlap": prior_overlap,
                "explicit_gtex_overlap": gtex_overlap,
                "catalog_eligible": eligible,
                "catalog_decision": reason,
            }
        )

    catalog = pd.DataFrame(records)
    eligible = catalog[catalog["catalog_eligible"]].copy()
    if eligible["prior_stage1_overlap"].any() or eligible["explicit_gtex_overlap"].any():
        raise RuntimeError("eligible catalog violates an exclusion firewall")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    catalog.to_parquet(output_dir / "sample_catalog.parquet", index=False)
    eligible.to_parquet(output_dir / "eligible_metadata.parquet", index=False)

    inventory = (
        eligible.groupby(["organ", "series_id"], dropna=False)
        .size()
        .rename("n_samples")
        .reset_index()
        .sort_values(["organ", "n_samples", "series_id"], ascending=[True, False, True])
    )
    inventory.to_csv(output_dir / "organ_study_inventory.csv", index=False)

    key_counts: Counter[tuple[str, str]] = Counter()
    for row in eligible.itertuples(index=False):
        for key in parse_characteristics(row.characteristics_ch1):
            key_counts[(str(row.organ), key)] += 1
    key_inventory = pd.DataFrame(
        [
            {"organ": organ, "characteristic_key": key, "n_samples": count}
            for (organ, key), count in sorted(key_counts.items())
        ]
    )
    key_inventory.to_csv(output_dir / "characteristic_key_inventory.csv", index=False)

    decision_counts = catalog["catalog_decision"].value_counts().sort_index().to_dict()
    report = {
        "schema_version": 1,
        "status": "complete_metadata_only_catalog",
        "access_mode": "metadata_only_no_expression",
        "expression_accessed": False,
        "metadata_sha256": sha256_file(metadata_path),
        "protocol_sha256": sha256_file(protocol_path),
        "ontology_sha256": sha256_file(ontology_path),
        "stage1_manifest_sha256": sha256_file(stage1_manifest_path),
        "stage1_exclusion_firewall": ledger["checks"],
        "n_input_samples": int(len(catalog)),
        "n_eligible_samples": int(len(eligible)),
        "n_eligible_series_values": int(eligible["series_id"].nunique()),
        "n_eligible_geo_series_tokens": int(
            len({token for value in eligible["series_id"] for token in series_tokens(value)})
        ),
        "decision_counts": {key: int(value) for key, value in decision_counts.items()},
        "per_organ": (
            eligible.groupby("organ").agg(samples=("geo_accession", "size"), studies=("series_id", "nunique"))
            .reset_index()
            .to_dict("records")
        ),
        "firewall_assertions": {
            "all_64_connected_stage1_groups_bound": ledger["checks"]["connected_study_groups"] == 64,
            "all_72_stage1_geo_tokens_excluded": ledger["checks"]["geo_series_tokens"] == 72,
            "eligible_stage1_overlap_rows": int(eligible["prior_stage1_overlap"].sum()),
            "eligible_explicit_gtex_overlap_rows": int(eligible["explicit_gtex_overlap"].sum()),
        },
        "limitations": [
            "Metadata-only catalog; no disease/intervention labels are frozen here.",
            "GTEx overlap is excluded only when an explicit GTEx marker or donor identifier is present; title-derived donor identity is not treated as verified identity.",
            "No ARCHS4 expression, headroom metric, or efficacy outcome was accessed.",
        ],
    }
    (output_dir / "catalog_report.json").write_text(json.dumps(report, indent=2) + "\n")
    checksums = []
    for path in sorted(output_dir.iterdir()):
        if path.name == "IMMUTABLE_SHA256SUMS":
            continue
        checksums.append(f"{sha256_file(path)}  {path.name}")
    (output_dir / "IMMUTABLE_SHA256SUMS").write_text("\n".join(checksums) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--stage1-manifest", required=True)
    parser.add_argument("--ontology", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    report = build_catalog(
        args.metadata,
        args.stage1_manifest,
        args.ontology,
        args.protocol,
        args.output_dir,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
