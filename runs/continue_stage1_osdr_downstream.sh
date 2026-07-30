#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:?ROOT is required}"
RESULT="${RESULT:?RESULT is required}"
TRAINING_ROOT="${TRAINING_ROOT:?TRAINING_ROOT is required}"
PROTOCOL="$ROOT/artifacts/final_evaluation/stage1_osdr_downstream/protocol.json"
EXECUTION="$ROOT/artifacts/final_evaluation/stage1_osdr_downstream/execution_v3.json"
LEDGER="$ROOT/artifacts/stage1_gtex_to_archs4/candidate_ledger.json"
PROTOCOL_SHA="04e8354b1417c2f4bb4459f053a4e343dce1e65a9b552e16f7fea08c52d8abb9"
COHORT="$RESULT/osdr_cohort"
FEATURES="$RESULT/features_v3"
SMOKE="$RESULT/evaluation_smoke_v3"
FULL="$RESULT/evaluation_full_v3"
STATUS="$RESULT/DOWNSTREAM_STATUS"

cd "$ROOT"

python3 - "$EXECUTION" <<'PY'
import hashlib, json, pathlib, sys
root = pathlib.Path.cwd()
manifest = json.loads(pathlib.Path(sys.argv[1]).read_text())
if manifest.get("status") != "frozen_stage1_osdr_downstream_execution":
    raise SystemExit("execution manifest is not frozen")
paths = {
    "feature_cache": root / "evaluation/cache_stage1_osdr_downstream_features.py",
    "evaluator": root / "evaluation/evaluate_stage1_osdr_downstream.py",
    "continuation": root / "runs/continue_stage1_osdr_downstream.sh",
}
for name, path in paths.items():
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != manifest["implementation_sha256"][name]:
        raise SystemExit(f"implementation hash mismatch: {name}")
PY

while [[ ! -f "$COHORT/COMPLETE" ]]; do
  printf 'waiting_for_osdr_qc %s\n' "$(date -u +%FT%TZ)" > "$STATUS"
  sleep 30
done

if [[ ! -f "$FEATURES/COMPLETE" ]]; then
  printf 'caching_stage1_features %s\n' "$(date -u +%FT%TZ)" > "$STATUS"
  /home/exouser/moe-env/bin/python3 \
    evaluation/cache_stage1_osdr_downstream_features.py \
    --protocol "$PROTOCOL" \
    --expected-protocol-sha256 "$PROTOCOL_SHA" \
    --candidate-ledger "$LEDGER" \
    --training-root "$TRAINING_ROOT" \
    --cohort-root "$COHORT" \
    --output-dir "$FEATURES" \
    --batch-size 4 \
    --device cuda:0
fi

if [[ ! -f "$SMOKE/COMPLETE" ]]; then
  printf 'running_grouped_smoke %s\n' "$(date -u +%FT%TZ)" > "$STATUS"
  /home/exouser/moe-env/bin/python3 \
    evaluation/evaluate_stage1_osdr_downstream.py \
    --protocol "$PROTOCOL" \
    --expected-protocol-sha256 "$PROTOCOL_SHA" \
    --cohort-root "$COHORT" \
    --feature-root "$FEATURES" \
    --output-dir "$SMOKE" \
    --outer-folds 2 \
    --inner-folds 2 \
    --smoke
fi

if [[ ! -f "$FULL/COMPLETE" ]]; then
  printf 'running_full_grouped_evaluation %s\n' "$(date -u +%FT%TZ)" > "$STATUS"
  /home/exouser/moe-env/bin/python3 \
    evaluation/evaluate_stage1_osdr_downstream.py \
    --protocol "$PROTOCOL" \
    --expected-protocol-sha256 "$PROTOCOL_SHA" \
    --cohort-root "$COHORT" \
    --feature-root "$FEATURES" \
    --output-dir "$FULL" \
    --outer-folds 5 \
    --inner-folds 3
fi

printf 'complete %s\n' "$(date -u +%FT%TZ)" > "$STATUS"
