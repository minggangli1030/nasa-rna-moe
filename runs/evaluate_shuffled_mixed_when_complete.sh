#!/bin/bash
# Wait for the globally shuffled pooled retrain, then run frozen evaluation.
set -uo pipefail
cd "$(dirname "$0")/.."

TRAIN_EXIT=results/mixed_20k_v3_shuffled_train.exit_code
STATUS=results/mixed_20k_v3_shuffled_eval.status
EXIT_CODE=results/mixed_20k_v3_shuffled_eval.exit_code
COMPLETE=results/mixed_20k_v3_shuffled_eval.COMPLETE
LOG=results/mixed_20k_v3_shuffled_eval.log
CHECKPOINT=checkpoints/mixed_20k_v3_shuffled/best_model.pt
FULL_OUT=results/interspecies_headroom_20k_v3_shuffled_corrected
STRICT_OUT=results/interspecies_headroom_20k_v3_shuffled_strict_study_disjoint
BLIND_OUT=results/blind_species_gate_20k_v3_shuffled
PYTHON=${PYTHON:-/home/exouser/moe-env/bin/python3}

if [ -f "$COMPLETE" ]; then
    exit 0
fi

printf 'WAITING_FOR_TRAINING %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
while [ ! -f "$TRAIN_EXIT" ]; do
    sleep 300
done

train_rc=$(cat "$TRAIN_EXIT")
if [ "$train_rc" != "0" ] || [ ! -f "$CHECKPOINT" ]; then
    printf 'BLOCKED training_rc=%s checkpoint=%s %s\n' \
        "$train_rc" "$CHECKPOINT" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
    printf '1\n' > "$EXIT_CODE"
    exit 1
fi

for output in "$FULL_OUT" "$STRICT_OUT" "$BLIND_OUT"; do
    if [ -e "$output" ]; then
        printf 'BLOCKED output_exists=%s %s\n' "$output" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
        printf '1\n' > "$EXIT_CODE"
        exit 1
    fi
done

printf 'RUNNING %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
mkdir -p "$FULL_OUT" "$STRICT_OUT"
{
    "$PYTHON" evaluation/analyze_moe_headroom.py \
        --eval-parquet data/holdout_eval/mixed_holdout_grouped.parquet \
        --input-space tpm \
        --human-ckpt checkpoints/human_20k_v3/best_model.pt \
        --mouse-ckpt checkpoints/mouse_20k_v3/best_model.pt \
        --mixed-ckpt "$CHECKPOINT" \
        --baseline-mean-npz data/holdout_eval/mixed_20k_v3_gene_mean.npz \
        --mask-artifact results/interspecies_headroom_20k_v3_corrected/mask_artifact.npz \
        --output-dir "$FULL_OUT" \
        --run-label 20k_v3_shuffled_corrected \
        --group-column series_group_id \
        --mask-ratio 0.30 \
        --seed 42 \
        --cv-folds 5 \
        --bootstrap-reps 2000 \
        --batch-size 16 \
        --device cuda:0

    "$PYTHON" evaluation/analyze_moe_headroom.py \
        --eval-parquet data/holdout_eval/mixed_holdout_strict_study_disjoint.parquet \
        --input-space tpm \
        --human-ckpt checkpoints/human_20k_v3/best_model.pt \
        --mouse-ckpt checkpoints/mouse_20k_v3/best_model.pt \
        --mixed-ckpt "$CHECKPOINT" \
        --baseline-mean-npz data/holdout_eval/mixed_20k_v3_gene_mean.npz \
        --cache-path "$FULL_OUT/predictions.npz" \
        --sample-ids-file data/holdout_eval/strict_study_disjoint_ids.txt \
        --output-dir "$STRICT_OUT" \
        --run-label 20k_v3_shuffled_strict_study_disjoint \
        --group-column series_group_id \
        --mask-ratio 0.30 \
        --seed 42 \
        --cv-folds 5 \
        --bootstrap-reps 2000 \
        --batch-size 16 \
        --device cuda:0 \
        --analyze-only

    "$PYTHON" evaluation/evaluate_blind_species_gate.py \
        --cache "$FULL_OUT/predictions.npz" \
        --strict-ids data/holdout_eval/strict_study_disjoint_ids.txt \
        --baseline-mean data/holdout_eval/mixed_20k_v3_gene_mean.npz \
        --output-dir "$BLIND_OUT" \
        --bootstrap-reps 2000

    "$PYTHON" - "$FULL_OUT/report.json" "$STRICT_OUT/report.json" <<'PY'
import json
import hashlib
import sys

full = json.load(open(sys.argv[1]))
strict = json.load(open(sys.argv[2]))
expected_mask = "0092b55fe7e8e23c0448a6957fd741369f77f3916f93d4e17d434a9119999e34"
expected_strict_mask = "739709804e7d56f54dc8a08e38fe0547e97b44d35b42fc5df4c02fd78e1a1059"
expected_strict = "e52a695f5e518be24803dcb1fba266c7a67b7d4696520dba35466f5f38da2b18"
if full["mask_sha256"] != expected_mask:
    raise SystemExit("full evaluation did not reuse the frozen mask")
if strict["mask_sha256"] != expected_strict_mask or strict["n_samples"] != 103:
    raise SystemExit("strict evaluation did not reuse the frozen mask/sample count")
strict_ids = open("data/holdout_eval/strict_study_disjoint_ids.txt", "rb").read()
if hashlib.sha256(strict_ids).hexdigest() != expected_strict:
    raise SystemExit("strict ID artifact changed from the frozen protocol")
if full["checkpoint_info"]["mixed"]["path"].split("/")[-2] != "mixed_20k_v3_shuffled":
    raise SystemExit("evaluation loaded the wrong pooled checkpoint")
print("frozen shuffled-pool evaluation validation passed")
PY
} > "$LOG" 2>&1
rc=$?

printf '%s\n' "$rc" > "$EXIT_CODE"
if [ "$rc" -eq 0 ]; then
    printf 'COMPLETE %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
    touch "$COMPLETE"
else
    printf 'FAILED rc=%s %s\n' "$rc" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
fi
exit "$rc"
