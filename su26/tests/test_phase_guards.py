import pytest

torch = pytest.importorskip("torch")
from torch import nn
from torch.optim import SGD
from torch.optim.lr_scheduler import CosineAnnealingLR

from core.phase_guards import (
    PhaseGuard,
    snapshot_trainable_state,
    tensor_state_sha256,
    validate_optimizer_coverage,
)


def _one_update(model: nn.Module, optimizer: SGD) -> None:
    optimizer.zero_grad(set_to_none=True)
    loss = model(torch.ones(4, 3)).square().mean()
    loss.backward()
    optimizer.step()


def test_positive_training_moves_declared_module():
    model = nn.Linear(3, 2)
    optimizer = SGD(model.parameters(), lr=0.1)
    guard = PhaseGuard("positive", {"head": model}, {"head": optimizer})
    _one_update(model, optimizer)
    report = guard.movement(checkpoint="update_1")
    assert report["module_deltas"]["head"]["l2"] > 0
    assert (
        report["initial_trainable_state_sha256"]
        != report["current_trainable_state_sha256"]
    )


def test_zero_learning_rate_fails_before_training():
    model = nn.Linear(3, 2)
    optimizer = SGD(model.parameters(), lr=0.0)
    with pytest.raises(ValueError, match="finite and positive"):
        PhaseGuard("zero_lr", {"head": model}, {"head": optimizer})


def test_declared_module_that_does_not_move_fails_closed():
    model = nn.Linear(3, 2)
    optimizer = SGD(model.parameters(), lr=0.1)
    guard = PhaseGuard("stagnant", {"head": model}, {"head": optimizer})
    with pytest.raises(RuntimeError, match="did not move"):
        guard.movement(checkpoint="update_1")


def test_terminal_cosine_zero_is_allowed_after_real_update():
    model = nn.Linear(3, 2)
    optimizer = SGD(model.parameters(), lr=0.1)
    scheduler = CosineAnnealingLR(optimizer, T_max=1)
    guard = PhaseGuard("cosine", {"head": model}, {"head": optimizer})
    _one_update(model, optimizer)
    scheduler.step()
    assert optimizer.param_groups[0]["lr"] == pytest.approx(0.0)
    assert guard.movement(checkpoint="terminal")["module_deltas"]["head"]["l2"] > 0


def test_identical_phase_boundary_hash_is_detected():
    model = nn.Linear(3, 2)
    optimizer = SGD(model.parameters(), lr=0.1)
    guard = PhaseGuard("identical", {"head": model}, {"head": optimizer})
    current = tensor_state_sha256(snapshot_trainable_state({"head": model}))
    assert current == guard.initial_sha256
    with pytest.raises(RuntimeError, match="did not move"):
        guard.movement(checkpoint="phase_end")


def test_optimizer_must_cover_exact_declared_parameters():
    model = nn.Sequential(nn.Linear(3, 2), nn.Linear(2, 1))
    optimizer = SGD(model[0].parameters(), lr=0.1)
    with pytest.raises(ValueError, match="coverage differs"):
        validate_optimizer_coverage(
            {"head": model}, {"head": optimizer}, phase="coverage"
        )
