#!/usr/bin/env python3
"""Freeze calibration-only random-expert mappings before ARCHS4 expression access."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import numpy as np

try:
    from evaluation.freeze_gtex_to_archs4_candidates import ORGANS, SEEDS
except ModuleNotFoundError:
    from freeze_gtex_to_archs4_candidates import ORGANS, SEEDS


RANDOM_AXES = ("random_k8_p17", "random_k8_p42", "random_k8_p101")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _equal_study_weights(organs: np.ndarray, groups: np.ndarray, organ: str) -> np.ndarray:
    keep = organs == organ
    if not keep.any():
        raise ValueError(f"calibration scores lack organ {organ}")
    selected_groups = groups[keep]
    weights = np.zeros(int(keep.sum()), dtype=np.float64)
    unique_groups = np.unique(selected_groups)
    for group in unique_groups:
        rows = selected_groups == group
        weights[rows] = 1.0 / (len(unique_groups) * int(rows.sum()))
    return weights / weights.sum()


def freeze_random_controls(args: argparse.Namespace) -> dict:
    ledger_path = Path(args.candidate_ledger)
    root = Path(args.training_root)
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(output)
    if sha256_file(ledger_path) != args.expected_candidate_ledger_sha256:
        raise ValueError("candidate ledger SHA256 mismatch")
    ledger = json.loads(ledger_path.read_text())
    if (
        ledger.get("status") != "frozen_gtex_only_k8_candidate_ledger"
        or ledger.get("archs4_expression_accessed") is not False
        or ledger.get("seeds") != list(SEEDS)
    ):
        raise ValueError("candidate ledger is not a sealed three-seed K8 family")
    seed_by_id = {
        int(entry["seed"]): entry for entry in ledger["seed_candidates"]
    }
    mappings = {}
    for seed in SEEDS:
        seed_entry = seed_by_id[seed]
        mappings[str(seed)] = {}
        for axis in RANDOM_AXES:
            artifact = seed_entry["banks"][axis]["calibration_scores"]
            path = root / artifact["path"]
            if not path.is_file():
                raise FileNotFoundError(path)
            if sha256_file(path) != artifact["sha256"]:
                raise ValueError(f"calibration-score hash mismatch for seed {seed}/{axis}")
            with np.load(path, allow_pickle=False) as archive:
                required = {"sample_ids", "groups", "organs", "expert_mse"}
                missing = sorted(required - set(archive.files))
                if missing:
                    raise ValueError(
                        f"calibration scores {seed}/{axis} lack {missing}"
                    )
                sample_ids = archive["sample_ids"].astype(str)
                groups = archive["groups"].astype(str)
                organs = archive["organs"].astype(str)
                expert_mse = np.asarray(archive["expert_mse"], dtype=np.float64)
            if (
                len(sample_ids) != len(groups)
                or len(groups) != len(organs)
                or expert_mse.shape != (len(sample_ids), 8)
                or len(np.unique(sample_ids)) != len(sample_ids)
                or not np.isfinite(expert_mse).all()
            ):
                raise ValueError(f"invalid calibration-score arrays for {seed}/{axis}")
            by_organ = {}
            for organ in ORGANS:
                keep = organs == organ
                weights = _equal_study_weights(organs, groups, organ)
                scores = weights @ expert_mse[keep]
                selected = int(np.argmin(scores))
                by_organ[organ] = {
                    "selected_random_expert_index": selected,
                    "selected_random_expert": f"random_{selected}",
                    "calibration_study_macro_mse": [
                        float(value) for value in scores
                    ],
                    "calibration_samples": int(keep.sum()),
                    "calibration_groups": int(len(np.unique(groups[keep]))),
                }
            mappings[str(seed)][axis] = {
                "calibration_scores": artifact,
                "selection_split": "gtex_calibration",
                "uses_archs4": False,
                "uses_test_targets": False,
                "by_organ": by_organ,
            }
    report = {
        "schema_version": 1,
        "status": "frozen_gtex_calibration_random_control_mappings",
        "candidate_ledger_sha256": sha256_file(ledger_path),
        "seeds": list(SEEDS),
        "random_axes": list(RANDOM_AXES),
        "organs": list(ORGANS),
        "archs4_expression_accessed": False,
        "archs4_efficacy_scored": False,
        "selection_rule": (
            "minimum GTEx-calibration equal-connected-study MSE within each organ; "
            "ties resolve to the smallest expert index"
        ),
        "mappings": mappings,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, output)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-ledger", required=True)
    parser.add_argument("--expected-candidate-ledger-sha256", required=True)
    parser.add_argument("--training-root", required=True)
    parser.add_argument("--output", required=True)
    print(json.dumps(freeze_random_controls(parser.parse_args()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
