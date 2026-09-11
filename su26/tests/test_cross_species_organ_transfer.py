import numpy as np

from evaluation.audit_cross_species_organ_transfer import (
    frozen_verdict,
    select_alpha_by_grouped_cv,
)


def test_frozen_verdict_uses_all_embedding_seeds():
    gates = {"preserved_balanced_accuracy": 0.60, "lost_balanced_accuracy": 0.25}
    assert frozen_verdict(0.8, [0.7, 0.62, 0.61], gates) == "CROSS_SPECIES_ORGAN_STRUCTURE_PRESERVED"
    assert frozen_verdict(0.8, [0.2, 0.22, 0.24], gates) == "ENCODER_SPECIFIC_ORGAN_INFORMATION_LOSS"
    assert frozen_verdict(0.2, [0.15, 0.18, 0.20], gates) == "CROSS_SPECIES_GAP_UPSTREAM_OR_TASK_LIMIT"
    assert frozen_verdict(0.8, [0.7, 0.5, 0.3], gates) == "CROSS_SPECIES_ORGAN_TRANSFER_PARTIAL"


def test_grouped_alpha_selection_is_reproducible():
    rng = np.random.default_rng(17)
    groups = np.repeat([f"d{i}" for i in range(12)], 3)
    labels = np.tile(np.asarray(["a", "b", "c"]), 12)
    features = np.eye(3)[np.tile(np.arange(3), 12)] + 0.05 * rng.normal(size=(36, 3))
    first = select_alpha_by_grouped_cv(features, labels, groups, alphas=(1e-4, 1e-3), folds=3, seed=17)
    second = select_alpha_by_grouped_cv(features, labels, groups, alphas=(1e-4, 1e-3), folds=3, seed=17)
    assert first == second
