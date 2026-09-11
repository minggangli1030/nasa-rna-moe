#!/usr/bin/env python3
"""Download and QC the frozen OSDR downstream development cohort."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from evaluate_osdr import (
    load_canonical_genes,
    load_mouse_exon_lengths,
    load_ortholog_map,
    preprocess_osdr,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--metadata-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--qc-min-nonzero", type=int, default=14_000)
    args = parser.parse_args()

    protocol_path = Path(args.protocol)
    metadata_path = Path(args.metadata_csv)
    output_dir = Path(args.output_dir)
    if sha256_file(protocol_path) != args.expected_protocol_sha256:
        raise ValueError("downstream protocol SHA256 mismatch")
    protocol = json.loads(protocol_path.read_text())
    if protocol.get("status") != "frozen_stage1_osdr_downstream_development":
        raise ValueError("protocol is not frozen")
    if protocol["cohort"]["candidate_metadata_sha256"] != sha256_file(metadata_path):
        raise ValueError("OSDR candidate metadata hash mismatch")
    if int(protocol["cohort"]["qc_min_nonzero"]) != int(args.qc_min_nonzero):
        raise ValueError("OSDR QC threshold differs from protocol")
    if output_dir.exists():
        raise FileExistsError(output_dir)
    output_dir.mkdir(parents=True)

    expression = preprocess_osdr(
        metadata_csv=metadata_path,
        osdr_raw_dir=None,
        cache_dir=output_dir,
        ortholog_map=load_ortholog_map(),
        canonical_genes=load_canonical_genes(),
        exon_lengths=load_mouse_exon_lengths(),
        download=True,
        force_rebuild=True,
        qc_min_nonzero=args.qc_min_nonzero,
    )
    candidate = pd.read_csv(metadata_path, low_memory=False)
    lookup = candidate.drop_duplicates(
        ["id.accession", "id.sample name"]
    ).set_index(["id.accession", "id.sample name"])
    retained = expression[["study_id", "sample_name", "spaceflight"]].copy()
    keys = list(zip(retained["study_id"], retained["sample_name"]))
    missing = [key for key in keys if key not in lookup.index]
    if missing:
        raise ValueError(f"retained OSDR rows are outside frozen metadata: {missing[:3]}")
    retained["organ"] = [
        str(lookup.loc[key, "downstream_organ"]) for key in keys
    ]
    retained["frozen_label"] = [
        int(lookup.loc[key, "downstream_label"]) for key in keys
    ]
    if not (
        retained["frozen_label"].to_numpy()
        == retained["spaceflight"].astype(int).to_numpy()
    ).all():
        raise ValueError("processed OSDR label differs from frozen metadata")

    valid_units = []
    for (study, organ), group in retained.groupby(["study_id", "organ"], sort=True):
        if group["frozen_label"].nunique() == 2:
            valid_units.extend(group.index.tolist())
    retained["valid_study_organ_contrast"] = retained.index.isin(valid_units)
    retained_path = output_dir / "retained_cohort.csv"
    retained.to_csv(retained_path, index=True)
    expression_path = output_dir / "osdr_expression_v3.parquet"
    coverage_path = output_dir / "osdr_coverage_v3.npz"
    source_manifest_path = output_dir / "osdr_manifest_v3.json"
    report = {
        "schema_version": 1,
        "status": "complete",
        "protocol_sha256": sha256_file(protocol_path),
        "candidate_metadata_sha256": sha256_file(metadata_path),
        "requested_samples": int(len(candidate)),
        "requested_studies": int(candidate["id.accession"].nunique()),
        "retained_samples_after_qc": int(len(retained)),
        "retained_studies_after_qc": int(retained["study_id"].nunique()),
        "retained_valid_contrast_samples": int(
            retained["valid_study_organ_contrast"].sum()
        ),
        "retained_valid_contrast_studies": int(
            retained.loc[
                retained["valid_study_organ_contrast"], "study_id"
            ].nunique()
        ),
        "no_replacements": True,
        "outcomes_used_for_model_selection": False,
        "hashes": {
            "expression_sha256": sha256_file(expression_path),
            "coverage_sha256": sha256_file(coverage_path),
            "preprocessing_manifest_sha256": sha256_file(source_manifest_path),
            "retained_cohort_sha256": sha256_file(retained_path),
        },
    }
    (output_dir / "downstream_qc_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    (output_dir / "COMPLETE").write_text("complete\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
