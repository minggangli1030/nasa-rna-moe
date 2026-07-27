from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import pandas as pd
import pytest

from evaluation.build_stage2_directed_transfer_schedules import (
    ORGANS,
    RANDOM_AXES,
    compile_schedules,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest(path: Path) -> pd.DataFrame:
    rows = []
    for donor_index in range(24):
        donor = f"donor-{donor_index:02d}"
        for organ_index, organ in enumerate(ORGANS):
            rows.append(
                {
                    "sample_id": f"{donor}-{organ}",
                    "donor_id": donor,
                    "split": "train" if donor_index < 20 else "calibration",
                    "balanced_train": donor_index < 20,
                    "organ": organ,
                    "series_group_id": donor,
                    "random_k8_p17": donor_index % 8,
                    "random_k8_p42": (donor_index + 3) % 8,
                    "random_k8_p101": (donor_index + 5) % 8,
                }
            )
    frame = pd.DataFrame(rows)
    frame.to_parquet(path, index=False)
    return frame


def _args(manifest: Path, output: Path, **updates):
    values = {
        "manifest": str(manifest),
        "expected_manifest_sha256": _sha(manifest),
        "output_dir": str(output),
        "schedule_seed": 20260727,
        "draws_per_source": 6,
        "initialization_key": "shared-k1",
        "additive_edge": None,
    }
    values.update(updates)
    return argparse.Namespace(**values)


def test_compile_exact_substitution_and_random_control_schedules(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.parquet"
    source = _manifest(manifest)
    output = tmp_path / "output"
    report = compile_schedules(_args(manifest, output))

    assert report["status"] == "complete"
    assert report["development_only"] is True
    assert report["expression_loaded"] is False
    assert report["model_fit"] is False
    assert report["counts"]["substitution_recipient_only_arms"] == 8
    assert report["counts"]["substitution_pair_arms"] == 28
    assert report["counts"]["substitution_random_control_arms"] == 24
    assert report["counts"]["total_arms"] == 60

    schedules = pd.read_parquet(output / "training_schedules.parquet")
    brain_only = schedules.loc[
        schedules["arm_id"].eq("sub__brain__recipient_only")
    ]
    assert len(brain_only) == 12
    assert brain_only["organ"].eq("brain").all()

    pair = schedules.loc[schedules["arm_id"].eq("sub__brain__liver")]
    assert pair["source_role"].value_counts().to_dict() == {
        "organ_1": 6,
        "organ_2": 6,
    }
    assert pair.groupby("source_role")["organ"].unique().map(list).to_dict() == {
        "organ_1": ["brain"],
        "organ_2": ["liver"],
    }

    random_arm = schedules.loc[
        schedules["arm_id"].eq("sub__brain__random__random_k8_p17")
    ]
    assert random_arm["source_role"].value_counts().to_dict() == {
        "recipient": 6,
        "random_auxiliary": 6,
    }
    auxiliary = random_arm.loc[
        random_arm["source_role"].eq("random_auxiliary")
    ]
    assert not auxiliary["organ"].eq("brain").any()
    selected = source.loc[
        source["sample_id"].isin(auxiliary["sample_id"])
    ]
    assert selected["random_k8_p17"].eq(ORGANS.index("brain")).all()

    # Recipient exposure is paired at the source level, not merely equal in count.
    brain_from_pair = pair.loc[pair["source_role"].eq("organ_1")].sort_values(
        "source_draw_number"
    )
    brain_from_only = brain_only.sort_values("source_draw_number").iloc[:6]
    assert brain_from_pair["sample_id"].tolist() == brain_from_only["sample_id"].tolist()
    assert brain_from_pair["source_draw_number"].tolist() == list(range(6))


def test_additive_edges_preserve_recipient_draws_and_add_controls(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.parquet"
    _manifest(manifest)
    output = tmp_path / "output"
    report = compile_schedules(
        _args(
            manifest,
            output,
            additive_edge=["brain:liver", "brain:skin"],
        )
    )
    schedules = pd.read_parquet(output / "training_schedules.parquet")
    named = schedules.loc[schedules["arm_id"].eq("add__brain__liver")]
    assert named["source_role"].value_counts().to_dict() == {
        "recipient": 12,
        "donor": 6,
    }
    self_control = schedules.loc[
        schedules["arm_id"].eq("add__brain__self_control")
    ]
    assert len(self_control) == 18
    assert self_control["organ"].eq("brain").all()
    assert report["counts"]["additive_named_donor_arms"] == 2
    assert report["counts"]["total_arms"] == 66


def test_compiler_fails_closed_on_hash_or_non_atomic_random_axis(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.parquet"
    frame = _manifest(manifest)
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        compile_schedules(
            _args(
                manifest,
                tmp_path / "bad-hash",
                expected_manifest_sha256="0" * 64,
            )
        )

    frame.loc[
        (frame["donor_id"].eq("donor-00")) & (frame["organ"].eq("brain")),
        RANDOM_AXES[0],
    ] = 7
    frame.to_parquet(manifest, index=False)
    with pytest.raises(ValueError, match="not donor-atomic"):
        compile_schedules(_args(manifest, tmp_path / "not-atomic"))


@pytest.mark.parametrize(
    ("edges", "message"),
    [
        (["brain"], "RECIPIENT:DONOR"),
        (["brain:brain"], "off-diagonal"),
        (["brain:unknown"], "unknown organ"),
        (["brain:liver", "brain:liver"], "repeated"),
    ],
)
def test_compiler_rejects_invalid_additive_edges(
    tmp_path: Path, edges: list[str], message: str
) -> None:
    manifest = tmp_path / "manifest.parquet"
    _manifest(manifest)
    with pytest.raises(ValueError, match=message):
        compile_schedules(
            _args(manifest, tmp_path / "output", additive_edge=edges)
        )
