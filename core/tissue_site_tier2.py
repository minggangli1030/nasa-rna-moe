"""Small deterministic modules and metrics for the tissue-site Tier-2 smoke."""

from __future__ import annotations

import numpy as np
import torch
from torch import nn


class ResidualHead(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int, output_dim: int):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, output_dim),
        )

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        return self.network(values)


class SiteBank(nn.Module):
    def __init__(
        self, input_dim: int, hidden_dim: int, output_dim: int, sites: int
    ):
        super().__init__()
        self.heads = nn.ModuleList(
            ResidualHead(input_dim, hidden_dim, output_dim) for _ in range(sites)
        )

    def forward_all(self, values: torch.Tensor) -> torch.Tensor:
        return torch.stack([head(values) for head in self.heads], dim=1)

    def forward_known(
        self, values: torch.Tensor, site_index: torch.Tensor
    ) -> torch.Tensor:
        all_values = self.forward_all(values)
        rows = torch.arange(len(values), device=values.device)
        return all_values[rows, site_index]


class SiteRouter(nn.Module):
    def __init__(self, input_dim: int, sites: int):
        super().__init__()
        self.linear = nn.Linear(input_dim, sites)

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        return self.linear(values)


def parameter_count(module: nn.Module) -> int:
    return sum(parameter.numel() for parameter in module.parameters())


def relative_improvement(base_mse: np.ndarray, candidate_mse: np.ndarray) -> float:
    base = float(np.mean(np.asarray(base_mse, dtype=np.float64)))
    candidate = float(np.mean(np.asarray(candidate_mse, dtype=np.float64)))
    if base <= 0:
        raise ValueError("base MSE must be positive")
    return (base - candidate) / base


def donor_bootstrap_difference(
    reference_mse: np.ndarray,
    candidate_mse: np.ndarray,
    donors: np.ndarray,
    *,
    replicates: int,
    seed: int,
) -> dict:
    reference = np.asarray(reference_mse, dtype=np.float64)
    candidate = np.asarray(candidate_mse, dtype=np.float64)
    groups = np.asarray(donors, dtype=str)
    unique = np.unique(groups)
    positions = {donor: np.flatnonzero(groups == donor) for donor in unique}
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(replicates):
        sampled = rng.choice(unique, size=len(unique), replace=True)
        rows = np.concatenate([positions[donor] for donor in sampled])
        denominator = float(np.mean(reference[rows]))
        values.append(
            0.0
            if denominator <= 0
            else float(np.mean(reference[rows] - candidate[rows]) / denominator)
        )
    return {
        "replicates": int(replicates),
        "median": float(np.median(values)),
        "ci95": np.quantile(values, [0.025, 0.975]).astype(float).tolist(),
    }


def router_usage(
    probabilities: np.ndarray,
    organs: np.ndarray,
    informative_organs: list[str],
) -> dict:
    probability = np.asarray(probabilities, dtype=np.float64)
    labels = np.asarray(organs, dtype=str)
    hard = probability.argmax(axis=1)
    output = {}
    for organ in informative_organs:
        rows = labels == organ
        mean = probability[rows].mean(axis=0)
        positive = mean[mean > 0]
        entropy = -float(np.sum(positive * np.log(positive)))
        output[organ] = {
            "effective_soft_sites": float(np.exp(entropy)),
            "hard_sites_used": int(np.unique(hard[rows]).size),
            "maximum_mean_soft_weight": float(mean.max()),
        }
    return output
