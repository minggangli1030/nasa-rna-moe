#!/usr/bin/env python3
"""Aligned shared/private residual heads for the Stage 2 representation pivot.

The pooled expression model is deliberately not part of these modules. Callers
freeze the trunk, provide its per-gene hidden states, and add the returned
score-gene residual to the pooled prediction.
"""

from __future__ import annotations

from collections.abc import Mapping

import torch
import torch.nn.functional as F
from torch import nn


class ProgramCoefficientHead(nn.Module):
    """Predict coefficients in a fixed, externally supplied program basis."""

    def __init__(self, hidden_dim: int, head_dim: int, components: int):
        super().__init__()
        if min(hidden_dim, head_dim, components) < 1:
            raise ValueError("program-head dimensions must be positive")
        self.network = nn.Sequential(
            nn.LayerNorm(hidden_dim),
            nn.Linear(hidden_dim, head_dim),
            nn.GELU(),
            nn.Linear(head_dim, components),
        )
        final = self.network[-1]
        nn.init.zeros_(final.weight)
        nn.init.zeros_(final.bias)

    def forward(
        self, hidden: torch.Tensor, observed_gene_mask: torch.Tensor
    ) -> torch.Tensor:
        if hidden.ndim != 3:
            raise ValueError("hidden must have shape [batch, genes, hidden_dim]")
        if observed_gene_mask.shape != hidden.shape[:2]:
            raise ValueError("observed-gene mask does not align with hidden states")
        weights = observed_gene_mask.to(dtype=hidden.dtype)
        denominator = weights.sum(dim=1, keepdim=True).clamp_min(1.0)
        summary = (hidden * weights.unsqueeze(-1)).sum(dim=1) / denominator
        return self.network(summary)


class PrivateResidualBank(nn.Module):
    """Hard-dispatched private residual adapters for score-gene hidden states."""

    def __init__(
        self, hidden_dim: int, adapter_dim: int, num_experts: int
    ):
        super().__init__()
        if num_experts < 1:
            raise ValueError("private bank requires at least one expert")
        self.experts = nn.ModuleList(
            nn.Sequential(
                nn.Linear(hidden_dim, adapter_dim),
                nn.GELU(),
                nn.Linear(adapter_dim, 1),
            )
            for _ in range(num_experts)
        )
        for expert in self.experts:
            nn.init.normal_(expert[-1].weight, mean=0.0, std=1e-3)
            nn.init.zeros_(expert[-1].bias)

    @property
    def num_experts(self) -> int:
        return len(self.experts)

    def forward(
        self, score_hidden: torch.Tensor, labels: torch.Tensor
    ) -> torch.Tensor:
        if labels.ndim != 1 or len(labels) != len(score_hidden):
            raise ValueError("private labels must be one-dimensional and batch aligned")
        if torch.any(labels < 0) or torch.any(labels >= self.num_experts):
            raise ValueError("private labels contain an out-of-range expert")
        output = torch.empty(
            score_hidden.shape[:2],
            dtype=score_hidden.dtype,
            device=score_hidden.device,
        )
        for index, expert in enumerate(self.experts):
            selected = labels == index
            if bool(selected.any()):
                output[selected] = expert(score_hidden[selected]).squeeze(-1)
        return output


class FixedProgramResidual(nn.Module):
    """Input-derived coefficient head decoded through one immutable basis."""

    def __init__(
        self,
        hidden_dim: int,
        head_dim: int,
        decoder: torch.Tensor,
    ):
        super().__init__()
        decoder = torch.as_tensor(decoder, dtype=torch.float32)
        if decoder.ndim != 2 or not min(decoder.shape):
            raise ValueError("decoder must have shape [components, score_genes]")
        self.register_buffer("decoder", decoder.clone(), persistent=True)
        self.coefficient_head = ProgramCoefficientHead(
            hidden_dim, head_dim, int(decoder.shape[0])
        )

    def forward(
        self, hidden: torch.Tensor, observed_gene_mask: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        coefficients = self.coefficient_head(hidden, observed_gene_mask)
        return coefficients @ self.decoder, coefficients


class AlignedProgramCondition(nn.Module):
    """One ablation/control condition with optional shared and private paths."""

    def __init__(
        self,
        *,
        hidden_dim: int,
        score_gene_indices: torch.Tensor,
        program_decoder: torch.Tensor | None,
        program_head_dim: int,
        private_adapter_dim: int | None,
        num_private_experts: int,
    ):
        super().__init__()
        score_gene_indices = torch.as_tensor(score_gene_indices, dtype=torch.long)
        if score_gene_indices.ndim != 1 or not len(score_gene_indices):
            raise ValueError("score-gene indices must be a nonempty vector")
        self.register_buffer(
            "score_gene_indices", score_gene_indices.clone(), persistent=True
        )
        self.program = (
            None
            if program_decoder is None
            else FixedProgramResidual(
                hidden_dim, program_head_dim, program_decoder
            )
        )
        self.private = (
            None
            if private_adapter_dim is None
            else PrivateResidualBank(
                hidden_dim, private_adapter_dim, num_private_experts
            )
        )
        if self.program is None and self.private is None:
            raise ValueError("condition must contain a shared or private path")

    def forward(
        self,
        hidden: torch.Tensor,
        masked_expression: torch.Tensor,
        labels: torch.Tensor | None,
    ) -> tuple[torch.Tensor, torch.Tensor | None]:
        score_hidden = hidden.index_select(1, self.score_gene_indices)
        residual = torch.zeros(
            score_hidden.shape[:2],
            dtype=hidden.dtype,
            device=hidden.device,
        )
        coefficients = None
        if self.program is not None:
            observed = masked_expression.ne(-10.0)
            program_residual, coefficients = self.program(hidden, observed)
            residual = residual + program_residual
        if self.private is not None:
            if labels is None:
                raise ValueError("private condition requires labels")
            residual = residual + self.private(score_hidden, labels)
        return residual, coefficients


def clone_matching_submodules(
    conditions: Mapping[str, AlignedProgramCondition],
) -> None:
    """Give matched controls identical shared/private initial states.

    All conditions containing a program head receive the first program-head state;
    all eight-expert private banks receive the first private-bank state. This keeps
    the planned basis and label comparisons initialization matched.
    """

    program_state = None
    private_state = None
    for condition in conditions.values():
        if condition.program is not None:
            if program_state is None:
                program_state = condition.program.coefficient_head.state_dict()
            else:
                condition.program.coefficient_head.load_state_dict(program_state)
        if condition.private is not None and condition.private.num_experts > 1:
            if private_state is None:
                private_state = condition.private.state_dict()
            else:
                condition.private.load_state_dict(private_state)


def trainable_parameter_count(module: nn.Module) -> int:
    return sum(value.numel() for value in module.parameters() if value.requires_grad)

