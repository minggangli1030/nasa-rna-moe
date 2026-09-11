#!/usr/bin/env bash
# Materialize the single locked-test score cache for one completed K5 seed.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SEED="${1:-${SEED:-}}"
[[ "$#" -le 1 ]] || { echo "usage: $0 SEED" >&2; exit 2; }
case "$SEED" in
  17|42|101) ;;
  *) echo "ERROR: SEED must be one of 17, 42, or 101" >&2; exit 2 ;;
esac

PYTHON_BIN="${PYTHON_BIN:-/home/exouser/moe-env/bin/python3}"
PROTOCOL="${PROTOCOL:-artifacts/stage1_organ_k_confirmation/protocol.json}"
SOURCE_ROOT="${SOURCE_ROOT:-results/stage1_organ_k5_train_20260717T165507Z}"
EXPRESSION_PARQUET="${EXPRESSION_PARQUET:-$SOURCE_ROOT/expression/expression.parquet}"
EXPRESSION_METADATA="${EXPRESSION_METADATA:-$SOURCE_ROOT/expression/extraction_report.json}"
MANIFEST="${MANIFEST:-$SOURCE_ROOT/expression/manifest.parquet}"
POOLED_CHECKPOINT="${POOLED_CHECKPOINT:-$SOURCE_ROOT/models/pooled/best_model.pt}"
AXIS_DEFINITIONS="${AXIS_DEFINITIONS:-results/stage2_utility_axis_pilot_f8ab3cd/axis/axis_definitions.npz}"
OUTPUT_ROOT="${OUTPUT_ROOT:-results/stage1_organ_k_confirmation}"
PARTITION_ROOT="${PARTITION_ROOT:-$OUTPUT_ROOT/partitions}"
SEALED_TEST_ASSIGNMENTS="${SEALED_TEST_ASSIGNMENTS:-$PARTITION_ROOT/sealed_test_assignments.parquet}"
SEALED_TEST_REPORT="${SEALED_TEST_REPORT:-$PARTITION_ROOT/sealed_test_report.json}"
ROUTER_ROOT="${ROUTER_ROOT:-$OUTPUT_ROOT/router}"
ROUTER_ARTIFACT="${ROUTER_ARTIFACT:-$ROUTER_ROOT/organ_k_router.npz}"
ROUTER_REPORT="${ROUTER_REPORT:-$ROUTER_ROOT/router_report.json}"
PACKED_ROOT="${PACKED_ROOT:-$OUTPUT_ROOT/packed}"
SEED_RUN="${SEED_RUN:-$PACKED_ROOT/seed$SEED}"
ORGAN_BANK_DIR="${ORGAN_BANK_DIR:-$SEED_RUN/banks/organ_k5}"
RANDOM_BANK_DIR="${RANDOM_BANK_DIR:-$SEED_RUN/banks/random_k5}"
GROUP_RANDOM_AXES=(random_group_k5_p17 random_group_k5_p42 random_group_k5_p101)
CACHE_ROOT="${CACHE_ROOT:-$OUTPUT_ROOT/test_cache/seed$SEED}"
EXPECTED_FINAL_UPDATE="${EXPECTED_FINAL_UPDATE:-1500}"
BATCH_SIZE="${BATCH_SIZE:-8}"
DEVICE="${DEVICE:-auto}"
PREFLIGHT_ONLY="${PREFLIGHT_ONLY:-0}"

EXPECTED_EXPRESSION_SHA256=148776bc2d5bbe4a969103de7abab932b7467c804934fc697366ae2c209c0821
EXPECTED_MANIFEST_SHA256=bc4e8e4e36ab0e869fd885197842dc797edad5a08b8093beb21185dbeda7f9cc
EXPECTED_CHECKPOINT_SHA256=080a8a36d2090c3a823cd3995d758d1205b0ad02c1c38c06e6763c5a7ebfd789
EXPECTED_AXIS_DEFINITIONS_SHA256=1d7fba55d00f3fe363932abfba2a0e0d76e70e8dedf71aa46c69e29679b0b7cb

mkdir -p "$(dirname "$CACHE_ROOT")"
STATUS="${STATUS:-${CACHE_ROOT}.status}"
LOCK="${LOCK:-${CACHE_ROOT}.lock}"
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "ERROR: cache lock exists: $LOCK" >&2
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
  "$POOLED_CHECKPOINT" \
  "$AXIS_DEFINITIONS" \
  "$SEALED_TEST_ASSIGNMENTS" \
  "$SEALED_TEST_REPORT" \
  "$ROUTER_ARTIFACT" \
  "$ROUTER_REPORT" \
  "$ORGAN_BANK_DIR/run_metadata.json" \
  "$ORGAN_BANK_DIR/final_experts.pt" \
  "$RANDOM_BANK_DIR/run_metadata.json" \
  "$RANDOM_BANK_DIR/final_experts.pt" \
  evaluation/cache_organ_k_confirmation_scores.py; do
  require_file "$path"
done
for axis in "${GROUP_RANDOM_AXES[@]}"; do
  require_file "$SEED_RUN/banks/$axis/run_metadata.json"
  require_file "$SEED_RUN/banks/$axis/final_experts.pt"
  [[ -e "$SEED_RUN/banks/$axis/COMPLETE" ]] \
    || fail "missing_marker=$SEED_RUN/banks/$axis/COMPLETE"
done
for marker in \
  "$OUTPUT_ROOT/PREPARE_COMPLETE" \
  "$ROUTER_ROOT/COMPLETE" \
  "$SEED_RUN/COMPLETE" \
  "$ORGAN_BANK_DIR/COMPLETE" \
  "$RANDOM_BANK_DIR/COMPLETE"; do
  [[ -e "$marker" ]] || fail "missing_marker=$marker"
done

[[ "$(file_sha256 "$EXPRESSION_PARQUET")" == "$EXPECTED_EXPRESSION_SHA256" ]] || fail expression_hash
[[ "$(file_sha256 "$MANIFEST")" == "$EXPECTED_MANIFEST_SHA256" ]] || fail manifest_hash
[[ "$(file_sha256 "$POOLED_CHECKPOINT")" == "$EXPECTED_CHECKPOINT_SHA256" ]] || fail checkpoint_hash
[[ "$(file_sha256 "$AXIS_DEFINITIONS")" == "$EXPECTED_AXIS_DEFINITIONS_SHA256" ]] || fail axis_definitions_hash
"$PYTHON_BIN" -m py_compile evaluation/cache_organ_k_confirmation_scores.py \
  || fail python_compile
"$PYTHON_BIN" -c \
  'import hashlib,json,sys; protocol=json.load(open(sys.argv[1])); sealed=json.load(open(sys.argv[2])); router=json.load(open(sys.argv[3])); digest=lambda p: hashlib.sha256(open(p,"rb").read()).hexdigest(); assert protocol["authorization"]["requested_by_user"] is True; assert protocol["evidence_label"]["internal_locked_replication"] is True and protocol["evidence_label"]["independent_confirmation"] is False; assert protocol["track_a_k5_internal_replication"]["score_split"] == "previously inspected study-disjoint test"; assert protocol["firewall"]["run_track_a_before_inspecting_track_b"] is True; assert sealed["status"] == "complete" and sealed["sealed"] is True and sealed["test_accessed"] is False and sealed["test_expression_accessed"] is False and sealed["test_targets_accessed"] is False; assert sealed["hashes"]["sealed_test_assignments_sha256"] == digest(sys.argv[4]); assert router["status"] == "complete" and router["test_accessed"] is False and router["test_features_loaded"] is False; assert router["hashes"]["router_artifact_sha256"] == digest(sys.argv[5])' \
  "$PROTOCOL" "$SEALED_TEST_REPORT" "$ROUTER_REPORT" "$SEALED_TEST_ASSIGNMENTS" "$ROUTER_ARTIFACT" \
  || fail frozen_test_access_contract
"$PYTHON_BIN" -c \
  'import hashlib,json,sys; seed=int(sys.argv[1]); update=int(sys.argv[2]); digest=lambda p: hashlib.sha256(open(p,"rb").read()).hexdigest(); pairs=(("organ_k5",3,4),("random_k5",5,6)); rows=[json.load(open(sys.argv[path])) for _,path,_ in pairs]; assert all(r["status"] == "complete" and r["axis"] == axis and r["training_seed"] == seed and r["test_accessed"] is False and r["mechanical_only"] is False and r["config"]["num_experts"] == 5 and r["config"]["final_update"] == update and r["artifacts"]["final_experts_sha256"] == digest(sys.argv[checkpoint]) for (axis,_,checkpoint),r in zip(pairs,rows)); assert rows[0]["hashes"]["protocol_sha256"] == rows[1]["hashes"]["protocol_sha256"] == digest(sys.argv[7]); assert rows[0]["hashes"]["partition_manifest_sha256"] == rows[1]["hashes"]["partition_manifest_sha256"]; assert rows[0]["hashes"]["score_gene_indices_sha256"] == rows[1]["hashes"]["score_gene_indices_sha256"]' \
  "$SEED" "$EXPECTED_FINAL_UPDATE" \
  "$ORGAN_BANK_DIR/run_metadata.json" "$ORGAN_BANK_DIR/final_experts.pt" \
  "$RANDOM_BANK_DIR/run_metadata.json" "$RANDOM_BANK_DIR/final_experts.pt" "$PROTOCOL" \
  || fail matched_seed_bank_contract
for axis in "${GROUP_RANDOM_AXES[@]}"; do
  "$PYTHON_BIN" -c \
    'import hashlib,json,sys; r=json.load(open(sys.argv[1])); digest=lambda p: hashlib.sha256(open(p,"rb").read()).hexdigest(); assert r["status"]=="complete" and r["axis"]==sys.argv[3] and r["training_seed"]==int(sys.argv[4]) and r["test_accessed"] is False and r["mechanical_only"] is False and r["config"]["num_experts"]==5 and r["config"]["final_update"]==1500 and r["artifacts"]["final_experts_sha256"]==digest(sys.argv[2]) and r["hashes"]["protocol_sha256"]==digest(sys.argv[5])' \
    "$SEED_RUN/banks/$axis/run_metadata.json" \
    "$SEED_RUN/banks/$axis/final_experts.pt" "$axis" "$SEED" "$PROTOCOL" \
    || fail "matched_group_random_bank_contract_$axis"
done

if [[ "$PREFLIGHT_ONLY" == "1" ]]; then
  echo "ORGAN_K_CONFIRMATION_CACHE_PREFLIGHT_OK seed=$SEED"
  echo "python=$PYTHON_BIN"
  echo "cache_root=$CACHE_ROOT"
  FINAL_STATUS_WRITTEN=1
  exit 0
fi

[[ ! -e "$CACHE_ROOT" ]] || fail "cache_output_exists=$CACHE_ROOT"
set_status "RUNNING phase=locked_test_cache seed=$SEED"
"$PYTHON_BIN" evaluation/cache_organ_k_confirmation_scores.py \
  --protocol "$PROTOCOL" \
  --expression-parquet "$EXPRESSION_PARQUET" \
  --expression-metadata "$EXPRESSION_METADATA" \
  --manifest "$MANIFEST" \
  --pooled-checkpoint "$POOLED_CHECKPOINT" \
  --axis-definitions "$AXIS_DEFINITIONS" \
  --sealed-test-assignments "$SEALED_TEST_ASSIGNMENTS" \
  --sealed-test-report "$SEALED_TEST_REPORT" \
  --organ-bank-dir "$ORGAN_BANK_DIR" \
  --random-bank-dir "$RANDOM_BANK_DIR" \
  --group-random-bank "random_group_k5_p17=$SEED_RUN/banks/random_group_k5_p17" \
  --group-random-bank "random_group_k5_p42=$SEED_RUN/banks/random_group_k5_p42" \
  --group-random-bank "random_group_k5_p101=$SEED_RUN/banks/random_group_k5_p101" \
  --router-artifact "$ROUTER_ARTIFACT" \
  --router-report "$ROUTER_REPORT" \
  --output-dir "$CACHE_ROOT" \
  --expected-seed "$SEED" \
  --expected-final-update "$EXPECTED_FINAL_UPDATE" \
  --batch-size "$BATCH_SIZE" \
  --device "$DEVICE" \
  > "${CACHE_ROOT}.log" 2>&1 \
  || fail "locked_test_cache_seed=$SEED"

SCORES="$CACHE_ROOT/test_scores.npz"
REPORT="$CACHE_ROOT/test_score_report.json"
require_file "$SCORES"
require_file "$REPORT"
"$PYTHON_BIN" -c \
  'import hashlib,json,sys; r=json.load(open(sys.argv[1])); digest=hashlib.sha256(open(sys.argv[2],"rb").read()).hexdigest(); assert r["status"] == "complete" and r["training_seed"] == int(sys.argv[3]) and r["mechanical_only"] is False; assert r["test_accessed"] is True and r["test_expression_accessed"] is True and r["test_targets_accessed"] is True; assert r["internal_locked_replication"] is True and r["independent_confirmation"] is False; assert r["model_fitting_during_test_access"] is False; assert r["hashes"]["test_scores_sha256"] == digest and r["artifacts"]["test_scores_sha256"] == digest; assert r["counts"]["experts_per_bank"] == 5; assert r["target_hiding"]["all_score_genes_replaced_by_mask_token"] is True and r["target_hiding"]["same_masked_features_used_for_router_and_experts"] is True' \
  "$REPORT" "$SCORES" "$SEED" \
  || fail test_cache_artifact_contract

touch "$CACHE_ROOT/COMPLETE"
set_status "COMPLETE seed=$SEED"
FINAL_STATUS_WRITTEN=1
cat "$REPORT"
