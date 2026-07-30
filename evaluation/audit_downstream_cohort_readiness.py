#!/usr/bin/env python3
"""Fail-closed readiness audit for the August 17 downstream tasks.

The audit answers the five questions required before a task may enter the
downstream harness: exact cohort, sample count, independent group count, label
source, and whether the expression matrix is already local.  It does not access
outcomes from a frozen final-test cohort and performs no model fitting.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

import pandas as pd


ORGANS = (
    "adipose",
    "brain",
    "colon",
    "heart",
    "liver",
    "lung",
    "skeletal_muscle",
    "skin",
)

_ORGAN_PATTERNS = (
    ("adipose", r"\badipose\b"),
    ("brain", r"\b(brain|cerebr\w*|hippocamp\w*)\b"),
    ("colon", r"\bcolon\b"),
    ("heart", r"\b(heart|ventricle|cardiac)\b"),
    ("liver", r"\bliver\b"),
    ("lung", r"\blung\b"),
    ("skin", r"\bskin\b"),
    (
        "skeletal_muscle",
        r"\b(skeletal muscle|soleus|quadriceps|gastrocnemius|"
        r"extensor digitorum|tibialis anterior|plantaris)\b",
    ),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def map_osdr_organ(value: object) -> str:
    text = " ".join(str(value).casefold().replace("_", " ").split())
    matches = [organ for organ, pattern in _ORGAN_PATTERNS if re.search(pattern, text)]
    return matches[0] if len(matches) == 1 else ""


def build_osdr_candidate(metadata: pd.DataFrame) -> pd.DataFrame:
    required = {
        "id.accession",
        "id.sample name",
        "study.characteristics.material type",
        "study.factor value.spaceflight",
        "counts_file",
        "counts_path",
    }
    missing = sorted(required - set(metadata.columns))
    if missing:
        raise ValueError(f"OSDR metadata lacks required columns: {missing}")
    frame = metadata.copy()
    frame["downstream_organ"] = frame[
        "study.characteristics.material type"
    ].map(map_osdr_organ)
    normalized = (
        frame["study.factor value.spaceflight"].fillna("").astype(str).str.casefold().str.strip()
    )
    frame["downstream_label"] = normalized.map({"space flight": 1, "ground control": 0})
    frame = frame[
        frame["downstream_organ"].isin(ORGANS) & frame["downstream_label"].notna()
    ].copy()
    eligible = []
    for _, group in frame.groupby(["id.accession", "downstream_organ"], sort=True):
        if group["downstream_label"].nunique() == 2:
            eligible.append(group)
    if not eligible:
        raise ValueError("no OSDR study-organ unit has both exact flight and ground labels")
    frame = pd.concat(eligible, axis=0).sort_values(
        ["id.accession", "downstream_organ", "id.sample name"]
    )
    if frame["id.sample name"].isna().any():
        raise ValueError("eligible OSDR cohort contains a missing sample name")
    return frame


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--osdr-metadata", default="data/osdr/metadata_new.csv")
    parser.add_argument(
        "--archs4-labels",
        default="artifacts/stage1_label_recovery/recovered_labels.parquet",
    )
    parser.add_argument("--tcga-expression", default="data/tcga/tcga_expression.parquet")
    parser.add_argument(
        "--output-dir", default="artifacts/final_evaluation/downstream_readiness"
    )
    args = parser.parse_args()

    osdr_path = Path(args.osdr_metadata)
    archs4_path = Path(args.archs4_labels)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    metadata = pd.read_csv(osdr_path, low_memory=False)
    candidate = build_osdr_candidate(metadata)
    candidate_path = output_dir / "osdr_spaceflight_candidate_metadata.csv"
    candidate.to_csv(candidate_path, index=False)
    local_count_files = {
        str(path)
        for path in candidate["counts_path"].dropna().astype(str).unique()
        if os.path.isfile(path)
    }
    organ_summary = (
        candidate.groupby("downstream_organ", sort=True)
        .agg(
            samples=("downstream_label", "size"),
            studies=("id.accession", "nunique"),
            flight=("downstream_label", "sum"),
        )
        .reset_index()
    )
    organ_summary["ground"] = organ_summary["samples"] - organ_summary["flight"]

    archs4 = pd.read_parquet(archs4_path)
    archive_dates = pd.to_datetime(
        archs4["submission_date"], errors="coerce", format="mixed"
    )
    latest_archs4_date = archive_dates.max()
    archs4_label_rows = int(
        (
            archs4["organ"].isin(ORGANS)
            & (archs4["flag_disease"].astype(bool) | archs4["flag_tumor"].astype(bool))
        ).sum()
    )

    tasks = [
        {
            "task": "OSDR mouse spaceflight versus exact ground control",
            "cohort": (
                "strict eight-organ OSDR RNA-seq study-organ units containing both "
                "exact Space Flight and Ground Control labels"
            ),
            "samples": int(len(candidate)),
            "groups": int(candidate["id.accession"].nunique()),
            "study_organ_units": int(
                candidate[["id.accession", "downstream_organ"]].drop_duplicates().shape[0]
            ),
            "label_source": "structured OSDR study.factor value.spaceflight",
            "expression_local": len(local_count_files)
            == candidate["counts_file"].nunique(),
            "local_expression_files": len(local_count_files),
            "required_expression_files": int(candidate["counts_file"].nunique()),
            "readiness": (
                "ready_after_versioned_download_and_qc"
                if len(local_count_files) < candidate["counts_file"].nunique()
                else "ready"
            ),
        },
        {
            "task": "ARCHS4 within-organ disease or tumor versus control",
            "cohort": "not frozen; free-text candidates require independent label curation",
            "samples": None,
            "groups": None,
            "label_source": (
                "ARCHS4/GEO free text; existing keyword flags are candidate retrieval "
                "only and are not valid phenotype labels"
            ),
            "expression_local": Path("data/archs4/current/human_gene_v2.latest.h5").is_file(),
            "candidate_positive_rows_in_historical_label_table": archs4_label_rows,
            "historical_label_table_latest_submission_date": (
                latest_archs4_date.date().isoformat()
                if pd.notna(latest_archs4_date)
                else None
            ),
            "readiness": "cut_from_core_until_curated_study_disjoint_labels_exist",
        },
        {
            "task": "low-label adaptation curves",
            "cohort": "derived from the first frozen labeled downstream cohort",
            "samples": int(len(candidate)),
            "groups": int(candidate["id.accession"].nunique()),
            "label_source": "inherits OSDR structured labels",
            "expression_local": len(local_count_files)
            == candidate["counts_file"].nunique(),
            "readiness": "extension_after_primary_osdr_harness_passes",
        },
        {
            "task": "TCGA disease or cancer endpoint",
            "cohort": "not frozen",
            "samples": None,
            "groups": None,
            "label_source": "not present locally",
            "expression_local": Path(args.tcga_expression).is_file(),
            "readiness": "cut_from_core",
        },
    ]
    report = {
        "schema_version": 1,
        "status": "downstream_cohort_readiness_audited",
        "selection_outcomes_accessed": False,
        "model_fitting_performed": False,
        "source_sha256": {
            "osdr_metadata": sha256_file(osdr_path),
            "archs4_candidate_labels": sha256_file(archs4_path),
        },
        "tasks": tasks,
        "osdr_organ_summary": organ_summary.to_dict(orient="records"),
        "osdr_candidate_metadata": str(candidate_path),
        "osdr_candidate_metadata_sha256": sha256_file(candidate_path),
    }
    report_path = output_dir / "readiness_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
