from evaluation.check_organ_smoke_health import check


def _report():
    return {
        "validation": {
            "leakage_free": True,
            "random_shard_count_matches_organs": True,
            "mask_hash_verified": True,
            "prediction_masks_match_cache": True,
            "sample_hash_verified": True,
            "gene_hash_verified": True,
        },
        "router": {
            "uses_reconstruction_targets": False,
            "uses_test_labels_or_targets_for_fit": False,
        },
        "conditions": {
            name: {"primary_balanced_organ_study_macro": {"mse": 1.0}}
            for name in (
                "pooled", "organ_fixed", "true_organ_hard", "blind_organ_hard",
                "blind_organ_soft", "hard_oracle", "soft_oracle", "random_fixed",
                "random_soft_oracle", "organ_gene_mean",
            )
        },
        "comparisons": {
            name: {
                "primary": {
                    "candidate_mse": 1.0,
                    "reference_mse": 2.0,
                    "mse_improvement_mean": 1.0,
                    "relative_mse_reduction": 0.5,
                }
            }
            for name in (
                "pooled_vs_gene_mean", "true_organ_hard_vs_pooled",
                "organ_fixed_vs_random_fixed", "blind_hard_vs_pooled",
                "blind_soft_vs_organ_fixed", "soft_oracle_vs_organ_fixed",
            )
        },
        "models": {"organ_expert_order": ["a", "b"], "random_expert_order": ["0", "1"]},
        "splits": {"n_train": 2, "n_calibration": 2, "n_test": 2, "n_test_groups": 2},
    }


def test_smoke_health_passes_valid_report_and_rejects_leakage():
    report = _report()
    assert check(report)["status"] == "pass"
    report["validation"]["leakage_free"] = False
    assert check(report)["status"] == "fail"
