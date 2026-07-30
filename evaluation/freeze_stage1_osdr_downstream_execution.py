#!/usr/bin/env python3
"""Bind the downstream feature/evaluator implementations before model outcomes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    protocol = Path(args.protocol)
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(output)
    sources = {
        "feature_cache": Path("evaluation/cache_stage1_osdr_downstream_features.py"),
        "evaluator": Path("evaluation/evaluate_stage1_osdr_downstream.py"),
        "continuation": Path("runs/continue_stage1_osdr_downstream.sh"),
    }
    manifest = {
        "schema_version": 1,
        "status": "frozen_stage1_osdr_downstream_execution",
        "protocol_sha256": sha256_file(protocol),
        "frozen_before_model_outcomes": True,
        "implementation_sha256": {
            name: sha256_file(path) for name, path in sources.items()
        },
        "cache": {
            "seeds": [17, 42, 101],
            "conditions": [
                "pooled",
                "pooled_adapter",
                "true_organ",
                "blind_router_hard",
                "blind_router_soft",
            ],
            "batch_size": 4,
        },
        "smoke": {
            "seeds": [17],
            "outer_folds": 2,
            "inner_folds": 2,
            "grid": [
                {"C": 0.1, "l1_ratio": 0.0},
                {"C": 0.1, "l1_ratio": 1.0},
                {"C": 1.0, "l1_ratio": 0.0},
                {"C": 1.0, "l1_ratio": 1.0},
            ],
            "role": "mechanical only; cannot select a representation",
        },
        "full": {
            "seeds": [17, 42, 101],
            "outer_folds": 5,
            "inner_folds": 3,
            "grid": [
                {"C": c_value, "l1_ratio": l1_ratio}
                for c_value in (0.01, 0.1, 1.0, 10.0)
                for l1_ratio in (0.0, 0.5, 1.0)
            ],
            "report_all_seeds": True,
            "best_seed_selection": False,
        },
        "interpretation": {
            "primary_comparison": "true_organ versus pooled AUROC, all seeds",
            "deployable_comparisons": [
                "blind_router_hard versus pooled",
                "blind_router_soft versus pooled",
            ],
            "must_also_compare": ["raw_expression", "pca_64"],
            "positive_development_signal": (
                "positive true-organ minus pooled AUROC in all three seeds; "
                "no universality or final-confirmation claim"
            ),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(output), "sha256": sha256_file(output)}, indent=2))


if __name__ == "__main__":
    main()
