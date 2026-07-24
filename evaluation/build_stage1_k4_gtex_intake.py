#!/usr/bin/env python3
"""Build a metadata-only GTEx V11 intake audit for Stage 1 K4 validation.

This command never opens an expression file. It binds the GTEx metadata release,
recovers the exact bulk RNA-seq target-tissue rows, joins public donor attributes,
and excludes every GTEx donor known to overlap historical ARCHS4/ENCODE material.
The result is a provisional donor-controlled cohort, not a frozen lockbox and not
authorization to download or score expression.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import pandas as pd


TARGET_ORGANS = (
    "adipose",
    "brain",
    "liver",
    "skeletal_muscle",
    "skin",
)
REQUIRED_SAMPLE_COLUMNS = {
    "SAMPID",
    "SMATSSCR",
    "SMPTHNTS",
    "SMRIN",
    "SMTS",
    "SMTSD",
    "SMUBRID",
    "SMTSISCH",
    "SMTSPAX",
    "SMGEBTCHT",
    "ANALYTE_TYPE",
}
REQUIRED_SUBJECT_COLUMNS = {"SUBJID", "SEX", "AGE", "DTHHRDY"}
REQUIRED_HISTORICAL_COLUMNS = {
    "sample_id",
    "organ",
    "series_group_id",
    "source_name",
    "title",
    "characteristics",
}
FULL_SAMPLE_RE = re.compile(
    r"^(?P<donor>GTEX-[A-Z0-9]+)(?:-[A-Za-z0-9]+)+-SM-[A-Za-z0-9]+$"
)
ENCODE_DONOR_RE = re.compile(r"\bENCDO[A-Z0-9]+\b")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_protocol(path: Path, expected_sha256: str) -> dict:
    if sha256(path) != expected_sha256:
        raise ValueError("GTEx intake protocol hash mismatch")
    protocol = json.loads(path.read_text())
    if protocol.get("metadata_only") is not True:
        raise ValueError("GTEx intake protocol is not metadata-only")
    for field in (
        "expression_values_read",
        "expression_file_downloaded",
        "external_lockbox_frozen",
        "ready_for_expression_access",
    ):
        if protocol.get(field) is not False:
            raise ValueError(f"GTEx intake protocol does not seal {field}")
    if protocol.get("evidence_role") != "secondary_donor_controlled_validation":
        raise ValueError("GTEx evidence role is not donor-controlled secondary validation")
    return protocol


def _verify_bound_file(path: Path, contract: dict, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{label} is missing: {path}")
    if path.stat().st_size != int(contract["file_size"]):
        raise ValueError(f"{label} size mismatch")
    if sha256(path) != contract["sha256"]:
        raise ValueError(f"{label} SHA256 mismatch")


def _organ_for_tissue(
    broad_tissue: str,
    detailed_tissue: str,
    mappings: dict[str, list[str]],
) -> str:
    hits = [
        organ
        for organ, tissue_names in mappings.items()
        if detailed_tissue in tissue_names
    ]
    if len(hits) > 1:
        raise ValueError(f"GTEx tissue is mapped to multiple organs: {detailed_tissue}")
    if not hits:
        return ""
    organ = hits[0]
    expected_broad = {
        "adipose": "Adipose Tissue",
        "brain": "Brain",
        "liver": "Liver",
        "skeletal_muscle": "Muscle",
        "skin": "Skin",
    }[organ]
    if broad_tissue != expected_broad:
        raise ValueError(
            f"unexpected broad tissue for {detailed_tissue}: "
            f"{broad_tissue} != {expected_broad}"
        )
    return organ


def _historical_overlap_audit(
    historical: pd.DataFrame,
    crosswalk: dict[str, str],
    contract: dict,
) -> dict:
    missing = sorted(REQUIRED_HISTORICAL_COLUMNS - set(historical.columns))
    if missing:
        raise KeyError(f"historical manifest is missing fields: {missing}")
    text = historical[
        ["source_name", "title", "characteristics"]
    ].fillna("").astype(str).agg(" ".join, axis=1)
    gtex_mask = text.str.contains("GTEx", case=False, regex=False)
    rows = historical.loc[
        gtex_mask,
        ["sample_id", "organ", "series_group_id", "source_name", "title", "characteristics"],
    ].copy()
    encode_donors = sorted({
        match
        for value in rows["characteristics"].astype(str)
        for match in ENCODE_DONOR_RE.findall(value)
    })
    if encode_donors != sorted(crosswalk):
        raise ValueError(
            "historical GTEx-derived ENCODE donors differ from the frozen crosswalk"
        )
    expected_rows = int(contract["expected_gtex_derived_rows"])
    if len(rows) != expected_rows:
        raise ValueError(
            f"unexpected historical GTEx-derived row count: {len(rows)} != {expected_rows}"
        )
    expected_series = sorted(contract["expected_series_group_ids"])
    observed_series = sorted(rows["series_group_id"].astype(str).unique())
    if observed_series != expected_series:
        raise ValueError("historical GTEx-derived series groups changed")
    return {
        "gtex_derived_rows": int(len(rows)),
        "sample_ids": sorted(rows["sample_id"].astype(str)),
        "series_group_ids": observed_series,
        "encode_donor_ids": encode_donors,
        "gtex_donor_ids": sorted(crosswalk.values()),
    }


def _count_summary(frame: pd.DataFrame) -> dict:
    by_organ = {}
    for organ in TARGET_ORGANS:
        subset = frame[frame["organ"] == organ]
        by_organ[organ] = {
            "samples": int(len(subset)),
            "donors": int(subset["donor_id"].nunique()),
            "tissue_sites": {
                str(key): int(value)
                for key, value in subset["tissue_site"].value_counts().sort_index().items()
            },
        }
    return {
        "samples": int(len(frame)),
        "donors": int(frame["donor_id"].nunique()),
        "by_organ": by_organ,
    }


def _assert_expected_counts(observed: dict, expected: dict, label: str) -> None:
    if observed["samples"] != int(expected["samples"]):
        raise ValueError(f"{label} sample count mismatch")
    if observed["donors"] != int(expected["donors"]):
        raise ValueError(f"{label} donor count mismatch")
    for organ in TARGET_ORGANS:
        for field in ("samples", "donors"):
            if observed["by_organ"][organ][field] != int(
                expected["by_organ"][organ][field]
            ):
                raise ValueError(f"{label} {organ} {field} count mismatch")


def build_gtex_intake(args: argparse.Namespace) -> dict:
    if re.fullmatch(r"[0-9a-f]{40}", args.code_commit) is None:
        raise ValueError("GTEx intake requires a full code commit")

    protocol_path = Path(args.protocol)
    protocol = _read_protocol(protocol_path, args.expected_protocol_sha256)
    sources = protocol["source_contract"]["metadata_files"]
    paths = {
        "sample_attributes": Path(args.sample_attributes),
        "sample_dictionary": Path(args.sample_dictionary),
        "subject_phenotypes": Path(args.subject_phenotypes),
        "subject_dictionary": Path(args.subject_dictionary),
    }
    for label, path in paths.items():
        _verify_bound_file(path, sources[label], label)

    historical_path = Path(args.historical_manifest)
    historical_contract = protocol["historical_overlap_contract"]
    if sha256(historical_path) != historical_contract["historical_manifest_sha256"]:
        raise ValueError("historical manifest SHA256 mismatch")
    historical = pd.read_csv(historical_path, keep_default_na=False)
    crosswalk = historical_contract["encode_to_gtex_donor_crosswalk"]
    overlap_audit = _historical_overlap_audit(
        historical, crosswalk, historical_contract
    )

    samples = pd.read_csv(
        paths["sample_attributes"],
        sep="\t",
        dtype=str,
        keep_default_na=False,
        low_memory=False,
    )
    subjects = pd.read_csv(
        paths["subject_phenotypes"],
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )
    missing_samples = sorted(REQUIRED_SAMPLE_COLUMNS - set(samples.columns))
    missing_subjects = sorted(REQUIRED_SUBJECT_COLUMNS - set(subjects.columns))
    if missing_samples:
        raise KeyError(f"GTEx sample attributes are missing fields: {missing_samples}")
    if missing_subjects:
        raise KeyError(f"GTEx subject phenotypes are missing fields: {missing_subjects}")
    if samples["SAMPID"].duplicated().any():
        raise ValueError("GTEx sample attributes repeat SAMPID")
    if subjects["SUBJID"].duplicated().any():
        raise ValueError("GTEx subject phenotypes repeat SUBJID")

    selection = protocol["sample_selection_contract"]
    tissue_mappings = selection["tissue_site_to_organ"]
    if tuple(tissue_mappings) != TARGET_ORGANS:
        raise ValueError("GTEx tissue mapping order differs from target organ order")
    organ_values = [
        _organ_for_tissue(row.SMTS, row.SMTSD, tissue_mappings)
        for row in samples[["SMTS", "SMTSD"]].itertuples(index=False)
    ]
    samples = samples.assign(_organ=organ_values)
    selected = samples[
        samples["SAMPID"].str.startswith("GTEX-")
        & samples["ANALYTE_TYPE"].eq(selection["required_analyte_type"])
        & samples["SMGEBTCHT"].eq(selection["required_expression_batch_type"])
        & samples["_organ"].ne("")
    ].copy()
    donor_ids = []
    for sample_id in selected["SAMPID"]:
        match = FULL_SAMPLE_RE.fullmatch(sample_id)
        if match is None:
            raise ValueError(f"unexpected GTEx bulk sample ID: {sample_id}")
        donor_ids.append(match.group("donor"))
    selected["donor_id"] = donor_ids
    selected["organ"] = selected.pop("_organ")

    joined = selected.merge(
        subjects,
        how="left",
        left_on="donor_id",
        right_on="SUBJID",
        validate="many_to_one",
        indicator=True,
    )
    if not joined["_merge"].eq("both").all():
        missing = sorted(
            joined.loc[joined["_merge"] != "both", "donor_id"].unique()
        )
        raise ValueError(f"GTEx candidates lack public subject metadata: {missing[:5]}")

    overlapping_gtex_donors = set(crosswalk.values())
    joined["historical_overlap"] = joined["donor_id"].isin(overlapping_gtex_donors)
    joined["intake_decision"] = joined["historical_overlap"].map({
        True: "exclude_historical_donor_overlap",
        False: "provisional_include_pending_expression_header_and_evaluator_freeze",
    })
    joined["donor_organ_sample_count"] = joined.groupby(
        ["donor_id", "organ"]
    )["SAMPID"].transform("size")
    joined["donor_organ_weight_if_frozen"] = (
        1.0 / joined["donor_organ_sample_count"].astype(float)
    )

    audit = joined.rename(columns={
        "SAMPID": "sample_id",
        "SMTS": "broad_tissue",
        "SMTSD": "tissue_site",
        "SMUBRID": "uberon_id",
        "ANALYTE_TYPE": "analyte_type",
        "SMGEBTCHT": "expression_batch_type",
        "SMRIN": "rin",
        "SMATSSCR": "autolysis_score",
        "SMPTHNTS": "pathology_notes",
        "SMTSISCH": "ischemic_time_minutes",
        "SMTSPAX": "paxgene_fixation_time",
        "SEX": "sex_code",
        "AGE": "age_bracket",
        "DTHHRDY": "death_hardy_scale",
    })
    audit_columns = [
        "sample_id",
        "donor_id",
        "organ",
        "broad_tissue",
        "tissue_site",
        "uberon_id",
        "analyte_type",
        "expression_batch_type",
        "rin",
        "autolysis_score",
        "pathology_notes",
        "ischemic_time_minutes",
        "paxgene_fixation_time",
        "sex_code",
        "age_bracket",
        "death_hardy_scale",
        "historical_overlap",
        "intake_decision",
        "donor_organ_sample_count",
        "donor_organ_weight_if_frozen",
    ]
    organ_order = {organ: index for index, organ in enumerate(TARGET_ORGANS)}
    audit["_organ_order"] = audit["organ"].map(organ_order)
    audit = audit.sort_values(
        ["_organ_order", "tissue_site", "donor_id", "sample_id"],
        kind="mergesort",
    ).drop(columns="_organ_order")[audit_columns]
    provisional = audit[~audit["historical_overlap"]].copy()

    counts_all = _count_summary(audit)
    counts_provisional = _count_summary(provisional)
    expected = protocol["expected_metadata_counts"]
    _assert_expected_counts(counts_all, expected["before_overlap_exclusion"], "pre-exclusion")
    _assert_expected_counts(
        counts_provisional,
        expected["after_overlap_exclusion"],
        "post-exclusion",
    )
    if set(audit.loc[audit["historical_overlap"], "donor_id"]) != overlapping_gtex_donors:
        raise ValueError("not every frozen overlapping GTEx donor was found and excluded")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    audit_path = output_dir / "gtex_v11_sample_audit.csv"
    provisional_path = output_dir / "gtex_v11_provisional_cohort.csv"
    report_path = output_dir / "gtex_v11_intake_report.json"
    audit.to_csv(audit_path, index=False, lineterminator="\n")
    provisional.to_csv(provisional_path, index=False, lineterminator="\n")

    report = {
        "schema_version": 1,
        "protocol_name": protocol["protocol_name"],
        "protocol_sha256": sha256(protocol_path),
        "code_commit": args.code_commit,
        "evidence_role": protocol["evidence_role"],
        "metadata_only": True,
        "expression_values_read": False,
        "expression_file_downloaded": False,
        "efficacy_scoring_performed": False,
        "external_lockbox_frozen": False,
        "ready_for_evaluator_drafting": True,
        "ready_for_lockbox_freeze": False,
        "ready_for_expression_access": False,
        "source_release": protocol["source_contract"]["release"],
        "expression_object_catalog_binding": protocol["source_contract"][
            "expression_object_catalog_binding"
        ],
        "historical_overlap_audit": overlap_audit,
        "counts": {
            "before_overlap_exclusion": counts_all,
            "after_overlap_exclusion": counts_provisional,
            "excluded_samples": int(len(audit) - len(provisional)),
            "excluded_donors": int(
                audit.loc[audit["historical_overlap"], "donor_id"].nunique()
            ),
        },
        "aggregation_contract": protocol["aggregation_contract"],
        "health_interpretation": protocol["health_interpretation"],
        "expression_contract_status": protocol["expression_contract_status"],
        "remaining_gates": protocol["remaining_gates"],
        "hashes": {
            "sample_audit_sha256": sha256(audit_path),
            "provisional_cohort_sha256": sha256(provisional_path),
            "historical_manifest_sha256": sha256(historical_path),
            "metadata_file_sha256": {
                label: sha256(path) for label, path in paths.items()
            },
        },
    }
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (output_dir / "METADATA_ONLY_COMPLETE").write_text(
        "GTEx V11 metadata intake complete; expression remains sealed.\n"
    )
    (output_dir / "EXPRESSION_ACCESS_NOT_AUTHORIZED").write_text(
        "Do not download or inspect expression until the evaluator and cohort are frozen.\n"
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-attributes", required=True)
    parser.add_argument("--sample-dictionary", required=True)
    parser.add_argument("--subject-phenotypes", required=True)
    parser.add_argument("--subject-dictionary", required=True)
    parser.add_argument("--historical-manifest", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def main() -> None:
    report = build_gtex_intake(parse_args())
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
