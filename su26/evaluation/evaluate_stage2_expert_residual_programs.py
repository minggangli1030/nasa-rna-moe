#!/usr/bin/env python3
"""Evaluate seed-stable functional programs from frozen organ experts."""

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


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.freeze_gtex_to_archs4_candidates import ORGANS, SEEDS
from core.train_manifest import sha256_file


def _cosine(left: np.ndarray, right: np.ndarray) -> float:
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    return float(np.dot(left, right) / denominator) if denominator else 0.0


def _spearman(left: np.ndarray, right: np.ndarray) -> float:
    a = pd.Series(left).rank(method="average").to_numpy()
    b = pd.Series(right).rank(method="average").to_numpy()
    return float(np.corrcoef(a, b)[0, 1])


def _top_jaccard(left: np.ndarray, right: np.ndarray, top_k: int) -> float:
    a = set(np.argpartition(np.abs(left), -top_k)[-top_k:].tolist())
    b = set(np.argpartition(np.abs(right), -top_k)[-top_k:].tolist())
    return float(len(a & b) / len(a | b))


def _donor_means(values: np.ndarray, donors: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    names = np.asarray(sorted(set(donors.astype(str))), dtype=str)
    means = np.stack([values[donors == donor].mean(axis=0) for donor in names])
    return names, means


def _bootstrap_ci(
    donor_values: np.ndarray,
    *,
    replicates: int,
    seed: int,
    levels: tuple[float, ...] = (0.95, 0.99),
) -> dict[float, tuple[np.ndarray, np.ndarray]]:
    rng = np.random.default_rng(seed)
    n = len(donor_values)
    samples = np.empty((replicates, donor_values.shape[1]), dtype=np.float32)
    for start in range(0, replicates, 100):
        stop = min(replicates, start + 100)
        indices = rng.integers(0, n, size=(stop - start, n))
        samples[start:stop] = donor_values[indices].mean(axis=1)
    output = {}
    for level in levels:
        tail = (1.0 - level) / 2.0
        output[level] = (
            np.quantile(samples, tail, axis=0),
            np.quantile(samples, 1.0 - tail, axis=0),
        )
    return output


def _scalar_bootstrap(
    donor_values: np.ndarray, *, replicates: int, seed: int
) -> tuple[float, float, float]:
    values = donor_values.mean(axis=1)
    ci = _bootstrap_ci(
        values[:, None], replicates=replicates, seed=seed, levels=(0.95,)
    )[0.95]
    return float(values.mean()), float(ci[0][0]), float(ci[1][0])


def _load_cache(path: Path, protocol_sha256: str, seed: int) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        arrays = {name: archive[name] for name in archive.files}
    metadata = json.loads(str(arrays.pop("metadata_json")))
    if (
        metadata.get("status") != "complete"
        or int(metadata.get("seed", -1)) != seed
        or metadata.get("protocol_sha256") != protocol_sha256
        or metadata.get("model_fitting_performed") is not False
        or metadata.get("archs4_accessed") is not False
        or metadata.get("original_calibration_score_roundtrip_verified") is not True
    ):
        raise ValueError(f"seed {seed} extraction metadata violates protocol")
    return arrays


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    protocol_path = Path(args.protocol)
    if sha256_file(protocol_path) != args.expected_protocol_sha256:
        raise ValueError("protocol SHA256 mismatch")
    protocol = json.loads(protocol_path.read_text())
    if protocol.get("status") != "frozen_before_representation_outputs":
        raise ValueError("representation protocol is not frozen")
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise FileExistsError(output_dir)
    output_dir.mkdir(parents=True)
    paths = [Path(value) for value in args.seed_cache]
    if len(paths) != 3:
        raise ValueError("exactly three seed caches are required")
    caches = {
        seed: _load_cache(path, args.expected_protocol_sha256, seed)
        for seed, path in zip(SEEDS, paths)
    }
    first = caches[SEEDS[0]]
    identity_names = ("sample_ids", "donors", "organs", "score_gene_indices", "score_gene_names")
    for seed in SEEDS[1:]:
        for name in identity_names:
            if not np.array_equal(first[name], caches[seed][name]):
                raise ValueError(f"seed {seed} {name} differs")
    genes = first["score_gene_names"].astype(str)
    donors = first["donors"].astype(str)
    organs = first["organs"].astype(str)
    replicates = int(protocol["reproducibility_metrics"]["bootstrap_replicates"])
    bootstrap_seed = int(protocol["reproducibility_metrics"]["bootstrap_seed"])
    gate = protocol["organ_representation_gate"]
    rows: list[dict[str, Any]] = []
    gene_rows: list[pd.DataFrame] = []
    correction_signatures: dict[str, np.ndarray] = {}
    efficacy_signatures: dict[str, np.ndarray] = {}
    organ_report: dict[str, Any] = {}
    pair_indices = ((0, 1), (0, 2), (1, 2))
    for organ_index, organ in enumerate(ORGANS):
        selected = organs == organ
        organ_donors = donors[selected]
        per_seed: dict[int, dict[str, np.ndarray]] = {}
        donor_names: np.ndarray | None = None
        for seed in SEEDS:
            cache = caches[seed]
            metrics = {
                "efficacy_vs_pooled": (
                    cache["pooled_squared_error"][selected]
                    - cache["specialist_squared_error"][selected]
                ),
                "efficacy_vs_generic": (
                    cache["pooled_adapter_squared_error"][selected]
                    - cache["specialist_squared_error"][selected]
                ),
                "semantic_vs_random": (
                    cache["random_assigned_mean_squared_error"][selected]
                    - cache["specialist_squared_error"][selected]
                ),
                "correction": cache[
                    "specialist_minus_pooled_adapter_prediction"
                ][selected],
                "random_correction": cache[
                    "random_mean_minus_pooled_adapter_prediction"
                ][selected],
            }
            per_seed[seed] = {}
            for name, values in metrics.items():
                names, means = _donor_means(values, organ_donors)
                if donor_names is None:
                    donor_names = names
                elif not np.array_equal(donor_names, names):
                    raise AssertionError("donor aggregation changed across seeds")
                per_seed[seed][name] = means
        assert donor_names is not None
        seed_correction = [per_seed[seed]["correction"].mean(axis=0) for seed in SEEDS]
        seed_efficacy = [
            per_seed[seed]["efficacy_vs_generic"].mean(axis=0) for seed in SEEDS
        ]
        seed_random_correction = [
            per_seed[seed]["random_correction"].mean(axis=0) for seed in SEEDS
        ]
        correction_cosines = [
            _cosine(seed_correction[a], seed_correction[b]) for a, b in pair_indices
        ]
        efficacy_spearman = [
            _spearman(seed_efficacy[a], seed_efficacy[b]) for a, b in pair_indices
        ]
        top_jaccards = [
            _top_jaccard(seed_correction[a], seed_correction[b], 100)
            for a, b in pair_indices
        ]
        random_cosines = [
            _cosine(seed_random_correction[a], seed_random_correction[b])
            for a, b in pair_indices
        ]
        mean_by_donor = {
            name: np.mean(
                np.stack([per_seed[seed][name] for seed in SEEDS], axis=0), axis=0
            )
            for name in ("efficacy_vs_pooled", "efficacy_vs_generic", "semantic_vs_random")
        }
        efficacy_ci = _bootstrap_ci(
            mean_by_donor["efficacy_vs_generic"],
            replicates=replicates,
            seed=bootstrap_seed + organ_index * 10 + 1,
        )
        semantic_ci = _bootstrap_ci(
            mean_by_donor["semantic_vs_random"],
            replicates=replicates,
            seed=bootstrap_seed + organ_index * 10 + 2,
        )
        overall_generic = _scalar_bootstrap(
            mean_by_donor["efficacy_vs_generic"],
            replicates=replicates,
            seed=bootstrap_seed + organ_index * 10 + 3,
        )
        overall_semantic = _scalar_bootstrap(
            mean_by_donor["semantic_vs_random"],
            replicates=replicates,
            seed=bootstrap_seed + organ_index * 10 + 4,
        )
        signs = np.sign(np.stack(seed_efficacy))
        same_nonzero_sign = np.all(signs == signs[0], axis=0) & (signs[0] != 0)
        efficacy_99 = efficacy_ci[0.99]
        semantic_99 = semantic_ci[0.99]
        stable_gene = (
            same_nonzero_sign
            & ((efficacy_99[0] > 0) | (efficacy_99[1] < 0))
            & (semantic_99[0] > 0)
        )
        mean_efficacy = mean_by_donor["efficacy_vs_generic"].mean(axis=0)
        mean_semantic = mean_by_donor["semantic_vs_random"].mean(axis=0)
        mean_correction = np.mean(np.stack(seed_correction), axis=0)
        correction_signatures[organ] = mean_correction
        efficacy_signatures[organ] = mean_efficacy
        frame = pd.DataFrame({
            "organ": organ,
            "gene": genes,
            "mean_efficacy_vs_generic": mean_efficacy,
            "efficacy_99ci_low": efficacy_99[0],
            "efficacy_99ci_high": efficacy_99[1],
            "mean_semantic_specificity_vs_random": mean_semantic,
            "semantic_99ci_low": semantic_99[0],
            "semantic_99ci_high": semantic_99[1],
            "mean_functional_correction": mean_correction,
            "same_sign_all_seeds": same_nonzero_sign,
            "candidate_stable_gene": stable_gene,
        })
        gene_rows.append(frame)
        passed = bool(
            min(correction_cosines)
            >= float(gate["minimum_pairwise_functional_correction_cosine"])
            and min(efficacy_spearman)
            >= float(gate["minimum_pairwise_efficacy_spearman"])
            and min(top_jaccards)
            >= float(gate["minimum_pairwise_top100_jaccard"])
            and overall_generic[1]
            > float(gate["overall_specialist_vs_generic_adapter_95ci_lower_bound"])
            and overall_semantic[1]
            > float(gate["overall_semantic_specificity_vs_random_95ci_lower_bound"])
        )
        row = {
            "organ": organ,
            "samples": int(selected.sum()),
            "donors": int(len(donor_names)),
            "min_correction_cosine": min(correction_cosines),
            "median_correction_cosine": float(np.median(correction_cosines)),
            "median_random_correction_cosine": float(np.median(random_cosines)),
            "min_efficacy_spearman": min(efficacy_spearman),
            "median_efficacy_spearman": float(np.median(efficacy_spearman)),
            "min_top100_jaccard": min(top_jaccards),
            "efficacy_vs_generic_mean": overall_generic[0],
            "efficacy_vs_generic_95ci_low": overall_generic[1],
            "efficacy_vs_generic_95ci_high": overall_generic[2],
            "semantic_vs_random_mean": overall_semantic[0],
            "semantic_vs_random_95ci_low": overall_semantic[1],
            "semantic_vs_random_95ci_high": overall_semantic[2],
            "candidate_stable_genes": int(stable_gene.sum()),
            "representation_gate_pass": passed,
        }
        rows.append(row)
        organ_report[organ] = {
            **row,
            "pairwise_correction_cosines": correction_cosines,
            "pairwise_efficacy_spearman": efficacy_spearman,
            "pairwise_top100_jaccard": top_jaccards,
            "pairwise_random_correction_cosines": random_cosines,
        }
    summary = pd.DataFrame(rows)
    summary.to_csv(output_dir / "organ_reproducibility_summary.csv", index=False)
    genes_frame = pd.concat(gene_rows, ignore_index=True)
    genes_frame.to_csv(output_dir / "gene_programs.csv.gz", index=False, compression="gzip")
    correction_matrix = np.asarray([
        [_cosine(correction_signatures[left], correction_signatures[right]) for right in ORGANS]
        for left in ORGANS
    ])
    efficacy_matrix = np.asarray([
        [_cosine(efficacy_signatures[left], efficacy_signatures[right]) for right in ORGANS]
        for left in ORGANS
    ])
    pd.DataFrame(correction_matrix, index=ORGANS, columns=ORGANS).to_csv(
        output_dir / "organ_functional_correction_cosine.csv"
    )
    pd.DataFrame(efficacy_matrix, index=ORGANS, columns=ORGANS).to_csv(
        output_dir / "organ_efficacy_cosine.csv"
    )
    fig, ax = plt.subplots(figsize=(8.4, 7.0))
    image = ax.imshow(correction_matrix, cmap="RdYlBu", vmin=-1, vmax=1)
    ax.set_xticks(range(len(ORGANS)), labels=ORGANS, rotation=45, ha="right")
    ax.set_yticks(range(len(ORGANS)), labels=ORGANS)
    ax.set_title("Frozen organ-expert functional correction similarity")
    fig.colorbar(image, ax=ax, label="cosine similarity")
    fig.tight_layout()
    fig.savefig(output_dir / "organ_functional_correction_cosine.png", dpi=180)
    plt.close(fig)
    passed_count = int(summary["representation_gate_pass"].sum())
    if passed_count >= 4:
        decision = "representation_first_success_freeze_prospective_predictor"
    elif passed_count:
        decision = "partial_signal_broaden_attribute_audit"
    else:
        decision = "organ_axis_insufficient_pivot_multi_attribute"
    report = {
        "schema_version": 1,
        "status": "complete",
        "research_stage": "stage2_representation_first_pivot",
        "code_commit": args.code_commit,
        "protocol_sha256": args.expected_protocol_sha256,
        "seeds": list(SEEDS),
        "organs": list(ORGANS),
        "model_fitting_performed": False,
        "archs4_accessed": False,
        "best_seed_selection_performed": False,
        "candidate_gene_scope": protocol["reproducibility_metrics"]["candidate_gene_scope"],
        "organs_passing_representation_gate": passed_count,
        "decision": decision,
        "organ_results": organ_report,
        "limitations": [
            "GTEx donor-disjoint development evidence is not independent-study universality.",
            "Candidate stable genes are exploratory and not multiplicity-controlled discoveries.",
            "Signature similarity does not by itself authorize training-data sharing."
        ],
    }
    report_path = output_dir / "evaluation_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    checksum_rows = []
    for path in sorted(output_dir.iterdir()):
        if path.name != "IMMUTABLE_SHA256SUMS" and path.is_file():
            checksum_rows.append(f"{sha256_file(path)}  {path.name}")
    (output_dir / "IMMUTABLE_SHA256SUMS").write_text("\n".join(checksum_rows) + "\n")
    (output_dir / "COMPLETE").touch()
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--seed-cache", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--code-commit", required=True)
    return parser


if __name__ == "__main__":
    print(json.dumps(evaluate(build_parser().parse_args()), indent=2, sort_keys=True))
