#!/usr/bin/env python3
"""Build an exact, metadata-only sample sheet for manual external-cohort review.

The input shortlist contains provisional study/sample selectors chosen after reading
the pinned GEO series metadata.  This program resolves those selectors to exact sample
accessions and attaches study provenance.  It does not accept a study, freeze a
lockbox, read expression values, or compute model efficacy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

import pandas as pd


TARGET_ORGANS = ("adipose", "brain", "liver", "skeletal_muscle", "skin")
REQUIRED_TRIAGE_COLUMNS = {
    "sample_id",
    "series_id",
    "series_group_id",
    "organ",
    "source_name_ch1",
    "title",
    "characteristics_ch1",
    "submitted_after_v11_creation",
    "classifier_tier",
    "triage_tier",
}
REQUIRED_GEO_COLUMNS = {
    "organ",
    "series_group_id",
    "series_tokens",
    "geo_pubmed_ids",
    "geo_bioproject_ids",
    "geo_series_titles",
    "geo_overall_designs",
    "geo_summaries",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _text_mask(values: pd.Series, pattern: str) -> pd.Series:
    try:
        compiled = re.compile(pattern, re.IGNORECASE)
    except re.error as error:
        raise ValueError(f"invalid selector regex {pattern!r}: {error}") from error
    return values.fillna("").astype(str).map(lambda value: bool(compiled.search(value)))


def resolve_selector(group: pd.DataFrame, selector: dict) -> pd.DataFrame:
    """Resolve one documented selector against one organ/group sample table."""
    allowed = {
        "all_post_cutoff",
        "explicit_sample_ids",
        "regex",
    }
    mode = selector.get("mode")
    if mode not in allowed:
        raise ValueError(f"unsupported selector mode: {mode!r}")
    if mode == "all_post_cutoff":
        selected = group.copy()
    elif mode == "explicit_sample_ids":
        requested = selector.get("sample_ids")
        if not isinstance(requested, list) or not requested:
            raise ValueError("explicit_sample_ids requires a nonempty sample_ids list")
        if len(requested) != len(set(requested)):
            raise ValueError("explicit sample IDs contain duplicates")
        available = set(group["sample_id"])
        missing = sorted(set(requested) - available)
        if missing:
            raise ValueError(f"explicit sample IDs are absent from group: {missing}")
        order = {sample_id: index for index, sample_id in enumerate(requested)}
        selected = group[group["sample_id"].isin(requested)].copy()
        selected["_selector_order"] = selected["sample_id"].map(order)
        selected = selected.sort_values("_selector_order").drop(
            columns="_selector_order"
        )
    else:
        selected_mask = pd.Series(True, index=group.index)
        title_pattern = selector.get("title_include_regex")
        if title_pattern:
            selected_mask &= _text_mask(group["title"], title_pattern)
        combined = group[
            ["sample_id", "title", "source_name_ch1", "characteristics_ch1"]
        ].fillna("").astype(str).agg(" | ".join, axis=1)
        for pattern in selector.get("metadata_include_all_regex", []):
            selected_mask &= _text_mask(combined, pattern)
        for pattern in selector.get("metadata_exclude_any_regex", []):
            selected_mask &= ~_text_mask(combined, pattern)
        selected = group[selected_mask].copy()
    if selected.empty:
        raise ValueError("selector resolved to zero samples")
    return selected


def _validated_json(path: Path, expected_hash: str, label: str) -> dict:
    if sha256(path) != expected_hash:
        raise ValueError(f"{label} hash mismatch")
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise TypeError(f"{label} must contain a JSON object")
    return value


def build_sample_review(args: argparse.Namespace) -> dict:
    if re.fullmatch(r"[0-9a-f]{40}", args.code_commit) is None:
        raise ValueError("sample review requires a full code commit")
    triage_path = Path(args.sample_triage)
    geo_path = Path(args.geo_study_review)
    shortlist_path = Path(args.shortlist)
    if sha256(triage_path) != args.expected_triage_sha256:
        raise ValueError("sample-triage hash mismatch")
    if sha256(geo_path) != args.expected_geo_review_sha256:
        raise ValueError("GEO study-review hash mismatch")
    shortlist = _validated_json(
        shortlist_path, args.expected_shortlist_sha256, "shortlist"
    )
    if shortlist.get("metadata_only") is not True:
        raise ValueError("shortlist is not marked metadata-only")
    if shortlist.get("expression_values_read") is not False:
        raise ValueError("shortlist does not prove expression stayed sealed")
    if shortlist.get("external_lockbox_frozen") is not False:
        raise ValueError("shortlist must not claim a frozen external lockbox")
    if shortlist.get("study_status") != "provisional_manual_review":
        raise ValueError("shortlist study status is not provisional manual review")

    triage = pd.read_parquet(triage_path)
    geo = pd.read_csv(geo_path, keep_default_na=False)
    missing_triage = sorted(REQUIRED_TRIAGE_COLUMNS - set(triage.columns))
    missing_geo = sorted(REQUIRED_GEO_COLUMNS - set(geo.columns))
    if missing_triage:
        raise KeyError(f"sample triage is missing fields: {missing_triage}")
    if missing_geo:
        raise KeyError(f"GEO study review is missing fields: {missing_geo}")
    if triage["sample_id"].duplicated().any():
        raise ValueError("sample triage contains duplicate sample IDs")

    entries = shortlist.get("entries")
    if not isinstance(entries, list):
        raise TypeError("shortlist entries must be a list")
    expected_per_organ = int(shortlist.get("provisional_groups_per_organ", 0))
    entry_table = pd.DataFrame(entries)
    required_entry_fields = {
        "organ",
        "series_group_id",
        "review_rationale",
        "donor_resolution_status",
        "selector",
    }
    missing_entry_fields = sorted(required_entry_fields - set(entry_table.columns))
    if missing_entry_fields:
        raise KeyError(f"shortlist entries are missing fields: {missing_entry_fields}")
    if set(entry_table["organ"]) != set(TARGET_ORGANS):
        raise ValueError("shortlist does not cover exactly the five target organs")
    group_counts = entry_table.groupby("organ").size()
    if not group_counts.eq(expected_per_organ).all():
        raise ValueError(
            f"shortlist must have {expected_per_organ} groups per organ: "
            f"{group_counts.to_dict()}"
        )
    if entry_table.duplicated(["organ", "series_group_id"]).any():
        raise ValueError("shortlist repeats an organ/group entry")

    resolved_parts = []
    group_summary_rows = []
    for entry in entries:
        organ = entry["organ"]
        group_id = entry["series_group_id"]
        group = triage[
            (triage["organ"] == organ)
            & (triage["series_group_id"] == group_id)
            & triage["submitted_after_v11_creation"].astype(bool)
        ].copy()
        if group.empty:
            raise ValueError(f"no post-cutoff samples for {organ}/{group_id}")
        geo_row = geo[
            (geo["organ"] == organ) & (geo["series_group_id"] == group_id)
        ]
        if len(geo_row) != 1:
            raise ValueError(
                f"expected one pinned GEO review row for {organ}/{group_id}, "
                f"found {len(geo_row)}"
            )
        selected = resolve_selector(group, entry["selector"])
        if not selected["submitted_after_v11_creation"].astype(bool).all():
            raise ValueError("pre-cutoff sample passed a selector")
        if (selected["classifier_tier"] != "high_confidence").any():
            bad = selected.loc[
                selected["classifier_tier"] != "high_confidence", "sample_id"
            ].tolist()
            raise ValueError(f"selector included classifier-ineligible samples: {bad}")
        if (selected["triage_tier"] == "excluded_by_classifier").any():
            raise ValueError("selector included samples excluded by classifier")

        provenance = geo_row.iloc[0]
        selector_json = json.dumps(
            entry["selector"], sort_keys=True, separators=(",", ":")
        )
        selected["review_rationale"] = entry["review_rationale"]
        selected["donor_resolution_status"] = entry["donor_resolution_status"]
        selected["selector_json"] = selector_json
        selected["geo_series_tokens"] = provenance["series_tokens"]
        selected["geo_pubmed_ids"] = provenance["geo_pubmed_ids"]
        selected["geo_bioproject_ids"] = provenance["geo_bioproject_ids"]
        selected["geo_series_titles"] = provenance["geo_series_titles"]
        selected["manual_sample_decision"] = "pending"
        selected["manual_donor_id"] = ""
        selected["manual_near_duplicate_set"] = ""
        selected["manual_review_notes"] = ""
        resolved_parts.append(selected)
        group_summary_rows.append({
            "organ": organ,
            "series_group_id": group_id,
            "n_post_cutoff_candidates": int(len(group)),
            "n_provisional_selector_matches": int(len(selected)),
            "donor_resolution_status": entry["donor_resolution_status"],
            "review_rationale": entry["review_rationale"],
            "selector_json": selector_json,
            "geo_series_tokens": provenance["series_tokens"],
            "geo_pubmed_ids": provenance["geo_pubmed_ids"],
            "geo_bioproject_ids": provenance["geo_bioproject_ids"],
            "geo_series_titles": provenance["geo_series_titles"],
            "manual_study_decision": "pending",
            "manual_donor_audit": "pending",
            "manual_near_duplicate_audit": "pending",
            "manual_review_notes": "",
        })

    resolved = pd.concat(resolved_parts, ignore_index=True)
    if resolved["sample_id"].duplicated().any():
        duplicates = sorted(
            resolved.loc[resolved["sample_id"].duplicated(False), "sample_id"].unique()
        )
        raise ValueError(f"shortlist resolves duplicate sample IDs: {duplicates}")
    organ_rank = {organ: index for index, organ in enumerate(TARGET_ORGANS)}
    entry_rank = {
        (entry["organ"], entry["series_group_id"]): index
        for index, entry in enumerate(entries)
    }
    resolved["_organ_rank"] = resolved["organ"].map(organ_rank)
    resolved["_entry_rank"] = [
        entry_rank[(organ, group_id)]
        for organ, group_id in zip(resolved["organ"], resolved["series_group_id"])
    ]
    resolved = resolved.sort_values(
        ["_organ_rank", "_entry_rank", "sample_id"]
    ).drop(columns=["_organ_rank", "_entry_rank"])
    group_summary = pd.DataFrame(group_summary_rows)
    group_summary["_organ_rank"] = group_summary["organ"].map(organ_rank)
    group_summary["_entry_rank"] = [
        entry_rank[(organ, group_id)]
        for organ, group_id in zip(
            group_summary["organ"], group_summary["series_group_id"]
        )
    ]
    group_summary = group_summary.sort_values(
        ["_organ_rank", "_entry_rank"]
    ).drop(columns=["_organ_rank", "_entry_rank"])

    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise FileExistsError("sample-review output already exists")
    output_dir.mkdir(parents=True)
    samples_path = output_dir / "provisional_sample_review.csv"
    groups_path = output_dir / "provisional_study_review.csv"
    resolved.to_csv(samples_path, index=False)
    group_summary.to_csv(groups_path, index=False)

    # Repeated publication or BioProject identifiers are a review warning because
    # nominally different connected GEO groups can still share donors.
    identifier_groups: dict[str, set[str]] = {}
    for row in group_summary.itertuples(index=False):
        for value in f"{row.geo_pubmed_ids} {row.geo_bioproject_ids}".split():
            if value:
                identifier_groups.setdefault(value, set()).add(row.series_group_id)
    repeated_identifiers = {
        key: sorted(values)
        for key, values in sorted(identifier_groups.items())
        if len(values) > 1
    }
    counts = (
        resolved.groupby("organ").size().reindex(TARGET_ORGANS, fill_value=0)
    )
    report = {
        "schema_version": 1,
        "status": "provisional_sample_review_ready_not_frozen",
        "code_commit": args.code_commit,
        "metadata_only": True,
        "expression_values_read": False,
        "efficacy_scoring_performed": False,
        "external_lockbox_frozen": False,
        "automated_decisions_are_final": False,
        "manual_decisions_complete": False,
        "provisional_groups_per_organ": expected_per_organ,
        "provisional_group_rows": int(len(group_summary)),
        "provisional_sample_rows": int(len(resolved)),
        "provisional_sample_counts": {
            organ: int(counts[organ]) for organ in TARGET_ORGANS
        },
        "repeated_publication_or_bioproject_ids": repeated_identifiers,
        "hashes": {
            "source_sample_triage_sha256": sha256(triage_path),
            "source_geo_study_review_sha256": sha256(geo_path),
            "shortlist_sha256": sha256(shortlist_path),
            "provisional_sample_review_sha256": sha256(samples_path),
            "provisional_study_review_sha256": sha256(groups_path),
        },
        "next_gate": (
            "Manually verify each exact sample, publication/BioProject, donor ID, "
            "technical/biological replicate status, and cross-study near-duplicate "
            "link. Replace rejected or overlapping studies from reserves, then "
            "preregister power and evaluation rules before freezing any lockbox or "
            "requesting expression."
        ),
    }
    report_path = output_dir / "sample_review_report.json"
    temporary = output_dir / "sample_review_report.json.tmp"
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, report_path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-triage", required=True)
    parser.add_argument("--expected-triage-sha256", required=True)
    parser.add_argument("--geo-study-review", required=True)
    parser.add_argument("--expected-geo-review-sha256", required=True)
    parser.add_argument("--shortlist", required=True)
    parser.add_argument("--expected-shortlist-sha256", required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    print(json.dumps(build_sample_review(args), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
