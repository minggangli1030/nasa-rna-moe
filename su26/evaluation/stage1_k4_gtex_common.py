#!/usr/bin/env python3
"""Shared, prospective contracts for the Stage 1 K4 GTEx evaluation."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


SEEDS = (17, 42, 101)
PARTITION_SEEDS = (17, 42, 101)
ORGANS = ("adipose", "brain", "liver", "skeletal_muscle", "skin")
ACTIVE_ORGANS = ("brain", "liver", "skeletal_muscle", "skin")
ORGAN_TO_EXPERT = {organ: index for index, organ in enumerate(ACTIVE_ORGANS)}
FALLBACK_LABEL = -1
BOOTSTRAP_DRAWS = 10_000
BOOTSTRAP_SEED = 314159


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_lines(values: Iterable[Any]) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(str(value).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def atomic_json(path: str | Path, value: Any) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, output)


def load_frozen_protocol(path: str | Path, expected_sha256: str | None = None) -> dict:
    protocol_path = Path(path)
    if expected_sha256 and sha256_file(protocol_path) != expected_sha256:
        raise ValueError("GTEx evaluation protocol SHA256 mismatch")
    protocol = json.loads(protocol_path.read_text())
    if protocol.get("status") != "frozen":
        raise ValueError("GTEx evaluation protocol is not frozen")
    authorization = protocol.get("authorization", {})
    if authorization.get("requested_by_user") is not True:
        raise ValueError("GTEx expression access is not user-authorized")
    if protocol.get("one_time_expression_access") is not True:
        raise ValueError("GTEx protocol does not enforce one-time expression access")
    if tuple(protocol.get("estimand", {}).get("organ_order", ())) != ORGANS:
        raise ValueError("GTEx protocol organ order changed")
    if tuple(protocol.get("model", {}).get("training_seeds", ())) != SEEDS:
        raise ValueError("GTEx protocol training seeds changed")
    source_hashes = protocol.get("implementation", {}).get("source_sha256", {})
    if source_hashes:
        root = Path(__file__).resolve().parents[1]
        for relative, expected in source_hashes.items():
            source = root / relative
            if not source.is_file() or sha256_file(source) != expected:
                raise ValueError(f"GTEx implementation source hash mismatch: {relative}")
    return protocol


def deterministic_random_assignments(
    frame: pd.DataFrame,
    partition_seed: int,
    *,
    donor_column: str = "donor_id",
    organ_column: str = "organ",
) -> np.ndarray:
    """Assign donor-organ units to four experts with deterministic balance.

    Donors are hash-ranked independently inside each organ and allocated in a
    round-robin cycle. Every sample from a donor-organ unit therefore receives
    the same label, and expert donor counts differ by at most one per organ.
    """
    if int(partition_seed) not in PARTITION_SEEDS:
        raise ValueError("unknown frozen random partition seed")
    required = {donor_column, organ_column}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"assignment frame lacks columns: {missing}")
    if frame[list(required)].isna().any().any():
        raise ValueError("assignment frame contains missing donor or organ")
    organs = frame[organ_column].astype(str)
    if not set(organs).issubset(ORGANS):
        raise ValueError("assignment frame contains a noncanonical organ")

    unit_labels: dict[tuple[str, str], int] = {}
    units = frame[[donor_column, organ_column]].drop_duplicates()
    for organ in ORGANS:
        donors = units.loc[
            units[organ_column].astype(str).eq(organ), donor_column
        ].astype(str).tolist()
        ranked = sorted(
            donors,
            key=lambda donor: (
                hashlib.sha256(
                    f"{partition_seed}\0{organ}\0{donor}".encode("utf-8")
                ).hexdigest(),
                donor,
            ),
        )
        for rank, donor in enumerate(ranked):
            unit_labels[(donor, organ)] = rank % len(ACTIVE_ORGANS)
    output = np.asarray(
        [
            unit_labels[(str(donor), str(organ))]
            for donor, organ in frame[[donor_column, organ_column]].itertuples(
                index=False, name=None
            )
        ],
        dtype=np.int64,
    )
    return output


def donor_organ_means(
    frame: pd.DataFrame,
    value_columns: list[str],
    *,
    donor_column: str = "donor_id",
    organ_column: str = "organ",
) -> pd.DataFrame:
    required = {donor_column, organ_column, *value_columns}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"score frame lacks columns: {missing}")
    if frame[[donor_column, organ_column]].isna().any().any():
        raise ValueError("score frame contains missing donor or organ")
    values = frame[value_columns].to_numpy(dtype=np.float64)
    if not np.isfinite(values).all():
        raise ValueError("score frame contains nonfinite metrics")
    output = (
        frame.groupby([donor_column, organ_column], sort=True, observed=True)[
            value_columns
        ]
        .mean()
        .reset_index()
    )
    if set(output[organ_column].astype(str)) != set(ORGANS):
        raise ValueError("donor-organ summaries do not cover all five organs")
    return output


def equal_organ_mean(
    donor_organ: pd.DataFrame,
    value_column: str,
    *,
    donor_multiplicity: dict[str, int] | None = None,
) -> float:
    organ_means: list[float] = []
    for organ in ORGANS:
        subset = donor_organ.loc[
            donor_organ["organ"].astype(str).eq(organ), ["donor_id", value_column]
        ]
        if subset.empty:
            raise ValueError(f"no donor summaries for {organ}")
        values = subset[value_column].to_numpy(dtype=np.float64)
        if donor_multiplicity is None:
            organ_means.append(float(values.mean()))
        else:
            weights = np.asarray(
                [donor_multiplicity.get(str(value), 0) for value in subset["donor_id"]],
                dtype=np.float64,
            )
            if weights.sum() <= 0:
                raise ValueError(f"bootstrap draw contains no donors for {organ}")
            organ_means.append(float(np.average(values, weights=weights)))
    return float(np.mean(organ_means))


def donor_bootstrap_comparison(
    donor_organ: pd.DataFrame,
    control_column: str,
    candidate_column: str,
    *,
    draws: int = BOOTSTRAP_DRAWS,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """Paired global-donor bootstrap preserving cross-organ donor correlation."""
    if draws < 100:
        raise ValueError("donor bootstrap requires at least 100 draws")
    donors = np.asarray(sorted(donor_organ["donor_id"].astype(str).unique()))
    if len(donors) < 2:
        raise ValueError("donor bootstrap requires at least two donors")
    control = equal_organ_mean(donor_organ, control_column)
    candidate = equal_organ_mean(donor_organ, candidate_column)
    if control <= 0:
        raise ValueError("control MSE must be positive")
    sampled = _bootstrap_equal_organ_means(
        donor_organ, [control_column, candidate_column], draws=draws, seed=seed
    )
    sampled_control = sampled[:, 0]
    sampled_candidate = sampled[:, 1]
    improvements = sampled_control - sampled_candidate
    relative = improvements / sampled_control
    absolute = control - candidate
    return {
        "control_mean": control,
        "candidate_mean": candidate,
        "absolute_improvement": absolute,
        "relative_reduction": absolute / control,
        "absolute_ci95": np.quantile(improvements, [0.025, 0.975]).tolist(),
        "relative_ci95": np.quantile(relative, [0.025, 0.975]).tolist(),
        "one_sided_p": float((1 + np.count_nonzero(improvements <= 0)) / (draws + 1)),
        "bootstrap_draws": int(draws),
        "bootstrap_seed": int(seed),
    }


def donor_bootstrap_difference(
    donor_organ: pd.DataFrame,
    candidate_column: str,
    control_column: str,
    *,
    draws: int = BOOTSTRAP_DRAWS,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """Bootstrap a candidate-minus-control metric difference by donor."""
    if draws < 100:
        raise ValueError("donor bootstrap requires at least 100 draws")
    donors = np.asarray(sorted(donor_organ["donor_id"].astype(str).unique()))
    if len(donors) < 2:
        raise ValueError("donor bootstrap requires at least two donors")
    candidate = equal_organ_mean(donor_organ, candidate_column)
    control = equal_organ_mean(donor_organ, control_column)
    sampled = _bootstrap_equal_organ_means(
        donor_organ, [candidate_column, control_column], draws=draws, seed=seed
    )
    gains = sampled[:, 0] - sampled[:, 1]
    return {
        "candidate_mean": candidate,
        "control_mean": control,
        "gain": candidate - control,
        "gain_ci95": np.quantile(gains, [0.025, 0.975]).tolist(),
        "one_sided_p": float((1 + np.count_nonzero(gains <= 0)) / (draws + 1)),
        "bootstrap_draws": int(draws),
        "bootstrap_seed": int(seed),
    }


def _bootstrap_equal_organ_means(
    donor_organ: pd.DataFrame,
    value_columns: list[str],
    *,
    draws: int,
    seed: int,
) -> np.ndarray:
    """Vectorized global-donor bootstrap with equal organ mass."""
    donors = sorted(donor_organ["donor_id"].astype(str).unique())
    donor_index = {donor: index for index, donor in enumerate(donors)}
    organ_index = {organ: index for index, organ in enumerate(ORGANS)}
    values = np.full(
        (len(donors), len(ORGANS), len(value_columns)), np.nan, dtype=np.float64
    )
    for row in donor_organ[
        ["donor_id", "organ", *value_columns]
    ].itertuples(index=False, name=None):
        donor, organ, *metrics = row
        values[donor_index[str(donor)], organ_index[str(organ)]] = metrics
    present = np.isfinite(values[:, :, 0]).astype(np.float64)
    if np.any(present.sum(axis=0) == 0):
        raise ValueError("bootstrap matrix lacks an organ")
    if not np.array_equal(np.isfinite(values).all(axis=2), present.astype(bool)):
        raise ValueError("bootstrap metrics have inconsistent missingness")
    numeric = np.nan_to_num(values)
    rng = np.random.default_rng(int(seed))
    output = np.empty((draws, len(value_columns)), dtype=np.float64)
    filled = 0
    attempts = 0
    probability = np.full(len(donors), 1.0 / len(donors))
    while filled < draws:
        attempts += 1
        if attempts > 1000:
            raise RuntimeError("could not draw donor bootstraps covering every organ")
        batch_size = min(1024, draws - filled)
        counts = rng.multinomial(len(donors), probability, size=batch_size)
        denominators = counts @ present
        valid = np.all(denominators > 0, axis=1)
        if not valid.any():
            continue
        counts = counts[valid]
        denominators = denominators[valid]
        take = min(len(counts), draws - filled)
        counts = counts[:take]
        denominators = denominators[:take]
        organ_means = np.empty((take, len(ORGANS), len(value_columns)))
        for metric in range(len(value_columns)):
            organ_means[:, :, metric] = (
                counts @ numeric[:, :, metric]
            ) / denominators
        output[filled : filled + take] = organ_means.mean(axis=1)
        filled += take
    return output


def holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    names = sorted(p_values, key=lambda name: (float(p_values[name]), name))
    adjusted: dict[str, float] = {}
    running = 0.0
    count = len(names)
    for rank, name in enumerate(names):
        value = min(1.0, (count - rank) * float(p_values[name]))
        running = max(running, value)
        adjusted[name] = running
    return {name: adjusted[name] for name in p_values}
