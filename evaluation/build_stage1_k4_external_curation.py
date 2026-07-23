#!/usr/bin/env python3
"""Build a metadata-only study curation workbook for external K4 confirmation.

This program does not select or freeze a cohort.  It re-applies the improved organ
classifier to the broad scout pool, attaches conservative metadata triage flags, and
collapses samples into connected GEO-series groups for manual study-level review.
No expression input is accepted and no model score is computed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

import pandas as pd

from attach_archs4_series import _series_tokens
from recover_organ_labels import _norm, classify_row, load_ontology


TARGET_ORGANS = ("adipose", "brain", "liver", "skeletal_muscle", "skin")
POSITIVE_REFERENCE = re.compile(
    r"\b(?:healthy|normal|control|unaffected|untreated|baseline|placebo|"
    r"vehicle|naive|without treatment|no treatment|wild[- ]?type|wt)\b",
    re.IGNORECASE,
)
ACTIVE_PERTURBATION = re.compile(
    r"\b(?:after|post(?![- ]?mortem)|irradiat\w*|"
    r"radiat\w*|exercise|intervention|transfect\w*|knockdown|overexpress\w*|"
    r"crispr|sirna|shrna|stimulat\w*|challeng\w*)\b",
    re.IGNORECASE,
)
DISEASE_CONTEXT = re.compile(
    r"\b(?:patient|lesion\w*|syndrome|tumou?r|cancer|"
    r"metasta\w*|pathology|case|adjacent|margin|uninvolved|perilesional)\b",
    re.IGNORECASE,
)
NONREFERENCE_STATUS = re.compile(
    r"\b(?:disease(?: state| status)?|diagnosis|condition)\s*:"
    r"(?!\s*(?:healthy|normal|control|unaffected|none|na|n/a)\b)\s*",
    re.IGNORECASE,
)
DEVELOPMENTAL_CONTEXT = re.compile(
    r"\b(?:fetal|foetal|embryonic|gestational|pediatric|paediatric|infant|child)\b",
    re.IGNORECASE,
)
ADJACENT_CONTEXT = re.compile(
    r"\b(?:adjacent|margin|paired normal|uninvolved|perilesional|non[- ]?lesional)\b",
    re.IGNORECASE,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _geo_urls(series_id: str) -> str:
    return ";".join(
        f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={token}"
        for token in sorted(_series_tokens(series_id))
    )


def triage_candidates(candidates: pd.DataFrame, ontology: dict) -> pd.DataFrame:
    rows = []
    for row in candidates.itertuples(index=False):
        classification = classify_row(
            row.source_name_ch1,
            row.title,
            row.characteristics_ch1,
            row.singlecellprobability,
            ontology,
            0.5,
        )
        text = _norm(
            " | ".join((
                str(row.source_name_ch1),
                str(row.title),
                str(row.characteristics_ch1),
            ))
        )
        extra_flags = []
        if ACTIVE_PERTURBATION.search(text):
            extra_flags.append("active_perturbation")
        if DISEASE_CONTEXT.search(text) or NONREFERENCE_STATUS.search(text):
            extra_flags.append("disease_context")
        if DEVELOPMENTAL_CONTEXT.search(text):
            extra_flags.append("developmental_context")
        if ADJACENT_CONTEXT.search(text):
            extra_flags.append("adjacent_context")

        classifier_eligible = (
            classification["tier"] == "high_confidence"
            and classification["organ"] == row.organ
        )
        positive_reference = bool(POSITIVE_REFERENCE.search(text))
        hard_manual_context = bool(
            {"active_perturbation", "developmental_context", "adjacent_context"}
            & set(extra_flags)
        )
        if not classifier_eligible:
            triage_tier = "excluded_by_classifier"
        elif positive_reference and not hard_manual_context and not extra_flags:
            triage_tier = "priority_a_clean_positive_reference"
        else:
            triage_tier = "priority_b_manual_review"

        rows.append({
            **row._asdict(),
            "triage_tier": triage_tier,
            "positive_reference_marker": positive_reference,
            "classifier_tier": classification["tier"],
            "classifier_reasons": classification["all_reasons"],
            "triage_flags": ";".join(extra_flags),
        })
    return pd.DataFrame.from_records(rows)


def build_workbook(args: argparse.Namespace) -> dict:
    if re.fullmatch(r"[0-9a-f]{40}", args.code_commit) is None:
        raise ValueError("curation workbook requires a full code commit")
    candidate_path = Path(args.candidate_metadata)
    scout_report_path = Path(args.scout_report)
    scout_report = json.loads(scout_report_path.read_text())
    if scout_report.get("metadata_only") is not True:
        raise ValueError("source scout is not marked metadata-only")
    if scout_report.get("expression_values_read") is not False:
        raise ValueError("source scout does not prove expression stayed sealed")
    candidate_hash = _sha256(candidate_path)
    if candidate_hash != args.expected_candidate_sha256:
        raise ValueError("source candidate metadata hash mismatch")
    if (
        scout_report.get("hashes", {}).get("candidate_metadata_sha256")
        != candidate_hash
    ):
        raise ValueError("source scout report has a different candidate hash")

    candidates = pd.read_parquet(candidate_path)
    required = {
        "sample_id", "series_id", "series_group_id", "organ",
        "source_name_ch1", "title", "characteristics_ch1",
        "singlecellprobability", "submitted_after_v11_creation",
    }
    missing = sorted(required - set(candidates.columns))
    if missing:
        raise KeyError(f"candidate metadata is missing fields: {missing}")
    ontology_path = Path(args.ontology)
    triaged = triage_candidates(candidates, load_ontology(ontology_path))

    rank = {
        "priority_a_clean_positive_reference": 0,
        "priority_b_manual_review": 1,
        "excluded_by_classifier": 2,
    }
    triaged["_triage_rank"] = triaged["triage_tier"].map(rank)
    group_organs = triaged.groupby("series_group_id")["organ"].agg(
        lambda values: "|".join(sorted(set(values)))
    )
    workbook_rows = []
    for (organ, group_id), group in triaged.groupby(
        ["organ", "series_group_id"], sort=True
    ):
        ordered = group.sort_values(
            ["_triage_rank", "submitted_after_v11_creation", "sample_id"],
            ascending=[True, False, True],
        )
        representative = ordered.iloc[0]
        counts = group["triage_tier"].value_counts()
        priority_samples = ordered[
            ordered["triage_tier"] != "excluded_by_classifier"
        ]["sample_id"].head(10)
        flags = sorted({
            flag
            for value in group["triage_flags"]
            for flag in str(value).split(";")
            if flag
        })
        classifier_reasons = sorted({
            reason
            for value in group["classifier_reasons"]
            for reason in str(value).split(";")
            if reason
        })
        n_a = int(counts.get("priority_a_clean_positive_reference", 0))
        n_b = int(counts.get("priority_b_manual_review", 0))
        n_excluded = int(counts.get("excluded_by_classifier", 0))
        automated_priority = (
            "A"
            if n_a == len(group) and not flags and not classifier_reasons
            else ("B" if n_a + n_b else "excluded_only")
        )
        organs_in_group = group_organs[group_id]
        workbook_rows.append({
            "organ": organ,
            "series_group_id": group_id,
            "organs_in_connected_group": organs_in_group,
            "cross_organ_connected_group": "|" in organs_in_group,
            "series_tokens": " ".join(sorted({
                token
                for value in group["series_id"]
                for token in _series_tokens(value)
            })),
            "geo_urls": _geo_urls(" ".join(group["series_id"].astype(str))),
            "n_samples": int(len(group)),
            "n_post_cutoff_samples": int(
                group["submitted_after_v11_creation"].sum()
            ),
            "n_priority_a": n_a,
            "n_priority_b": n_b,
            "n_excluded_by_classifier": n_excluded,
            "automated_priority": automated_priority,
            "representative_sample_id": representative["sample_id"],
            "representative_source": representative["source_name_ch1"],
            "representative_title": representative["title"],
            "representative_characteristics": representative[
                "characteristics_ch1"
            ],
            "triage_flags_seen": ";".join(flags),
            "classifier_reasons_seen": ";".join(classifier_reasons),
            "candidate_sample_ids_first10": " ".join(priority_samples),
            "review_decision": "pending",
            "reviewed_organ": "",
            "bulk_tissue_confirmed": "",
            "healthy_control_confirmed": "",
            "publication_or_bioproject": "",
            "donor_overlap_audit": "",
            "near_duplicate_audit": "",
            "review_notes": "",
        })
    workbook = pd.DataFrame(workbook_rows)
    workbook["_organ_rank"] = workbook["organ"].map({
        organ: i for i, organ in enumerate(TARGET_ORGANS)
    })
    workbook["_priority_rank"] = workbook["automated_priority"].map(
        {"A": 0, "B": 1, "excluded_only": 2}
    )
    workbook = workbook.sort_values(
        [
            "_organ_rank", "_priority_rank", "n_priority_a",
            "n_priority_b", "n_post_cutoff_samples", "series_group_id",
        ],
        ascending=[True, True, False, False, False, True],
    ).drop(columns=["_organ_rank", "_priority_rank"]).reset_index(drop=True)
    triaged = triaged.drop(columns="_triage_rank")

    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise FileExistsError("curation-workbook output already exists")
    output_dir.mkdir(parents=True)
    triage_path = output_dir / "sample_triage.parquet"
    workbook_path = output_dir / "study_curation_workbook.csv"
    triaged.to_parquet(triage_path, index=False)
    workbook.to_csv(workbook_path, index=False)

    tier_counts = triaged.groupby(["organ", "triage_tier"]).size().unstack(
        fill_value=0
    )
    priority_counts = workbook.groupby(["organ", "automated_priority"]).size().unstack(
        fill_value=0
    )
    report = {
        "schema_version": 1,
        "status": "curation_workbook_complete_not_external_lockbox",
        "code_commit": args.code_commit,
        "metadata_only": True,
        "expression_values_read": False,
        "efficacy_scoring_performed": False,
        "external_lockbox_frozen": False,
        "automated_decisions_are_final": False,
        "source_candidate_rows": int(len(candidates)),
        "study_groups": int(len(workbook)),
        "sample_triage_counts": tier_counts.to_dict("index"),
        "study_priority_counts": priority_counts.to_dict("index"),
        "hashes": {
            "source_candidate_sha256": candidate_hash,
            "source_scout_report_sha256": _sha256(scout_report_path),
            "ontology_sha256": _sha256(ontology_path),
            "sample_triage_sha256": _sha256(triage_path),
            "study_curation_workbook_sha256": _sha256(workbook_path),
        },
        "next_gate": (
            "Manually review connected studies, verify GEO/publication/BioProject/"
            "donor and near-duplicate links, then write and validate an explicit "
            "accepted-series/sample manifest before any expression request."
        ),
    }
    temporary_report = output_dir / "curation_report.json.tmp"
    temporary_report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    os.replace(temporary_report, output_dir / "curation_report.json")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-metadata", required=True)
    parser.add_argument("--scout-report", required=True)
    parser.add_argument("--expected-candidate-sha256", required=True)
    parser.add_argument("--ontology", required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    print(json.dumps(build_workbook(args), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
