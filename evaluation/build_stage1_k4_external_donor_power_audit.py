#!/usr/bin/env python3
"""Audit provisional external samples for donor proxies and design sensitivity.

This gate reads only the exact metadata review sheet. It derives auditable within-study
donor keys, searches for explicit cross-study identifier reuse, and evaluates the
preregistered *cluster-count* sensitivity of an exact sign test. It never reads
expression, predictions, losses, or model efficacy and cannot freeze a lockbox.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from pathlib import Path

import pandas as pd


TARGET_ORGANS = ("adipose", "brain", "liver", "skeletal_muscle", "skin")
REQUIRED_SAMPLE_COLUMNS = {
    "sample_id",
    "organ",
    "series_group_id",
    "title",
    "characteristics_ch1",
    "submitted_after_v11_creation",
    "manual_sample_decision",
}
REQUIRED_STUDY_COLUMNS = {
    "organ",
    "series_group_id",
    "n_provisional_selector_matches",
    "manual_study_decision",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_bound_json(path: Path, expected_hash: str, label: str) -> dict:
    if sha256(path) != expected_hash:
        raise ValueError(f"{label} hash mismatch")
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be a JSON object")
    return value


def _extract_characteristic_values(text: str, field: str) -> list[str]:
    pattern = re.compile(
        rf"(?i)(?:^|,){re.escape(field)}:\s*([^,|]+)"
    )
    return [
        re.sub(r"\s+", " ", match).strip()
        for match in pattern.findall(str(text))
        if match.strip()
    ]


def _sign_test_rejection_cutoff(n_clusters: int, alpha: float) -> int:
    """Smallest positive-count cutoff with P_H0(X >= cutoff) <= alpha."""
    for cutoff in range(0, n_clusters + 1):
        tail = sum(
            math.comb(n_clusters, successes) * (0.5 ** n_clusters)
            for successes in range(cutoff, n_clusters + 1)
        )
        if tail <= alpha:
            return cutoff
    return n_clusters + 1


def _binomial_tail(n: int, cutoff: int, probability: float) -> float:
    return sum(
        math.comb(n, successes)
        * (probability ** successes)
        * ((1.0 - probability) ** (n - successes))
        for successes in range(cutoff, n + 1)
    )


def exact_sign_test_sensitivity(
    n_clusters: int, alpha: float, probabilities: list[float]
) -> dict:
    cutoff = _sign_test_rejection_cutoff(n_clusters, alpha)
    null_tail = _binomial_tail(n_clusters, cutoff, 0.5)
    return {
        "n_clusters": n_clusters,
        "one_sided_alpha": alpha,
        "minimum_positive_studies_for_rejection": cutoff,
        "achieved_null_tail_probability": null_tail,
        "power_by_true_positive_study_probability": {
            f"{probability:.2f}": _binomial_tail(
                n_clusters, cutoff, probability
            )
            for probability in probabilities
        },
    }


def _derive_donor_keys(samples: pd.DataFrame, protocol: dict) -> pd.DataFrame:
    donor_contract = protocol["donor_key_contract"]
    overrides = {
        (entry["organ"], entry["series_group_id"]): entry
        for entry in donor_contract.get("explicit_characteristic_overrides", [])
    }
    if len(overrides) != len(
        donor_contract.get("explicit_characteristic_overrides", [])
    ):
        raise ValueError("donor override list repeats an organ/group")

    parts = []
    for (organ, group_id), group in samples.groupby(
        ["organ", "series_group_id"], sort=False
    ):
        group = group.copy()
        override = overrides.get((organ, group_id))
        if override:
            try:
                pattern = re.compile(override["regex"])
            except re.error as error:
                raise ValueError(
                    f"invalid donor regex for {organ}/{group_id}: {error}"
                ) from error
            tokens = []
            for text in group["characteristics_ch1"].astype(str):
                match = pattern.search(text)
                if match is None or not match.groupdict().get("donor"):
                    raise ValueError(
                        f"donor regex failed for {organ}/{group_id}"
                    )
                tokens.append(match.group("donor"))
            basis = override["basis"]
            resolution = "explicit_metadata_identifier"
        else:
            tokens = [
                re.sub(r"\s+", " ", str(title)).strip()
                for title in group["title"]
            ]
            if any(not token for token in tokens):
                raise ValueError(f"empty title donor proxy in {organ}/{group_id}")
            basis = donor_contract["default_basis"]
            resolution = "unique_title_proxy_not_verified_donor"
        group["derived_donor_token"] = tokens
        group["derived_donor_key"] = [
            f"{organ}|{group_id}|{token}" for token in tokens
        ]
        group["donor_key_basis"] = basis
        group["donor_resolution_class"] = resolution
        parts.append(group)
    audited = pd.concat(parts, ignore_index=True)
    if audited["derived_donor_key"].duplicated().any():
        duplicates = sorted(
            audited.loc[
                audited["derived_donor_key"].duplicated(False),
                "derived_donor_key",
            ].unique()
        )
        raise ValueError(f"duplicate within-study donor keys: {duplicates}")
    return audited


def build_donor_power_audit(args: argparse.Namespace) -> dict:
    if re.fullmatch(r"[0-9a-f]{40}", args.code_commit) is None:
        raise ValueError("donor/power audit requires a full code commit")
    samples_path = Path(args.samples)
    studies_path = Path(args.studies)
    source_report_path = Path(args.source_report)
    protocol_path = Path(args.protocol)
    protocol = _read_bound_json(
        protocol_path, args.expected_protocol_sha256, "donor/power protocol"
    )
    if protocol.get("metadata_only") is not True:
        raise ValueError("donor/power protocol is not metadata-only")
    if protocol.get("expression_values_read") is not False:
        raise ValueError("donor/power protocol does not seal expression")
    if protocol.get("external_lockbox_frozen") is not False:
        raise ValueError("donor/power protocol claims a frozen lockbox")

    source_contract = protocol["source_contract"]
    if sha256(samples_path) != source_contract[
        "expected_provisional_sample_review_sha256"
    ]:
        raise ValueError("provisional sample-review hash mismatch")
    if sha256(studies_path) != source_contract[
        "expected_provisional_study_review_sha256"
    ]:
        raise ValueError("provisional study-review hash mismatch")
    source_report = json.loads(source_report_path.read_text())
    if source_report.get("metadata_only") is not True:
        raise ValueError("source review is not metadata-only")
    if source_report.get("expression_values_read") is not False:
        raise ValueError("source review does not prove expression stayed sealed")
    if source_report.get("external_lockbox_frozen") is not False:
        raise ValueError("source review unexpectedly claims a frozen lockbox")
    if source_report.get("hashes", {}).get(
        "provisional_sample_review_sha256"
    ) != sha256(samples_path):
        raise ValueError("source report sample hash mismatch")
    if source_report.get("hashes", {}).get(
        "provisional_study_review_sha256"
    ) != sha256(studies_path):
        raise ValueError("source report study hash mismatch")

    samples = pd.read_csv(samples_path, keep_default_na=False)
    studies = pd.read_csv(studies_path, keep_default_na=False)
    missing_samples = sorted(REQUIRED_SAMPLE_COLUMNS - set(samples.columns))
    missing_studies = sorted(REQUIRED_STUDY_COLUMNS - set(studies.columns))
    if missing_samples:
        raise KeyError(f"sample review is missing fields: {missing_samples}")
    if missing_studies:
        raise KeyError(f"study review is missing fields: {missing_studies}")
    if len(samples) != source_contract["expected_sample_rows"]:
        raise ValueError("unexpected provisional sample-row count")
    if len(studies) != source_contract["expected_study_rows"]:
        raise ValueError("unexpected provisional study-row count")
    if samples["sample_id"].duplicated().any():
        raise ValueError("provisional sample review repeats sample IDs")
    if not samples["submitted_after_v11_creation"].astype(bool).all():
        raise ValueError("pre-cutoff sample reached donor audit")
    if set(samples["manual_sample_decision"]) != {"pending"}:
        raise ValueError("source sample decisions are not uniformly pending")
    if set(studies["manual_study_decision"]) != {"pending"}:
        raise ValueError("source study decisions are not uniformly pending")

    group_counts = studies.groupby("organ").size().reindex(TARGET_ORGANS, fill_value=0)
    expected_per_organ = source_contract["expected_groups_per_organ"]
    if not group_counts.eq(expected_per_organ).all():
        raise ValueError(f"unexpected study groups per organ: {group_counts.to_dict()}")
    sample_groups = set(zip(samples["organ"], samples["series_group_id"]))
    study_groups = set(zip(studies["organ"], studies["series_group_id"]))
    if sample_groups != study_groups:
        raise ValueError("sample and study review group sets differ")

    audited = _derive_donor_keys(samples, protocol)
    explicit_fields = protocol["donor_key_contract"][
        "cross_group_explicit_identifier_fields"
    ]
    explicit_rows = []
    identifier_to_groups: dict[tuple[str, str], set[str]] = {}
    for row in audited.itertuples(index=False):
        for field in explicit_fields:
            for value in _extract_characteristic_values(
                row.characteristics_ch1, field
            ):
                normalized = value.lower()
                identifier_to_groups.setdefault(
                    (field, normalized), set()
                ).add(row.series_group_id)
                explicit_rows.append({
                    "organ": row.organ,
                    "series_group_id": row.series_group_id,
                    "sample_id": row.sample_id,
                    "identifier_field": field,
                    "identifier_value": value,
                })
    overlaps = [
        {
            "identifier_field": field,
            "identifier_value_normalized": value,
            "series_group_ids": sorted(groups),
        }
        for (field, value), groups in sorted(identifier_to_groups.items())
        if len(groups) > 1
    ]

    group_audit_rows = []
    singleton_keys = {
        (entry["organ"], entry["series_group_id"])
        for entry in protocol["donor_key_contract"].get(
            "conservative_single_sample_groups", []
        )
    }
    for row in studies.itertuples(index=False):
        group = audited[
            (audited["organ"] == row.organ)
            & (audited["series_group_id"] == row.series_group_id)
        ]
        resolutions = sorted(set(group["donor_resolution_class"]))
        if len(resolutions) != 1:
            raise ValueError("one study group has mixed donor resolution classes")
        group_audit_rows.append({
            **row._asdict(),
            "n_derived_donor_keys": int(group["derived_donor_key"].nunique()),
            "donor_resolution_class": resolutions[0],
            "conservative_single_sample_group": (
                (row.organ, row.series_group_id) in singleton_keys
            ),
            "within_group_duplicate_donor_keys": False,
            "cross_group_explicit_identifier_overlap": any(
                row.series_group_id in overlap["series_group_ids"]
                for overlap in overlaps
            ),
            "audit_decision": "retain_for_protocol_drafting",
            "audit_decision_is_lockbox_acceptance": False,
        })
    group_audit = pd.DataFrame(group_audit_rows)

    power_contract = protocol["power_sensitivity_contract"]
    sensitivity = exact_sign_test_sensitivity(
        int(power_contract["exact_sign_test_clusters"]),
        float(power_contract["one_sided_alpha"]),
        [float(value) for value in power_contract[
            "positive_study_probability_grid"
        ]],
    )
    readiness_rules = protocol["readiness_rules"]
    checks = {
        "minimum_groups_per_organ": bool(
            group_counts.ge(readiness_rules["minimum_groups_per_organ"]).all()
        ),
        "minimum_total_study_groups": bool(
            len(studies) >= readiness_rules["minimum_total_study_groups"]
        ),
        "no_cross_group_explicit_identifier_overlap": not overlaps,
        "no_duplicate_derived_donor_keys_within_group": bool(
            not audited["derived_donor_key"].duplicated().any()
        ),
        "source_metadata_pending_not_silently_accepted": True,
    }
    ready_for_protocol_drafting = all(checks.values())

    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise FileExistsError("donor/power audit output already exists")
    output_dir.mkdir(parents=True)
    audited_samples_path = output_dir / "audited_sample_donor_keys.csv"
    group_audit_path = output_dir / "study_donor_audit.csv"
    explicit_path = output_dir / "explicit_identifier_ledger.csv"
    audited.to_csv(audited_samples_path, index=False)
    group_audit.to_csv(group_audit_path, index=False)
    pd.DataFrame(
        explicit_rows,
        columns=[
            "organ",
            "series_group_id",
            "sample_id",
            "identifier_field",
            "identifier_value",
        ],
    ).to_csv(explicit_path, index=False)

    report = {
        "schema_version": 1,
        "status": (
            "ready_for_protocol_drafting_not_lockbox"
            if ready_for_protocol_drafting
            else "donor_audit_hold"
        ),
        "code_commit": args.code_commit,
        "metadata_only": True,
        "expression_values_read": False,
        "efficacy_scoring_performed": False,
        "external_lockbox_frozen": False,
        "manual_decisions_complete": False,
        "ready_for_protocol_drafting": ready_for_protocol_drafting,
        "ready_for_lockbox_freeze": False,
        "ready_for_expression_access": False,
        "sample_rows": int(len(audited)),
        "study_groups": int(len(studies)),
        "study_groups_per_organ": {
            organ: int(group_counts[organ]) for organ in TARGET_ORGANS
        },
        "derived_donor_keys": int(audited["derived_donor_key"].nunique()),
        "explicit_identifier_rows": int(len(explicit_rows)),
        "cross_group_explicit_identifier_overlaps": overlaps,
        "readiness_checks": checks,
        "sign_test_design_sensitivity": sensitivity,
        "analysis_unit_contract": protocol["analysis_unit_contract"],
        "power_warning": power_contract["warning"],
        "hashes": {
            "protocol_sha256": sha256(protocol_path),
            "source_sample_review_sha256": sha256(samples_path),
            "source_study_review_sha256": sha256(studies_path),
            "source_report_sha256": sha256(source_report_path),
            "audited_sample_donor_keys_sha256": sha256(audited_samples_path),
            "study_donor_audit_sha256": sha256(group_audit_path),
            "explicit_identifier_ledger_sha256": sha256(explicit_path),
        },
        "next_gate": protocol["next_gate"],
    }
    report_path = output_dir / "donor_power_audit_report.json"
    temporary = output_dir / "donor_power_audit_report.json.tmp"
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, report_path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", required=True)
    parser.add_argument("--studies", required=True)
    parser.add_argument("--source-report", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    print(json.dumps(build_donor_power_audit(args), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
