#!/usr/bin/env python3
"""GTEx-trained, OSDR-tested cross-species organ-transfer audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import balanced_accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler

from core.train_manifest import load_expression_rows


SEEDS = (17, 42, 101)
METADATA_COLUMNS = {"sample_name", "condition", "spaceflight", "study_id", "species"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_seed_paths(values: list[str]) -> dict[int, Path]:
    output = {}
    for value in values:
        seed_text, path_text = value.split("=", 1)
        seed = int(seed_text)
        if seed in output:
            raise ValueError(f"duplicate seed path: {seed}")
        output[seed] = Path(path_text)
    if set(output) != set(SEEDS):
        raise ValueError(f"expected exact seeds {SEEDS}")
    return output


def _classifier(alpha: float, seed: int) -> SGDClassifier:
    return SGDClassifier(
        loss="log_loss",
        penalty="l2",
        alpha=alpha,
        class_weight="balanced",
        max_iter=5000,
        tol=1e-4,
        random_state=seed,
        average=True,
        early_stopping=False,
        n_jobs=1,
    )


def _validate_fold_labels(labels: np.ndarray, train: np.ndarray, test: np.ndarray) -> None:
    expected = set(np.unique(labels))
    if set(np.unique(labels[train])) != expected or set(np.unique(labels[test])) != expected:
        raise ValueError("donor-grouped fold does not contain every organ class")


def select_alpha_by_grouped_cv(
    features: np.ndarray,
    labels: np.ndarray,
    groups: np.ndarray,
    *,
    alphas: tuple[float, ...],
    folds: int,
    seed: int,
) -> tuple[float, list[dict]]:
    splitter = GroupKFold(n_splits=folds)
    scores = {alpha: [] for alpha in alphas}
    iterations = {alpha: [] for alpha in alphas}
    for train, test in splitter.split(features, labels, groups):
        _validate_fold_labels(labels, train, test)
        scaler = StandardScaler()
        x_train = scaler.fit_transform(features[train])
        x_test = scaler.transform(features[test])
        for alpha in alphas:
            model = _classifier(alpha, seed)
            model.fit(x_train, labels[train])
            if int(model.n_iter_) >= int(model.max_iter):
                raise RuntimeError(f"SGD did not converge for alpha={alpha}")
            predicted = model.predict(x_test)
            scores[alpha].append(float(balanced_accuracy_score(labels[test], predicted)))
            iterations[alpha].append(int(model.n_iter_))
    table = [
        {
            "alpha": alpha,
            "mean_donor_grouped_balanced_accuracy": float(np.mean(scores[alpha])),
            "fold_balanced_accuracy": scores[alpha],
            "max_iterations": max(iterations[alpha]),
        }
        for alpha in alphas
    ]
    selected = sorted(
        table,
        key=lambda row: (-row["mean_donor_grouped_balanced_accuracy"], row["alpha"]),
    )[0]["alpha"]
    return float(selected), table


def fit_gtex_apply_osdr(
    gtex_features: np.ndarray,
    gtex_labels: np.ndarray,
    gtex_donors: np.ndarray,
    osdr_features: np.ndarray,
    osdr_labels: np.ndarray,
    *,
    alphas: tuple[float, ...],
    folds: int,
    seed: int,
    organ_order: tuple[str, ...],
) -> dict:
    if not np.isfinite(gtex_features).all() or not np.isfinite(osdr_features).all():
        raise ValueError("organ-transfer features contain non-finite values")
    if gtex_features.shape[1] != osdr_features.shape[1]:
        raise ValueError("GTEx and OSDR feature widths differ")
    selected, tuning = select_alpha_by_grouped_cv(
        gtex_features,
        gtex_labels,
        gtex_donors,
        alphas=alphas,
        folds=folds,
        seed=seed,
    )
    scaler = StandardScaler()
    train = scaler.fit_transform(gtex_features)
    test = scaler.transform(osdr_features)
    model = _classifier(selected, seed)
    model.fit(train, gtex_labels)
    if int(model.n_iter_) >= int(model.max_iter):
        raise RuntimeError("final SGD classifier did not converge")
    predicted = model.predict(test)
    matrix = confusion_matrix(osdr_labels, predicted, labels=list(organ_order))
    recalls = np.divide(
        np.diag(matrix),
        matrix.sum(axis=1),
        out=np.zeros(len(organ_order), dtype=np.float64),
        where=matrix.sum(axis=1) > 0,
    )
    return {
        "balanced_accuracy": float(balanced_accuracy_score(osdr_labels, predicted)),
        "macro_f1": float(f1_score(osdr_labels, predicted, average="macro")),
        "selected_alpha": selected,
        "final_iterations": int(model.n_iter_),
        "donor_grouped_tuning": tuning,
        "confusion_matrix": matrix.astype(int).tolist(),
        "per_organ_recall": {
            organ: float(recall) for organ, recall in zip(organ_order, recalls)
        },
        "predictions": predicted,
    }


def frozen_verdict(raw_accuracy: float, embedding_accuracies: list[float], gates: dict) -> str:
    preserved = float(gates["preserved_balanced_accuracy"])
    lost = float(gates["lost_balanced_accuracy"])
    if raw_accuracy <= lost:
        return "CROSS_SPECIES_GAP_UPSTREAM_OR_TASK_LIMIT"
    if min(embedding_accuracies) >= preserved:
        return "CROSS_SPECIES_ORGAN_STRUCTURE_PRESERVED"
    if raw_accuracy >= preserved and max(embedding_accuracies) <= lost:
        return "ENCODER_SPECIFIC_ORGAN_INFORMATION_LOSS"
    return "CROSS_SPECIES_ORGAN_TRANSFER_PARTIAL"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--gtex-expression", required=True)
    parser.add_argument("--gtex-manifest", required=True)
    parser.add_argument("--gtex-cache", action="append", required=True)
    parser.add_argument("--osdr-cohort-root", required=True)
    parser.add_argument("--osdr-feature-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()

    protocol_path = Path(args.protocol)
    if sha256_file(protocol_path) != args.expected_protocol_sha256:
        raise ValueError("replacement D1b protocol SHA256 mismatch")
    protocol = json.loads(protocol_path.read_text())
    if protocol.get("status") != "frozen_before_cross_species_organ_transfer_outcome_access":
        raise ValueError("replacement D1b protocol is not frozen")
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise FileExistsError(output_dir)
    output_dir.mkdir(parents=True)

    cohort_root = Path(args.osdr_cohort_root)
    fixed = {
        "gtex_expression_sha256": Path(args.gtex_expression),
        "gtex_manifest_sha256": Path(args.gtex_manifest),
        "osdr_expression_sha256": cohort_root / "osdr_expression_v3.parquet",
        "osdr_retained_sha256": cohort_root / "retained_cohort.csv",
    }
    for key, path in fixed.items():
        if sha256_file(path) != protocol["inputs"][key]:
            raise ValueError(f"input hash mismatch: {key}")
    gtex_paths = parse_seed_paths(args.gtex_cache)
    osdr_root = Path(args.osdr_feature_root)
    for seed in SEEDS:
        if sha256_file(gtex_paths[seed]) != protocol["inputs"]["gtex_cache_sha256"][str(seed)]:
            raise ValueError(f"GTEx cache hash mismatch: {seed}")
        osdr_path = osdr_root / f"seed{seed}_features.npz"
        if sha256_file(osdr_path) != protocol["inputs"]["osdr_feature_sha256"][str(seed)]:
            raise ValueError(f"OSDR cache hash mismatch: {seed}")

    manifest = pd.read_parquet(args.gtex_manifest)
    required = {"sample_id", "split", "balanced_train", "organ", "donor_id"}
    if not required.issubset(manifest.columns):
        raise ValueError(f"GTEx manifest lacks {sorted(required - set(manifest.columns))}")
    training = (
        manifest.loc[
            manifest["split"].astype(str).eq("train")
            & manifest["balanced_train"].astype(bool)
        ]
        .sort_values("sample_id")
        .reset_index(drop=True)
    )
    if len(training) != int(protocol["cohort"]["gtex_training_rows"]):
        raise ValueError("GTEx training membership changed")
    organ_order = tuple(protocol["cohort"]["shared_organs"])
    keep_gtex = training["organ"].astype(str).isin(organ_order).to_numpy()
    gtex_labels = training.loc[keep_gtex, "organ"].astype(str).to_numpy()
    gtex_donors = training.loc[keep_gtex, "donor_id"].astype(str).to_numpy()
    if np.any(gtex_donors == "") or np.unique(gtex_donors).size < 20:
        raise ValueError("GTEx donor groups are missing or insufficient")

    retained = pd.read_csv(cohort_root / "retained_cohort.csv")
    retained = retained.loc[retained["valid_study_organ_contrast"].astype(bool)].copy()
    if len(retained) != int(protocol["cohort"]["osdr_rows"]):
        raise ValueError("OSDR membership changed")
    osdr_labels = retained["organ"].astype(str).to_numpy()
    if tuple(sorted(np.unique(osdr_labels))) != tuple(sorted(organ_order)):
        raise ValueError("OSDR shared-organ membership changed")
    sample_ids = retained["sample_id"].astype(str).to_numpy()

    gtex_raw, info = load_expression_rows(
        args.gtex_expression, training["sample_id"].astype(str).tolist()
    )
    gtex_raw = np.log1p(gtex_raw[keep_gtex]).astype(np.float32)
    osdr_expression = pd.read_parquet(cohort_root / "osdr_expression_v3.parquet")
    osdr_expression.index = osdr_expression.index.astype(str)
    osdr_expression = osdr_expression.reindex(sample_ids)
    genes = [column for column in osdr_expression.columns if column not in METADATA_COLUMNS]
    if list(info.gene_columns) != genes:
        raise ValueError("GTEx and OSDR raw gene order differs")
    osdr_raw = osdr_expression[genes].to_numpy(dtype=np.float32)

    alphas = tuple(float(value) for value in protocol["classifier"]["alpha_grid"])
    if args.smoke:
        alphas = (alphas[0], alphas[-1])
    folds = int(protocol["classifier"]["donor_grouped_folds"])
    results = {}
    predictions = []
    raw_result = fit_gtex_apply_osdr(
        gtex_raw,
        gtex_labels,
        gtex_donors,
        osdr_raw,
        osdr_labels,
        alphas=alphas,
        folds=folds,
        seed=int(protocol["classifier"]["random_seed"]),
        organ_order=organ_order,
    )
    raw_predictions = raw_result.pop("predictions")
    results["raw_expression"] = raw_result
    for sample_id, truth, prediction in zip(sample_ids, osdr_labels, raw_predictions):
        predictions.append({"representation": "raw_expression", "seed": -1, "sample_id": sample_id, "true_organ": truth, "predicted_organ": prediction})

    embedding_accuracies = []
    for seed in SEEDS:
        with np.load(gtex_paths[seed], allow_pickle=False) as archive:
            gtex_hidden = archive["h_canon"][keep_gtex].astype(np.float32)
        with np.load(osdr_root / f"seed{seed}_features.npz", allow_pickle=False) as archive:
            if not np.array_equal(archive["sample_ids"].astype(str), sample_ids):
                raise ValueError(f"OSDR feature membership differs: {seed}")
            osdr_hidden = archive["feature__pooled_hidden"].astype(np.float32)
        result = fit_gtex_apply_osdr(
            gtex_hidden,
            gtex_labels,
            gtex_donors,
            osdr_hidden,
            osdr_labels,
            alphas=alphas,
            folds=folds,
            seed=seed,
            organ_order=organ_order,
        )
        predicted = result.pop("predictions")
        results[f"seed{seed}__pooled_hidden"] = result
        embedding_accuracies.append(result["balanced_accuracy"])
        for sample_id, truth, prediction in zip(sample_ids, osdr_labels, predicted):
            predictions.append({"representation": "pooled_hidden", "seed": seed, "sample_id": sample_id, "true_organ": truth, "predicted_organ": prediction})

    verdict = frozen_verdict(
        results["raw_expression"]["balanced_accuracy"],
        embedding_accuracies,
        protocol["thresholds"],
    )
    predictions_path = output_dir / "cross_species_predictions.csv"
    pd.DataFrame(predictions).to_csv(predictions_path, index=False)
    report = {
        "schema_version": 1,
        "status": "complete",
        "role": protocol["role"],
        "smoke": bool(args.smoke),
        "protocol_sha256": sha256_file(protocol_path),
        "shared_organs": list(organ_order),
        "gtex_rows": int(np.sum(keep_gtex)),
        "gtex_donors": int(np.unique(gtex_donors).size),
        "osdr_rows": int(len(osdr_labels)),
        "results": results,
        "verdict": verdict,
        "prior_d1b_status": "D1B_CONFOUNDED_UNINFORMATIVE",
        "best_seed_or_condition_selection": False,
        "final_confirmation": False,
        "predictions_sha256": sha256_file(predictions_path),
    }
    report_path = output_dir / "cross_species_organ_transfer_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    checksums = {
        report_path.name: sha256_file(report_path),
        predictions_path.name: sha256_file(predictions_path),
    }
    (output_dir / "IMMUTABLE_SHA256SUMS").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in sorted(checksums.items()))
    )
    (output_dir / "COMPLETE").write_text("complete\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
