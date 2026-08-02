import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evaluation"))

from evaluate_post_d2_phase1 import (  # noqa: E402
    paired_study_bootstrap,
    sha256_file,
    verify_protocol,
)


def test_paired_study_bootstrap_is_directional_and_deterministic():
    rows = []
    for study_index, study in enumerate(("S1", "S2", "S3")):
        for label in (0, 1):
            sample = f"{study}-{label}"
            rows.extend(
                [
                    {
                        "representation": "candidate",
                        "sample_id": sample,
                        "study_id": study,
                        "organ": "skeletal_muscle",
                        "label": label,
                        "probability": 0.1 + 0.8 * label,
                    },
                    {
                        "representation": "baseline",
                        "sample_id": sample,
                        "study_id": study,
                        "organ": "skeletal_muscle",
                        "label": label,
                        "probability": 0.45 + 0.1 * ((label + study_index) % 2),
                    },
                ]
            )
    frame = pd.DataFrame(rows)
    first = paired_study_bootstrap(
        frame,
        candidate="candidate",
        baseline="baseline",
        seed=17,
        replicates=100,
    )
    second = paired_study_bootstrap(
        frame,
        candidate="candidate",
        baseline="baseline",
        seed=17,
        replicates=100,
    )
    assert first == second
    assert first["delta_auroc"] > 0
    assert first["study_bootstrap_ci95"][0] >= 0


def test_protocol_hash_is_fail_closed(tmp_path: Path):
    path = tmp_path / "protocol.json"
    path.write_text(
        json.dumps({"status": "frozen_post_d2_secondary_analysis_before_execution"})
    )
    digest = sha256_file(path)
    assert verify_protocol(path, digest)["status"].startswith("frozen_post_d2")
    path.write_text("{}")
    try:
        verify_protocol(path, digest)
    except ValueError as error:
        assert "mismatch" in str(error)
    else:
        raise AssertionError("modified protocol did not fail closed")
