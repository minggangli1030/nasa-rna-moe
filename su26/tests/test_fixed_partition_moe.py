from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

from train_fixed_partition_moe import FixedGeneMaskDataset  # noqa: E402
from train_latent_moe import FrozenTrunkResidualMoE, _masked_row_mse  # noqa: E402
from train_single import ExpressionPerformer  # noqa: E402


def test_fixed_gene_mask_dataset_masks_only_sorted_score_genes_and_returns_copies():
    expression = np.asarray(
        [
            [0.0, 1.0, 3.0, 7.0, 15.0, 31.0],
            [2.0, 4.0, 6.0, 8.0, 10.0, 12.0],
        ],
        dtype=np.float32,
    )
    dataset = FixedGeneMaskDataset(
        expression,
        ["sample-a", "sample-b"],
        mask_indices=np.asarray([4, 1]),
        mask_token=-10.0,
    )

    masked, truth, mask = dataset[0]
    expected = torch.from_numpy(np.log1p(expression[0]).astype(np.float32))
    torch.testing.assert_close(truth, expected)
    torch.testing.assert_close(mask, torch.tensor([1, 4]))
    assert masked[1].item() == -10.0
    assert masked[4].item() == -10.0
    torch.testing.assert_close(masked[[0, 2, 3, 5]], expected[[0, 2, 3, 5]])

    masked[0] = 999.0
    truth[0] = 999.0
    mask[0] = 0
    masked_again, truth_again, mask_again = dataset[0]
    torch.testing.assert_close(truth_again, expected)
    torch.testing.assert_close(mask_again, torch.tensor([1, 4]))
    assert masked_again[0].item() != 999.0


def test_hard_assignment_backpropagates_only_to_the_selected_expert():
    torch.manual_seed(7)
    trunk = ExpressionPerformer(
        num_genes=6,
        hidden_dim=8,
        n_heads=2,
        n_layers=1,
        ffn_dim=16,
        gradient_checkpointing=False,
    )
    trunk.requires_grad_(False)
    model = FrozenTrunkResidualMoE(
        trunk,
        num_experts=2,
        adapter_dim=4,
        router_hidden_dim=4,
        mask_token=-10.0,
    )
    model.router.requires_grad_(False)
    model.train()

    dataset = FixedGeneMaskDataset(
        np.asarray(
            [
                [0.0, 1.0, 3.0, 7.0, 15.0, 31.0],
                [2.0, 4.0, 6.0, 8.0, 10.0, 12.0],
            ],
            dtype=np.float32,
        ),
        ["sample-a", "sample-b"],
        mask_indices=np.asarray([1, 4]),
        mask_token=-10.0,
    )
    masked, truth, mask = next(iter(DataLoader(dataset, batch_size=2)))
    predictions, _, _ = model(masked)
    labels = torch.zeros(len(masked), dtype=torch.long)
    rows = torch.arange(len(masked))
    selected = predictions[rows, labels]
    loss = _masked_row_mse(selected, truth, mask).mean()
    loss.backward()

    selected_gradients = [
        parameter.grad for parameter in model.experts[0].parameters()
    ]
    unselected_gradients = [
        parameter.grad for parameter in model.experts[1].parameters()
    ]
    assert any(
        gradient is not None and torch.count_nonzero(gradient).item() > 0
        for gradient in selected_gradients
    )
    assert all(
        gradient is None or torch.count_nonzero(gradient).item() == 0
        for gradient in unselected_gradients
    )
    assert all(parameter.grad is None for parameter in model.router.parameters())
    assert all(parameter.grad is None for parameter in model.trunk.parameters())

