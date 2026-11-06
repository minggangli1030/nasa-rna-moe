#!/usr/bin/env python3
"""Evaluate the frozen Stage 2 recipient-exposure-preserving additive subset.

For eight prospectively frozen recipient→donor edges, compare A1500+B750 with
A1500, A2250, and three A1500+random750 controls on held-out recipient GTEx
donors. All three prespecified seeds are retained.
"""

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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from train_manifest import sha256_file  # noqa: E402
from evaluation.evaluate_stage2_directed_transfer import (  # noqa: E402
    ORGANS,
    RANDOM_AXES,
    SEEDS,
    _bootstrap_interval,
    _load_score_cache,
    _paired_donor_arrays,
    _parse_seed_roots,
    _relative_reduction_percent,
)


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _validate_seed_root(
    root: Path,
    *,
    seed: int,
    expected_schedule_hash: str,
    expected_definitions_hash: str | None,
    expected_arm_ids: set[str] | None,
    expected_completed_arms: int,
) -> str:
    metadata_path = root / "run_metadata.json"
    metadata = json.loads(metadata_path.read_text())
    if (
        metadata.get("status") != "complete"
        or metadata.get("mechanical_only") is not False
        or metadata.get("training_seed") != seed
        or metadata.get("best_seed_selection_allowed") is not False
    ):
        raise ValueError(f"seed {seed} training root is incomplete or invalid")
    hashes = metadata.get("hashes", {})
    if hashes.get("training_schedules_sha256") != expected_schedule_hash:
        raise ValueError(f"seed {seed} schedule hash differs from evaluator")
    if (
        expected_definitions_hash is not None
        and hashes.get("arm_definitions_sha256") != expected_definitions_hash
    ):
        raise ValueError(f"seed {seed} definitions hash differs from evaluator")
    completed_ids = {str(value["arm_id"]) for value in metadata.get("arms", [])}
    if expected_arm_ids is not None and completed_ids != expected_arm_ids:
        raise ValueError(f"seed {seed} completed arm set differs from definition")
    if (
        metadata.get("completed_arms") != len(completed_ids)
        or len(completed_ids) != expected_completed_arms
    ):
        raise ValueError(f"seed {seed} completed-arm count is inconsistent")
    return sha256_file(metadata_path)


def _render_additive_plot(frame: pd.DataFrame, output_path: Path) -> None:
    import matplotlib.pyplot as plt

    labels = [
        f"{row.recipient.replace('_', ' ')} ← {row.donor.replace('_', ' ')}"
        for row in frame.itertuples()
    ]
    y = np.arange(len(frame))
    values = frame["mean_effect_vs_a1500_percent"].to_numpy()
    low = frame["donor_ci_low_vs_a1500_percent"].to_numpy()
    high = frame["donor_ci_high_vs_a1500_percent"].to_numpy()
    errors = np.vstack([values - low, high - values])
    colors = np.where(values >= 0, "#28714b", "#a44e48")
    figure, axis = plt.subplots(figsize=(10.5, 6.5))
    axis.barh(y, values, color=colors, alpha=0.9)
    axis.errorbar(
        values,
        y,
        xerr=errors,
        fmt="none",
        ecolor="#17201d",
        elinewidth=1.2,
        capsize=3,
    )
    axis.axvline(0, color="#17201d", linewidth=1)
    axis.set_yticks(y, labels)
    axis.invert_yaxis()
    axis.set_xlabel("A1500+B750 improvement versus A1500 (%)")
    axis.set_title(
        "Frozen additive organ-transfer subset\n"
        "mean across seeds with paired donor-bootstrap 95% interval"
    )
    for index, row in enumerate(frame.itertuples()):
        axis.text(
            values[index],
            index,
            f"  {values[index]:+.2f}% · {row.positive_seed_count}/3+",
            va="center",
            ha="left" if values[index] >= 0 else "right",
            fontsize=9,
        )
    figure.tight_layout()
    figure.savefig(output_path, dpi=180)
    plt.close(figure)


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output_dir}")

    substitution_roots = _parse_seed_roots(args.substitution_seed_root)
    additive_roots = _parse_seed_roots(args.additive_seed_root)
    expected_substitution_schedule = str(
        args.expected_substitution_schedule_sha256
    ).lower()
    expected_additive_schedule = str(args.expected_additive_schedule_sha256).lower()
    expected_additive_definitions = str(
        args.expected_additive_definitions_sha256
    ).lower()

    definitions_path = Path(args.additive_arm_definitions)
    freeze_path = Path(args.edge_freeze)
    if sha256_file(definitions_path) != expected_additive_definitions:
        raise ValueError("additive arm definitions differ from expected SHA256")
    if sha256_file(freeze_path) != str(args.expected_edge_freeze_sha256).lower():
        raise ValueError("additive edge freeze differs from expected SHA256")
    definitions = json.loads(definitions_path.read_text())
    expected_additive_arms = {
        str(value["arm_id"]) for value in definitions.get("arms", [])
    }
    if len(expected_additive_arms) != 40 or not all(
        value.startswith("add__") for value in expected_additive_arms
    ):
        raise ValueError("additive evaluator requires exactly 40 additive arms")

    freeze = json.loads(freeze_path.read_text())
    if (
        freeze.get("status") != "frozen_before_directed_transfer_outcomes"
        or freeze.get("transfer_training_started_before_freeze") is not False
        or freeze.get("transfer_score_cache_accessed_before_freeze") is not False
        or freeze.get("best_seed_selection_allowed") is not False
    ):
        raise ValueError("additive edge freeze violates the development firewall")
    edges = [
        {
            "recipient": str(value["recipient"]),
            "donor": str(value["donor"]),
            "stratum": str(value["stratum"]),
            "similarity": float(value["frozen_expert_utility_cosine_similarity"]),
        }
        for value in freeze.get("edges", [])
    ]
    if (
        len(edges) != len(ORGANS)
        or {value["recipient"] for value in edges} != set(ORGANS)
        or any(value["recipient"] == value["donor"] for value in edges)
    ):
        raise ValueError("additive edge freeze must cover each recipient exactly once")

    run_hashes: dict[str, dict[str, str]] = {"substitution": {}, "additive": {}}
    for seed in SEEDS:
        run_hashes["substitution"][str(seed)] = _validate_seed_root(
            substitution_roots[seed],
            seed=seed,
            expected_schedule_hash=expected_substitution_schedule,
            expected_definitions_hash=None,
            expected_arm_ids=None,
            expected_completed_arms=60,
        )
        run_hashes["additive"][str(seed)] = _validate_seed_root(
            additive_roots[seed],
            seed=seed,
            expected_schedule_hash=expected_additive_schedule,
            expected_definitions_hash=expected_additive_definitions,
            expected_arm_ids=expected_additive_arms,
            expected_completed_arms=40,
        )

    per_seed_rows: list[dict[str, Any]] = []
    edge_rows: list[dict[str, Any]] = []
    for edge_index, edge in enumerate(edges):
        recipient = edge["recipient"]
        donor = edge["donor"]
        baselines = []
        candidates = []
        named_effects = []
        self_effects = []
        beats_all_random = []
        donor_order = None
        for seed in SEEDS:
            substitution_root = substitution_roots[seed]
            additive_root = additive_roots[seed]
            baseline = _load_score_cache(
                substitution_root,
                f"sub__{recipient}__recipient_only",
                recipient,
            )
            named = _load_score_cache(
                additive_root, f"add__{recipient}__{donor}", recipient
            )
            self_control = _load_score_cache(
                additive_root, f"add__{recipient}__self_control", recipient
            )
            baseline_donor, named_donor, donors = _paired_donor_arrays(
                baseline, named
            )
            self_donor, named_from_self, self_donors = _paired_donor_arrays(
                self_control, named
            )
            if donors != self_donors:
                raise ValueError("additive comparison donor orders differ")
            if donor_order is None:
                donor_order = donors
            elif donor_order != donors:
                raise ValueError("held-out donor order differs across seeds")
            random_effects = []
            for axis in RANDOM_AXES:
                random_control = _load_score_cache(
                    additive_root,
                    f"add__{recipient}__random__{axis}",
                    recipient,
                )
                random_donor, named_from_random, random_donors = _paired_donor_arrays(
                    random_control, named
                )
                if donors != random_donors:
                    raise ValueError("random comparison donor orders differ")
                random_effects.append(
                    _relative_reduction_percent(
                        random_donor, named_from_random
                    )
                )
            effect_vs_a1500 = _relative_reduction_percent(
                baseline_donor, named_donor
            )
            effect_vs_a2250 = _relative_reduction_percent(
                self_donor, named_from_self
            )
            baselines.append(baseline_donor)
            candidates.append(named_donor)
            named_effects.append(effect_vs_a1500)
            self_effects.append(effect_vs_a2250)
            beats_all_random.append(min(random_effects) > 0)
            per_seed_rows.append(
                {
                    "recipient": recipient,
                    "donor": donor,
                    "stratum": edge["stratum"],
                    "seed": seed,
                    "effect_vs_a1500_percent": effect_vs_a1500,
                    "effect_vs_a2250_percent": effect_vs_a2250,
                    "positive_vs_a1500": effect_vs_a1500 > 0,
                    "positive_vs_a2250": effect_vs_a2250 > 0,
                    "beats_all_random_controls": min(random_effects) > 0,
                    "random_comparison_effects_percent": random_effects,
                    "held_out_donors": len(donors),
                }
            )
        baseline_array = np.stack(baselines)
        candidate_array = np.stack(candidates)
        point = _relative_reduction_percent(
            baseline_array.reshape(-1), candidate_array.reshape(-1)
        )
        low, high = _bootstrap_interval(
            baseline_array,
            candidate_array,
            draws=int(args.bootstrap_draws),
            seed=int(args.bootstrap_seed) + edge_index,
        )
        edge_rows.append(
            {
                "recipient": recipient,
                "donor": donor,
                "stratum": edge["stratum"],
                "frozen_expert_utility_cosine_similarity": edge["similarity"],
                "mean_effect_vs_a1500_percent": point,
                "positive_seed_count": int(np.sum(np.asarray(named_effects) > 0)),
                "donor_ci_low_vs_a1500_percent": low,
                "donor_ci_high_vs_a1500_percent": high,
                "mean_effect_vs_a2250_percent": float(np.mean(self_effects)),
                "positive_vs_a2250_seed_count": int(
                    np.sum(np.asarray(self_effects) > 0)
                ),
                "beats_all_random_seed_count": int(sum(beats_all_random)),
            }
        )

    edge_frame = pd.DataFrame(edge_rows)
    per_seed_frame = pd.DataFrame(per_seed_rows)
    edge_path = output_dir / "additive_edges.csv"
    per_seed_path = output_dir / "additive_per_seed.csv"
    plot_path = output_dir / "additive_effects.png"
    edge_frame.to_csv(edge_path, index=False)
    per_seed_frame.to_csv(per_seed_path, index=False)
    if not bool(args.no_plot):
        _render_additive_plot(edge_frame, plot_path)

    report = {
        "schema_version": 1,
        "status": "complete",
        "research_stage": "stage2_additive_organ_transfer_development",
        "development_only": True,
        "study_disjoint": False,
        "held_out_unit": "GTEx donor",
        "best_seed_selection_allowed": False,
        "seeds": list(SEEDS),
        "primary_estimand": "A1500+B750 versus A1500 donor-balanced recipient MSE",
        "controls": [
            "A2250",
            "A1500+random_k8_p17_750",
            "A1500+random_k8_p42_750",
            "A1500+random_k8_p101_750",
        ],
        "effect_sign": "positive is helpful additive transfer",
        "bootstrap": {
            "unit": "held-out GTEx donor paired across arms and seeds",
            "draws": int(args.bootstrap_draws),
            "seed": int(args.bootstrap_seed),
        },
        "summary": {
            "frozen_edges": len(edge_frame),
            "positive_all_seed_and_ci_edges": int(
                (
                    edge_frame["positive_seed_count"].eq(len(SEEDS))
                    & edge_frame["donor_ci_low_vs_a1500_percent"].gt(0)
                ).sum()
            ),
            "negative_all_seed_and_ci_edges": int(
                (
                    edge_frame["positive_seed_count"].eq(0)
                    & edge_frame["donor_ci_high_vs_a1500_percent"].lt(0)
                ).sum()
            ),
            "beats_a2250_all_seed_edges": int(
                edge_frame["positive_vs_a2250_seed_count"].eq(len(SEEDS)).sum()
            ),
            "beats_all_random_all_seed_edges": int(
                edge_frame["beats_all_random_seed_count"].eq(len(SEEDS)).sum()
            ),
        },
        "universality_boundary": (
            "Seed-sign agreement and donor-bootstrap stability do not establish "
            "independent-study universality; a new untouched multisource cohort is required."
        ),
        "hashes": {
            "edge_freeze_sha256": sha256_file(freeze_path),
            "additive_arm_definitions_sha256": expected_additive_definitions,
            "additive_training_schedule_sha256": expected_additive_schedule,
            "substitution_training_schedule_sha256": expected_substitution_schedule,
            "seed_run_metadata_sha256": run_hashes,
            "edge_table_sha256": sha256_file(edge_path),
            "per_seed_table_sha256": sha256_file(per_seed_path),
        },
    }
    if not bool(args.no_plot):
        report["hashes"]["plot_sha256"] = sha256_file(plot_path)
    _atomic_json(output_dir / "evaluation_report.json", report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--substitution-seed-root", action="append", required=True)
    parser.add_argument("--additive-seed-root", action="append", required=True)
    parser.add_argument("--additive-arm-definitions", required=True)
    parser.add_argument("--edge-freeze", required=True)
    parser.add_argument("--expected-substitution-schedule-sha256", required=True)
    parser.add_argument("--expected-additive-schedule-sha256", required=True)
    parser.add_argument("--expected-additive-definitions-sha256", required=True)
    parser.add_argument("--expected-edge-freeze-sha256", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--bootstrap-draws", type=int, default=10000)
    parser.add_argument("--bootstrap-seed", type=int, default=20260728)
    parser.add_argument("--no-plot", action="store_true")
    return parser


def main() -> None:
    result = evaluate(build_parser().parse_args())
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
