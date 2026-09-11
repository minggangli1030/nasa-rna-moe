#!/bin/bash
# Train human_20k_v3 (V3 scale-up). Full A100 (moe-reboot2): NCCL backend,
# batch_size 16 (set in VARIANT_CONFIGS), ~15 epochs. best_model.pt is rewritten
# every epoch val-loss improves, so intermediate reads are safe.
set -eo pipefail
cd "$(dirname "$0")/.."
MERGED="data/archs4/human_20k_v3_merged/expression.parquet"
[ -f "$MERGED" ] || { echo "ERROR: $MERGED not found (run preprocess_20k_v3.sh or copy it over)."; exit 1; }
DATASET_VARIANT=human_20k_v3 torchrun --standalone --nproc_per_node=1 core/train_single.py
echo "Done: checkpoints/human_20k_v3/best_model.pt"
