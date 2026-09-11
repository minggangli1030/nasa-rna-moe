#!/bin/bash
# Retrain the 20k pooled control with globally shuffled cross-species batches.
set -eo pipefail
cd "$(dirname "$0")/.."
MERGED="data/archs4/mixed_20k_v3_merged/expression.parquet"
[ -f "$MERGED" ] || { echo "ERROR: $MERGED not found."; exit 1; }
DATASET_VARIANT=mixed_20k_v3_shuffled WANDB_MODE=disabled \
    torchrun --standalone --nproc_per_node=1 core/train_single.py
echo "Done: checkpoints/mixed_20k_v3_shuffled/best_model.pt"
