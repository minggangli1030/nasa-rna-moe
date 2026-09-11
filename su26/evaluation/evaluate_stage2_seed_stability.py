#!/usr/bin/env python3
"""Evaluate the frozen 3x3 Stage 2 seed-factorization diagnosis."""

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
CORE_DIR = ROOT / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from train_manifest import sha256_file  # noqa: E402
from evaluation.evaluate_stage2_directed_transfer import (  # noqa: E402
    _load_score_cache,
    _paired_donor_arrays,
    _relative_reduction_percent,
)


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _parse_combo_roots(
    values: list[str], expected: set[tuple[int, int]]
) -> dict[tuple[int, int], Path]:
    roots: dict[tuple[int, int], Path] = {}
    for raw in values:
        if "=" not in raw or ":" not in raw.split("=", 1)[0]:
            raise ValueError("combo roots must use TRUNK_SEED:OPT_SEED=PATH")
        combo_raw, path_raw = raw.split("=", 1)
        trunk_raw, opt_raw = combo_raw.split(":", 1)
        combo = (int(trunk_raw), int(opt_raw))
        if combo in roots:
            raise ValueError(f"repeated combo root {combo}")
        roots[combo] = Path(path_raw)
    if set(roots) != expected:
        raise ValueError("combo roots differ from the frozen crossed design")
    return roots


def _factor_bootstrap(
    baseline: np.ndarray,
    candidate: np.ndarray,
    *,
    draws: int,
    seed: int,
) -> tuple[float, float]:
    if baseline.shape != candidate.shape or baseline.ndim != 3:
        raise ValueError("factor bootstrap arrays must align as trunk x opt x donor")
    rng = np.random.default_rng(seed)
    trunk_count, opt_count, donor_count = baseline.shape
    values = np.empty(draws, dtype=np.float64)
    for draw in range(draws):
        trunks = rng.integers(0, trunk_count, size=trunk_count)
        opts = rng.integers(0, opt_count, size=opt_count)
        donors = rng.integers(0, donor_count, size=donor_count)
        selected_baseline = baseline[np.ix_(trunks, opts, donors)]
        selected_candidate = candidate[np.ix_(trunks, opts, donors)]
        values[draw] = _relative_reduction_percent(
            selected_baseline.reshape(-1), selected_candidate.reshape(-1)
        )
    low, high = np.quantile(values, [0.025, 0.975])
    return float(low), float(high)


def _variance_fractions(values: np.ndarray) -> dict[str, float]:
    if values.ndim != 2:
        raise ValueError("factor effects must be trunk x optimization")
    grand = float(values.mean())
    trunk_effect = values.mean(axis=1) - grand
    opt_effect = values.mean(axis=0) - grand
    residual = values - grand - trunk_effect[:, None] - opt_effect[None, :]
    total = float(np.square(values - grand).sum())
    if total == 0:
        return {
            "trunk": 0.0,
            "optimization": 0.0,
            "interaction_and_unresolved": 0.0,
        }
    return {
        "trunk": float(values.shape[1] * np.square(trunk_effect).sum() / total),
        "optimization": float(values.shape[0] * np.square(opt_effect).sum() / total),
        "interaction_and_unresolved": float(np.square(residual).sum() / total),
    }


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output_dir}")

    protocol_path = Path(args.protocol)
    if sha256_file(protocol_path) != str(args.expected_protocol_sha256).lower():
        raise ValueError("stability protocol differs from expected SHA256")
    protocol = json.loads(protocol_path.read_text())
    if (
        protocol.get("status") != "frozen_before_stability_outcomes"
        or protocol.get("best_seed_selection_allowed") is not False
        or protocol.get("diagnostic_training_started_before_freeze") is not False
        or protocol.get("diagnostic_outcomes_accessed_before_freeze") is not False
    ):
        raise ValueError("stability protocol violates the development firewall")

    trunks = tuple(int(value) for value in protocol["factor_design"]["trunk_seeds"])
    opts = tuple(
        int(value) for value in protocol["factor_design"]["optimization_seeds"]
    )
    expected_combos = {(trunk, opt) for trunk in trunks for opt in opts}
    roots = _parse_combo_roots(args.combo_root, expected_combos)
    expected_schedule = str(args.expected_schedule_sha256).lower()
    expected_definitions = str(args.expected_definitions_sha256).lower()
    expected_arms = {
        str(value["arm_id"])
        for value in json.loads(Path(args.arm_definitions).read_text())["arms"]
    }
    if len(expected_arms) != 24 or not all(
        value.startswith("diag__") for value in expected_arms
    ):
        raise ValueError("stability diagnosis requires exactly 24 diagnostic arms")

    run_hashes: dict[str, str] = {}
    for combo, root in roots.items():
        metadata_path = root / "run_metadata.json"
        metadata = json.loads(metadata_path.read_text())
        trunk, opt = combo
        completed = {str(value["arm_id"]) for value in metadata.get("arms", [])}
        if (
            metadata.get("status") != "complete"
            or metadata.get("mechanical_only") is not False
            or metadata.get("best_seed_selection_allowed") is not False
            or metadata.get("trunk_seed") != trunk
            or metadata.get("optimization_seed") != opt
            or metadata.get("mask_seed") != opt
            or metadata.get("loader_seed") != opt
            or metadata.get("config", {}).get("use_amp") is not False
            or completed != expected_arms
            or metadata.get("completed_arms") != 24
        ):
            raise ValueError(f"diagnostic combo {combo} is incomplete or invalid")
        hashes = metadata.get("hashes", {})
        if (
            hashes.get("training_schedules_sha256") != expected_schedule
            or hashes.get("arm_definitions_sha256") != expected_definitions
        ):
            raise ValueError(f"diagnostic combo {combo} hash contract differs")
        run_hashes[f"{trunk}:{opt}"] = sha256_file(metadata_path)

    gates = protocol["decision_gates"]
    minimum_effect = float(gates["minimum_absolute_effect_percent"])
    required_positive = int(gates["required_positive_combos"])
    required_stable_edges = int(gates["reproducible_map_required_stable_edges"])
    required_helpful_edges = int(gates["raw_addition_required_helpful_edges"])
    bootstrap_draws = int(protocol["bootstrap"]["draws"])
    bootstrap_seed = int(protocol["bootstrap"]["seed"])

    combo_rows: list[dict[str, Any]] = []
    edge_rows: list[dict[str, Any]] = []
    for edge_index, edge in enumerate(protocol["edges"]):
        recipient = str(edge["recipient"])
        donor = str(edge["donor"])
        baseline_grid: list[list[np.ndarray]] = []
        candidate_grid: list[list[np.ndarray]] = []
        effect_grid = np.empty((len(trunks), len(opts)), dtype=np.float64)
        self_effect_grid = np.empty_like(effect_grid)
        donor_order: list[str] | None = None
        for trunk_index, trunk in enumerate(trunks):
            baseline_row = []
            candidate_row = []
            for opt_index, opt in enumerate(opts):
                root = roots[(trunk, opt)]
                baseline = _load_score_cache(
                    root, f"diag__{recipient}__recipient_only", recipient
                )
                candidate = _load_score_cache(
                    root, f"diag__{recipient}__{donor}", recipient
                )
                self_control = _load_score_cache(
                    root, f"diag__{recipient}__self_control", recipient
                )
                baseline_donor, candidate_donor, donors = _paired_donor_arrays(
                    baseline, candidate
                )
                self_donor, candidate_from_self, self_donors = _paired_donor_arrays(
                    self_control, candidate
                )
                if donors != self_donors:
                    raise ValueError("recipient and self-control donor order differs")
                if donor_order is None:
                    donor_order = donors
                elif donor_order != donors:
                    raise ValueError("held-out donor order differs across combos")
                effect = _relative_reduction_percent(
                    baseline_donor, candidate_donor
                )
                self_effect = _relative_reduction_percent(
                    self_donor, candidate_from_self
                )
                effect_grid[trunk_index, opt_index] = effect
                self_effect_grid[trunk_index, opt_index] = self_effect
                baseline_row.append(baseline_donor)
                candidate_row.append(candidate_donor)
                combo_rows.append(
                    {
                        "recipient": recipient,
                        "donor": donor,
                        "trunk_seed": trunk,
                        "optimization_seed": opt,
                        "effect_vs_a1500_percent": effect,
                        "effect_vs_a2250_percent": self_effect,
                        "positive_vs_a1500": effect > 0,
                        "positive_vs_a2250": self_effect > 0,
                        "held_out_donors": len(donors),
                    }
                )
            baseline_grid.append(baseline_row)
            candidate_grid.append(candidate_row)
        baseline_array = np.asarray(baseline_grid)
        candidate_array = np.asarray(candidate_grid)
        point = _relative_reduction_percent(
            baseline_array.reshape(-1), candidate_array.reshape(-1)
        )
        low, high = _factor_bootstrap(
            baseline_array,
            candidate_array,
            draws=bootstrap_draws,
            seed=bootstrap_seed + edge_index,
        )
        combo_positive = int(np.count_nonzero(effect_grid > 0))
        trunk_means = effect_grid.mean(axis=1)
        opt_means = effect_grid.mean(axis=0)
        helpful = (
            combo_positive >= required_positive
            and bool(np.all(trunk_means > 0))
            and bool(np.all(opt_means > 0))
            and low > 0
            and point >= minimum_effect
        )
        harmful = (
            combo_positive <= len(expected_combos) - required_positive
            and bool(np.all(trunk_means < 0))
            and bool(np.all(opt_means < 0))
            and high < 0
            and point <= -minimum_effect
        )
        classification = (
            "stable_helpful"
            if helpful
            else "stable_harmful"
            if harmful
            else "unstable_or_negligible"
        )
        edge_rows.append(
            {
                "recipient": recipient,
                "donor": donor,
                "mean_effect_vs_a1500_percent": point,
                "factor_bootstrap_ci_low_percent": low,
                "factor_bootstrap_ci_high_percent": high,
                "positive_combo_count": combo_positive,
                "positive_trunk_mean_count": int(np.count_nonzero(trunk_means > 0)),
                "positive_optimization_mean_count": int(
                    np.count_nonzero(opt_means > 0)
                ),
                "mean_effect_vs_a2250_percent": float(self_effect_grid.mean()),
                "positive_vs_a2250_combo_count": int(
                    np.count_nonzero(self_effect_grid > 0)
                ),
                "combo_effect_sd_percent": float(effect_grid.std(ddof=1)),
                "classification": classification,
                **{
                    f"variance_fraction_{key}": value
                    for key, value in _variance_fractions(effect_grid).items()
                },
            }
        )

    combo_frame = pd.DataFrame(combo_rows)
    edge_frame = pd.DataFrame(edge_rows)
    combo_path = output_dir / "combo_effects.csv"
    edge_path = output_dir / "stability_edges.csv"
    combo_frame.to_csv(combo_path, index=False)
    edge_frame.to_csv(edge_path, index=False)

    stable_helpful = int(edge_frame["classification"].eq("stable_helpful").sum())
    stable_harmful = int(edge_frame["classification"].eq("stable_harmful").sum())
    stable_total = stable_helpful + stable_harmful
    if stable_helpful >= required_helpful_edges:
        decision = "raw_addition_has_actionable_reproducible_helpful_structure"
    elif stable_total >= required_stable_edges:
        decision = "pivot_raw_addition_toward_negative_transfer_or_selective_sharing"
    else:
        decision = "optimization_instability_confirmed_test_robust_sharing_then_pivot"

    report = {
        "schema_version": 1,
        "status": "complete",
        "research_stage": "stage2_seed_factorized_stability_diagnosis",
        "development_only": True,
        "study_disjoint": False,
        "best_seed_selection_allowed": False,
        "factor_design": {
            "trunk_seeds": list(trunks),
            "optimization_seeds": list(opts),
            "mask_seed_equals_optimization_seed": True,
            "loader_seed_equals_optimization_seed": True,
            "combos": len(expected_combos),
        },
        "summary": {
            "edges": len(edge_frame),
            "stable_helpful_edges": stable_helpful,
            "stable_harmful_edges": stable_harmful,
            "unstable_or_negligible_edges": int(len(edge_frame) - stable_total),
            "decision": decision,
        },
        "decision_gates": gates,
        "bootstrap": protocol["bootstrap"],
        "universality_boundary": (
            "This diagnosis separates frozen-trunk and optimization stability on "
            "donor-disjoint GTEx development data; it does not establish study "
            "universality."
        ),
        "hashes": {
            "protocol_sha256": sha256_file(protocol_path),
            "training_schedules_sha256": expected_schedule,
            "arm_definitions_sha256": expected_definitions,
            "combo_run_metadata_sha256": run_hashes,
            "combo_table_sha256": sha256_file(combo_path),
            "edge_table_sha256": sha256_file(edge_path),
        },
    }
    _atomic_json(output_dir / "evaluation_report.json", report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--combo-root", action="append", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--arm-definitions", required=True)
    parser.add_argument("--expected-schedule-sha256", required=True)
    parser.add_argument("--expected-definitions-sha256", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser


def main() -> None:
    result = evaluate(build_parser().parse_args())
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
