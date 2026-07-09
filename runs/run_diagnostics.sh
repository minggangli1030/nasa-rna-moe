#!/bin/bash
# Post-training diagnostics for the 3 v2 5k experts, in dependency order:
#   1. evaluate_osdr.py  -- zero-shot OSDR eval; also downloads + caches
#                            data/osdr/osdr_expression.parquet, which the next
#                            two scripts require via --osdr-parquet.
#   2. check_alignment.py -- per-expert gene-mean-collapse / alignment check.
#   3. analyze_moe_headroom.py -- oracle-vs-best-single-expert ceiling; tells us
#                            whether training the MoE gate is worth the compute.
#
# Needs all 3 checkpoints in one place -- if the 3 experts trained on separate
# instances (as they did this sprint), copy checkpoints/{variant}/best_model.pt
# from each onto whichever single instance runs this script.
set -eo pipefail
cd "$(dirname "$0")/.."

HUMAN_CKPT=checkpoints/human_5k_v2/best_model.pt
MOUSE_CKPT=checkpoints/mouse_5k_v2/best_model.pt
MIXED_CKPT=checkpoints/mixed_5k_v2/best_model.pt
OSDR_PARQUET=data/osdr/osdr_expression.parquet

for c in "$HUMAN_CKPT" "$MOUSE_CKPT" "$MIXED_CKPT"; do
    if [ ! -f "$c" ]; then
        echo "ERROR: $c not found. Train it first (runs/train_*.sh) or copy it from the instance that did."
        exit 1
    fi
done

echo "========================================"
echo "=== [1/3] evaluate_osdr.py (zero-shot, builds OSDR parquet cache) ==="
echo "========================================"
python evaluation/evaluate_osdr.py \
    --checkpoints "$HUMAN_CKPT" "$MOUSE_CKPT" "$MIXED_CKPT" \
    --output-dir results/osdr_eval_5k_v2

echo "========================================"
echo "=== [2/3] check_alignment.py per variant ==="
echo "========================================"
for VARIANT in human_5k_v2 mouse_5k_v2 mixed_5k_v2; do
    echo "--- $VARIANT ---"
    python evaluation/check_alignment.py \
        --checkpoint "checkpoints/${VARIANT}/best_model.pt" \
        --osdr-parquet "$OSDR_PARQUET"
done

echo "========================================"
echo "=== [3/3] analyze_moe_headroom.py ==="
echo "========================================"
python evaluation/analyze_moe_headroom.py \
    --osdr-parquet "$OSDR_PARQUET" \
    --human-ckpt "$HUMAN_CKPT" \
    --mouse-ckpt "$MOUSE_CKPT" \
    --mixed-ckpt "$MIXED_CKPT" \
    --output-dir results/moe_headroom_5k_v2
