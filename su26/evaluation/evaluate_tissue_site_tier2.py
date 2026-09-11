#!/usr/bin/env python3
"""Train and evaluate one frozen-seed protected tissue-site Tier-2 smoke."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from sklearn.model_selection import StratifiedGroupKFold
from torch import nn

from core.multiaxis_tier1 import permute_within_organ
from core.stage2b_diagnostics import array_sha256
from core.tissue_site_tier2 import (
    ResidualHead,
    SiteBank,
    SiteRouter,
    donor_bootstrap_difference,
    parameter_count,
    relative_improvement,
    router_usage,
)
from core.train_manifest import sha256_file


def atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def load_cache(
    root: Path, seed: int, expected_protocol: str, expected_metadata_sha: str
) -> dict[str, np.ndarray]:
    metadata_path = root / "run_metadata.json"
    if sha256_file(metadata_path) != expected_metadata_sha:
        raise ValueError("seed run metadata SHA256 mismatch")
    metadata = json.loads(metadata_path.read_text())
    if (
        metadata.get("status") != "complete"
        or int(metadata.get("seed", -1)) != seed
        or metadata.get("protocol_sha256") != expected_protocol
        or int(metadata.get("rows", -1)) != 7369
    ):
        raise ValueError("invalid frozen canonical cache metadata")
    path = root / "canonical_cache.npz"
    if sha256_file(path) != metadata["hashes"]["canonical_cache_sha256"]:
        raise ValueError("canonical cache file SHA256 mismatch")
    required = (
        "h_canon",
        "private_prediction",
        "truth_score",
        "sample_ordinal",
    )
    with np.load(path, allow_pickle=False) as archive:
        output = {name: archive[name] for name in required}
    for name, value in output.items():
        if array_sha256(value) != metadata["hashes"]["canonical_arrays"][name]:
            raise ValueError(f"canonical array hash mismatch: {name}")
    if not np.array_equal(output["sample_ordinal"], np.arange(7369)):
        raise ValueError("canonical cache row order changed")
    return output


def correction_coefficients(residual: np.ndarray, decoder: np.ndarray) -> np.ndarray:
    matrix = np.asarray(decoder, dtype=np.float64)
    gram = matrix @ matrix.T
    if not np.allclose(gram, np.eye(len(matrix)), atol=2e-4, rtol=2e-4):
        raise ValueError("frozen decoder is not sufficiently orthonormal")
    return np.asarray(residual, dtype=np.float64) @ matrix.T


def _set_determinism(seed: int) -> None:
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False


def _batches(rows: np.ndarray, batch_size: int, seed: int):
    order = np.random.default_rng(seed).permutation(rows)
    for start in range(0, len(order), batch_size):
        yield order[start : start + batch_size]


def train_site_model(
    features: np.ndarray,
    targets: np.ndarray,
    labels: np.ndarray,
    rows: np.ndarray,
    *,
    site_hidden: int,
    sites: int,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    weight_decay: float,
    router_weight: float,
    gradient_clip: float,
    seed: int,
    device: torch.device,
) -> tuple[SiteBank, SiteRouter]:
    _set_determinism(seed)
    bank = SiteBank(features.shape[1], site_hidden, targets.shape[1], sites).to(device)
    router = SiteRouter(features.shape[1], sites).to(device)
    optimizer = torch.optim.AdamW(
        list(bank.parameters()) + list(router.parameters()),
        lr=learning_rate,
        weight_decay=weight_decay,
    )
    x = torch.as_tensor(features, dtype=torch.float32)
    y = torch.as_tensor(targets, dtype=torch.float32)
    site = torch.as_tensor(labels, dtype=torch.long)
    bank.train()
    router.train()
    for epoch in range(epochs):
        for batch in _batches(rows, batch_size, seed + epoch):
            bx = x[batch].to(device)
            by = y[batch].to(device)
            bs = site[batch].to(device)
            prediction = bank.forward_known(bx, bs)
            logits = router(bx)
            loss = nn.functional.mse_loss(prediction, by) + router_weight * nn.functional.cross_entropy(logits, bs)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(
                list(bank.parameters()) + list(router.parameters()), gradient_clip
            )
            optimizer.step()
    bank.eval()
    router.eval()
    return bank, router


def train_generic_model(
    features: np.ndarray,
    targets: np.ndarray,
    rows: np.ndarray,
    *,
    hidden: int,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    weight_decay: float,
    gradient_clip: float,
    seed: int,
    device: torch.device,
) -> ResidualHead:
    _set_determinism(seed)
    model = ResidualHead(features.shape[1], hidden, targets.shape[1]).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=learning_rate, weight_decay=weight_decay
    )
    x = torch.as_tensor(features, dtype=torch.float32)
    y = torch.as_tensor(targets, dtype=torch.float32)
    model.train()
    for epoch in range(epochs):
        for batch in _batches(rows, batch_size, seed + epoch):
            bx = x[batch].to(device)
            by = y[batch].to(device)
            loss = nn.functional.mse_loss(model(bx), by)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), gradient_clip)
            optimizer.step()
    model.eval()
    return model


@torch.no_grad()
def predict_site(
    bank: SiteBank,
    router: SiteRouter,
    features: np.ndarray,
    labels: np.ndarray,
    device: torch.device,
) -> dict[str, np.ndarray]:
    x = torch.as_tensor(features, dtype=torch.float32, device=device)
    site = torch.as_tensor(labels, dtype=torch.long, device=device)
    all_values = bank.forward_all(x)
    logits = router(x)
    probability = torch.softmax(logits, dim=1)
    hard = nn.functional.one_hot(
        probability.argmax(dim=1), num_classes=probability.shape[1]
    ).float()
    known = all_values[torch.arange(len(x), device=device), site]
    soft_value = torch.einsum("bsc,bs->bc", all_values, probability)
    hard_value = torch.einsum("bsc,bs->bc", all_values, hard)
    return {
        "known": known.cpu().numpy(),
        "soft": soft_value.cpu().numpy(),
        "hard": hard_value.cpu().numpy(),
        "probability": probability.cpu().numpy(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--stage2b-protocol", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--basis-bundle", required=True)
    parser.add_argument("--cache-root", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    protocol_path = Path(args.protocol)
    if sha256_file(protocol_path) != args.expected_protocol_sha256:
        raise ValueError("Tier-2 protocol SHA256 mismatch")
    protocol = json.loads(protocol_path.read_text())
    if protocol.get("status") != "frozen_before_tissue_site_tier2_outcome_access":
        raise ValueError("Tier-2 protocol is not frozen")
    inputs = protocol["inputs"]
    for path, expected in (
        (Path(args.stage2b_protocol), inputs["stage2b_protocol_sha256"]),
        (Path(args.manifest), inputs["manifest_sha256"]),
        (Path(args.metadata), inputs["training_metadata_sha256"]),
        (Path(args.basis_bundle), inputs["basis_bundle_sha256"]),
    ):
        if sha256_file(path) != expected:
            raise ValueError(f"input SHA256 mismatch: {path}")
    if args.seed not in inputs["seeds"]:
        raise ValueError("seed is outside frozen protocol")
    stage2b_sha = sha256_file(Path(args.stage2b_protocol))
    cache = load_cache(
        Path(args.cache_root),
        args.seed,
        stage2b_sha,
        inputs["seed_run_metadata_sha256"][str(args.seed)],
    )

    manifest = pd.read_parquet(args.manifest)
    training = (
        manifest.loc[
            manifest["split"].astype(str).eq("train")
            & manifest["balanced_train"].astype(bool)
        ]
        .sort_values("sample_id")
        .reset_index(drop=True)
    )
    metadata = pd.read_parquet(args.metadata)
    aligned = metadata.set_index("sample_id").reindex(training["sample_id"].astype(str))
    if aligned.index.has_duplicates or aligned["tissue_site"].isna().any():
        raise ValueError("tissue-site metadata does not align")
    if (
        aligned["donor_id"].astype(str).to_numpy()
        != training["series_group_id"].astype(str).to_numpy()
    ).any():
        raise ValueError("metadata donor IDs differ")
    donors = training["series_group_id"].astype(str).to_numpy()
    organs = training["organ"].astype(str).to_numpy()
    tissue = aligned["tissue_site"].astype(str).to_numpy()
    informative_organs = list(protocol["scope"]["informative_organs"])
    active_sites = list(protocol["scope"]["site_levels"])
    site_lookup = {value: index for index, value in enumerate(active_sites)}
    eligible = np.isin(organs, informative_organs)
    if any(value not in site_lookup for value in tissue[eligible]):
        raise ValueError("informative organ contains an unfrozen tissue site")
    site_labels = np.array(
        [site_lookup.get(value, -1) for value in tissue], dtype=np.int64
    )

    with np.load(args.basis_bundle, allow_pickle=False) as archive:
        decoder = archive["program_components"].astype(np.float64)
    residual = cache["truth_score"].astype(np.float64) - cache[
        "private_prediction"
    ].astype(np.float64)
    target_coefficients = correction_coefficients(residual, decoder)
    hidden = cache["h_canon"].astype(np.float64)
    base_mse = np.mean(np.square(residual), axis=1)
    conditions = (
        "protected_base",
        "known_site",
        "soft_site",
        "hard_site",
        "soft_shuffled_site",
        "generic_capacity_matched",
    )
    mse = {name: np.full(len(training), np.nan) for name in conditions}
    router_probability = np.zeros((len(training), len(active_sites)), dtype=np.float32)
    split = StratifiedGroupKFold(
        n_splits=int(protocol["training"]["outer_folds"]),
        shuffle=True,
        random_state=int(protocol["training"]["fold_seed_base"]) + args.seed,
    )
    folds = list(split.split(hidden, tissue, donors))
    config = protocol["training"]
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    parameter_record = None
    fold_records = []
    for fold_index, (train_rows, test_rows) in enumerate(folds):
        train_eligible = train_rows[eligible[train_rows]]
        test_eligible = test_rows[eligible[test_rows]]
        x_mean = hidden[train_rows].mean(axis=0)
        x_scale = np.maximum(hidden[train_rows].std(axis=0, ddof=1), 1e-6)
        features = (hidden - x_mean) / x_scale
        y_mean = target_coefficients[train_eligible].mean(axis=0)
        y_scale = np.maximum(
            target_coefficients[train_eligible].std(axis=0, ddof=1), 1e-6
        )
        targets = (target_coefficients - y_mean) / y_scale
        shuffled = site_labels.copy()
        shuffled[train_rows] = permute_within_organ(
            site_labels[train_rows, None],
            organs[train_rows],
            seed=int(config["shuffle_seed_base"]) + args.seed * 100 + fold_index,
        )[:, 0]
        common = dict(
            site_hidden=int(protocol["model"]["site_hidden_dim"]),
            sites=len(active_sites),
            epochs=int(config["epochs"]),
            batch_size=int(config["batch_size"]),
            learning_rate=float(config["learning_rate"]),
            weight_decay=float(config["weight_decay"]),
            router_weight=float(config["router_loss_weight"]),
            gradient_clip=float(config["gradient_clip_norm"]),
            device=device,
        )
        bank, router = train_site_model(
            features,
            targets,
            site_labels,
            train_eligible,
            seed=args.seed * 1000 + fold_index * 10 + 1,
            **common,
        )
        shuffled_bank, shuffled_router = train_site_model(
            features,
            targets,
            shuffled,
            train_eligible,
            seed=args.seed * 1000 + fold_index * 10 + 2,
            **common,
        )
        generic = train_generic_model(
            features,
            targets,
            train_eligible,
            hidden=int(protocol["model"]["generic_hidden_dim"]),
            epochs=int(config["epochs"]),
            batch_size=int(config["batch_size"]),
            learning_rate=float(config["learning_rate"]),
            weight_decay=float(config["weight_decay"]),
            gradient_clip=float(config["gradient_clip_norm"]),
            seed=args.seed * 1000 + fold_index * 10 + 3,
            device=device,
        )
        site_parameters = parameter_count(bank) + parameter_count(router)
        shuffled_parameters = parameter_count(shuffled_bank) + parameter_count(
            shuffled_router
        )
        generic_parameters = parameter_count(generic)
        match = abs(site_parameters - generic_parameters) / site_parameters
        if match > float(protocol["model"]["generic_parameter_match_tolerance_fraction"]):
            raise RuntimeError("generic control parameter match failed")
        current_parameters = {
            "site_bank_plus_router": site_parameters,
            "shuffled_bank_plus_router": shuffled_parameters,
            "generic": generic_parameters,
            "generic_fractional_difference": match,
        }
        if parameter_record is not None and current_parameters != parameter_record:
            raise RuntimeError("parameter counts changed across folds")
        parameter_record = current_parameters

        mse["protected_base"][test_rows] = base_mse[test_rows]
        if len(test_eligible):
            site_prediction = predict_site(
                bank,
                router,
                features[test_eligible],
                site_labels[test_eligible],
                device,
            )
            shuffled_prediction = predict_site(
                shuffled_bank,
                shuffled_router,
                features[test_eligible],
                shuffled[test_eligible],
                device,
            )
            with torch.no_grad():
                generic_value = generic(
                    torch.as_tensor(
                        features[test_eligible], dtype=torch.float32, device=device
                    )
                ).cpu().numpy()
            router_probability[test_eligible] = site_prediction["probability"]
            coefficient = {
                "known_site": site_prediction["known"],
                "soft_site": site_prediction["soft"],
                "hard_site": site_prediction["hard"],
                "soft_shuffled_site": shuffled_prediction["soft"],
                "generic_capacity_matched": generic_value,
            }
            for name, standardized in coefficient.items():
                correction = (standardized * y_scale + y_mean) @ decoder
                prediction = cache["private_prediction"][test_eligible] + correction
                mse[name][test_eligible] = np.mean(
                    np.square(cache["truth_score"][test_eligible] - prediction), axis=1
                )
        fallback = test_rows[~eligible[test_rows]]
        for name in conditions[1:]:
            mse[name][fallback] = base_mse[fallback]
        fold_records.append(
            {
                "fold": fold_index,
                "training_donors": int(np.unique(donors[train_rows]).size),
                "test_donors": int(np.unique(donors[test_rows]).size),
                "training_eligible_rows": int(len(train_eligible)),
                "test_eligible_rows": int(len(test_eligible)),
            }
        )

    if any(not np.isfinite(values).all() for values in mse.values()):
        raise RuntimeError("cross-fitted evaluation left unscored rows")
    improvements = {
        name: relative_improvement(mse["protected_base"], values)
        for name, values in mse.items()
        if name != "protected_base"
    }
    pairwise = {}
    for reference in (
        "protected_base",
        "soft_shuffled_site",
        "generic_capacity_matched",
    ):
        key = f"soft_site_vs_{reference}"
        pairwise[key] = {
            "relative_improvement": relative_improvement(
                mse[reference], mse["soft_site"]
            ),
            "donor_bootstrap": donor_bootstrap_difference(
                mse[reference],
                mse["soft_site"],
                donors,
                replicates=int(protocol["evaluation"]["donor_bootstrap_replicates"]),
                seed=int(protocol["evaluation"]["donor_bootstrap_seed"])
                + args.seed,
            ),
        }
    per_organ = {
        organ: relative_improvement(
            mse["protected_base"][organs == organ], mse["soft_site"][organs == organ]
        )
        for organ in sorted(np.unique(organs))
    }
    usage = router_usage(router_probability[eligible], organs[eligible], informative_organs)
    minimum_effective = float(
        protocol["evaluation"]["minimum_effective_soft_sites_per_informative_organ"]
    )
    minimum_hard = int(
        protocol["evaluation"]["minimum_hard_sites_used_per_informative_organ"]
    )
    noncollapse = all(
        value["effective_soft_sites"] >= minimum_effective
        and value["hard_sites_used"] >= minimum_hard
        for value in usage.values()
    )
    maximum_harm = float(protocol["evaluation"]["maximum_per_organ_relative_harm"])
    gates = {
        "soft_site_improves_protected_base": pairwise[
            "soft_site_vs_protected_base"
        ]["relative_improvement"]
        > 0,
        "soft_site_improves_shuffled": pairwise[
            "soft_site_vs_soft_shuffled_site"
        ]["relative_improvement"]
        > 0,
        "soft_site_improves_generic": pairwise[
            "soft_site_vs_generic_capacity_matched"
        ]["relative_improvement"]
        > 0,
        "pairwise_bootstrap_lower_bounds_positive": all(
            value["donor_bootstrap"]["ci95"][0] > 0 for value in pairwise.values()
        ),
        "known_site_improves_protected_base": improvements["known_site"] > 0,
        "per_organ_safety": all(value >= -maximum_harm for value in per_organ.values()),
        "router_noncollapse": noncollapse,
        "generic_parameter_match": parameter_record[
            "generic_fractional_difference"
        ]
        <= float(protocol["model"]["generic_parameter_match_tolerance_fraction"]),
    }
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    arrays_path = output_dir / "cross_fitted_scores.npz"
    np.savez_compressed(
        arrays_path,
        donor_id=donors.astype(str),
        organ=organs.astype(str),
        tissue_site=tissue.astype(str),
        router_probability=router_probability,
        **{f"mse__{name}": values for name, values in mse.items()},
    )
    report = {
        "schema_version": 1,
        "status": "complete",
        "role": protocol["role"],
        "seed": args.seed,
        "protocol_sha256": sha256_file(protocol_path),
        "device": str(device),
        "torch_version": torch.__version__,
        "parameter_counts": parameter_record,
        "folds": fold_records,
        "relative_improvement_vs_protected_base": improvements,
        "pairwise": pairwise,
        "per_organ_soft_site_relative_improvement": per_organ,
        "router_usage": usage,
        "gates": gates,
        "all_gates_pass": bool(all(gates.values())),
        "scores_sha256": sha256_file(arrays_path),
        "best_seed_selection": False,
        "claim_boundary": "GTEx training-donor Tier-2 development smoke; no calibration, ARCHS4, or OSDR outcome access",
    }
    report_path = output_dir / "tissue_site_tier2_report.json"
    atomic_json(report_path, report)
    (output_dir / "IMMUTABLE_SHA256SUMS").write_text(
        f"{sha256_file(report_path)}  {report_path.name}\n"
        f"{sha256_file(arrays_path)}  {arrays_path.name}\n"
    )
    (output_dir / "COMPLETE").touch()
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
