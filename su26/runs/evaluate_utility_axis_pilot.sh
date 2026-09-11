#!/usr/bin/env bash
# Aggregate the exact 7-bank x 3-seed calibration-only utility-axis screen.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-/home/exouser/moe-env/bin/python3}"
RUN_ROOT="${RUN_ROOT:-results/stage2_utility_axis_pilot/packed}"
AXIS_ROOT="${AXIS_ROOT:-results/stage2_utility_axis_pilot/axis}"
OUTPUT="${OUTPUT:-results/stage2_utility_axis_pilot/utility_axis_decision.json}"
axes=(head_gradient_k2 head_gradient_k3 residual_pca_k2 residual_pca_k3 random_k2 random_k3 organ_k5)
seeds=(17 42 101)

args=()
for axis in "${axes[@]}"; do
  for seed in "${seeds[@]}"; do
    run="$RUN_ROOT/seed${seed}/banks/$axis"
    [[ -f "$run/COMPLETE" ]] || { echo "ERROR: incomplete bank $run" >&2; exit 1; }
    args+=(--run "$run")
  done
done
[[ -s "$AXIS_ROOT/partition_report.json" ]] || { echo "ERROR: missing partition report" >&2; exit 1; }
[[ ! -e "$OUTPUT" ]] || { echo "ERROR: decision already exists: $OUTPUT" >&2; exit 1; }
mkdir -p "$(dirname "$OUTPUT")"
"$PYTHON_BIN" evaluation/evaluate_utility_axis_pilot.py \
  "${args[@]}" \
  --partition-report "$AXIS_ROOT/partition_report.json" \
  --bootstrap-reps 2000 \
  --bootstrap-seed 8675309 \
  --minimum-relative-gain 0.03 \
  --maximum-seed-sd-fraction 0.5 \
  --minimum-ami 0.5 \
  --minimum-partition-fraction 0.10 \
  --minimum-effective-expert-fraction 0.8 \
  --minimum-studies-per-partition 5 \
  --maximum-study-dominance 0.5 \
  --output "$OUTPUT" \
  > "${OUTPUT%.json}.log" 2>&1
touch "${OUTPUT%.json}.complete"
cat "$OUTPUT"
