#!/usr/bin/env python3
"""Audit GTEx/EN-TEx donor overlap across the full historical ARCHS4 catalog."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

from stage1_k4_gtex_common import atomic_json, sha256_file, sha256_lines


ENCODE_DONOR_RE = re.compile(r"\bENCDO[A-Z0-9]+\b")


def audit(args: argparse.Namespace) -> dict:
    source = Path(args.historical_metadata)
    if sha256_file(source) != args.expected_sha256:
        raise ValueError("historical ARCHS4 metadata SHA256 mismatch")
    frame = pd.read_parquet(source)
    text = frame.fillna("").astype(str).agg(" ".join, axis=1)
    selected = frame.loc[text.str.contains("GTEx", case=False, regex=False)].copy()
    selected_text = text.loc[selected.index]
    donors = sorted(
        {
            donor
            for value in selected_text
            for donor in ENCODE_DONOR_RE.findall(str(value))
        }
    )
    expected_donors = sorted(args.expected_encode_donor)
    if len(selected) != int(args.expected_rows):
        raise ValueError("historical GTEx-related row count changed")
    if donors != expected_donors:
        raise ValueError("historical GTEx-related donor family changed")
    id_column = "geo_accession"
    if id_column not in selected:
        raise ValueError("historical ARCHS4 metadata lacks geo_accession")
    report = {
        "schema_version": 1,
        "status": "complete",
        "expression_values_read": False,
        "historical_metadata_sha256": sha256_file(source),
        "historical_rows": len(frame),
        "gtex_related_rows": len(selected),
        "encode_donor_ids": donors,
        "gtex_related_geo_accessions_sha256": sha256_lines(
            sorted(selected[id_column].astype(str))
        ),
        "scope": "complete historical ARCHS4 v11 sample metadata, not a Stage-1 subset",
        "conclusion": (
            "All historical GTEx-related records resolve to the four frozen "
            "EN-TEx donors excluded globally from the GTEx cohort."
        ),
    }
    output = Path(args.output)
    atomic_json(output, report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical-metadata", required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--expected-rows", required=True, type=int)
    parser.add_argument("--expected-encode-donor", action="append", required=True)
    parser.add_argument("--output", required=True)
    return parser


def main() -> None:
    print(json.dumps(audit(build_parser().parse_args()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
