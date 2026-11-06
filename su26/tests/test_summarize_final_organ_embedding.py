import hashlib
import json
from pathlib import Path

from evaluation.summarize_final_organ_embedding import REPORTABLE, SEEDS, summarize


def test_summary_requires_one_contract_to_beat_every_reference(tmp_path: Path):
    protocol = {
        "status": "frozen_before_final_organ_embedding_development_outcome_access"
    }
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(json.dumps(protocol))
    digest = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    results = {
        "raw_expression": {"pooled_out_of_fold": {"auroc": 0.70}},
        "pca_64": {"pooled_out_of_fold": {"auroc": 0.71}},
    }
    for name in REPORTABLE:
        for seed in SEEDS:
            value = 0.72 if name == "blind_router_soft_embedding" and seed != 101 else 0.60
            results[f"seed{seed}__{name}"] = {
                "pooled_out_of_fold": {"auroc": value}
            }
    report = {
        "status": "complete",
        "smoke": False,
        "protocol_sha256": digest,
        "results": results,
    }
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report))
    output = summarize(protocol_path, report_path)
    assert output["any_deployable_embedding_passes"] is False
    assert output["deployable_gates"]["blind_router_soft_embedding"]["by_seed"]["101"]["beats_all_references"] is False
    assert output["best_seed_selection"] is False
