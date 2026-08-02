#!/usr/bin/env python3
"""Frozen D1 audit separating OSDR domain shift from representation failure."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from core.train_manifest import load_expression_rows
from evaluation.evaluate_osdr import load_coverage_artifact
from evaluation.evaluate_stage1_osdr_downstream import (
    _fit,
    _fit_grid_path,
    _score,
    _transform,
)


METADATA_COLUMNS = {"sample_name", "condition", "spaceflight", "study_id", "species"}
SEEDS = (17, 42, 101)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _parse_seed_paths(values: list[str], label: str) -> dict[int, Path]:
    parsed: dict[int, Path] = {}
    for value in values:
        seed_text, separator, path_text = value.partition("=")
        if not separator:
            raise ValueError(f"{label} must use SEED=PATH")
        parsed[int(seed_text)] = Path(path_text)
    if tuple(sorted(parsed)) != SEEDS:
        raise ValueError(f"{label} must provide exactly {SEEDS}")
    return parsed


def effective_rank(values: np.ndarray) -> float:
    centered = np.asarray(values, dtype=np.float64) - np.mean(values, axis=0)
    singular = np.linalg.svd(centered, compute_uv=False)
    variance = np.square(singular)
    total = float(variance.sum())
    if total <= 0:
        return 0.0
    probability = variance / total
    active = probability[probability > 0]
    return float(np.exp(-np.sum(active * np.log(active))))


def distribution_metrics(values: np.ndarray, relative_dead_threshold: float) -> dict[str, float]:
    matrix = np.asarray(values, dtype=np.float64)
    if matrix.ndim != 2 or not np.isfinite(matrix).all():
        raise ValueError("embedding must be a finite 2D matrix")
    standard_deviation = matrix.std(axis=0, ddof=1)
    positive = standard_deviation[standard_deviation > 0]
    reference = float(np.median(positive)) if len(positive) else 0.0
    dead_limit = max(reference * relative_dead_threshold, 1e-12)
    centered = matrix - matrix.mean(axis=0)
    singular = np.linalg.svd(centered, compute_uv=False)
    variance = np.square(singular)
    norms = np.linalg.norm(matrix, axis=1)
    normalized = matrix / np.maximum(norms[:, None], 1e-12)
    cosine = normalized @ normalized.T
    pair_count = len(matrix) * (len(matrix) - 1)
    mean_pairwise = 0.0 if pair_count == 0 else float((cosine.sum() - len(matrix)) / pair_count)
    return {
        "dimensions": int(matrix.shape[1]),
        "dead_dimensions": int(np.sum(standard_deviation <= dead_limit)),
        "dead_dimension_fraction": float(np.mean(standard_deviation <= dead_limit)),
        "effective_rank": effective_rank(matrix),
        "pc1_variance_fraction": 0.0 if variance.sum() <= 0 else float(variance[0] / variance.sum()),
        "mean_pairwise_cosine_similarity": mean_pairwise,
        "median_dimension_sd": float(np.median(standard_deviation)),
    }


def distribution_verdict(
    *, rank_ratio: float, median_abs_z: float, dead_fraction: float, thresholds: dict[str, float]
) -> str:
    if (
        rank_ratio < thresholds["out_of_distribution_rank_ratio"]
        or median_abs_z > thresholds["out_of_distribution_median_abs_z"]
        or dead_fraction > thresholds["out_of_distribution_dead_fraction"]
    ):
        return "ENCODER_OUT_OF_DISTRIBUTION"
    if (
        rank_ratio >= thresholds["in_distribution_rank_ratio"]
        and median_abs_z <= thresholds["in_distribution_median_abs_z"]
    ):
        return "ENCODER_IN_DISTRIBUTION"
    return "ENCODER_MARGINAL"


def balanced_group_splits(y: np.ndarray, groups: np.ndarray, folds: int) -> list[tuple[np.ndarray, np.ndarray]]:
    """Assign pure-label studies per class so every train and test fold has both labels."""
    labels = np.asarray(y, dtype=np.int64)
    group_values = np.asarray(groups, dtype=str)
    unique_groups = sorted(np.unique(group_values).tolist())
    records: dict[int, list[tuple[str, int]]] = {}
    for group in unique_groups:
        selected = group_values == group
        group_labels = np.unique(labels[selected])
        if len(group_labels) != 1:
            raise ValueError(f"positive-control study {group} contains multiple organ labels")
        records.setdefault(int(group_labels[0]), []).append((group, int(selected.sum())))
    if len(records) != 2 or any(len(items) < folds for items in records.values()):
        raise ValueError("insufficient pure-label studies for balanced grouped folds")
    assigned: list[list[str]] = [[] for _ in range(folds)]
    for label in sorted(records):
        totals = np.zeros(folds, dtype=np.int64)
        for group, count in sorted(records[label], key=lambda item: (-item[1], item[0])):
            fold = int(np.argmin(totals))
            assigned[fold].append(group)
            totals[fold] += count
    output = []
    for test_groups in assigned:
        test = np.flatnonzero(np.isin(group_values, test_groups))
        train = np.flatnonzero(~np.isin(group_values, test_groups))
        if set(labels[train]) != {0, 1} or set(labels[test]) != {0, 1}:
            raise RuntimeError("balanced grouped split lost a class")
        if set(group_values[train]) & set(group_values[test]):
            raise RuntimeError("balanced grouped split leaked a study")
        output.append((train, test))
    return output


def nested_balanced_group_evaluate(
    x: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    *,
    outer_folds: int,
    inner_folds: int,
    pca_components: int | None,
    grid: tuple[tuple[float, float], ...],
) -> dict[str, Any]:
    probabilities = np.full(len(y), np.nan, dtype=np.float64)
    predictions = np.full(len(y), -1, dtype=np.int64)
    fold_records = []
    for outer_index, (train_index, test_index) in enumerate(
        balanced_group_splits(y, groups, outer_folds)
    ):
        candidates = {item: [] for item in grid}
        iterations = {item: [] for item in grid}
        for inner_train, inner_test in balanced_group_splits(
            y[train_index], groups[train_index], inner_folds
        ):
            a, b = train_index[inner_train], train_index[inner_test]
            train, test = _transform(x[a], x[b], pca_components=pca_components)
            path = _fit_grid_path(train, y[a], test, grid)
            for item, (probability, n_iter) in path.items():
                from sklearn.metrics import roc_auc_score

                candidates[item].append(float(roc_auc_score(y[b], probability)))
                iterations[item].append(int(n_iter))
        ranked = [
            {
                "C": float(c_value),
                "l1_ratio": float(l1_ratio),
                "mean_inner_auroc": float(np.mean(candidates[(c_value, l1_ratio)])),
                "max_inner_iterations": int(max(iterations[(c_value, l1_ratio)])),
            }
            for c_value, l1_ratio in grid
        ]
        selected = sorted(
            ranked,
            key=lambda item: (-item["mean_inner_auroc"], item["C"], item["l1_ratio"]),
        )[0]
        train, test = _transform(
            x[train_index], x[test_index], pca_components=pca_components
        )
        probability, prediction, n_iter = _fit(
            train,
            y[train_index],
            test,
            c_value=selected["C"],
            l1_ratio=selected["l1_ratio"],
        )
        probabilities[test_index] = probability
        predictions[test_index] = prediction
        fold_records.append(
            {
                "fold": outer_index,
                "train_studies": sorted(np.unique(groups[train_index]).astype(str).tolist()),
                "test_studies": sorted(np.unique(groups[test_index]).astype(str).tolist()),
                "selected": selected,
                "outer_fit_iterations": int(n_iter),
                "metrics": _score(y[test_index], probability, prediction),
            }
        )
    if not np.isfinite(probabilities).all() or np.any(predictions < 0):
        raise RuntimeError("positive control did not score every row")
    return {
        "pooled_out_of_fold": _score(y, probabilities, predictions),
        "folds": fold_records,
        "probabilities": probabilities,
        "predictions": predictions,
    }


def organ_recovery_verdict(raw_accuracy: float, ratios: list[float], thresholds: dict[str, float]) -> str:
    if raw_accuracy < thresholds["minimum_raw_balanced_accuracy"]:
        return "D1B_INCONCLUSIVE_LOW_RAW"
    if min(ratios) >= thresholds["recovers_organ_ratio"]:
        return "ENCODER_RECOVERS_ORGAN"
    if max(ratios) < thresholds["degenerate_ratio"]:
        return "ENCODER_DEGENERATE"
    return "ENCODER_PARTIAL"


def input_domain_verdict(
    *, imputed_fraction: float, constant_fraction: float, normalization_identical: bool,
    thresholds: dict[str, float],
) -> str:
    worst = max(imputed_fraction, constant_fraction)
    if not normalization_identical or worst > thresholds["shift_fraction"]:
        return "INPUT_DOMAIN_SHIFT"
    if worst <= thresholds["ok_fraction"]:
        return "INPUT_DOMAIN_OK"
    return "INPUT_DOMAIN_MARGINAL"


def aggregate_verdict(d1a: str, d1b: str, d1c: str) -> str:
    if (
        d1a == "ENCODER_OUT_OF_DISTRIBUTION"
        or d1b == "ENCODER_DEGENERATE"
        or d1c == "INPUT_DOMAIN_SHIFT"
    ):
        return "CROSS_SPECIES_ENCODER_BREAKDOWN"
    if (
        d1a == "ENCODER_IN_DISTRIBUTION"
        and d1b == "ENCODER_RECOVERS_ORGAN"
        and d1c == "INPUT_DOMAIN_OK"
    ):
        return "ENCODER_TRANSFERS_OBJECTIVE_LIMIT"
    return "INCONCLUSIVE_MIXED"


def _verify_inputs(protocol: dict[str, Any], paths: dict[str, Path]) -> None:
    for key, path in paths.items():
        expected = protocol["inputs"][key]
        actual = sha256_file(path)
        if actual != expected:
            raise ValueError(f"input hash mismatch for {key}: {actual} != {expected}")


def _load_feature_archives(
    root: Path, protocol: dict[str, Any]
) -> dict[int, dict[str, np.ndarray]]:
    output = {}
    for seed in SEEDS:
        path = root / f"seed{seed}_features.npz"
        if sha256_file(path) != protocol["inputs"]["osdr_feature_sha256"][str(seed)]:
            raise ValueError(f"OSDR feature cache differs for seed {seed}")
        with np.load(path, allow_pickle=False) as archive:
            output[seed] = {name: archive[name] for name in archive.files}
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--osdr-feature-root", required=True)
    parser.add_argument("--osdr-cohort-root", required=True)
    parser.add_argument("--gtex-expression", required=True)
    parser.add_argument("--gtex-manifest", required=True)
    parser.add_argument("--gtex-extraction-report", required=True)
    parser.add_argument("--axis-definitions", required=True)
    parser.add_argument("--canonical-genes", required=True)
    parser.add_argument("--training-ortholog-map", required=True)
    parser.add_argument("--osdr-ortholog-table", required=True)
    parser.add_argument("--mouse-exon-lengths", required=True)
    parser.add_argument("--gtex-cache", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()

    protocol_path = Path(args.protocol)
    if sha256_file(protocol_path) != args.expected_protocol_sha256:
        raise ValueError("D1 protocol SHA256 mismatch")
    protocol = json.loads(protocol_path.read_text())
    if protocol.get("status") != "frozen_before_encoder_validity_audit":
        raise ValueError("D1 protocol is not frozen")
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise FileExistsError(output_dir)
    output_dir.mkdir(parents=True)

    cohort_root = Path(args.osdr_cohort_root)
    fixed_paths = {
        "osdr_expression_sha256": cohort_root / "osdr_expression_v3.parquet",
        "osdr_coverage_sha256": cohort_root / "osdr_coverage_v3.npz",
        "osdr_retained_sha256": cohort_root / "retained_cohort.csv",
        "osdr_manifest_sha256": cohort_root / "osdr_manifest_v3.json",
        "gtex_expression_sha256": Path(args.gtex_expression),
        "gtex_manifest_sha256": Path(args.gtex_manifest),
        "gtex_extraction_report_sha256": Path(args.gtex_extraction_report),
        "axis_definitions_sha256": Path(args.axis_definitions),
        "canonical_genes_sha256": Path(args.canonical_genes),
        "training_ortholog_map_sha256": Path(args.training_ortholog_map),
        "osdr_ortholog_table_sha256": Path(args.osdr_ortholog_table),
        "mouse_exon_lengths_sha256": Path(args.mouse_exon_lengths),
    }
    _verify_inputs(protocol, fixed_paths)
    features = _load_feature_archives(Path(args.osdr_feature_root), protocol)
    gtex_paths = _parse_seed_paths(args.gtex_cache, "GTEx cache")
    gtex_archives = {}
    for seed, path in gtex_paths.items():
        if sha256_file(path) != protocol["inputs"]["gtex_cache_sha256"][str(seed)]:
            raise ValueError(f"GTEx canonical cache differs for seed {seed}")
        with np.load(path, allow_pickle=False) as archive:
            gtex_archives[seed] = {"h_canon": archive["h_canon"]}

    reference = features[17]
    sample_ids = reference["sample_ids"].astype(str)
    groups = reference["groups"].astype(str)
    organs = reference["organs"].astype(str)
    for seed, archive in features.items():
        for key, expected in (("sample_ids", sample_ids), ("groups", groups), ("organs", organs)):
            if not np.array_equal(archive[key].astype(str), expected):
                raise ValueError(f"OSDR feature {key} differs for seed {seed}")

    manifest = pd.read_parquet(args.gtex_manifest)
    training = (
        manifest.loc[
            manifest["split"].astype(str).eq("train") & manifest["balanced_train"].astype(bool)
        ]
        .sort_values("sample_id")
        .reset_index(drop=True)
    )
    if len(training) != int(protocol["design"]["gtex_training_rows"]):
        raise ValueError("GTEx training membership differs")
    draw_size = min(len(sample_ids), int(protocol["design"]["distribution_draw_rows"]))
    if args.smoke:
        draw_size = min(draw_size, 64)
    rng = np.random.default_rng(int(protocol["design"]["distribution_draw_seed"]))
    draw = np.sort(rng.choice(len(training), size=draw_size, replace=False))

    organ_order = protocol["design"]["organ_order"]
    organ_one_hot = np.eye(len(organ_order), dtype=np.float32)[
        [organ_order.index(value) for value in organs]
    ]
    d1a_seeds = {}
    condition_metrics = {}
    thresholds_a = protocol["thresholds"]["d1a"]
    for seed in SEEDS:
        gtex_hidden = gtex_archives[seed]["h_canon"][draw]
        pooled = features[seed]["feature__pooled_hidden"]
        gtex_metric = distribution_metrics(gtex_hidden, thresholds_a["relative_dead_threshold"])
        osdr_metric = distribution_metrics(pooled, thresholds_a["relative_dead_threshold"])
        gtex_sd = gtex_hidden.std(axis=0, ddof=1).astype(np.float64)
        z = (pooled.mean(axis=0) - gtex_hidden.mean(axis=0)) / np.maximum(gtex_sd, 1e-8)
        rank_ratio = osdr_metric["effective_rank"] / max(gtex_metric["effective_rank"], 1e-12)
        median_abs_z = float(np.median(np.abs(z)))
        verdict = distribution_verdict(
            rank_ratio=rank_ratio,
            median_abs_z=median_abs_z,
            dead_fraction=osdr_metric["dead_dimension_fraction"],
            thresholds=thresholds_a,
        )
        d1a_seeds[str(seed)] = {
            "gtex_pooled_hidden": gtex_metric,
            "osdr_pooled_hidden": osdr_metric,
            "effective_rank_ratio": rank_ratio,
            "median_abs_mean_z": median_abs_z,
            "fraction_dimensions_abs_mean_z_gt_3": float(np.mean(np.abs(z) > 3)),
            "verdict": verdict,
        }
        arrays = {
            name: features[seed][f"feature__{name}"]
            for name in protocol["design"]["stored_embedding_conditions"]
        }
        arrays["pooled_hidden_plus_organ_label"] = np.concatenate([pooled, organ_one_hot], axis=1)
        condition_metrics[str(seed)] = {
            name: distribution_metrics(value, thresholds_a["relative_dead_threshold"])
            for name, value in arrays.items()
        }
    seed_verdicts = [d1a_seeds[str(seed)]["verdict"] for seed in SEEDS]
    d1a_verdict = (
        "ENCODER_OUT_OF_DISTRIBUTION"
        if "ENCODER_OUT_OF_DISTRIBUTION" in seed_verdicts
        else "ENCODER_IN_DISTRIBUTION"
        if all(value == "ENCODER_IN_DISTRIBUTION" for value in seed_verdicts)
        else "ENCODER_MARGINAL"
    )

    expression = pd.read_parquet(cohort_root / "osdr_expression_v3.parquet")
    expression.index = expression.index.astype(str)
    expression = expression.reindex(sample_ids)
    genes = [column for column in expression.columns if column not in METADATA_COLUMNS]
    raw = expression[genes].to_numpy(dtype=np.float32)
    if not np.isfinite(raw).all():
        raise ValueError("OSDR expression is nonfinite")
    positive = np.isin(organs, protocol["design"]["positive_control_organs"])
    positive_organs = organs[positive]
    y_organ = (positive_organs == protocol["design"]["positive_control_positive_organ"]).astype(np.int64)
    positive_groups = groups[positive]
    grid = tuple(
        (float(item["C"]), float(item["l1_ratio"])) for item in protocol["design"]["head_grid"]
    )
    if args.smoke:
        grid = ((0.1, 0.0), (1.0, 1.0))
    outer_folds = int(protocol["design"]["positive_control_outer_folds"])
    inner_folds = int(protocol["design"]["positive_control_inner_folds"])
    d1b_results = {}
    for name, values, components in (
        ("raw_expression", raw[positive], None),
        ("pca_64", raw[positive], 64),
    ):
        result = nested_balanced_group_evaluate(
            values,
            y_organ,
            positive_groups,
            outer_folds=outer_folds,
            inner_folds=inner_folds,
            pca_components=components,
            grid=grid,
        )
        d1b_results[name] = {
            key: value for key, value in result.items() if key not in {"probabilities", "predictions"}
        }
    for seed in SEEDS:
        for condition in protocol["design"]["stored_embedding_conditions"]:
            result = nested_balanced_group_evaluate(
                features[seed][f"feature__{condition}"][positive],
                y_organ,
                positive_groups,
                outer_folds=outer_folds,
                inner_folds=inner_folds,
                pca_components=None,
                grid=grid,
            )
            d1b_results[f"seed{seed}__{condition}"] = {
                key: value for key, value in result.items() if key not in {"probabilities", "predictions"}
            }
    raw_accuracy = d1b_results["raw_expression"]["pooled_out_of_fold"]["balanced_accuracy"]
    pooled_ratios = [
        d1b_results[f"seed{seed}__pooled_hidden"]["pooled_out_of_fold"]["balanced_accuracy"]
        / max(raw_accuracy, 1e-12)
        for seed in SEEDS
    ]
    d1b_verdict = organ_recovery_verdict(
        raw_accuracy,
        pooled_ratios,
        protocol["thresholds"]["d1b"],
    )
    contingency = pd.crosstab(groups, organs)
    contingency_path = output_dir / "organ_by_study.csv"
    contingency.to_csv(contingency_path)

    all_expression = pd.read_parquet(cohort_root / "osdr_expression_v3.parquet")
    all_expression.index = all_expression.index.astype(str)
    all_sample_ids = all_expression.index.to_numpy(dtype=str)
    coverage_all = load_coverage_artifact(
        cohort_root / "osdr_coverage_v3.npz", all_sample_ids, genes
    )
    positions = pd.Index(all_sample_ids).get_indexer(sample_ids)
    if np.any(positions < 0):
        raise ValueError("OSDR retained membership missing from coverage")
    coverage = coverage_all[positions]
    with np.load(args.axis_definitions, allow_pickle=False) as archive:
        score_indices = archive["score_gene_indices"].astype(np.int64)
        axis_genes = archive["gene_names"].astype(str).tolist()
    if axis_genes != genes:
        raise ValueError("OSDR genes differ from axis definitions")
    non_score = np.setdiff1d(np.arange(len(genes), dtype=np.int64), score_indices)
    gtex_values, gtex_info = load_expression_rows(
        args.gtex_expression, training.iloc[draw]["sample_id"].astype(str).tolist()
    )
    if list(gtex_info.gene_columns) != genes:
        raise ValueError("GTEx genes differ from OSDR genes")
    gtex_model_input = np.log1p(gtex_values).astype(np.float32)
    gtex_model_input[:, score_indices] = -10.0
    osdr_model_input = raw.copy()
    osdr_model_input[~coverage] = -10.0
    osdr_model_input[:, score_indices] = -10.0
    gtex_sd = gtex_model_input[:, non_score].std(axis=0, ddof=1).astype(np.float64)
    input_z = (
        osdr_model_input[:, non_score].mean(axis=0)
        - gtex_model_input[:, non_score].mean(axis=0)
    ) / np.maximum(gtex_sd, 1e-8)
    missing_entry_fraction = float(np.mean(~coverage[:, non_score]))
    constant_gene_fraction = float(
        np.mean(np.ptp(osdr_model_input[:, non_score], axis=0) == 0)
    )
    absent_all_fraction = float(np.mean(~coverage[:, non_score].any(axis=0)))
    osdr_manifest = json.loads((cohort_root / "osdr_manifest_v3.json").read_text())
    gtex_report = json.loads(Path(args.gtex_extraction_report).read_text())
    normalization_identical = bool(
        osdr_manifest.get("expression_space") == "log1p_tpm"
        and gtex_report.get("expression_space") == "tpm"
        and gtex_report.get("log_transform_applied") is False
        and protocol["design"]["gtex_model_transform"] == "numpy.log1p_exactly_once"
    )
    canonical = [line.strip() for line in Path(args.canonical_genes).read_text().splitlines() if line.strip()]
    training_map = pd.read_csv(args.training_ortholog_map, sep="\t").dropna(
        subset=["Gene name", "Human gene name"]
    )
    mapped_human = set(training_map["Human gene name"].astype(str).str.strip())
    homology = pd.read_csv(args.osdr_ortholog_table).dropna(subset=["Gene name", "Mouse homology type"])
    homology["Gene name"] = homology["Gene name"].astype(str).str.strip()
    homology = homology[homology["Gene name"].isin(canonical)]
    homology_counts = (
        homology.groupby("Mouse homology type")["Gene name"].nunique().sort_index().astype(int).to_dict()
    )
    d1c_verdict = input_domain_verdict(
        imputed_fraction=missing_entry_fraction,
        constant_fraction=constant_gene_fraction,
        normalization_identical=normalization_identical,
        thresholds=protocol["thresholds"]["d1c"],
    )
    d1c = {
        "verdict": d1c_verdict,
        "model_gene_panel": len(canonical),
        "training_one_to_one_mapped_panel_genes": int(len(set(canonical) & mapped_human)),
        "training_one_to_one_mapped_fraction": float(len(set(canonical) & mapped_human) / len(canonical)),
        "osdr_reference_homology_type_unique_human_genes": homology_counts,
        "retained_samples": len(sample_ids),
        "mean_non_score_missing_entry_fraction": missing_entry_fraction,
        "non_score_genes_absent_in_all_samples_fraction": absent_all_fraction,
        "non_score_constant_gene_fraction": constant_gene_fraction,
        "median_abs_model_input_mean_z": float(np.median(np.abs(input_z))),
        "fraction_non_score_dimensions_abs_mean_z_gt_3": float(np.mean(np.abs(input_z) > 3)),
        "absent_gene_policy": "set to mask_token_-10_using_per_sample_coverage",
        "osdr_expression_space": osdr_manifest.get("expression_space"),
        "osdr_normalization_order": osdr_manifest.get("normalization_order"),
        "gtex_expression_space_on_disk": gtex_report.get("expression_space"),
        "gtex_model_transform": protocol["design"]["gtex_model_transform"],
        "normalization_identical_at_model_input_value_space": normalization_identical,
    }

    verdict = aggregate_verdict(d1a_verdict, d1b_verdict, d1c_verdict)
    report = {
        "schema_version": 1,
        "status": "complete",
        "role": "osdr_encoder_validity_development_audit",
        "smoke": bool(args.smoke),
        "protocol_sha256": sha256_file(protocol_path),
        "verdict": verdict,
        "d1a": {
            "verdict": d1a_verdict,
            "seed_reports": d1a_seeds,
            "osdr_condition_metrics": condition_metrics,
            "gtex_draw_ordinals_sha256": hashlib.sha256(
                np.ascontiguousarray(draw, dtype="<i8").tobytes()
            ).hexdigest(),
        },
        "d1b": {
            "verdict": d1b_verdict,
            "positive_control_organs": protocol["design"]["positive_control_organs"],
            "n_samples": int(positive.sum()),
            "n_studies": int(np.unique(positive_groups).size),
            "raw_balanced_accuracy": raw_accuracy,
            "pooled_hidden_to_raw_ratios": {
                str(seed): pooled_ratios[index] for index, seed in enumerate(SEEDS)
            },
            "results": d1b_results,
            "organ_by_study_sha256": sha256_file(contingency_path),
        },
        "d1c": d1c,
        "firewalls": {
            "model_training": False,
            "checkpoint_updates": False,
            "best_seed_selection": False,
            "architecture_changes": False,
            "archs4_expression_access": False,
        },
    }
    report_path = output_dir / "encoder_validity_report.json"
    _atomic_json(report_path, report)
    (output_dir / "COMPLETE").write_text("complete\n")
    checksum_paths = [report_path, contingency_path, output_dir / "COMPLETE"]
    manifest = output_dir / "IMMUTABLE_SHA256SUMS"
    manifest.write_text(
        "".join(f"{sha256_file(path)}  {path.name}\n" for path in sorted(checksum_paths))
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
