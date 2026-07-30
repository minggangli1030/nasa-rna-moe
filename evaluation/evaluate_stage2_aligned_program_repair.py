#!/usr/bin/env python3
"""Evaluate all three frozen coefficient-supervised aligned-program repairs."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.train_manifest import sha256_file  # noqa: E402
from core.train_manifest import sha256_lines  # noqa: E402
from core.train_stage2_aligned_program_repair import (  # noqa: E402
    COEFFICIENT_CONDITION,
    CONDITIONS,
    SEEDS,
)


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _load_seed(root: Path, seed: int, protocol_sha: str) -> dict[str, Any]:
    metadata_path = root / "run_metadata.json"
    scores_path = root / "calibration_scores.npz"
    if not (root / "COMPLETE").exists():
        raise ValueError(f"seed {seed} is not complete")
    metadata = json.loads(metadata_path.read_text())
    if (
        metadata.get("status") != "complete"
        or int(metadata.get("seed", -1)) != seed
        or metadata.get("mechanical_only") is not False
        or metadata.get("external_data_accessed") is not False
        or metadata.get("archs4_accessed") is not False
        or metadata.get("best_seed_selection_allowed") is not False
    ):
        raise ValueError(f"seed {seed} metadata violates the protocol")
    if metadata["hashes"]["protocol_sha256"] != protocol_sha:
        raise ValueError(f"seed {seed} protocol hash differs")
    if metadata["hashes"]["calibration_scores_sha256"] != sha256_file(scores_path):
        raise ValueError(f"seed {seed} score-cache hash differs")
    numeric_expected = {
        "sample_weights",
        "pooled_mse",
        "program_coefficients",
        *{f"{name}_mse" for name in CONDITIONS},
        "organ_labels",
        "random_labels",
    }
    complete_expected = numeric_expected | {"sample_ids", "donors", "organs"}
    with np.load(scores_path, allow_pickle=False) as archive:
        if set(archive.files) != complete_expected:
            raise ValueError(f"seed {seed} score-cache fields differ")
        # Text labels in the first completed run were emitted as NumPy object
        # arrays. Never enable pickle to read them. The evaluator reconstructs
        # those fields from the separately hash-pinned source manifest below.
        arrays = {name: archive[name] for name in numeric_expected}
    if set(arrays) != numeric_expected:
        raise ValueError(f"seed {seed} score-cache fields differ")
    if not all(np.isfinite(value).all() for value in arrays.values() if value.dtype.kind in "fc"):
        raise ValueError(f"seed {seed} score cache contains nonfinite values")
    return {"metadata": metadata, "arrays": arrays, "root": root}


def _balanced_effect(
    baseline: np.ndarray,
    candidate: np.ndarray,
    organs: np.ndarray,
    donors: np.ndarray,
) -> float:
    values = []
    for organ in sorted(set(organs)):
        selected = organs == organ
        frame = pd.DataFrame({
            "donor": donors[selected],
            "baseline": baseline[selected],
            "candidate": candidate[selected],
        }).groupby("donor", sort=True).mean()
        values.append(
            (frame["baseline"].mean() - frame["candidate"].mean())
            / frame["baseline"].mean()
        )
    return float(np.mean(values))


def _bootstrap_effect(
    baseline: np.ndarray,
    candidate: np.ndarray,
    organs: np.ndarray,
    donors: np.ndarray,
    *,
    replicates: int,
    seed: int,
) -> tuple[float, float, float]:
    strata = {}
    for organ in sorted(set(organs)):
        selected = organs == organ
        strata[organ] = (
            pd.DataFrame({
                "donor": donors[selected],
                "baseline": baseline[selected],
                "candidate": candidate[selected],
            })
            .groupby("donor", sort=True)
            .mean()
        )
    rng = np.random.default_rng(seed)
    draws = np.empty(replicates, dtype=np.float64)
    for draw in range(replicates):
        effects = []
        for frame in strata.values():
            indices = rng.integers(0, len(frame), len(frame))
            base = frame["baseline"].to_numpy()[indices].mean()
            candidate_value = frame["candidate"].to_numpy()[indices].mean()
            effects.append((base - candidate_value) / base)
        draws[draw] = np.mean(effects)
    point = _balanced_effect(baseline, candidate, organs, donors)
    low, high = np.quantile(draws, [0.025, 0.975])
    return point, float(low), float(high)


def _pearson(left: np.ndarray, right: np.ndarray) -> float:
    left = np.asarray(left, dtype=np.float64)
    right = np.asarray(right, dtype=np.float64)
    left = left - left.mean()
    right = right - right.mean()
    denominator = np.sqrt(np.square(left).sum() * np.square(right).sum())
    return float(np.dot(left, right) / denominator) if denominator > 0 else 0.0


def _donor_coefficients(
    coefficients: np.ndarray, donors: np.ndarray
) -> np.ndarray:
    frame = pd.DataFrame(coefficients)
    frame.insert(0, "donor", donors)
    return frame.groupby("donor", sort=True).mean().to_numpy()


def _effective_rank(values: np.ndarray) -> float:
    centered = values - values.mean(axis=0)
    singular = np.linalg.svd(centered.astype(np.float64), compute_uv=False)
    variance = np.square(singular)
    probability = variance / max(variance.sum(), 1e-30)
    active = probability[probability > 0]
    return float(np.exp(-np.sum(active * np.log(active))))


def _within_group(values: np.ndarray, labels: np.ndarray) -> np.ndarray:
    output = values.copy()
    for label in sorted(set(labels.astype(str))):
        selected = labels.astype(str) == label
        output[selected] -= output[selected].mean(axis=0)
    return output


def _coefficient_diagnostics(
    runs: dict[int, dict[str, Any]]
) -> dict[str, Any]:
    pairs = ((17, 42), (17, 101), (42, 101))
    donor_values = {
        seed: _donor_coefficients(
            value["arrays"]["program_coefficients"],
            value["arrays"]["donors"].astype(str),
        )
        for seed, value in runs.items()
    }
    flattened = []
    median_components = []
    component_rows = []
    for left, right in pairs:
        a, b = donor_values[left], donor_values[right]
        flattened_value = _pearson(a.ravel(), b.ravel())
        component_values = np.asarray([
            _pearson(a[:, index], b[:, index]) for index in range(a.shape[1])
        ])
        flattened.append(flattened_value)
        median_components.append(float(np.median(component_values)))
        for index, value in enumerate(component_values):
            component_rows.append({
                "seed_left": left,
                "seed_right": right,
                "component": index,
                "donor_coefficient_pearson": value,
            })
    sample_ranks = {}
    donor_ranks = {}
    within_organ_ranks = {}
    for seed, run in runs.items():
        values = run["arrays"]["program_coefficients"].astype(np.float64)
        organs = run["arrays"]["organs"].astype(str)
        sample_ranks[str(seed)] = _effective_rank(values)
        donor_ranks[str(seed)] = _effective_rank(donor_values[seed])
        within_organ_ranks[str(seed)] = _effective_rank(
            _within_group(values, organs)
        )
    return {
        "minimum_flattened_donor_coefficient_pearson": min(flattened),
        "minimum_pairwise_median_component_pearson": min(median_components),
        "minimum_sample_effective_rank": min(sample_ranks.values()),
        "minimum_donor_effective_rank": min(donor_ranks.values()),
        "minimum_within_organ_effective_rank": min(within_organ_ranks.values()),
        "pairwise_flattened_pearson": flattened,
        "pairwise_median_component_pearson": median_components,
        "sample_effective_rank_by_seed": sample_ranks,
        "donor_effective_rank_by_seed": donor_ranks,
        "within_organ_effective_rank_by_seed": within_organ_ranks,
        "component_rows": component_rows,
    }


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    protocol_path = Path(args.protocol)
    protocol_sha = sha256_file(protocol_path)
    if protocol_sha != args.expected_protocol_sha256:
        raise ValueError("aligned-program repair protocol SHA256 mismatch")
    protocol = json.loads(protocol_path.read_text())
    if protocol.get("status") != "frozen_before_repair_training":
        raise ValueError("aligned-program repair protocol is not frozen")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    roots = [Path(value) for value in args.seed_root]
    if len(roots) != 3:
        raise ValueError("exactly three seed roots are required")
    runs = {
        seed: _load_seed(root, seed, protocol_sha)
        for seed, root in zip(SEEDS, roots)
    }
    manifest_path = Path(args.manifest)
    if sha256_file(manifest_path) != protocol["inputs"]["manifest_sha256"]:
        raise ValueError("source manifest differs from frozen protocol")
    manifest = pd.read_parquet(manifest_path)
    calibration = (
        manifest.loc[manifest["split"].astype(str).eq("calibration")]
        .sort_values("sample_id")
        .reset_index(drop=True)
    )
    sample_ids = calibration["sample_id"].astype(str).to_numpy()
    donors = calibration["series_group_id"].astype(str).to_numpy()
    organs = calibration["organ"].astype(str).to_numpy()
    for seed in SEEDS:
        arrays = runs[seed]["arrays"]
        if len(arrays["pooled_mse"]) != len(calibration):
            raise ValueError(f"seed {seed} score rows differ from calibration manifest")
        if (
            runs[seed]["metadata"]["hashes"]["calibration_sample_ids_sha256"]
            != sha256_lines(sample_ids.tolist())
        ):
            raise ValueError(f"seed {seed} calibration sample order differs")
        arrays["sample_ids"] = sample_ids
        arrays["donors"] = donors
        arrays["organs"] = organs
    first = runs[SEEDS[0]]["arrays"]

    comparisons = [
        ("candidate_vs_pooled", "pooled_mse", f"{COEFFICIENT_CONDITION}_mse"),
        (
            "candidate_vs_private_phase1",
            "organ_private_phase1_mse",
            f"{COEFFICIENT_CONDITION}_mse",
        ),
        (
            "candidate_vs_private_extended",
            "organ_private_extended_mse",
            f"{COEFFICIENT_CONDITION}_mse",
        ),
        (
            "candidate_vs_random_basis",
            "random_coefficient_supervised_plus_frozen_private_mse",
            f"{COEFFICIENT_CONDITION}_mse",
        ),
        (
            "candidate_vs_generic_extended",
            "generic_capacity_extended_mse",
            f"{COEFFICIENT_CONDITION}_mse",
        ),
        (
            "private_phase1_vs_pooled",
            "pooled_mse",
            "organ_private_phase1_mse",
        ),
    ]
    bootstrap = protocol["evaluation"]["bootstrap"]
    rows = []
    for comparison_index, (name, baseline_name, candidate_name) in enumerate(comparisons):
        for seed_index, seed in enumerate(SEEDS):
            arrays = runs[seed]["arrays"]
            point, low, high = _bootstrap_effect(
                arrays[baseline_name],
                arrays[candidate_name],
                arrays["organs"].astype(str),
                arrays["donors"].astype(str),
                replicates=int(bootstrap["replicates"]),
                seed=int(bootstrap["seed"]) + comparison_index * 100 + seed_index,
            )
            rows.append({
                "comparison": name,
                "seed": seed,
                "relative_mse_reduction": point,
                "ci95_low": low,
                "ci95_high": high,
            })
    frame = pd.DataFrame(rows)
    frame.to_csv(output_dir / "performance_comparisons.csv", index=False)
    coefficient = _coefficient_diagnostics(runs)
    pd.DataFrame(coefficient.pop("component_rows")).to_csv(
        output_dir / "coefficient_reproducibility.csv", index=False
    )

    gate = protocol["success_gate"]
    organ_rows = []
    for seed in SEEDS:
        arrays = runs[seed]["arrays"]
        for organ in sorted(set(organs)):
            selected = organs == organ
            baseline = arrays["organ_private_phase1_mse"][selected]
            candidate = arrays[f"{COEFFICIENT_CONDITION}_mse"][selected]
            organ_donors = donors[selected]
            organ_rows.append({
                "seed": seed,
                "organ": organ,
                "relative_mse_reduction_vs_private_phase1": _balanced_effect(
                    baseline,
                    candidate,
                    np.repeat(organ, len(baseline)),
                    organ_donors,
                ),
            })
    organ_frame = pd.DataFrame(organ_rows)
    organ_frame.to_csv(output_dir / "per_organ_safety.csv", index=False)

    candidate_pooled = frame.loc[frame["comparison"].eq("candidate_vs_pooled")]
    candidate_phase1 = frame.loc[
        frame["comparison"].eq("candidate_vs_private_phase1")
    ]
    candidate_extended = frame.loc[
        frame["comparison"].eq("candidate_vs_private_extended")
    ]
    candidate_random = frame.loc[
        frame["comparison"].eq("candidate_vs_random_basis")
    ]
    candidate_generic = frame.loc[
        frame["comparison"].eq("candidate_vs_generic_extended")
    ]
    private_pooled = frame.loc[frame["comparison"].eq("private_phase1_vs_pooled")]
    preservation_fraction = float(
        candidate_pooled["relative_mse_reduction"].mean()
        / max(private_pooled["relative_mse_reduction"].mean(), 1e-12)
    )
    gates = {
        "positive_vs_pooled_all_seeds": bool(
            (candidate_pooled["relative_mse_reduction"] > 0).all()
        ),
        "minimum_private_gain_preserved": bool(
            preservation_fraction >= float(gate["minimum_private_gain_fraction_preserved"])
        ),
        "beats_private_phase1_all_seed_intervals": bool(
            (candidate_phase1["ci95_low"] > 0).all()
        ),
        "beats_extended_private_all_seed_intervals": bool(
            (candidate_extended["ci95_low"] > 0).all()
        ),
        "beats_random_basis_all_seed_intervals": bool(
            (candidate_random["ci95_low"] > 0).all()
        ),
        "beats_extended_generic_all_seed_intervals": bool(
            (candidate_generic["ci95_low"] > 0).all()
        ),
        "per_organ_safety": bool(
            organ_frame["relative_mse_reduction_vs_private_phase1"].min()
            >= -float(gate["maximum_per_organ_harm_fraction"])
        ),
        "coefficient_flattened_reproducibility": bool(
            coefficient["minimum_flattened_donor_coefficient_pearson"]
            >= float(gate["minimum_flattened_donor_coefficient_pearson"])
        ),
        "coefficient_component_reproducibility": bool(
            coefficient["minimum_pairwise_median_component_pearson"]
            >= float(gate["minimum_pairwise_median_component_pearson"])
        ),
        "coefficient_sample_noncollapse": bool(
            coefficient["minimum_sample_effective_rank"]
            >= float(gate["minimum_sample_effective_rank"])
        ),
        "coefficient_donor_noncollapse": bool(
            coefficient["minimum_donor_effective_rank"]
            >= float(gate["minimum_donor_effective_rank"])
        ),
        "coefficient_within_organ_noncollapse": bool(
            coefficient["minimum_within_organ_effective_rank"]
            >= float(gate["minimum_within_organ_effective_rank"])
        ),
    }
    performance_keys = (
        "positive_vs_pooled_all_seeds",
        "minimum_private_gain_preserved",
        "beats_private_phase1_all_seed_intervals",
        "beats_extended_private_all_seed_intervals",
        "beats_random_basis_all_seed_intervals",
        "beats_extended_generic_all_seed_intervals",
        "per_organ_safety",
    )
    alignment_keys = (
        "coefficient_flattened_reproducibility",
        "coefficient_component_reproducibility",
        "coefficient_sample_noncollapse",
        "coefficient_donor_noncollapse",
        "coefficient_within_organ_noncollapse",
    )
    if all(gates.values()):
        decision = "coefficient_supervision_repair_pass_utility_alignment_and_safety"
    elif all(gates[key] for key in performance_keys):
        decision = "repair_utility_pass_alignment_fail_pivot_representation"
    elif all(gates[key] for key in alignment_keys):
        decision = "repair_alignment_pass_utility_or_safety_fail_do_not_advance"
    else:
        decision = "coefficient_supervision_repair_fail_pivot_representation"
    report = {
        "schema_version": 2,
        "status": "complete",
        "research_stage": "stage2_aligned_program_coefficient_supervision_repair_evaluation",
        "development_only": True,
        "external_data_accessed": False,
        "archs4_accessed": False,
        "best_seed_selection_allowed": False,
        "seeds": list(SEEDS),
        "decision": decision,
        "private_gain_preservation_fraction": preservation_fraction,
        "gates": gates,
        "coefficient_diagnostics": coefficient,
        "hashes": {
            "protocol_sha256": protocol_sha,
            "performance_comparisons_sha256": sha256_file(
                output_dir / "performance_comparisons.csv"
            ),
            "coefficient_reproducibility_sha256": sha256_file(
                output_dir / "coefficient_reproducibility.csv"
            ),
            "per_organ_safety_sha256": sha256_file(
                output_dir / "per_organ_safety.csv"
            ),
            "seed_score_sha256": {
                str(seed): runs[seed]["metadata"]["hashes"]["calibration_scores_sha256"]
                for seed in SEEDS
            },
        },
        "claim_boundary": protocol["claim_boundary"],
    }
    _atomic_json(output_dir / "evaluation_report.json", report)
    with (output_dir / "IMMUTABLE_SHA256SUMS").open("w") as handle:
        for path in sorted(output_dir.iterdir()):
            if path.name == "IMMUTABLE_SHA256SUMS":
                continue
            handle.write(f"{sha256_file(path)}  {path.name}\n")
    (output_dir / "COMPLETE").touch()
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--seed-root", action="append", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser


def main() -> None:
    report = evaluate(build_parser().parse_args())
    print(json.dumps({
        "status": report["status"],
        "decision": report["decision"],
        "gates": report["gates"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
