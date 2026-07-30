#!/usr/bin/env python3
"""Create a fail-closed Tier-0 inventory after frozen Stage 2B evaluation.

This performs no efficacy fitting. It records which proposed axes are already
evaluated, available for an ID-safe join, require a frozen derived representation,
or must remain downstream-only to protect the final evaluation firewall.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd


REQUIRED_COLUMNS = {"sample_id", "donor_id", "organ", "tissue_site", "split"}
AXIS_REGISTRY = {
    "tissue_site": {
        "kind": "categorical_biological",
        "source": "existing_gtex_manifest",
        "next_action": "use_frozen_stage2b_b4_result",
    },
    "age_or_developmental_stage": {
        "kind": "categorical_or_continuous_biological",
        "source": "id_safe_public_gtex_subject_or_sample_attributes",
        "next_action": "join_then_inventory_before_fitting",
    },
    "sex": {
        "kind": "categorical_biological",
        "source": "id_safe_public_gtex_subject_attributes",
        "next_action": "join_then_inventory_before_fitting",
    },
    "cell_type_composition": {
        "kind": "continuous_biological",
        "source": "frozen_public_marker_or_reference_method",
        "next_action": "freeze_reference_and_visible_gene_scoring_contract",
    },
    "continuous_programs": {
        "kind": "continuous_biological",
        "programs": [
            "immune",
            "metabolic",
            "mitochondrial",
            "contractile",
            "extracellular_matrix",
            "cell_cycle",
            "stress_response",
        ],
        "source": "frozen_public_gene_sets",
        "next_action": "freeze_gene_sets_and_visible_gene_scoring_contract",
    },
    "disease_treatment_hypoxia": {
        "kind": "downstream_target_first",
        "source": "independent_development_and_final_study_disjoint_cohorts",
        "next_action": "do_not_select_architecture_on_final_evaluation_cohort",
    },
    "spaceflight_state": {
        "kind": "downstream_target_first",
        "source": "osdr_mission_or_experiment_grouped_cohorts",
        "next_action": "do_not_select_architecture_on_final_evaluation_cohort",
    },
}


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


def build(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path = Path(args.manifest)
    report_path = Path(args.b0_b4_report)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)

    manifest = pd.read_parquet(manifest_path)
    missing = sorted(REQUIRED_COLUMNS - set(manifest.columns))
    if missing:
        raise ValueError(f"manifest lacks required columns: {missing}")
    if manifest["sample_id"].astype(str).duplicated().any():
        raise ValueError("manifest sample IDs are not unique")

    training = manifest.loc[manifest["split"].astype(str).eq("train")].copy()
    if training.empty:
        raise ValueError("manifest contains no training rows")
    if set(training["sample_id"].astype(str)) & set(
        manifest.loc[~manifest["split"].astype(str).eq("train"), "sample_id"].astype(str)
    ):
        raise ValueError("training and non-training sample IDs overlap")

    b0_b4 = json.loads(report_path.read_text())
    if b0_b4.get("status") != "complete":
        raise ValueError("B0-B4 report is not complete")
    if "b4" not in b0_b4:
        raise ValueError("B0-B4 report lacks B4")

    field_inventory = {}
    for field in sorted(set(manifest.columns) | {"sex", "age_bracket"}):
        if field not in training.columns:
            field_inventory[field] = {"status": "missing"}
            continue
        values = training[field]
        field_inventory[field] = {
            "status": "available",
            "missing_fraction": float(values.isna().mean()),
            "unique_nonmissing": int(values.nunique(dropna=True)),
        }

    tissue_counts = (
        training.groupby(["organ", "tissue_site"], dropna=False)
        .agg(samples=("sample_id", "size"), donors=("donor_id", "nunique"))
        .reset_index()
        .sort_values(["organ", "tissue_site"])
    )
    tissue_path = output_dir / "tissue_site_training_counts.csv"
    tissue_counts.to_csv(tissue_path, index=False)

    result = {
        "schema_version": 1,
        "status": "complete",
        "scope": "training-only Tier-0 inventory; no new efficacy fitting",
        "firewalls": {
            "calibration_access": False,
            "archs4_access": False,
            "downstream_final_test_axis_selection": False,
            "neural_checkpoint_updates": False,
        },
        "inputs": {
            "manifest_sha256": sha256_file(manifest_path),
            "b0_b4_report_sha256": sha256_file(report_path),
            "training_samples": int(len(training)),
            "training_donors": int(training["donor_id"].astype(str).nunique()),
            "organs": int(training["organ"].astype(str).nunique()),
            "tissue_sites": int(training["tissue_site"].astype(str).nunique()),
        },
        "stage2b_b4": {
            "decision": b0_b4["b4"]["decision"],
            "pause_fields": b0_b4["b4"]["pause_fields"],
            "inventory": b0_b4["b4"]["inventory"],
        },
        "manifest_field_inventory": field_inventory,
        "axis_registry": AXIS_REGISTRY,
        "next_gate": (
            "freeze ID-safe metadata joins and public feature definitions before "
            "running the common organ-conditional grouped-CV Tier-1 screen"
        ),
    }
    report_output = output_dir / "multiaxis_tier0_inventory.json"
    atomic_json(report_output, result)
    artifacts = (report_output, tissue_path)
    (output_dir / "IMMUTABLE_SHA256SUMS").write_text(
        "".join(f"{sha256_file(path)}  {path.name}\n" for path in artifacts)
    )
    (output_dir / "COMPLETE").touch()
    return result


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--manifest", required=True)
    value.add_argument("--b0-b4-report", required=True)
    value.add_argument("--output-dir", required=True)
    return value


if __name__ == "__main__":
    print(json.dumps(build(parser().parse_args()), indent=2, sort_keys=True))

