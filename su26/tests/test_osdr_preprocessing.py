from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evaluation"))

from evaluate_osdr import (  # noqa: E402
    OSDR_CACHE_SCHEMA_VERSION,
    OSDR_EXPRESSION_SPACE,
    build_mouse_canonical_reference,
    canonicalize_mouse_counts,
    decode_mouse_counts_for_qc,
    load_coverage_artifact,
    make_osdr_cache_fingerprint,
    make_mask_random_coverage,
    parse_spaceflight_condition,
    tpm_normalize_mouse,
    validate_log1p_tpm,
    validate_spaceflight_labels,
)


CANONICAL = ["H1", "H2", "H3"]
SYMBOL_TO_HUMAN = {"m1": "H1", "m2": "H2", "m3": "H3"}
ENSMUSG_TO_MOUSE = {"ENSMUSG1": "m1", "ENSMUSG2": "m2", "ENSMUSG3": "m3"}
LENGTHS = pd.Series([1_000.0, 2_000.0, 4_000.0], index=CANONICAL)


def test_symbol_and_ensembl_inputs_normalize_identically():
    symbol = pd.DataFrame({"s": [10.0, 20.0, 40.0]}, index=["m1", "m2", "m3"])
    ensembl = pd.DataFrame(
        {"s": [10.0, 20.0, 40.0]},
        index=["ENSMUSG1.7", "ENSMUSG2.1", "ENSMUSG3.9"],
    )
    symbol_counts, symbol_coverage = canonicalize_mouse_counts(
        symbol, CANONICAL, SYMBOL_TO_HUMAN, ENSMUSG_TO_MOUSE
    )
    ensembl_counts, ensembl_coverage = canonicalize_mouse_counts(
        ensembl, CANONICAL, SYMBOL_TO_HUMAN, ENSMUSG_TO_MOUSE
    )
    np.testing.assert_allclose(
        tpm_normalize_mouse(symbol_counts, LENGTHS),
        tpm_normalize_mouse(ensembl_counts, LENGTHS),
    )
    np.testing.assert_array_equal(symbol_coverage, ensembl_coverage)


def test_duplicate_mapped_rows_are_summed_before_tpm():
    counts = pd.DataFrame(
        {"s": [4.0, 6.0, 20.0, 40.0]},
        index=["ENSMUSG1.1", "ENSMUSG1.2", "ENSMUSG2", "ENSMUSG3"],
    )
    canonical, _ = canonicalize_mouse_counts(
        counts, CANONICAL, SYMBOL_TO_HUMAN, ENSMUSG_TO_MOUSE
    )
    assert canonical.loc["H1", "s"] == 10.0


def test_reference_uses_training_mapping_and_lengths_not_osdr_human_mapping():
    mapping = pd.DataFrame({
        "Gene name": ["H1"],
        "Mouse gene stable ID": ["ENSMUSG1"],
        "Mouse gene name": ["current_m1"],
        "Mouse homology type": ["ortholog_one2one"],
    })
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "mapping.csv"
        mapping.to_csv(path, index=False)
        symbol_map, stable_map, lengths = build_mouse_canonical_reference(
            ["H1"], pd.Series({"m1": 1234.0}), {"m1": "H1"}, path
        )
    assert symbol_map == {"m1": "H1"}
    assert stable_map == {"ENSMUSG1": "m1"}
    assert lengths.loc["H1"] == 1234.0


def test_cache_fingerprint_changes_with_qc_or_metadata():
    with tempfile.TemporaryDirectory() as tmp:
        metadata = Path(tmp) / "metadata.csv"
        metadata.write_text("sample\ns1\n")
        args = (
            metadata,
            ["H1"],
            {"m1": "H1"},
            {"ENSMUSG1": "m1"},
            pd.Series({"H1": 1234.0}),
        )
        first, _ = make_osdr_cache_fingerprint(*args, qc_min_nonzero=1)
        changed_qc, _ = make_osdr_cache_fingerprint(*args, qc_min_nonzero=2)
        metadata.write_text("sample\ns2\n")
        changed_metadata, _ = make_osdr_cache_fingerprint(*args, qc_min_nonzero=1)
    assert len({first, changed_qc, changed_metadata}) == 3


def test_coverage_artifact_is_bound_to_expression_hash():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "coverage.npz"
        np.savez_compressed(
            path,
            schema_version=np.int64(OSDR_CACHE_SCHEMA_VERSION),
            expression_space=np.asarray(OSDR_EXPRESSION_SPACE),
            cache_fingerprint=np.asarray("cache-hash"),
            expression_sha256=np.asarray("expression-hash"),
            coverage=np.asarray([[True, False]]),
            genes=np.asarray(["H1", "H2"]),
            sample_ids=np.asarray(["s1"]),
        )
        coverage = load_coverage_artifact(
            path,
            np.asarray(["s1"]),
            ["H2", "H1"],
            expected_cache_fingerprint="cache-hash",
            expected_expression_sha256="expression-hash",
        )
        np.testing.assert_array_equal(coverage, [[False, True]])
        with unittest.TestCase().assertRaisesRegex(ValueError, "expression hashes"):
            load_coverage_artifact(
                path,
                np.asarray(["s1"]),
                ["H1", "H2"],
                expected_expression_sha256="wrong-hash",
            )


def test_qc_decoding_filters_invalid_length_genes_before_nonzero_count():
    counts = pd.DataFrame(
        {"s": [4.0, 6.0, 9.0, 7.0]},
        index=["ENSMUSG1.1", "ENSMUSG1.2", "no_length", "m2"],
    )
    decoded = decode_mouse_counts_for_qc(
        counts,
        pd.Series({"m1": 1000.0, "m2": 2000.0}),
        {"ENSMUSG1": "m1"},
    )
    assert decoded.index.tolist() == ["m1", "m2"]
    assert decoded.loc["m1", "s"] == 10.0
    assert int((decoded["s"] > 0).sum()) == 2


def test_unmapped_large_gene_does_not_change_canonical_tpm():
    base = pd.DataFrame({"s": [10.0, 20.0, 40.0]}, index=["m1", "m2", "m3"])
    augmented = pd.concat([
        base,
        pd.DataFrame({"s": [1e12]}, index=["unmapped"]),
    ])
    base_counts, _ = canonicalize_mouse_counts(
        base, CANONICAL, SYMBOL_TO_HUMAN, ENSMUSG_TO_MOUSE
    )
    augmented_counts, _ = canonicalize_mouse_counts(
        augmented, CANONICAL, SYMBOL_TO_HUMAN, ENSMUSG_TO_MOUSE
    )
    np.testing.assert_allclose(
        tpm_normalize_mouse(base_counts, LENGTHS),
        tpm_normalize_mouse(augmented_counts, LENGTHS),
    )


def test_tpm_sums_to_one_million_and_missing_length_fails():
    counts = pd.DataFrame({"s": [10.0, 20.0, 40.0]}, index=CANONICAL)
    tpm = tpm_normalize_mouse(counts, LENGTHS)
    np.testing.assert_allclose(tpm.sum(axis=0), 1e6, rtol=1e-6)
    with unittest.TestCase().assertRaisesRegex(ValueError, "exon lengths"):
        tpm_normalize_mouse(counts, LENGTHS.drop("H3"))


def test_spaceflight_labels_preserve_other_and_missing_states():
    assert parse_spaceflight_condition(" Space   Flight ") == ("Space Flight", 1.0)
    assert parse_spaceflight_condition("ground control") == ("ground control", 0.0)
    condition, label = parse_spaceflight_condition("Vivarium Control")
    assert condition == "Vivarium Control" and np.isnan(label)
    condition, label = parse_spaceflight_condition(np.nan)
    assert condition == "" and np.isnan(label)


def test_spaceflight_label_validation_rejects_missing_and_invalid_states():
    with unittest.TestCase().assertRaisesRegex(ValueError, "missing required"):
        validate_spaceflight_labels(pd.DataFrame({"x": [1]}))
    with unittest.TestCase().assertRaisesRegex(ValueError, "invalid values"):
        validate_spaceflight_labels(pd.DataFrame({"spaceflight": [0.0, 2.0]}))
    labels = validate_spaceflight_labels(
        pd.DataFrame({"spaceflight": [0.0, 1.0, np.nan]})
    )
    np.testing.assert_allclose(labels[:2], [0.0, 1.0])
    assert np.isnan(labels[2])


def test_expression_space_validation_accepts_log1p_tpm_and_rejects_raw_tpm():
    tpm = np.array(
        [[250_000.0, 750_000.0], [600_000.0, 400_000.0]], dtype=np.float32
    )
    validate_log1p_tpm(np.log1p(tpm))
    with unittest.TestCase().assertRaisesRegex(ValueError, "not log1p TPM"):
        validate_log1p_tpm(tpm)


def test_random_masks_never_target_absent_genes():
    coverage = np.array([
        [True, True, True, False, False],
        [False, True, True, True, False],
    ])
    mask = make_mask_random_coverage(coverage, 2, np.random.default_rng(2))
    assert np.all(coverage[np.arange(2)[:, None], mask])


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            suite.addTest(unittest.FunctionTestCase(value))
    return suite
