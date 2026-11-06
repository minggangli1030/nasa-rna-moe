import hashlib
import json
from pathlib import Path

import torch

from evaluation.freeze_final_k8_package import SEEDS, build_package, sha256_file


def _descriptor(root: Path, relative: str) -> dict:
    path = root / relative
    return {"path": relative, "sha256": sha256_file(path), "size_bytes": path.stat().st_size}


def test_package_preserves_all_seeds_without_training(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    entries = []
    for seed in SEEDS:
        directory = source / f"seed{seed}"
        directory.mkdir()
        torch.save(
            {"config": {"hidden_dim": 768}, "model_state_dict": {"x": torch.ones(1)}},
            directory / "pooled.pt",
        )
        (directory / "pooled.json").write_text("{}")
        torch.save(
            {"axis": "organ_k8", "training_seed": seed, "expert_state_dict": {"x": torch.ones(1)}},
            directory / "organ.pt",
        )
        (directory / "organ.json").write_text("{}")
        entries.append(
            {
                "seed": seed,
                "pooled": {
                    "checkpoint": _descriptor(source, f"seed{seed}/pooled.pt"),
                    "metadata": _descriptor(source, f"seed{seed}/pooled.json"),
                },
                "banks": {
                    "organ_k8": {
                        "checkpoint": _descriptor(source, f"seed{seed}/organ.pt"),
                        "metadata": _descriptor(source, f"seed{seed}/organ.json"),
                    }
                },
            }
        )
    router = source / "router"
    router.mkdir()
    (router / "router.npz").write_bytes(b"router")
    (router / "report.json").write_text("{}")
    ledger = {
        "seed_candidates": entries,
        "router": {
            "artifact": _descriptor(source, "router/router.npz"),
            "report": _descriptor(source, "router/report.json"),
        },
    }
    ledger_path = tmp_path / "ledger.json"
    ledger_path.write_text(json.dumps(ledger))
    protocol = {
        "status": "frozen_before_final_k8_package_execution",
        "role": "package",
        "architecture": {"seeds": list(SEEDS)},
        "source": {"candidate_ledger_sha256": sha256_file(ledger_path)},
        "output_contract": {"downstream_positive_embedding": None},
    }
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(json.dumps(protocol))
    output = tmp_path / "output"
    result = build_package(
        protocol_path=protocol_path,
        expected_protocol_sha256=sha256_file(protocol_path),
        ledger_path=ledger_path,
        training_root=source,
        output_dir=output,
        code_commit="a" * 40,
    )
    assert result["seeds"] == list(SEEDS)
    assert result["training_performed"] is False
    assert result["best_seed_selection"] is False
    assert (output / "FULL_SHA256SUMS").is_file()
    assert (output / "PACKAGE_COMPLETE").is_file()
