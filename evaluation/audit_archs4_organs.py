#!/usr/bin/env python3
"""Build a conservative, study-aware audit of human ARCHS4 organ labels."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import h5py
except ImportError:  # Pure label helpers remain testable without optional H5 IO.
    h5py = None

from attach_archs4_series import connected_series_groups


ORGAN_PATTERNS = {
    "adipose": r"\b(adipose tissue|subcutaneous fat|visceral fat|omental fat)\b",
    "brain": r"\b(brain|cerebellum|cerebral cortex|prefrontal cortex|hippocampus|hypothalamus|amygdala)\b",
    "breast": r"\b(breast tissue|mammary tissue)\b",
    "colon": r"\b(colon tissue|colonic tissue|large intestine|colorectal tissue|colon$|colonic mucosa)\b",
    "heart": r"\b(heart tissue|whole heart|cardiac tissue|myocardium|left ventricle|right ventricle|left atrium|right atrium)\b",
    "kidney": r"\b(kidney tissue|renal tissue|kidney cortex|kidney medulla|kidney$)\b",
    "liver": r"\b(liver tissue|hepatic tissue|liver$)\b",
    "lung": r"\b(lung tissue|pulmonary tissue|lung parenchyma|lung$)\b",
    "ovary": r"\b(ovary tissue|ovarian tissue|ovary$)\b",
    "pancreas": r"\b(pancreas tissue|pancreatic tissue|pancreatic islet|pancreas$)\b",
    "placenta": r"\b(placenta tissue|placental tissue|placenta$)\b",
    "prostate": r"\b(prostate tissue|prostatic tissue|prostate biopsy|prostate$)\b",
    "skeletal_muscle": r"\b(skeletal muscle|vastus lateralis|gastrocnemius|quadriceps muscle)\b",
    "skin": r"\b(skin tissue|skin biopsy|epidermal tissue|dermal tissue|skin$)\b",
    "testis": r"\b(testis tissue|testicular tissue|testes tissue|testis$|testes$)\b",
}
COMPILED_ORGANS = {
    label: re.compile(pattern, re.IGNORECASE) for label, pattern in ORGAN_PATTERNS.items()
}
CELL_LIKE = re.compile(
    r"\b(cell line|cell culture|cultured|organoid|xenograft|iPSC|induced pluripotent|"
    r"single[- ]cell|cells?|fibroblast|epithelial|endothelial|lymphocyte|monocyte|"
    r"macrophage|HeLa|HEK[- ]?293|MCF[- ]?7|A549|K562|Jurkat)\b",
    re.IGNORECASE,
)
TUMOR_LIKE = re.compile(
    r"\b(tumou?r|cancer|carcinoma|adenocarcinoma|sarcoma|melanoma|leukemia|lymphoma|metastatic)\b",
    re.IGNORECASE,
)


def _decode(value) -> str:
    return value.decode("utf-8", "ignore") if isinstance(value, bytes) else str(value)


def classify_organ(source: str, title: str) -> tuple[str | None, str, list[str]]:
    """Return one conservative organ label and its evidence source."""
    source_hits = [label for label, pattern in COMPILED_ORGANS.items() if pattern.search(source)]
    title_hits = [label for label, pattern in COMPILED_ORGANS.items() if pattern.search(title)]
    hits = sorted(set(source_hits) | set(title_hits))
    if len(hits) != 1:
        return None, "ambiguous" if hits else "unmatched", hits
    evidence = "source" if hits[0] in source_hits else "title"
    return hits[0], evidence, hits


def _sha256_lines(values: list[str]) -> str:
    payload = "\n".join(values) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def audit(args) -> dict:
    if h5py is None:
        raise RuntimeError("h5py is required to audit ARCHS4 organ metadata")
    records = []
    exclusions = {
        "single_cell_probability": 0,
        "cell_like_metadata": 0,
        "empty_series": 0,
        "unmatched": 0,
        "ambiguous_organ": 0,
    }
    with h5py.File(args.human_h5, "r") as handle:
        samples = handle["meta/samples"]
        n_samples = len(samples["geo_accession"])
        for start in range(0, n_samples, args.chunk_size):
            stop = min(start + args.chunk_size, n_samples)
            accessions = samples["geo_accession"][start:stop]
            series_ids = samples["series_id"][start:stop]
            sources = samples["source_name_ch1"][start:stop]
            titles = samples["title"][start:stop]
            characteristics = samples["characteristics_ch1"][start:stop]
            single_cell = samples["singlecellprobability"][start:stop]
            for accession_raw, series_raw, source_raw, title_raw, chars_raw, sc_prob in zip(
                accessions, series_ids, sources, titles, characteristics, single_cell
            ):
                if float(sc_prob) >= args.max_single_cell_probability:
                    exclusions["single_cell_probability"] += 1
                    continue
                accession = _decode(accession_raw).strip()
                series = _decode(series_raw).strip()
                source = _decode(source_raw).strip()
                title = _decode(title_raw).strip()
                characteristics_text = _decode(chars_raw).strip()
                if not series:
                    exclusions["empty_series"] += 1
                    continue
                all_text = " | ".join((source, title, characteristics_text))
                if CELL_LIKE.search(all_text):
                    exclusions["cell_like_metadata"] += 1
                    continue
                label, evidence, hits = classify_organ(source, title)
                if label is None:
                    exclusions["ambiguous_organ" if hits else "unmatched"] += 1
                    continue
                records.append({
                    "sample_id": accession,
                    "organ": label,
                    "label_evidence": evidence,
                    "series_id": series,
                    "source_name": source,
                    "title": title,
                    "single_cell_probability": float(sc_prob),
                    "tumor_like": bool(TUMOR_LIKE.search(all_text)),
                })

    frame = pd.DataFrame.from_records(records)
    if frame.empty:
        raise ValueError("no conservative organ labels were found")
    if frame["sample_id"].duplicated().any():
        raise ValueError("ARCHS4 organ candidates contain duplicate sample IDs")
    frame["series_group_id"] = connected_series_groups(frame["series_id"].tolist())
    frame = frame.sort_values(["organ", "series_group_id", "sample_id"]).reset_index(drop=True)

    summary_rows = []
    for organ, subset in frame.groupby("organ", sort=True):
        group_sizes = subset.groupby("series_group_id").size()
        n_samples = len(subset)
        n_groups = len(group_sizes)
        summary_rows.append({
            "organ": organ,
            "n_samples": n_samples,
            "n_series_groups": n_groups,
            "median_samples_per_group": float(group_sizes.median()),
            "largest_group_samples": int(group_sizes.max()),
            "largest_group_fraction": float(group_sizes.max() / n_samples),
            "tumor_like_samples": int(subset["tumor_like"].sum()),
            "source_labeled_samples": int((subset["label_evidence"] == "source").sum()),
            "eligible_for_pilot": bool(
                n_samples >= args.min_samples
                and n_groups >= args.min_series_groups
                and group_sizes.max() / n_samples <= args.max_group_fraction
            ),
        })
    summary = pd.DataFrame(summary_rows).sort_values(
        ["eligible_for_pilot", "n_series_groups", "n_samples"], ascending=[False, False, False]
    )
    eligible = summary.loc[summary["eligible_for_pilot"], "organ"].tolist()
    eligible_ids = frame.loc[frame["organ"].isin(eligible), "sample_id"].tolist()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output_dir / "organ_candidates.parquet", index=False)
    summary.to_csv(output_dir / "organ_summary.csv", index=False)
    report = {
        "schema_version": 1,
        "human_h5": str(Path(args.human_h5).resolve()),
        "thresholds": {
            "max_single_cell_probability": args.max_single_cell_probability,
            "min_samples": args.min_samples,
            "min_series_groups": args.min_series_groups,
            "max_group_fraction": args.max_group_fraction,
        },
        "n_conservative_candidates": int(len(frame)),
        "n_connected_series_groups": int(frame["series_group_id"].nunique()),
        "exclusions": exclusions,
        "eligible_organs": eligible,
        "eligible_sample_id_sha256": _sha256_lines(eligible_ids),
        "organ_summary": summary.to_dict("records"),
        "warning": (
            "Labels are conservative regex normalization of ARCHS4 source/title metadata, "
            "not a validated tissue ontology. Manually audit candidates before freezing cohorts."
        ),
    }
    (output_dir / "audit_report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--human-h5", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--chunk-size", type=int, default=20_000)
    parser.add_argument("--max-single-cell-probability", type=float, default=0.5)
    parser.add_argument("--min-samples", type=int, default=1_000)
    parser.add_argument("--min-series-groups", type=int, default=50)
    parser.add_argument("--max-group-fraction", type=float, default=0.20)
    args = parser.parse_args()
    report = audit(args)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
