#!/bin/bash
# Train the human_5k_v2 expert. Ran this sprint on `moe-reboot` (full A100,
# g3.xl) -- uncapped (base 30-epoch config), since it started first and had no
# reason to be interrupted once the other two variants got their own instances.
# For a full-A100 instance, the default NCCL DDP backend works fine; no env
# var overrides needed (see train_mixed_5k_v2.sh for the vGPU/partial-GPU case).
set -eo pipefail
cd "$(dirname "$0")/.."

MERGED="data/archs4/human_5k_v2_merged/expression.parquet"
if [ ! -f "$MERGED" ]; then
    echo "ERROR: $MERGED not found. Run runs/preprocess_5k_v2.sh first (or copy it from another instance)."
    exit 1
fi

DATASET_VARIANT=human_5k_v2 torchrun --standalone --nproc_per_node=1 core/train_single.py
echo "Done: checkpoints/human_5k_v2/best_model.pt"
