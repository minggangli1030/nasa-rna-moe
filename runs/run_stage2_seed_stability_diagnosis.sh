#!/usr/bin/env bash
# Run an explicit subset of the frozen 3x3 Stage 2 stability diagnosis.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-/home/exouser/moe-env/bin/python3}"
CODE_COMMIT="${CODE_COMMIT:?set the deployed full Git commit}"
SOURCE_ROOT="${SOURCE_ROOT:?set the completed GTEx extraction root}"
SOURCE_TRAINING_ROOT="${SOURCE_TRAINING_ROOT:?set the completed GTEx training root}"
SCHEDULE_ROOT="${SCHEDULE_ROOT:?set the frozen diagnostic schedule root}"
RESULT_ROOT="${RESULT_ROOT:?set a new persistent diagnostic output root}"
RUN_COMBOS="${RUN_COMBOS:?set space-separated TRUNK:OPT combos}"
EXPECTED_SCHEDULE_SHA256="${EXPECTED_SCHEDULE_SHA256:?set frozen schedule SHA256}"
EXPECTED_DEFINITIONS_SHA256="${EXPECTED_DEFINITIONS_SHA256:?set definitions SHA256}"
EXPECTED_PROTOCOL_SHA256="${EXPECTED_PROTOCOL_SHA256:?set frozen protocol SHA256}"
PROTOCOL="${PROTOCOL:-artifacts/stage2_organ_expert_mechanism/seed_stability_protocol.json}"
AXIS_DEFINITIONS="${AXIS_DEFINITIONS:-/media/volume/moe-reboot/results/stage1_k4_final_refit_e8c0383/candidate/bundle/axis_definitions.npz}"

EXPECTED_MANIFEST_SHA256=d37023f08fabf5059a886501ab416feb5caabbce9aa719086832f6d2579ed2e6
MANIFEST="$SOURCE_ROOT/manifest/gtex_training_manifest.parquet"
EXPRESSION="$SOURCE_ROOT/expression/expression.parquet"
EXPRESSION_METADATA="$SOURCE_ROOT/expression/extraction_report.json"
SCHEDULES="$SCHEDULE_ROOT/training_schedules.parquet"
DEFINITIONS="$SCHEDULE_ROOT/arm_definitions.json"
SCHEDULE_REPORT="$SCHEDULE_ROOT/schedule_report.json"

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
for path in \
  "$MANIFEST" "$EXPRESSION" "$EXPRESSION_METADATA" \
  "$SCHEDULES" "$DEFINITIONS" "$SCHEDULE_REPORT" \
  "$PROTOCOL" "$AXIS_DEFINITIONS" core/train_stage2_directed_transfer.py; do
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
  echo "ERROR: diagnostic schedule hash mismatch" >&2
  exit 1
}
[[ "$(sha256sum "$DEFINITIONS" | awk '{print $1}')" == "$EXPECTED_DEFINITIONS_SHA256" ]] || {
  echo "ERROR: diagnostic definitions hash mismatch" >&2
  exit 1
}
[[ "$(sha256sum "$PROTOCOL" | awk '{print $1}')" == "$EXPECTED_PROTOCOL_SHA256" ]] || {
  echo "ERROR: stability protocol hash mismatch" >&2
  exit 1
}

"$PYTHON_BIN" - "$PROTOCOL" "$SCHEDULE_REPORT" <<'PY'
import json,sys
protocol=json.load(open(sys.argv[1]))
report=json.load(open(sys.argv[2]))
assert protocol["status"] == "frozen_before_stability_outcomes"
assert protocol["diagnostic_training_started_before_freeze"] is False
assert protocol["diagnostic_outcomes_accessed_before_freeze"] is False
assert protocol["best_seed_selection_allowed"] is False
assert report["schedule_mode"] == "stability_diagnostic_only"
assert report["counts"]["total_arms"] == 24
assert report["counts"]["total_schedule_draws"] == 48000
assert report["best_seed_selection_allowed"] is False
PY

read -r -a COMBOS <<< "$RUN_COMBOS"
[[ "${#COMBOS[@]}" -ge 1 ]] || {
  echo "ERROR: RUN_COMBOS is empty" >&2
  exit 1
}
mkdir -p "$RESULT_ROOT"
STATUS="$RESULT_ROOT/STAGE2_STABILITY_STATUS"
mkdir "$RESULT_ROOT/stage2_stability.lock"
cleanup() {
  rc=$?
  rmdir "$RESULT_ROOT/stage2_stability.lock" 2>/dev/null || true
  if [[ "$rc" -ne 0 ]]; then
    printf 'FAILED exit=%s %s\n' "$rc" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
  fi
}
trap cleanup EXIT
printf '%s\n' "$CODE_COMMIT" > "$RESULT_ROOT/CODE_COMMIT"
printf '%s\n' "$EXPECTED_SCHEDULE_SHA256" > "$RESULT_ROOT/SCHEDULE_SHA256"
printf '%s\n' "$EXPECTED_DEFINITIONS_SHA256" > "$RESULT_ROOT/DEFINITIONS_SHA256"
printf '%s\n' "$EXPECTED_PROTOCOL_SHA256" > "$RESULT_ROOT/PROTOCOL_SHA256"

completed=0
for combo in "${COMBOS[@]}"; do
  [[ "$combo" =~ ^(17|42|101):(211|223|227)$ ]] || {
    echo "ERROR: unexpected frozen combo $combo" >&2
    exit 1
  }
  trunk_seed="${combo%%:*}"
  opt_seed="${combo##*:}"
  checkpoint="$SOURCE_TRAINING_ROOT/seed$trunk_seed/pooled/best_model.pt"
  [[ -s "$checkpoint" ]] || {
    echo "ERROR: missing pooled checkpoint for trunk $trunk_seed" >&2
    exit 1
  }
  combo_id="trunk${trunk_seed}_opt${opt_seed}"
  printf 'RUNNING combo=%s completed=%s/%s %s\n' \
    "$combo_id" "$completed" "${#COMBOS[@]}" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
  "$PYTHON_BIN" core/train_stage2_directed_transfer.py \
    --expression-parquet "$EXPRESSION" \
    --expression-metadata "$EXPRESSION_METADATA" \
    --manifest "$MANIFEST" \
    --pooled-checkpoint "$checkpoint" \
    --axis-definitions "$AXIS_DEFINITIONS" \
    --training-schedules "$SCHEDULES" \
    --arm-definitions "$DEFINITIONS" \
    --schedule-report "$SCHEDULE_REPORT" \
    --expected-schedule-sha256 "$EXPECTED_SCHEDULE_SHA256" \
    --expected-definitions-sha256 "$EXPECTED_DEFINITIONS_SHA256" \
    --output-dir "$RESULT_ROOT/$combo_id" \
    --seed "$trunk_seed" \
    --optimization-seed "$opt_seed" \
    --mask-seed "$opt_seed" \
    --loader-seed "$opt_seed" \
    --code-commit "$CODE_COMMIT" \
    --device cuda \
    --no-use-amp \
    > "$RESULT_ROOT/$combo_id.log" 2>&1
  "$PYTHON_BIN" - "$RESULT_ROOT/$combo_id/run_metadata.json" "$trunk_seed" "$opt_seed" <<'PY'
import json,sys
p=json.load(open(sys.argv[1]))
trunk=int(sys.argv[2]); opt=int(sys.argv[3])
assert p["status"] == "complete" and p["mechanical_only"] is False
assert p["best_seed_selection_allowed"] is False
assert p["completed_arms"] == 24 and p["counts"]["executed_arms"] == 24
assert p["trunk_seed"] == trunk and p["training_seed"] == trunk
assert p["optimization_seed"] == opt
assert p["mask_seed"] == opt and p["loader_seed"] == opt
assert p["config"]["use_amp"] is False
PY
  completed=$((completed + 1))
done

printf 'COMPLETE combos=%s/%s %s\n' \
  "$completed" "${#COMBOS[@]}" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
(
  cd "$RESULT_ROOT"
  find . -type f \
    ! -name IMMUTABLE_SHA256SUMS \
    ! -name STAGE2_STABILITY_STATUS \
    -print0 |
    sort -z |
    xargs -0 sha256sum
) > "$RESULT_ROOT/IMMUTABLE_SHA256SUMS"
touch "$RESULT_ROOT/COMPLETE"
