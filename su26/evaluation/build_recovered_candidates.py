#!/usr/bin/env python3
"""Turn recovered high-confidence labels into an organ-candidates parquet.

Bridges ``evaluation/recover_organ_labels.py`` output to the existing
``evaluation/build_organ_pilot_manifest.py``, which freezes the study-disjoint
train/calibration/test manifest. This selects one tier (default ``high_confidence``)
and an explicit organ set, renames columns to the candidates schema, and recomputes
connected ``series_group_id`` over exactly the selected subset (connected components
depend on which samples are present).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from attach_archs4_series import connected_series_groups  # noqa: E402


COLUMN_MAP = {
    "geo_accession": "sample_id",
    "source_name_ch1": "source_name",
    "characteristics_ch1": "characteristics",
    "singlecellprobability": "single_cell_probability",
    "flag_tumor": "tumor_like",
}
KEEP = [
    "sample_id", "organ", "series_group_id", "tumor_like", "label_evidence",
    "series_id", "source_name", "title", "characteristics", "single_cell_probability",
]


def build(args) -> dict:
    recovered = pd.read_parquet(args.recovered)
    organs = [o.strip() for o in args.organs.split(",") if o.strip()]
    subset = recovered[
        (recovered["tier"] == args.tier) & (recovered["organ"].isin(organs))
    ].copy()
    if subset.empty:
        raise ValueError("no rows matched the requested tier/organs")
    missing = set(organs) - set(subset["organ"].unique())
    if missing:
        raise ValueError(f"requested organs absent from recovered labels: {sorted(missing)}")

    subset = subset.rename(columns=COLUMN_MAP)
    # Recompute connected study groups over just this selection.
    subset["series_group_id"] = connected_series_groups(subset["series_id"].tolist())
    if "label_evidence" not in subset.columns:
        subset["label_evidence"] = subset.get("evidence", "")
    subset["tumor_like"] = subset["tumor_like"].astype(bool)
    candidates = subset[[c for c in KEEP if c in subset.columns]].copy()
    candidates = candidates.sort_values(
        ["organ", "series_group_id", "sample_id"]
    ).reset_index(drop=True)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    candidates.to_parquet(output, index=False)

    per_organ = (
        candidates.groupby("organ")
        .agg(n_samples=("sample_id", "size"), n_series_groups=("series_group_id", "nunique"))
        .reset_index()
        .sort_values("n_samples", ascending=False)
    )
    report = {
        "schema_version": 1,
        "recovered_labels": str(Path(args.recovered).resolve()),
        "tier": args.tier,
        "organs": organs,
        "n_candidates": int(len(candidates)),
        "per_organ": per_organ.to_dict("records"),
        "output_parquet": str(output.resolve()),
    }
    print(json.dumps(report, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--recovered",
        default="artifacts/stage1_label_recovery/recovered_labels.parquet",
    )
    parser.add_argument("--tier", default="high_confidence")
    parser.add_argument(
        "--organs",
        default="brain,adipose,liver,skin,skeletal_muscle",
        help="comma-separated organ set to freeze",
    )
    parser.add_argument(
        "--output",
        default="artifacts/stage1_organ_k5/organ_candidates.parquet",
    )
    args = parser.parse_args()
    build(args)


if __name__ == "__main__":
    main()
