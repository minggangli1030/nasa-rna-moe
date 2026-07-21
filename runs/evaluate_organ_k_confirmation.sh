#!/usr/bin/env bash
# Evaluate immutable Track A first, then unlock the calibration-only K search.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-/home/exouser/moe-env/bin/python3}"
PROTOCOL="${PROTOCOL:-artifacts/stage1_organ_k_confirmation/protocol.json}"
OUTPUT_ROOT="${OUTPUT_ROOT:-results/stage1_organ_k_confirmation}"
PARTITION_ROOT="${PARTITION_ROOT:-$OUTPUT_ROOT/partitions}"
SEALED_TEST_ASSIGNMENTS="${SEALED_TEST_ASSIGNMENTS:-$PARTITION_ROOT/sealed_test_assignments.parquet}"
SEALED_TEST_REPORT="${SEALED_TEST_REPORT:-$PARTITION_ROOT/sealed_test_report.json}"
ROUTER_ROOT="${ROUTER_ROOT:-$OUTPUT_ROOT/router}"
ROUTER_ARTIFACT="${ROUTER_ARTIFACT:-$ROUTER_ROOT/organ_k_router.npz}"
ROUTER_REPORT="${ROUTER_REPORT:-$ROUTER_ROOT/router_report.json}"
PACKED_ROOT="${PACKED_ROOT:-$OUTPUT_ROOT/packed}"
CACHE_ROOT="${CACHE_ROOT:-$OUTPUT_ROOT/test_cache}"
TRACK_A_ROOT="${TRACK_A_ROOT:-$OUTPUT_ROOT/track_a_internal_replication}"
TRACK_B_ROOT="${TRACK_B_ROOT:-$OUTPUT_ROOT/track_b_k_search}"
BOOTSTRAP_REPS="${BOOTSTRAP_REPS:-2000}"
TRACK_A_BOOTSTRAP_SEED="${TRACK_A_BOOTSTRAP_SEED:-424242}"
TRACK_B_BOOTSTRAP_SEED="${TRACK_B_BOOTSTRAP_SEED:-515151}"
PREFLIGHT_ONLY="${PREFLIGHT_ONLY:-0}"
SEEDS=(17 42 101)
GROUP_RANDOM_AXES=(random_group_k5_p17 random_group_k5_p42 random_group_k5_p101)

mkdir -p "$OUTPUT_ROOT"
STATUS="${STATUS:-$OUTPUT_ROOT/EVALUATION_STATUS}"
LOCK="${LOCK:-$OUTPUT_ROOT/evaluation.lock}"
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "ERROR: evaluation lock exists: $LOCK" >&2
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
require_marker() {
  [[ -e "$1" ]] || fail "missing_marker=$1"
}

for path in \
  "$PROTOCOL" \
  "$SEALED_TEST_ASSIGNMENTS" \
  "$SEALED_TEST_REPORT" \
  "$ROUTER_ARTIFACT" \
  "$ROUTER_REPORT" \
  evaluation/evaluate_organ_k_confirmation.py \
  evaluation/evaluate_organ_k_search.py; do
  require_file "$path"
done
require_marker "$OUTPUT_ROOT/PREPARE_COMPLETE"
require_marker "$ROUTER_ROOT/COMPLETE"

bank_args=()
cache_args=()
for seed in "${SEEDS[@]}"; do
  bank_run="$PACKED_ROOT/seed$seed"
  cache_run="$CACHE_ROOT/seed$seed"
  require_marker "$bank_run/COMPLETE"
  require_marker "$bank_run/banks/organ_k5/COMPLETE"
  require_marker "$bank_run/banks/random_k5/COMPLETE"
  require_marker "$cache_run/COMPLETE"
  require_file "$bank_run/banks/organ_k5/run_metadata.json"
  require_file "$bank_run/banks/organ_k5/calibration_scores.npz"
  require_file "$bank_run/banks/random_k5/run_metadata.json"
  require_file "$bank_run/banks/random_k5/calibration_scores.npz"
  for axis in "${GROUP_RANDOM_AXES[@]}"; do
    require_marker "$bank_run/banks/$axis/COMPLETE"
    require_file "$bank_run/banks/$axis/run_metadata.json"
    require_file "$bank_run/banks/$axis/calibration_scores.npz"
  done
  require_file "$cache_run/test_scores.npz"
  require_file "$cache_run/test_score_report.json"
  bank_args+=(--bank-run "$seed=$bank_run")
  cache_args+=(--test-cache "$seed=$cache_run")
done

"$PYTHON_BIN" -m py_compile \
  evaluation/evaluate_organ_k_confirmation.py \
  evaluation/evaluate_organ_k_search.py \
  || fail python_compile
"$PYTHON_BIN" -c \
  'import json,sys; p=json.load(open(sys.argv[1])); assert p["track_a_k5_internal_replication"]["immutable"] is True; assert p["track_b_development_k_search"]["test_access_allowed"] is False; assert p["track_b_development_k_search"]["candidate_k"] == [1,2,3,4,5]; assert p["firewall"]["run_track_a_before_inspecting_track_b"] is True; assert p["firewall"]["track_b_code_must_reject_test"] is True; assert p["firewall"]["track_b_cannot_modify_track_a"] is True; assert p["firewall"]["track_a_cannot_select_k"] is True; assert p["firewall"]["automatic_external_test_authorization"] is False' \
  "$PROTOCOL" \
  || fail protocol_firewall_contract

if [[ -e "$TRACK_B_ROOT" && ! -e "$TRACK_A_ROOT/COMPLETE" ]]; then
  fail track_b_exists_without_track_a_complete
fi

if [[ "$PREFLIGHT_ONLY" == "1" ]]; then
  echo "ORGAN_K_CONFIRMATION_EVALUATION_PREFLIGHT_OK"
  echo "python=$PYTHON_BIN"
  echo "track_a_root=$TRACK_A_ROOT"
  echo "track_b_root=$TRACK_B_ROOT"
  FINAL_STATUS_WRITTEN=1
  exit 0
fi

TRACK_A_REPORT="$TRACK_A_ROOT/report.json"
if [[ -e "$TRACK_A_ROOT" ]]; then
  require_marker "$TRACK_A_ROOT/COMPLETE"
  require_file "$TRACK_A_REPORT"
else
  set_status "RUNNING phase=track_a_locked_internal_replication"
  "$PYTHON_BIN" evaluation/evaluate_organ_k_confirmation.py \
    --protocol "$PROTOCOL" \
    --router-artifact "$ROUTER_ARTIFACT" \
    --router-report "$ROUTER_REPORT" \
    --sealed-test-assignments "$SEALED_TEST_ASSIGNMENTS" \
    --sealed-test-report "$SEALED_TEST_REPORT" \
    "${bank_args[@]}" \
    "${cache_args[@]}" \
    --output-dir "$TRACK_A_ROOT" \
    --bootstrap-reps "$BOOTSTRAP_REPS" \
    --bootstrap-seed "$TRACK_A_BOOTSTRAP_SEED" \
    > "$OUTPUT_ROOT/track_a_evaluation.log" 2>&1 \
    || fail track_a_evaluation
fi
require_marker "$TRACK_A_ROOT/COMPLETE"
require_file "$TRACK_A_REPORT"
require_file "$TRACK_A_ROOT/decision_scores.npz"
"$PYTHON_BIN" -c \
  'import hashlib,json,sys; r=json.load(open(sys.argv[1])); digest=lambda p: hashlib.sha256(open(p,"rb").read()).hexdigest(); allowed={"pass","true_pass_blind_fail","random_control_fail","pooled_fail","technical_fail"}; assert r["status"] == "complete" and r["test_accessed"] is True; assert r["internal_locked_replication"] is True and r["independent_confirmation"] is False and r["external_confirmation_required"] is True; assert r["decision"]["decision_branch"] in allowed; assert r["decision"]["automatic_external_test_authorization"] is False; assert r["hashes"]["decision_scores_sha256"] == digest(sys.argv[2]); assert r["hashes"]["protocol_sha256"] == digest(sys.argv[3]); assert r["hashes"]["router_artifact_sha256"] == digest(sys.argv[4]); assert r["hashes"]["sealed_test_assignments_sha256"] == digest(sys.argv[5])' \
  "$TRACK_A_REPORT" "$TRACK_A_ROOT/decision_scores.npz" "$PROTOCOL" "$ROUTER_ARTIFACT" "$SEALED_TEST_ASSIGNMENTS" \
  || fail track_a_artifact_contract

# Track B is deliberately unreachable until the completed Track A artifact
# above has been parsed and all provenance/test-label guardrails have passed.
TRACK_B_REPORT="$TRACK_B_ROOT/report.json"
if [[ -e "$TRACK_B_ROOT" ]]; then
  require_marker "$TRACK_B_ROOT/COMPLETE"
  require_file "$TRACK_B_REPORT"
else
  set_status "RUNNING phase=track_b_calibration_only_k_search"
  "$PYTHON_BIN" evaluation/evaluate_organ_k_search.py \
    --protocol "$PROTOCOL" \
    --router-artifact "$ROUTER_ARTIFACT" \
    --router-report "$ROUTER_REPORT" \
    --track-a-report "$TRACK_A_REPORT" \
    "${bank_args[@]}" \
    --output-dir "$TRACK_B_ROOT" \
    --bootstrap-reps "$BOOTSTRAP_REPS" \
    --bootstrap-seed "$TRACK_B_BOOTSTRAP_SEED" \
    > "$OUTPUT_ROOT/track_b_evaluation.log" 2>&1 \
    || fail track_b_evaluation
fi
require_marker "$TRACK_B_ROOT/COMPLETE"
require_file "$TRACK_B_REPORT"
require_file "$TRACK_B_ROOT/calibration_k_scores.npz"
"$PYTHON_BIN" -c \
  'import hashlib,json,sys; r=json.load(open(sys.argv[1])); digest=lambda p: hashlib.sha256(open(p,"rb").read()).hexdigest(); assert r["status"] == "complete" and r["test_accessed"] is False and r["test_features_loaded"] is False and r["test_targets_loaded"] is False; assert r["selection_is_development_only"] is True and r["strict_outer_inner_router"] is True and r["router_policy"] == "common_k5_probability_collapse"; assert r["matched_random_subset_family"].startswith("all C(5,K) subsets"); assert r["decision"]["decision_branch"] in {"development_nomination","no_eligible_k"}; assert r["decision"]["test_accessed"] is False and r["decision"]["automatic_test_authorization"] is False; assert r["hashes"]["track_a_report_sha256"] == digest(sys.argv[2]); assert r["hashes"]["calibration_k_scores_sha256"] == digest(sys.argv[3]); assert r["hashes"]["protocol_sha256"] == digest(sys.argv[4]); assert r["hashes"]["router_artifact_sha256"] == digest(sys.argv[5])' \
  "$TRACK_B_REPORT" "$TRACK_A_REPORT" "$TRACK_B_ROOT/calibration_k_scores.npz" "$PROTOCOL" "$ROUTER_ARTIFACT" \
  || fail track_b_artifact_contract

touch "$OUTPUT_ROOT/EVALUATION_COMPLETE"
set_status COMPLETE
FINAL_STATUS_WRITTEN=1
"$PYTHON_BIN" -c \
  'import json,sys; a=json.load(open(sys.argv[1])); b=json.load(open(sys.argv[2])); print(json.dumps({"track_a": a["decision"], "track_b": b["decision"], "independent_confirmation": a["independent_confirmation"], "external_confirmation_required": a["external_confirmation_required"]}, indent=2, sort_keys=True))' \
  "$TRACK_A_REPORT" "$TRACK_B_REPORT"
