from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import torch
from torch import nn


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))

from build_utility_axis_partitions import (  # noqa: E402
    build_gene_partition,
    compute_fingerprints,
    fit_balanced_consensus_partition,
)


class _DeterministicTinyTrunk(nn.Module):
    """Small encode/decode model with an exactly checkable linear head."""

    def __init__(self, num_genes: int):
        super().__init__()
        gene_position = torch.linspace(-0.5, 0.5, num_genes)
        self.register_buffer("gene_position", gene_position)
        self.output_map = nn.Linear(3, 1)
        with torch.no_grad():
            self.output_map.weight.copy_(torch.tensor([[0.20, -0.10, 0.30]]))
            self.output_map.bias.fill_(0.05)

    def encode(self, values: torch.Tensor) -> torch.Tensor:
        position = self.gene_position.to(values).expand(len(values), -1)
        return torch.stack(
            [values, position, values * position],
            dim=-1,
        )

    def decode(self, hidden: torch.Tensor) -> torch.Tensor:
        return self.output_map(hidden).squeeze(-1)


def test_gene_partition_is_deterministic_disjoint_and_complete():
    first = build_gene_partition(
        31,
        seed=17,
        probe_fraction=0.20,
        score_fraction=0.30,
    )
    second = build_gene_partition(
        31,
        seed=17,
        probe_fraction=0.20,
        score_fraction=0.30,
    )
    changed_seed = build_gene_partition(
        31,
        seed=18,
        probe_fraction=0.20,
        score_fraction=0.30,
    )

    for left, right in zip(first, second, strict=True):
        np.testing.assert_array_equal(left, right)
        assert left.dtype == np.int64
        assert np.all(left[:-1] < left[1:])

    probe, score, context = first
    assert len(probe) == 6
    assert len(score) == 9
    assert len(context) == 16
    assert not set(probe) & set(score)
    assert not set(probe) & set(context)
    assert not set(score) & set(context)
    np.testing.assert_array_equal(
        np.sort(np.concatenate([probe, score, context])),
        np.arange(31),
    )
    assert any(
        not np.array_equal(left, right)
        for left, right in zip(first, changed_seed, strict=True)
    )


def test_analytic_head_gradient_fingerprint_matches_autograd():
    trunk = _DeterministicTinyTrunk(num_genes=6)
    expression = np.asarray(
        [
            [0.0, 1.0, 3.0, 7.0, 15.0, 31.0],
            [2.0, 4.0, 6.0, 8.0, 10.0, 12.0],
            [1.0, 5.0, 2.0, 9.0, 4.0, 11.0],
        ],
        dtype=np.float32,
    )
    probe = np.asarray([0, 2, 5], dtype=np.int64)
    score = np.asarray([1, 4], dtype=np.int64)
    mask_token = -10.0

    residual, analytic_gradient = compute_fingerprints(
        trunk,
        expression,
        probe_indices=probe,
        score_indices=score,
        mask_token=mask_token,
        batch_size=2,
        device=torch.device("cpu"),
    )

    truth = torch.from_numpy(np.log1p(expression).astype(np.float32))
    masked = truth.clone()
    masked[:, np.sort(np.concatenate([probe, score]))] = mask_token
    with torch.no_grad():
        hidden = trunk.encode(masked)
        base = trunk.decode(hidden)
    np.testing.assert_allclose(
        residual,
        (truth[:, probe] - base[:, probe]).numpy(),
        rtol=1e-6,
        atol=1e-6,
    )

    autograd_rows = []
    for sample in range(len(expression)):
        residual_head = nn.Linear(hidden.shape[-1], 1)
        nn.init.zeros_(residual_head.weight)
        nn.init.zeros_(residual_head.bias)
        prediction = (
            base[sample, probe]
            + residual_head(hidden[sample, probe]).squeeze(-1)
        )
        loss = torch.mean((prediction - truth[sample, probe]) ** 2)
        weight_gradient, bias_gradient = torch.autograd.grad(
            loss,
            (residual_head.weight, residual_head.bias),
        )
        autograd_rows.append(
            torch.cat([weight_gradient.flatten(), bias_gradient]).numpy()
        )
    np.testing.assert_allclose(
        analytic_gradient,
        np.stack(autograd_rows),
        rtol=1e-5,
        atol=1e-6,
    )


def test_balanced_consensus_partition_is_deterministic_and_respects_quota():
    rng = np.random.default_rng(23)
    train = np.concatenate(
        [
            rng.normal(loc=(-2.0, 0.0, 0.0), scale=0.15, size=(4, 3)),
            rng.normal(loc=(0.0, 2.0, 0.0), scale=0.15, size=(4, 3)),
            rng.normal(loc=(2.0, 0.0, 0.0), scale=0.15, size=(3, 3)),
        ]
    )
    calibration = np.asarray(
        [
            [-2.0, 0.0, 0.0],
            [0.0, 2.0, 0.0],
            [2.0, 0.0, 0.0],
            [1.9, 0.1, 0.0],
        ],
        dtype=np.float64,
    )

    first = fit_balanced_consensus_partition(
        train,
        calibration,
        k=3,
        seed=101,
        restarts=4,
    )
    second = fit_balanced_consensus_partition(
        train,
        calibration,
        k=3,
        seed=101,
        restarts=4,
    )
    train_labels, calibration_labels, centers, report = first

    for left, right in zip(first[:3], second[:3], strict=True):
        np.testing.assert_array_equal(left, right)
    assert report == second[3]
    assert sorted(np.bincount(train_labels, minlength=3).tolist()) == [3, 4, 4]
    assert set(train_labels) == {0, 1, 2}
    assert set(calibration_labels).issubset({0, 1, 2})

    distances = (
        np.square(calibration).sum(axis=1, keepdims=True)
        + np.square(centers).sum(axis=1)[None, :]
        - 2.0 * calibration @ centers.T
    )
    np.testing.assert_array_equal(calibration_labels, distances.argmin(axis=1))
    assert report["restarts"] == 4
    assert 0.0 <= report["minimum_pairwise_ami"] <= 1.0

