#!/usr/bin/env bash
# Freeze the matched K5 assignments and calibration-only organ-K routers.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-/home/exouser/moe-env/bin/python3}"
PROTOCOL="${PROTOCOL:-artifacts/stage1_organ_k_confirmation/protocol.json}"
SOURCE_ROOT="${SOURCE_ROOT:-results/stage1_organ_k5_train_20260717T165507Z}"
EXPRESSION_PARQUET="${EXPRESSION_PARQUET:-$SOURCE_ROOT/expression/expression.parquet}"
EXPRESSION_METADATA="${EXPRESSION_METADATA:-$SOURCE_ROOT/expression/extraction_report.json}"
MANIFEST="${MANIFEST:-$SOURCE_ROOT/expression/manifest.parquet}"
UTILITY_AXIS_ROOT="${UTILITY_AXIS_ROOT:-results/stage2_utility_axis_pilot_f8ab3cd/axis}"
UTILITY_PARTITION_REPORT="${UTILITY_PARTITION_REPORT:-$UTILITY_AXIS_ROOT/partition_report.json}"
AXIS_DEFINITIONS="${AXIS_DEFINITIONS:-$UTILITY_AXIS_ROOT/axis_definitions.npz}"
OUTPUT_ROOT="${OUTPUT_ROOT:-results/stage1_organ_k_confirmation}"
PARTITION_ROOT="${PARTITION_ROOT:-$OUTPUT_ROOT/partitions}"
ROUTER_ROOT="${ROUTER_ROOT:-$OUTPUT_ROOT/router}"
ROUTER_SEED="${ROUTER_SEED:-271828}"
MASK_TOKEN="${MASK_TOKEN:--10.0}"
PREFLIGHT_ONLY="${PREFLIGHT_ONLY:-0}"

EXPECTED_EXPRESSION_SHA256=148776bc2d5bbe4a969103de7abab932b7467c804934fc697366ae2c209c0821
EXPECTED_MANIFEST_SHA256=bc4e8e4e36ab0e869fd885197842dc797edad5a08b8093beb21185dbeda7f9cc
EXPECTED_AXIS_DEFINITIONS_SHA256=1d7fba55d00f3fe363932abfba2a0e0d76e70e8dedf71aa46c69e29679b0b7cb
EXPECTED_UTILITY_REPORT_SHA256=62f4b19e0fd111d99f265f8b1bd7beba9b5af7edf8bf35ffdce2ce98d0e33b16

mkdir -p "$OUTPUT_ROOT"
STATUS="${STATUS:-$OUTPUT_ROOT/PREPARE_STATUS}"
LOCK="${LOCK:-$OUTPUT_ROOT/prepare.lock}"
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "ERROR: preparation lock exists: $LOCK" >&2
  exit 1
fi
FINAL_STATUS_WRITTEN=0
cleanup() {
  rc=$?
  if [[ "$rc" -ne 0 && "$FINAL_STATUS_WRITTEN" -eq 0 ]]; then
    printf 'FAILED reason=unexpected_exit_%s %s\n' "$rc" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
  fi
  rmdir "$LOCK" 2>/dev/null || true
  exit "$rc"
}
trap cleanup EXIT

set_status() {
  printf '%s %s\n' "$1" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
}
fail() {
  set_status "FAILED reason=$1"
  FINAL_STATUS_WRITTEN=1
  exit 1
}
require_file() {
  [[ -s "$1" ]] || fail "missing_file=$1"
}
file_sha256() {
  sha256sum "$1" | awk '{print $1}'
}

for path in \
  "$PROTOCOL" \
  "$EXPRESSION_PARQUET" \
  "$EXPRESSION_METADATA" \
  "$MANIFEST" \
  "$UTILITY_PARTITION_REPORT" \
  "$AXIS_DEFINITIONS" \
  evaluation/build_organ_k_confirmation_partitions.py \
  evaluation/freeze_organ_k_router.py; do
  require_file "$path"
done

[[ "$(file_sha256 "$EXPRESSION_PARQUET")" == "$EXPECTED_EXPRESSION_SHA256" ]] || fail expression_hash
[[ "$(file_sha256 "$MANIFEST")" == "$EXPECTED_MANIFEST_SHA256" ]] || fail manifest_hash
[[ "$(file_sha256 "$AXIS_DEFINITIONS")" == "$EXPECTED_AXIS_DEFINITIONS_SHA256" ]] || fail axis_definitions_hash
[[ "$(file_sha256 "$UTILITY_PARTITION_REPORT")" == "$EXPECTED_UTILITY_REPORT_SHA256" ]] || fail utility_partition_report_hash

"$PYTHON_BIN" -m py_compile \
  evaluation/build_organ_k_confirmation_partitions.py \
  evaluation/freeze_organ_k_router.py \
  || fail python_compile
"$PYTHON_BIN" -c \
  'import json,sys; p=json.load(open(sys.argv[1])); b=p["track_b_development_k_search"]; assert p["authorization"]["requested_by_user"] is True; assert p["evidence_label"]["internal_locked_replication"] is True; assert p["evidence_label"]["independent_confirmation"] is False; assert p["expert_training"]["training_seeds"] == [17,42,101]; assert b["candidate_k"] == [1,2,3,4,5]; assert b["test_access_allowed"] is False; assert b["router_policy"] == "common_k5_probability_collapse" and b["strict_outer_inner_router"] is True; assert b["matched_random_subset_family"].startswith("all C(5,K) subsets"); assert p["firewall"]["run_track_a_before_inspecting_track_b"] is True; assert p["firewall"]["track_b_code_must_reject_test"] is True' \
  "$PROTOCOL" \
  || fail protocol_contract
"$PYTHON_BIN" -c \
  'import json,sys; r=json.load(open(sys.argv[1])); assert r["status"] == "complete"; assert r["test_accessed"] is False; assert r["hashes"]["axis_definitions_sha256"] == sys.argv[2]' \
  "$UTILITY_PARTITION_REPORT" "$EXPECTED_AXIS_DEFINITIONS_SHA256" \
  || fail utility_report_contract

if [[ "$PREFLIGHT_ONLY" == "1" ]]; then
  echo "ORGAN_K_CONFIRMATION_PREPARE_PREFLIGHT_OK"
  echo "python=$PYTHON_BIN"
  echo "partition_root=$PARTITION_ROOT"
  echo "router_root=$ROUTER_ROOT"
  FINAL_STATUS_WRITTEN=1
  exit 0
fi

[[ ! -e "$PARTITION_ROOT" ]] || fail "partition_output_exists=$PARTITION_ROOT"
[[ ! -e "$ROUTER_ROOT" ]] || fail "router_output_exists=$ROUTER_ROOT"

set_status "RUNNING phase=freeze_partitions"
"$PYTHON_BIN" evaluation/build_organ_k_confirmation_partitions.py \
  --manifest "$MANIFEST" \
  --utility-partition-report "$UTILITY_PARTITION_REPORT" \
  --utility-axis-definitions "$AXIS_DEFINITIONS" \
  --output-dir "$PARTITION_ROOT" \
  --emit-sealed-test \
  > "$OUTPUT_ROOT/prepare_partitions.log" 2>&1 \
  || fail freeze_partitions

PARTITION_MANIFEST="$PARTITION_ROOT/train_cal_partitions.parquet"
PARTITION_REPORT="$PARTITION_ROOT/partition_report.json"
SEALED_TEST_ASSIGNMENTS="$PARTITION_ROOT/sealed_test_assignments.parquet"
SEALED_TEST_REPORT="$PARTITION_ROOT/sealed_test_report.json"
for path in \
  "$PARTITION_ROOT/COMPLETE" \
  "$PARTITION_MANIFEST" \
  "$PARTITION_REPORT" \
  "$SEALED_TEST_ASSIGNMENTS" \
  "$SEALED_TEST_REPORT"; do
  [[ -e "$path" ]] || fail "missing_partition_artifact=$path"
done
"$PYTHON_BIN" -c \
  'import hashlib,json,sys; report=json.load(open(sys.argv[1])); sealed=json.load(open(sys.argv[2])); digest=lambda p: hashlib.sha256(open(p,"rb").read()).hexdigest(); expected=["organ_k5","random_k5","random_group_k5_p17","random_group_k5_p42","random_group_k5_p101"]; assert report["status"] == "complete" and report["test_accessed"] is False and report["test_expression_accessed"] is False and report["test_targets_accessed"] is False; assert report["sealed_test_assignment_emitted"] is True; assert report["axes"] == expected; assert report["gating_axes"] == ["organ_k5",*expected[2:]] and report["non_gating_diagnostic_axes"] == ["random_k5"]; assert report["hashes"]["partition_manifest_sha256"] == digest(sys.argv[3]); assert report["hashes"]["sealed_test_assignments_sha256"] == digest(sys.argv[4]); assert report["hashes"]["sealed_test_report_sha256"] == digest(sys.argv[2]); assert sealed["status"] == "complete" and sealed["sealed"] is True and sealed["test_accessed"] is False and sealed["test_expression_accessed"] is False and sealed["test_targets_accessed"] is False and sealed["assignment_metadata_materialized"] is True; assert sealed["hashes"]["sealed_test_assignments_sha256"] == digest(sys.argv[4]); assert all(sealed["partitions"][axis]["group_preserving"] is True for axis in expected[2:])' \
  "$PARTITION_REPORT" "$SEALED_TEST_REPORT" "$PARTITION_MANIFEST" "$SEALED_TEST_ASSIGNMENTS" \
  || fail partition_artifact_contract

set_status "RUNNING phase=freeze_calibration_router"
"$PYTHON_BIN" evaluation/freeze_organ_k_router.py \
  --expression-parquet "$EXPRESSION_PARQUET" \
  --expression-metadata "$EXPRESSION_METADATA" \
  --source-manifest "$MANIFEST" \
  --axis-definitions "$AXIS_DEFINITIONS" \
  --partition-manifest "$PARTITION_MANIFEST" \
  --partition-report "$PARTITION_REPORT" \
  --output-dir "$ROUTER_ROOT" \
  --router-seed "$ROUTER_SEED" \
  --mask-token "$MASK_TOKEN" \
  > "$OUTPUT_ROOT/prepare_router.log" 2>&1 \
  || fail freeze_router

ROUTER_ARTIFACT="$ROUTER_ROOT/organ_k_router.npz"
ROUTER_REPORT="$ROUTER_ROOT/router_report.json"
for path in "$ROUTER_ROOT/COMPLETE" "$ROUTER_ARTIFACT" "$ROUTER_REPORT"; do
  [[ -e "$path" ]] || fail "missing_router_artifact=$path"
done
"$PYTHON_BIN" -c \
  'import hashlib,json,sys,numpy as np; r=json.load(open(sys.argv[1])); digest=lambda p: hashlib.sha256(open(p,"rb").read()).hexdigest(); assert r["status"] == "complete" and r["test_accessed"] is False and r["test_features_loaded"] is False and r["train_features_loaded"] is False; assert r["data_access"]["loaded_expression_split"] == "calibration"; assert r["config"]["k_values"] == [1,2,3,4,5] and r["config"]["subset_router_policy"].startswith("fit one common five-organ router"); assert r["crossfit"]["strict_nested_selection"]["enabled"] is True; assert r["exhaustive_subsets"]["n_subsets"] == 31; assert r["hashes"]["router_artifact_sha256"] == digest(sys.argv[2]); assert r["hashes"]["partition_manifest_sha256"] == digest(sys.argv[3]); assert r["hashes"]["partition_report_sha256"] == digest(sys.argv[4]); assert r["hashes"]["axis_definitions_sha256"] == digest(sys.argv[5]); z=np.load(sys.argv[2],allow_pickle=False); assert z["outer_inner_k5_probabilities"].shape[0] == 5 and z["outer_inner_valid_mask"].shape[0] == 5 and z["subset_ids"].shape == (31,)' \
  "$ROUTER_REPORT" "$ROUTER_ARTIFACT" "$PARTITION_MANIFEST" "$PARTITION_REPORT" "$AXIS_DEFINITIONS" \
  || fail router_artifact_contract

touch "$OUTPUT_ROOT/PREPARE_COMPLETE"
set_status COMPLETE
FINAL_STATUS_WRITTEN=1
cat "$ROUTER_REPORT"
