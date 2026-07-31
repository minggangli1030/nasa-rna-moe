import json
from pathlib import Path

from evaluation.aggregate_tissue_site_tier2 import SEEDS, aggregate


def test_aggregate_requires_every_seed_to_pass(tmp_path: Path):
    protocol = {
        "status": "frozen_before_tissue_site_tier2_outcome_access",
        "inputs": {"seeds": list(SEEDS)},
        "decision": {"pass": "advance", "fail": "organ_only"},
    }
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(json.dumps(protocol))
    import hashlib

    digest = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    for seed in SEEDS:
        directory = tmp_path / f"seed{seed}"
        directory.mkdir()
        passed = seed != 42
        report = {
            "seed": seed,
            "protocol_sha256": digest,
            "all_gates_pass": passed,
            "gates": {"primary": passed},
            "pairwise": {
                name: {"relative_improvement": 0.1}
                for name in (
                    "soft_site_vs_protected_base",
                    "soft_site_vs_soft_shuffled_site",
                    "soft_site_vs_generic_capacity_matched",
                )
            },
        }
        (directory / "tissue_site_tier2_report.json").write_text(json.dumps(report))
    result = aggregate(protocol_path, tmp_path)
    assert result["all_seeds_pass"] is False
    assert result["decision"] == "organ_only"
    assert result["failed_gates_by_seed"][42] == ["primary"]
    assert result["best_seed_selection"] is False
