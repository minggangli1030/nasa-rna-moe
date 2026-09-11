#!/usr/bin/env python3
"""Freeze balanced Stage 1 training IDs and matched random-shard controls.

This module does not relabel samples or create cohort splits.  It augments an
already study-disjoint organ manifest with two training-only fields:

``balanced_train``
    A deterministic, equal-size subset for every organ.  Selection is spread
    across connected studies before taking a second sample from a study.

``random_shard``
    A deterministic pseudogroup assignment over exactly the balanced union.
    Every shard has the same size as an organ specialist and (up to a single
    row when division is uneven) the same mixture of source organs.  These
    shards control for extra model storage and generic ensemble diversity.

The original rows and natural class frequencies remain in the output.  A
trainer may therefore run both the balanced primary smoke comparison and a
natural-frequency sensitivity analysis from one frozen artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {"sample_id", "organ", "series_group_id", "split"}


def _stable_seed(seed: int, label: str) -> int:
    digest = hashlib.sha256(f"{seed}:{label}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "little")


def _sha256_lines(values) -> str:
    payload = "\n".join(str(value) for value in values) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _study_round_robin_ids(
    frame: pd.DataFrame,
    target: int,
    seed: int,
    label: str,
) -> list[str]:
    """Select ``target`` rows while distributing selection across studies."""
    if target < 1:
        raise ValueError("target must be positive")
    if target > len(frame):
        raise ValueError(f"target {target} exceeds available rows {len(frame)} for {label}")

    queues: dict[str, list[str]] = {}
    for group, subset in frame.groupby("series_group_id", sort=True):
        ids = sorted(subset["sample_id"].astype(str).tolist())
        rng = np.random.default_rng(_stable_seed(seed, f"{label}:{group}:rows"))
        order = rng.permutation(len(ids))
        queues[str(group)] = [ids[index] for index in order]

    groups = sorted(queues)
    rng = np.random.default_rng(_stable_seed(seed, f"{label}:groups"))
    group_order = [groups[index] for index in rng.permutation(len(groups))]
    selected: list[str] = []
    depth = 0
    while len(selected) < target:
        added = 0
        for group in group_order:
            if depth < len(queues[group]):
                selected.append(queues[group][depth])
                added += 1
                if len(selected) == target:
                    break
        if added == 0:
            raise AssertionError("round-robin selection exhausted before reaching target")
        depth += 1
    return selected


def _assign_random_shards(
    selected: pd.DataFrame,
    organs: list[str],
    target: int,
    seed: int,
) -> dict[str, str]:
    """Return equal-sized, organ-balanced pseudogroups for selected rows."""
    k = len(organs)
    shard_names = [f"random_{index}" for index in range(k)]
    assignments: dict[str, str] = {}
    base, remainder = divmod(target, k)

    for organ_index, organ in enumerate(organs):
        organ_rows = selected.loc[selected["organ"].eq(organ)].copy()
        if len(organ_rows) != target:
            raise ValueError(
                f"balanced organ {organ} has {len(organ_rows)} rows, expected {target}"
            )

        # Rotating the remainder across K source organs gives every shard an
        # exact final size of ``target`` while keeping organ mixtures matched.
        extra = {(organ_index + offset) % k for offset in range(remainder)}
        quotas = [base + int(index in extra) for index in range(k)]
        organ_counts = [0] * k

        groups = []
        for group, subset in organ_rows.groupby("series_group_id", sort=True):
            ids = sorted(subset["sample_id"].astype(str).tolist())
            rng = np.random.default_rng(
                _stable_seed(seed, f"random-shards:{organ}:{group}:rows")
            )
            ids = [ids[index] for index in rng.permutation(len(ids))]
            group_tie = _stable_seed(seed, f"random-shards:{organ}:{group}:order")
            groups.append((str(group), ids, group_tie))
        # Large studies are allocated first so their rows are spread across
        # shards instead of filling whatever capacity happens to remain.
        groups.sort(key=lambda item: (-len(item[1]), item[2], item[0]))

        for group, ids, tie_seed in groups:
            group_counts = [0] * k
            tie_order = list(np.random.default_rng(tie_seed).permutation(k))
            tie_rank = {shard: rank for rank, shard in enumerate(tie_order)}
            for sample_id in ids:
                candidates = [index for index in range(k) if organ_counts[index] < quotas[index]]
                if not candidates:
                    raise AssertionError("random-shard capacities exhausted early")
                shard_index = min(
                    candidates,
                    key=lambda index: (
                        group_counts[index],
                        organ_counts[index] / max(1, quotas[index]),
                        tie_rank[index],
                    ),
                )
                assignments[sample_id] = shard_names[shard_index]
                organ_counts[shard_index] += 1
                group_counts[shard_index] += 1
        if organ_counts != quotas:
            raise AssertionError(
                f"random-shard organ quotas not met for {organ}: {organ_counts} != {quotas}"
            )

    counts = pd.Series(assignments).value_counts().to_dict()
    if set(counts) != set(shard_names) or any(counts[name] != target for name in shard_names):
        raise AssertionError(f"random shards are not exactly balanced: {counts}")
    return assignments


def _assign_nontrain_random_shards(
    frame: pd.DataFrame,
    organs: list[str],
    seed: int,
    split: str,
) -> dict[str, str]:
    """Balance each organ across validation/test pseudogroups.

    These assignments are used only for random-expert checkpoint validation;
    final evaluation still scores every expert on every test sample.
    """
    k = len(organs)
    assignments: dict[str, str] = {}
    for organ_index, organ in enumerate(organs):
        subset = frame.loc[frame["organ"].eq(organ)]
        if subset.empty:
            raise ValueError(f"split {split!r} has no rows for organ {organ!r}")
        ordered_ids = _study_round_robin_ids(
            subset,
            len(subset),
            seed,
            f"{split}:{organ}:random-validation",
        )
        for position, sample_id in enumerate(ordered_ids):
            shard_index = (position + organ_index) % k
            assignments[sample_id] = f"random_{shard_index}"
    return assignments


def build_balanced_protocol(
    manifest: pd.DataFrame,
    *,
    seed: int = 314159,
    train_split: str = "train",
    target_per_organ: int | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Augment ``manifest`` with a balanced train set and random controls."""
    missing = REQUIRED_COLUMNS - set(manifest.columns)
    if missing:
        raise ValueError(f"manifest is missing required columns: {sorted(missing)}")
    if manifest["sample_id"].isna().any() or manifest["sample_id"].duplicated().any():
        raise ValueError("manifest sample_id values must be non-null and unique")
    if manifest[list(REQUIRED_COLUMNS - {"sample_id"})].isna().any().any():
        raise ValueError("organ, series_group_id, and split must be non-null")
    overlap = manifest.groupby("series_group_id")["split"].nunique()
    if (overlap > 1).any():
        bad = overlap[overlap > 1].index.astype(str).tolist()[:5]
        raise ValueError(f"connected studies cross splits: {bad}")

    output = manifest.copy()
    output["sample_id"] = output["sample_id"].astype(str)
    output["organ"] = output["organ"].astype(str)
    train = output.loc[output["split"].astype(str).eq(train_split)].copy()
    if train.empty:
        raise ValueError(f"manifest contains no rows for train split {train_split!r}")
    organs = sorted(train["organ"].unique().tolist())
    if len(organs) < 2:
        raise ValueError("at least two organs are required")
    available = train.groupby("organ")["sample_id"].size().to_dict()
    if set(available) != set(organs):
        raise AssertionError("organ count construction failed")

    target = min(available.values()) if target_per_organ is None else int(target_per_organ)
    if target < 1:
        raise ValueError("target_per_organ must be positive")
    too_small = {organ: count for organ, count in available.items() if count < target}
    if too_small:
        raise ValueError(f"target_per_organ exceeds availability: {too_small}")

    selected_ids: list[str] = []
    for organ in organs:
        subset = train.loc[train["organ"].eq(organ)]
        selected_ids.extend(_study_round_robin_ids(subset, target, seed, organ))
    selected_set = set(selected_ids)
    if len(selected_set) != len(organs) * target:
        raise AssertionError("balanced selection contains duplicate sample IDs")

    output["balanced_train"] = output["sample_id"].isin(selected_set)
    random_assignments = _assign_random_shards(
        output.loc[output["balanced_train"]], organs, target, seed
    )
    for split in sorted(output["split"].astype(str).unique()):
        if split == train_split:
            continue
        split_rows = output.loc[output["split"].astype(str).eq(split)]
        random_assignments.update(
            _assign_nontrain_random_shards(split_rows, organs, seed, split)
        )
    output["random_shard"] = output["sample_id"].map(random_assignments).fillna("")

    # Full-union weights are useful for a sensitivity run that retains every
    # training row but samples organs uniformly.  Non-training rows get zero.
    output["organ_balanced_weight"] = 0.0
    for organ, count in available.items():
        mask = output["split"].astype(str).eq(train_split) & output["organ"].eq(organ)
        output.loc[mask, "organ_balanced_weight"] = 1.0 / float(count)

    selected = output.loc[output["balanced_train"]]
    organ_counts = selected.groupby("organ").size().sort_index().to_dict()
    shard_counts = selected.groupby("random_shard").size().sort_index().to_dict()
    mixture = (
        selected.groupby(["random_shard", "organ"]).size().unstack(fill_value=0)
        .sort_index().reindex(columns=organs, fill_value=0)
    )
    shard_study_counts = (
        selected.groupby("random_shard")["series_group_id"].nunique().sort_index().to_dict()
    )
    if any(count != target for count in organ_counts.values()):
        raise AssertionError(f"organ selection is not balanced: {organ_counts}")
    if any(count != target for count in shard_counts.values()):
        raise AssertionError(f"random shards are not size matched: {shard_counts}")
    if int((mixture.max(axis=0) - mixture.min(axis=0)).max()) > 1:
        raise AssertionError("source-organ mixture differs by more than one across shards")

    sorted_selected_ids = sorted(selected_set)
    report = {
        "schema_version": 1,
        "seed": seed,
        "train_split": train_split,
        "organs": organs,
        "n_organs": len(organs),
        "target_per_organ": target,
        "available_train_counts": {key: int(value) for key, value in sorted(available.items())},
        "balanced_train_counts": {key: int(value) for key, value in organ_counts.items()},
        "random_shard_counts": {key: int(value) for key, value in shard_counts.items()},
        "random_shard_source_organ_counts": {
            shard: {organ: int(value) for organ, value in row.items()}
            for shard, row in mixture.to_dict("index").items()
        },
        "random_shard_connected_study_counts": {
            key: int(value) for key, value in shard_study_counts.items()
        },
        "random_shard_counts_by_split": {
            str(split): {
                str(shard): int(count)
                for shard, count in subset.loc[subset["random_shard"].ne("")]
                .groupby("random_shard").size().sort_index().items()
            }
            for split, subset in output.groupby("split", sort=True)
        },
        "balanced_sample_id_sha256": _sha256_lines(sorted_selected_ids),
        "random_shard_assignment_sha256": _sha256_lines(
            f"{sample_id}\t{random_assignments[sample_id]}"
            for sample_id in sorted(random_assignments)
        ),
        "natural_rows_retained": int(len(output)),
        "notes": [
            "balanced_train is the primary class-balanced protocol subset",
            "organ_balanced_weight supports a full-union balanced-sampling sensitivity run",
            "natural class frequencies are retained for secondary evaluation",
        ],
    }
    return output, report


def _read_frame(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--seed", type=int, default=314159)
    parser.add_argument("--train-split", default="train")
    parser.add_argument(
        "--target-per-organ",
        type=int,
        default=0,
        help="Exact balanced training rows per organ; 0 uses the smallest organ.",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output, report = build_balanced_protocol(
        _read_frame(manifest_path),
        seed=args.seed,
        train_split=args.train_split,
        target_per_organ=args.target_per_organ or None,
    )
    output.to_csv(output_dir / "organ_protocol_manifest.csv", index=False)
    output.to_parquet(output_dir / "organ_protocol_manifest.parquet", index=False)
    (output_dir / "protocol_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
