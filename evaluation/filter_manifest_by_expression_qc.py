#!/usr/bin/env python3
"""Explicitly remove samples named by a failed exact-extraction QC report.

The extractor intentionally refuses to drop samples silently.  This companion
step turns its machine-readable failure list into a new, hashed manifest.  It
does not relabel or resplit studies; definitive cohorts should run expression QC
before their final split, while the current engineering smoke may retain the
already frozen study assignment and record the reduced counts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = {"sample_id", "organ", "series_group_id", "split"}


def _sha256_lines(values) -> str:
    payload = "\n".join(str(value) for value in values) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _read_manifest(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    return pd.read_csv(path)


def filter_manifest(
    manifest: pd.DataFrame,
    extraction_report: dict,
) -> tuple[pd.DataFrame, dict]:
    missing = REQUIRED_COLUMNS - set(manifest.columns)
    if missing:
        raise ValueError(f"manifest is missing required columns: {sorted(missing)}")
    if manifest["sample_id"].isna().any() or manifest["sample_id"].duplicated().any():
        raise ValueError("manifest sample_id values must be non-null and unique")
    frame = manifest.copy()
    for column in REQUIRED_COLUMNS:
        if frame[column].isna().any():
            raise ValueError(f"manifest column {column!r} contains missing values")
        frame[column] = frame[column].astype(str)

    if extraction_report.get("status") != "failed_qc":
        raise ValueError("extraction report must have status 'failed_qc'")
    report_manifest = extraction_report.get("manifest", {})
    if int(report_manifest.get("n_samples", -1)) != len(frame):
        raise ValueError("extraction report sample count does not match manifest")
    expected_order_hash = report_manifest.get("ordered_sample_id_sha256")
    actual_order_hash = _sha256_lines(frame["sample_id"].tolist())
    if expected_order_hash != actual_order_hash:
        raise ValueError("extraction report sample order hash does not match manifest")

    failures = extraction_report.get("qc", {}).get("failures", [])
    if not failures:
        raise ValueError("failed_qc report has no qc.failures entries")
    failed_ids = [str(row.get("sample_id", "")) for row in failures]
    if any(not sample_id for sample_id in failed_ids) or len(set(failed_ids)) != len(failed_ids):
        raise ValueError("QC failure sample IDs must be nonempty and unique")
    unknown = sorted(set(failed_ids) - set(frame["sample_id"]))
    if unknown:
        raise ValueError(f"QC report names samples absent from manifest: {unknown[:5]}")

    before = frame.groupby(["organ", "split"], sort=True).size()
    filtered = frame.loc[~frame["sample_id"].isin(failed_ids)].copy().reset_index(drop=True)
    if filtered.empty:
        raise ValueError("expression QC removed every manifest row")
    split_overlap = filtered.groupby("series_group_id")["split"].nunique()
    if (split_overlap > 1).any():
        raise ValueError("filtered manifest unexpectedly contains connected-study split leakage")
    after = filtered.groupby(["organ", "split"], sort=True).size()
    missing_cells = [
        f"{organ}/{split_name}"
        for organ in sorted(frame["organ"].unique())
        for split_name in sorted(frame["split"].unique())
        if int(after.get((organ, split_name), 0)) == 0
    ]
    if missing_cells:
        raise ValueError(f"expression QC emptied required organ/split cells: {missing_cells}")

    result_report = {
        "schema_version": 1,
        "source_extraction_status": "failed_qc",
        "n_before": int(len(frame)),
        "n_removed": int(len(failed_ids)),
        "n_after": int(len(filtered)),
        "removed_sample_id_sha256": _sha256_lines(sorted(failed_ids)),
        "output_ordered_sample_id_sha256": _sha256_lines(filtered["sample_id"].tolist()),
        "counts_before": {
            f"{organ}/{split_name}": int(value)
            for (organ, split_name), value in before.items()
        },
        "counts_after": {
            f"{organ}/{split_name}": int(value)
            for (organ, split_name), value in after.items()
        },
        "removed_by_organ_split": {
            f"{organ}/{split_name}": int(
                before.get((organ, split_name), 0) - after.get((organ, split_name), 0)
            )
            for organ, split_name in before.index
        },
        "note": (
            "Engineering-smoke QC filter only; definitive cohorts must apply expression "
            "QC before freezing their final connected-study split."
        ),
    }
    return filtered, result_report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--failed-extraction-report", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    report_path = Path(args.failed_extraction_report)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    filtered, report = filter_manifest(
        _read_manifest(manifest_path), json.loads(report_path.read_text())
    )
    filtered.to_csv(output_dir / "qc_eligible_manifest.csv", index=False)
    filtered.to_parquet(output_dir / "qc_eligible_manifest.parquet", index=False)
    (output_dir / "qc_filter_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
