#!/usr/bin/env python3
"""Frozen post-D2 secondary analyses on the accessed OSDR cohort.

This evaluator never updates a checkpoint.  It separates the deployment question
(learned representation versus raw/PCA) from the matched scientific question
(organ specialization versus pooling).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from evaluate_stage1_osdr_downstream import (
    EMBEDDING_CONDITIONS,
    _fit,
    _fit_grid_path,
    _score,
    _splits,
    _transform,
    nested_group_evaluate,
)


METADATA_COLUMNS = {"sample_name", "condition", "spaceflight", "study_id", "species"}
GRID = tuple(
    (c_value, l1_ratio)
    for c_value in (0.01, 0.1, 1.0, 10.0)
    for l1_ratio in (0.0, 0.5, 1.0)
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_protocol(path: Path, expected_sha256: str) -> dict:
    actual = sha256_file(path)
    if actual != expected_sha256:
        raise ValueError(f"protocol SHA256 mismatch: {actual}")
    protocol = json.loads(path.read_text())
    if protocol.get("status") != "frozen_post_d2_secondary_analysis_before_execution":
        raise ValueError("post-D2 protocol is not frozen")
    return protocol


def load_archives(root: Path, expected_hashes: dict[str, str]) -> dict[int, np.lib.npyio.NpzFile]:
    archives = {}
    for seed_text, expected in expected_hashes.items():
        seed = int(seed_text)
        path = root / f"seed{seed}_features.npz"
        if sha256_file(path) != expected:
            raise ValueError(f"seed {seed} feature-cache SHA256 mismatch")
        archive = np.load(path, allow_pickle=False)
        metadata = json.loads(str(archive["metadata_json"].item()))
        if metadata.get("status") != "complete" or int(metadata.get("seed", -1)) != seed:
            raise ValueError(f"seed {seed} feature cache is incomplete")
        archives[seed] = archive
    return archives


def load_cohort(cohort_root: Path, reference: np.lib.npyio.NpzFile):
    expression = pd.read_parquet(cohort_root / "osdr_expression_v3.parquet")
    sample_ids = reference["sample_ids"].astype(str)
    groups = reference["groups"].astype(str)
    organs = reference["organs"].astype(str)
    labels = reference["labels"].astype(np.int64)
    expression.index = expression.index.astype(str)
    expression = expression.reindex(sample_ids)
    genes = [column for column in expression.columns if column not in METADATA_COLUMNS]
    raw = expression[genes].to_numpy(dtype=np.float32)
    if expression.index.has_duplicates or expression.isna().any().any():
        raise ValueError("cohort membership or expression is invalid")
    if not np.isfinite(raw).all():
        raise ValueError("cohort expression is non-finite")
    return sample_ids, groups, organs, labels, raw


def assert_aligned(archives: dict[int, np.lib.npyio.NpzFile], reference) -> None:
    for seed, archive in archives.items():
        for key in ("sample_ids", "groups", "organs", "labels"):
            left = archive[key].astype(str) if key != "labels" else archive[key]
            right = reference[key].astype(str) if key != "labels" else reference[key]
            if not np.array_equal(left, right):
                raise ValueError(f"seed {seed} {key} differs from reference")


def _center_from_training_groups(
    x_train: np.ndarray,
    organs_train: np.ndarray,
    x_test: np.ndarray,
    organs_test: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Subtract organ means learned only from the training partition."""
    train = np.empty_like(x_train, dtype=np.float32)
    test = np.empty_like(x_test, dtype=np.float32)
    for organ in np.unique(organs_train):
        train_rows = organs_train == organ
        test_rows = organs_test == organ
        mean = x_train[train_rows].mean(axis=0, dtype=np.float64).astype(np.float32)
        train[train_rows] = x_train[train_rows] - mean
        if np.any(test_rows):
            test[test_rows] = x_test[test_rows] - mean
    unseen = set(np.unique(organs_test)) - set(np.unique(organs_train))
    if unseen:
        raise ValueError(f"test partition contains unseen organs: {sorted(unseen)}")
    return train, test


def nested_group_evaluate_centered(
    x: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    organs: np.ndarray,
    *,
    outer_folds: int,
    inner_folds: int,
    grid: tuple[tuple[float, float], ...],
) -> dict:
    """Nested grouped evaluation with fold-fit organ centering before scaling."""
    folds = []
    probabilities = np.full(len(y), np.nan, dtype=np.float64)
    predictions = np.full(len(y), -1, dtype=np.int64)
    for outer_index, (train_index, test_index) in enumerate(_splits(groups, outer_folds)):
        candidate_scores = {item: [] for item in grid}
        candidate_iterations = {item: [] for item in grid}
        inner_groups = groups[train_index]
        for inner_train, inner_test in _splits(inner_groups, inner_folds):
            a = train_index[inner_train]
            b = train_index[inner_test]
            centered_train, centered_test = _center_from_training_groups(
                x[a], organs[a], x[b], organs[b]
            )
            train, test = _transform(centered_train, centered_test, pca_components=None)
            path = _fit_grid_path(train, y[a], test, grid)
            for item, (probability, n_iter) in path.items():
                candidate_scores[item].append(float(roc_auc_score(y[b], probability)))
                candidate_iterations[item].append(n_iter)
        candidates = []
        for c_value, l1_ratio in grid:
            candidates.append(
                {
                    "C": c_value,
                    "l1_ratio": l1_ratio,
                    "mean_inner_auroc": float(
                        np.mean(candidate_scores[(c_value, l1_ratio)])
                    ),
                    "max_inner_iterations": int(
                        max(candidate_iterations[(c_value, l1_ratio)])
                    ),
                }
            )
        selected = sorted(
            candidates,
            key=lambda item: (-item["mean_inner_auroc"], item["C"], item["l1_ratio"]),
        )[0]
        centered_train, centered_test = _center_from_training_groups(
            x[train_index], organs[train_index], x[test_index], organs[test_index]
        )
        train, test = _transform(centered_train, centered_test, pca_components=None)
        probability, prediction, n_iter = _fit(
            train,
            y[train_index],
            test,
            c_value=selected["C"],
            l1_ratio=selected["l1_ratio"],
        )
        probabilities[test_index] = probability
        predictions[test_index] = prediction
        folds.append(
            {
                "fold": outer_index,
                "selected": selected,
                "outer_fit_iterations": n_iter,
                "metrics": _score(y[test_index], probability, prediction),
            }
        )
    if not np.isfinite(probabilities).all() or np.any(predictions < 0):
        raise RuntimeError("centered grouped evaluation did not score every sample")
    return {
        "pooled_out_of_fold": _score(y, probabilities, predictions),
        "folds": folds,
        "probabilities": probabilities,
        "predictions": predictions,
    }


def paired_study_bootstrap(
    frame: pd.DataFrame,
    *,
    candidate: str,
    baseline: str,
    seed: int,
    replicates: int,
) -> dict:
    keys = ["sample_id", "study_id", "organ", "label"]
    candidate_frame = frame.loc[frame["representation"] == candidate, keys + ["probability"]]
    baseline_frame = frame.loc[frame["representation"] == baseline, keys + ["probability"]]
    paired = candidate_frame.merge(
        baseline_frame,
        on=keys,
        how="inner",
        validate="one_to_one",
        suffixes=("_candidate", "_baseline"),
    )
    if len(paired) != len(candidate_frame) or len(paired) != len(baseline_frame):
        raise ValueError(f"unaligned comparison: {candidate} versus {baseline}")
    studies = np.unique(paired["study_id"].astype(str))
    if len(studies) < 2:
        raise ValueError("paired study bootstrap requires at least two studies")
    point_candidate = float(roc_auc_score(paired["label"], paired["probability_candidate"]))
    point_baseline = float(roc_auc_score(paired["label"], paired["probability_baseline"]))
    rng = np.random.default_rng(seed)
    deltas = []
    for _ in range(replicates):
        sampled = rng.choice(studies, size=len(studies), replace=True)
        blocks = [paired.loc[paired["study_id"].astype(str) == study] for study in sampled]
        draw = pd.concat(blocks, ignore_index=True)
        if draw["label"].nunique() != 2:
            raise RuntimeError("a paired study-bootstrap draw lost a class")
        deltas.append(
            float(roc_auc_score(draw["label"], draw["probability_candidate"]))
            - float(roc_auc_score(draw["label"], draw["probability_baseline"]))
        )
    return {
        "candidate": candidate,
        "baseline": baseline,
        "candidate_auroc": point_candidate,
        "baseline_auroc": point_baseline,
        "delta_auroc": point_candidate - point_baseline,
        "study_bootstrap_ci95": [
            float(np.quantile(deltas, 0.025)),
            float(np.quantile(deltas, 0.975)),
        ],
        "n_samples": int(len(paired)),
        "n_studies": int(len(studies)),
        "replicates": int(replicates),
    }


def prediction_rows(
    *,
    seed: int,
    representation: str,
    sample_ids,
    groups,
    organs,
    labels,
    result: dict,
) -> list[dict]:
    return [
        {
            "seed": int(seed),
            "representation": representation,
            "sample_id": sample_id,
            "study_id": group,
            "organ": organ,
            "label": int(label),
            "probability": float(probability),
            "prediction": int(prediction),
        }
        for sample_id, group, organ, label, probability, prediction in zip(
            sample_ids,
            groups,
            organs,
            labels,
            result["probabilities"],
            result["predictions"],
        )
    ]


def analyze_matched_deltas(
    frame: pd.DataFrame,
    protocol: dict,
    family: str,
    *,
    scopes: tuple[tuple[str, str | None], ...] | None = None,
) -> dict:
    bootstrap = protocol["shared_evaluation"]
    if family == "embedding":
        pooled = "pooled_hidden"
        candidates = (
            "true_organ_embedding",
            "blind_router_hard_embedding",
            "blind_router_soft_embedding",
        )
    elif family == "score_panel":
        pooled = "pooled"
        candidates = ("true_organ", "blind_router_hard", "blind_router_soft")
    else:
        raise ValueError(family)
    output = {}
    if scopes is None:
        scopes = (
            ("full_cohort", None),
            ("skeletal_muscle", "skeletal_muscle"),
            ("brain", "brain"),
        )
    for scope_index, (scope, organ) in enumerate(scopes):
        scoped = frame if organ is None else frame.loc[frame["organ"] == organ]
        if organ is not None and len(scoped["sample_id"].unique()) < 20:
            raise ValueError(f"prespecified {organ} scope has fewer than 20 samples")
        output[scope] = {}
        for seed_index, model_seed in enumerate((17, 42, 101)):
            per_seed = scoped.loc[scoped["seed"].isin((-1, model_seed))]
            output[scope][str(model_seed)] = {}
            for candidate_index, candidate in enumerate(candidates):
                candidate_frame = per_seed.loc[per_seed["seed"] == model_seed]
                baseline_frame = per_seed.loc[per_seed["seed"] == model_seed]
                joined = pd.concat(
                    [
                        candidate_frame.loc[candidate_frame["representation"] == candidate],
                        baseline_frame.loc[baseline_frame["representation"] == pooled],
                    ],
                    ignore_index=True,
                )
                output[scope][str(model_seed)][candidate] = paired_study_bootstrap(
                    joined,
                    candidate=candidate,
                    baseline=pooled,
                    seed=int(bootstrap["study_bootstrap_seed"])
                    + scope_index * 1000
                    + seed_index * 100
                    + candidate_index,
                    replicates=int(bootstrap["study_bootstrap_replicates"]),
                )
    return output


def run_e1(args, protocol: dict, output_dir: Path) -> dict:
    archives = load_archives(
        Path(args.embedding_feature_root),
        protocol["inputs"]["final_embedding_feature_sha256"],
    )
    reference = archives[17]
    assert_aligned(archives, reference)
    sample_ids, groups, organs, labels, raw = load_cohort(Path(args.cohort_root), reference)
    keep = organs == "skeletal_muscle"
    if int(keep.sum()) != int(protocol["e1_muscle_only"]["expected_samples"]):
        raise ValueError("skeletal-muscle sample count differs from frozen protocol")
    if int(np.unique(groups[keep]).size) != int(protocol["e1_muscle_only"]["expected_studies"]):
        raise ValueError("skeletal-muscle study count differs from frozen protocol")
    organ_order = [
        "adipose", "brain", "colon", "heart", "liver", "lung", "skeletal_muscle", "skin"
    ]
    organ_one_hot = np.eye(len(organ_order), dtype=np.float32)[
        [organ_order.index(value) for value in organs]
    ]
    results = {}
    rows = []
    for name, features, components in (
        ("raw_expression", raw, None),
        ("pca_64", raw, 64),
    ):
        result = nested_group_evaluate(
            features[keep], labels[keep], groups[keep],
            outer_folds=5, inner_folds=3, pca_components=components, grid=GRID,
        )
        results[name] = {k: v for k, v in result.items() if k not in {"probabilities", "predictions"}}
        rows.extend(prediction_rows(
            seed=-1, representation=name, sample_ids=sample_ids[keep], groups=groups[keep],
            organs=organs[keep], labels=labels[keep], result=result,
        ))
    for seed, archive in archives.items():
        for condition in EMBEDDING_CONDITIONS:
            if condition == "pooled_hidden_plus_organ_label":
                features = np.concatenate(
                    [archive["feature__pooled_hidden"], organ_one_hot], axis=1
                )
            else:
                features = archive[f"feature__{condition}"]
            result = nested_group_evaluate(
                features[keep], labels[keep], groups[keep],
                outer_folds=5, inner_folds=3, pca_components=None, grid=GRID,
            )
            key = f"seed{seed}__{condition}"
            results[key] = {k: v for k, v in result.items() if k not in {"probabilities", "predictions"}}
            rows.extend(prediction_rows(
                seed=seed, representation=condition, sample_ids=sample_ids[keep],
                groups=groups[keep], organs=organs[keep], labels=labels[keep], result=result,
            ))
    frame = pd.DataFrame(rows)
    predictions_path = output_dir / "out_of_fold_predictions.csv"
    frame.to_csv(predictions_path, index=False)
    q_b = analyze_matched_deltas(
        frame,
        protocol,
        "embedding",
        scopes=(("skeletal_muscle", "skeletal_muscle"),),
    )["skeletal_muscle"]
    q_a = {}
    bootstrap = protocol["shared_evaluation"]
    for seed_index, seed in enumerate((17, 42, 101)):
        q_a[str(seed)] = {}
        for candidate_index, candidate in enumerate(
            ("blind_router_hard_embedding", "blind_router_soft_embedding")
        ):
            for baseline_index, baseline in enumerate(("raw_expression", "pca_64")):
                selected = frame.loc[
                    ((frame["seed"] == seed) & (frame["representation"] == candidate))
                    | ((frame["seed"] == -1) & (frame["representation"] == baseline))
                ]
                key = f"{candidate}_vs_{baseline}"
                q_a[str(seed)][key] = paired_study_bootstrap(
                    selected,
                    candidate=candidate,
                    baseline=baseline,
                    seed=int(bootstrap["study_bootstrap_seed"]) + 5000
                    + seed_index * 100 + candidate_index * 10 + baseline_index,
                    replicates=int(bootstrap["study_bootstrap_replicates"]),
                )
    return {
        "status": "complete",
        "component": "e1_muscle_only",
        "n_samples": int(keep.sum()),
        "n_studies": int(np.unique(groups[keep]).size),
        "results": results,
        "q_a_deployment_deltas": q_a,
        "q_b_specialization_deltas": q_b,
        "predictions_sha256": sha256_file(predictions_path),
    }


def run_e4(args, protocol: dict) -> dict:
    paths = {
        "embedding": Path(args.embedding_oof),
        "score_panel": Path(args.score_oof),
    }
    expected = {
        "embedding": protocol["inputs"]["embedding_oof_sha256"],
        "score_panel": protocol["inputs"]["score_panel_oof_sha256"],
    }
    output = {}
    for family, path in paths.items():
        if sha256_file(path) != expected[family]:
            raise ValueError(f"{family} OOF SHA256 mismatch")
        frame = pd.read_csv(path)
        output[family] = analyze_matched_deltas(frame, protocol, family)
    return {
        "status": "complete",
        "component": "e4_specialization_estimand",
        "results": output,
    }


def _centered_scope_is_feasible(groups: np.ndarray, organs: np.ndarray) -> bool:
    for train_index, test_index in _splits(groups, 5):
        if set(np.unique(organs[test_index])) - set(np.unique(organs[train_index])):
            return False
        inner_groups = groups[train_index]
        for inner_train, inner_test in _splits(inner_groups, 3):
            a = train_index[inner_train]
            b = train_index[inner_test]
            if set(np.unique(organs[b])) - set(np.unique(organs[a])):
                return False
    return True


def _comparison_frame(
    frame: pd.DataFrame,
    *,
    seed: int,
    candidate: str,
    baseline: str,
) -> pd.DataFrame:
    baseline_seed = -1 if baseline in {
        "score_panel_within_organ_centered",
        "full_raw_within_organ_centered",
        "raw_expression",
        "pca_64",
    } else seed
    return frame.loc[
        ((frame["seed"] == seed) & (frame["representation"] == candidate))
        | ((frame["seed"] == baseline_seed) & (frame["representation"] == baseline))
    ]


def run_e2(args, protocol: dict, output_dir: Path) -> dict:
    archives = load_archives(
        Path(args.score_feature_root),
        protocol["inputs"]["score_panel_feature_sha256"],
    )
    reference = archives[17]
    assert_aligned(archives, reference)
    sample_ids, groups, organs, labels, raw = load_cohort(Path(args.cohort_root), reference)
    score_indices = reference["score_gene_indices"].astype(np.int64)
    if np.any(score_indices < 0) or np.any(score_indices >= raw.shape[1]):
        raise ValueError("score-gene indices are outside the cohort expression matrix")
    observed_score = raw[:, score_indices]
    scope_masks = {
        "skeletal_muscle": organs == "skeletal_muscle",
        "full_cohort": np.ones(len(organs), dtype=bool),
    }
    reports = {}
    bootstrap = protocol["shared_evaluation"]
    for scope_index, (scope, keep) in enumerate(scope_masks.items()):
        scoped_groups = groups[keep]
        scoped_organs = organs[keep]
        if not _centered_scope_is_feasible(scoped_groups, scoped_organs):
            reports[scope] = {
                "status": "not_estimable",
                "reason": "at least one grouped inner/test fold contains an organ absent from its training partition; frozen fold-fit centering has no authorized fallback",
                "n_samples": int(keep.sum()),
                "n_studies": int(np.unique(scoped_groups).size),
            }
            continue
        rows = []
        results = {}
        baseline_specs = (
            ("score_panel_within_organ_centered", observed_score, "centered"),
            ("full_raw_within_organ_centered", raw, "centered"),
            ("raw_expression", raw, "plain"),
            ("pca_64", raw, "pca"),
        )
        for name, features, mode in baseline_specs:
            if mode == "centered":
                result = nested_group_evaluate_centered(
                    features[keep], labels[keep], scoped_groups, scoped_organs,
                    outer_folds=5, inner_folds=3, grid=GRID,
                )
            else:
                result = nested_group_evaluate(
                    features[keep], labels[keep], scoped_groups,
                    outer_folds=5, inner_folds=3,
                    pca_components=64 if mode == "pca" else None,
                    grid=GRID,
                )
            results[name] = {
                key: value
                for key, value in result.items()
                if key not in {"probabilities", "predictions"}
            }
            rows.extend(
                prediction_rows(
                    seed=-1, representation=name, sample_ids=sample_ids[keep],
                    groups=scoped_groups, organs=scoped_organs, labels=labels[keep],
                    result=result,
                )
            )
        residual_conditions = {
            "residual_pooled": "pooled",
            "residual_true_organ": "true_organ",
            "residual_blind_router_hard": "blind_router_hard",
            "residual_blind_router_soft": "blind_router_soft",
        }
        for model_seed, archive in archives.items():
            for name, source in residual_conditions.items():
                residual = observed_score - archive[f"feature__{source}"]
                result = nested_group_evaluate(
                    residual[keep], labels[keep], scoped_groups,
                    outer_folds=5, inner_folds=3, pca_components=None, grid=GRID,
                )
                results[f"seed{model_seed}__{name}"] = {
                    key: value
                    for key, value in result.items()
                    if key not in {"probabilities", "predictions"}
                }
                rows.extend(
                    prediction_rows(
                        seed=model_seed, representation=name, sample_ids=sample_ids[keep],
                        groups=scoped_groups, organs=scoped_organs, labels=labels[keep],
                        result=result,
                    )
                )
        frame = pd.DataFrame(rows)
        predictions_path = output_dir / f"{scope}_out_of_fold_predictions.csv"
        frame.to_csv(predictions_path, index=False)
        comparisons = {}
        scientific_candidates = (
            "residual_true_organ",
            "residual_blind_router_hard",
            "residual_blind_router_soft",
        )
        for seed_index, model_seed in enumerate((17, 42, 101)):
            comparisons[str(model_seed)] = {}
            comparison_index = 0
            for candidate in scientific_candidates:
                baselines = [
                    "residual_pooled",
                    "score_panel_within_organ_centered",
                ]
                if candidate.startswith("residual_blind"):
                    baselines.extend(
                        ["full_raw_within_organ_centered", "raw_expression", "pca_64"]
                    )
                for baseline in baselines:
                    selected = _comparison_frame(
                        frame, seed=model_seed, candidate=candidate, baseline=baseline
                    )
                    key = f"{candidate}_vs_{baseline}"
                    comparisons[str(model_seed)][key] = paired_study_bootstrap(
                        selected,
                        candidate=candidate,
                        baseline=baseline,
                        seed=int(bootstrap["study_bootstrap_seed"])
                        + 10000 + scope_index * 1000 + seed_index * 100 + comparison_index,
                        replicates=int(bootstrap["study_bootstrap_replicates"]),
                    )
                    comparison_index += 1
        reports[scope] = {
            "status": "complete",
            "n_samples": int(keep.sum()),
            "n_studies": int(np.unique(scoped_groups).size),
            "results": results,
            "comparisons": comparisons,
            "predictions_sha256": sha256_file(predictions_path),
        }
    return {
        "status": "complete",
        "component": "e2_organ_conditional_residuals",
        "scopes": reports,
    }


def write_immutable_output(output_dir: Path, report: dict, protocol_path: Path) -> None:
    report["protocol_sha256"] = sha256_file(protocol_path)
    report["best_seed_selection"] = False
    report["confirmation_claim"] = False
    report_path = output_dir / "evaluation_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (output_dir / "COMPLETE").write_text("complete\n")
    lines = []
    for path in sorted(output_dir.rglob("*")):
        if path.is_file() and path.name != "IMMUTABLE_SHA256SUMS":
            lines.append(f"{sha256_file(path)}  {path.relative_to(output_dir)}")
    (output_dir / "IMMUTABLE_SHA256SUMS").write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--component", choices=("e1", "e2", "e4"), required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--cohort-root")
    parser.add_argument("--embedding-feature-root")
    parser.add_argument("--score-feature-root")
    parser.add_argument("--embedding-oof")
    parser.add_argument("--score-oof")
    args = parser.parse_args()
    protocol_path = Path(args.protocol)
    protocol = verify_protocol(protocol_path, args.expected_protocol_sha256)
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise FileExistsError(output_dir)
    output_dir.mkdir(parents=True)
    if args.component == "e1":
        if not args.cohort_root or not args.embedding_feature_root:
            raise ValueError("E1 requires cohort and embedding feature roots")
        report = run_e1(args, protocol, output_dir)
    elif args.component == "e2":
        if not args.cohort_root or not args.score_feature_root:
            raise ValueError("E2 requires cohort and score-panel feature roots")
        report = run_e2(args, protocol, output_dir)
    else:
        if not args.embedding_oof or not args.score_oof:
            raise ValueError("E4 requires both frozen OOF prediction files")
        report = run_e4(args, protocol)
    write_immutable_output(output_dir, report, protocol_path)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
