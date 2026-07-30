import numpy as np
import pytest

from core.stage2b_cache import CanonicalCacheKey, assert_cache_key
from core.stage2b_metrics import rank_record, ridge_effective_dof


def _sha(char: str) -> str:
    return char * 64


def _cache_key() -> CanonicalCacheKey:
    return CanonicalCacheKey(
        sample_id="GTEX-1",
        trunk_checkpoint_sha256=_sha("a"),
        manifest_sha256=_sha("b"),
        score_index_sha256=_sha("c"),
        decoder_sha256=_sha("d"),
        mask_token_id="float:-10.0",
        preprocessing_version="stage2b-canonical-v1",
        ridge_lambda=1e-5,
        dtype_policy="deterministic-fp32",
    )


def test_canonical_cache_key_round_trip_is_exact_and_hash_stable():
    key = _cache_key()
    assert_cache_key(key.to_dict(), key)
    assert key.sha256() == _cache_key().sha256()
    changed = key.to_dict()
    changed["ridge_lambda"] = 1e-4
    with pytest.raises(ValueError, match="changed=.*ridge_lambda"):
        assert_cache_key(changed, key)
    missing = key.to_dict()
    missing.pop("decoder_sha256")
    with pytest.raises(ValueError, match="missing=.*decoder_sha256"):
        assert_cache_key(missing, key)


def test_rank_record_distinguishes_entropy_rank_from_participation_ratio():
    rows, dims = 16, 7
    rng = np.random.default_rng(17)
    raw = rng.normal(size=(rows, dims))
    centered = raw - raw.mean(axis=0, keepdims=True)
    left, _, _ = np.linalg.svd(centered, full_matrices=False)
    spectrum = np.asarray([3.0, 1, 1, 1, 1, 1, 1])
    values = left[:, :dims] @ np.diag(np.sqrt((rows - 1) * spectrum))
    record = rank_record(
        values,
        convention="raw",
        aggregation_unit="sample",
        ridge_lambda=0.01,
        effective_dof=6.5,
    )
    assert record.participation_ratio == pytest.approx(5.4, abs=1e-10)
    assert record.entropy_rank == pytest.approx(6.240251, abs=1e-5)
    assert record.entropy_rank > record.participation_ratio
    assert record.n_rows == rows
    assert record.n_dims == dims
    assert len(record.eigenvalues) == dims


def test_rank_record_rejects_row_limited_matrices():
    with pytest.raises(ValueError, match="n_rows > n_dims"):
        rank_record(
            np.ones((4, 4)),
            convention="standardized",
            aggregation_unit="donor",
            ridge_lambda=0.0,
            effective_dof=4.0,
        )


def test_ridge_effective_dof_matches_closed_form():
    decoder = np.diag([3.0, 2.0, 1.0])
    ridge = 2.0
    expected = 9 / 11 + 4 / 6 + 1 / 3
    assert ridge_effective_dof(decoder, ridge) == pytest.approx(expected)
