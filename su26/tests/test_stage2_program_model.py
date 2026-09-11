import pytest

torch = pytest.importorskip("torch")

from core.stage2_program_model import (  # noqa: E402
    AlignedProgramCondition,
    PrivateResidualBank,
    ProgramCoefficientHead,
    clone_matching_submodules,
    trainable_parameter_count,
)


def test_program_head_starts_as_zero_residual():
    head = ProgramCoefficientHead(5, 3, 2)
    hidden = torch.randn(4, 7, 5)
    observed = torch.ones(4, 7, dtype=torch.bool)
    assert torch.equal(head(hidden, observed), torch.zeros(4, 2))


def test_private_bank_dispatches_every_row():
    bank = PrivateResidualBank(5, 3, 2)
    hidden = torch.randn(4, 7, 5)
    labels = torch.tensor([0, 1, 0, 1])
    output = bank(hidden, labels)
    assert output.shape == (4, 7)
    with pytest.raises(ValueError, match="out-of-range"):
        bank(hidden, torch.tensor([0, 1, 2, 1]))


def test_matched_submodules_share_initialization_but_not_storage():
    score = torch.tensor([1, 3, 5])
    decoder = torch.randn(2, 3)
    kwargs = dict(
        hidden_dim=5,
        score_gene_indices=score,
        program_head_dim=3,
        private_adapter_dim=2,
        num_private_experts=2,
    )
    conditions = torch.nn.ModuleDict({
        "a": AlignedProgramCondition(program_decoder=decoder, **kwargs),
        "b": AlignedProgramCondition(program_decoder=decoder.flip(0), **kwargs),
    })
    clone_matching_submodules(conditions)
    left = conditions["a"].private.state_dict()
    right = conditions["b"].private.state_dict()
    assert left.keys() == right.keys()
    assert all(torch.equal(left[name], right[name]) for name in left)
    assert trainable_parameter_count(conditions["a"]) > 0


def test_condition_returns_score_residual_and_coefficients():
    condition = AlignedProgramCondition(
        hidden_dim=5,
        score_gene_indices=torch.tensor([1, 3, 5]),
        program_decoder=torch.randn(2, 3),
        program_head_dim=3,
        private_adapter_dim=2,
        num_private_experts=2,
    )
    hidden = torch.randn(4, 7, 5)
    masked = torch.randn(4, 7)
    labels = torch.tensor([0, 1, 0, 1])
    residual, coefficients = condition(hidden, masked, labels)
    assert residual.shape == (4, 3)
    assert coefficients.shape == (4, 2)
