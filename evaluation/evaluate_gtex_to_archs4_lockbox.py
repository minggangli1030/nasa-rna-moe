#!/usr/bin/env python3
"""Evaluate every frozen GTEx K8 seed with study-macro ARCHS4 estimands."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np

try:
    from evaluation.cache_gtex_to_archs4_lockbox_scores import CONDITIONS, sha256_array
    from evaluation.freeze_gtex_to_archs4_candidates import ORGANS, SEEDS
    from evaluation.freeze_gtex_to_archs4_random_controls import RANDOM_AXES
except ModuleNotFoundError:
    from cache_gtex_to_archs4_lockbox_scores import CONDITIONS, sha256_array
    from freeze_gtex_to_archs4_candidates import ORGANS, SEEDS
    from freeze_gtex_to_archs4_random_controls import RANDOM_AXES


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mse_rows(prediction: np.ndarray, target: np.ndarray) -> np.ndarray:
    return np.mean(
        np.square(
            np.asarray(prediction, dtype=np.float64)
            - np.asarray(target, dtype=np.float64)
        ),
        axis=1,
    )


def pearson_rows(prediction: np.ndarray, target: np.ndarray) -> np.ndarray:
    left = np.asarray(prediction, dtype=np.float64)
    right = np.asarray(target, dtype=np.float64)
    left = left - left.mean(axis=1, keepdims=True)
    right = right - right.mean(axis=1, keepdims=True)
    denominator = np.sqrt(
        np.square(left).sum(axis=1) * np.square(right).sum(axis=1)
    )
    output = np.full(len(left), np.nan, dtype=np.float64)
    valid = denominator > 0
    output[valid] = (left[valid] * right[valid]).sum(axis=1) / denominator[valid]
    return output


def study_table(
    values: np.ndarray, groups: np.ndarray, organs: np.ndarray
) -> dict[str, dict[str, float]]:
    values = np.asarray(values, dtype=np.float64)
    output: dict[str, dict[str, float]] = {}
    for organ in ORGANS:
        keep = organs == organ
        organ_groups = np.unique(groups[keep])
        if len(organ_groups) != 8:
            raise ValueError(f"{organ} does not have exactly eight study groups")
        output[organ] = {
            str(group): float(np.nanmean(values[keep & (groups == group)]))
            for group in organ_groups
        }
    return output


def macro(table: dict[str, dict[str, float]]) -> float:
    return float(
        np.mean(
            [
                np.mean(list(table[organ].values()), dtype=np.float64)
                for organ in ORGANS
            ],
            dtype=np.float64,
        )
    )


def bootstrap_difference(
    candidate: dict[str, dict[str, float]],
    reference: dict[str, dict[str, float]],
    *,
    seed: int,
    repetitions: int,
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    draws = np.empty(repetitions, dtype=np.float64)
    for index in range(repetitions):
        organ_values = []
        for organ in ORGANS:
            groups = sorted(candidate[organ])
            selected = rng.integers(0, len(groups), size=len(groups))
            organ_values.append(
                np.mean(
                    [
                        reference[organ][groups[item]]
                        - candidate[organ][groups[item]]
                        for item in selected
                    ]
                )
            )
        draws[index] = np.mean(organ_values)
    point = macro(reference) - macro(candidate)
    return {
        "mse_improvement": point,
        "ci95": [
            float(np.quantile(draws, 0.025)),
            float(np.quantile(draws, 0.975)),
        ],
        "one_sided_bootstrap_probability_not_positive": float(
            (1 + np.count_nonzero(draws <= 0)) / (repetitions + 1)
        ),
        "bootstrap_repetitions": repetitions,
        "bootstrap_unit": "connected_study_group_resampled_within_organ",
    }


def _load_seed_cache(path: Path, seed: int) -> dict[str, Any]:
    with np.load(path, allow_pickle=False) as archive:
        required = {
            "sample_ids",
            "groups",
            "organs",
            "target_masked",
            "metadata_json",
            *{f"prediction__{name}" for name in CONDITIONS},
        }
        missing = required - set(archive.files)
        if missing:
            raise ValueError(f"seed {seed} score cache lacks {sorted(missing)}")
        result = {name: np.asarray(archive[name]) for name in required}
    metadata = json.loads(str(result.pop("metadata_json").item()))
    if (
        metadata.get("status") != "complete"
        or int(metadata.get("seed", -1)) != seed
        or metadata.get("best_seed_selection_performed") is not False
        or metadata.get("conditions") != list(CONDITIONS)
    ):
        raise ValueError(f"seed {seed} cache metadata violates protocol")
    for name, expected in metadata.get("content_sha256", {}).items():
        if name not in result or sha256_array(result[name]) != expected:
            raise ValueError(f"seed {seed} cache content hash mismatch for {name}")
    result["metadata"] = metadata
    return result


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    protocol_path = Path(args.protocol)
    report_path = Path(args.score_cache_report)
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(output)
    if sha256_file(protocol_path) != args.expected_protocol_sha256:
        raise ValueError("protocol SHA256 mismatch")
    protocol = json.loads(protocol_path.read_text())
    if protocol.get("implementation_hashes", {}).get(
        "lockbox_evaluator_sha256"
    ) != sha256_file(Path(__file__).resolve()):
        raise ValueError("frozen evaluator implementation hash mismatch")
    score_report = json.loads(report_path.read_text())
    if (
        score_report.get("status") != "complete"
        or score_report.get("seeds") != list(SEEDS)
        or score_report.get("all_prespecified_seeds_scored") is not True
        or score_report.get("best_seed_selection_performed") is not False
    ):
        raise ValueError("score report does not contain the complete seed family")

    seed_results: dict[str, Any] = {}
    shared_ids = shared_groups = shared_organs = None
    study_mse: dict[str, dict[str, dict[str, dict[str, float]]]] = {}
    study_pearson: dict[str, dict[str, dict[str, dict[str, float]]]] = {}
    for seed in SEEDS:
        descriptor = score_report["seed_reports"][str(seed)]
        path = Path(descriptor["score_cache"])
        if sha256_file(path) != descriptor["score_cache_sha256"]:
            raise ValueError(f"seed {seed} score-cache file hash mismatch")
        cache = _load_seed_cache(path, seed)
        sample_ids = cache["sample_ids"].astype(str)
        groups = cache["groups"].astype(str)
        organs = cache["organs"].astype(str)
        if shared_ids is None:
            shared_ids, shared_groups, shared_organs = sample_ids, groups, organs
        elif not (
            np.array_equal(sample_ids, shared_ids)
            and np.array_equal(groups, shared_groups)
            and np.array_equal(organs, shared_organs)
        ):
            raise ValueError("seed caches do not share identical lockbox rows")
        target = cache["target_masked"]
        condition_result = {}
        study_mse[str(seed)] = {}
        study_pearson[str(seed)] = {}
        for condition in CONDITIONS:
            prediction = cache[f"prediction__{condition}"]
            mse = mse_rows(prediction, target)
            pearson = pearson_rows(prediction, target)
            mse_table = study_table(mse, groups, organs)
            pearson_table = study_table(pearson, groups, organs)
            study_mse[str(seed)][condition] = mse_table
            study_pearson[str(seed)][condition] = pearson_table
            condition_result[condition] = {
                "primary_equal_organ_study_macro_mse": macro(mse_table),
                "secondary_equal_organ_study_macro_pearson": macro(pearson_table),
                "by_organ_study_macro_mse": {
                    organ: float(np.mean(list(mse_table[organ].values())))
                    for organ in ORGANS
                },
            }
        seed_results[str(seed)] = {"conditions": condition_result}

    aggregate = {}
    repetitions = int(args.bootstrap_repetitions)
    if repetitions < 100:
        raise ValueError("bootstrap repetitions must be at least 100")
    for condition in CONDITIONS:
        aggregate[condition] = {
            "mean_across_all_prespecified_seeds": {
                "primary_equal_organ_study_macro_mse": float(
                    np.mean(
                        [
                            seed_results[str(seed)]["conditions"][condition][
                                "primary_equal_organ_study_macro_mse"
                            ]
                            for seed in SEEDS
                        ]
                    )
                ),
                "secondary_equal_organ_study_macro_pearson": float(
                    np.mean(
                        [
                            seed_results[str(seed)]["conditions"][condition][
                                "secondary_equal_organ_study_macro_pearson"
                            ]
                            for seed in SEEDS
                        ]
                    )
                ),
            },
            "vs_pooled_by_seed": {
                str(seed): bootstrap_difference(
                    study_mse[str(seed)][condition],
                    study_mse[str(seed)]["pooled"],
                    seed=int(args.bootstrap_seed) + seed * 1009,
                    repetitions=repetitions,
                )
                for seed in SEEDS
            },
        }
        aggregate[condition]["mean_mse_improvement_vs_pooled_across_all_seeds"] = float(
            np.mean(
                [
                    aggregate[condition]["vs_pooled_by_seed"][str(seed)][
                        "mse_improvement"
                    ]
                    for seed in SEEDS
                ]
            )
        )
    random_mean = float(
        np.mean(
            [
                aggregate[axis]["mean_across_all_prespecified_seeds"][
                    "primary_equal_organ_study_macro_mse"
                ]
                for axis in RANDOM_AXES
            ]
        )
    )
    report = {
        "schema_version": 1,
        "status": "complete",
        "protocol_sha256": sha256_file(protocol_path),
        "score_cache_report_sha256": sha256_file(report_path),
        "primary_estimand": "equal-organ equal-connected-study mean sample MSE",
        "inference": "paired connected-study bootstrap within organ",
        "seeds": list(SEEDS),
        "seed_aggregation": "arithmetic mean across every prespecified seed",
        "best_seed_selection_performed": False,
        "fine_tuning_performed": False,
        "seed_results": seed_results,
        "aggregate": aggregate,
        "random_control_mean_primary_mse_across_axes_and_seeds": random_mean,
        "router_diagnostics": {
            "hard_and_soft_reported": True,
            "true_organ_is_oracle_metadata_condition": True,
        },
        "donor_identity_limitation": (
            "connected study is the primary power unit; title-derived donor keys "
            "are not claimed as verified donor identity"
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, output)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--score-cache-report", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--bootstrap-seed", type=int, default=314159)
    parser.add_argument("--bootstrap-repetitions", type=int, default=10000)
    print(json.dumps(evaluate(parser.parse_args()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
