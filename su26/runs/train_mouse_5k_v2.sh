#!/bin/bash
# Train the mouse_5k_v2 expert. Ran this sprint on `moe-reboot2` (full A100,
# g3.xl). Capped at 20 epochs (see VARIANT_CONFIGS in core/train_single.py) --
# chosen from human_5k_v2's measured ~35 min/epoch rate so this provably fits
# inside a 16h budget with real margin, rather than assuming an unproven speedup.
# For a full-A100 instance, the default NCCL DDP backend works fine.
set -eo pipefail
cd "$(dirname "$0")/.."

MERGED="data/archs4/mouse_5k_v2_merged/expression.parquet"
if [ ! -f "$MERGED" ]; then
    echo "ERROR: $MERGED not found. Run runs/preprocess_5k_v2.sh first (or copy it from another instance)."
    exit 1
fi

DATASET_VARIANT=mouse_5k_v2 torchrun --standalone --nproc_per_node=1 core/train_single.py
echo "Done: checkpoints/mouse_5k_v2/best_model.pt"
