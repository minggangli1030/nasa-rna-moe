"""Deterministic downstream summaries from the frozen organ-MoE components."""

from __future__ import annotations

import torch
import torch.nn.functional as F


def observed_mean(values: torch.Tensor, observed: torch.Tensor) -> torch.Tensor:
    if values.ndim != 3 or observed.ndim != 2 or values.shape[:2] != observed.shape:
        raise ValueError("values/observed shapes are incompatible")
    weights = observed.to(values.dtype)
    denominator = weights.sum(dim=1, keepdim=True).clamp_min(1.0)
    return (values * weights.unsqueeze(-1)).sum(dim=1) / denominator


def expert_bottleneck_summaries(
    experts: torch.nn.ModuleList,
    hidden: torch.Tensor,
    observed: torch.Tensor,
) -> torch.Tensor:
    summaries = []
    for expert in experts:
        summaries.append(observed_mean(F.gelu(expert.down(hidden)), observed))
    return torch.stack(summaries, dim=1)


def compose_embeddings(
    pooled_summary: torch.Tensor,
    expert_summaries: torch.Tensor,
    router_probabilities: torch.Tensor,
    true_labels: torch.Tensor,
) -> dict[str, torch.Tensor]:
    if expert_summaries.ndim != 3:
        raise ValueError("expert summaries must be [rows, experts, dimensions]")
    if router_probabilities.shape != expert_summaries.shape[:2]:
        raise ValueError("router probabilities do not match expert summaries")
    if true_labels.shape != (len(pooled_summary),):
        raise ValueError("true labels do not match pooled summaries")
    router_probabilities = router_probabilities.to(
        device=expert_summaries.device, dtype=expert_summaries.dtype
    )
    true_labels = true_labels.to(device=expert_summaries.device, dtype=torch.long)
    rows = torch.arange(len(pooled_summary), device=pooled_summary.device)
    hard_labels = router_probabilities.argmax(dim=1)
    true_summary = expert_summaries[rows, true_labels]
    hard_summary = expert_summaries[rows, hard_labels]
    soft_summary = torch.einsum("nk,nkd->nd", router_probabilities, expert_summaries)

    def joined(summary: torch.Tensor) -> torch.Tensor:
        return torch.cat([pooled_summary, summary, router_probabilities], dim=1)

    return {
        "pooled_hidden": pooled_summary,
        "pooled_hidden_plus_router": torch.cat(
            [pooled_summary, router_probabilities], dim=1
        ),
        "true_organ_embedding": joined(true_summary),
        "blind_router_hard_embedding": joined(hard_summary),
        "blind_router_soft_embedding": joined(soft_summary),
    }
