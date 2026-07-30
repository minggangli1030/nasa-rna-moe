#!/usr/bin/env python3
"""Build an ID-safe, training-only GTEx v8 axis/nuisance feature inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd


SUBJECT_FIELDS = ("SEX", "AGE", "DTHHRDY")
SAMPLE_FIELDS = ("SMRIN", "SMTSISCH")
REQUIRED_MANIFEST = {"sample_id", "donor_id", "organ", "tissue_site", "split"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def summarize(frame: pd.DataFrame, field: str) -> dict[str, Any]:
    values = frame[field]
    numeric = pd.to_numeric(values, errors="coerce")
    record: dict[str, Any] = {
        "missing_fraction": float(values.isna().mean()),
        "unique_nonmissing": int(values.nunique(dropna=True)),
        "donors_with_value": int(
            frame.loc[values.notna(), "donor_id"].astype(str).nunique()
        ),
    }
    if int(numeric.notna().sum()) == int(values.notna().sum()) and numeric.notna().any():
        record["numeric_min"] = float(numeric.min())
        record["numeric_max"] = float(numeric.max())
    else:
        record["level_counts"] = {
            str(key): int(count)
            for key, count in values.astype("string").value_counts(dropna=False).items()
        }
    return record


def build(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path = Path(args.manifest)
    subject_path = Path(args.subject_attributes)
    sample_path = Path(args.sample_attributes)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)

    manifest = pd.read_parquet(manifest_path)
    missing_manifest = sorted(REQUIRED_MANIFEST - set(manifest.columns))
    if missing_manifest:
        raise ValueError(f"manifest lacks required columns: {missing_manifest}")
    training = manifest.loc[manifest["split"].astype(str).eq("train")].copy()
    if training.empty:
        raise ValueError("manifest has no training rows")
    for field in ("sample_id", "donor_id"):
        training[field] = training[field].astype(str)
    if training["sample_id"].duplicated().any():
        raise ValueError("training sample IDs are not unique")

    subjects = pd.read_csv(subject_path, sep="\t", dtype="string")
    samples = pd.read_csv(sample_path, sep="\t", dtype="string", low_memory=False)
    required_subject = {"SUBJID", *SUBJECT_FIELDS}
    required_sample = {"SAMPID", *SAMPLE_FIELDS}
    if missing := sorted(required_subject - set(subjects.columns)):
        raise ValueError(f"subject attributes lack columns: {missing}")
    if missing := sorted(required_sample - set(samples.columns)):
        raise ValueError(f"sample attributes lack columns: {missing}")
    if subjects["SUBJID"].duplicated().any():
        raise ValueError("subject attributes contain duplicate SUBJID")
    if samples["SAMPID"].duplicated().any():
        raise ValueError("sample attributes contain duplicate SAMPID")

    subject_subset = subjects[["SUBJID", *SUBJECT_FIELDS]].rename(
        columns={
            "SUBJID": "donor_id",
            "SEX": "sex_code",
            "AGE": "age_bracket",
            "DTHHRDY": "death_hardy_scale",
        }
    )
    sample_subset = samples[["SAMPID", *SAMPLE_FIELDS]].rename(
        columns={
            "SAMPID": "sample_id",
            "SMRIN": "rin",
            "SMTSISCH": "ischemic_time_minutes",
        }
    )
    joined = training[
        ["sample_id", "donor_id", "organ", "tissue_site"]
    ].merge(sample_subset, on="sample_id", how="left", validate="one_to_one")
    joined = joined.merge(
        subject_subset, on="donor_id", how="left", validate="many_to_one"
    )
    if len(joined) != len(training):
        raise AssertionError("metadata join changed row count")
    if joined["sample_id"].tolist() != training["sample_id"].tolist():
        raise AssertionError("metadata join changed sample order")

    biological = ("sex_code", "age_bracket", "death_hardy_scale")
    nuisance = ("rin", "ischemic_time_minutes")
    for field in (*biological, *nuisance):
        joined[field] = joined[field].replace({"": pd.NA})
    feature_path = output_dir / "gtex_v8_training_multiaxis_features.parquet"
    joined.to_parquet(feature_path, index=False)

    report = {
        "schema_version": 1,
        "status": "complete",
        "scope": "GTEx v8 training rows only; metadata inventory without efficacy fitting",
        "firewalls": {
            "calibration_rows_in_output": False,
            "archs4_access": False,
            "neural_checkpoint_updates": False,
            "outcome_based_field_selection": False,
        },
        "inputs": {
            "manifest_sha256": sha256_file(manifest_path),
            "subject_attributes_sha256": sha256_file(subject_path),
            "sample_attributes_sha256": sha256_file(sample_path),
        },
        "rows": int(len(joined)),
        "donors": int(joined["donor_id"].nunique()),
        "organs": int(joined["organ"].nunique()),
        "tissue_sites": int(joined["tissue_site"].nunique()),
        "biological_candidate_fields": {
            field: summarize(joined, field) for field in biological
        },
        "technical_nuisance_fields": {
            field: summarize(joined, field) for field in nuisance
        },
        "interpretation": {
            "sex_code": (
                "retain official raw GTEx v8 code until the official data dictionary "
                "is hash-pinned; do not infer labels from the integer"
            ),
            "death_hardy_scale": (
                "candidate physiological/death-context covariate; treat cautiously "
                "and test primarily as a nuisance/confound before a biological axis"
            ),
            "rin_and_ischemic_time": "technical nuisance controls, not biological experts",
        },
        "next_gate": (
            "freeze field handling and grouped-CV protocol before joining these "
            "features to Stage 2B residual outcomes"
        ),
    }
    report_path = output_dir / "gtex_v8_multiaxis_metadata_report.json"
    atomic_json(report_path, report)
    artifacts = (feature_path, report_path)
    (output_dir / "IMMUTABLE_SHA256SUMS").write_text(
        "".join(f"{sha256_file(path)}  {path.name}\n" for path in artifacts)
    )
    (output_dir / "COMPLETE").touch()
    return report


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--manifest", required=True)
    value.add_argument("--subject-attributes", required=True)
    value.add_argument("--sample-attributes", required=True)
    value.add_argument("--output-dir", required=True)
    return value


if __name__ == "__main__":
    print(json.dumps(build(parser().parse_args()), indent=2, sort_keys=True))

