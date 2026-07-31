import torch
from torch import nn

from core.final_organ_embedding import compose_embeddings, observed_mean


def test_observed_mean_excludes_masked_positions():
    values = torch.tensor([[[1.0, 2.0], [100.0, 200.0], [3.0, 4.0]]])
    observed = torch.tensor([[True, False, True]])
    assert torch.equal(observed_mean(values, observed), torch.tensor([[2.0, 3.0]]))


def test_compose_embeddings_uses_true_hard_and_soft_routes():
    pooled = torch.tensor([[10.0], [20.0]])
    experts = torch.tensor([[[1.0], [3.0]], [[2.0], [4.0]]])
    probabilities = torch.tensor([[0.75, 0.25], [0.1, 0.9]])
    labels = torch.tensor([1, 0])
    result = compose_embeddings(pooled, experts, probabilities, labels)
    assert torch.allclose(result["true_organ_embedding"][:, 1], torch.tensor([3.0, 2.0]))
    assert torch.allclose(
        result["blind_router_hard_embedding"][:, 1], torch.tensor([1.0, 4.0])
    )
    assert torch.allclose(
        result["blind_router_soft_embedding"][:, 1], torch.tensor([1.5, 3.8])
    )
    assert result["pooled_hidden_plus_router"].shape == (2, 3)


def test_compose_embeddings_normalizes_router_dtype():
    result = compose_embeddings(
        torch.ones(1, 2, dtype=torch.float32),
        torch.ones(1, 2, 3, dtype=torch.float32),
        torch.tensor([[0.5, 0.5]], dtype=torch.float64),
        torch.tensor([0]),
    )
    assert result["blind_router_soft_embedding"].dtype == torch.float32
