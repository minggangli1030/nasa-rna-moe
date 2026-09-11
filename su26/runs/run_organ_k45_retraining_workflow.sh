#!/usr/bin/env bash
# Prepare, smoke-gate, train all seeds, and evaluate the adaptive K4/K5 run.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
EXPERIMENT_ROOT="${EXPERIMENT_ROOT:?set EXPERIMENT_ROOT to persistent storage}"
CODE_COMMIT="${CODE_COMMIT:-$(git rev-parse HEAD 2>/dev/null || echo archive)}"
PYTHON_BIN="${PYTHON_BIN:-/home/exouser/moe-env/bin/python3}"
export EXPERIMENT_ROOT CODE_COMMIT PYTHON_BIN
if [[ ! -e "$EXPERIMENT_ROOT/PREPARE_COMPLETE" ]]; then
  OUTPUT_ROOT="$EXPERIMENT_ROOT" bash runs/prepare_organ_k45_retraining.sh
fi
SMOKE_ROOT="$EXPERIMENT_ROOT/smoke"
RUN_SEEDS=17 OUTPUT_ROOT="$SMOKE_ROOT" MAX_UPDATES_OVERRIDE=2 SMOKE_ONLY=1 \
  bash runs/run_organ_k45_retraining_worker.sh
"$PYTHON_BIN" -c 'import json,sys; m=json.load(open(sys.argv[1]+"/seed17/run_metadata.json")); assert m["status"]=="complete" and m["mechanical_only"] is True and m["test_accessed"] is False; assert len(m["banks"])==12 and all(v["final_update"]==2 for v in m["banks"].values())' "$SMOKE_ROOT"
touch "$EXPERIMENT_ROOT/SMOKE_COMPLETE"
RUN_SEEDS="17 42 101" OUTPUT_ROOT="$EXPERIMENT_ROOT/packed" \
  bash runs/run_organ_k45_retraining_worker.sh
PACKED_ROOT="$EXPERIMENT_ROOT/packed" bash runs/evaluate_organ_k45_retraining.sh
touch "$EXPERIMENT_ROOT/WORKFLOW_COMPLETE"
