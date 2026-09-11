#!/usr/bin/env python3
"""Build the expression-sealed K8 ARCHS4 curation workbook.

This is a metadata-only bridge between the frozen GTEx-to-ARCHS4 inventory and an
eventual external lockbox.  It reconstructs the exact post-v11, series-disjoint K8
candidate pool, re-applies conservative study triage, and emits blank manual review
fields.  It cannot accept a study, freeze a cohort, read expression, or score a model.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = ROOT / "core"
EVALUATION_DIR = ROOT / "evaluation"
for source_dir in (CORE_DIR, EVALUATION_DIR):
    if str(source_dir) not in sys.path:
        sys.path.insert(0, str(source_dir))

from attach_archs4_series import _series_tokens, connected_series_groups  # noqa: E402
from build_stage1_k4_external_curation import triage_candidates  # noqa: E402
from recover_organ_labels import load_ontology  # noqa: E402
from train_manifest import sha256_file, sha256_lines  # noqa: E402


COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
EXPECTED_STATUS = "frozen_gtex_to_archs4_development_contract"


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _validate_sources(args: argparse.Namespace) -> tuple[dict[str, Any], list[str]]:
    protocol_path = Path(args.protocol)
    if sha256_file(protocol_path) != args.expected_protocol_sha256:
        raise ValueError("GTEx-to-ARCHS4 protocol SHA256 mismatch")
    protocol = json.loads(protocol_path.read_text())
    if protocol.get("status") != EXPECTED_STATUS:
        raise ValueError("GTEx-to-ARCHS4 protocol is not frozen")
    if (
        protocol.get("firewalls", {}).get(
            "archs4_lockbox_expression_access_before_candidate_freeze"
        )
        is not False
    ):
        raise ValueError("ARCHS4 expression firewall is not closed")
    if COMMIT_PATTERN.fullmatch(args.code_commit) is None:
        raise ValueError("curation build requires a full hexadecimal Git commit")

    sources = protocol["archs4_inventory_sources"]
    expected = {
        Path(args.current_metadata): sources["current_human_metadata_sha256"],
        Path(args.historical_metadata): sources["historical_v11_metadata_sha256"],
        Path(args.recovered_labels): sources["recovered_labels_sha256"],
        Path(args.recovery_report): sources["recovery_report_sha256"],
        Path(args.ontology): sources["ontology_sha256"],
        Path(args.recovery_source): sources["label_recovery_source_sha256"],
    }
    for path, digest in expected.items():
        if not path.is_file() or sha256_file(path) != digest:
            raise ValueError(f"curation source SHA256 mismatch: {path}")

    organs = list(protocol["organ_selection"]["ordered_organs"])
    if len(organs) != 8 or len(set(organs)) != 8:
        raise ValueError("frozen K8 organ family is incomplete")
    return protocol, organs


def _build_candidates(
    current: pd.DataFrame,
    historical: pd.DataFrame,
    recovered: pd.DataFrame,
    *,
    organs: list[str],
    cutoff: str,
) -> tuple[pd.DataFrame, dict[str, int]]:
    if len(current) != len(recovered):
        raise ValueError("current metadata and recovered labels differ in length")
    alignment = ["h5_row", "geo_accession", "series_id"]
    if not current[alignment].astype(str).equals(recovered[alignment].astype(str)):
        raise ValueError("recovered labels are not row-aligned to current metadata")
    if current["geo_accession"].duplicated().any():
        raise ValueError("current metadata repeats sample accessions")

    historical_ids = set(historical["geo_accession"].astype(str))
    historical_tokens: set[str] = set()
    for value in historical["series_id"].astype(str):
        historical_tokens.update(_series_tokens(value))

    candidates = recovered[
        recovered["tier"].eq("high_confidence")
        & recovered["organ"].isin(organs)
    ].copy()
    candidates = candidates[
        ~candidates["geo_accession"].astype(str).isin(historical_ids)
    ].copy()
    candidates["_historical_series_overlap"] = candidates["series_id"].astype(str).map(
        lambda value: bool(_series_tokens(value) & historical_tokens)
    )
    candidates = candidates[~candidates["_historical_series_overlap"]].copy()
    candidates["series_group_id"] = connected_series_groups(
        candidates["series_id"].astype(str).tolist()
    )
    dates = pd.to_datetime(candidates["submission_date"], errors="coerce", utc=True)
    cutoff_timestamp = pd.Timestamp(cutoff, tz="UTC")
    candidates = candidates.loc[dates > cutoff_timestamp].copy()
    if candidates.empty or set(candidates["organ"]) != set(organs):
        raise ValueError("post-firewall candidate pool does not cover all K8 organs")

    candidates = candidates.rename(
        columns={
            "geo_accession": "sample_id",
            "evidence": "label_evidence",
        }
    )
    candidates["submitted_after_v11_creation"] = True
    output_columns = [
        "h5_row",
        "sample_id",
        "series_id",
        "organ",
        "uberon_id",
        "label_evidence",
        "source_name_ch1",
        "title",
        "characteristics_ch1",
        "singlecellprobability",
        "library_strategy",
        "library_source",
        "submission_date",
        "last_update_date",
        "readsaligned",
        "readstotal",
        "series_group_id",
        "submitted_after_v11_creation",
    ]
    candidates = candidates[output_columns].sort_values(
        ["organ", "series_group_id", "sample_id"]
    ).reset_index(drop=True)
    counts = {
        "historical_accessions": len(historical_ids),
        "historical_series_tokens": len(historical_tokens),
        "candidate_samples": len(candidates),
        "candidate_connected_studies": candidates["series_group_id"].nunique(),
    }
    return candidates, counts


def _build_workbook(
    triaged: pd.DataFrame, *, organs: list[str]
) -> pd.DataFrame:
    rank = {
        "priority_a_clean_positive_reference": 0,
        "priority_b_manual_review": 1,
        "excluded_by_classifier": 2,
    }
    triaged = triaged.copy()
    triaged["_triage_rank"] = triaged["triage_tier"].map(rank)
    group_organs = triaged.groupby("series_group_id")["organ"].agg(
        lambda values: "|".join(sorted(set(values)))
    )
    rows: list[dict[str, Any]] = []
    for (organ, group_id), group in triaged.groupby(
        ["organ", "series_group_id"], sort=True
    ):
        ordered = group.sort_values(
            ["_triage_rank", "submitted_after_v11_creation", "sample_id"],
            ascending=[True, False, True],
        )
        representative = ordered.iloc[0]
        counts = group["triage_tier"].value_counts()
        flags = sorted(
            {
                flag
                for value in group["triage_flags"]
                for flag in str(value).split(";")
                if flag
            }
        )
        reasons = sorted(
            {
                reason
                for value in group["classifier_reasons"]
                for reason in str(value).split(";")
                if reason
            }
        )
        n_a = int(counts.get("priority_a_clean_positive_reference", 0))
        n_b = int(counts.get("priority_b_manual_review", 0))
        n_excluded = int(counts.get("excluded_by_classifier", 0))
        automated_priority = (
            "A"
            if n_a == len(group) and not flags and not reasons
            else ("B" if n_a + n_b else "excluded_only")
        )
        organ_family = group_organs[group_id]
        priority_samples = ordered[
            ordered["triage_tier"] != "excluded_by_classifier"
        ]["sample_id"].head(10)
        rows.append(
            {
                "organ": organ,
                "series_group_id": group_id,
                "organs_in_connected_group": organ_family,
                "cross_organ_connected_group": "|" in organ_family,
                "series_tokens": " ".join(
                    sorted(
                        {
                            token
                            for value in group["series_id"]
                            for token in _series_tokens(value)
                        }
                    )
                ),
                "geo_urls": ";".join(
                    f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={token}"
                    for token in sorted(
                        {
                            token
                            for value in group["series_id"]
                            for token in _series_tokens(value)
                        }
                    )
                ),
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
                "classifier_reasons_seen": ";".join(reasons),
                "candidate_sample_ids_first10": " ".join(priority_samples),
                "manual_study_decision": "pending",
                "reviewed_organ": "",
                "bulk_tissue_confirmed": "",
                "reference_stratum": "",
                "publication_or_bioproject": "",
                "manual_donor_audit": "pending",
                "manual_near_duplicate_audit": "pending",
                "manual_review_notes": "",
            }
        )
    workbook = pd.DataFrame(rows)
    workbook["_organ_rank"] = workbook["organ"].map(
        {organ: index for index, organ in enumerate(organs)}
    )
    workbook["_priority_rank"] = workbook["automated_priority"].map(
        {"A": 0, "B": 1, "excluded_only": 2}
    )
    return (
        workbook.sort_values(
            [
                "_organ_rank",
                "_priority_rank",
                "n_priority_a",
                "n_priority_b",
                "n_post_cutoff_samples",
                "series_group_id",
            ],
            ascending=[True, True, False, False, False, True],
        )
        .drop(columns=["_organ_rank", "_priority_rank"])
        .reset_index(drop=True)
    )


def build(args: argparse.Namespace) -> dict[str, Any]:
    protocol, organs = _validate_sources(args)
    current = pd.read_parquet(Path(args.current_metadata))
    historical = pd.read_parquet(Path(args.historical_metadata))
    recovered = pd.read_parquet(Path(args.recovered_labels))
    candidates, firewall_counts = _build_candidates(
        current,
        historical,
        recovered,
        organs=organs,
        cutoff=protocol["archs4_inventory_sources"]["temporal_cutoff"],
    )
    ontology = load_ontology(Path(args.ontology))
    triaged = triage_candidates(candidates, ontology)
    workbook = _build_workbook(triaged, organs=organs)

    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise FileExistsError(f"curation output already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    candidate_path = output_dir / "candidate_metadata.parquet"
    triage_path = output_dir / "sample_triage.parquet"
    workbook_path = output_dir / "study_curation_workbook.csv"
    candidates.to_parquet(candidate_path, index=False)
    triaged.to_parquet(triage_path, index=False)
    workbook.to_csv(workbook_path, index=False, lineterminator="\n")

    report = {
        "schema_version": 1,
        "status": "k8_curation_ready_manual_decisions_required",
        "code_commit": args.code_commit,
        "metadata_only": True,
        "expression_values_read": False,
        "efficacy_scoring_performed": False,
        "external_lockbox_frozen": False,
        "ready_for_lockbox_freeze": False,
        "ready_for_expression_access": False,
        "automated_decisions_are_final": False,
        "manual_decisions_complete": False,
        "ordered_organs": organs,
        "counts": {
            **firewall_counts,
            "workbook_rows": len(workbook),
            "pending_study_decisions": int(
                workbook["manual_study_decision"].eq("pending").sum()
            ),
            "pending_donor_audits": int(
                workbook["manual_donor_audit"].eq("pending").sum()
            ),
            "pending_near_duplicate_audits": int(
                workbook["manual_near_duplicate_audit"].eq("pending").sum()
            ),
            "candidate_samples_by_organ": {
                key: int(value)
                for key, value in candidates["organ"].value_counts().items()
            },
            "candidate_studies_by_organ": {
                key: int(value)
                for key, value in candidates.groupby("organ")[
                    "series_group_id"
                ].nunique().items()
            },
        },
        "hashes": {
            "protocol_sha256": sha256_file(Path(args.protocol)),
            "current_metadata_sha256": sha256_file(Path(args.current_metadata)),
            "historical_metadata_sha256": sha256_file(
                Path(args.historical_metadata)
            ),
            "historical_accession_sha256": sha256_lines(
                historical["geo_accession"].astype(str)
            ),
            "recovered_labels_sha256": sha256_file(Path(args.recovered_labels)),
            "recovery_report_sha256": sha256_file(Path(args.recovery_report)),
            "ontology_sha256": sha256_file(Path(args.ontology)),
            "candidate_metadata_sha256": sha256_file(candidate_path),
            "sample_triage_sha256": sha256_file(triage_path),
            "study_curation_workbook_sha256": sha256_file(workbook_path),
        },
        "blocking_gates": [
            "candidate and evaluator bundle hashes are not yet frozen",
            "manual study decisions are pending",
            "manual donor and cross-study near-duplicate audits are pending",
            "exact development and lockbox study roles are not frozen",
            "strata, fine-tuning doses, and decision gates are not frozen",
        ],
        "next_gate": (
            "Pin GEO/publication/BioProject metadata for a conservative ordered "
            "shortlist in every organ, record explicit accept/reject and donor/"
            "near-duplicate decisions, and validate an exact expression-sealed "
            "development/lockbox manifest."
        ),
    }
    _atomic_json(output_dir / "curation_report.json", report)
    (output_dir / "CURATION_READY").write_text(
        "K8 metadata curation workbook ready; ARCHS4 expression remains sealed.\n"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--current-metadata", required=True)
    parser.add_argument("--historical-metadata", required=True)
    parser.add_argument("--recovered-labels", required=True)
    parser.add_argument("--recovery-report", required=True)
    parser.add_argument("--ontology", required=True)
    parser.add_argument("--recovery-source", required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    print(json.dumps(build(args), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
