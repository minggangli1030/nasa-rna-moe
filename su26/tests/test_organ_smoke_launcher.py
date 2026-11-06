from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import h5py
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def test_launcher_completes_tiny_cpu_pipeline(tmp_path: Path):
    genes = [f"G{index}" for index in range(8)]
    canonical = genes[:6]
    canonical_path = tmp_path / "genes.txt"
    canonical_path.write_text("\n".join(canonical) + "\n")
    exon_path = tmp_path / "exons.csv"
    pd.DataFrame({"gene_symbol": genes, "exon_length": [1000] * len(genes)}).to_csv(
        exon_path, index=False
    )

    rows = []
    for split in ("train", "calibration", "test"):
        for organ in ("brain", "skin"):
            for group_index in range(2):
                for sample_index in range(2):
                    rows.append({
                        "sample_id": f"{split}-{organ}-{group_index}-{sample_index}",
                        "organ": organ,
                        "series_group_id": f"{split}-{organ}-g{group_index}",
                        "split": split,
                    })
    manifest = pd.DataFrame(rows)
    manifest_path = tmp_path / "manifest.csv"
    manifest.to_csv(manifest_path, index=False)

    rng = np.random.default_rng(9)
    counts = rng.integers(5, 100, size=(len(genes), len(manifest)), dtype=np.int32)
    h5_path = tmp_path / "human.h5"
    with h5py.File(h5_path, "w") as handle:
        handle.create_dataset("data/expression", data=counts)
        handle.create_dataset(
            "meta/samples/geo_accession",
            data=np.asarray(manifest["sample_id"].tolist(), dtype="S"),
        )
        handle.create_dataset("meta/genes/gene_symbol", data=np.asarray(genes, dtype="S"))

    output = tmp_path / "run"
    env = os.environ.copy()
    env.update({
        "PYTHON_BIN": sys.executable,
        "SOURCE_MANIFEST": str(manifest_path),
        "HUMAN_H5": str(h5_path),
        "CANONICAL_GENES": str(canonical_path),
        "HUMAN_EXON_LENGTHS": str(exon_path),
        "QC_MIN_NONZERO": "1",
        "MAX_UPDATES": "1",
        "BATCH_SIZE": "2",
        "HIDDEN_DIM": "8",
        "FFN_DIM": "16",
        "NUM_HEADS": "2",
        "NUM_LAYERS": "1",
        "BOOTSTRAP_REPS": "20",
        "DEVICE": "cpu",
    })
    completed = subprocess.run(
        [
            "bash",
            str(ROOT / "runs/run_organ_smoke.sh"),
            "--allow-stage0-incomplete",
            "--output-root",
            str(output),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stdout + "\n" + completed.stderr
    assert (output / "COMPLETE").is_file()
    assert (output / "SMOKE_ONLY").is_file()
    assert not (output / "FAILED").exists()
    assert (output / "STATUS").read_text().startswith("COMPLETE ")
    health = json.loads((output / "mechanical_health.json").read_text())
    assert health["status"] == "pass"
    report = json.loads((output / "evaluation/report.json").read_text())
    assert report["validation"]["leakage_free"] is True
    assert report["router"]["uses_reconstruction_targets"] is False
    assert set(report["models"]["organ_expert_order"]) == {"brain", "skin"}
