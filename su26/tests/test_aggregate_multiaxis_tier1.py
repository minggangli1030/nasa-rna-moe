from evaluation.aggregate_multiaxis_tier1 import evaluate_axis


def _seed(seed, *, bootstrap_low=0.1, minimum_safety=0.0):
    outcome = {
        "incremental_r2": 0.2,
        "donor_bootstrap": {"ci95": [bootstrap_low, 0.3]},
        "per_organ_incremental_r2": {"a": minimum_safety},
    }
    primary = {
        **outcome,
        "within_organ_permutation": {"real_above_p95": True},
    }
    return {
        "seed": seed,
        "results": {
            "axis": {
                "coverage": {"pass": True},
                "technical_proxy_pass": True,
                "maximum_absolute_technical_proxy_partial_correlation": 0.2,
                "outcomes": {
                    "pooled_reconstruction_error": outcome,
                    "protected_private_error": outcome,
                    "post_private_coefficients": primary,
                },
            }
        },
    }


def test_axis_requires_every_seed_and_downstream_gate():
    reports = [_seed(17), _seed(42), _seed(101)]
    osdr = {
        "results": {
            "axis": {
                "positive_gate": True,
                "auroc_minus_organ_base": 0.1,
                "study_bootstrap": {"ci95": [0.01, 0.2]},
            }
        }
    }
    result = evaluate_axis("axis", reports, osdr, maximum_harm=0.02)
    assert result["tier1_pass"]
    reports[1] = _seed(42, bootstrap_low=-0.01)
    assert not evaluate_axis(
        "axis", reports, osdr, maximum_harm=0.02
    )["tier1_pass"]


def test_axis_enforces_per_organ_safety():
    reports = [_seed(17), _seed(42, minimum_safety=-0.03), _seed(101)]
    osdr = {
        "results": {
            "axis": {
                "positive_gate": True,
                "auroc_minus_organ_base": 0.1,
                "study_bootstrap": {"ci95": [0.01, 0.2]},
            }
        }
    }
    result = evaluate_axis("axis", reports, osdr, maximum_harm=0.02)
    assert not result["tier1_pass"]
    assert not result["per_seed"][1]["gates"]["per_organ_safety"]
