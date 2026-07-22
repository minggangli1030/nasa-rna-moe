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

from build_stage1_k4_final_refit_manifest import (  # noqa: E402
    ACTIVE_ORGANS,
    CANONICAL_ORGANS,
    EXPECTED_CALIBRATION_SAMPLES,
    EXPECTED_FIT_SAMPLES,
    EXPECTED_TRAIN_SAMPLES,
    FINAL_AXES,
    FINAL_RANDOM_AXES,
    FIT_ROLE,
    ORGAN_TO_FINAL_LABEL,
    OUTPUT_FILENAME,
    RANDOM_SEEDS,
    RANDOM_ASSIGNMENT_POLICY,
    SOURCE_RANDOM_AXES,
    _assignment_hash,
    build,
)
from train_manifest import sha256_file  # noqa: E402


TRAIN_COUNTS = {
    "adipose": 363,
    "brain": 363,
    "liver": 363,
    "skeletal_muscle": 363,
    "skin": 363,
}
CALIBRATION_COUNTS = {
    "adipose": 136,
    "brain": 242,
    "liver": 85,
    "skeletal_muscle": 184,
    "skin": 195,
}
OLD_K45_PROTOCOL_HASH = "a" * 64


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _source_frame() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    sample_index = 0
    seed_offsets = {17: 0, 42: 1, 101: 3}
    for utility_split, counts in (
        ("train", TRAIN_COUNTS),
        ("calibration", CALIBRATION_COUNTS),
    ):
        for organ, count in counts.items():
            remaining = count
            group_index = 0
            while remaining:
                group_size = min(3, remaining)
                group = f"{utility_split}-{organ}-study-{group_index:04d}"
                organ_label = ORGAN_TO_FINAL_LABEL.get(organ, -1)
                for _ in range(group_size):
                    row: dict[str, object] = {
                        "sample_id": f"sample-{sample_index:05d}",
                        "utility_split": utility_split,
                        "split": utility_split,
                        "organ": organ,
                        "series_group_id": group,
                        "organ_k4_epe": organ_label,
                    }
                    for seed, axis in zip(RANDOM_SEEDS, SOURCE_RANDOM_AXES):
                        row[axis] = (
                            -1
                            if organ == "adipose"
                            else (group_index + seed_offsets[seed]) % 4
                        )
                    rows.append(row)
                    sample_index += 1
                group_index += 1
                remaining -= group_size
    frame = pd.DataFrame(rows)
    assert len(frame) == EXPECTED_FIT_SAMPLES
    return frame


def _source_report(frame: pd.DataFrame, manifest_path: Path) -> dict:
    hashes = {
        "protocol_sha256": OLD_K45_PROTOCOL_HASH,
        "partition_manifest_sha256": sha256_file(manifest_path),
    }
    for axis in ("organ_k4_epe", *SOURCE_RANDOM_AXES):
        hashes[f"{axis}_assignment_sha256"] = _assignment_hash(frame, axis)
    return {
        "schema_version": 1,
        "status": "complete",
        "development_only": True,
        "test_accessed": False,
        "test_assignment_metadata_accessed": False,
        "counts": {
            "train": sum(TRAIN_COUNTS.values()),
            "calibration": sum(CALIBRATION_COUNTS.values()),
        },
        "config": {"axes": ["organ_k4_epe", *SOURCE_RANDOM_AXES]},
        "hashes": hashes,
    }


def _k45_evaluation_report(
    manifest_path: Path,
    source_report_path: Path,
    *,
    selected_candidate: str = "k4_epe",
) -> dict:
    return {
        "schema_version": 1,
        "status": "complete",
        "experiment": "development_only_genuine_organ_k4_k5_retraining",
        "development_only": True,
        "test_accessed": False,
        "independent_confirmation": False,
        "external_confirmation_required": True,
        "decision": {
            "decision_branch": "k4_robust",
            "selected_candidate_for_future_freeze": selected_candidate,
            "development_only": True,
            "test_accessed": False,
            "automatic_external_test_authorization": False,
        },
        "technical_gates": {
            "development_firewall": True,
            "alignment": True,
            "router_target_hidden": True,
            "shared_epe_experts_bitwise_equal": True,
        },
        "support_gate_details": {
            "k4_epe": {
                "blind_vs_pooled": True,
                "true_vs_pooled": True,
                "true_vs_every_random": True,
                "exposure": True,
            }
        },
        "noninferiority": {"gates": {"k4_epe": True}},
        "hashes": {
            "protocol_sha256": OLD_K45_PROTOCOL_HASH,
            "partition_manifest_sha256": sha256_file(manifest_path),
            "partition_report_sha256": sha256_file(source_report_path),
        },
    }


def _final_protocol(
    manifest_path: Path,
    source_report_path: Path,
    k45_report_path: Path,
    development_fit_manifest_sha256: str,
) -> dict:
    return {
        "schema_version": 1,
        "evidence_label": {
            "label": "final_refit_for_external_confirmation",
            "development_only": True,
            "internally_confirmatory": False,
            "internal_efficacy_scoring": False,
        },
        "data": {
            "source_k45_partition_manifest_sha256": sha256_file(manifest_path),
            "source_k45_partition_report_sha256": sha256_file(source_report_path),
            "fitting_pool": "balanced_train_plus_calibration",
            "expected_train_samples": EXPECTED_TRAIN_SAMPLES,
            "expected_calibration_samples": EXPECTED_CALIBRATION_SAMPLES,
            "expected_fit_samples": EXPECTED_FIT_SAMPLES,
            "expected_organs": list(CANONICAL_ORGANS),
            "axis_definitions_sha256": "d" * 64,
            "development_expression_parquet_sha256": "1" * 64,
            "development_expression_metadata_sha256": "2" * 64,
            "development_extracted_manifest_sha256": "3" * 64,
            "development_fit_manifest_sha256": development_fit_manifest_sha256,
            "development_firewall_report_sha256": "4" * 64,
            "development_data_full_sha256s_sha256": "5" * 64,
        },
        "prior_evidence": {
            "k45_evaluation_report_sha256": sha256_file(k45_report_path),
            "decision_branch": "k4_robust",
            "selected_candidate": "k4_epe",
        },
        "partitions": {
            "axes": list(FINAL_AXES),
            "random_partition_seeds": list(RANDOM_SEEDS),
            "active_organs": list(ACTIVE_ORGANS),
            "organ_label_order": list(ACTIVE_ORGANS),
            "fallback": {"organ": "adipose", "label": -1, "dispatch": "pooled"},
            "random_assignment_policy": RANDOM_ASSIGNMENT_POLICY,
            "pooled_adapter_label": 0,
        },
        "firewall": {
            "test_access_allowed": False,
            "test_cache_allowed": False,
            "internal_efficacy_scoring_allowed": False,
        },
    }


def _expected_output_hash(frame: pd.DataFrame, path: Path) -> str:
    output = frame[
        ["sample_id", "utility_split", "split", "organ", "series_group_id"]
    ].copy()
    output.insert(2, "fit_role", FIT_ROLE)
    output.insert(4, "balanced_train", True)
    output["organ_k4_final"] = frame["organ_k4_epe"].to_numpy(dtype=np.int64)
    for source_axis, final_axis in zip(SOURCE_RANDOM_AXES, FINAL_RANDOM_AXES):
        output[final_axis] = frame[source_axis].to_numpy(dtype=np.int64)
    output["pooled_adapter"] = np.zeros(len(output), dtype=np.int64)
    output = output[
        [
            "sample_id",
            "utility_split",
            "fit_role",
            "split",
            "balanced_train",
            "organ",
            "series_group_id",
            *FINAL_AXES,
        ]
    ]
    output.to_parquet(path, index=False)
    return sha256_file(path)


def _fixture(tmp_path: Path, *, selected_candidate: str = "k4_epe") -> dict[str, Path]:
    frame = _source_frame()
    manifest_path = tmp_path / "k45_train_cal_partitions.parquet"
    frame.to_parquet(manifest_path, index=False)
    source_report_path = tmp_path / "k45_partition_report.json"
    _write_json(source_report_path, _source_report(frame, manifest_path))
    k45_report_path = tmp_path / "k45_evaluation_report.json"
    _write_json(
        k45_report_path,
        _k45_evaluation_report(
            manifest_path,
            source_report_path,
            selected_candidate=selected_candidate,
        ),
    )
    protocol_path = tmp_path / "final_protocol.json"
    expected_hash = _expected_output_hash(frame, tmp_path / "expected_output.parquet")
    _write_json(
        protocol_path,
        _final_protocol(
            manifest_path,
            source_report_path,
            k45_report_path,
            expected_hash,
        ),
    )
    return {
        "manifest": manifest_path,
        "source_report": source_report_path,
        "k45_report": k45_report_path,
        "protocol": protocol_path,
    }


def _args(fixture: dict[str, Path], output_dir: Path) -> SimpleNamespace:
    return SimpleNamespace(
        protocol=str(fixture["protocol"]),
        source_partition_manifest=str(fixture["manifest"]),
        source_partition_report=str(fixture["source_report"]),
        k45_evaluation_report=str(fixture["k45_report"]),
        output_dir=str(output_dir),
    )


def _rebind_all(fixture: dict[str, Path]) -> None:
    frame = pd.read_parquet(fixture["manifest"])
    _write_json(
        fixture["source_report"],
        _source_report(frame, fixture["manifest"]),
    )
    old_k45 = json.loads(fixture["k45_report"].read_text())
    selected = old_k45["decision"]["selected_candidate_for_future_freeze"]
    _write_json(
        fixture["k45_report"],
        _k45_evaluation_report(
            fixture["manifest"],
            fixture["source_report"],
            selected_candidate=selected,
        ),
    )
    _write_json(
        fixture["protocol"],
        _final_protocol(
            fixture["manifest"],
            fixture["source_report"],
            fixture["k45_report"],
            _expected_output_hash(
                frame, fixture["protocol"].with_name("expected_output.parquet")
            ),
        ),
    )


def test_build_preserves_all_rows_provenance_and_exact_k45_random_assignments(tmp_path):
    fixture = _fixture(tmp_path)
    output_dir = tmp_path / "output"

    report = build(_args(fixture, output_dir))

    source = pd.read_parquet(fixture["manifest"])
    output = pd.read_parquet(output_dir / OUTPUT_FILENAME)
    assert len(output) == EXPECTED_FIT_SAMPLES
    assert output["sample_id"].tolist() == source["sample_id"].tolist()
    assert output["utility_split"].tolist() == source["utility_split"].tolist()
    assert output["split"].tolist() == source["split"].tolist()
    assert output["balanced_train"].eq(True).all()
    assert set(output["fit_role"]) == {FIT_ROLE}
    np.testing.assert_array_equal(output["organ_k4_final"], source["organ_k4_epe"])
    for source_axis, final_axis in zip(SOURCE_RANDOM_AXES, FINAL_RANDOM_AXES):
        np.testing.assert_array_equal(output[final_axis], source[source_axis])
        assert report["axes"][final_axis]["assignments_rebuilt"] is False
        assert report["axes"][final_axis]["assignments_reused_exactly"] is True
        assert output.groupby("series_group_id")[final_axis].nunique().max() == 1
    assert set(output.loc[output["organ"].eq("adipose"), "organ_k4_final"]) == {-1}
    assert set(output.loc[~output["organ"].eq("adipose"), "organ_k4_final"]) == {
        0,
        1,
        2,
        3,
    }
    assert set(output["pooled_adapter"]) == {0}
    assert report["counts"] == {
        "fit": EXPECTED_FIT_SAMPLES,
        "source_train": 1815,
        "source_calibration": 842,
        "by_organ": {
            organ: TRAIN_COUNTS[organ] + CALIBRATION_COUNTS[organ]
            for organ in TRAIN_COUNTS
        },
    }
    assert report["internal_efficacy_scoring"] is False
    assert report["test_accessed"] is False
    assert report["hashes"]["development_fit_manifest_sha256"] == sha256_file(
        output_dir / OUTPUT_FILENAME
    )
    assert report["hashes"]["partition_manifest_sha256"] == sha256_file(
        output_dir / OUTPUT_FILENAME
    )
    assert (output_dir / "partition_report.json").is_file()
    assert (output_dir / "COMPLETE").read_text() == "complete\n"
    assert not list(output_dir.glob("*.tmp"))


def test_build_is_deterministic_without_repartitioning_controls(tmp_path):
    fixture = _fixture(tmp_path)
    first = build(_args(fixture, tmp_path / "first"))
    second = build(_args(fixture, tmp_path / "second"))

    pd.testing.assert_frame_equal(
        pd.read_parquet(tmp_path / "first" / OUTPUT_FILENAME),
        pd.read_parquet(tmp_path / "second" / OUTPUT_FILENAME),
    )
    assert (
        first["hashes"]["development_fit_manifest_sha256"]
        == second["hashes"]["development_fit_manifest_sha256"]
    )
    for axis in FINAL_AXES:
        assert (
            first["hashes"][f"{axis}_assignment_sha256"]
            == second["hashes"][f"{axis}_assignment_sha256"]
        )


@pytest.mark.parametrize(
    ("section", "key", "value", "message"),
    [
        ("evidence_label", "internal_efficacy_scoring", True, "evidence label"),
        ("data", "expected_fit_samples", 2656, "2,657-row"),
        ("prior_evidence", "selected_candidate", "k5", "K4-EPE decision"),
        ("firewall", "test_access_allowed", True, "firewalls"),
    ],
)
def test_protocol_contract_fails_closed(tmp_path, section, key, value, message):
    fixture = _fixture(tmp_path)
    protocol = json.loads(fixture["protocol"].read_text())
    protocol[section][key] = value
    _write_json(fixture["protocol"], protocol)

    with pytest.raises(ValueError, match=message):
        build(_args(fixture, tmp_path / "output"))


def test_source_manifest_tampering_fails_its_protocol_hash(tmp_path):
    fixture = _fixture(tmp_path)
    frame = pd.read_parquet(fixture["manifest"])
    frame.loc[0, "sample_id"] = "tampered-sample"
    frame.to_parquet(fixture["manifest"], index=False)

    with pytest.raises(ValueError, match="manifest hash differs from protocol"):
        build(_args(fixture, tmp_path / "output"))


def test_k45_decision_content_fails_even_when_its_new_hash_is_protocol_bound(tmp_path):
    fixture = _fixture(tmp_path, selected_candidate="k5")

    with pytest.raises(ValueError, match="decision differs"):
        build(_args(fixture, tmp_path / "output"))


def test_k45_cross_hash_mismatch_fails_even_when_report_hash_is_protocol_bound(tmp_path):
    fixture = _fixture(tmp_path)
    k45 = json.loads(fixture["k45_report"].read_text())
    k45["hashes"]["partition_manifest_sha256"] = "b" * 64
    _write_json(fixture["k45_report"], k45)
    protocol = json.loads(fixture["protocol"].read_text())
    protocol["prior_evidence"]["k45_evaluation_report_sha256"] = sha256_file(
        fixture["k45_report"]
    )
    _write_json(fixture["protocol"], protocol)

    with pytest.raises(ValueError, match="different partition manifest"):
        build(_args(fixture, tmp_path / "output"))


def test_rebound_random_assignment_still_fails_if_it_splits_a_connected_study(tmp_path):
    fixture = _fixture(tmp_path)
    frame = pd.read_parquet(fixture["manifest"])
    active_group = frame.loc[frame["organ"].eq("brain"), "series_group_id"].iloc[0]
    group_rows = frame.index[frame["series_group_id"].eq(active_group)].tolist()
    assert len(group_rows) > 1
    old_label = int(frame.loc[group_rows[0], SOURCE_RANDOM_AXES[0]])
    frame.loc[group_rows[0], SOURCE_RANDOM_AXES[0]] = (old_label + 1) % 4
    frame.to_parquet(fixture["manifest"], index=False)
    _rebind_all(fixture)

    with pytest.raises(ValueError, match="splits a connected study"):
        build(_args(fixture, tmp_path / "output"))


def test_rejects_nonempty_output_directory_before_overwrite(tmp_path):
    fixture = _fixture(tmp_path)
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "keep.txt").write_text("user data\n")

    with pytest.raises(FileExistsError, match="not empty"):
        build(_args(fixture, output_dir))
    assert (output_dir / "keep.txt").read_text() == "user data\n"
