import numpy as np

from evaluation.evaluate_osdr_hallmark_downstream import (
    _hallmark_pca_transform,
    random_matched_sets,
)


def test_random_sets_are_reproducible_and_size_matched():
    names = ["a", "b", "c"]
    sizes = [3, 5, 4]
    pool = [f"g{i}" for i in range(20)]
    first = random_matched_sets(names, sizes, pool, seed=17)
    second = random_matched_sets(names, sizes, pool, seed=17)
    assert first == second
    assert [len(first[name]) for name in names] == sizes
    assert all(len(set(first[name])) == len(first[name]) for name in names)


def test_combined_transform_is_fold_fit_and_has_expected_width():
    rng = np.random.default_rng(42)
    raw_train = rng.normal(size=(30, 100))
    raw_test = rng.normal(size=(8, 100))
    hallmark_train = rng.normal(size=(30, 50))
    hallmark_test = rng.normal(size=(8, 50))
    train, test = _hallmark_pca_transform(
        raw_train, raw_test, hallmark_train, hallmark_test
    )
    assert train.shape == (30, 79)
    assert test.shape == (8, 79)
    assert np.allclose(train[:, 29:].mean(axis=0), 0.0, atol=1e-10)
