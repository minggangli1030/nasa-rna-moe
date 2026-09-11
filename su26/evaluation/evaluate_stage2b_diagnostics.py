#!/usr/bin/env python3
"""Evaluate frozen Stage 2B B0-B4 diagnostics from canonical numeric caches."""

from __future__ import annotations

import argparse
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

from core.stage2b_diagnostics import (  # noqa: E402
    array_sha256,
    fixed_decoder_ridge,
    grouped_ridge_predictions,
)
from core.stage2b_metrics import rank_record, ridge_effective_dof  # noqa: E402
from core.train_manifest import sha256_file  # noqa: E402
from core.train_stage2_aligned_program_repair import _load_basis  # noqa: E402


SEEDS = (17, 42, 101)


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _parse_seed_paths(values: list[str]) -> dict[int, Path]:
    parsed = {}
    for value in values:
        seed_text, separator, path_text = value.partition("=")
        if not separator:
            raise ValueError("cache roots must use SEED=PATH")
        parsed[int(seed_text)] = Path(path_text)
    if tuple(sorted(parsed)) != SEEDS:
        raise ValueError(f"cache roots must provide exactly {SEEDS}")
    return parsed


def _safe_corr(a: np.ndarray, b: np.ndarray) -> float:
    x = np.asarray(a, dtype=np.float64)
    y = np.asarray(b, dtype=np.float64)
    if np.std(x) == 0 or np.std(y) == 0:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def _component_correlations(a: np.ndarray, b: np.ndarray) -> list[float]:
    return [_safe_corr(a[:, index], b[:, index]) for index in range(a.shape[1])]


def _canonical_correlations(a: np.ndarray, b: np.ndarray) -> list[float]:
    x = np.asarray(a, dtype=np.float64)
    y = np.asarray(b, dtype=np.float64)
    x = x - x.mean(axis=0, keepdims=True)
    y = y - y.mean(axis=0, keepdims=True)
    ux, sx, _ = np.linalg.svd(x, full_matrices=False)
    uy, sy, _ = np.linalg.svd(y, full_matrices=False)
    rank_x = int(np.sum(sx > sx.max(initial=0) * 1e-10))
    rank_y = int(np.sum(sy > sy.max(initial=0) * 1e-10))
    if min(rank_x, rank_y) == 0:
        return []
    singular = np.linalg.svd(
        ux[:, :rank_x].T @ uy[:, :rank_y], compute_uv=False
    )
    return singular.astype(float).tolist()


def _principal_angles(a: np.ndarray, b: np.ndarray, components: int = 10) -> list[float]:
    _, _, va = np.linalg.svd(a - a.mean(axis=0), full_matrices=False)
    _, _, vb = np.linalg.svd(b - b.mean(axis=0), full_matrices=False)
    k = min(components, len(va), len(vb))
    singular = np.linalg.svd(va[:k] @ vb[:k].T, compute_uv=False)
    return np.degrees(np.arccos(np.clip(singular, -1.0, 1.0))).astype(float).tolist()


def _load_cache(
    root: Path, seed: int, protocol_sha: str, expected_rows: int
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray], dict[str, Any]]:
    metadata_path = root / "run_metadata.json"
    metadata = json.loads(metadata_path.read_text())
    if (
        metadata.get("status") != "complete"
        or metadata.get("mechanical_only") is not False
        or int(metadata.get("seed", -1)) != seed
        or metadata.get("protocol_sha256") != protocol_sha
        or int(metadata.get("rows", -1)) != expected_rows
    ):
        raise ValueError(f"seed {seed} canonical cache metadata is not a full valid run")
    cache_path = root / "canonical_cache.npz"
    b1_path = root / "b1_mask_probe.npz"
    if sha256_file(cache_path) != metadata["hashes"]["canonical_cache_sha256"]:
        raise ValueError(f"seed {seed} canonical cache hash mismatch")
    if sha256_file(b1_path) != metadata["hashes"]["b1_mask_probe_sha256"]:
        raise ValueError(f"seed {seed} B1 cache hash mismatch")
    with np.load(cache_path, allow_pickle=False) as archive:
        cache = {name: archive[name] for name in archive.files}
    with np.load(b1_path, allow_pickle=False) as archive:
        b1 = {name: archive[name] for name in archive.files}
    for name, value in cache.items():
        if array_sha256(value) != metadata["hashes"]["canonical_arrays"][name]:
            raise ValueError(f"seed {seed} canonical array {name} hash mismatch")
    for name, value in b1.items():
        if array_sha256(value) != metadata["hashes"]["b1_arrays"][name]:
            raise ValueError(f"seed {seed} B1 array {name} hash mismatch")
    return cache, b1, metadata


def _rank_views(
    coefficients: np.ndarray,
    decoder: np.ndarray,
    frame: pd.DataFrame,
    ridge: float,
    effective_dof: float,
) -> list[dict]:
    raw = np.asarray(coefficients, dtype=np.float64)
    scale = raw.std(axis=0, ddof=1)
    standardized = (raw - raw.mean(axis=0)) / np.maximum(scale, 1e-8)
    gram = decoder @ decoder.T
    eigenvalue, eigenvector = np.linalg.eigh(gram)
    whitened = raw @ eigenvector @ np.diag(np.sqrt(np.maximum(eigenvalue, 0)))
    conventions = {
        "raw": raw,
        "standardized": standardized,
        "whitened": whitened,
    }
    records = []
    donors = frame["series_group_id"].astype(str).to_numpy()
    organs = frame["organ_k8"].to_numpy(dtype=np.int64)
    for convention, values in conventions.items():
        donor_values = pd.DataFrame(values).assign(donor=donors).groupby("donor").mean().to_numpy()
        organ_mean = np.stack(
            [values[organs == organ].mean(axis=0) for organ in range(8)]
        )
        within = values - organ_mean[organs]
        for unit, matrix in (
            ("sample", values),
            ("donor", donor_values),
            ("within_organ", within),
        ):
            records.append(
                rank_record(
                    matrix,
                    convention=convention,
                    aggregation_unit=unit,
                    ridge_lambda=ridge,
                    effective_dof=effective_dof,
                ).to_dict()
            )
    return records


def _bootstrap_ceiling(
    coefficients: np.ndarray,
    frame: pd.DataFrame,
    *,
    ridge: float,
    effective_dof: float,
    replicates: int,
    seed: int,
) -> dict[str, Any]:
    donors = frame["series_group_id"].astype(str).to_numpy()
    organs = frame["organ_k8"].to_numpy(dtype=np.int64)
    unique = np.unique(donors)
    rows = {donor: np.flatnonzero(donors == donor) for donor in unique}
    rng = np.random.default_rng(seed)
    distributions = {"sample": [], "donor": [], "within_organ": []}
    for _ in range(replicates):
        sampled = rng.choice(unique, len(unique), replace=True)
        sample_rows = np.concatenate([rows[value] for value in sampled])
        values = coefficients[sample_rows]
        sampled_organs = organs[sample_rows]
        donor_means = np.stack([coefficients[rows[value]].mean(axis=0) for value in sampled])
        organ_means = np.stack(
            [
                values[sampled_organs == organ].mean(axis=0)
                if np.any(sampled_organs == organ)
                else values.mean(axis=0)
                for organ in range(8)
            ]
        )
        within = values - organ_means[sampled_organs]
        for unit, matrix in (
            ("sample", values),
            ("donor", donor_means),
            ("within_organ", within),
        ):
            distributions[unit].append(
                rank_record(
                    matrix,
                    convention="raw",
                    aggregation_unit=unit,
                    ridge_lambda=ridge,
                    effective_dof=effective_dof,
                ).entropy_rank
            )
    return {
        unit: {
            "median": float(np.median(values)),
            "ci95": np.quantile(values, [0.025, 0.975]).astype(float).tolist(),
            "replicates": replicates,
        }
        for unit, values in distributions.items()
    }


def _one_hot(values: pd.Series) -> np.ndarray:
    codes = pd.Categorical(values.astype(str))
    return np.eye(len(codes.categories), dtype=np.float64)[codes.codes]


def _cross_validated_r2(
    x: np.ndarray,
    y: np.ndarray,
    donors: np.ndarray,
    folds: int,
    seed: int,
) -> dict[str, Any]:
    target = np.asarray(y, dtype=np.float64)
    if target.ndim == 1:
        target = target[:, None]
    prediction, records = grouped_ridge_predictions(
        x,
        target,
        donors,
        folds=folds,
        fold_seed=seed,
        ridge_grid=[1e-4, 1e-3, 1e-2, 1e-1, 1.0, 10.0],
    )
    baseline = np.broadcast_to(target.mean(axis=0), target.shape)
    denominator = float(np.mean(np.square(target - baseline)))
    mse = float(np.mean(np.square(target - prediction)))
    return {
        "held_out_mse": mse,
        "incremental_r2": 0.0 if denominator == 0 else 1.0 - mse / denominator,
        "folds": records,
    }


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    protocol_path = Path(args.protocol)
    if sha256_file(protocol_path) != args.expected_protocol_sha256:
        raise ValueError("Stage 2B protocol SHA256 mismatch")
    protocol = json.loads(protocol_path.read_text())
    if protocol.get("status") != "frozen_before_stage2b_diagnostic_access":
        raise ValueError("Stage 2B protocol is not frozen")
    manifest = pd.read_parquet(args.manifest)
    if sha256_file(args.manifest) != protocol["inputs"]["manifest_sha256"]:
        raise ValueError("manifest differs from protocol")
    training = (
        manifest.loc[
            manifest["split"].astype(str).eq("train")
            & manifest["balanced_train"].astype(bool)
        ]
        .sort_values("sample_id")
        .reset_index(drop=True)
    )
    with np.load(args.axis_definitions, allow_pickle=False) as archive:
        score_indices = archive["score_gene_indices"].astype(np.int64)
        gene_names = archive["gene_names"].astype(str).tolist()
    program, random, hashes = _load_basis(
        Path(args.basis_bundle),
        expected_sha256=protocol["inputs"]["basis_bundle_sha256"],
        gene_names=gene_names,
        score_indices=score_indices,
    )
    if hashes["program_decoder_sha256"] != protocol["inputs"]["program_decoder_sha256"]:
        raise ValueError("program decoder hash differs")
    roots = _parse_seed_paths(args.cache_root)
    caches, b1s, metadata = {}, {}, {}
    protocol_sha = sha256_file(protocol_path)
    for seed, root in roots.items():
        caches[seed], b1s[seed], metadata[seed] = _load_cache(
            root, seed, protocol_sha, len(training)
        )
        if not np.array_equal(caches[seed]["sample_ordinal"], np.arange(len(training))):
            raise ValueError(f"seed {seed} cache rows do not reconstruct manifest")
    ridge_values = {float(value["ridge_lambda"]) for value in metadata.values()}
    if len(ridge_values) != 1:
        raise ValueError("canonical caches do not share one ridge lambda")
    ridge = ridge_values.pop()
    effective_dof = ridge_effective_dof(program, ridge)
    donors = training["series_group_id"].astype(str).to_numpy()

    b0_probes = []
    ridge_grid = protocol["b0_cross_trunk"]["ridge_grid"]
    for source in SEEDS:
        for target in SEEDS:
            predicted, folds = grouped_ridge_predictions(
                caches[source]["h_canon"],
                caches[target]["c_canon"],
                donors,
                folds=int(protocol["b0_cross_trunk"]["probe_folds"]),
                fold_seed=int(protocol["ridge_selection"]["fold_seed"]),
                ridge_grid=ridge_grid,
            )
            correlations = _component_correlations(
                caches[target]["c_canon"], predicted
            )
            base_mse = float(np.mean(np.square(caches[target]["r_full"])))
            reconstructed_mse = float(
                np.mean(
                    np.square(
                        caches[target]["r_full"]
                        - predicted.astype(np.float64) @ program.astype(np.float64)
                    )
                )
            )
            b0_probes.append(
                {
                    "source_seed": source,
                    "target_seed": target,
                    "median_component_pearson": float(np.median(correlations)),
                    "component_pearson": correlations,
                    "gene_space_error_recovery_fraction": 1.0
                    - reconstructed_mse / base_mse,
                    "held_out_gene_space_mse": reconstructed_mse,
                    "predicted_entropy_rank": rank_record(
                        predicted,
                        convention="raw",
                        aggregation_unit="sample",
                        ridge_lambda=ridge,
                        effective_dof=effective_dof,
                    ).entropy_rank,
                    "folds": folds,
                }
            )
    target_agreements = []
    for index, first in enumerate(SEEDS):
        for second in SEEDS[index + 1 :]:
            a = caches[first]["c_canon"]
            b = caches[second]["c_canon"]
            random_a = fixed_decoder_ridge(caches[first]["r_full"], random, ridge)
            random_b = fixed_decoder_ridge(caches[second]["r_full"], random, ridge)
            component = _component_correlations(a, b)
            cca = _canonical_correlations(a, b)
            random_cca = _canonical_correlations(random_a, random_b)
            target_agreements.append(
                {
                    "first_seed": first,
                    "second_seed": second,
                    "median_component_pearson": float(np.median(component)),
                    "component_pearson": component,
                    "canonical_correlations": cca,
                    "median_canonical_correlation": float(np.median(cca)),
                    "random_basis_median_canonical_correlation": float(
                        np.median(random_cca)
                    ),
                    "canonical_correlation_margin_over_random_basis": float(
                        np.median(cca) - np.median(random_cca)
                    ),
                    "top10_principal_angles_degrees": _principal_angles(a, b),
                }
            )
    agreement_rule = protocol["b0_cross_trunk"]["high_target_agreement_rule"]
    target_high = all(
        row["median_component_pearson"]
        >= agreement_rule["minimum_median_component_pearson"]
        and row["canonical_correlation_margin_over_random_basis"]
        >= agreement_rule[
            "minimum_median_canonical_correlation_margin_over_random_basis"
        ]
        for row in target_agreements
    )
    probe_rule = protocol["b0_cross_trunk"]["high_probe_rule"]
    cross_rows = [
        row for row in b0_probes if row["source_seed"] != row["target_seed"]
    ]
    cross_high = all(
        row["median_component_pearson"]
        >= probe_rule["minimum_median_component_pearson"]
        and row["gene_space_error_recovery_fraction"]
        >= probe_rule["minimum_gene_space_error_recovery_fraction"]
        for row in cross_rows
    )
    if target_high and cross_high:
        b0_branch = "cross_trunk_reproducible_sample_associated_structure"
    elif target_high:
        b0_branch = "shared_target_trunk_specific_map"
    else:
        b0_branch = "trunk_specific_oracle_target_rank_descriptive_only"
    seed17 = next(
        row
        for row in b0_probes
        if row["source_seed"] == 17 and row["target_seed"] == 17
    )
    replication_rule = protocol["b0_cross_trunk"]["seed17_replication_rule"]
    replication_pass = (
        seed17["median_component_pearson"]
        >= replication_rule["minimum_median_component_pearson"]
        and seed17["gene_space_error_recovery_fraction"]
        >= replication_rule["minimum_gene_space_error_recovery_fraction"]
    )

    b1_reports = {}
    for seed in SEEDS:
        b1 = b1s[seed]
        full = caches[seed]["c_canon"][b1["sample_ordinal"]]
        seed_report = {}
        for arm in (
            "behavioral_coefficients",
            "geometric_coefficients",
            "combined_legacy_coefficients",
        ):
            values = b1[arm]
            denominator = np.linalg.norm(values, axis=2) * np.linalg.norm(
                full[:, None, :], axis=2
            )
            cosine = np.sum(values * full[:, None, :], axis=2) / np.maximum(
                denominator, 1e-12
            )
            mask_variance = np.var(values, axis=1).mean(axis=0)
            sample_variance = np.var(values.mean(axis=1), axis=0)
            seed_report[arm] = {
                "median_partial_to_full_cosine": float(np.median(cosine)),
                "median_mask_variance_to_sample_variance": float(
                    np.median(mask_variance / np.maximum(sample_variance, 1e-12))
                ),
            }
        seed_report["median_gram_condition_number"] = float(
            np.median(b1["gram_condition_number"])
        )
        seed_report["median_maximum_leverage"] = float(
            np.median(b1["maximum_leverage"])
        )
        b1_reports[str(seed)] = seed_report

    ranks = {
        str(seed): _rank_views(
            caches[seed]["c_canon"], program, training, ridge, effective_dof
        )
        for seed in SEEDS
    }
    ceilings = {
        str(seed): _bootstrap_ceiling(
            caches[seed]["c_canon"],
            training,
            ridge=ridge,
            effective_dof=effective_dof,
            replicates=int(protocol["b3_ceiling"]["replicates"]),
            seed=int(protocol["b3_ceiling"]["seed"]) + seed,
        )
        for seed in SEEDS
    }

    inventory = {}
    for field in protocol["b4_metadata"]["candidate_fields"]:
        if field not in training.columns:
            inventory[field] = {"status": "missing"}
        else:
            values = training[field]
            inventory[field] = {
                "status": "available",
                "missing_fraction": float(values.isna().mean()),
                "unique_nonmissing": int(values.nunique(dropna=True)),
            }
    supported = [
        field
        for field, record in inventory.items()
        if record["status"] == "available"
        and record["missing_fraction"] == 0.0
        and record["unique_nonmissing"] > 1
    ]
    metadata_models = {}
    for seed in SEEDS:
        seed_models = {}
        for field in supported:
            x = _one_hot(training[field])
            seed_models[field] = {
                "pooled_reconstruction_error": _cross_validated_r2(
                    x,
                    caches[seed]["pooled_mse"],
                    donors,
                    int(protocol["b4_metadata"]["grouped_folds"]),
                    20260730 + seed,
                ),
                "post_private_coefficients": _cross_validated_r2(
                    x,
                    caches[seed]["c_canon"],
                    donors,
                    int(protocol["b4_metadata"]["grouped_folds"]),
                    20260730 + seed,
                ),
            }
        metadata_models[str(seed)] = seed_models
    margin = float(
        protocol["b4_metadata"]["minimum_incremental_r2_margin_for_pause"]
    )
    pause_fields = []
    for field in supported:
        if field == "organ":
            continue
        comparisons = []
        for seed in SEEDS:
            fields = metadata_models[str(seed)]
            if "organ" not in fields:
                continue
            for outcome in ("pooled_reconstruction_error", "post_private_coefficients"):
                comparisons.append(
                    fields[field][outcome]["incremental_r2"]
                    - fields["organ"][outcome]["incremental_r2"]
                    > margin
                )
        if comparisons and all(comparisons):
            pause_fields.append(field)
    b4_decision = (
        "human_review_axis_amendment_required"
        if pause_fields
        else "organ_remains_authorized_primary_axis"
    )

    report = {
        "schema_version": 1,
        "status": "complete",
        "protocol_sha256": protocol_sha,
        "claim_boundary": protocol["claim_boundary"],
        "shared_ridge_lambda": ridge,
        "ridge_effective_dof": effective_dof,
        "b0": {
            "replication_pass": replication_pass,
            "target_agreement_high": target_high,
            "cross_seed_probe_high": cross_high,
            "branch": b0_branch,
            "target_agreements": target_agreements,
            "probes": b0_probes,
        },
        "b1": b1_reports,
        "b2": {"rank_records": ranks},
        "b3": {
            "ceiling_is_gate_eligible": target_high,
            "bootstrap_ceilings": ceilings,
        },
        "b4": {
            "inventory": inventory,
            "models": metadata_models,
            "pause_fields": pause_fields,
            "decision": b4_decision,
        },
        "phase_c_conditioning_axis_authorized": b4_decision
        == "organ_remains_authorized_primary_axis",
        "completed_at_utc": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
    }
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    report_path = output_dir / "b0_b4_report.json"
    _atomic_json(report_path, report)
    pd.DataFrame(b0_probes).drop(columns=["component_pearson", "folds"]).to_csv(
        output_dir / "b0_probe_summary.csv", index=False
    )
    pd.DataFrame(target_agreements).drop(
        columns=[
            "component_pearson",
            "canonical_correlations",
            "top10_principal_angles_degrees",
        ]
    ).to_csv(output_dir / "b0_target_agreement_summary.csv", index=False)
    artifact_paths = [
        report_path,
        output_dir / "b0_probe_summary.csv",
        output_dir / "b0_target_agreement_summary.csv",
    ]
    (output_dir / "IMMUTABLE_SHA256SUMS").write_text(
        "\n".join(f"{sha256_file(path)}  {path.name}" for path in artifact_paths)
        + "\n"
    )
    (output_dir / "COMPLETE").touch()
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--axis-definitions", required=True)
    parser.add_argument("--basis-bundle", required=True)
    parser.add_argument("--cache-root", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser


def main() -> None:
    report = evaluate(build_parser().parse_args())
    print(
        json.dumps(
            {
                "status": report["status"],
                "b0_branch": report["b0"]["branch"],
                "b4_decision": report["b4"]["decision"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
