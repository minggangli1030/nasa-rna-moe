#!/usr/bin/env python3
"""Freeze the Stage 1 OSDR downstream-development protocol before data download."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-metadata", required=True)
    parser.add_argument("--candidate-ledger", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    metadata_path = Path(args.candidate_metadata)
    ledger_path = Path(args.candidate_ledger)
    output_path = Path(args.output)
    if output_path.exists():
        raise FileExistsError(output_path)
    frame = pd.read_csv(metadata_path, low_memory=False)
    organs = sorted(frame["downstream_organ"].unique().tolist())
    if organs != [
        "adipose",
        "brain",
        "colon",
        "heart",
        "liver",
        "lung",
        "skeletal_muscle",
        "skin",
    ]:
        raise ValueError("candidate cohort does not contain the exact K8 organs")
    protocol = {
        "schema_version": 1,
        "status": "frozen_stage1_osdr_downstream_development",
        "role": (
            "external cross-species downstream development; not a final untouched "
            "confirmatory test"
        ),
        "cohort": {
            "candidate_metadata_sha256": sha256_file(metadata_path),
            "requested_samples": int(len(frame)),
            "requested_studies": int(frame["id.accession"].nunique()),
            "requested_study_organ_units": int(
                frame[["id.accession", "downstream_organ"]]
                .drop_duplicates()
                .shape[0]
            ),
            "organs": organs,
            "label_positive": "exact structured Space Flight",
            "label_negative": "exact structured Ground Control",
            "group_column": "id.accession",
            "qc_min_nonzero": 14_000,
            "post_qc_rule": (
                "exclude failed samples and any study-organ unit losing either class; "
                "add no replacements"
            ),
        },
        "stage1_family": {
            "candidate_ledger_sha256": sha256_file(ledger_path),
            "seeds": [17, 42, 101],
            "conditions": [
                "pooled",
                "pooled_adapter",
                "true_organ",
                "blind_router_hard",
                "blind_router_soft",
            ],
            "best_seed_selection": False,
            "checkpoint_updates": False,
        },
        "representations": {
            "raw_expression": True,
            "pca": True,
            "stage1_score_panel_predictions": True,
            "target_hiding": "reuse frozen Stage 1 score-gene panel and mask token",
        },
        "evaluation": {
            "outer_split": "study-grouped, identical across representations",
            "inner_split": "training-study-grouped only",
            "primary_metric": "AUROC",
            "secondary_metrics": [
                "AUPRC",
                "balanced_accuracy",
                "macro_f1",
            ],
            "head": "elastic-net logistic regression",
            "equal_tuning_budget": True,
            "post_hoc_split_or_seed_selection": False,
        },
        "firewalls": {
            "osdr_used_for_stage1_training": False,
            "osdr_used_for_stage1_architecture_selection": False,
            "same_osdr_cohort_may_select_future_axis_and_confirm_it": False,
            "final_claim_requires_new_untouched_grouped_confirmation": True,
        },
        "implementation_sha256": {
            "audit": sha256_file(
                Path("evaluation/audit_downstream_cohort_readiness.py")
            ),
            "freeze": sha256_file(Path(__file__)),
            "prepare": sha256_file(Path("evaluation/prepare_osdr_downstream_cohort.py")),
            "osdr_preprocessor": sha256_file(Path("evaluation/evaluate_osdr.py")),
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "output": str(output_path),
                "sha256": sha256_file(output_path),
                "requested_samples": len(frame),
                "requested_studies": frame["id.accession"].nunique(),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
