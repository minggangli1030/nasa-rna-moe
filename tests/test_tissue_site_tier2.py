import numpy as np
import torch

from core.tissue_site_tier2 import (
    ResidualHead,
    SiteBank,
    SiteRouter,
    donor_bootstrap_difference,
    parameter_count,
    relative_improvement,
    router_usage,
)


def test_frozen_parameter_match_is_within_two_percent():
    site = SiteBank(768, 16, 32, 20)
    router = SiteRouter(768, 20)
    generic = ResidualHead(768, 340, 32)
    site_count = parameter_count(site) + parameter_count(router)
    generic_count = parameter_count(generic)
    assert abs(site_count - generic_count) / site_count < 0.02


def test_site_bank_known_dispatch():
    torch.manual_seed(17)
    bank = SiteBank(4, 3, 2, 2)
    values = torch.randn(5, 4)
    labels = torch.tensor([0, 1, 0, 1, 1])
    all_values = bank.forward_all(values)
    expected = all_values[torch.arange(5), labels]
    assert torch.equal(bank.forward_known(values, labels), expected)


def test_relative_and_bootstrap_improvement_are_positive():
    base = np.ones(20)
    candidate = np.full(20, 0.8)
    donors = np.repeat([f"d{i}" for i in range(10)], 2)
    assert np.isclose(relative_improvement(base, candidate), 0.2)
    result = donor_bootstrap_difference(
        base, candidate, donors, replicates=100, seed=42
    )
    assert result["ci95"][0] > 0


def test_router_usage_detects_noncollapse():
    probabilities = np.tile([[0.8, 0.2], [0.2, 0.8]], (4, 1))
    organs = np.repeat(["a", "b"], 4)
    usage = router_usage(probabilities, organs, ["a", "b"])
    assert usage["a"]["effective_soft_sites"] > 1.25
    assert usage["a"]["hard_sites_used"] == 2
