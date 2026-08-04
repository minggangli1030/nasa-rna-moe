#!/usr/bin/env python3
"""Run an end-to-end, expression-free smoke of the ARCHS4 metadata catalog."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.build_archs4_downstream_metadata_catalog import build_catalog  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", required=True)
    parser.add_argument(
        "--stage1-manifest",
        default=str(
            ROOT
            / "artifacts/stage1_gtex_to_archs4/lockbox_run_73f9bd1/membership/lockbox_manifest.csv"
        ),
        help="Exact original 827-sample Stage-1 manifest; its SHA256 is protocol-bound.",
    )
    args = parser.parse_args()

    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=False)
    metadata_path = output_root / "synthetic_metadata.csv"
    pd.DataFrame(
        {
            "geo_accession": ["GSM_SMOKE_1", "GSM_SMOKE_2", "GSM_SMOKE_3", "GSM_SMOKE_4"],
            "series_id": ["GSE277232", "GSE999001", "GSE999002", "GSE999003"],
            "source_name_ch1": ["lung tissue", "lung tissue", "lung tissue", "kidney tissue"],
            "title": ["prior lockbox", "GTEx donor GTEX-SMOKE", "control", "control"],
            "characteristics_ch1": ["tissue: lung", "tissue: lung", "tissue: lung", "tissue: kidney"],
            "singlecellprobability": [0.0, 0.0, 0.0, 0.0],
        }
    ).to_csv(metadata_path, index=False)

    report = build_catalog(
        metadata_path=metadata_path,
        stage1_manifest_path=args.stage1_manifest,
        ontology_path=ROOT / "data/ontology/uberon_organ_map.json",
        protocol_path=ROOT / "artifacts/final_evaluation/archs4_downstream_benchmark/metadata_smoke_protocol.json",
        output_dir=output_root / "catalog",
    )
    expected = {
        "stage1_series_overlap": 1,
        "explicit_gtex_overlap": 1,
        "eligible_metadata_only": 1,
        "outside_target_organs": 1,
    }
    if report["decision_counts"] != expected:
        raise RuntimeError(f"unexpected smoke decisions: {report['decision_counts']}")
    if report["n_eligible_samples"] != 1 or report["expression_accessed"] is not False:
        raise RuntimeError("smoke did not preserve the metadata-only access contract")
    assertions = report["firewall_assertions"]
    if not assertions["all_64_connected_stage1_groups_bound"]:
        raise RuntimeError("64-group Stage-1 firewall was not bound")
    if not assertions["all_72_stage1_geo_tokens_excluded"]:
        raise RuntimeError("72-token Stage-1 firewall was not bound")

    smoke_report = {
        "schema_version": 1,
        "status": "complete",
        "kind": "synthetic_metadata_only_mechanical_smoke",
        "expression_accessed": False,
        "catalog_report": report,
    }
    (output_root / "SMOKE_COMPLETE.json").write_text(json.dumps(smoke_report, indent=2) + "\n")
    print(json.dumps(smoke_report, indent=2))


if __name__ == "__main__":
    main()
