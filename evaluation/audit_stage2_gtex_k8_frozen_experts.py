#!/usr/bin/env python3
"""Audit frozen GTEx K8 expert utility on development calibration rows.

This is a development-only functional audit. It does not load ARCHS4 expression,
fit a model, select a seed, or estimate the later controlled retraining-transfer
effect. It summarizes how every already-frozen organ expert performs on every
recipient organ in the existing GTEx calibration score caches.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    from evaluation.freeze_gtex_to_archs4_candidates import ORGANS, SEEDS
except ModuleNotFoundError:
    from freeze_gtex_to_archs4_candidates import ORGANS, SEEDS


REQUIRED_ARRAYS = {
    "sample_ids",
    "groups",
    "organs",
    "sample_weights",
    "pooled_mse",
    "true_partition_mse",
    "oracle_mse",
    "expert_mse",
    "true_labels",
}


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    values = np.asarray(values, dtype=np.float64)
    weights = np.asarray(weights, dtype=np.float64)
    if values.shape != weights.shape:
        raise ValueError("weighted mean values and weights differ in shape")
    if not np.isfinite(values).all() or not np.isfinite(weights).all():
        raise ValueError("weighted mean received nonfinite input")
    if np.any(weights < 0) or float(weights.sum()) <= 0:
        raise ValueError("weighted mean requires positive total nonnegative weight")
    return float(np.average(values, weights=weights))


def _cosine_matrix(vectors: np.ndarray) -> np.ndarray:
    vectors = np.asarray(vectors, dtype=np.float64)
    norms = np.linalg.norm(vectors, axis=0)
    output = np.full((vectors.shape[1], vectors.shape[1]), np.nan, dtype=np.float64)
    valid = norms > 0
    for left in range(vectors.shape[1]):
        for right in range(vectors.shape[1]):
            if valid[left] and valid[right]:
                output[left, right] = float(
                    np.dot(vectors[:, left], vectors[:, right])
                    / (norms[left] * norms[right])
                )
    return output


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _seed_descriptor(ledger: dict[str, Any], seed: int) -> dict[str, Any]:
    matches = [
        item for item in ledger.get("seed_candidates", []) if item.get("seed") == seed
    ]
    if len(matches) != 1:
        raise ValueError(f"candidate ledger lacks exactly one seed {seed}")
    return matches[0]


def _load_cache(
    path: Path, expected_sha256: str, seed: int
) -> dict[str, np.ndarray]:
    if not path.is_file():
        raise FileNotFoundError(path)
    if sha256_file(path) != expected_sha256:
        raise ValueError(f"seed {seed} calibration-score SHA256 mismatch")
    with np.load(path, allow_pickle=False) as archive:
        missing = REQUIRED_ARRAYS - set(archive.files)
        if missing:
            raise ValueError(
                f"seed {seed} calibration scores lack {sorted(missing)}"
            )
        values = {name: np.asarray(archive[name]) for name in REQUIRED_ARRAYS}
    n_rows = len(values["sample_ids"])
    if (
        values["expert_mse"].shape != (n_rows, len(ORGANS))
        or values["true_labels"].shape != (n_rows,)
        or any(
            values[name].shape != (n_rows,)
            for name in (
                "groups",
                "organs",
                "sample_weights",
                "pooled_mse",
                "true_partition_mse",
                "oracle_mse",
            )
        )
    ):
        raise ValueError(f"seed {seed} calibration-score shapes violate K8 contract")
    numeric = (
        "sample_weights",
        "pooled_mse",
        "true_partition_mse",
        "oracle_mse",
        "expert_mse",
    )
    if not all(np.isfinite(values[name]).all() for name in numeric):
        raise ValueError(f"seed {seed} calibration scores contain nonfinite values")
    if np.any(values["sample_weights"] < 0):
        raise ValueError(f"seed {seed} calibration weights are negative")
    organs = values["organs"].astype(str)
    labels = values["true_labels"].astype(np.int64)
    expected_labels = np.asarray([ORGANS.index(organ) for organ in organs])
    if not np.array_equal(labels, expected_labels):
        raise ValueError(f"seed {seed} true labels differ from frozen organ order")
    if set(organs) != set(ORGANS):
        raise ValueError(f"seed {seed} calibration rows do not cover every organ")
    values["sample_ids"] = values["sample_ids"].astype(str)
    values["groups"] = values["groups"].astype(str)
    values["organs"] = organs
    values["true_labels"] = labels
    return values


def audit(args: argparse.Namespace) -> dict[str, Any]:
    ledger_path = Path(args.candidate_ledger)
    training_root = Path(args.training_root)
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise FileExistsError(output_dir)
    if not ledger_path.is_file():
        raise FileNotFoundError(ledger_path)
    ledger_sha256 = sha256_file(ledger_path)
    if ledger_sha256 != args.expected_candidate_ledger_sha256:
        raise ValueError("candidate ledger SHA256 mismatch")
    ledger = json.loads(ledger_path.read_text())
    if (
        ledger.get("status") != "frozen_gtex_only_k8_candidate_ledger"
        or ledger.get("organs") != list(ORGANS)
        or ledger.get("best_seed_selection_allowed") is not False
        or ledger.get("fine_tuning_exposure") != "zero"
    ):
        raise ValueError("candidate ledger is not the frozen all-seed GTEx K8 family")

    seed_matrices: dict[int, np.ndarray] = {}
    seed_true_gain: dict[int, float] = {}
    input_hashes: dict[str, str] = {}
    shared_ids = shared_groups = shared_organs = None
    for seed in SEEDS:
        descriptor = _seed_descriptor(ledger, seed)
        scores = descriptor["banks"]["organ_k8"]["calibration_scores"]
        path = training_root / scores["path"]
        cache = _load_cache(path, scores["sha256"], seed)
        input_hashes[str(seed)] = scores["sha256"]
        if shared_ids is None:
            shared_ids = cache["sample_ids"]
            shared_groups = cache["groups"]
            shared_organs = cache["organs"]
        elif not (
            np.array_equal(cache["sample_ids"], shared_ids)
            and np.array_equal(cache["groups"], shared_groups)
            and np.array_equal(cache["organs"], shared_organs)
        ):
            raise ValueError("calibration caches do not share identical rows")

        matrix = np.empty((len(ORGANS), len(ORGANS)), dtype=np.float64)
        for recipient_index, recipient in enumerate(ORGANS):
            keep = cache["organs"] == recipient
            weights = cache["sample_weights"][keep]
            pooled = _weighted_mean(cache["pooled_mse"][keep], weights)
            for expert_index in range(len(ORGANS)):
                expert = _weighted_mean(cache["expert_mse"][keep, expert_index], weights)
                matrix[recipient_index, expert_index] = 100.0 * (
                    pooled - expert
                ) / pooled
        pooled_all = _weighted_mean(cache["pooled_mse"], cache["sample_weights"])
        true_all = _weighted_mean(
            cache["true_partition_mse"], cache["sample_weights"]
        )
        seed_true_gain[seed] = 100.0 * (pooled_all - true_all) / pooled_all
        seed_matrices[seed] = matrix

    stacked = np.stack([seed_matrices[seed] for seed in SEEDS], axis=0)
    mean_matrix = stacked.mean(axis=0)
    sd_matrix = stacked.std(axis=0, ddof=1)
    positive_seed_count = np.count_nonzero(stacked > 0, axis=0)
    cosine = _cosine_matrix(mean_matrix)

    output_dir.mkdir(parents=True)
    mean_frame = pd.DataFrame(
        mean_matrix, index=pd.Index(ORGANS, name="recipient_organ"), columns=ORGANS
    )
    mean_frame.columns.name = "frozen_expert"
    sd_frame = pd.DataFrame(
        sd_matrix, index=pd.Index(ORGANS, name="recipient_organ"), columns=ORGANS
    )
    sd_frame.columns.name = "frozen_expert"
    direction_frame = pd.DataFrame(
        positive_seed_count,
        index=pd.Index(ORGANS, name="recipient_organ"),
        columns=ORGANS,
    )
    direction_frame.columns.name = "frozen_expert"
    cosine_frame = pd.DataFrame(
        cosine, index=pd.Index(ORGANS, name="expert"), columns=ORGANS
    )
    cosine_frame.columns.name = "expert"
    outputs = {
        "mean_relative_mse_improvement_percent": mean_frame,
        "seed_sd_relative_mse_improvement_percent": sd_frame,
        "positive_seed_count": direction_frame,
        "expert_utility_cosine_similarity": cosine_frame,
    }
    output_hashes: dict[str, str] = {}
    for name, frame in outputs.items():
        path = output_dir / f"{name}.csv"
        frame.to_csv(path, float_format="%.10g")
        output_hashes[path.name] = sha256_file(path)

    recipient_summary: dict[str, Any] = {}
    for recipient_index, recipient in enumerate(ORGANS):
        row = mean_matrix[recipient_index]
        order = np.argsort(-row, kind="stable")
        named_index = recipient_index
        recipient_summary[recipient] = {
            "named_expert_relative_mse_improvement_percent": float(row[named_index]),
            "named_expert_positive_seed_count": int(
                positive_seed_count[recipient_index, named_index]
            ),
            "named_expert_rank_among_8": int(
                np.flatnonzero(order == named_index)[0] + 1
            ),
            "best_expert": ORGANS[int(order[0])],
            "best_expert_relative_mse_improvement_percent": float(row[order[0]]),
        }

    report = {
        "schema_version": 1,
        "status": "complete",
        "analysis": "stage2_gtex_k8_frozen_expert_cross_dispatch_audit",
        "development_only": True,
        "data_source": "GTEx calibration score caches",
        "archs4_expression_loaded": False,
        "completed_archs4_lockbox_used_for_selection": False,
        "model_fitting_performed": False,
        "best_seed_selection_performed": False,
        "controlled_retraining_transfer_estimated": False,
        "interpretation": (
            "cross-dispatch utility of already-frozen experts; not the causal effect "
            "of adding donor-organ training data"
        ),
        "seeds": list(SEEDS),
        "organs": list(ORGANS),
        "calibration_rows": int(len(shared_ids)),
        "calibration_groups": int(len(np.unique(shared_groups))),
        "seed_true_dispatch_relative_mse_improvement_percent": {
            str(seed): seed_true_gain[seed] for seed in SEEDS
        },
        "mean_true_dispatch_relative_mse_improvement_percent": float(
            np.mean(list(seed_true_gain.values()))
        ),
        "recipient_summary": recipient_summary,
        "hashes": {
            "candidate_ledger_sha256": ledger_sha256,
            "input_calibration_scores_sha256": input_hashes,
            "outputs": output_hashes,
        },
    }
    report_path = output_dir / "audit_report.json"
    _atomic_json(report_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-ledger", required=True)
    parser.add_argument("--expected-candidate-ledger-sha256", required=True)
    parser.add_argument("--training-root", required=True)
    parser.add_argument("--output-dir", required=True)
    print(json.dumps(audit(parser.parse_args()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
