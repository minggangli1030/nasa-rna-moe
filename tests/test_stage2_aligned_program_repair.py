import pytest

torch = pytest.importorskip("torch")

from core.stage2_program_model import AlignedProgramCondition
from core.train_stage2_aligned_program_repair import (
    _coefficient_targets,
    _copy_private,
    _freeze_private,
    _hidden_summary,
)


def test_masked_projection_recovers_known_coefficients():
    generator = torch.Generator().manual_seed(17)
    decoder = torch.randn(4, 12, generator=generator)
    coefficients = torch.randn(3, 4, generator=generator)
    local_mask = torch.tensor([
        [0, 1, 2, 3, 4, 5, 6, 7],
        [1, 2, 4, 5, 7, 8, 9, 10],
        [0, 2, 3, 6, 8, 9, 10, 11],
    ])
    residual = coefficients @ decoder
    recovered, gram = _coefficient_targets(
        residual, local_mask, decoder, ridge=1e-8
    )
    assert gram.shape == (3, 4, 4)
    assert torch.allclose(recovered, coefficients, atol=1e-4, rtol=1e-4)


def test_hidden_summary_ignores_masked_gene():
    hidden = torch.tensor([[[1.0, 2.0], [100.0, 200.0], [3.0, 4.0]]])
    masked = torch.tensor([[0.0, -10.0, 0.0]])
    summary = _hidden_summary(hidden, masked, -10.0)
    assert torch.equal(summary, torch.tensor([[2.0, 3.0]]))


def test_private_snapshot_is_copied_then_frozen():
    kwargs = dict(
        hidden_dim=5,
        score_gene_indices=torch.tensor([1, 3, 5]),
        program_head_dim=3,
        private_adapter_dim=2,
        num_private_experts=2,
    )
    source = AlignedProgramCondition(program_decoder=None, **kwargs)
    target = AlignedProgramCondition(
        program_decoder=torch.randn(4, 3), **kwargs
    )
    _copy_private(source, target)
    left = source.private.state_dict()
    right = target.private.state_dict()
    assert all(torch.equal(left[name], right[name]) for name in left)
    _freeze_private(target)
    assert not any(parameter.requires_grad for parameter in target.private.parameters())
    assert all(
        parameter.requires_grad
        for parameter in target.program.coefficient_head.parameters()
    )
