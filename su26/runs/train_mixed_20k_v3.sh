#!/bin/bash
# Train mixed_20k_v3 (V3 scale-up). Full A100 (moe-reboot): NCCL backend,
# batch_size 16, balanced human/mouse sampling, ~15 epochs. Most important
# variant for the MoE test (it was best-single on both species at 5k).
set -eo pipefail
cd "$(dirname "$0")/.."
MERGED="data/archs4/mixed_20k_v3_merged/expression.parquet"
[ -f "$MERGED" ] || { echo "ERROR: $MERGED not found (run preprocess_20k_v3.sh or copy it over)."; exit 1; }
DATASET_VARIANT=mixed_20k_v3 torchrun --standalone --nproc_per_node=1 core/train_single.py
echo "Done: checkpoints/mixed_20k_v3/best_model.pt"
