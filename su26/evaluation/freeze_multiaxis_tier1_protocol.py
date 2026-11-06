#!/usr/bin/env python3
"""Freeze the common training-only multiaxis Tier-1 screen."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage2b-protocol", required=True)
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--hallmark-gmt", required=True)
    parser.add_argument("--router", required=True)
    parser.add_argument("--osdr-protocol", required=True)
    parser.add_argument("--osdr-candidate-metadata", required=True)
    parser.add_argument("--seed-metadata", action="append", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    seed_hashes = {}
    for value in args.seed_metadata:
        seed, separator, path = value.partition("=")
        if not separator:
            raise ValueError("seed metadata must use SEED=PATH")
        seed_hashes[str(int(seed))] = sha256_file(path)
    if sorted(seed_hashes) != ["101", "17", "42"]:
        raise ValueError("seed metadata must provide 17, 42, and 101")

    protocol = {
        "schema_version": 1,
        "status": "frozen_before_tier1_incremental_outcome_access",
        "role": (
            "training-donor multiaxis development screen plus separate OSDR "
            "downstream-label development probe; not final confirmation"
        ),
        "inputs": {
            "stage2b_protocol_sha256": sha256_file(args.stage2b_protocol),
            "training_metadata_sha256": sha256_file(args.metadata),
            "hallmark_gmt_sha256": sha256_file(args.hallmark_gmt),
            "hallmark_release": "MSigDB 2026.1.Hs",
            "hallmark_source": (
                "https://data.broadinstitute.org/gsea-msigdb/msigdb/release/"
                "2026.1.Hs/h.all.v2026.1.Hs.symbols.gmt"
            ),
            "router_sha256": sha256_file(args.router),
            "osdr_protocol_sha256": sha256_file(args.osdr_protocol),
            "osdr_candidate_metadata_sha256": sha256_file(
                args.osdr_candidate_metadata
            ),
            "seed_run_metadata_sha256": seed_hashes,
        },
        "candidates": {
            "tissue_site": {
                "kind": "categorical_nested_within_organ",
                "features": "one-hot exact GTEx tissue site",
                "coverage": (
                    "at least two >=20-donor sites in at least five organs"
                ),
            },
            "sex": {
                "kind": "categorical_donor_attribute",
                "features": "official raw GTEx v8 sex code; no inferred relabeling",
                "coverage": (
                    "every retained level >=20 donors and represented in >=5 organs"
                ),
            },
            "age_bracket": {
                "kind": "categorical_donor_attribute",
                "features": "official GTEx v8 age bracket",
                "coverage": (
                    "every retained level >=20 donors and represented in >=5 organs"
                ),
            },
            "hallmark_50": {
                "kind": "continuous_program_block",
                "features": (
                    "mean standardized log1p expression over visible non-score "
                    "members for each of the 50 hash-pinned Hallmark sets"
                ),
                "minimum_visible_genes_per_set": 10,
                "coverage": "all 50 sets valid and nonconstant in all eight organs",
            },
        },
        "base_model": {
            "features": [
                "organ one-hot",
                "RIN/10 plus missing indicator",
                "ischemic minutes/2000 plus missing indicator",
                "detected-gene fraction",
                "log1p expression sum / 20",
            ],
            "technical_proxy_names": [
                "rin",
                "ischemic_time",
                "detected_gene_fraction",
                "log_expression_sum",
            ],
        },
        "training_screen": {
            "seeds": [17, 42, 101],
            "groups": "GTEx training donor",
            "folds": 5,
            "fold_seed_base": 20260801,
            "ridge_grid": [0.0001, 0.001, 0.01, 0.1, 1.0, 10.0],
            "outcomes": [
                "pooled_reconstruction_error",
                "protected_private_error",
                "post_private_coefficients",
            ],
            "primary_outcome": "post_private_coefficients",
            "within_organ_permutation": {
                "unit": "sample row within exact organ",
                "replicates": 100,
                "seed": 20260802,
                "gate": "real incremental R2 above permutation 95th percentile",
            },
            "donor_bootstrap": {
                "replicates": 2000,
                "seed": 20260803,
                "gate": "primary incremental R2 lower 95% bound above zero",
            },
            "technical_proxy_gate": {
                "maximum_absolute_organ_partial_correlation": 0.5
            },
            "per_organ_safety": {
                "maximum_incremental_r2_harm": 0.02,
                "outcome": "protected_private_error",
            },
        },
        "advance_gate": {
            "all_outcomes_positive_in_all_three_seeds": True,
            "primary_bootstrap_lower_bound_positive_in_all_three_seeds": True,
            "primary_above_within_organ_permutation_p95_in_all_three_seeds": True,
            "coverage_pass": True,
            "technical_proxy_pass": True,
            "per_organ_safety_pass_all_seeds": True,
            "separate_osdr_downstream_label_probe_positive": True,
            "maximum_axes_advancing_to_tier2": 2,
            "maximum_axes_in_final_architecture": 1,
        },
        "firewalls": {
            "calibration_or_archs4_access": False,
            "neural_checkpoint_updates": False,
            "best_seed_selection": False,
            "cell_composition": False,
            "osdr_can_select_axis_but_cannot_confirm_final_claim": True,
            "no_post_hoc_gate_changes": True,
        },
        "deadline": "close architecture by 2026-08-02 even if no axis passes",
    }
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(sha256_file(output))


if __name__ == "__main__":
    main()
