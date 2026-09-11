#!/usr/bin/env bash
# Evaluate all nine calibration-only latent-axis runs once they are colocated.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
PYTHON_BIN="${PYTHON_BIN:-/home/exouser/moe-env/bin/python3}"
RUN_ROOT="${RUN_ROOT:-results/stage2_latent_axis_pilot}"
OUTPUT="$RUN_ROOT/calibration_decision.json"

args=()
for mode in organ_supervised balanced_random label_free; do
  for seed in 17 42 101; do
    run="$RUN_ROOT/${mode}_seed${seed}"
    [[ -f "$run/COMPLETE" ]] || { echo "ERROR: incomplete run $run" >&2; exit 1; }
    args+=(--run "$run")
  done
done

[[ ! -e "$OUTPUT" ]] || { echo "ERROR: decision already exists: $OUTPUT" >&2; exit 1; }
"$PYTHON_BIN" evaluation/evaluate_latent_axis_pilot.py \
  "${args[@]}" \
  --min-seeds 3 \
  --num-experts 5 \
  --bootstrap-reps 2000 \
  --output "$OUTPUT" \
  > "$RUN_ROOT/calibration_decision.log" 2>&1
touch "$RUN_ROOT/EVALUATION_COMPLETE"
cat "$OUTPUT"
