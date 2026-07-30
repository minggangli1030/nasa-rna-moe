#!/usr/bin/env python3
"""Evaluate the frozen random-adjusted Stage 2B refusal policy (B5)."""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.train_manifest import sha256_file  # noqa: E402


REQUIRED = (
    "substitution_report",
    "substitution_per_seed_edges",
    "additive_report",
    "additive_edges",
    "additive_per_seed",
    "stability_report",
    "stability_edges",
    "expert_similarity",
)


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _parse_paths(values: list[str]) -> dict[str, Path]:
    parsed = {}
    for value in values:
        name, separator, path_text = value.partition("=")
        if not separator:
            raise ValueError("refusal inputs must use NAME=PATH")
        parsed[name] = Path(path_text)
    if tuple(sorted(parsed)) != tuple(sorted(REQUIRED)):
        raise ValueError(f"refusal inputs must be exactly {REQUIRED}")
    return parsed


def _fit_predict_ridge(
    train_x: np.ndarray,
    train_y: np.ndarray,
    test_x: np.ndarray,
    ridge: float,
) -> np.ndarray:
    mean = train_x.mean(axis=0)
    scale = train_x.std(axis=0)
    scale[scale < 1e-8] = 1.0
    x = (train_x - mean) / scale
    test = (test_x - mean) / scale
    y_mean = float(train_y.mean())
    weights = np.linalg.solve(
        x.T @ x + ridge * np.eye(x.shape[1]),
        x.T @ (train_y - y_mean),
    )
    return y_mean + test @ weights


def _one_hot(values: pd.Series, levels: list[str]) -> np.ndarray:
    mapping = {value: index for index, value in enumerate(levels)}
    output = np.zeros((len(values), len(levels)), dtype=np.float64)
    for row, value in enumerate(values.astype(str)):
        output[row, mapping[value]] = 1.0
    return output


def _classification(actual: np.ndarray, flagged: np.ndarray) -> dict[str, float]:
    actual = np.asarray(actual, dtype=bool)
    flagged = np.asarray(flagged, dtype=bool)
    tp = int(np.sum(actual & flagged))
    fp = int(np.sum(~actual & flagged))
    tn = int(np.sum(~actual & ~flagged))
    fn = int(np.sum(actual & ~flagged))
    return {
        "precision": 0.0 if tp + fp == 0 else tp / (tp + fp),
        "recall": 0.0 if tp + fn == 0 else tp / (tp + fn),
        "specificity": 0.0 if tn + fp == 0 else tn / (tn + fp),
        "flagged_fraction": float(flagged.mean()),
        "true_positive": tp,
        "false_positive": fp,
        "true_negative": tn,
        "false_negative": fn,
    }


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    return float(pd.Series(a).rank().corr(pd.Series(b).rank()))


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    protocol_path = Path(args.protocol)
    if sha256_file(protocol_path) != args.expected_protocol_sha256:
        raise ValueError("Stage 2B protocol SHA256 mismatch")
    protocol = json.loads(protocol_path.read_text())
    paths = _parse_paths(args.refusal_input)
    for name, path in paths.items():
        if sha256_file(path) != protocol["inputs"]["refusal_inputs_sha256"][name]:
            raise ValueError(f"refusal input {name} differs from frozen protocol")
    for name in ("substitution_report", "additive_report", "stability_report"):
        report = json.loads(paths[name].read_text())
        if report.get("status") != "complete":
            raise ValueError(f"{name} is not a complete frozen result")

    substitution = pd.read_csv(paths["substitution_per_seed_edges"])
    required_columns = {
        "recipient",
        "donor",
        "seed",
        "effect_percent",
        "random_control_mean_effect_percent",
    }
    if not required_columns.issubset(substitution.columns):
        raise ValueError("substitution table lacks frozen estimand fields")
    substitution["excess_effect_percent"] = (
        substitution["effect_percent"]
        - substitution["random_control_mean_effect_percent"]
    )
    edge = (
        substitution.groupby(["recipient", "donor"], as_index=False)
        .agg(
            mean_opportunity_cost_percent=("effect_percent", "mean"),
            mean_excess_effect_percent=("excess_effect_percent", "mean"),
            excess_seed_sd_percent=("excess_effect_percent", "std"),
            negative_excess_seed_count=(
                "excess_effect_percent",
                lambda value: int(np.sum(np.asarray(value) < 0)),
            ),
        )
        .sort_values(["recipient", "donor"])
        .reset_index(drop=True)
    )
    if len(edge) != 56 or not np.all(edge["negative_excess_seed_count"].between(0, 3)):
        raise ValueError("substitution table is not the complete 56-edge/3-seed design")
    edge["robust_harmful"] = (
        (edge["mean_excess_effect_percent"] < 0)
        & (edge["negative_excess_seed_count"] == 3)
    )
    organs = sorted(set(edge["recipient"]) | set(edge["donor"]))
    if len(organs) != 8:
        raise ValueError("refusal design does not contain exact K8 organs")
    recipient = _one_hot(edge["recipient"], organs)
    donor = _one_hot(edge["donor"], organs)
    similarity_table = pd.read_csv(paths["expert_similarity"], index_col=0)
    if sorted(similarity_table.index.astype(str)) != organs:
        raise ValueError("expert-similarity rows do not match K8 organs")
    similarity = np.asarray(
        [
            similarity_table.loc[row.recipient, row.donor]
            for row in edge.itertuples()
        ],
        dtype=np.float64,
    )[:, None]
    designs = {
        "recipient_only": recipient,
        "donor_only": donor,
        "recipient_plus_donor": np.hstack([recipient, donor]),
        "recipient_plus_donor_plus_frozen_similarity": np.hstack(
            [recipient, donor, similarity]
        ),
    }
    ridge = float(protocol["b5_refusal"]["fixed_ridge_lambda"])
    predictions = {
        name: np.empty(len(edge), dtype=np.float64) for name in designs
    }
    fold_records = []
    for held in organs:
        test = edge["recipient"].eq(held) | edge["donor"].eq(held)
        train = ~test
        for name, matrix in designs.items():
            predictions[name][test] = _fit_predict_ridge(
                matrix[train],
                edge.loc[train, "mean_excess_effect_percent"].to_numpy(),
                matrix[test],
                ridge,
            )
        fold_records.append(
            {
                "held_out_organ": held,
                "train_edges": int(train.sum()),
                "test_edges": int(test.sum()),
            }
        )
    outcome = edge["mean_excess_effect_percent"].to_numpy(dtype=np.float64)
    model_metrics = {}
    for name, prediction in predictions.items():
        flagged = prediction < 0
        model_metrics[name] = {
            "leave_one_organ_out_mse": float(np.mean(np.square(outcome - prediction))),
            "pearson": float(np.corrcoef(outcome, prediction)[0, 1]),
            "spearman": _spearman(outcome, prediction),
            **_classification(edge["robust_harmful"].to_numpy(), flagged),
        }
    null_names = protocol["b5_refusal"]["null_models"]
    best_null = min(
        null_names,
        key=lambda name: model_metrics[name]["leave_one_organ_out_mse"],
    )
    feature_name = "recipient_plus_donor_plus_frozen_similarity"
    beats_null = (
        model_metrics[feature_name]["leave_one_organ_out_mse"]
        < model_metrics[best_null]["leave_one_organ_out_mse"]
    )
    nonvacuous = (
        model_metrics[feature_name]["flagged_fraction"]
        <= float(protocol["b5_refusal"]["maximum_flagged_fraction"])
    )

    additive = pd.read_csv(paths["additive_per_seed"])
    additive["random_mean_effect_percent"] = additive[
        "random_comparison_effects_percent"
    ].map(lambda value: float(np.mean(ast.literal_eval(value))))
    additive["excess_effect_percent"] = (
        additive["effect_vs_a1500_percent"]
        - additive["random_mean_effect_percent"]
    )
    additive_edge = (
        additive.groupby(["recipient", "donor"], as_index=False)
        .agg(
            mean_named_vs_random_excess_percent=("excess_effect_percent", "mean"),
            negative_excess_seed_count=(
                "excess_effect_percent",
                lambda value: int(np.sum(np.asarray(value) < 0)),
            ),
            mean_effect_vs_a2250_percent=("effect_vs_a2250_percent", "mean"),
        )
        .sort_values(["recipient", "donor"])
        .reset_index(drop=True)
    )
    lookup = {
        (row.recipient, row.donor): predictions[feature_name][index]
        for index, row in enumerate(edge.itertuples())
    }
    additive_prediction = np.asarray(
        [lookup[(row.recipient, row.donor)] for row in additive_edge.itertuples()]
    )
    additive_harmful = (
        (additive_edge["mean_named_vs_random_excess_percent"] < 0)
        & (additive_edge["negative_excess_seed_count"] == 3)
    ).to_numpy()
    additive_metrics = {
        "edges": len(additive_edge),
        "spearman_predicted_substitution_excess_vs_additive_named_random_excess": _spearman(
            additive_prediction,
            additive_edge["mean_named_vs_random_excess_percent"].to_numpy(),
        ),
        **_classification(additive_harmful, additive_prediction < 0),
        "a2250_reported_separately": additive_edge[
            [
                "recipient",
                "donor",
                "mean_effect_vs_a2250_percent",
            ]
        ].to_dict(orient="records"),
    }

    stability = pd.read_csv(paths["stability_edges"])
    stable_harmful = stability.loc[
        stability["classification"].astype(str).eq("stable_harmful"),
        ["recipient", "donor"],
    ].to_dict(orient="records")
    if beats_null and nonvacuous:
        decision = "learned_refusal_feature_model_authorized_for_phase_c"
        policy = {
            "type": "leave_one_organ_out_feature_model",
            "model": feature_name,
            "flag_if": "predicted donor-specific excess effect is below zero",
        }
    else:
        decision = "private_by_default_no_graph_wide_learned_rule"
        policy = {
            "type": "conservative_specific_edge_refusal",
            "replicated_harmful_edges": stable_harmful,
        }
    report = {
        "schema_version": 1,
        "status": "complete",
        "protocol_sha256": sha256_file(protocol_path),
        "outcome": protocol["b5_refusal"]["outcome"],
        "opportunity_cost_summary_percent": {
            "mean": float(edge["mean_opportunity_cost_percent"].mean()),
            "minimum": float(edge["mean_opportunity_cost_percent"].min()),
            "maximum": float(edge["mean_opportunity_cost_percent"].max()),
        },
        "donor_specific_excess_summary_percent": {
            "mean": float(edge["mean_excess_effect_percent"].mean()),
            "minimum": float(edge["mean_excess_effect_percent"].min()),
            "maximum": float(edge["mean_excess_effect_percent"].max()),
            "robust_harmful_edges": int(edge["robust_harmful"].sum()),
        },
        "folds": fold_records,
        "models": model_metrics,
        "best_null": best_null,
        "feature_model_beats_best_null": beats_null,
        "feature_model_nonvacuous": nonvacuous,
        "additive_holdout": additive_metrics,
        "decision": decision,
        "policy": policy,
        "claim_boundary": protocol["claim_boundary"],
        "completed_at_utc": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
    }
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    report_path = output_dir / "b5_refusal_report.json"
    edge_output = edge.copy()
    for name, prediction in predictions.items():
        edge_output[f"prediction_{name}"] = prediction
    edge_path = output_dir / "b5_edge_predictions.csv"
    additive_path = output_dir / "b5_additive_holdout.csv"
    _atomic_json(report_path, report)
    edge_output.to_csv(edge_path, index=False)
    additive_edge.assign(predicted_substitution_excess=additive_prediction).to_csv(
        additive_path, index=False
    )
    artifacts = (report_path, edge_path, additive_path)
    (output_dir / "IMMUTABLE_SHA256SUMS").write_text(
        "\n".join(f"{sha256_file(path)}  {path.name}" for path in artifacts)
        + "\n"
    )
    (output_dir / "COMPLETE").touch()
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--refusal-input", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser


def main() -> None:
    report = evaluate(build_parser().parse_args())
    print(
        json.dumps(
            {
                "status": report["status"],
                "decision": report["decision"],
                "feature_model_beats_best_null": report[
                    "feature_model_beats_best_null"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
