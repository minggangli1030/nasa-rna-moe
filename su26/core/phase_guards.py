"""Fail-closed guards for multi-phase PyTorch training.

The guards are deliberately independent of any scientific model.  They verify that
each phase starts with a usable optimizer, covers exactly the parameters declared
trainable, and actually changes every declared trainable module.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import torch
from torch import nn
from torch.optim import Optimizer


def _trainable_parameters(module: nn.Module) -> dict[str, nn.Parameter]:
    parameters = {
        name: parameter
        for name, parameter in module.named_parameters()
        if parameter.requires_grad
    }
    if not parameters:
        raise ValueError("declared trainable module has no trainable parameters")
    return parameters


def snapshot_trainable_state(
    modules: Mapping[str, nn.Module],
) -> dict[str, torch.Tensor]:
    """Copy every declared trainable tensor to CPU under a stable qualified name."""

    state: dict[str, torch.Tensor] = {}
    parameter_ids: set[int] = set()
    for module_name in sorted(modules):
        for parameter_name, parameter in _trainable_parameters(
            modules[module_name]
        ).items():
            if id(parameter) in parameter_ids:
                raise ValueError("declared trainable modules share a parameter")
            parameter_ids.add(id(parameter))
            state[f"{module_name}.{parameter_name}"] = (
                parameter.detach().cpu().contiguous().clone()
            )
    if not state:
        raise ValueError("no trainable tensors were declared")
    return state


def tensor_state_sha256(state: Mapping[str, torch.Tensor]) -> str:
    """Hash tensor names, dtypes, shapes, and exact bytes deterministically."""

    digest = hashlib.sha256()
    for name in sorted(state):
        value = state[name].detach().cpu().contiguous()
        digest.update(name.encode("utf-8"))
        digest.update(str(value.dtype).encode("utf-8"))
        digest.update(np.asarray(value.shape, dtype=np.int64).tobytes())
        digest.update(value.numpy().tobytes())
    return digest.hexdigest()


def validate_optimizer_learning_rates(
    optimizers: Mapping[str, Optimizer], *, phase: str
) -> dict[str, list[float]]:
    """Require finite positive learning rates at phase initialization.

    A scheduler may legitimately reach zero at its predetermined final step.  This
    validation is therefore intentionally called only when the phase is created.
    """

    if not optimizers:
        raise ValueError(f"{phase}: no optimizers were provided")
    learning_rates: dict[str, list[float]] = {}
    for name in sorted(optimizers):
        groups = optimizers[name].param_groups
        if not groups:
            raise ValueError(f"{phase}/{name}: optimizer has no parameter groups")
        values = [float(group["lr"]) for group in groups]
        if not all(math.isfinite(value) and value > 0 for value in values):
            raise ValueError(
                f"{phase}/{name}: every initial optimizer learning rate must be "
                f"finite and positive, observed {values}"
            )
        learning_rates[name] = values
    return learning_rates


def validate_optimizer_coverage(
    modules: Mapping[str, nn.Module],
    optimizers: Mapping[str, Optimizer],
    *,
    phase: str,
) -> None:
    """Require one matching optimizer to cover every declared trainable tensor."""

    if set(modules) != set(optimizers):
        raise ValueError(
            f"{phase}: optimizer/module names differ: "
            f"{sorted(optimizers)} versus {sorted(modules)}"
        )
    for name in sorted(modules):
        expected = {
            id(parameter)
            for parameter in _trainable_parameters(modules[name]).values()
        }
        actual = {
            id(parameter)
            for group in optimizers[name].param_groups
            for parameter in group["params"]
        }
        if actual != expected:
            missing = len(expected - actual)
            extra = len(actual - expected)
            raise ValueError(
                f"{phase}/{name}: optimizer coverage differs from declared "
                f"trainable parameters (missing={missing}, extra={extra})"
            )


def parameter_delta_report(
    before: Mapping[str, torch.Tensor],
    modules: Mapping[str, nn.Module],
) -> dict[str, dict[str, float | int]]:
    """Return L2 and maximum absolute movement for each declared module."""

    after = snapshot_trainable_state(modules)
    if set(before) != set(after):
        raise ValueError("trainable tensor set changed during the phase")
    report: dict[str, dict[str, float | int]] = {}
    for module_name in sorted(modules):
        names = [
            name for name in sorted(after) if name.startswith(f"{module_name}.")
        ]
        squared = 0.0
        maximum = 0.0
        elements = 0
        for name in names:
            difference = (
                after[name].to(dtype=torch.float64)
                - before[name].to(dtype=torch.float64)
            )
            squared += float(torch.square(difference).sum().item())
            maximum = max(maximum, float(difference.abs().max().item()))
            elements += difference.numel()
        report[module_name] = {
            "l2": math.sqrt(squared),
            "max_abs": maximum,
            "elements": elements,
        }
    return report


@dataclass
class PhaseGuard:
    """Capture and verify the mechanical contract of one training phase."""

    phase: str
    modules: Mapping[str, nn.Module]
    optimizers: Mapping[str, Optimizer]
    minimum_l2_delta: float = 0.0

    def __post_init__(self) -> None:
        if self.minimum_l2_delta < 0:
            raise ValueError("minimum L2 delta must be nonnegative")
        validate_optimizer_coverage(
            self.modules, self.optimizers, phase=self.phase
        )
        self.initial_learning_rates = validate_optimizer_learning_rates(
            self.optimizers, phase=self.phase
        )
        self.initial_state = snapshot_trainable_state(self.modules)
        self.initial_sha256 = tensor_state_sha256(self.initial_state)

    def movement(self, *, checkpoint: str) -> dict[str, Any]:
        deltas = parameter_delta_report(self.initial_state, self.modules)
        stagnant = [
            name
            for name, values in deltas.items()
            if float(values["l2"]) <= self.minimum_l2_delta
        ]
        if stagnant:
            raise RuntimeError(
                f"{self.phase}/{checkpoint}: declared trainable modules did not "
                f"move beyond L2 tolerance {self.minimum_l2_delta}: {stagnant}"
            )
        current_state = snapshot_trainable_state(self.modules)
        current_sha256 = tensor_state_sha256(current_state)
        if current_sha256 == self.initial_sha256:
            raise RuntimeError(
                f"{self.phase}/{checkpoint}: trainable tensor hash is unchanged"
            )
        return {
            "phase": self.phase,
            "checkpoint": checkpoint,
            "initial_learning_rates": self.initial_learning_rates,
            "minimum_l2_delta": self.minimum_l2_delta,
            "initial_trainable_state_sha256": self.initial_sha256,
            "current_trainable_state_sha256": current_sha256,
            "module_deltas": deltas,
        }
