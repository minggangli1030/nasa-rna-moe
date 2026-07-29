#!/usr/bin/env python3
"""Evaluate frozen organ-expert effects in training-derived expression modules."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.train_manifest import sha256_file
from evaluation.evaluate_stage2_expert_residual_programs import (
    _cosine,
    _donor_means,
    _scalar_bootstrap,
    _spearman,
    _top_jaccard,
)
from evaluation.freeze_gtex_to_archs4_candidates import ORGANS, SEEDS


def _load_cache(path: Path, expected_sha: str, seed: int) -> dict[str, np.ndarray]:
    if sha256_file(path) != expected_sha:
        raise ValueError(f"seed {seed} cache SHA256 mismatch")
    with np.load(path, allow_pickle=False) as archive:
        arrays = {name: archive[name] for name in archive.files}
    metadata = json.loads(str(arrays.pop("metadata_json")))
    if (
        metadata.get("status") != "complete"
        or int(metadata.get("seed", -1)) != seed
        or metadata.get("model_fitting_performed") is not False
        or metadata.get("archs4_accessed") is not False
        or metadata.get("original_calibration_score_roundtrip_verified") is not True
    ):
        raise ValueError(f"seed {seed} cache metadata violates protocol")
    return arrays


def _training_basis(
    expression_path: Path,
    manifest: pd.DataFrame,
    score_genes: list[str],
    config: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    train = manifest.loc[manifest["split"].astype(str) == "train"]
    ids = train["sample_id"].astype(str).tolist()
    frame = pd.read_parquet(
        expression_path, columns=["sample_id", *score_genes]
    )
    frame["sample_id"] = frame["sample_id"].astype(str)
    frame = frame.set_index("sample_id").reindex(ids)
    if frame.isna().any().any():
        raise ValueError("training expression does not match manifest")
    values = np.log1p(frame.to_numpy(dtype=np.float32))
    donors = train["series_group_id"].astype(str).to_numpy()
    donor_counts = pd.Series(donors).value_counts()
    weights = np.asarray([1.0 / donor_counts[value] for value in donors])
    weights /= weights.sum()
    mean = np.sum(values * weights[:, None], axis=0)
    variance = np.sum(np.square(values - mean) * weights[:, None], axis=0)
    scale = np.sqrt(np.maximum(variance, 1e-8))
    standardized = (values - mean) / scale
    weighted = standardized * np.sqrt(weights * len(weights))[:, None]
    pca = PCA(
        n_components=int(config["components"]),
        svd_solver="randomized",
        random_state=int(config["random_state"]),
        n_oversamples=int(config["n_oversamples"]),
        iterated_power=int(config["iterated_power"]),
    )
    pca.fit(weighted)
    components = pca.components_.astype(np.float64)
    for index in range(len(components)):
        anchor = int(np.argmax(np.abs(components[index])))
        if components[index, anchor] < 0:
            components[index] *= -1
    top = np.stack([
        np.argpartition(np.abs(component), -100)[-100:]
        for component in components
    ])
    return mean, scale, components, top


def _module_vectors(
    cache: dict[str, np.ndarray],
    selected: np.ndarray,
    donors: np.ndarray,
    *,
    scale: np.ndarray,
    components: np.ndarray,
    top: np.ndarray,
) -> dict[str, np.ndarray]:
    correction = cache["specialist_minus_pooled_adapter_prediction"][selected]
    efficacy = (
        cache["pooled_adapter_squared_error"][selected]
        - cache["specialist_squared_error"][selected]
    )
    semantic = (
        cache["random_assigned_mean_squared_error"][selected]
        - cache["specialist_squared_error"][selected]
    )
    _, correction_donor = _donor_means(correction, donors)
    _, efficacy_donor = _donor_means(efficacy, donors)
    _, semantic_donor = _donor_means(semantic, donors)
    correction_gene = correction_donor.mean(axis=0) / scale
    correction_module = correction_gene @ components.T
    efficacy_gene = efficacy_donor.mean(axis=0)
    efficacy_module = np.asarray([efficacy_gene[index].mean() for index in top])
    return {
        "correction_module": correction_module,
        "efficacy_module": efficacy_module,
        "efficacy_donor": efficacy_donor,
        "semantic_donor": semantic_donor,
    }


def _stratum_result(
    seed_values: list[dict[str, np.ndarray]],
    *,
    gate: dict[str, Any],
    bootstrap_seed: int,
) -> dict[str, Any]:
    pairs = ((0, 1), (0, 2), (1, 2))
    corrections = [value["correction_module"] for value in seed_values]
    efficacies = [value["efficacy_module"] for value in seed_values]
    cosines = [_cosine(corrections[a], corrections[b]) for a, b in pairs]
    spearman = [_spearman(efficacies[a], efficacies[b]) for a, b in pairs]
    jaccard = [_top_jaccard(corrections[a], corrections[b], 8) for a, b in pairs]
    efficacy_donor = np.mean(
        np.stack([value["efficacy_donor"] for value in seed_values]), axis=0
    )
    semantic_donor = np.mean(
        np.stack([value["semantic_donor"] for value in seed_values]), axis=0
    )
    efficacy_scalar = _scalar_bootstrap(
        efficacy_donor,
        replicates=int(gate["bootstrap_replicates"]),
        seed=bootstrap_seed,
    )
    semantic_scalar = _scalar_bootstrap(
        semantic_donor,
        replicates=int(gate["bootstrap_replicates"]),
        seed=bootstrap_seed + 1,
    )
    passed = bool(
        min(cosines) >= float(gate["minimum_pairwise_module_correction_cosine"])
        and min(spearman) >= float(gate["minimum_pairwise_module_efficacy_spearman"])
        and min(jaccard) >= float(gate["minimum_pairwise_top8_module_jaccard"])
        and efficacy_scalar[1]
        > float(gate["overall_specialist_vs_generic_95ci_lower_bound"])
        and semantic_scalar[1]
        > float(gate["overall_semantic_specificity_95ci_lower_bound"])
    )
    return {
        "min_module_correction_cosine": min(cosines),
        "median_module_correction_cosine": float(np.median(cosines)),
        "min_module_efficacy_spearman": min(spearman),
        "median_module_efficacy_spearman": float(np.median(spearman)),
        "min_top8_module_jaccard": min(jaccard),
        "efficacy_mean": efficacy_scalar[0],
        "efficacy_95ci_low": efficacy_scalar[1],
        "efficacy_95ci_high": efficacy_scalar[2],
        "semantic_mean": semantic_scalar[0],
        "semantic_95ci_low": semantic_scalar[1],
        "semantic_95ci_high": semantic_scalar[2],
        "module_gate_pass": passed,
        "mean_correction_module": np.mean(np.stack(corrections), axis=0),
    }


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    protocol_path = Path(args.protocol)
    if sha256_file(protocol_path) != args.expected_protocol_sha256:
        raise ValueError("protocol SHA256 mismatch")
    protocol = json.loads(protocol_path.read_text())
    if protocol.get("status") != "frozen_before_multiscale_outputs":
        raise ValueError("multiscale protocol is not frozen")
    expression_path = Path(args.expression_parquet)
    manifest_path = Path(args.manifest)
    axes_path = Path(args.axis_definitions)
    expected = protocol["inputs"]
    for path, key in (
        (expression_path, "expression_sha256"),
        (manifest_path, "manifest_sha256"),
        (axes_path, "axis_definitions_sha256"),
    ):
        if sha256_file(path) != expected[key]:
            raise ValueError(f"{key} mismatch")
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise FileExistsError(output_dir)
    output_dir.mkdir(parents=True)
    paths = [Path(value) for value in args.seed_cache]
    if len(paths) != 3:
        raise ValueError("exactly three seed caches are required")
    caches = {
        seed: _load_cache(
            path, expected["seed_cache_sha256"][str(seed)], seed
        )
        for seed, path in zip(SEEDS, paths)
    }
    first = caches[SEEDS[0]]
    for seed in SEEDS[1:]:
        for name in ("sample_ids", "donors", "organs", "score_gene_names"):
            if not np.array_equal(first[name], caches[seed][name]):
                raise ValueError(f"seed {seed} {name} differs")
    manifest = pd.read_parquet(manifest_path)
    calibration = manifest.loc[manifest["split"].astype(str) == "calibration"].copy()
    if calibration["sample_id"].astype(str).tolist() != first["sample_ids"].astype(str).tolist():
        raise ValueError("calibration manifest order differs from score caches")
    sites = calibration["tissue_site"].astype(str).to_numpy()
    organs = calibration["organ"].astype(str).to_numpy()
    donors_all = calibration["series_group_id"].astype(str).to_numpy()
    eligible = list(protocol["attributes"]["eligible_tissue_sites"])
    observed_eligible = sorted(
        calibration.groupby("tissue_site")["series_group_id"].nunique()
        .loc[lambda x: x >= int(protocol["attributes"]["minimum_calibration_donors"])]
        .index.astype(str)
    )
    if sorted(eligible) != observed_eligible:
        raise ValueError("eligible tissue-site set differs from frozen protocol")
    mean, scale, components, top = _training_basis(
        expression_path,
        manifest,
        first["score_gene_names"].astype(str).tolist(),
        protocol["basis"],
    )
    np.savez_compressed(
        output_dir / "training_expression_basis.npz",
        gene_names=first["score_gene_names"].astype(str),
        weighted_mean=mean,
        weighted_scale=scale,
        components=components,
        top100_gene_indices=top,
    )
    gate = {**protocol["gate"]}
    organ_rows = []
    organ_vectors = {}
    for index, organ in enumerate(ORGANS):
        selected = organs == organ
        seed_values = [
            _module_vectors(
                caches[seed],
                selected,
                donors_all[selected],
                scale=scale,
                components=components,
                top=top,
            )
            for seed in SEEDS
        ]
        result = _stratum_result(
            seed_values,
            gate=gate,
            bootstrap_seed=int(gate["bootstrap_seed"]) + index * 10,
        )
        organ_vectors[organ] = result.pop("mean_correction_module")
        organ_rows.append({
            "organ": organ,
            "samples": int(selected.sum()),
            "donors": int(len(set(donors_all[selected]))),
            **result,
        })
    site_rows = []
    for index, site in enumerate(eligible):
        selected = sites == site
        organ_values = sorted(set(organs[selected]))
        if len(organ_values) != 1:
            raise ValueError(f"site {site} maps to multiple organs")
        seed_values = [
            _module_vectors(
                caches[seed],
                selected,
                donors_all[selected],
                scale=scale,
                components=components,
                top=top,
            )
            for seed in SEEDS
        ]
        result = _stratum_result(
            seed_values,
            gate=gate,
            bootstrap_seed=int(gate["bootstrap_seed"]) + 1000 + index * 10,
        )
        result.pop("mean_correction_module")
        site_rows.append({
            "organ": organ_values[0],
            "tissue_site": site,
            "samples": int(selected.sum()),
            "donors": int(len(set(donors_all[selected]))),
            **result,
        })
    organ_frame = pd.DataFrame(organ_rows)
    site_frame = pd.DataFrame(site_rows)
    organ_frame.to_csv(output_dir / "organ_module_reproducibility.csv", index=False)
    site_frame.to_csv(output_dir / "tissue_site_module_reproducibility.csv", index=False)
    similarity = np.asarray([
        [_cosine(organ_vectors[left], organ_vectors[right]) for right in ORGANS]
        for left in ORGANS
    ])
    pd.DataFrame(similarity, index=ORGANS, columns=ORGANS).to_csv(
        output_dir / "organ_module_correction_cosine.csv"
    )
    fig, axis = plt.subplots(figsize=(8.4, 7.0))
    image = axis.imshow(similarity, cmap="RdYlBu", vmin=-1, vmax=1)
    axis.set_xticks(range(8), labels=ORGANS, rotation=45, ha="right")
    axis.set_yticks(range(8), labels=ORGANS)
    axis.set_title("Training-derived module correction similarity")
    fig.colorbar(image, ax=axis, label="cosine similarity")
    fig.tight_layout()
    fig.savefig(output_dir / "organ_module_correction_cosine.png", dpi=180)
    plt.close(fig)
    organ_passes = int(organ_frame["module_gate_pass"].sum())
    multi_site_organs = {
        organ for organ, count in site_frame.groupby("organ").size().items() if count > 1
    }
    passing_sites = site_frame.loc[
        site_frame["module_gate_pass"] & site_frame["organ"].isin(multi_site_organs)
    ]
    site_passes = int(len(passing_sites))
    site_organs = int(passing_sites["organ"].nunique())
    if organ_passes >= 4:
        decision = "coarse_programs_reproducible_freeze_predictor"
    elif site_passes >= 8 and site_organs >= 3:
        decision = "hierarchical_site_signal_freeze_factorized_predictor"
    else:
        decision = "no_stable_existing_representation_design_explicit_program_heads"
    report = {
        "schema_version": 1,
        "status": "complete",
        "research_stage": "stage2_multiscale_multi_attribute_pivot",
        "code_commit": args.code_commit,
        "protocol_sha256": args.expected_protocol_sha256,
        "model_fitting_performed": False,
        "archs4_accessed": False,
        "basis_fit_role": "GTEx training expression only",
        "organ_gate_passes": organ_passes,
        "eligible_tissue_sites": len(site_frame),
        "multi_site_gate_passes": site_passes,
        "multi_site_organs_with_pass": site_organs,
        "decision": decision,
        "basis": {
            "components": int(len(components)),
            "explained_variance_not_used_for_selection": True,
            "basis_sha256": sha256_file(output_dir / "training_expression_basis.npz"),
        },
        "limitations": [
            "Continuous expression components are statistical modules, not annotated biological pathways.",
            "Tissue-site results remain GTEx donor-disjoint development evidence.",
            "Reproducibility does not itself prove beneficial parameter or data sharing."
        ],
    }
    (output_dir / "evaluation_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    checksum_rows = [
        f"{sha256_file(path)}  {path.name}"
        for path in sorted(output_dir.iterdir())
        if path.is_file() and path.name != "IMMUTABLE_SHA256SUMS"
    ]
    (output_dir / "IMMUTABLE_SHA256SUMS").write_text(
        "\n".join(checksum_rows) + "\n"
    )
    (output_dir / "COMPLETE").touch()
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--seed-cache", action="append", required=True)
    parser.add_argument("--expression-parquet", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--axis-definitions", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--code-commit", required=True)
    return parser


if __name__ == "__main__":
    print(json.dumps(evaluate(build_parser().parse_args()), indent=2, sort_keys=True))
