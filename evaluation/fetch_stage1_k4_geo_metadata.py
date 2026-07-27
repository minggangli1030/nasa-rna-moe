#!/usr/bin/env python3
"""Fetch GEO series-level metadata for the Stage 1 external curation workbook.

Only the public GEO SOFT *series record* is requested. Supplementary files, SRA
objects, sample expression, and model evaluation are out of scope. Automated context
flags prioritize human review and never accept or reject a study.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
import urllib.request
from pathlib import Path

import pandas as pd

from attach_archs4_series import _series_tokens


TARGET_ORGANS = ("adipose", "brain", "liver", "skeletal_muscle", "skin")
GEO_URL = (
    "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?"
    "acc={accession}&targ=self&form=text&view=full"
)
CONTEXT_PATTERNS = {
    "tumor_or_cancer": re.compile(
        r"\b(?:tumou?r|cancer|carcinoma|glioma|metasta\w*|sarcoma|"
        r"melanoma|leukemia|lymphoma|neoplasm|HCC|GBM|LGG|CRC)\b",
        re.IGNORECASE,
    ),
    "disease_study": re.compile(
        r"\b(?:disease|patient|syndrome|fibrosis|cirrhosis|diabet\w*|"
        r"obes\w*|heart failure|parkinson|alzheimer|psoriasis|dermatitis|"
        r"sarcopenia|dystrophy|infect\w*)\b",
        re.IGNORECASE,
    ),
    "cell_or_model": re.compile(
        r"\b(?:cell line|cultured|organoid|stem cells?|iPSC|xenograft|"
        r"HepG2|fibroblast|keratinocyte|hepatocyte|myotube)\b",
        re.IGNORECASE,
    ),
    "nonbulk_assay": re.compile(
        r"\b(?:single[- ]cell|single[- ]nucleus|scRNA|snRNA|spatial|"
        r"Visium|10x|DropSeq|Ribo[- ]?seq)\b",
        re.IGNORECASE,
    ),
    "active_intervention": re.compile(
        r"\b(?:intervention|treated|treatment|exercise|irradiat\w*|"
        r"drug|knockdown|transfect\w*|challenge)\b",
        re.IGNORECASE,
    ),
    "developmental": re.compile(
        r"\b(?:fetal|foetal|embryonic|gestational|pediatric|infant|child)\b",
        re.IGNORECASE,
    ),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_series_soft(text: str, expected_accession: str) -> dict:
    fields: dict[str, list[str]] = {}
    header = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r")
        if line.startswith("^SERIES = "):
            header = line.split("=", 1)[1].strip()
        elif line.startswith("!Series_") and " = " in line:
            key, value = line[1:].split(" = ", 1)
            fields.setdefault(key, []).append(value.strip())
    if header != expected_accession:
        raise ValueError(
            f"GEO SOFT accession mismatch: expected {expected_accession}, got {header}"
        )
    reported = fields.get("Series_geo_accession", [])
    if reported != [expected_accession]:
        raise ValueError("GEO SOFT record lacks its exact series accession")

    def joined(key: str, separator: str = " | ") -> str:
        return separator.join(fields.get(key, []))

    relations = fields.get("Series_relation", [])
    bioprojects = sorted({
        match
        for value in relations
        for match in re.findall(r"\bPRJNA\d+\b", value)
    })
    pubmed = sorted(set(fields.get("Series_pubmed_id", [])))
    combined = " ".join((
        joined("Series_title"),
        joined("Series_summary"),
        joined("Series_overall_design"),
    ))
    context_flags = [
        name for name, pattern in CONTEXT_PATTERNS.items()
        if pattern.search(combined)
    ]
    return {
        "series_accession": expected_accession,
        "series_title": joined("Series_title"),
        "series_status": joined("Series_status"),
        "series_submission_date": joined("Series_submission_date"),
        "series_last_update_date": joined("Series_last_update_date"),
        "series_type": joined("Series_type"),
        "series_summary": joined("Series_summary"),
        "series_overall_design": joined("Series_overall_design"),
        "pubmed_ids": " ".join(pubmed),
        "bioproject_ids": " ".join(bioprojects),
        "n_geo_samples": len(fields.get("Series_sample_id", [])),
        "geo_context_flags": ";".join(context_flags),
    }


def select_review_groups(
    workbook: pd.DataFrame,
    per_organ: int,
    target_organs: tuple[str, ...] = TARGET_ORGANS,
) -> pd.DataFrame:
    usable = workbook[workbook["automated_priority"] != "excluded_only"].copy()
    parts = []
    for organ in target_organs:
        subset = usable[usable["organ"] == organ].head(per_organ)
        if len(subset) != per_organ:
            raise ValueError(
                f"not enough non-excluded study groups for {organ}: {len(subset)}"
            )
        parts.append(subset)
    return pd.concat(parts, ignore_index=True)


def select_explicit_review_groups(
    workbook: pd.DataFrame,
    requested: list[dict],
    target_organs: tuple[str, ...] = TARGET_ORGANS,
) -> pd.DataFrame:
    """Select exact, ordered organ/group pairs for a targeted reserve review."""
    if not requested:
        raise ValueError("explicit GEO review list is empty")
    parts = []
    seen = set()
    for entry in requested:
        if not isinstance(entry, dict):
            raise TypeError("explicit GEO review entries must be objects")
        organ = entry.get("organ")
        group_id = entry.get("series_group_id")
        if organ not in target_organs:
            raise ValueError(f"unsupported explicit-review organ: {organ!r}")
        key = (organ, group_id)
        if key in seen:
            raise ValueError(f"duplicate explicit-review pair: {key}")
        seen.add(key)
        match = workbook[
            (workbook["organ"] == organ)
            & (workbook["series_group_id"] == group_id)
            & (workbook["automated_priority"] != "excluded_only")
        ]
        if len(match) != 1:
            raise ValueError(
                f"expected one non-excluded workbook row for {key}, found {len(match)}"
            )
        parts.append(match)
    return pd.concat(parts, ignore_index=True)


def fetch_soft(accession: str, timeout: int) -> bytes:
    request = urllib.request.Request(
        GEO_URL.format(accession=accession),
        headers={"User-Agent": "nasa-rna-moe-metadata-review/1.0"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read()
    if not payload.startswith(b"^SERIES = "):
        raise ValueError(f"unexpected GEO response for {accession}")
    return payload


def build_geo_review(args: argparse.Namespace) -> dict:
    if re.fullmatch(r"[0-9a-f]{40}", args.code_commit) is None:
        raise ValueError("GEO metadata review requires a full code commit")
    workbook_path = Path(args.workbook)
    if sha256(workbook_path) != args.expected_workbook_sha256:
        raise ValueError("curation workbook hash mismatch")
    workbook = pd.read_csv(workbook_path)
    raw_target_organs = getattr(args, "target_organs", None)
    target_organs = (
        tuple(value.strip() for value in raw_target_organs.split(",") if value.strip())
        if raw_target_organs
        else TARGET_ORGANS
    )
    if (
        not target_organs
        or len(set(target_organs)) != len(target_organs)
        or not set(target_organs).issubset(set(workbook["organ"]))
    ):
        raise ValueError("target-organ family is empty, duplicated, or absent")
    explicit_groups_path = getattr(args, "explicit_groups", None)
    if explicit_groups_path:
        explicit_path = Path(explicit_groups_path)
        if sha256(explicit_path) != args.expected_explicit_groups_sha256:
            raise ValueError("explicit GEO review-list hash mismatch")
        explicit = json.loads(explicit_path.read_text())
        if explicit.get("metadata_only") is not True:
            raise ValueError("explicit GEO review list is not metadata-only")
        if explicit.get("expression_values_read") is not False:
            raise ValueError("explicit GEO review list does not seal expression")
        selected = select_explicit_review_groups(
            workbook, explicit.get("entries", []), target_organs
        )
        selection_mode = "explicit_ordered_organ_group_pairs"
        selected_groups_per_organ = {
            organ: int(count)
            for organ, count in selected.groupby("organ").size().items()
        }
        explicit_hash = sha256(explicit_path)
    else:
        selected = select_review_groups(workbook, args.per_organ, target_organs)
        selection_mode = "workbook_priority_head_per_organ"
        selected_groups_per_organ = {
            organ: args.per_organ for organ in target_organs
        }
        explicit_hash = None
    accessions = sorted({
        token
        for value in selected["series_tokens"]
        for token in _series_tokens(value)
    })

    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise FileExistsError("GEO metadata-review output already exists")
    soft_dir = output_dir / "soft"
    soft_dir.mkdir(parents=True)

    records = []
    for index, accession in enumerate(accessions):
        if index:
            time.sleep(args.request_delay_seconds)
        payload = fetch_soft(accession, args.timeout_seconds)
        soft_path = soft_dir / f"{accession}.soft"
        soft_path.write_bytes(payload)
        parsed = parse_series_soft(payload.decode("utf-8"), accession)
        parsed["soft_sha256"] = sha256(soft_path)
        parsed["geo_url"] = GEO_URL.format(accession=accession)
        records.append(parsed)
        print(
            f"geo_metadata={index + 1}/{len(accessions)} accession={accession}",
            flush=True,
        )
    series_metadata = pd.DataFrame(records).sort_values("series_accession")

    metadata_by_accession = series_metadata.set_index("series_accession")
    enriched_rows = []
    for row in selected.itertuples(index=False):
        tokens = sorted(_series_tokens(row.series_tokens))
        token_records = metadata_by_accession.loc[tokens]
        if isinstance(token_records, pd.Series):
            token_records = token_records.to_frame().T
        enriched_rows.append({
            **row._asdict(),
            "geo_series_titles": " || ".join(token_records["series_title"]),
            "geo_overall_designs": " || ".join(
                token_records["series_overall_design"]
            ),
            "geo_summaries": " || ".join(token_records["series_summary"]),
            "geo_pubmed_ids": " ".join(sorted({
                value
                for values in token_records["pubmed_ids"]
                for value in str(values).split()
                if value and value != "nan"
            })),
            "geo_bioproject_ids": " ".join(sorted({
                value
                for values in token_records["bioproject_ids"]
                for value in str(values).split()
                if value and value != "nan"
            })),
            "geo_context_flags": ";".join(sorted({
                flag
                for values in token_records["geo_context_flags"]
                for flag in str(values).split(";")
                if flag and flag != "nan"
            })),
            "geo_review_decision": "pending",
            "geo_review_notes": "",
        })
    enriched = pd.DataFrame(enriched_rows)
    series_path = output_dir / "geo_series_metadata.csv"
    enriched_path = output_dir / "selected_study_review.csv"
    series_metadata.to_csv(series_path, index=False)
    enriched.to_csv(enriched_path, index=False)

    report = {
        "schema_version": 1,
        "status": "geo_metadata_review_ready_not_external_lockbox",
        "code_commit": args.code_commit,
        "metadata_only": True,
        "expression_values_read": False,
        "supplementary_files_downloaded": False,
        "efficacy_scoring_performed": False,
        "external_lockbox_frozen": False,
        "automated_decisions_are_final": False,
        "selection_mode": selection_mode,
        "target_organs": list(target_organs),
        "selected_groups_per_organ": selected_groups_per_organ,
        "selected_organ_group_rows": int(len(selected)),
        "fetched_geo_series": int(len(accessions)),
        "hashes": {
            "source_workbook_sha256": sha256(workbook_path),
            "geo_series_metadata_sha256": sha256(series_path),
            "selected_study_review_sha256": sha256(enriched_path),
        },
        "next_gate": (
            "Manually read the pinned GEO summaries/designs and linked publications; "
            "record accept/reject decisions and donor/near-duplicate audits before "
            "constructing any exact sample manifest."
        ),
    }
    if explicit_hash is not None:
        report["hashes"]["explicit_groups_sha256"] = explicit_hash
    report_path = output_dir / "geo_review_report.json"
    temporary = output_dir / "geo_review_report.json.tmp"
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, report_path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", required=True)
    parser.add_argument("--expected-workbook-sha256", required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--per-organ", type=int, default=20)
    parser.add_argument(
        "--target-organs",
        help="Comma-separated ordered organ family; defaults to the historical K4 set.",
    )
    parser.add_argument("--explicit-groups")
    parser.add_argument("--expected-explicit-groups-sha256")
    parser.add_argument("--request-delay-seconds", type=float, default=0.4)
    parser.add_argument("--timeout-seconds", type=int, default=60)
    args = parser.parse_args()
    print(json.dumps(build_geo_review(args), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
