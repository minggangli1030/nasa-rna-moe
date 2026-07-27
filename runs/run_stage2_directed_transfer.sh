#!/usr/bin/env bash
# Run the frozen all-three-seed Stage 2 substitution matrix and evaluator.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-/home/exouser/moe-env/bin/python3}"
CODE_COMMIT="${CODE_COMMIT:?set the deployed full Git commit}"
SOURCE_ROOT="${SOURCE_ROOT:?set the completed GTEx extraction root}"
SOURCE_TRAINING_ROOT="${SOURCE_TRAINING_ROOT:?set the completed three-seed GTEx training root}"
SCHEDULE_ROOT="${SCHEDULE_ROOT:?set the frozen Stage 2 schedule root}"
RESULT_ROOT="${RESULT_ROOT:?set a new persistent Stage 2 output root}"
AXIS_DEFINITIONS="${AXIS_DEFINITIONS:-/media/volume/moe-reboot/results/stage1_k4_final_refit_e8c0383/candidate/bundle/axis_definitions.npz}"

EXPECTED_MANIFEST_SHA256=d37023f08fabf5059a886501ab416feb5caabbce9aa719086832f6d2579ed2e6
EXPECTED_SCHEDULE_SHA256=6390071cdc463a12e2bbf533b931235c17c6a40d75aacc61dbbd881b8c46ed20
EXPECTED_DEFINITIONS_SHA256=b4cae61170614a83bc9fc2a7222a0f824557985bba8130c91750cddc963c8774
EXPECTED_ADDITIVE_FREEZE_SHA256=15d5cfe19506aa7fe267a422626417ceb794ef6707481d3a15d7fdbf5a89813d
ADDITIVE_FREEZE=artifacts/stage2_organ_expert_mechanism/additive_edge_freeze_20260727.json
RUN_SEEDS=(17 42 101)

[[ "$CODE_COMMIT" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ERROR: CODE_COMMIT must be a full hexadecimal commit" >&2
  exit 1
}
[[ "$(git rev-parse HEAD)" == "$CODE_COMMIT" ]] || {
  echo "ERROR: deployed Git HEAD differs from CODE_COMMIT" >&2
  exit 1
}
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || {
  echo "ERROR: deployed tracked Git tree is dirty" >&2
  exit 1
}
[[ ! -e "$RESULT_ROOT" ]] || {
  echo "ERROR: result root already exists: $RESULT_ROOT" >&2
  exit 1
}

MANIFEST="$SOURCE_ROOT/manifest/gtex_training_manifest.parquet"
EXPRESSION="$SOURCE_ROOT/expression/expression.parquet"
EXPRESSION_METADATA="$SOURCE_ROOT/expression/extraction_report.json"
SCHEDULES="$SCHEDULE_ROOT/training_schedules.parquet"
DEFINITIONS="$SCHEDULE_ROOT/arm_definitions.json"
SCHEDULE_REPORT="$SCHEDULE_ROOT/schedule_report.json"
for path in \
  "$MANIFEST" \
  "$EXPRESSION" \
  "$EXPRESSION_METADATA" \
  "$SCHEDULES" \
  "$DEFINITIONS" \
  "$SCHEDULE_REPORT" \
  "$AXIS_DEFINITIONS" \
  "$ADDITIVE_FREEZE" \
  core/train_stage2_directed_transfer.py \
  evaluation/evaluate_stage2_directed_transfer.py; do
  [[ -s "$path" ]] || {
    echo "ERROR: missing required input $path" >&2
    exit 1
  }
done
[[ "$(sha256sum "$MANIFEST" | awk '{print $1}')" == "$EXPECTED_MANIFEST_SHA256" ]] || {
  echo "ERROR: GTEx manifest hash mismatch" >&2
  exit 1
}
[[ "$(sha256sum "$SCHEDULES" | awk '{print $1}')" == "$EXPECTED_SCHEDULE_SHA256" ]] || {
  echo "ERROR: Stage 2 schedule hash mismatch" >&2
  exit 1
}
[[ "$(sha256sum "$DEFINITIONS" | awk '{print $1}')" == "$EXPECTED_DEFINITIONS_SHA256" ]] || {
  echo "ERROR: Stage 2 definitions hash mismatch" >&2
  exit 1
}
[[ "$(sha256sum "$ADDITIVE_FREEZE" | awk '{print $1}')" == "$EXPECTED_ADDITIVE_FREEZE_SHA256" ]] || {
  echo "ERROR: additive-edge freeze hash mismatch" >&2
  exit 1
}

"$PYTHON_BIN" -m py_compile \
  core/train_stage2_directed_transfer.py \
  evaluation/evaluate_stage2_directed_transfer.py
"$PYTHON_BIN" -c \
  'import json,sys; p=json.load(open(sys.argv[1])); assert p["status"]=="frozen_before_directed_transfer_outcomes"; assert p["transfer_training_started_before_freeze"] is False; assert p["transfer_score_cache_accessed_before_freeze"] is False; assert p["best_seed_selection_allowed"] is False; assert len(p["edges"])==8 and len({e["recipient"] for e in p["edges"]})==8' \
  "$ADDITIVE_FREEZE"
"$PYTHON_BIN" -c \
  'import json,sys; p=json.load(open(sys.argv[1])); assert p["status"]=="complete" and p["model_fit"] is False and p["best_seed_selection_allowed"] is False; assert p["counts"]["total_arms"]==60 and p["counts"]["total_schedule_draws"]==90000 and p["batch_size"]==6' \
  "$SCHEDULE_REPORT"
"$PYTHON_BIN" -c \
  'import matplotlib,torch; assert torch.cuda.is_available(); p=torch.cuda.get_device_properties(0); assert p.total_memory >= 39*1024**3; print(matplotlib.__version__,p.name,p.total_memory)' \
  > /tmp/stage2_directed_transfer_cuda_preflight.log

for seed in "${RUN_SEEDS[@]}"; do
  [[ -s "$SOURCE_TRAINING_ROOT/seed$seed/pooled/best_model.pt" ]] || {
    echo "ERROR: missing frozen pooled checkpoint for seed $seed" >&2
    exit 1
  }
done

mkdir -p "$RESULT_ROOT"
STATUS="$RESULT_ROOT/STAGE2_STATUS"
LOCK="$RESULT_ROOT/stage2.lock"
mkdir "$LOCK"
cleanup() {
  rc=$?
  rmdir "$LOCK" 2>/dev/null || true
  if [[ "$rc" -ne 0 ]]; then
    printf 'FAILED exit=%s %s\n' "$rc" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
  fi
}
trap cleanup EXIT
printf '%s\n' "$CODE_COMMIT" > "$RESULT_ROOT/CODE_COMMIT"
printf '%s\n' "$EXPECTED_SCHEDULE_SHA256" > "$RESULT_ROOT/SCHEDULE_SHA256"
printf '%s\n' "$EXPECTED_DEFINITIONS_SHA256" > "$RESULT_ROOT/DEFINITIONS_SHA256"
printf '%s\n' "$EXPECTED_ADDITIVE_FREEZE_SHA256" > "$RESULT_ROOT/ADDITIVE_FREEZE_SHA256"

for seed in "${RUN_SEEDS[@]}"; do
  printf 'RUNNING phase=training seed=%s completed_seeds=%s/3 %s\n' \
    "$seed" "$(( $(find "$RESULT_ROOT" -maxdepth 1 -name 'SEED*_COMPLETE' | wc -l) ))" \
    "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
  "$PYTHON_BIN" core/train_stage2_directed_transfer.py \
    --expression-parquet "$EXPRESSION" \
    --expression-metadata "$EXPRESSION_METADATA" \
    --manifest "$MANIFEST" \
    --pooled-checkpoint "$SOURCE_TRAINING_ROOT/seed$seed/pooled/best_model.pt" \
    --axis-definitions "$AXIS_DEFINITIONS" \
    --training-schedules "$SCHEDULES" \
    --arm-definitions "$DEFINITIONS" \
    --schedule-report "$SCHEDULE_REPORT" \
    --expected-schedule-sha256 "$EXPECTED_SCHEDULE_SHA256" \
    --expected-definitions-sha256 "$EXPECTED_DEFINITIONS_SHA256" \
    --output-dir "$RESULT_ROOT/seed$seed" \
    --seed "$seed" \
    --code-commit "$CODE_COMMIT" \
    --device cuda \
    > "$RESULT_ROOT/seed$seed.log" 2>&1
  "$PYTHON_BIN" -c \
    'import json,sys; p=json.load(open(sys.argv[1])); assert p["status"]=="complete" and p["mechanical_only"] is False and p["best_seed_selection_allowed"] is False; assert p["completed_arms"]==60 and p["counts"]["executed_arms"]==60' \
    "$RESULT_ROOT/seed$seed/run_metadata.json"
  touch "$RESULT_ROOT/SEED${seed}_COMPLETE"
done

printf 'RUNNING phase=evaluation completed_seeds=3/3 %s\n' \
  "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
"$PYTHON_BIN" evaluation/evaluate_stage2_directed_transfer.py \
  --seed-root "17=$RESULT_ROOT/seed17" \
  --seed-root "42=$RESULT_ROOT/seed42" \
  --seed-root "101=$RESULT_ROOT/seed101" \
  --arm-definitions "$DEFINITIONS" \
  --expected-schedule-sha256 "$EXPECTED_SCHEDULE_SHA256" \
  --expected-definitions-sha256 "$EXPECTED_DEFINITIONS_SHA256" \
  --output-dir "$RESULT_ROOT/evaluation" \
  > "$RESULT_ROOT/evaluation.log" 2>&1
"$PYTHON_BIN" -c \
  'import json,sys; p=json.load(open(sys.argv[1])); assert p["status"]=="complete" and p["development_only"] is True and p["study_disjoint"] is False and p["best_seed_selection_allowed"] is False; assert p["summary"]["directed_edges"]==56' \
  "$RESULT_ROOT/evaluation/evaluation_report.json"

(
  cd "$RESULT_ROOT"
  find . -type f ! -name FULL_SHA256SUMS -print0 |
    sort -z |
    xargs -0 sha256sum
) > "$RESULT_ROOT/FULL_SHA256SUMS"
printf 'COMPLETE phase=evaluation completed_seeds=3/3 %s\n' \
  "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
touch "$RESULT_ROOT/COMPLETE"
