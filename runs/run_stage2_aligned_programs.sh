#!/usr/bin/env bash
# Strict smoke/full launcher for the aligned shared/private Stage 2 pivot.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-/home/exouser/moe-env/bin/python3}"
CODE_COMMIT="${CODE_COMMIT:?set the exact deployed full Git commit}"
EXPECTED_PROTOCOL_SHA256="${EXPECTED_PROTOCOL_SHA256:?set the frozen protocol SHA256}"
OUTPUT_ROOT="${OUTPUT_ROOT:?set a new persistent result root}"
RUN_MODE="${RUN_MODE:-full}"
RUN_SEEDS="${RUN_SEEDS:-17 42 101}"
SOURCE_ROOT="${SOURCE_ROOT:-/media/volume/moe-reboot/results/stage1_gtex_to_archs4_529c0c3}"
TRAINING_ROOT="${TRAINING_ROOT:-/media/volume/moe-reboot/results/stage1_gtex_to_archs4_training_98e2cba}"
AXIS_DEFINITIONS="${AXIS_DEFINITIONS:-/media/volume/moe-reboot/results/stage1_k4_final_refit_e8c0383/candidate/bundle/axis_definitions.npz}"
PROTOCOL="${PROTOCOL:-artifacts/stage2_organ_expert_mechanism/aligned_program_protocol.json}"
BASIS_BUNDLE="${BASIS_BUNDLE:-artifacts/stage2_organ_expert_mechanism/aligned_program_basis.npz}"
SMOKE_ROOT="${SMOKE_ROOT:-}"

[[ "$CODE_COMMIT" =~ ^[0-9a-f]{40}$ ]] || exit 2
[[ "$(git rev-parse HEAD)" == "$CODE_COMMIT" ]] || exit 2
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || exit 2
[[ "$(sha256sum "$PROTOCOL" | awk '{print $1}')" == "$EXPECTED_PROTOCOL_SHA256" ]] || exit 2
[[ "$RUN_MODE" == "smoke" || "$RUN_MODE" == "full" ]] || exit 2
[[ ! -e "$OUTPUT_ROOT" ]] || exit 2
if [[ "$RUN_MODE" == "full" ]]; then
  [[ -n "$SMOKE_ROOT" && -e "$SMOKE_ROOT/SMOKE_COMPLETE" ]] || exit 2
  grep -q '^COMPLETE mode=smoke ' "$SMOKE_ROOT/PROGRAM_STATUS" || exit 2
fi

mkdir -p "$OUTPUT_ROOT"
STATUS="$OUTPUT_ROOT/PROGRAM_STATUS"
trap 'rc=$?; if [[ $rc -ne 0 ]]; then printf "FAILED exit=%s %s\n" "$rc" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$STATUS"; fi' EXIT
printf 'RUNNING mode=%s phase=preflight %s\n' "$RUN_MODE" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$STATUS"

"$PYTHON_BIN" -m py_compile \
  core/stage2_program_model.py \
  core/train_stage2_aligned_programs.py \
  evaluation/evaluate_stage2_aligned_programs.py
"$PYTHON_BIN" -c \
  'import json,sys; p=json.load(open(sys.argv[1])); assert p["status"]=="frozen_before_aligned_program_training"; assert p["firewalls"]["archs4_access"] is False; assert p["firewalls"]["best_seed_selection"] is False; assert p["inputs"]["seeds"]==[17,42,101]' \
  "$PROTOCOL"
"$PYTHON_BIN" -c \
  'import torch; assert torch.cuda.is_available(); p=torch.cuda.get_device_properties(0); assert p.total_memory >= 39*1024**3; print(p.name,p.total_memory)' \
  > "$OUTPUT_ROOT/cuda_preflight.log"

for seed in $RUN_SEEDS; do
  [[ "$seed" == "17" || "$seed" == "42" || "$seed" == "101" ]] || exit 2
  SEED_ROOT="$OUTPUT_ROOT/seed$seed"
  printf 'RUNNING mode=%s phase=train seed=%s %s\n' \
    "$RUN_MODE" "$seed" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$STATUS"
  extra=()
  if [[ "$RUN_MODE" == "smoke" ]]; then
    extra+=(--smoke-only --smoke-updates 2)
  fi
  "$PYTHON_BIN" core/train_stage2_aligned_programs.py \
    --protocol "$PROTOCOL" \
    --expected-protocol-sha256 "$EXPECTED_PROTOCOL_SHA256" \
    --basis-bundle "$BASIS_BUNDLE" \
    --expression-parquet "$SOURCE_ROOT/expression/expression.parquet" \
    --expression-metadata "$SOURCE_ROOT/expression/extraction_report.json" \
    --manifest "$SOURCE_ROOT/manifest/gtex_training_manifest.parquet" \
    --axis-definitions "$AXIS_DEFINITIONS" \
    --pooled-checkpoint "$TRAINING_ROOT/seed$seed/pooled/best_model.pt" \
    --output-dir "$SEED_ROOT" \
    --seed "$seed" \
    --code-commit "$CODE_COMMIT" \
    --device cuda \
    --no-use-amp \
    "${extra[@]}" \
    > "$OUTPUT_ROOT/seed$seed.log" 2>&1
done

if [[ "$RUN_MODE" == "full" ]]; then
  printf 'RUNNING mode=full phase=evaluate %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$STATUS"
  "$PYTHON_BIN" evaluation/evaluate_stage2_aligned_programs.py \
    --protocol "$PROTOCOL" \
    --expected-protocol-sha256 "$EXPECTED_PROTOCOL_SHA256" \
    --seed-root "$OUTPUT_ROOT/seed17" \
    --seed-root "$OUTPUT_ROOT/seed42" \
    --seed-root "$OUTPUT_ROOT/seed101" \
    --output-dir "$OUTPUT_ROOT/evaluation" \
    > "$OUTPUT_ROOT/evaluation.log" 2>&1
  decision="$("$PYTHON_BIN" -c 'import json,sys; print(json.load(open(sys.argv[1]))["decision"])' "$OUTPUT_ROOT/evaluation/evaluation_report.json")"
  touch "$OUTPUT_ROOT/COMPLETE"
  printf 'COMPLETE mode=full decision=%s %s\n' "$decision" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$STATUS"
else
  touch "$OUTPUT_ROOT/SMOKE_COMPLETE"
  printf 'COMPLETE mode=smoke %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$STATUS"
fi

(
  cd "$OUTPUT_ROOT"
  find . -type f ! -name IMMUTABLE_SHA256SUMS ! -name PROGRAM_STATUS -print0 \
    | sort -z | xargs -0 sha256sum > IMMUTABLE_SHA256SUMS
)

