#!/usr/bin/env python3
"""Recover, normalize, and tier ARCHS4 human organ labels for Stage 1.

Input is the portable metadata parquet from
``preprocessing/export_archs4_sample_metadata.py`` plus the frozen ontology map
``data/ontology/uberon_organ_map.json``. This implements the plan's label-recovery
track: parse ``characteristics_ch1`` key/value fields (which the original audit
ignored), normalize explicit anatomy to a UBERON-style organ, keep disease/tumor and
cell-source status as SEPARATE fields, and assign ``high_confidence`` / ``ambiguous``
/ ``unlabeled`` tiers with a full provenance trail. Only high-confidence rows are
eligible for the definitive cohort; ambiguous rows are stratified into a compact PI
review sheet.

No expression data and no H5 access — pure metadata reconciliation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd


# characteristics_ch1 keys whose values are trusted explicit anatomy.
ANATOMY_KEYS = (
    "tissue", "organ", "source tissue", "tissue type", "tissue source",
    "anatomic site", "anatomical site", "body site", "tissue region",
    "tissue subtype", "source name",
)
# characteristics keys that signal a cellular rather than tissue sample.
CELL_KEYS = ("cell type", "cell line", "cell-line", "cell_line", "cell subtype")

DEFAULT_SINGLE_CELL_THRESHOLD = 0.5
DEFAULT_MIN_TRAINING_ROWS = 1000
DEFAULT_MIN_SERIES = 30


def _norm(text: str) -> str:
    """Lowercase and collapse whitespace for whole-word matching."""
    return re.sub(r"\s+", " ", str(text).replace("\t", " ")).strip().lower()


def _word_regex(terms) -> re.Pattern:
    # Terms may already contain regex fragments (e.g. "tumou?r"); keep them as-is but
    # anchor on word boundaries. Longest-first avoids partial shadowing.
    ordered = sorted(set(terms), key=len, reverse=True)
    return re.compile(r"\b(?:" + "|".join(ordered) + r")\b", re.IGNORECASE)


def load_ontology(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text())
    organ_patterns = {}
    adjacent_patterns = {}
    uberon = {}
    for organ, spec in data["organs"].items():
        uberon[organ] = spec.get("uberon_id", "")
        organ_patterns[organ] = _word_regex([re.escape(s) for s in spec["synonyms"]])
        adj = spec.get("adjacent", [])
        adjacent_patterns[organ] = _word_regex([re.escape(s) for s in adj]) if adj else None
    return {
        "raw": data,
        "uberon": uberon,
        "organ_patterns": organ_patterns,
        "adjacent_patterns": adjacent_patterns,
        "tumor": _word_regex(data.get("tumor_terms", [])) if data.get("tumor_terms") else None,
        "disease": _word_regex(data.get("disease_terms", [])) if data.get("disease_terms") else None,
        "cell_source": _word_regex([re.escape(t) for t in data.get("cell_source_terms", [])]) if data.get("cell_source_terms") else None,
        "primary_cell": _word_regex([re.escape(t) for t in data.get("primary_cell_terms", [])]) if data.get("primary_cell_terms") else None,
    }


def parse_characteristics(raw: str) -> dict:
    """Split ARCHS4 ``characteristics_ch1`` into a lowercase key -> value dict."""
    fields: dict[str, str] = {}
    for token in str(raw).split("\t"):
        if ":" not in token:
            continue
        key, value = token.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key and key not in fields:
            fields[key] = value
    return fields


def _match_organs(text: str, organ_patterns: dict) -> set:
    if not text:
        return set()
    return {organ for organ, pattern in organ_patterns.items() if pattern.search(text)}


def classify_row(
    source_name: str,
    title: str,
    characteristics: str,
    single_cell_probability: float,
    ontology: dict,
    single_cell_threshold: float,
) -> dict:
    organ_patterns = ontology["organ_patterns"]
    kv = parse_characteristics(characteristics)

    strong_text = " | ".join(_norm(kv[k]) for k in kv if k in ANATOMY_KEYS)
    source_text = _norm(source_name)
    title_text = _norm(title)
    combined = " | ".join(t for t in (source_text, title_text, _norm(characteristics)) if t)

    strong = _match_organs(strong_text, organ_patterns)
    medium = _match_organs(source_text, organ_patterns)
    weak = _match_organs(title_text, organ_patterns)
    all_organs = strong | medium | weak

    # Separate status flags — never folded into the organ label.
    flags = {
        "tumor": bool(ontology["tumor"] and ontology["tumor"].search(combined)),
        "disease": bool(ontology["disease"] and ontology["disease"].search(combined)),
        "cell_source": bool(
            (ontology["cell_source"] and ontology["cell_source"].search(combined))
            or any(k in kv for k in CELL_KEYS)
        ),
        "primary_cell": bool(ontology["primary_cell"] and ontology["primary_cell"].search(combined)),
        "single_cell": bool(
            single_cell_probability is not None
            and not (isinstance(single_cell_probability, float) and np.isnan(single_cell_probability))
            and float(single_cell_probability) >= single_cell_threshold
        ),
    }

    # Label + evidence precedence: explicit characteristics > source_name > title.
    label = None
    evidence = "none"
    if len(strong) == 1:
        label, evidence = next(iter(strong)), "characteristics_tissue"
    elif len(strong) > 1:
        evidence = "conflict_characteristics"
    elif len(medium) == 1:
        label, evidence = next(iter(medium)), "source_name"
    elif len(medium) > 1:
        evidence = "conflict_source_name"
    elif len(weak) == 1:
        label, evidence = next(iter(weak)), "title_only"
    elif len(weak) > 1:
        evidence = "conflict_title"

    # Boundary tissue: the labeled organ's own adjacent-region terms appearing in the
    # text (e.g. "bile duct" near a liver sample) mean the exact anatomy is uncertain.
    adjacent_hits = []
    if label is not None:
        pattern = ontology["adjacent_patterns"].get(label)
        if pattern is not None and pattern.search(combined):
            adjacent_hits = [label]

    reasons: list[str] = []
    if label is None:
        tier = "unlabeled" if not all_organs else "ambiguous"
        if all_organs:
            reasons.append(evidence if evidence.startswith("conflict") else "multi_field_conflict")
        else:
            reasons.append("no_anatomy_match")
    else:
        if len(all_organs) > 1:
            reasons.append("cross_field_conflict")
        if evidence == "title_only":
            reasons.append("weak_title_only_evidence")
        for name in ("cell_source", "single_cell", "tumor", "primary_cell", "disease"):
            if flags[name]:
                reasons.append(name if name != "disease" else "disease_nontumor")
        if adjacent_hits:
            reasons.append("adjacent_anatomy")
        tier = "high_confidence" if not reasons else "ambiguous"

    return {
        "organ": label if label is not None else "",
        "uberon_id": ontology["uberon"].get(label, "") if label else "",
        "tier": tier,
        "evidence": evidence,
        "all_matched_organs": "|".join(sorted(all_organs)),
        "strong_organs": "|".join(sorted(strong)),
        "source_organs": "|".join(sorted(medium)),
        "title_organs": "|".join(sorted(weak)),
        "tissue_value": kv.get("tissue", ""),
        "adjacent_organs": "|".join(adjacent_hits),
        "flag_tumor": flags["tumor"],
        "flag_disease": flags["disease"],
        "flag_cell_source": flags["cell_source"],
        "flag_primary_cell": flags["primary_cell"],
        "flag_single_cell": flags["single_cell"],
        "review_reason": reasons[0] if reasons else "",
        "all_reasons": ";".join(reasons),
    }


def _sha256_lines(values) -> str:
    payload = "\n".join(values) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def recover(args) -> dict:
    ontology = load_ontology(args.ontology)
    ontology_hash = hashlib.sha256(Path(args.ontology).read_bytes()).hexdigest()
    meta = pd.read_parquet(args.metadata)
    for column in ("geo_accession", "series_id", "source_name_ch1", "title", "characteristics_ch1"):
        if column not in meta.columns:
            raise KeyError(f"metadata parquet missing required column: {column}")
    if "singlecellprobability" not in meta.columns:
        meta["singlecellprobability"] = np.nan

    results = [
        classify_row(
            row.source_name_ch1, row.title, row.characteristics_ch1,
            row.singlecellprobability, ontology, args.single_cell_threshold,
        )
        for row in meta.itertuples(index=False)
    ]
    recovered = pd.concat(
        [meta.reset_index(drop=True), pd.DataFrame(results)], axis=1
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    recovered.to_parquet(output_dir / "recovered_labels.parquet", index=False)

    # Per-organ tier summary against the frozen Gate 0 thresholds.
    labeled = recovered[recovered["organ"] != ""]
    summary_rows = []
    for organ, subset in labeled.groupby("organ", sort=True):
        hc = subset[subset["tier"] == "high_confidence"]
        summary_rows.append({
            "organ": organ,
            "uberon_id": ontology["uberon"].get(organ, ""),
            "n_high_confidence": int(len(hc)),
            "n_ambiguous": int((subset["tier"] == "ambiguous").sum()),
            "n_series_high_confidence": int(hc["series_id"].nunique()),
            "meets_min_training_rows": bool(len(hc) >= args.min_training_rows),
            "meets_min_series": bool(hc["series_id"].nunique() >= args.min_series),
        })
    summary = pd.DataFrame(summary_rows)
    if not summary.empty:
        summary = summary.sort_values("n_high_confidence", ascending=False)
    summary.to_csv(output_dir / "tier_summary.csv", index=False)

    # Stratified PI ambiguity sheet: up to N rows per (organ-or-none, reason).
    ambiguous = recovered[recovered["tier"] == "ambiguous"].copy()
    ambiguous["organ_key"] = ambiguous["organ"].replace("", "none")
    sheet_parts = []
    rng_cols = ["geo_accession", "series_id", "organ_key", "review_reason"]
    for _, group in ambiguous.sort_values(rng_cols).groupby(["organ_key", "review_reason"], sort=True):
        sheet_parts.append(group.head(args.per_reason))
    sheet_cols = [
        "geo_accession", "series_id", "organ", "review_reason", "all_reasons",
        "evidence", "all_matched_organs", "tissue_value", "adjacent_organs",
        "flag_tumor", "flag_disease", "flag_cell_source", "flag_primary_cell",
        "flag_single_cell", "source_name_ch1", "title", "characteristics_ch1",
    ]
    if sheet_parts:
        sheet = pd.concat(sheet_parts).sort_values(["organ_key", "review_reason", "geo_accession"])
        sheet[sheet_cols].to_csv(output_dir / "pi_ambiguity_sheet.csv", index=False)
    else:
        pd.DataFrame(columns=sheet_cols).to_csv(output_dir / "pi_ambiguity_sheet.csv", index=False)

    tier_counts = recovered["tier"].value_counts().to_dict()
    hc_ids = sorted(recovered.loc[recovered["tier"] == "high_confidence", "geo_accession"].tolist())
    report = {
        "schema_version": 1,
        "metadata_parquet": str(Path(args.metadata).resolve()),
        "ontology_sha256": ontology_hash,
        "thresholds": {
            "single_cell_threshold": args.single_cell_threshold,
            "min_training_rows": args.min_training_rows,
            "min_series": args.min_series,
            "per_reason": args.per_reason,
        },
        "n_samples": int(len(recovered)),
        "tier_counts": {
            "high_confidence": int(tier_counts.get("high_confidence", 0)),
            "ambiguous": int(tier_counts.get("ambiguous", 0)),
            "unlabeled": int(tier_counts.get("unlabeled", 0)),
        },
        "n_review_reasons": int(ambiguous["review_reason"].nunique()) if not ambiguous.empty else 0,
        "n_ambiguity_sheet_rows": int(sum(len(p) for p in sheet_parts)),
        "organs_meeting_gate0_rows": summary.loc[summary["meets_min_training_rows"], "organ"].tolist() if not summary.empty else [],
        "high_confidence_sample_id_sha256": _sha256_lines(hc_ids) if hc_ids else "",
        "per_organ_summary": summary.to_dict("records"),
        "warning": (
            "Automated metadata reconciliation only. High-confidence tiers still "
            "require >=50 stratified manual reviews per organ (>=95% precision) before "
            "any organ enters the definitive cohort (plan Gate 0)."
        ),
    }
    (output_dir / "recovery_report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--metadata",
        default="artifacts/stage1_label_recovery/human_sample_metadata.parquet",
    )
    parser.add_argument("--ontology", default="data/ontology/uberon_organ_map.json")
    parser.add_argument("--output-dir", default="artifacts/stage1_label_recovery")
    parser.add_argument("--single-cell-threshold", type=float, default=DEFAULT_SINGLE_CELL_THRESHOLD)
    parser.add_argument("--min-training-rows", type=int, default=DEFAULT_MIN_TRAINING_ROWS)
    parser.add_argument("--min-series", type=int, default=DEFAULT_MIN_SERIES)
    parser.add_argument("--per-reason", type=int, default=25)
    args = parser.parse_args()
    report = recover(args)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
