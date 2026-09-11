#!/usr/bin/env python3
"""Build a metadata-only candidate pool for future K4 external confirmation.

This is deliberately a scout, not a frozen lockbox.  Every current ARCHS4 row
sharing either a sample accession or any GEO series token with the historical
v11 snapshot is removed before organ-label recovery.  No expression file is
accepted by this program and no efficacy metric is computed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from attach_archs4_series import _series_tokens, connected_series_groups
from recover_organ_labels import classify_row, load_ontology


TARGET_ORGANS = ("adipose", "brain", "liver", "skeletal_muscle", "skin")
CURRENT_COLUMNS = (
    "h5_row",
    "geo_accession",
    "series_id",
    "source_name_ch1",
    "title",
    "characteristics_ch1",
    "singlecellprobability",
    "library_strategy",
    "library_source",
    "submission_date",
    "last_update_date",
    "readsaligned",
    "readstotal",
)


def sha256_lines(values) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(str(value).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def sha256_pairs(left, right) -> str:
    digest = hashlib.sha256()
    for first, second in zip(left, right):
        digest.update(str(first).encode("utf-8"))
        digest.update(b"\t")
        digest.update(str(second).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _is_rna_seq(value: str) -> bool:
    normalized = str(value).strip().lower().replace("_", "-")
    return normalized in {"rna-seq", "rnaseq"}


def _strictly_after(values: pd.Series, cutoff: str) -> pd.Series:
    dates = pd.to_datetime(values, errors="coerce", utc=True)
    threshold = pd.Timestamp(cutoff, tz="UTC")
    return dates > threshold


def _manual_review_sheet(
    candidates: pd.DataFrame,
    per_organ: int,
    excluded_series_tokens: set[str] | None = None,
) -> pd.DataFrame:
    excluded_series_tokens = excluded_series_tokens or set()
    series_is_held_out = candidates["series_id"].map(
        lambda value: not bool(_series_tokens(value) & excluded_series_tokens)
    )
    parts = []
    for organ in TARGET_ORGANS:
        subset = candidates[
            (candidates["organ"] == organ)
            & series_is_held_out
        ].sort_values(
            ["series_group_id", "sample_id"]
        )
        if subset.empty:
            continue
        ranks = subset.groupby("series_group_id").cumcount()
        subset = subset.assign(_within_group_rank=ranks).sort_values(
            ["_within_group_rank", "series_group_id", "sample_id"]
        )
        parts.append(subset.head(per_organ).drop(columns="_within_group_rank"))
    if not parts:
        return candidates.head(0)
    return pd.concat(parts, ignore_index=True)


def build_scout(args: argparse.Namespace) -> dict:
    if re.fullmatch(r"[0-9a-f]{40}", args.code_commit) is None:
        raise ValueError("metadata scout requires a full 40-character code commit")
    protocol_path = Path(args.protocol)
    protocol = json.loads(protocol_path.read_text())
    if protocol.get("status") != "metadata_scout_only_not_external_lockbox":
        raise ValueError("unexpected external-scout protocol status")
    current_path = Path(args.current_metadata)
    historical_path = Path(args.historical_metadata)
    current_report = json.loads(Path(args.current_report).read_text())
    if current_report.get("metadata_only") is not True:
        raise ValueError("current metadata report is not marked metadata-only")
    if current_report.get("expression_values_read") is not False:
        raise ValueError("current metadata report does not prove expression stayed sealed")
    if current_report.get("output_parquet_sha256") != hashlib.sha256(
        current_path.read_bytes()
    ).hexdigest():
        raise ValueError("current metadata parquet hash differs from its report")

    historical = pd.read_parquet(
        historical_path,
        columns=["geo_accession", "series_id"],
    )
    historical_ids_ordered = historical["geo_accession"].astype(str).tolist()
    historical_series_ordered = historical["series_id"].astype(str).tolist()
    historical_hash = sha256_lines(historical_ids_ordered)
    if historical_hash != args.expected_historical_accession_sha256:
        raise ValueError("historical v11 accession hash mismatch")
    historical_mapping_hash = sha256_pairs(
        historical_ids_ordered, historical_series_ordered
    )
    if historical_mapping_hash != args.expected_historical_series_mapping_sha256:
        raise ValueError("historical v11 accession/series mapping hash mismatch")
    historical_ids = set(historical_ids_ordered)
    historical_series_tokens: set[str] = set()
    for value in historical_series_ordered:
        historical_series_tokens.update(_series_tokens(value))

    ontology = load_ontology(args.ontology)
    ontology_hash = hashlib.sha256(Path(args.ontology).read_bytes()).hexdigest()
    prior_review_path_value = getattr(args, "prior_review", None)
    expected_prior_review_sha256 = getattr(
        args, "expected_prior_review_sha256", None
    )
    prior_review_path = (
        Path(prior_review_path_value) if prior_review_path_value else None
    )
    prior_review_sha256 = None
    excluded_review_series_tokens: set[str] = set()
    if prior_review_path is not None:
        if not expected_prior_review_sha256:
            raise ValueError("prior review requires its expected SHA256")
        prior_review_sha256 = hashlib.sha256(prior_review_path.read_bytes()).hexdigest()
        if prior_review_sha256 != expected_prior_review_sha256:
            raise ValueError("prior manual-review sheet hash mismatch")
        prior_review = pd.read_csv(prior_review_path)
        required_prior_columns = {
            "organ", "sample_id", "series_id", "series_group_id"
        }
        missing_prior = sorted(required_prior_columns - set(prior_review.columns))
        if missing_prior:
            raise KeyError(
                f"prior manual-review sheet is missing fields: {missing_prior}"
            )
        for value in prior_review["series_id"].astype(str):
            excluded_review_series_tokens.update(_series_tokens(value))
    parquet = pq.ParquetFile(current_path)
    missing = sorted(set(CURRENT_COLUMNS) - set(parquet.schema.names))
    if missing:
        raise KeyError(f"current metadata is missing required fields: {missing}")

    exclusions = {
        "historical_sample": 0,
        "historical_series": 0,
        "empty_series": 0,
        "not_rna_seq": 0,
        "not_high_confidence_target_organ": 0,
    }
    records: list[dict] = []
    current_rows = 0
    for batch in parquet.iter_batches(
        batch_size=args.batch_size,
        columns=list(CURRENT_COLUMNS),
    ):
        frame = batch.to_pandas()
        current_rows += len(frame)
        for row in frame.itertuples(index=False):
            accession = str(row.geo_accession).strip()
            if accession in historical_ids:
                exclusions["historical_sample"] += 1
                continue
            series_tokens = _series_tokens(row.series_id)
            if not series_tokens:
                exclusions["empty_series"] += 1
                continue
            if series_tokens & historical_series_tokens:
                exclusions["historical_series"] += 1
                continue
            if not _is_rna_seq(row.library_strategy):
                exclusions["not_rna_seq"] += 1
                continue
            classification = classify_row(
                row.source_name_ch1,
                row.title,
                row.characteristics_ch1,
                row.singlecellprobability,
                ontology,
                args.single_cell_threshold,
            )
            if (
                classification["tier"] != "high_confidence"
                or classification["organ"] not in TARGET_ORGANS
            ):
                exclusions["not_high_confidence_target_organ"] += 1
                continue
            records.append({
                "h5_row": int(row.h5_row),
                "sample_id": accession,
                "series_id": " ".join(sorted(series_tokens)),
                "organ": classification["organ"],
                "uberon_id": classification["uberon_id"],
                "label_evidence": classification["evidence"],
                "source_name_ch1": str(row.source_name_ch1),
                "title": str(row.title),
                "characteristics_ch1": str(row.characteristics_ch1),
                "singlecellprobability": float(row.singlecellprobability),
                "library_strategy": str(row.library_strategy),
                "library_source": str(row.library_source),
                "submission_date": str(row.submission_date),
                "last_update_date": str(row.last_update_date),
                "readsaligned": float(row.readsaligned),
                "readstotal": float(row.readstotal),
            })
        print(f"scout_rows={current_rows}/{parquet.metadata.num_rows}", flush=True)

    candidates = pd.DataFrame.from_records(records)
    if candidates.empty:
        raise ValueError("metadata scout found no eligible candidates")
    if candidates["sample_id"].duplicated().any():
        raise ValueError("metadata scout produced duplicate sample IDs")
    candidates["series_group_id"] = connected_series_groups(
        candidates["series_id"].tolist()
    )
    candidates["submitted_after_v11_creation"] = _strictly_after(
        candidates["submission_date"], args.temporal_cutoff
    )
    candidates = candidates.sort_values(
        ["organ", "series_group_id", "sample_id"]
    ).reset_index(drop=True)

    summary_rows = []
    for organ in TARGET_ORGANS:
        subset = candidates[candidates["organ"] == organ]
        temporal = subset[subset["submitted_after_v11_creation"]]
        group_sizes = subset.groupby("series_group_id").size()
        summary_rows.append({
            "organ": organ,
            "n_samples": int(len(subset)),
            "n_series_groups": int(subset["series_group_id"].nunique()),
            "n_temporally_new_samples": int(len(temporal)),
            "n_temporally_new_series_groups": int(
                temporal["series_group_id"].nunique()
            ),
            "largest_group_fraction": (
                float(group_sizes.max() / len(subset)) if len(subset) else None
            ),
            "meets_minimum_five_series": bool(
                temporal["series_group_id"].nunique() >= 5
            ),
            "meets_preferred_eight_series": bool(
                temporal["series_group_id"].nunique() >= 8
            ),
        })
    summary = pd.DataFrame(summary_rows)
    review = _manual_review_sheet(
        candidates,
        args.manual_review_per_organ,
        excluded_review_series_tokens,
    )
    review_counts = review.groupby("organ").size().to_dict()
    incomplete_review_organs = [
        organ
        for organ in TARGET_ORGANS
        if review_counts.get(organ, 0) != args.manual_review_per_organ
    ]
    if prior_review_path is not None and incomplete_review_organs:
        raise ValueError(
            "manual-review sheet lacks the requested held-out rows for: "
            + ", ".join(incomplete_review_organs)
        )

    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise FileExistsError("external metadata scout output already exists")
    output_dir.mkdir(parents=True)
    candidate_path = output_dir / "candidate_metadata.parquet"
    summary_path = output_dir / "organ_summary.csv"
    review_path = output_dir / "manual_review.csv"
    candidates.to_parquet(candidate_path, index=False)
    summary.to_csv(summary_path, index=False)
    review.to_csv(review_path, index=False)

    report = {
        "schema_version": 1,
        "status": "scout_complete_not_frozen_lockbox",
        "code_commit": args.code_commit,
        "metadata_only": True,
        "expression_values_read": False,
        "efficacy_scoring_performed": False,
        "external_lockbox_frozen": False,
        "target_organs": list(TARGET_ORGANS),
        "current_metadata_rows": int(current_rows),
        "candidate_rows": int(len(candidates)),
        "candidate_series_groups": int(candidates["series_group_id"].nunique()),
        "historical_v11_rows": int(len(historical)),
        "historical_v11_accession_sha256": historical_hash,
        "historical_v11_accession_series_sha256": historical_mapping_hash,
        "historical_v11_series_token_sha256": sha256_lines(
            sorted(historical_series_tokens)
        ),
        "ontology_sha256": ontology_hash,
        "temporal_cutoff": args.temporal_cutoff,
        "exclusions": exclusions,
        "organ_summary": summary.to_dict("records"),
        "manual_review": {
            "round": 2 if prior_review_path is not None else 1,
            "rows_per_organ": int(args.manual_review_per_organ),
            "excluded_prior_series_tokens": int(
                len(excluded_review_series_tokens)
            ),
            "prior_review_sha256": prior_review_sha256,
            "held_out_from_prior_review": bool(prior_review_path is not None),
        },
        "hashes": {
            "protocol_sha256": hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
            "current_metadata_parquet_sha256": hashlib.sha256(
                current_path.read_bytes()
            ).hexdigest(),
            "candidate_metadata_sha256": hashlib.sha256(
                candidate_path.read_bytes()
            ).hexdigest(),
            "candidate_sample_ids_sha256": sha256_lines(
                candidates["sample_id"].tolist()
            ),
            "summary_sha256": hashlib.sha256(summary_path.read_bytes()).hexdigest(),
            "manual_review_sha256": hashlib.sha256(review_path.read_bytes()).hexdigest(),
        },
        "next_gate": (
            "Manually review the deterministic sheet, verify publication/BioProject/"
            "donor links and near duplicates, then freeze exact sample IDs before any "
            "expression request. This scout is not confirmatory data."
        ),
    }
    temporary_report = output_dir / "scout_report.json.tmp"
    temporary_report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    os.replace(temporary_report, output_dir / "scout_report.json")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current-metadata", required=True)
    parser.add_argument("--current-report", required=True)
    parser.add_argument("--historical-metadata", required=True)
    parser.add_argument("--expected-historical-accession-sha256", required=True)
    parser.add_argument("--expected-historical-series-mapping-sha256", required=True)
    parser.add_argument("--ontology", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--batch-size", type=int, default=20_000)
    parser.add_argument("--single-cell-threshold", type=float, default=0.5)
    parser.add_argument("--temporal-cutoff", default="2021-11-13")
    parser.add_argument("--manual-review-per-organ", type=int, default=50)
    parser.add_argument(
        "--prior-review",
        help=(
            "Optional prior manual-review CSV. Its connected series groups are "
            "excluded from the new review sheet, not from the candidate pool."
        ),
    )
    parser.add_argument("--expected-prior-review-sha256")
    args = parser.parse_args()
    report = build_scout(args)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
