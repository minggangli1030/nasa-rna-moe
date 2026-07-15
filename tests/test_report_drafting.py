from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))

import draft_interspecies_report as report_module  # noqa: E402


def _comparison(
    name: str,
    *,
    relative: float = 0.04,
    mse_ci: tuple[float, float] = (0.02, 0.06),
    residual_ci: tuple[float, float] = (0.005, 0.015),
) -> dict:
    return {
        "name": name,
        "pearson_gain_mean": 0.02,
        "pearson_gain_ci95": [0.01, 0.03],
        "mse_improvement_mean": 0.04,
        "mse_improvement_ci95": list(mse_ci),
        "candidate_mse_mean": 1.0 - relative,
        "reference_mse_mean": 1.0,
        "relative_mse_reduction": relative,
        "residual_pearson_gain_mean": 0.01,
        "residual_pearson_gain_ci95": list(residual_ci),
    }


def _report(checkpoint_prefix: str) -> dict:
    conditions = {
        name: {
            "primary_pearson_study_macro": 0.5,
            "primary_residual_pearson_study_macro": 0.1,
            "primary_mse_study_macro": 0.2,
        }
        for name in report_module.CONDITIONS
    }
    comparisons = [
        _comparison(name)
        for name in (
            "fixed_blend_vs_pooled_mixed",
            "species_soft_vs_pooled_mixed",
            "species_soft_vs_fixed_blend",
            "soft_mse_oracle_vs_fixed_blend",
        )
    ]
    return {
        "conditions": conditions,
        "comparisons": comparisons,
        "checkpoint_info": {
            expert: {"sha256": f"{checkpoint_prefix}-{expert}"}
            for expert in ("human", "mouse", "mixed")
        },
    }


def _scale() -> dict:
    return {
        "direct_scale_change": [
            {
                "condition": condition,
                "pearson_20k_minus_5k": {"mean": 0.03, "ci95": [0.01, 0.05]},
                "mse_5k_minus_20k": {"mean": 0.02, "ci95": [0.01, 0.03]},
            }
            for condition in (
                "human",
                "mouse",
                "mixed",
                "fixed_blend_mse_crossfit",
                "metadata_species_soft_mse_crossfit",
            )
        ]
    }


def test_report_render_uses_validated_results_and_includes_decision_sections():
    validation = {
        "n_common_genes": 15448,
        "n_masked_genes": 4634,
        "full_mask_sha256": "full-mask",
        "strict_mask_sha256": "strict-mask",
    }

    def fake_read(path: Path) -> dict:
        if path.name.startswith("interspecies_scale_change"):
            return _scale()
        prefix = "20k" if "20k" in str(path) else "5k"
        return _report(prefix)

    with (
        mock.patch.object(report_module, "validate", return_value=validation) as validate,
        mock.patch.object(report_module, "_read", side_effect=fake_read),
    ):
        rendered, fingerprint = report_module.render(Path("results"))

    validate.assert_called_once_with(Path("results"))
    assert len(fingerprint) == 64
    assert f"<!-- corrected-interspecies-report:{fingerprint} -->" in rendered
    assert "### 5K Full results" in rendered
    assert "### 20K Strict results" in rendered
    assert "### Paired scale effect: 20k minus 5k" in rendered
    assert "### Recommended next work" in rendered
    assert "Promising adaptive MoE ceiling" in rendered
    assert "relative MSE reduction 4.0%" in rendered


def _diagnosis(
    *,
    fixed_relative: float,
    fixed_mse_ci: tuple[float, float],
    fixed_residual_ci: tuple[float, float] = (-0.01, 0.01),
    pooled_mse_ci: tuple[float, float] = (0.02, 0.06),
) -> str:
    report = _report("20k")
    by_name = {row["name"]: row for row in report["comparisons"]}
    by_name["species_soft_vs_pooled_mixed"].update(
        _comparison("species_soft_vs_pooled_mixed", relative=0.10, mse_ci=pooled_mse_ci)
    )
    by_name["species_soft_vs_fixed_blend"].update(
        _comparison(
            "species_soft_vs_fixed_blend",
            relative=fixed_relative,
            mse_ci=fixed_mse_ci,
            residual_ci=fixed_residual_ci,
        )
    )
    return report_module._diagnose_usefulness(report)


def test_pooled_win_without_fixed_blend_win_is_only_ensemble_benefit():
    diagnosis = _diagnosis(fixed_relative=-0.01, fixed_mse_ci=(-0.03, 0.01))
    assert "ensemble benefit" in diagnosis
    assert "does not establish usable adaptive MoE benefit" in diagnosis
    assert "Promising adaptive MoE" not in diagnosis


def test_positive_ci_below_three_percent_is_practically_small():
    diagnosis = _diagnosis(fixed_relative=0.029, fixed_mse_ci=(0.001, 0.02))
    assert "statistically positive" in diagnosis
    assert "below 3%" in diagnosis
    assert "Promising adaptive MoE" not in diagnosis


def test_three_percent_with_positive_mse_ci_is_promising():
    diagnosis = _diagnosis(fixed_relative=0.03, fixed_mse_ci=(0.001, 0.03))
    assert "Promising adaptive MoE ceiling" in diagnosis
    assert "Practically convincing" not in diagnosis


def test_five_percent_with_positive_residual_ci_is_convincing():
    diagnosis = _diagnosis(
        fixed_relative=0.05,
        fixed_mse_ci=(0.001, 0.04),
        fixed_residual_ci=(0.001, 0.02),
    )
    assert "Practically convincing adaptive MoE ceiling" in diagnosis


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            suite.addTest(unittest.FunctionTestCase(value))
    return suite
