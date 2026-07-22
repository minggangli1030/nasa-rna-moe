#!/usr/bin/env python3
"""Build the metadata-only development-fit manifest for the frozen K4 refit.

The builder merges the already frozen K45 train and calibration fitting rows
without changing their order.  It renames, but never rebuilds, the three K45
equal-per-expert random controls.  No expression, reconstruction target,
prediction, or efficacy score is accepted or computed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = ROOT / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from train_manifest import sha256_file, sha256_json, sha256_lines  # noqa: E402


CANONICAL_ORGANS = (
    "adipose",
    "brain",
    "liver",
    "skeletal_muscle",
    "skin",
)
ACTIVE_ORGANS = (
    "brain",
    "liver",
    "skeletal_muscle",
    "skin",
)
ORGAN_TO_FINAL_LABEL = {organ: index for index, organ in enumerate(ACTIVE_ORGANS)}
RANDOM_SEEDS = (17, 42, 101)
SOURCE_RANDOM_AXES = tuple(
    f"random_group_k4_epe_p{seed}" for seed in RANDOM_SEEDS
)
FINAL_RANDOM_AXES = tuple(
    f"random_group_k4_final_p{seed}" for seed in RANDOM_SEEDS
)
FINAL_AXES = ("organ_k4_final", *FINAL_RANDOM_AXES, "pooled_adapter")
SOURCE_TO_FINAL_RANDOM_AXIS = dict(zip(SOURCE_RANDOM_AXES, FINAL_RANDOM_AXES))
EXPECTED_FIT_SAMPLES = 2657
EXPECTED_TRAIN_SAMPLES = 1815
EXPECTED_CALIBRATION_SAMPLES = 842
FIT_ROLE = "development_fit"
OUTPUT_FILENAME = "development_fit_manifest.parquet"
REPORT_FILENAME = "partition_report.json"
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
RANDOM_ASSIGNMENT_POLICY = (
    "Reuse the exact K45 K4-EPE connected-study-atomic train and calibration "
    "assignments; merge without repartitioning or relabeling."
)

REQUIRED_SOURCE_COLUMNS = {
    "sample_id",
    "utility_split",
    "split",
    "organ",
    "series_group_id",
    "organ_k4_epe",
    *SOURCE_RANDOM_AXES,
}


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _atomic_parquet(frame: pd.DataFrame, path: Path) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_parquet(temporary, index=False)
    os.replace(temporary, path)


def _atomic_text(path: Path, value: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value)
    os.replace(temporary, path)


def _load_json(path: Path, role: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not load {role}: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{role} must contain a JSON object")
    return value


def _require_hash(value: Any, role: str) -> str:
    if not isinstance(value, str) or HASH_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{role} is not a lowercase SHA-256 digest")
    return value


def _assignment_hash(frame: pd.DataFrame, axis: str) -> str:
    return sha256_lines(
        f"{row.sample_id}\t{getattr(row, axis)}"
        for row in frame[["sample_id", axis]].itertuples(index=False)
    )


def _counts(values: Iterable[str], names: tuple[str, ...]) -> dict[str, int]:
    observed = pd.Series(list(values), dtype="object").value_counts().to_dict()
    return {name: int(observed.get(name, 0)) for name in names}


def _require_protocol_contract(protocol: dict[str, Any]) -> None:
    evidence = protocol.get("evidence_label", {})
    if (
        evidence.get("label") != "final_refit_for_external_confirmation"
        or evidence.get("development_only") is not True
        or evidence.get("internally_confirmatory") is not False
        or evidence.get("internal_efficacy_scoring") is not False
    ):
        raise ValueError("protocol evidence label does not freeze a nonconfirmatory refit")

    data = protocol.get("data", {})
    if (
        data.get("fitting_pool") != "balanced_train_plus_calibration"
        or data.get("expected_train_samples") != EXPECTED_TRAIN_SAMPLES
        or data.get("expected_calibration_samples")
        != EXPECTED_CALIBRATION_SAMPLES
        or data.get("expected_fit_samples") != EXPECTED_FIT_SAMPLES
        or data.get("expected_organs") != list(CANONICAL_ORGANS)
    ):
        raise ValueError("protocol does not freeze the 2,657-row development fitting pool")
    _require_hash(
        data.get("source_k45_partition_manifest_sha256"),
        "protocol source K45 partition manifest hash",
    )
    _require_hash(
        data.get("source_k45_partition_report_sha256"),
        "protocol source K45 partition report hash",
    )
    _require_hash(
        data.get("axis_definitions_sha256"),
        "protocol axis definitions hash",
    )
    for key in (
        "development_expression_parquet_sha256",
        "development_expression_metadata_sha256",
        "development_extracted_manifest_sha256",
        "development_fit_manifest_sha256",
        "development_firewall_report_sha256",
        "development_data_full_sha256s_sha256",
    ):
        _require_hash(data.get(key), f"protocol {key}")

    prior = protocol.get("prior_evidence", {})
    _require_hash(
        prior.get("k45_evaluation_report_sha256"),
        "protocol K45 evaluation report hash",
    )
    if (
        prior.get("decision_branch") != "k4_robust"
        or prior.get("selected_candidate") != "k4_epe"
    ):
        raise ValueError("protocol does not freeze the supported K4-EPE decision")

    partitions = protocol.get("partitions", {})
    if partitions.get("axes") != list(FINAL_AXES):
        raise ValueError("protocol final-refit axes differ from the frozen axis order")
    if partitions.get("random_partition_seeds") != list(RANDOM_SEEDS):
        raise ValueError("protocol random partition seeds differ from 17/42/101")
    if partitions.get("active_organs") != list(ACTIVE_ORGANS):
        raise ValueError("protocol active organs differ from the frozen K4 order")
    if partitions.get("organ_label_order") != list(ACTIVE_ORGANS):
        raise ValueError("protocol organ label order differs from the frozen K4 order")
    fallback = partitions.get("fallback", {})
    if fallback != {"organ": "adipose", "label": -1, "dispatch": "pooled"}:
        raise ValueError("protocol fallback is not adipose label -1 to pooled dispatch")
    if (
        partitions.get("random_assignment_policy") != RANDOM_ASSIGNMENT_POLICY
        or partitions.get("pooled_adapter_label") != 0
    ):
        raise ValueError("protocol does not freeze exact K45 control reuse")

    firewall = protocol.get("firewall", {})
    if (
        firewall.get("test_access_allowed") is not False
        or firewall.get("test_cache_allowed") is not False
        or firewall.get("internal_efficacy_scoring_allowed") is not False
    ):
        raise ValueError("protocol does not close the test and efficacy-score firewalls")


def _validate_evidence(
    *,
    protocol: dict[str, Any],
    source_manifest_path: Path,
    source_report_path: Path,
    source_report: dict[str, Any],
    k45_report_path: Path,
    k45_report: dict[str, Any],
) -> None:
    data = protocol["data"]
    prior = protocol["prior_evidence"]
    source_manifest_hash = sha256_file(source_manifest_path)
    source_report_hash = sha256_file(source_report_path)
    k45_report_hash = sha256_file(k45_report_path)
    if source_manifest_hash != data["source_k45_partition_manifest_sha256"]:
        raise ValueError("source K45 partition manifest hash differs from protocol")
    if source_report_hash != data["source_k45_partition_report_sha256"]:
        raise ValueError("source K45 partition report hash differs from protocol")
    if k45_report_hash != prior["k45_evaluation_report_sha256"]:
        raise ValueError("K45 evaluation report hash differs from protocol")

    source_hashes = source_report.get("hashes", {})
    if (
        source_report.get("status") != "complete"
        or source_report.get("development_only") is not True
        or source_report.get("test_accessed") is not False
        or source_report.get("test_assignment_metadata_accessed") is not False
    ):
        raise ValueError("source K45 partition report violates the development firewall")
    if source_hashes.get("partition_manifest_sha256") != source_manifest_hash:
        raise ValueError("source K45 partition report does not bind its manifest")
    source_protocol_hash = _require_hash(
        source_hashes.get("protocol_sha256"),
        "source K45 protocol hash",
    )
    source_axes = source_report.get("config", {}).get("axes", [])
    required_axes = {"organ_k4_epe", *SOURCE_RANDOM_AXES}
    if not required_axes.issubset(set(source_axes)):
        raise ValueError("source K45 partition report lacks the frozen EPE axes")

    decision = k45_report.get("decision", {})
    if (
        k45_report.get("status") != "complete"
        or k45_report.get("development_only") is not True
        or k45_report.get("test_accessed") is not False
        or k45_report.get("independent_confirmation") is not False
        or k45_report.get("external_confirmation_required") is not True
    ):
        raise ValueError("K45 evidence is not complete development-only evidence")
    if (
        decision.get("decision_branch") != prior["decision_branch"]
        or decision.get("selected_candidate_for_future_freeze")
        != prior["selected_candidate"]
        or decision.get("development_only") is not True
        or decision.get("test_accessed") is not False
        or decision.get("automatic_external_test_authorization") is not False
    ):
        raise ValueError("K45 decision differs from the final-refit protocol")
    expected_technical_gates = {
        "development_firewall",
        "alignment",
        "router_target_hidden",
        "shared_epe_experts_bitwise_equal",
    }
    technical_gates = k45_report.get("technical_gates", {})
    if set(technical_gates) != expected_technical_gates or not all(
        value is True for value in technical_gates.values()
    ):
        raise ValueError("K45 technical gates are incomplete or did not all pass")
    k4_support = k45_report.get("support_gate_details", {}).get("k4_epe", {})
    expected_support_gates = {
        "blind_vs_pooled",
        "true_vs_pooled",
        "true_vs_every_random",
        "exposure",
    }
    if set(k4_support) != expected_support_gates or not all(
        value is True for value in k4_support.values()
    ):
        raise ValueError("K45 K4-EPE support gates are incomplete or did not all pass")
    if k45_report.get("noninferiority", {}).get("gates", {}).get("k4_epe") is not True:
        raise ValueError("K45 K4-EPE noninferiority gate did not pass")

    evidence_hashes = k45_report.get("hashes", {})
    if evidence_hashes.get("partition_manifest_sha256") != source_manifest_hash:
        raise ValueError("K45 evidence used a different partition manifest")
    if evidence_hashes.get("partition_report_sha256") != source_report_hash:
        raise ValueError("K45 evidence used a different partition report")
    if evidence_hashes.get("protocol_sha256") != source_protocol_hash:
        raise ValueError("K45 evidence and partition report used different protocols")


def _validated_integer_labels(frame: pd.DataFrame, axis: str) -> np.ndarray:
    numeric = pd.to_numeric(frame[axis], errors="raise").to_numpy(dtype=np.float64)
    if not np.isfinite(numeric).all() or not np.equal(numeric, np.floor(numeric)).all():
        raise ValueError(f"source axis {axis!r} contains noninteger labels")
    labels = numeric.astype(np.int64)
    if np.any(labels < -1) or np.any(labels > 3):
        raise ValueError(f"source axis {axis!r} contains labels outside -1..3")
    return labels


def _validate_source_frame(
    frame: pd.DataFrame,
    *,
    protocol: dict[str, Any],
    source_report: dict[str, Any],
) -> pd.DataFrame:
    missing = sorted(REQUIRED_SOURCE_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"source K45 partition manifest lacks columns: {missing}")
    frame = frame.copy()
    for column in ("sample_id", "utility_split", "split", "organ", "series_group_id"):
        if frame[column].isna().any() or not frame[column].map(
            lambda value: isinstance(value, str) and bool(value)
        ).all():
            raise ValueError(f"source column {column!r} must contain nonempty strings")
    if frame["sample_id"].duplicated().any():
        raise ValueError("source K45 partition manifest contains duplicate sample IDs")
    if len(frame) != protocol["data"]["expected_fit_samples"]:
        raise ValueError("source K45 fitting row count differs from the frozen protocol")
    if set(frame["utility_split"]) != {"train", "calibration"}:
        raise ValueError("source K45 partition is not exactly train plus calibration")
    train_mask = frame["utility_split"].eq("train").to_numpy()
    first_calibration = int(train_mask.sum())
    if (
        first_calibration != protocol["data"]["expected_train_samples"]
        or len(frame) - first_calibration
        != protocol["data"]["expected_calibration_samples"]
    ):
        raise ValueError("source K45 train/calibration counts differ from protocol")
    source_counts = source_report.get("counts", {})
    if (
        source_counts.get("train") != first_calibration
        or source_counts.get("calibration") != len(frame) - first_calibration
    ):
        raise ValueError("source K45 partition report counts do not match its manifest")
    if not train_mask[:first_calibration].all() or train_mask[first_calibration:].any():
        raise ValueError("source K45 rows are not ordered train then calibration")
    if "test" in set(frame["split"]):
        raise ValueError("source K45 partition contains forbidden test rows")
    if set(frame["organ"]) != set(CANONICAL_ORGANS):
        raise ValueError("source organs differ from the frozen five-organ family")

    group_organs = frame.groupby("series_group_id", sort=False)["organ"].nunique()
    if (group_organs != 1).any():
        raise ValueError("a connected study spans organ and pooled-fallback roles")
    group_provenance = frame.groupby("series_group_id", sort=False)[
        "utility_split"
    ].nunique()
    if (group_provenance != 1).any():
        raise ValueError("a connected study crosses frozen train/calibration provenance")

    expected_organ_labels = (
        frame["organ"].map(ORGAN_TO_FINAL_LABEL).fillna(-1).to_numpy(dtype=np.int64)
    )
    source_organ_labels = _validated_integer_labels(frame, "organ_k4_epe")
    if not np.array_equal(source_organ_labels, expected_organ_labels):
        raise ValueError("source organ_k4_epe labels differ from frozen organ semantics")

    source_hashes = source_report.get("hashes", {})
    for axis in ("organ_k4_epe", *SOURCE_RANDOM_AXES):
        labels = _validated_integer_labels(frame, axis)
        fallback = frame["organ"].eq("adipose").to_numpy()
        if not np.all(labels[fallback] == -1) or np.any(labels[~fallback] < 0):
            raise ValueError(f"source axis {axis!r} violates the adipose fallback contract")
        if not np.array_equal(np.unique(labels[~fallback]), np.arange(4)):
            raise ValueError(f"source axis {axis!r} does not cover active labels 0..3")
        labeled = pd.DataFrame({
            "series_group_id": frame["series_group_id"],
            "label": labels,
        })
        if labeled.groupby("series_group_id", sort=False)["label"].nunique().max() != 1:
            raise ValueError(f"source axis {axis!r} splits a connected study")
        expected_hash = _require_hash(
            source_hashes.get(f"{axis}_assignment_sha256"),
            f"source K45 {axis} assignment hash",
        )
        if _assignment_hash(frame.assign(**{axis: labels}), axis) != expected_hash:
            raise ValueError(f"source axis {axis!r} differs from its frozen assignment hash")
        frame[axis] = labels
    return frame


def build(args: argparse.Namespace) -> dict[str, Any]:
    protocol_path = Path(args.protocol)
    source_manifest_path = Path(args.source_partition_manifest)
    source_report_path = Path(args.source_partition_report)
    k45_report_path = Path(args.k45_evaluation_report)
    for path in (
        protocol_path,
        source_manifest_path,
        source_report_path,
        k45_report_path,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)

    protocol = _load_json(protocol_path, "final-refit protocol")
    source_report = _load_json(source_report_path, "source K45 partition report")
    k45_report = _load_json(k45_report_path, "K45 evaluation report")
    _require_protocol_contract(protocol)
    _validate_evidence(
        protocol=protocol,
        source_manifest_path=source_manifest_path,
        source_report_path=source_report_path,
        source_report=source_report,
        k45_report_path=k45_report_path,
        k45_report=k45_report,
    )
    source = _validate_source_frame(
        pd.read_parquet(source_manifest_path),
        protocol=protocol,
        source_report=source_report,
    )

    output = source[
        ["sample_id", "utility_split", "split", "organ", "series_group_id"]
    ].copy()
    output.insert(2, "fit_role", FIT_ROLE)
    output.insert(4, "balanced_train", True)
    output["organ_k4_final"] = source["organ_k4_epe"].to_numpy(dtype=np.int64)
    for source_axis, final_axis in SOURCE_TO_FINAL_RANDOM_AXIS.items():
        output[final_axis] = source[source_axis].to_numpy(dtype=np.int64)
    output["pooled_adapter"] = np.zeros(len(output), dtype=np.int64)
    expected_columns = [
        "sample_id",
        "utility_split",
        "fit_role",
        "split",
        "balanced_train",
        "organ",
        "series_group_id",
        *FINAL_AXES,
    ]
    output = output[expected_columns]
    if output["sample_id"].tolist() != source["sample_id"].tolist():
        raise AssertionError("final-refit row order changed during construction")
    for source_axis, final_axis in SOURCE_TO_FINAL_RANDOM_AXIS.items():
        if not np.array_equal(output[final_axis], source[source_axis]):
            raise AssertionError(f"final axis {final_axis!r} was not copied exactly")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output_dir}")
    output_path = output_dir / OUTPUT_FILENAME
    _atomic_parquet(output, output_path)
    if sha256_file(output_path) != protocol["data"]["development_fit_manifest_sha256"]:
        raise ValueError("development-fit manifest hash differs from the frozen protocol")

    config = {
        "fit_role": FIT_ROLE,
        "fitting_pool": "balanced_train_plus_calibration",
        "axes": list(FINAL_AXES),
        "active_organs": list(ACTIVE_ORGANS),
        "fallback": {"organ": "adipose", "label": -1, "dispatch": "pooled"},
        "random_partition_seeds": list(RANDOM_SEEDS),
        "random_control_provenance": {
            final_axis: {
                "source_axis": source_axis,
                "operation": "exact row-wise copy and rename; no reassignment",
            }
            for source_axis, final_axis in SOURCE_TO_FINAL_RANDOM_AXIS.items()
        },
        "internal_efficacy_scoring": False,
        "test_access_allowed": False,
    }
    hashes = {
        "protocol_sha256": sha256_file(protocol_path),
        "source_k45_partition_manifest_sha256": sha256_file(source_manifest_path),
        "source_k45_partition_report_sha256": sha256_file(source_report_path),
        "k45_evaluation_report_sha256": sha256_file(k45_report_path),
        "development_fit_manifest_sha256": sha256_file(output_path),
        "partition_manifest_sha256": sha256_file(output_path),
        "axis_definitions_sha256": protocol["data"]["axis_definitions_sha256"],
        "ordered_sample_ids_sha256": sha256_lines(output["sample_id"].tolist()),
        "utility_split_provenance_sha256": _assignment_hash(output, "utility_split"),
        "fit_role_assignment_sha256": _assignment_hash(output, "fit_role"),
        "organ_assignment_sha256": _assignment_hash(output, "organ"),
        "resolved_config_sha256": sha256_json(config),
    }
    for axis in FINAL_AXES:
        hashes[f"{axis}_assignment_sha256"] = _assignment_hash(output, axis)
    for source_axis, final_axis in SOURCE_TO_FINAL_RANDOM_AXIS.items():
        source_hash = _assignment_hash(source, source_axis)
        if hashes[f"{final_axis}_assignment_sha256"] != source_hash:
            raise AssertionError(f"renamed axis {final_axis!r} changed assignments")
        hashes[f"source_{source_axis}_assignment_sha256"] = source_hash

    report = {
        "schema_version": 1,
        "status": "complete",
        "research_stage": "stage1_k4_final_refit",
        "artifact_role": "development_fit_manifest",
        "evidence_label": "final_refit_for_external_confirmation",
        "development_only": True,
        "internally_confirmatory": False,
        "internal_efficacy_scoring": False,
        "test_accessed": False,
        "test_cache_accessed": False,
        "counts": {
            "fit": int(len(output)),
            "source_train": int(output["utility_split"].eq("train").sum()),
            "source_calibration": int(
                output["utility_split"].eq("calibration").sum()
            ),
            "by_organ": _counts(output["organ"], CANONICAL_ORGANS),
        },
        "axes": {
            "organ_k4_final": {
                "kind": "frozen_organ_identity",
                "labels": ORGAN_TO_FINAL_LABEL,
                "fallback": {"organ": "adipose", "label": -1},
            },
            **{
                final_axis: {
                    "kind": "frozen_connected_study_atomic_random_k4_control",
                    "partition_seed": seed,
                    "source_axis": source_axis,
                    "assignments_rebuilt": False,
                    "assignments_reused_exactly": True,
                    "fallback": {"organ": "adipose", "label": -1},
                }
                for seed, source_axis, final_axis in zip(
                    RANDOM_SEEDS, SOURCE_RANDOM_AXES, FINAL_RANDOM_AXES
                )
            },
            "pooled_adapter": {
                "kind": "single_pooled_adapter_control",
                "labels": {"pooled": 0},
            },
        },
        "decision_evidence": {
            "decision_branch": "k4_robust",
            "selected_candidate": "k4_epe",
            "external_confirmation_required": True,
        },
        "config": config,
        "hashes": hashes,
        "artifact": str(output_path.resolve()),
        "guardrails": [
            "the 2,657 source rows remain in their frozen train-then-calibration order",
            "utility_split is provenance only; every row has fit_role=development_fit",
            "K45 equal-per-expert random assignments are copied exactly and never rebuilt",
            "connected studies remain atomic in every specialist and random-control axis",
            "the builder accepts no expression, target, prediction, test, or score input",
            "this refit artifact contains no internal efficacy estimate",
        ],
    }
    _atomic_json(output_dir / REPORT_FILENAME, report)
    _atomic_text(output_dir / "COMPLETE", "complete\n")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--source-partition-manifest", required=True)
    parser.add_argument("--source-partition-report", required=True)
    parser.add_argument("--k45-evaluation-report", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser


def main() -> None:
    report = build(build_parser().parse_args())
    print(json.dumps({
        "status": report["status"],
        "artifact_role": report["artifact_role"],
        "counts": report["counts"],
        "hashes": report["hashes"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
