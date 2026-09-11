#!/usr/bin/env bash
# Run frozen Stage 2 additive-only arms for an explicit subset of prespecified seeds.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-/home/exouser/moe-env/bin/python3}"
CODE_COMMIT="${CODE_COMMIT:?set the deployed full Git commit}"
SOURCE_ROOT="${SOURCE_ROOT:?set the completed GTEx extraction root}"
SOURCE_TRAINING_ROOT="${SOURCE_TRAINING_ROOT:?set the completed three-seed GTEx training root}"
SCHEDULE_ROOT="${SCHEDULE_ROOT:?set the frozen Stage 2 additive schedule root}"
RESULT_ROOT="${RESULT_ROOT:?set a new persistent Stage 2 additive output root}"
RUN_SEEDS="${RUN_SEEDS:?set a space-separated subset of 17 42 101}"
EXPECTED_SCHEDULE_SHA256="${EXPECTED_SCHEDULE_SHA256:?set frozen additive schedule SHA256}"
EXPECTED_DEFINITIONS_SHA256="${EXPECTED_DEFINITIONS_SHA256:?set frozen additive definitions SHA256}"
AXIS_DEFINITIONS="${AXIS_DEFINITIONS:-/media/volume/moe-reboot/results/stage1_k4_final_refit_e8c0383/candidate/bundle/axis_definitions.npz}"

EXPECTED_MANIFEST_SHA256=d37023f08fabf5059a886501ab416feb5caabbce9aa719086832f6d2579ed2e6
EXPECTED_ADDITIVE_FREEZE_SHA256=15d5cfe19506aa7fe267a422626417ceb794ef6707481d3a15d7fdbf5a89813d
ADDITIVE_FREEZE=artifacts/stage2_organ_expert_mechanism/additive_edge_freeze_20260727.json

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
  core/train_stage2_directed_transfer.py; do
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
  echo "ERROR: Stage 2 additive schedule hash mismatch" >&2
  exit 1
}
[[ "$(sha256sum "$DEFINITIONS" | awk '{print $1}')" == "$EXPECTED_DEFINITIONS_SHA256" ]] || {
  echo "ERROR: Stage 2 additive definitions hash mismatch" >&2
  exit 1
}
[[ "$(sha256sum "$ADDITIVE_FREEZE" | awk '{print $1}')" == "$EXPECTED_ADDITIVE_FREEZE_SHA256" ]] || {
  echo "ERROR: additive-edge freeze hash mismatch" >&2
  exit 1
}

"$PYTHON_BIN" -m py_compile core/train_stage2_directed_transfer.py
"$PYTHON_BIN" -c \
  'import json,sys; p=json.load(open(sys.argv[1])); assert p["status"]=="complete" and p["model_fit"] is False and p["best_seed_selection_allowed"] is False; assert p["schedule_mode"]=="additive_only"; assert p["counts"]["total_arms"]==40 and p["counts"]["additive_named_donor_arms"]==8 and p["counts"]["total_schedule_draws"]==90000' \
  "$SCHEDULE_REPORT"
"$PYTHON_BIN" - "$ADDITIVE_FREEZE" "$SCHEDULE_REPORT" <<'PY'
import json,sys
freeze=json.load(open(sys.argv[1]))
report=json.load(open(sys.argv[2]))
expected=[f"{edge['recipient']}:{edge['donor']}" for edge in freeze["edges"]]
assert report["additive_edges"] == expected
assert len({edge["recipient"] for edge in freeze["edges"]}) == 8
assert freeze["transfer_training_started_before_freeze"] is False
assert freeze["transfer_score_cache_accessed_before_freeze"] is False
assert freeze["best_seed_selection_allowed"] is False
PY

read -r -a SEEDS <<< "$RUN_SEEDS"
[[ "${#SEEDS[@]}" -ge 1 ]] || {
  echo "ERROR: RUN_SEEDS is empty" >&2
  exit 1
}
for seed in "${SEEDS[@]}"; do
  [[ "$seed" == 17 || "$seed" == 42 || "$seed" == 101 ]] || {
    echo "ERROR: unexpected seed $seed" >&2
    exit 1
  }
  [[ -s "$SOURCE_TRAINING_ROOT/seed$seed/pooled/best_model.pt" ]] || {
    echo "ERROR: missing frozen pooled checkpoint for seed $seed" >&2
    exit 1
  }
done

mkdir -p "$RESULT_ROOT"
STATUS="$RESULT_ROOT/STAGE2_ADDITIVE_STATUS"
LOCK="$RESULT_ROOT/stage2_additive.lock"
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

completed=0
for seed in "${SEEDS[@]}"; do
  printf 'RUNNING phase=additive_training seed=%s completed_seeds=%s/%s %s\n' \
    "$seed" "$completed" "${#SEEDS[@]}" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
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
    'import json,sys; p=json.load(open(sys.argv[1])); assert p["status"]=="complete" and p["mechanical_only"] is False and p["best_seed_selection_allowed"] is False; assert p["completed_arms"]==40 and p["counts"]["executed_arms"]==40' \
    "$RESULT_ROOT/seed$seed/run_metadata.json"
  touch "$RESULT_ROOT/SEED${seed}_COMPLETE"
  completed=$((completed + 1))
done

(
  cd "$RESULT_ROOT"
  find . -type f ! -name FULL_SHA256SUMS -print0 |
    sort -z |
    xargs -0 sha256sum
) > "$RESULT_ROOT/FULL_SHA256SUMS"
printf 'COMPLETE phase=additive_training completed_seeds=%s/%s %s\n' \
  "$completed" "${#SEEDS[@]}" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
touch "$RESULT_ROOT/COMPLETE"
