#!/usr/bin/env bash
# Build immutable, train/calibration-only partitions for genuine K4/K5 retraining.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-/home/exouser/moe-env/bin/python3}"
PROTOCOL="${PROTOCOL:-artifacts/stage1_organ_k45_retraining/protocol.json}"
PRIOR_ROOT="${PRIOR_ROOT:-/media/volume/moe-reboot/results/stage1_organ_k_confirmation_53ec6c4}"
SOURCE_PARTITIONS="${SOURCE_PARTITIONS:-$PRIOR_ROOT/partitions/train_cal_partitions.parquet}"
SOURCE_PARTITION_REPORT="${SOURCE_PARTITION_REPORT:-$PRIOR_ROOT/partitions/partition_report.json}"
TRACK_B_REPORT="${TRACK_B_REPORT:-$PRIOR_ROOT/track_b_k_search/report.json}"
OUTPUT_ROOT="${OUTPUT_ROOT:?set OUTPUT_ROOT to the persistent experiment root}"
PARTITION_ROOT="${PARTITION_ROOT:-$OUTPUT_ROOT/partitions}"
PREFLIGHT_ONLY="${PREFLIGHT_ONLY:-0}"

EXPECTED_SOURCE_PARTITIONS_SHA256=43f1ca70c6c0aa8033c9f826b6f24be5b7db9e45ec3943ff784ba7b5bcbdcedd
EXPECTED_SOURCE_REPORT_SHA256=70aab83817b17b06bb4ca50685216f476bb0ed8e2be84b028e133b76b32a39a5
EXPECTED_TRACK_B_REPORT_SHA256=bf890073fdf055e79f0ef86a0351ae6ef43992d9b069a68d36a0bb528aa818bc

mkdir -p "$OUTPUT_ROOT"
STATUS="$OUTPUT_ROOT/PREPARE_STATUS"
LOCK="$OUTPUT_ROOT/prepare.lock"
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
  "$SOURCE_PARTITIONS" \
  "$SOURCE_PARTITION_REPORT" \
  "$TRACK_B_REPORT" \
  evaluation/build_organ_k45_retraining_partitions.py; do
  require_file "$path"
done
[[ "$(file_sha256 "$SOURCE_PARTITIONS")" == "$EXPECTED_SOURCE_PARTITIONS_SHA256" ]] || fail source_partitions_hash
[[ "$(file_sha256 "$SOURCE_PARTITION_REPORT")" == "$EXPECTED_SOURCE_REPORT_SHA256" ]] || fail source_partition_report_hash
[[ "$(file_sha256 "$TRACK_B_REPORT")" == "$EXPECTED_TRACK_B_REPORT_SHA256" ]] || fail track_b_report_hash

"$PYTHON_BIN" -m py_compile evaluation/build_organ_k45_retraining_partitions.py || fail python_compile
"$PYTHON_BIN" -c \
  'import json,sys; p=json.load(open(sys.argv[1])); assert p["authorization"]["requested_by_user"] is True; assert p["evidence_label"]["development_only"] is True and p["evidence_label"]["independent_confirmation"] is False; assert p["prior_evidence"]["frozen_selection"]["k4_specialists"] == ["brain","skin","skeletal_muscle","liver"]; assert p["training"]["training_seeds"] == [17,42,101]; assert p["firewall"]["test_access_allowed"] is False and p["firewall"]["test_cache_allowed"] is False and p["firewall"]["automatic_external_test_authorization"] is False' \
  "$PROTOCOL" || fail protocol_contract

if [[ "$PREFLIGHT_ONLY" == "1" ]]; then
  echo "ORGAN_K45_PREPARE_PREFLIGHT_OK"
  echo "partition_root=$PARTITION_ROOT"
  FINAL_STATUS_WRITTEN=1
  exit 0
fi

[[ ! -e "$PARTITION_ROOT" ]] || fail "partition_output_exists=$PARTITION_ROOT"
set_status "RUNNING phase=build_train_cal_partitions"
"$PYTHON_BIN" evaluation/build_organ_k45_retraining_partitions.py \
  --protocol "$PROTOCOL" \
  --source-partition-manifest "$SOURCE_PARTITIONS" \
  --source-partition-report "$SOURCE_PARTITION_REPORT" \
  --track-b-report "$TRACK_B_REPORT" \
  --output-dir "$PARTITION_ROOT" \
  > "$OUTPUT_ROOT/prepare_partitions.log" 2>&1 \
  || fail build_partitions

PARTITION_MANIFEST="$PARTITION_ROOT/train_cal_partitions.parquet"
PARTITION_REPORT="$PARTITION_ROOT/partition_report.json"
for path in "$PARTITION_ROOT/COMPLETE" "$PARTITION_MANIFEST" "$PARTITION_REPORT"; do
  [[ -e "$path" ]] || fail "missing_partition_artifact=$path"
done
"$PYTHON_BIN" -c \
  'import hashlib,json,sys; r=json.load(open(sys.argv[1])); digest=lambda p: hashlib.sha256(open(p,"rb").read()).hexdigest(); expected=["organ_k5","organ_k4_epe","organ_k4_total_active","random_group_k5_p17","random_group_k5_p42","random_group_k5_p101","random_group_k4_epe_p17","random_group_k4_epe_p42","random_group_k4_epe_p101","random_group_k4_total_active_p17","random_group_k4_total_active_p42","random_group_k4_total_active_p101"]; assert r["status"]=="complete" and r["development_only"] is True and r["test_accessed"] is False and r["test_assignment_metadata_accessed"] is False; assert r["config"]["axes"]==expected; assert r["hashes"]["partition_manifest_sha256"]==digest(sys.argv[2]); assert r["hashes"]["protocol_sha256"]==digest(sys.argv[3]); assert all(r["axes"][axis]["k"] in (4,5) for axis in expected)' \
  "$PARTITION_REPORT" "$PARTITION_MANIFEST" "$PROTOCOL" \
  || fail partition_artifact_contract

touch "$OUTPUT_ROOT/PREPARE_COMPLETE"
set_status COMPLETE
FINAL_STATUS_WRITTEN=1
cat "$PARTITION_REPORT"
