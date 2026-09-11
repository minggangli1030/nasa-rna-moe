from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evaluation"))

from analyze_moe_headroom import (  # noqa: E402
    CACHE_SCHEMA_VERSION,
    _make_or_load_mask,
    _sha256_arrays,
    analyze,
    prepare_expression,
)


def test_tpm_is_transformed_exactly_once():
    tpm = np.array([[0.0, 100_000.0, 900_000.0], [10.0, 20.0, 999_970.0]], dtype=np.float32)
    transformed, _ = prepare_expression(tpm, "tpm")
    np.testing.assert_allclose(transformed, np.log1p(tpm), rtol=1e-6)

    already_log, _ = prepare_expression(transformed, "log1p_tpm")
    np.testing.assert_allclose(already_log, transformed)


def test_input_space_mismatch_and_nonfinite_data_fail():
    raw = np.array([[0.0, 100_000.0, 900_000.0]], dtype=np.float32)
    with unittest.TestCase().assertRaisesRegex(ValueError, "raw-scale"):
        prepare_expression(raw, "log1p_tpm")
    with unittest.TestCase().assertRaisesRegex(ValueError, "already be log1p"):
        prepare_expression(np.log1p(raw), "tpm")
    raw[0, 0] = np.nan
    with unittest.TestCase().assertRaisesRegex(ValueError, "nonfinite"):
        prepare_expression(raw, "tpm")


def test_mask_generation_is_deterministic_and_coverage_aware():
    with tempfile.TemporaryDirectory() as directory:
        tmp_path = Path(directory)
        args = SimpleNamespace(mask_artifact=None, mask_ratio=0.25, seed=42)
        samples = np.array(["a", "b"])
        genes = [f"g{i}" for i in range(20)]
        coverage = np.ones((2, 20), dtype=bool)
        coverage[0, :4] = False
        coverage[1, -4:] = False

        first_dir = tmp_path / "first"
        second_dir = tmp_path / "second"
        first_dir.mkdir()
        second_dir.mkdir()
        first = _make_or_load_mask(args, first_dir, samples, genes, coverage)
        second = _make_or_load_mask(args, second_dir, samples, genes, coverage)

        np.testing.assert_array_equal(first, second)
        assert np.all(coverage[np.arange(2)[:, None], first])


def test_mask_artifact_rejects_absent_gene():
    with tempfile.TemporaryDirectory() as directory:
        tmp_path = Path(directory)
        samples = np.array(["a"])
        genes = [f"g{i}" for i in range(10)]
        coverage = np.ones((1, 10), dtype=bool)
        coverage[0, 2] = False
        artifact = tmp_path / "bad_mask.npz"
        np.savez_compressed(
            artifact,
            mask_idx_common=np.array([[1, 2, 3]]),
            common_genes=np.asarray(genes),
            sample_ids=samples,
        )
        args = SimpleNamespace(mask_artifact=str(artifact), mask_ratio=0.3, seed=42)

        with unittest.TestCase().assertRaisesRegex(ValueError, "absent"):
            _make_or_load_mask(args, tmp_path, samples, genes, coverage)


def test_legacy_cache_is_rejected_before_analysis():
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "out"
        output.mkdir()
        cache = output / "predictions.npz"
        np.savez_compressed(cache, common_genes=np.array(["A"]))
        args = SimpleNamespace(
            group_column="series_id", baseline_mean_npz=None, cv_folds=2,
            seed=42, bootstrap_reps=10, run_label="test",
        )
        with unittest.TestCase().assertRaisesRegex(ValueError, "legacy prediction cache rejected"):
            analyze(args, cache, output)


def test_synthetic_cache_analysis_writes_crossfit_report():
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory)
        rng = np.random.default_rng(4)
        n_samples, n_genes = 12, 10
        true = rng.normal(size=(n_samples, n_genes)).astype(np.float32)
        pred_h = true + rng.normal(scale=0.2, size=true.shape)
        pred_m = true + rng.normal(scale=0.3, size=true.shape)
        pred_x = true + rng.normal(scale=0.25, size=true.shape)
        mask = np.stack([rng.choice(n_genes, 4, replace=False) for _ in range(n_samples)])
        cache = output / "predictions.npz"
        np.savez_compressed(
            cache,
            schema_version=np.int64(CACHE_SCHEMA_VERSION),
            common_genes=np.asarray([f"g{i}" for i in range(n_genes)]),
            mask_idx_common=mask,
            gt_common=true,
            pred_human=pred_h,
            pred_mouse=pred_m,
            pred_mixed=pred_x,
            sample_ids=np.asarray([f"s{i}" for i in range(n_samples)]),
            species=np.asarray(["human"] * 6 + ["mouse"] * 6),
            series_id=np.asarray([f"study{i // 2}" for i in range(n_samples)]),
            input_space=np.asarray("tpm"),
            mask_ratio=np.float64(0.4),
            seed=np.int64(42),
            mask_sha256=np.asarray(_sha256_arrays(mask)),
            value_stats_json=np.asarray("{}"),
            checkpoint_info_json=np.asarray("{}"),
        )
        baseline = output / "mean.npz"
        np.savez_compressed(
            baseline,
            genes=np.asarray([f"g{i}" for i in range(n_genes)]),
            mean=np.zeros(n_genes),
            n_samples=np.int64(50),
        )
        args = SimpleNamespace(
            group_column="series_id", baseline_mean_npz=str(baseline), cv_folds=3,
            seed=42, bootstrap_reps=20, run_label="synthetic",
        )

        analyze(args, cache, output)

        report = json.loads((output / "report.json").read_text())
        assert "fixed_blend_mse_crossfit" in report["conditions"]
        assert "soft_oracle_mse" in report["conditions"]
        assert "metadata_species_soft_mse_crossfit" in report["conditions"]
        for comparison in report["comparisons"]:
            expected = (
                comparison["reference_mse_mean"] - comparison["candidate_mse_mean"]
            ) / comparison["reference_mse_mean"]
            assert abs(comparison["relative_mse_reduction"] - expected) < 1e-12


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            suite.addTest(unittest.FunctionTestCase(value))
    return suite
