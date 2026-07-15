#!/bin/bash
# Train mouse_20k_v3 (V3 scale-up). vGPU instance (moe-reboot-partial, GRID
# A100X-20C, 20GB): needs DDP_BACKEND=gloo and must NOT set
# PYTORCH_CUDA_ALLOC_CONF=expandable_segments (the vGPU lacks the VMM driver APIs
# it needs) -- same deviations as train_mixed_5k_v2.sh. batch_size 8 (set in
# VARIANT_CONFIGS) to stay within 20GB. ~15 epochs; slowest of the three, so it
# gates the final all-three headroom analysis (preliminary reads possible earlier
# off best_model.pt).
set -eo pipefail
cd "$(dirname "$0")/.."
MERGED="data/archs4/mouse_20k_v3_merged/expression.parquet"
[ -f "$MERGED" ] || { echo "ERROR: $MERGED not found (run preprocess_20k_v3.sh or copy it over)."; exit 1; }
export DDP_BACKEND=gloo
unset PYTORCH_CUDA_ALLOC_CONF
DATASET_VARIANT=mouse_20k_v3 torchrun --standalone --nproc_per_node=1 core/train_single.py
echo "Done: checkpoints/mouse_20k_v3/best_model.pt"
