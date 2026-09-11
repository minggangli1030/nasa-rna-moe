#!/usr/bin/env python3
"""Evaluate the frozen Stage 2 directed organ-transfer development matrix.

The primary cell compares recipient-A donor-balanced calibration MSE from the
A750+B750 adapter with the A1500 recipient-only adapter. All three seeds are
retained. Uncertainty resamples held-out GTEx donors; it is not a study bootstrap.
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
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from train_manifest import sha256_file  # noqa: E402


ORGANS = (
    "adipose",
    "brain",
    "colon",
    "heart",
    "liver",
    "lung",
    "skeletal_muscle",
    "skin",
)
SEEDS = (17, 42, 101)
RANDOM_AXES = ("random_k8_p17", "random_k8_p42", "random_k8_p101")
# Recipient-only and pair-arm score caches batch the same frozen pooled trunk
# differently. Across all 38,346 frozen comparisons the observed maxima were
# 2.3842e-7 absolute and 2.4033e-7 relative; these bounds admit only that
# float32-scale variation while still failing closed on material divergence.
POOLED_SCORE_RTOL = 5e-7
POOLED_SCORE_ATOL = 3e-7


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _parse_seed_roots(values: list[str]) -> dict[int, Path]:
    output: dict[int, Path] = {}
    for raw in values:
        if "=" not in raw:
            raise ValueError("seed roots must use SEED=PATH")
        seed_raw, path_raw = raw.split("=", 1)
        seed = int(seed_raw)
        if seed not in SEEDS:
            raise ValueError(f"unexpected seed {seed}")
        if seed in output:
            raise ValueError(f"repeated seed root {seed}")
        output[seed] = Path(path_raw)
    if set(output) != set(SEEDS):
        raise ValueError(f"seed roots must cover exactly {SEEDS}")
    return output


def _pair_arm(recipient: str, donor: str) -> str:
    left, right = sorted((recipient, donor), key=ORGANS.index)
    return f"sub__{left}__{right}"


def _load_score_cache(
    seed_root: Path,
    arm_id: str,
    recipient: str,
) -> pd.DataFrame:
    arm_root = seed_root / "arms" / arm_id
    metadata_path = arm_root / "run_metadata.json"
    scores_path = arm_root / "calibration_scores.npz"
    metadata = json.loads(metadata_path.read_text())
    if (
        metadata.get("status") != "complete"
        or metadata.get("mechanical_only") is not False
        or recipient not in metadata.get("evaluation_recipients", [])
    ):
        raise ValueError(f"arm {arm_id!r} is incomplete, mechanical, or misrouted")
    if sha256_file(scores_path) != metadata["hashes"]["score_cache_sha256"]:
        raise ValueError(f"arm {arm_id!r} score cache differs from metadata")
    # The frozen producer used pandas ``astype(str).to_numpy()``, which emits
    # object-backed string arrays even though every value is a plain string.
    # These files are trusted only after the exact producer-recorded SHA256 above
    # passes. Keep the load narrow and reject any object entry that is not a string.
    with np.load(scores_path, allow_pickle=True) as archive:
        required = {
            "sample_ids",
            "donor_ids",
            "groups",
            "organs",
            "pooled_mse",
            "adapter_mse",
        }
        if set(archive.files) != required:
            raise ValueError(f"arm {arm_id!r} score cache schema is invalid")
        strings = {}
        for key in ("sample_ids", "donor_ids", "groups", "organs"):
            values = archive[key]
            if values.ndim != 1 or values.dtype.kind not in {"O", "U", "S"}:
                raise ValueError(f"arm {arm_id!r} has invalid {key} dtype or shape")
            if values.dtype.kind == "O":
                items = values.tolist()
                if not all(type(value) is str for value in items):
                    raise ValueError(
                        f"arm {arm_id!r} has non-string objects in {key}"
                    )
                strings[key] = np.asarray(items, dtype=str)
            else:
                strings[key] = values.astype(str)
        frame = pd.DataFrame(
            {
                "sample_id": strings["sample_ids"],
                "donor_id": strings["donor_ids"],
                "group": strings["groups"],
                "organ": strings["organs"],
                "pooled_mse": archive["pooled_mse"].astype(np.float64),
                "adapter_mse": archive["adapter_mse"].astype(np.float64),
            }
        )
    frame = frame.loc[frame["organ"].eq(recipient)].copy()
    if frame.empty or frame["sample_id"].duplicated().any():
        raise ValueError(f"arm {arm_id!r} lacks unique recipient rows")
    if not np.isfinite(frame[["pooled_mse", "adapter_mse"]]).all().all():
        raise ValueError(f"arm {arm_id!r} contains non-finite MSE")
    return frame.sort_values("sample_id", kind="stable").reset_index(drop=True)


def _paired_donor_arrays(
    baseline: pd.DataFrame,
    candidate: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    if baseline["sample_id"].tolist() != candidate["sample_id"].tolist():
        raise ValueError("baseline and candidate sample IDs differ")
    for column in ("donor_id", "group", "organ"):
        if baseline[column].tolist() != candidate[column].tolist():
            raise ValueError(f"baseline and candidate {column} values differ")
    if not np.allclose(
        baseline["pooled_mse"].to_numpy(),
        candidate["pooled_mse"].to_numpy(),
        rtol=POOLED_SCORE_RTOL,
        atol=POOLED_SCORE_ATOL,
    ):
        raise ValueError("frozen pooled scores differ across comparison arms")
    combined = pd.DataFrame(
        {
            "donor_id": baseline["donor_id"],
            "baseline": baseline["adapter_mse"],
            "candidate": candidate["adapter_mse"],
        }
    )
    donors = sorted(combined["donor_id"].unique())
    means = combined.groupby("donor_id", sort=True)[["baseline", "candidate"]].mean()
    means = means.reindex(donors)
    return (
        means["baseline"].to_numpy(dtype=np.float64),
        means["candidate"].to_numpy(dtype=np.float64),
        donors,
    )


def _relative_reduction_percent(
    baseline: np.ndarray, candidate: np.ndarray
) -> float:
    baseline_mean = float(np.mean(baseline))
    candidate_mean = float(np.mean(candidate))
    return 100.0 * (baseline_mean - candidate_mean) / baseline_mean


def _bootstrap_interval(
    baseline_by_seed: np.ndarray,
    candidate_by_seed: np.ndarray,
    *,
    draws: int,
    seed: int,
) -> tuple[float, float]:
    if baseline_by_seed.shape != candidate_by_seed.shape:
        raise ValueError("bootstrap arrays are misaligned")
    if baseline_by_seed.ndim != 2 or baseline_by_seed.shape[0] != len(SEEDS):
        raise ValueError("bootstrap arrays must be seed by donor")
    rng = np.random.default_rng(seed)
    donor_count = baseline_by_seed.shape[1]
    values = np.empty(draws, dtype=np.float64)
    for draw in range(draws):
        indices = rng.integers(0, donor_count, size=donor_count)
        baseline = float(baseline_by_seed[:, indices].mean())
        candidate = float(candidate_by_seed[:, indices].mean())
        values[draw] = 100.0 * (baseline - candidate) / baseline
    low, high = np.quantile(values, [0.025, 0.975])
    return float(low), float(high)


def _matrix(
    values: dict[tuple[str, str], float | int],
    *,
    diagonal: float | int,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            [
                diagonal if recipient == donor else values[(recipient, donor)]
                for donor in ORGANS
            ]
            for recipient in ORGANS
        ],
        index=ORGANS,
        columns=ORGANS,
    )


def _render_heatmap(
    effect: pd.DataFrame,
    seed_positive: pd.DataFrame,
    ci_low: pd.DataFrame,
    ci_high: pd.DataFrame,
    output_path: Path,
) -> None:
    import matplotlib.pyplot as plt
    from matplotlib.colors import TwoSlopeNorm

    values = effect.to_numpy(dtype=np.float64)
    off_diagonal = values[~np.eye(len(values), dtype=bool)]
    bound = max(0.5, float(np.nanmax(np.abs(off_diagonal))))
    figure, axis = plt.subplots(figsize=(11.5, 9.5))
    image = axis.imshow(
        values,
        cmap="RdBu",
        norm=TwoSlopeNorm(vmin=-bound, vcenter=0.0, vmax=bound),
    )
    axis.set_xticks(range(len(ORGANS)), [value.replace("_", "\n") for value in ORGANS])
    axis.set_yticks(range(len(ORGANS)), [value.replace("_", " ") for value in ORGANS])
    axis.set_xlabel("Donor training organ B")
    axis.set_ylabel("Recipient evaluation organ A")
    axis.set_title(
        "Directed organ transfer: A750+B750 vs A1500\n"
        "cell = mean ΔMSE% across seeds; sign count and donor-bootstrap CI"
    )
    for row, recipient in enumerate(ORGANS):
        for column, donor in enumerate(ORGANS):
            if recipient == donor:
                label = "ref"
            else:
                value = effect.loc[recipient, donor]
                count = int(seed_positive.loc[recipient, donor])
                low = ci_low.loc[recipient, donor]
                high = ci_high.loc[recipient, donor]
                label = f"{value:+.2f}%\n{count}/3+\n[{low:+.2f},{high:+.2f}]"
            color = "white" if abs(values[row, column]) > bound * 0.55 else "black"
            axis.text(column, row, label, ha="center", va="center", fontsize=7, color=color)
    figure.colorbar(image, ax=axis, shrink=0.78, label="Helpful transfer ← ΔMSE reduction (%)")
    figure.tight_layout()
    figure.savefig(output_path, dpi=180)
    plt.close(figure)


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output_dir}")
    seed_roots = _parse_seed_roots(args.seed_root)
    expected_schedule_hash = str(args.expected_schedule_sha256).lower()
    expected_definitions_hash = str(args.expected_definitions_sha256).lower()
    definitions_path = Path(args.arm_definitions)
    if sha256_file(definitions_path) != expected_definitions_hash:
        raise ValueError("arm definitions differ from expected SHA256")
    definitions = json.loads(definitions_path.read_text())
    expected_arms = {str(value["arm_id"]) for value in definitions["arms"]}
    if len(expected_arms) != 60:
        raise ValueError("primary substitution evaluator requires exactly 60 arms")

    run_hashes = {}
    for seed, root in seed_roots.items():
        metadata_path = root / "run_metadata.json"
        metadata = json.loads(metadata_path.read_text())
        if (
            metadata.get("status") != "complete"
            or metadata.get("mechanical_only") is not False
            or metadata.get("training_seed") != seed
            or metadata.get("best_seed_selection_allowed") is not False
            or metadata.get("completed_arms") != 60
        ):
            raise ValueError(f"seed {seed} training root is incomplete or invalid")
        hashes = metadata.get("hashes", {})
        if hashes.get("training_schedules_sha256") != expected_schedule_hash:
            raise ValueError(f"seed {seed} schedule hash differs from evaluator")
        if hashes.get("arm_definitions_sha256") != expected_definitions_hash:
            raise ValueError(f"seed {seed} definitions hash differs from evaluator")
        completed_ids = {str(value["arm_id"]) for value in metadata.get("arms", [])}
        if completed_ids != expected_arms:
            raise ValueError(f"seed {seed} completed arm set differs from definition")
        run_hashes[str(seed)] = sha256_file(metadata_path)

    edge_rows: list[dict[str, Any]] = []
    effect_values: dict[tuple[str, str], float] = {}
    positive_counts: dict[tuple[str, str], int] = {}
    low_values: dict[tuple[str, str], float] = {}
    high_values: dict[tuple[str, str], float] = {}
    beats_random_counts: dict[tuple[str, str], int] = {}

    baseline_cache: dict[tuple[int, str], pd.DataFrame] = {}
    random_effect: dict[tuple[int, str, str], float] = {}
    for seed, root in seed_roots.items():
        for recipient in ORGANS:
            baseline = _load_score_cache(
                root, f"sub__{recipient}__recipient_only", recipient
            )
            baseline_cache[(seed, recipient)] = baseline
            for axis in RANDOM_AXES:
                random_frame = _load_score_cache(
                    root, f"sub__{recipient}__random__{axis}", recipient
                )
                baseline_donor, random_donor, _ = _paired_donor_arrays(
                    baseline, random_frame
                )
                random_effect[(seed, recipient, axis)] = _relative_reduction_percent(
                    baseline_donor, random_donor
                )

    for recipient_index, recipient in enumerate(ORGANS):
        for donor_index, donor in enumerate(ORGANS):
            if recipient == donor:
                continue
            seed_baselines = []
            seed_candidates = []
            donor_order = None
            seed_effects = []
            seed_beats_random = []
            arm_id = _pair_arm(recipient, donor)
            for seed, root in seed_roots.items():
                baseline = baseline_cache[(seed, recipient)]
                candidate = _load_score_cache(root, arm_id, recipient)
                baseline_donor, candidate_donor, donors = _paired_donor_arrays(
                    baseline, candidate
                )
                if donor_order is None:
                    donor_order = donors
                elif donor_order != donors:
                    raise ValueError("held-out donor order differs across seeds")
                effect = _relative_reduction_percent(
                    baseline_donor, candidate_donor
                )
                seed_effects.append(effect)
                seed_baselines.append(baseline_donor)
                seed_candidates.append(candidate_donor)
                random_values = [
                    random_effect[(seed, recipient, axis)] for axis in RANDOM_AXES
                ]
                seed_beats_random.append(effect > max(random_values))
                edge_rows.append(
                    {
                        "recipient": recipient,
                        "donor": donor,
                        "seed": seed,
                        "effect_percent": effect,
                        "positive": effect > 0,
                        "beats_all_three_random_controls": effect > max(random_values),
                        "random_control_mean_effect_percent": float(
                            np.mean(random_values)
                        ),
                        "held_out_donors": len(donors),
                    }
                )
            baseline_array = np.stack(seed_baselines)
            candidate_array = np.stack(seed_candidates)
            point = _relative_reduction_percent(
                baseline_array.reshape(-1), candidate_array.reshape(-1)
            )
            low, high = _bootstrap_interval(
                baseline_array,
                candidate_array,
                draws=int(args.bootstrap_draws),
                seed=int(args.bootstrap_seed)
                + recipient_index * len(ORGANS)
                + donor_index,
            )
            key = (recipient, donor)
            effect_values[key] = point
            positive_counts[key] = int(np.sum(np.asarray(seed_effects) > 0))
            low_values[key] = low
            high_values[key] = high
            beats_random_counts[key] = int(sum(seed_beats_random))

    effect = _matrix(effect_values, diagonal=0.0)
    seed_positive = _matrix(positive_counts, diagonal=0)
    ci_low = _matrix(low_values, diagonal=0.0)
    ci_high = _matrix(high_values, diagonal=0.0)
    beats_random = _matrix(beats_random_counts, diagonal=0)
    paths = {
        "effect": output_dir / "directed_transfer_effect_percent.csv",
        "seed_positive": output_dir / "seed_positive_count.csv",
        "ci_low": output_dir / "donor_bootstrap_ci_low_percent.csv",
        "ci_high": output_dir / "donor_bootstrap_ci_high_percent.csv",
        "beats_random": output_dir / "beats_all_random_seed_count.csv",
        "per_seed": output_dir / "per_seed_edges.csv",
        "heatmap": output_dir / "directed_transfer_heatmap.png",
    }
    effect.to_csv(paths["effect"])
    seed_positive.to_csv(paths["seed_positive"])
    ci_low.to_csv(paths["ci_low"])
    ci_high.to_csv(paths["ci_high"])
    beats_random.to_csv(paths["beats_random"])
    pd.DataFrame(edge_rows).to_csv(paths["per_seed"], index=False)
    if not bool(args.no_plot):
        _render_heatmap(effect, seed_positive, ci_low, ci_high, paths["heatmap"])

    off_diagonal = [
        (recipient, donor)
        for recipient in ORGANS
        for donor in ORGANS
        if recipient != donor
    ]
    all_seed_same_sign = sum(
        positive_counts[key] in {0, len(SEEDS)} for key in off_diagonal
    )
    donor_ci_excludes_zero = sum(
        low_values[key] > 0 or high_values[key] < 0 for key in off_diagonal
    )
    positive_all_seed_and_ci = sum(
        positive_counts[key] == len(SEEDS) and low_values[key] > 0
        for key in off_diagonal
    )
    negative_all_seed_and_ci = sum(
        positive_counts[key] == 0 and high_values[key] < 0
        for key in off_diagonal
    )
    report = {
        "schema_version": 1,
        "status": "complete",
        "research_stage": "stage2_directed_organ_transfer_development",
        "development_only": True,
        "study_disjoint": False,
        "held_out_unit": "GTEx donor",
        "best_seed_selection_allowed": False,
        "seeds": list(SEEDS),
        "organs": list(ORGANS),
        "primary_estimand": "A750+B750 versus A1500 donor-balanced recipient MSE",
        "effect_sign": "positive is helpful transfer; negative is interference",
        "bootstrap": {
            "unit": "held-out GTEx donor paired across arms and seeds",
            "draws": int(args.bootstrap_draws),
            "seed": int(args.bootstrap_seed),
        },
        "universality_boundary": (
            "Seed-sign agreement and donor-bootstrap stability do not establish "
            "independent-study universality; a new untouched multisource cohort is required."
        ),
        "summary": {
            "directed_edges": len(off_diagonal),
            "all_seed_same_sign_edges": all_seed_same_sign,
            "donor_ci_excludes_zero_edges": donor_ci_excludes_zero,
            "positive_all_seed_and_ci_edges": positive_all_seed_and_ci,
            "negative_all_seed_and_ci_edges": negative_all_seed_and_ci,
        },
        "hashes": {
            "arm_definitions_sha256": expected_definitions_hash,
            "training_schedule_sha256": expected_schedule_hash,
            "seed_run_metadata_sha256": run_hashes,
            "effect_matrix_sha256": sha256_file(paths["effect"]),
            "seed_positive_matrix_sha256": sha256_file(paths["seed_positive"]),
            "donor_ci_low_sha256": sha256_file(paths["ci_low"]),
            "donor_ci_high_sha256": sha256_file(paths["ci_high"]),
            "beats_random_matrix_sha256": sha256_file(paths["beats_random"]),
            "per_seed_edges_sha256": sha256_file(paths["per_seed"]),
        },
    }
    if not bool(args.no_plot):
        report["hashes"]["heatmap_sha256"] = sha256_file(paths["heatmap"])
    _atomic_json(output_dir / "evaluation_report.json", report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-root", action="append", required=True)
    parser.add_argument("--arm-definitions", required=True)
    parser.add_argument("--expected-schedule-sha256", required=True)
    parser.add_argument("--expected-definitions-sha256", required=True)
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
