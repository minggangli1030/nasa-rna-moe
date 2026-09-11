#!/usr/bin/env python3
"""Freeze the training-only Stage 2B B0-B5 diagnostic before opening outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.train_manifest import sha256_file, sha256_lines  # noqa: E402


SEEDS = (17, 42, 101)
REQUIRED_REFUSAL_INPUTS = (
    "substitution_report",
    "substitution_per_seed_edges",
    "additive_report",
    "additive_edges",
    "additive_per_seed",
    "stability_report",
    "stability_edges",
    "expert_similarity",
)


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _parse_seed_paths(values: list[str], *, label: str) -> dict[int, Path]:
    parsed: dict[int, Path] = {}
    for value in values:
        seed_text, separator, path_text = value.partition("=")
        if not separator:
            raise ValueError(f"{label} must use SEED=PATH")
        seed = int(seed_text)
        if seed in parsed:
            raise ValueError(f"{label} repeats seed {seed}")
        parsed[seed] = Path(path_text)
    if tuple(sorted(parsed)) != SEEDS:
        raise ValueError(f"{label} must provide exactly seeds {SEEDS}")
    return parsed


def _parse_named_paths(values: list[str], *, label: str) -> dict[str, Path]:
    parsed: dict[str, Path] = {}
    for value in values:
        name, separator, path_text = value.partition("=")
        if not separator or not name:
            raise ValueError(f"{label} must use NAME=PATH")
        if name in parsed:
            raise ValueError(f"{label} repeats {name}")
        parsed[name] = Path(path_text)
    return parsed


def _array_sha256(value: np.ndarray) -> str:
    array = np.ascontiguousarray(value)
    digest = hashlib.sha256()
    digest.update(str(array.dtype).encode("utf-8"))
    digest.update(np.asarray(array.shape, dtype=np.int64).tobytes())
    digest.update(array.tobytes())
    return digest.hexdigest()


def freeze(args: argparse.Namespace) -> dict[str, Any]:
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(output)
    if len(args.code_commit) != 40 or any(
        char not in "0123456789abcdef" for char in args.code_commit
    ):
        raise ValueError("code commit must be a full lowercase Git SHA")

    repair_protocol_path = Path(args.repair_protocol)
    repair_protocol_sha = sha256_file(repair_protocol_path)
    if repair_protocol_sha != args.expected_repair_protocol_sha256:
        raise ValueError("repair protocol SHA256 mismatch")
    repair = json.loads(repair_protocol_path.read_text())
    if repair.get("status") != "frozen_before_repair_training":
        raise ValueError("source repair protocol is not frozen")
    if repair.get("firewalls", {}).get("archs4_access") is not False:
        raise ValueError("source repair protocol does not prohibit ARCHS4")

    source_paths = {
        "expression_sha256": Path(args.expression_parquet),
        "expression_metadata_sha256": Path(args.expression_metadata),
        "manifest_sha256": Path(args.manifest),
        "axis_definitions_sha256": Path(args.axis_definitions),
        "basis_bundle_sha256": Path(args.basis_bundle),
    }
    source_hashes = {key: sha256_file(path) for key, path in source_paths.items()}
    for key, observed in source_hashes.items():
        if observed != repair["inputs"][key]:
            raise ValueError(f"{key} differs from the frozen repair lineage")

    pooled_paths = _parse_seed_paths(args.pooled_checkpoint, label="pooled checkpoint")
    pooled_hashes = {
        str(seed): sha256_file(path) for seed, path in pooled_paths.items()
    }
    if pooled_hashes != repair["inputs"]["pooled_checkpoint_sha256"]:
        raise ValueError("pooled checkpoint family differs from frozen inputs")

    private_roots = _parse_seed_paths(args.private_run_root, label="private run root")
    private_inputs: dict[str, Any] = {}
    for seed, root in private_roots.items():
        metadata_path = root / "run_metadata.json"
        checkpoint_path = root / "final_heads.pt"
        if not (root / "COMPLETE").exists():
            raise ValueError(f"private seed {seed} is incomplete")
        metadata = json.loads(metadata_path.read_text())
        if (
            metadata.get("status") != "complete"
            or int(metadata.get("seed", -1)) != seed
            or metadata.get("mechanical_only") is not False
            or metadata["hashes"].get("protocol_sha256") != repair_protocol_sha
        ):
            raise ValueError(f"private seed {seed} metadata violates lineage")
        checkpoint_sha = sha256_file(checkpoint_path)
        if checkpoint_sha != metadata["hashes"].get("checkpoint_sha256"):
            raise ValueError(f"private seed {seed} checkpoint hash differs")
        private_inputs[str(seed)] = {
            "run_metadata_sha256": sha256_file(metadata_path),
            "final_heads_sha256": checkpoint_sha,
            "valid_state_prefix": "organ_private_phase1.",
        }

    manifest = pd.read_parquet(args.manifest)
    required_columns = {
        "sample_id",
        "split",
        "balanced_train",
        "organ",
        "tissue_site",
        "series_group_id",
        "organ_k8",
    }
    if not required_columns.issubset(manifest.columns):
        raise ValueError("manifest lacks required Stage 2B fields")
    training = (
        manifest.loc[
            manifest["split"].astype(str).eq("train")
            & manifest["balanced_train"].astype(bool)
        ]
        .sort_values("sample_id")
        .reset_index(drop=True)
    )
    if len(training) == 0 or training["sample_id"].astype(str).duplicated().any():
        raise ValueError("training sample population is empty or duplicated")
    donor_ids = sorted(training["series_group_id"].astype(str).unique())
    if len(donor_ids) != int(repair["inputs"]["training_donors"]):
        raise ValueError("training donor count differs from repair protocol")
    organs = sorted(training["organ"].astype(str).unique())
    if len(organs) != 8:
        raise ValueError("training population does not contain exact K8 organs")

    with np.load(args.axis_definitions, allow_pickle=False) as archive:
        score_indices = archive["score_gene_indices"].astype(np.int64)
    if (
        score_indices.ndim != 1
        or len(score_indices) != int(repair["inputs"]["score_genes"])
        or len(np.unique(score_indices)) != len(score_indices)
    ):
        raise ValueError("score-index vector differs from frozen design")

    refusal_paths = _parse_named_paths(args.refusal_input, label="refusal input")
    if tuple(sorted(refusal_paths)) != tuple(sorted(REQUIRED_REFUSAL_INPUTS)):
        raise ValueError(
            f"refusal inputs must be exactly {REQUIRED_REFUSAL_INPUTS}"
        )
    refusal_hashes = {
        name: sha256_file(path) for name, path in refusal_paths.items()
    }

    protocol = {
        "schema_version": 1,
        "protocol_name": "stage2b_training_only_mask_consistency_diagnostic",
        "status": "frozen_before_stage2b_diagnostic_access",
        "frozen_at_utc": args.frozen_at_utc
        or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "authorized_by_user": True,
        "code_commit": args.code_commit,
        "inputs": {
            **source_hashes,
            "repair_protocol_sha256": repair_protocol_sha,
            "pooled_checkpoint_sha256": pooled_hashes,
            "valid_private_inputs": private_inputs,
            "program_decoder_sha256": repair["inputs"]["decoder_sha256"][
                "program_decoder_sha256"
            ],
            "random_decoder_sha256": repair["inputs"]["decoder_sha256"][
                "random_decoder_sha256"
            ],
            "score_index_sha256": _array_sha256(score_indices),
            "training_sample_ids_sha256": sha256_lines(
                training["sample_id"].astype(str).tolist()
            ),
            "training_donor_ids_sha256": sha256_lines(donor_ids),
            "training_samples": len(training),
            "training_donors": len(donor_ids),
            "organs": organs,
            "refusal_inputs_sha256": refusal_hashes,
        },
        "canonical_cache": {
            "preprocessing_version": "stage2b-canonical-full-score-mask-v1",
            "mask_token": float(repair["training"]["mask_token"]),
            "dtype_policy": "deterministic_fp32",
            "fixed_batch_size": 8,
            "determinism_probe_samples": 32,
            "determinism_requirement": "bitwise_identical_repeated_extraction",
            "required_key_fields": [
                "sample_id",
                "trunk_checkpoint_sha256",
                "manifest_sha256",
                "score_index_sha256",
                "decoder_sha256",
                "mask_token_id",
                "preprocessing_version",
                "ridge_lambda",
                "dtype_policy",
            ],
            "required_arrays": [
                "h_canon",
                "c_canon",
                "r_full",
                "pooled_prediction",
                "private_prediction",
            ],
            "partial_reuse_allowed": False,
        },
        "source_training": {
            "private_adapter_dim": int(repair["training"]["private_adapter_dim"]),
            "program_components": int(repair["inputs"]["components"]),
            "source_projection_ridge": float(
                repair["training"]["projection_ridge"]
            ),
        },
        "ridge_selection": {
            "grid": [0.0, 1e-8, 1e-7, 1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 1e-1],
            "folds": 5,
            "fold_seed": 20260730,
            "objective": "mean held-out gene-space residual reconstruction MSE across all three trunks",
            "selection": "single minimum shared by all trunks; smallest lambda breaks exact ties",
            "probe_samples_per_organ": 32,
        },
        "b0_cross_trunk": {
            "probe_folds": 5,
            "folds_identical_across_all_ordered_comparisons": True,
            "ridge_grid": [1e-4, 1e-3, 1e-2, 1e-1, 1.0, 10.0],
            "metrics": [
                "held_out_gene_space_reconstruction",
                "median_component_correlation",
                "entropy_rank",
                "principal_angles",
                "canonical_correlations",
            ],
            "high_target_agreement_rule": {
                "minimum_median_component_pearson": 0.3,
                "minimum_median_canonical_correlation_margin_over_random_basis": 0.05,
            },
            "high_probe_rule": {
                "minimum_median_component_pearson": 0.3,
                "minimum_gene_space_error_recovery_fraction": 0.0,
            },
            "seed17_replication_rule": {
                "minimum_median_component_pearson": 0.3,
                "minimum_gene_space_error_recovery_fraction": 0.0,
            },
            "claim_boundary": "cross-trunk reproducible sample-associated structure, not intrinsic biology",
        },
        "b1_mask_decomposition": {
            "probe_samples_per_organ": 32,
            "partial_mask_ratio": 0.3,
            "replicates": 8,
            "mask_seed": 20260731,
            "arms": ["behavioral", "geometric", "combined_legacy"],
        },
        "b2_rank": {
            "conventions": ["raw", "standardized", "whitened"],
            "metrics": ["entropy_rank", "participation_ratio"],
            "aggregation_units": ["sample", "donor", "within_organ"],
            "bare_scalar_allowed": False,
        },
        "b3_ceiling": {
            "bootstrap_unit": "training donor",
            "replicates": 2000,
            "seed": 20260801,
            "recompute_donor_means_and_spectrum_each_replicate": True,
        },
        "b4_metadata": {
            "available_manifest_fields": sorted(manifest.columns.astype(str)),
            "candidate_fields": [
                "organ",
                "tissue_site",
                "sex",
                "age_bracket",
                "rin",
                "ischemic_time",
                "detected_gene_count",
                "library_depth",
            ],
            "missing_fields_are_reported_not_invented": True,
            "grouped_folds": 5,
            "minimum_incremental_r2_margin_for_pause": 0.02,
            "pause_requires_margin_in_all_three_trunks": True,
            "pause_rule": "pause if a supported non-organ field has reproducibly larger held-out incremental R2 than organ",
        },
        "b5_refusal": {
            "outcome": "donor-specific excess effect versus exposure-matched random auxiliaries",
            "opportunity_cost_reported_separately": True,
            "cross_validation": "leave one organ out; remove every edge touching held-out organ",
            "null_models": ["recipient_only", "donor_only", "recipient_plus_donor"],
            "maximum_outcome_independent_features": 3,
            "candidate_features": [
                "frozen_expert_utility_cosine_similarity",
                "recipient_identity",
                "donor_identity",
            ],
            "additive_edges_are_independent_small_holdout": True,
            "fixed_ridge_lambda": 1.0,
            "harmful_label": "mean donor-specific excess effect below zero with all three seed excess effects below zero",
            "feature_model_must_reduce_leave_one_organ_out_mse_vs_best_null": True,
            "flag_if_predicted_donor_specific_excess_is_below_zero": True,
            "required_metrics": [
                "precision",
                "recall",
                "specificity",
                "flagged_fraction",
            ],
            "maximum_flagged_fraction": 0.5,
            "vacuous_refuse_everything_passes": False,
        },
        "decision_rule": {
            "phase_b_only": True,
            "selects_conditioning_axis_and_representation_interpretation": True,
            "does_not_open_archs4": True,
            "does_not_train_neural_checkpoints": True,
            "candidate_protocol_frozen_only_after_report": True,
        },
        "firewalls": {
            "archs4_access": False,
            "calibration_split_access": False,
            "neural_checkpoint_updates": False,
            "best_seed_selection": False,
            "post_outcome_threshold_changes": False,
            "normalization_fit_outside_training_donors": False,
        },
        "claim_boundary": "Training-only GTEx diagnostic evidence; no independent-study universality, mechanism, disease, clinical, or spaceflight claim.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    _atomic_json(output, protocol)
    return protocol


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repair-protocol", required=True)
    parser.add_argument("--expected-repair-protocol-sha256", required=True)
    parser.add_argument("--expression-parquet", required=True)
    parser.add_argument("--expression-metadata", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--axis-definitions", required=True)
    parser.add_argument("--basis-bundle", required=True)
    parser.add_argument("--pooled-checkpoint", action="append", required=True)
    parser.add_argument("--private-run-root", action="append", required=True)
    parser.add_argument("--refusal-input", action="append", required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--frozen-at-utc")
    parser.add_argument("--output", required=True)
    return parser


def main() -> None:
    parsed = build_parser().parse_args()
    protocol = freeze(parsed)
    output = Path(parsed.output)
    print(
        json.dumps(
            {
                "status": protocol["status"],
                "output": str(output),
                "sha256": sha256_file(output),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
