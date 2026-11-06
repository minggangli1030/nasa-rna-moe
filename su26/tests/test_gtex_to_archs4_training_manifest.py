from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
for source_dir in (ROOT / "core", ROOT / "evaluation"):
    if str(source_dir) not in sys.path:
        sys.path.insert(0, str(source_dir))

from build_gtex_to_archs4_training_manifest import (  # noqa: E402
    REQUIRED_STATUS,
    _assign_balanced_random_donors,
    build,
)
from train_manifest import sha256_file  # noqa: E402


ORGANS = (
    "adipose",
    "brain",
    "colon",
    "heart",
    "liver",
    "lung",
    "skeletal_muscle",
    "skin",
)


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _cohort() -> pd.DataFrame:
    rows = []
    for donor_index in range(40):
        donor = f"GTEX-D{donor_index:03d}"
        for organ_index, organ in enumerate(ORGANS):
            rows.append(
                {
                    "sample_id": f"{donor}-{organ_index:02d}-SM-X",
                    "donor_id": donor,
                    "organ": organ,
                    "tissue_site": f"{organ}-site-{donor_index % 2}",
                }
            )
    return pd.DataFrame(rows)


def _protocol(cohort_path: Path, *, status: str = REQUIRED_STATUS) -> dict:
    return {
        "schema_version": 1,
        "status": status,
        "organ_selection": {"ordered_organs": list(ORGANS)},
        "gtex_development": {
            "sealed_cohort_sha256": sha256_file(cohort_path),
            "split_seed": 20260724,
            "calibration_fraction": 0.2,
            "minimum_donors_per_organ_per_split": 5,
            "random_partition_seeds": [17, 42, 101],
        },
        "firewalls": {
            "archs4_lockbox_expression_access_before_candidate_freeze": False
        },
        "expression_contract": {"axis_definitions_sha256": ""},
    }


def _fixture(tmp_path: Path, *, frame: pd.DataFrame | None = None) -> dict[str, Path]:
    cohort_path = tmp_path / "sealed_cohort.parquet"
    (frame if frame is not None else _cohort()).to_parquet(cohort_path, index=False)
    protocol_path = tmp_path / "protocol.json"
    axis_path = tmp_path / "axis_definitions.npz"
    np.savez_compressed(
        axis_path,
        gene_names=np.asarray(["G1"]),
        score_gene_indices=np.asarray([0], dtype=np.int64),
        probe_gene_indices=np.asarray([], dtype=np.int64),
    )
    protocol = _protocol(cohort_path)
    protocol["expression_contract"]["axis_definitions_sha256"] = sha256_file(
        axis_path
    )
    _write_json(protocol_path, protocol)
    return {
        "cohort": cohort_path,
        "protocol": protocol_path,
        "axis_definitions": axis_path,
    }


def _args(fixture: dict[str, Path], output: Path) -> SimpleNamespace:
    return SimpleNamespace(
        sealed_cohort=str(fixture["cohort"]),
        axis_definitions=str(fixture["axis_definitions"]),
        protocol=str(fixture["protocol"]),
        expected_protocol_sha256=sha256_file(fixture["protocol"]),
        code_commit="a" * 40,
        output_dir=str(output),
    )


def test_manifest_is_donor_disjoint_complete_and_control_matched(tmp_path):
    fixture = _fixture(tmp_path)
    report = build(_args(fixture, tmp_path / "output"))
    manifest = pd.read_parquet(tmp_path / "output/gtex_training_manifest.parquet")

    assert report["status"] == "complete"
    assert report["metadata_only"] is True
    assert report["expression_values_read"] is False
    assert report["archs4_expression_accessed"] is False
    assert report["efficacy_scoring_performed"] is False
    assert report["counts"]["samples"] == 320
    assert report["counts"]["donors"] == 40
    assert report["split"]["train_donors"] == 32
    assert report["split"]["calibration_donors"] == 8
    assert set(manifest["split"]) == {"train", "calibration"}
    assert manifest.groupby("donor_id")["split"].nunique().max() == 1
    assert manifest["series_group_id"].equals(manifest["donor_id"])
    assert manifest["balanced_train"].all()
    assert manifest["organ_k8"].min() == 0
    assert manifest["organ_k8"].max() == 7
    assert set(manifest["organ_k8"]) == set(range(8))
    assert set(manifest["pooled_adapter"]) == {0}

    for seed in (17, 42, 101):
        axis = f"random_k8_p{seed}"
        assert set(manifest[axis]) == set(range(8))
        assert manifest.groupby("donor_id")[axis].nunique().max() == 1
        for split_name in ("train", "calibration"):
            subset = manifest[manifest["split"].eq(split_name)]
            assert set(subset[axis]) == set(range(8))
            for organ in ORGANS:
                assert set(subset.loc[subset["organ"].eq(organ), axis]) == set(
                    range(8)
                )

    train = set(manifest.loc[manifest["split"].eq("train"), "donor_id"])
    calibration = set(
        manifest.loc[manifest["split"].eq("calibration"), "donor_id"]
    )
    assert not train & calibration
    assert (tmp_path / "output/MANIFEST_COMPLETE").is_file()


def test_manifest_assignments_are_row_order_invariant(tmp_path):
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    first_fixture = _fixture(first_dir)
    shuffled = _cohort().sample(frac=1.0, random_state=91).reset_index(drop=True)
    second_fixture = _fixture(second_dir, frame=shuffled)

    first = build(_args(first_fixture, first_dir / "output"))
    second = build(_args(second_fixture, second_dir / "output"))
    first_frame = pd.read_parquet(
        first_dir / "output/gtex_training_manifest.parquet"
    )
    second_frame = pd.read_parquet(
        second_dir / "output/gtex_training_manifest.parquet"
    )

    pd.testing.assert_frame_equal(first_frame, second_frame)
    for key in first["hashes"]:
        if key in {"protocol_sha256", "sealed_cohort_sha256"}:
            continue
        assert first["hashes"][key] == second["hashes"][key]


def test_random_partition_balances_unbalanced_multiorgan_donors():
    rows = []
    for donor_index in range(32):
        donor = f"d{donor_index:03d}"
        for organ_index, organ in enumerate(ORGANS):
            repeats = 1 + int(organ == "brain" and donor_index % 3 == 0)
            for repeat in range(repeats):
                rows.append(
                    {
                        "sample_id": f"{donor}-{organ_index}-{repeat}",
                        "donor_id": donor,
                        "organ": organ,
                        "tissue_site": organ,
                    }
                )
    frame = pd.DataFrame(rows)
    labels, report = _assign_balanced_random_donors(
        frame,
        organs=ORGANS,
        k=8,
        seed=17,
        split_name="train",
    )
    labeled = frame.assign(label=labels)

    assert labeled.groupby("donor_id")["label"].nunique().max() == 1
    assert set(labels) == set(range(8))
    assert max(report["donors_per_shard"]) - min(report["donors_per_shard"]) <= 1
    for counts in report["organ_samples_per_shard"].values():
        assert max(counts) - min(counts) <= 2


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("draft", "not frozen"),
        ("hash", "SHA256 mismatch"),
        ("duplicate", "repeats sample IDs"),
        ("missing_organ", "organ set differs"),
        ("open_lockbox", "does not close"),
    ],
)
def test_manifest_fails_closed_on_contract_violations(tmp_path, mutation, message):
    fixture = _fixture(tmp_path)
    protocol = json.loads(fixture["protocol"].read_text())
    if mutation == "draft":
        protocol["status"] = "draft"
    elif mutation == "duplicate":
        frame = pd.read_parquet(fixture["cohort"])
        frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
        frame.to_parquet(fixture["cohort"], index=False)
        protocol["gtex_development"]["sealed_cohort_sha256"] = sha256_file(
            fixture["cohort"]
        )
    elif mutation == "missing_organ":
        frame = pd.read_parquet(fixture["cohort"])
        frame = frame[~frame["organ"].eq("lung")]
        frame.to_parquet(fixture["cohort"], index=False)
        protocol["gtex_development"]["sealed_cohort_sha256"] = sha256_file(
            fixture["cohort"]
        )
    elif mutation == "open_lockbox":
        protocol["firewalls"][
            "archs4_lockbox_expression_access_before_candidate_freeze"
        ] = True
    _write_json(fixture["protocol"], protocol)
    args = _args(fixture, tmp_path / "output")
    if mutation == "hash":
        args.expected_protocol_sha256 = "0" * 64
    with pytest.raises(ValueError, match=message):
        build(args)
