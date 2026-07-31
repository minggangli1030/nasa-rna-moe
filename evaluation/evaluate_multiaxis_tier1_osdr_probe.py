#!/usr/bin/env python3
"""Frozen study-grouped OSDR label probes for the Tier-1 candidate axes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from core.multiaxis_tier1 import stable_one_hot
from evaluation.evaluate_stage1_osdr_downstream import nested_group_evaluate


METADATA_COLUMNS = {"sample_name", "condition", "spaceflight", "study_id", "species"}
RAW_COLUMNS = {
    "tissue_site": "study.characteristics.material type",
    "sex": "study.characteristics.sex",
    "age_bracket": "study.characteristics.age at launch",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_exact(value: object) -> str:
    if pd.isna(value) or not str(value).strip():
        return "__missing__"
    return " ".join(str(value).strip().casefold().split())


def join_candidate_metadata(
    retained: pd.DataFrame, candidates: pd.DataFrame
) -> pd.DataFrame:
    keys = ["study_id", "sample_name"]
    right = candidates.rename(
        columns={"id.accession": "study_id", "id.sample name": "sample_name"}
    )
    if right.duplicated(keys).any():
        raise ValueError("candidate metadata has duplicate study/sample keys")
    joined = retained.merge(right, on=keys, how="left", validate="one_to_one")
    if len(joined) != len(retained):
        raise RuntimeError("candidate metadata join changed cohort size")
    if joined["id.assay name"].isna().any():
        raise ValueError("candidate metadata does not cover the frozen cohort")
    return joined


def parse_hallmark(path: Path) -> dict[str, tuple[str, ...]]:
    sets = {}
    for line in path.read_text().splitlines():
        fields = line.rstrip("\n").split("\t")
        if len(fields) < 3:
            raise ValueError("invalid Hallmark GMT row")
        sets[fields[0]] = tuple(dict.fromkeys(fields[2:]))
    if len(sets) != 50:
        raise ValueError(f"expected 50 Hallmark sets, found {len(sets)}")
    return sets


def hallmark_features(
    expression: pd.DataFrame,
    hallmark_sets: dict[str, tuple[str, ...]],
    score_genes: set[str],
) -> tuple[np.ndarray, dict[str, int]]:
    genes = set(expression.columns) - METADATA_COLUMNS
    columns = []
    coverage = {}
    for name in sorted(hallmark_sets):
        visible = sorted((set(hallmark_sets[name]) & genes) - score_genes)
        if len(visible) < 10:
            raise ValueError(f"{name} has only {len(visible)} visible genes")
        values = expression[visible].to_numpy(dtype=np.float64)
        if not np.isfinite(values).all():
            raise ValueError(f"{name} contains non-finite expression")
        columns.append(values.mean(axis=1))
        coverage[name] = len(visible)
    return np.column_stack(columns), coverage


def study_bootstrap_delta(
    labels: np.ndarray,
    base_probability: np.ndarray,
    candidate_probability: np.ndarray,
    groups: np.ndarray,
    *,
    replicates: int,
    seed: int,
) -> dict:
    unique = np.unique(groups)
    positions = {group: np.flatnonzero(groups == group) for group in unique}
    rng = np.random.default_rng(seed)
    values = []
    attempts = 0
    while len(values) < replicates and attempts < replicates * 20:
        attempts += 1
        sampled = rng.choice(unique, size=len(unique), replace=True)
        rows = np.concatenate([positions[group] for group in sampled])
        if np.unique(labels[rows]).size != 2:
            continue
        values.append(
            roc_auc_score(labels[rows], candidate_probability[rows])
            - roc_auc_score(labels[rows], base_probability[rows])
        )
    if len(values) != replicates:
        raise RuntimeError("could not form requested valid study bootstraps")
    return {
        "replicates": replicates,
        "median": float(np.median(values)),
        "ci95": np.quantile(values, [0.025, 0.975]).astype(float).tolist(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe-protocol", required=True)
    parser.add_argument("--expected-probe-protocol-sha256", required=True)
    parser.add_argument("--tier1-protocol", required=True)
    parser.add_argument("--osdr-protocol", required=True)
    parser.add_argument("--cohort-root", required=True)
    parser.add_argument("--candidate-metadata", required=True)
    parser.add_argument("--hallmark-gmt", required=True)
    parser.add_argument("--router", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()

    probe_path = Path(args.probe_protocol)
    if sha256_file(probe_path) != args.expected_probe_protocol_sha256:
        raise ValueError("probe protocol SHA256 mismatch")
    protocol = json.loads(probe_path.read_text())
    if protocol.get("status") != "frozen_before_multiaxis_osdr_probe_outcome_access":
        raise ValueError("probe protocol is not frozen")
    checks = (
        (Path(args.tier1_protocol), protocol["parent_tier1_protocol_sha256"]),
        (Path(args.osdr_protocol), protocol["cohort"]["stage1_osdr_protocol_sha256"]),
        (Path(args.candidate_metadata), protocol["inputs"]["candidate_metadata_sha256"]),
        (Path(args.hallmark_gmt), protocol["inputs"]["hallmark_gmt_sha256"]),
    )
    for path, expected in checks:
        if sha256_file(path) != expected:
            raise ValueError(f"input SHA256 mismatch: {path}")

    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise FileExistsError(output_dir)
    output_dir.mkdir(parents=True)
    cohort_root = Path(args.cohort_root)
    retained = pd.read_csv(cohort_root / "retained_cohort.csv")
    retained = retained.loc[retained["valid_study_organ_contrast"].astype(bool)].copy()
    if len(retained) != 292 or retained["study_id"].nunique() != 18:
        raise ValueError("frozen OSDR cohort membership changed")
    candidates = pd.read_csv(args.candidate_metadata)
    metadata = join_candidate_metadata(retained, candidates)

    expression = pd.read_parquet(cohort_root / "osdr_expression_v3.parquet")
    expression.index = expression.index.astype(str)
    sample_ids = retained["sample_id"].astype(str).to_numpy()
    expression = expression.reindex(sample_ids)
    if expression.isna().any().any():
        raise ValueError("expression does not cover frozen retained cohort")
    labels = retained["spaceflight"].astype(np.int64).to_numpy()
    groups = retained["study_id"].astype(str).to_numpy()
    organs = retained["organ"].astype(str).to_numpy()
    base, organ_levels = stable_one_hot(organs)

    router = np.load(args.router, allow_pickle=False)
    score_genes = set(router["score_gene_names"].astype(str).tolist())
    hallmark, hallmark_coverage = hallmark_features(
        expression, parse_hallmark(Path(args.hallmark_gmt)), score_genes
    )
    axis_features = {}
    coverage = {}
    for axis, column in RAW_COLUMNS.items():
        values = metadata[column].map(normalize_exact).to_numpy(dtype=str)
        encoded, levels = stable_one_hot(values)
        axis_features[axis] = encoded
        coverage[axis] = {
            "levels": list(levels),
            "counts": {level: int(np.sum(values == level)) for level in levels},
            "missing_rows": int(np.sum(values == "__missing__")),
        }
    axis_features["hallmark_50"] = hallmark
    coverage["hallmark_50"] = {
        "sets": 50,
        "minimum_visible_non_score_genes": min(hallmark_coverage.values()),
        "visible_non_score_genes": hallmark_coverage,
    }

    if args.smoke:
        grid = ((0.1, 0.0), (1.0, 1.0))
        outer_folds, inner_folds, bootstrap_replicates = 3, 2, 100
    else:
        grid = tuple(
            (float(item["C"]), float(item["l1_ratio"]))
            for item in protocol["head"]["grid"]
        )
        outer_folds = int(protocol["cohort"]["outer_folds"])
        inner_folds = int(protocol["cohort"]["inner_folds"])
        bootstrap_replicates = int(protocol["head"]["study_bootstrap_replicates"])

    base_result = nested_group_evaluate(
        base,
        labels,
        groups,
        outer_folds=outer_folds,
        inner_folds=inner_folds,
        pca_components=None,
        grid=grid,
    )
    base_auroc = base_result["pooled_out_of_fold"]["auroc"]
    results = {}
    predictions = []
    for axis in ("tissue_site", "sex", "age_bracket", "hallmark_50"):
        result = nested_group_evaluate(
            np.column_stack([base, axis_features[axis]]),
            labels,
            groups,
            outer_folds=outer_folds,
            inner_folds=inner_folds,
            pca_components=None,
            grid=grid,
        )
        delta = result["pooled_out_of_fold"]["auroc"] - base_auroc
        bootstrap = study_bootstrap_delta(
            labels,
            base_result["probabilities"],
            result["probabilities"],
            groups,
            replicates=bootstrap_replicates,
            seed=int(protocol["head"]["study_bootstrap_seed"]),
        )
        results[axis] = {
            "metrics": result["pooled_out_of_fold"],
            "auroc_minus_organ_base": float(delta),
            "positive_gate": bool(delta > 0),
            "study_bootstrap": bootstrap,
            "folds": result["folds"],
        }
        for sample_id, study, label, base_prob, axis_prob in zip(
            sample_ids,
            groups,
            labels,
            base_result["probabilities"],
            result["probabilities"],
        ):
            predictions.append(
                {
                    "axis": axis,
                    "sample_id": sample_id,
                    "study_id": study,
                    "label": int(label),
                    "organ_base_probability": float(base_prob),
                    "candidate_probability": float(axis_prob),
                }
            )
    predictions_path = output_dir / "out_of_fold_predictions.csv"
    pd.DataFrame(predictions).to_csv(predictions_path, index=False)
    report = {
        "schema_version": 1,
        "status": "complete",
        "role": protocol["role"],
        "smoke": bool(args.smoke),
        "probe_protocol_sha256": sha256_file(probe_path),
        "n_samples": int(len(labels)),
        "n_studies": int(np.unique(groups).size),
        "organ_levels": list(organ_levels),
        "coverage": coverage,
        "organ_base": {
            "metrics": base_result["pooled_out_of_fold"],
            "folds": base_result["folds"],
        },
        "results": results,
        "predictions_sha256": sha256_file(predictions_path),
        "best_seed_selection": False,
        "final_confirmation": False,
    }
    report_path = output_dir / "osdr_axis_probe_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    checksum = sha256_file(report_path)
    (output_dir / "IMMUTABLE_SHA256SUMS").write_text(
        f"{checksum}  {report_path.name}\n"
    )
    (output_dir / "COMPLETE").write_text("complete\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
