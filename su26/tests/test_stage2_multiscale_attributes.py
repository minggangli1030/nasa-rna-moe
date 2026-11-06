from __future__ import annotations

import numpy as np

from evaluation.evaluate_stage2_multiscale_attributes import _stratum_result


def test_module_gate_passes_aligned_positive_programs():
    donor = np.ones((12, 20), dtype=np.float64)
    values = []
    for scale in (1.0, 1.1, 0.9):
        values.append({
            "correction_module": scale * np.arange(1.0, 33.0),
            "efficacy_module": scale * np.arange(1.0, 33.0),
            "efficacy_donor": donor,
            "semantic_donor": donor,
        })
    gate = {
        "minimum_pairwise_module_correction_cosine": 0.5,
        "minimum_pairwise_module_efficacy_spearman": 0.3,
        "minimum_pairwise_top8_module_jaccard": 0.33,
        "overall_specialist_vs_generic_95ci_lower_bound": 0.0,
        "overall_semantic_specificity_95ci_lower_bound": 0.0,
        "bootstrap_replicates": 50,
    }
    result = _stratum_result(values, gate=gate, bootstrap_seed=17)
    assert result["module_gate_pass"] is True
    assert result["min_module_correction_cosine"] > 0.99
