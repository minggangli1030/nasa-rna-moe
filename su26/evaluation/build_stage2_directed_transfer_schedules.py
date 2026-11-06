#!/usr/bin/env python3
"""Compile exact, donor-auditable Stage 2 organ-transfer training schedules.

This builder reads only the GTEx development manifest. It creates deterministic
sample-draw schedules for the compute-matched substitution matrix and, when edges
are prospectively supplied, the recipient-exposure-matched additive confirmation.
It does not load expression, fit a model, or inspect any evaluation outcome.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = ROOT / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from train_manifest import (  # noqa: E402
    sha256_file,
    sha256_json,
    sha256_lines,
    stable_seed,
)


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
RANDOM_AXES = ("random_k8_p17", "random_k8_p42", "random_k8_p101")
REQUIRED_COLUMNS = {
    "sample_id",
    "donor_id",
    "split",
    "balanced_train",
    "organ",
    "series_group_id",
    *RANDOM_AXES,
}
SCHEMA_VERSION = 1


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _atomic_parquet(frame: pd.DataFrame, path: Path) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_parquet(temporary, index=False)
    os.replace(temporary, path)


class _ShuffledCycle:
    def __init__(self, values: Iterable[Any], rng: np.random.Generator):
        self.values = tuple(values)
        if not self.values:
            raise ValueError("cannot cycle over an empty pool")
        self.rng = rng
        self.order: list[Any] = []
        self.position = 0

    def next(self) -> Any:
        if self.position >= len(self.order):
            self.order = list(self.values)
            self.rng.shuffle(self.order)
            self.position = 0
        value = self.order[self.position]
        self.position += 1
        return value


class _DonorSampleCycle:
    """Cycle donors first, then samples within donor, for auditable exposure."""

    def __init__(
        self,
        frame: pd.DataFrame,
        eligible: np.ndarray,
        *,
        seed: int,
        source_pool_key: str,
    ):
        indices = np.flatnonzero(np.asarray(eligible, dtype=bool))
        if not len(indices):
            raise ValueError(f"source pool {source_pool_key!r} is empty")
        donors = frame.iloc[indices]["donor_id"].astype(str).to_numpy()
        donor_to_indices: dict[str, list[int]] = {}
        for index, donor in zip(indices.tolist(), donors.tolist()):
            donor_to_indices.setdefault(donor, []).append(int(index))
        rng = np.random.default_rng(
            stable_seed(
                seed,
                "stage2_directed_transfer_source_pool",
                source_pool_key,
                sha256_lines(
                    frame.iloc[indices]["sample_id"].astype(str).sort_values().tolist()
                ),
            )
        )
        self.donor_cycle = _ShuffledCycle(sorted(donor_to_indices), rng)
        self.sample_cycles = {
            donor: _ShuffledCycle(sorted(values), rng)
            for donor, values in donor_to_indices.items()
        }

    def next(self) -> int:
        donor = str(self.donor_cycle.next())
        return int(self.sample_cycles[donor].next())


def _read_manifest(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".parquet", ".pq"}:
        frame = pd.read_parquet(path)
    else:
        frame = pd.read_csv(path)
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"manifest lacks required columns: {missing}")
    if frame["sample_id"].astype(str).duplicated().any():
        raise ValueError("manifest contains repeated sample IDs")
    train = frame.loc[
        frame["split"].astype(str).eq("train")
        & frame["balanced_train"].astype(bool)
    ].copy()
    if train.empty:
        raise ValueError("manifest has no balanced training rows")
    train = train.sort_values("sample_id", kind="stable").reset_index(drop=True)
    observed = set(train["organ"].astype(str))
    if observed != set(ORGANS):
        raise ValueError(
            f"training organ set differs from frozen K8 set: {sorted(observed)}"
        )
    for axis in RANDOM_AXES:
        donor_counts = train.groupby("donor_id", sort=False)[axis].nunique(dropna=False)
        if int(donor_counts.max()) != 1:
            raise ValueError(f"{axis} is not donor-atomic")
        labels = pd.to_numeric(train[axis], errors="raise").astype(np.int64)
        if set(labels.unique()) != set(range(len(ORGANS))):
            raise ValueError(f"{axis} does not cover exact labels 0..7")
        train[axis] = labels
    return train


def _schedule_arm(
    frame: pd.DataFrame,
    *,
    arm_id: str,
    sources: list[tuple[str, str, np.ndarray, int]],
    seed: int,
    batch_size: int,
    initialization_key: str,
    evaluation_recipients: list[str],
    estimand: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if not sources or any(draws <= 0 for _, _, _, draws in sources):
        raise ValueError(f"arm {arm_id!r} has an invalid source specification")
    source_names = [role for role, _, _, _ in sources]
    if len(source_names) != len(set(source_names)):
        raise ValueError(f"arm {arm_id!r} repeats a source role")
    cycles = {
        role: _DonorSampleCycle(
            frame,
            eligible,
            seed=seed,
            source_pool_key=label,
        )
        for role, label, eligible, _ in sources
    }
    total_draws = int(sum(draws for _, _, _, draws in sources))
    if batch_size <= 0 or total_draws % batch_size:
        raise ValueError(
            f"arm {arm_id!r} total draws do not divide by batch size {batch_size}"
        )
    number_batches = total_draws // batch_size
    per_batch: dict[str, int] = {}
    for role, _, _, draws in sources:
        if draws % number_batches:
            raise ValueError(
                f"arm {arm_id!r} source {role!r} cannot be balanced in every batch"
            )
        per_batch[role] = draws // number_batches
    if sum(per_batch.values()) != batch_size:
        raise AssertionError(f"arm {arm_id!r} per-batch source quotas are invalid")
    role_batches = []
    for batch_number in range(number_batches):
        batch_roles = np.concatenate(
            [np.repeat(role, per_batch[role]) for role in source_names]
        ).astype(object)
        rng = np.random.default_rng(
            stable_seed(
                seed,
                "stage2_directed_transfer",
                arm_id,
                "batch_role_order",
                batch_number,
            )
        )
        rng.shuffle(batch_roles)
        role_batches.append(batch_roles)
    draw_roles = np.concatenate(role_batches)
    source_labels = {role: label for role, label, _, _ in sources}
    source_draw_numbers = {role: 0 for role in source_names}
    rows: list[dict[str, Any]] = []
    for draw_number, role_value in enumerate(draw_roles.tolist()):
        role = str(role_value)
        sample_index = cycles[role].next()
        source_row = frame.iloc[sample_index]
        source_draw_number = source_draw_numbers[role]
        source_draw_numbers[role] += 1
        rows.append(
            {
                "arm_id": arm_id,
                "draw_number": draw_number,
                "batch_number": draw_number // batch_size,
                "batch_position": draw_number % batch_size,
                "source_draw_number": source_draw_number,
                "source_role": role,
                "source_label": source_labels[role],
                "sample_id": str(source_row["sample_id"]),
                "donor_id": str(source_row["donor_id"]),
                "organ": str(source_row["organ"]),
                "series_group_id": str(source_row["series_group_id"]),
            }
        )
    schedule = pd.DataFrame(rows)
    realized = schedule["source_role"].value_counts().sort_index().to_dict()
    expected = {role: int(draws) for role, _, _, draws in sources}
    if realized != dict(sorted(expected.items())):
        raise AssertionError(f"arm {arm_id!r} did not realize exact source quotas")
    definition = {
        "arm_id": arm_id,
        "estimand": estimand,
        "initialization_key": initialization_key,
        "evaluation_recipients": evaluation_recipients,
        "total_draws": int(len(schedule)),
        "batch_size": batch_size,
        "number_batches": number_batches,
        "source_draws_per_batch": per_batch,
        "source_draws": expected,
        "source_labels": source_labels,
        "unique_samples": int(schedule["sample_id"].nunique()),
        "unique_donors": int(schedule["donor_id"].nunique()),
    }
    return schedule, definition


def _parse_edges(values: list[str] | None) -> list[tuple[str, str]]:
    edges: list[tuple[str, str]] = []
    for raw in values or []:
        if ":" not in raw:
            raise ValueError("additive edges must use RECIPIENT:DONOR")
        recipient, donor = (value.strip() for value in raw.split(":", 1))
        if recipient not in ORGANS or donor not in ORGANS:
            raise ValueError(f"additive edge names an unknown organ: {raw!r}")
        if recipient == donor:
            raise ValueError(f"additive edge must be off-diagonal: {raw!r}")
        edge = (recipient, donor)
        if edge in edges:
            raise ValueError(f"additive edge is repeated: {raw!r}")
        edges.append(edge)
    return edges


def compile_schedules(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path = Path(args.manifest)
    expected_hash = str(args.expected_manifest_sha256).lower()
    actual_hash = sha256_file(manifest_path)
    if actual_hash != expected_hash:
        raise ValueError(
            f"manifest SHA256 mismatch: expected {expected_hash}, observed {actual_hash}"
        )
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output_dir}")
    frame = _read_manifest(manifest_path)
    seed = int(args.schedule_seed)
    per_source = int(args.draws_per_source)
    if per_source <= 0:
        raise ValueError("draws-per-source must be positive")
    initialization_key = str(args.initialization_key)
    if not initialization_key:
        raise ValueError("initialization-key must be nonempty")
    additive_edges = _parse_edges(getattr(args, "additive_edge", None))
    additive_only = bool(getattr(args, "additive_only", False))
    stability_diagnostic_only = bool(
        getattr(args, "stability_diagnostic_only", False)
    )
    if additive_only and stability_diagnostic_only:
        raise ValueError(
            "additive-only and stability-diagnostic-only are mutually exclusive"
        )
    if additive_only and not additive_edges:
        raise ValueError("additive-only schedule requires at least one additive edge")
    if stability_diagnostic_only and not additive_edges:
        raise ValueError(
            "stability-diagnostic-only schedule requires at least one additive edge"
        )

    schedules: list[pd.DataFrame] = []
    definitions: list[dict[str, Any]] = []

    def add_arm(
        arm_id: str,
        sources: list[tuple[str, str, np.ndarray, int]],
        recipients: list[str],
        estimand: str,
    ) -> None:
        schedule, definition = _schedule_arm(
            frame,
            arm_id=arm_id,
            sources=sources,
            seed=seed,
            batch_size=int(args.batch_size),
            initialization_key=initialization_key,
            evaluation_recipients=recipients,
            estimand=estimand,
        )
        schedules.append(schedule)
        definitions.append(definition)

    organ_values = frame["organ"].astype(str).to_numpy()
    organ_masks = {organ: organ_values == organ for organ in ORGANS}
    if not additive_only and not stability_diagnostic_only:
        for recipient in ORGANS:
            add_arm(
                f"sub__{recipient}__recipient_only",
                [("recipient", recipient, organ_masks[recipient], 2 * per_source)],
                [recipient],
                "same_total_compute_recipient_only",
            )
        for left_index, left in enumerate(ORGANS):
            for right in ORGANS[left_index + 1 :]:
                add_arm(
                    f"sub__{left}__{right}",
                    [
                        ("organ_1", left, organ_masks[left], per_source),
                        ("organ_2", right, organ_masks[right], per_source),
                    ],
                    [left, right],
                    "same_total_compute_organ_pair",
                )
        for recipient_index, recipient in enumerate(ORGANS):
            for axis in RANDOM_AXES:
                auxiliary = (
                    frame[axis].to_numpy(dtype=np.int64) == recipient_index
                ) & ~organ_masks[recipient]
                auxiliary_label = f"{axis}:excluding:{recipient}"
                add_arm(
                    f"sub__{recipient}__random__{axis}",
                    [
                        ("recipient", recipient, organ_masks[recipient], per_source),
                        (
                            "random_auxiliary",
                            auxiliary_label,
                            auxiliary,
                            per_source,
                        ),
                    ],
                    [recipient],
                    "same_total_compute_random_auxiliary",
                )

    additive_recipients = sorted({recipient for recipient, _ in additive_edges})
    if stability_diagnostic_only:
        if len(additive_edges) != len(additive_recipients):
            raise ValueError(
                "stability diagnosis requires exactly one donor per recipient"
            )
        for recipient in additive_recipients:
            add_arm(
                f"diag__{recipient}__recipient_only",
                [("recipient", recipient, organ_masks[recipient], 2 * per_source)],
                [recipient],
                "stability_diagnostic_recipient_only",
            )
            add_arm(
                f"diag__{recipient}__self_control",
                [("recipient", recipient, organ_masks[recipient], 3 * per_source)],
                [recipient],
                "stability_diagnostic_additional_recipient_control",
            )
        for recipient, donor in additive_edges:
            add_arm(
                f"diag__{recipient}__{donor}",
                [
                    ("recipient", recipient, organ_masks[recipient], 2 * per_source),
                    ("donor", donor, organ_masks[donor], per_source),
                ],
                [recipient],
                "stability_diagnostic_named_donor",
            )
    else:
        for recipient in additive_recipients:
            add_arm(
                f"add__{recipient}__self_control",
                [("recipient", recipient, organ_masks[recipient], 3 * per_source)],
                [recipient],
                "same_total_draws_additional_recipient_control",
            )
            for axis in RANDOM_AXES:
                recipient_index = ORGANS.index(recipient)
                auxiliary = (
                    frame[axis].to_numpy(dtype=np.int64) == recipient_index
                ) & ~organ_masks[recipient]
                auxiliary_label = f"{axis}:excluding:{recipient}"
                add_arm(
                    f"add__{recipient}__random__{axis}",
                    [
                        (
                            "recipient",
                            recipient,
                            organ_masks[recipient],
                            2 * per_source,
                        ),
                        (
                            "random_auxiliary",
                            auxiliary_label,
                            auxiliary,
                            per_source,
                        ),
                    ],
                    [recipient],
                    "same_recipient_exposure_random_auxiliary",
                )
        for recipient, donor in additive_edges:
            add_arm(
                f"add__{recipient}__{donor}",
                [
                    ("recipient", recipient, organ_masks[recipient], 2 * per_source),
                    ("donor", donor, organ_masks[donor], per_source),
                ],
                [recipient],
                "same_recipient_exposure_named_donor",
            )

    arm_ids = [definition["arm_id"] for definition in definitions]
    if len(arm_ids) != len(set(arm_ids)):
        raise AssertionError("compiled arm IDs are not unique")
    schedule_frame = pd.concat(schedules, ignore_index=True)
    schedule_path = output_dir / "training_schedules.parquet"
    _atomic_parquet(schedule_frame, schedule_path)
    definitions_path = output_dir / "arm_definitions.json"
    _atomic_json(
        definitions_path,
        {
            "schema_version": SCHEMA_VERSION,
            "initialization_key": initialization_key,
            "schedule_seed": seed,
            "draws_per_source": per_source,
            "batch_size": int(args.batch_size),
            "arms": definitions,
        },
    )
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "complete",
        "research_stage": "stage2_directed_organ_transfer_development",
        "development_only": True,
        "expression_loaded": False,
        "model_fit": False,
        "efficacy_result_loaded": False,
        "best_seed_selection_allowed": False,
        "organs": list(ORGANS),
        "random_axes": list(RANDOM_AXES),
        "schedule_seed": seed,
        "draws_per_source": per_source,
        "batch_size": int(args.batch_size),
        "initialization_key": initialization_key,
        "schedule_mode": (
            "stability_diagnostic_only"
            if stability_diagnostic_only
            else "additive_only"
            if additive_only
            else "combined"
        ),
        "additive_edges": [f"{recipient}:{donor}" for recipient, donor in additive_edges],
        "counts": {
            "training_rows": int(len(frame)),
            "training_donors": int(frame["donor_id"].nunique()),
            "substitution_recipient_only_arms": (
                0 if additive_only or stability_diagnostic_only else len(ORGANS)
            ),
            "substitution_pair_arms": (
                0
                if additive_only or stability_diagnostic_only
                else len(ORGANS) * (len(ORGANS) - 1) // 2
            ),
            "substitution_random_control_arms": (
                0
                if additive_only or stability_diagnostic_only
                else len(ORGANS) * len(RANDOM_AXES)
            ),
            "additive_named_donor_arms": len(additive_edges),
            "stability_recipient_only_arms": (
                len(additive_recipients) if stability_diagnostic_only else 0
            ),
            "stability_self_control_arms": (
                len(additive_recipients) if stability_diagnostic_only else 0
            ),
            "total_arms": len(definitions),
            "total_schedule_draws": int(len(schedule_frame)),
        },
        "hashes": {
            "manifest_sha256": actual_hash,
            "training_schedules_sha256": sha256_file(schedule_path),
            "arm_definitions_sha256": sha256_file(definitions_path),
            "arm_definitions_content_sha256": sha256_json(definitions),
        },
    }
    _atomic_json(output_dir / "schedule_report.json", report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--schedule-seed", type=int, default=20260727)
    parser.add_argument("--draws-per-source", type=int, default=750)
    parser.add_argument("--batch-size", type=int, default=6)
    parser.add_argument(
        "--initialization-key", default="stage2_directed_transfer_shared_k1"
    )
    parser.add_argument(
        "--additive-edge",
        action="append",
        help=(
            "Prospectively frozen RECIPIENT:DONOR additive edge. Omit until "
            "development-only expert/router predictions freeze the subset."
        ),
    )
    parser.add_argument(
        "--additive-only",
        action="store_true",
        help=(
            "Compile only the prospectively supplied additive arms and their "
            "self/random controls, omitting the already completed substitution arms."
        ),
    )
    parser.add_argument(
        "--stability-diagnostic-only",
        action="store_true",
        help=(
            "Compile only paired A1500, A2250, and A1500+B750 arms for the "
            "supplied one-donor-per-recipient edge set."
        ),
    )
    return parser


def main() -> None:
    report = compile_schedules(build_parser().parse_args())
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
