#!/bin/bash
# Train the 3 v2 5k experts sequentially on a single GPU.
# v2 arch (num_layers=4, mask_ratio=0.30, weight_decay=0.01) and the shared
# canonical vocab are baked into VARIANT_CONFIGS in train_single.py already --
# just need DATASET_VARIANT set per run.
set -eo pipefail
cd "$(dirname "$0")/.."

for VARIANT in human_5k_v2 mouse_5k_v2 mixed_5k_v2; do
    MERGED="data/archs4/${VARIANT}_merged/expression.parquet"
    if [ ! -f "$MERGED" ]; then
        echo "ERROR: $MERGED not found. Run scripts/preprocess_5k_v2.sh first."
        exit 1
    fi
    echo "========================================"
    echo "=== Training $VARIANT ==="
    echo "========================================"
    DATASET_VARIANT="$VARIANT" torchrun --standalone --nproc_per_node=1 train_single.py
    echo "Done: checkpoints/${VARIANT}/best_model.pt"
done
