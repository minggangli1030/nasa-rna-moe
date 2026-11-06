#!/usr/bin/env python3
"""Freeze organ-to-random-expert mappings from held-out K45 calibration scores.

The mappings are control plumbing, not a candidate-selection result.  They are
computed before the final train+cal refit, using only the already completed
K45 banks whose adapters never trained on calibration rows.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = ROOT / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from train_manifest import sha256_file, sha256_json, sha256_lines  # noqa: E402


MODEL_SEEDS = (17, 42, 101)
PARTITION_SEEDS = (17, 42, 101)
ACTIVE_ORGANS = ("brain", "liver", "skeletal_muscle", "skin")


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _parse_seed_roots(values: list[str]) -> dict[int, Path]:
    output: dict[int, Path] = {}
    for raw in values:
        if "=" not in raw:
            raise ValueError("seed-root must use SEED=PATH")
        seed_text, path_text = raw.split("=", 1)
        seed = int(seed_text)
        if seed in output:
            raise ValueError(f"duplicate seed-root for {seed}")
        output[seed] = Path(path_text)
    if tuple(sorted(output)) != MODEL_SEEDS:
        raise ValueError(f"seed-root must cover exactly {MODEL_SEEDS}")
    return output


def aggregate_mapping(
    expert_mse_by_seed: dict[int, np.ndarray],
    organs: np.ndarray,
    groups: np.ndarray,
) -> tuple[dict[str, int], dict[str, list[float]]]:
    """Aggregate seeds, then samples within study, then studies within organ."""
    if tuple(sorted(expert_mse_by_seed)) != MODEL_SEEDS:
        raise ValueError(f"expert losses must cover exactly model seeds {MODEL_SEEDS}")
    shapes = {np.asarray(value).shape for value in expert_mse_by_seed.values()}
    if len(shapes) != 1:
        raise ValueError("expert loss arrays differ in shape across model seeds")
    shape = next(iter(shapes))
    organs = np.asarray(organs).astype(str)
    groups = np.asarray(groups).astype(str)
    if len(shape) != 2 or shape[1] != 4 or shape[0] != len(organs):
        raise ValueError("expert loss arrays must align as samples by four experts")
    if groups.shape != organs.shape:
        raise ValueError("organ and connected-study labels do not align")
    stacked = np.stack(
        [np.asarray(expert_mse_by_seed[seed], dtype=np.float64) for seed in MODEL_SEEDS]
    )
    if not np.isfinite(stacked).all():
        raise ValueError("expert loss arrays contain a non-finite value")
    seed_mean = stacked.mean(axis=0)

    mapping: dict[str, int] = {}
    score_table: dict[str, list[float]] = {}
    for organ in ACTIVE_ORGANS:
        organ_rows = organs == organ
        organ_groups = sorted(set(groups[organ_rows]))
        if not organ_groups:
            raise ValueError(f"calibration scores contain no rows for {organ}")
        study_means = np.stack(
            [seed_mean[organ_rows & (groups == group)].mean(axis=0) for group in organ_groups]
        )
        scores = study_means.mean(axis=0)
        score_table[organ] = scores.astype(float).tolist()
        mapping[organ] = int(np.argmin(scores))
    mapping["adipose"] = -1
    return mapping, score_table


def freeze(args: argparse.Namespace) -> dict[str, Any]:
    protocol_path = Path(args.protocol)
    k45_report_path = Path(args.k45_evaluation_report)
    for path in (protocol_path, k45_report_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output_dir}")

    protocol = json.loads(protocol_path.read_text())
    if (
        protocol.get("evidence_label", {}).get("internal_efficacy_scoring") is not False
        or protocol.get("firewall", {}).get("test_access_allowed") is not False
    ):
        raise ValueError("final protocol does not close internal/test scoring")
    if sha256_file(k45_report_path) != protocol.get("prior_evidence", {}).get(
        "k45_evaluation_report_sha256"
    ):
        raise ValueError("K45 evaluation report hash differs from final protocol")
    k45_report = json.loads(k45_report_path.read_text())
    decision = k45_report.get("decision", {})
    if (
        k45_report.get("status") != "complete"
        or k45_report.get("development_only") is not True
        or k45_report.get("test_accessed") is not False
        or decision.get("decision_branch") != "k4_robust"
        or decision.get("selected_candidate_for_future_freeze") != "k4_epe"
    ):
        raise ValueError("K45 report does not support the frozen K4-EPE decision")

    roots = _parse_seed_roots(args.seed_root)
    source_hashes: dict[str, dict[str, str]] = {}
    partition_results: dict[str, Any] = {}
    reference_ids = reference_organs = reference_groups = None
    for partition_seed in PARTITION_SEEDS:
        axis = f"random_group_k4_epe_p{partition_seed}"
        losses: dict[int, np.ndarray] = {}
        axis_hashes: dict[str, str] = {}
        for model_seed in MODEL_SEEDS:
            bank_dir = roots[model_seed] / "banks" / axis
            metadata_path = bank_dir / "run_metadata.json"
            scores_path = bank_dir / "calibration_scores.npz"
            checkpoint_path = bank_dir / "final_experts.pt"
            for path in (
                metadata_path,
                scores_path,
                checkpoint_path,
                bank_dir / "COMPLETE",
            ):
                if not path.exists():
                    raise FileNotFoundError(path)
            metadata = json.loads(metadata_path.read_text())
            config = metadata.get("config", {})
            hashes = metadata.get("hashes", {})
            artifacts = metadata.get("artifacts", {})
            provenance = (
                k45_report.get("bank_provenance", {})
                .get(axis, {})
                .get(str(model_seed), {})
            )
            if (
                metadata.get("status") != "complete"
                or metadata.get("axis") != axis
                or metadata.get("training_seed") != model_seed
                or metadata.get("test_accessed") is not False
                or metadata.get("mechanical_only") is not False
                or metadata.get("research_stage")
                != "stage1_organ_k45_adaptive_development"
                or config.get("num_experts") != 4
                or config.get("adapter_dim") != 64
                or config.get("final_update") != 1500
                or config.get("exposures_per_expert_target") != 2400
                or config.get("fallback_label") != -1
                or config.get("checkpoint_policy") != "predetermined_final_update"
                or config.get("router_trainable") is not False
                or hashes.get("protocol_sha256")
                != protocol.get("prior_evidence", {}).get("k45_protocol_sha256")
                or hashes.get("partition_manifest_sha256")
                != protocol.get("data", {}).get(
                    "source_k45_partition_manifest_sha256"
                )
                or hashes.get("partition_report_sha256")
                != protocol.get("data", {}).get("source_k45_partition_report_sha256")
                or hashes.get("pooled_checkpoint_sha256")
                != protocol.get("data", {}).get("pooled_checkpoint_sha256")
                or hashes.get("axis_definitions_sha256")
                != protocol.get("data", {}).get("axis_definitions_sha256")
            ):
                raise ValueError(f"invalid K45 bank metadata: seed={model_seed} axis={axis}")
            if (
                artifacts.get("calibration_scores_sha256") != sha256_file(scores_path)
                or artifacts.get("final_experts_sha256")
                != sha256_file(checkpoint_path)
                or provenance.get("metadata_sha256") != sha256_file(metadata_path)
                or provenance.get("calibration_scores_sha256")
                != sha256_file(scores_path)
                or provenance.get("final_experts_sha256")
                != sha256_file(checkpoint_path)
                or provenance.get("expert_state_sha256")
                != artifacts.get("expert_state_sha256")
            ):
                raise ValueError(f"K45 metadata does not bind scores: {scores_path}")
            with np.load(scores_path, allow_pickle=False) as archive:
                required = {"sample_ids", "groups", "organs", "expert_mse"}
                if not required.issubset(archive.files):
                    raise ValueError(f"K45 score archive lacks arrays: {scores_path}")
                sample_ids = np.asarray(archive["sample_ids"]).astype(str)
                organs = np.asarray(archive["organs"]).astype(str)
                groups = np.asarray(archive["groups"]).astype(str)
                losses[model_seed] = np.asarray(archive["expert_mse"], dtype=np.float64)
            if reference_ids is None:
                reference_ids, reference_organs, reference_groups = (
                    sample_ids,
                    organs,
                    groups,
                )
            elif not (
                np.array_equal(sample_ids, reference_ids)
                and np.array_equal(organs, reference_organs)
                and np.array_equal(groups, reference_groups)
            ):
                raise ValueError("K45 calibration score rows differ across banks")
            axis_hashes[f"seed{model_seed}_metadata_sha256"] = sha256_file(
                metadata_path
            )
            axis_hashes[f"seed{model_seed}_scores_sha256"] = sha256_file(scores_path)
            axis_hashes[f"seed{model_seed}_checkpoint_sha256"] = sha256_file(
                checkpoint_path
            )
        assert reference_organs is not None and reference_groups is not None
        mapping, scores = aggregate_mapping(
            losses, reference_organs, reference_groups
        )
        partition_results[str(partition_seed)] = {
            "source_axis": axis,
            "final_axis": f"random_group_k4_final_p{partition_seed}",
            "organ_to_expert": mapping,
            "equal_study_mse_by_organ_and_expert": scores,
        }
        source_hashes[str(partition_seed)] = axis_hashes

    assert reference_ids is not None
    config = {
        "model_seeds": list(MODEL_SEEDS),
        "partition_seeds": list(PARTITION_SEEDS),
        "active_organs": list(ACTIVE_ORGANS),
        "aggregation_order": [
            "mean model seeds per sample",
            "mean samples per connected study",
            "equal mean connected studies per organ",
        ],
        "selection": "minimum equal-study MSE within organ",
        "tie_break": "lowest expert index under exact equality",
        "adipose_dispatch": "pooled fallback (-1)",
        "fit_timing": "before final train+cal refit",
    }
    report = {
        "schema_version": 1,
        "status": "complete",
        "experiment": "freeze_stage1_k4_random_control_mappings",
        "development_only": True,
        "candidate_selection": False,
        "test_accessed": False,
        "external_data_accessed": False,
        "config": config,
        "mappings": partition_results,
        "counts": {
            "calibration_samples": int(len(reference_ids)),
            "calibration_connected_studies": int(len(np.unique(reference_groups))),
        },
        "hashes": {
            "protocol_sha256": sha256_file(protocol_path),
            "k45_evaluation_report_sha256": sha256_file(k45_report_path),
            "calibration_sample_ids_sha256": sha256_lines(reference_ids.tolist()),
            "resolved_config_sha256": sha256_json(config),
            "sources": source_hashes,
        },
    }
    _atomic_json(output_dir / "random_control_mappings.json", report)
    (output_dir / "COMPLETE").touch()
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--k45-evaluation-report", required=True)
    parser.add_argument("--seed-root", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser


def main() -> None:
    report = freeze(build_parser().parse_args())
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
