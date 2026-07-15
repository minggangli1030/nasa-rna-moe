#!/bin/bash
# Train the mixed_5k_v2 expert. Ran this sprint on `moe-reboot-partial`, an
# NVIDIA vGPU partition ("GRID A100X-20C", 20GB) rather than a full A100.
# Capped at 20 epochs, same reasoning as train_mouse_5k_v2.sh.
#
# IMPORTANT -- this vGPU partition needs two deviations from the full-A100
# scripts, found by bisection after two separate CUDA failures (see PROGESS.md):
#   1. DDP_BACKEND=gloo -- the default NCCL backend fails even in single-process
#      mode with "CUDA driver error: operation not supported" on this vGPU.
#   2. Do NOT set PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True here -- that
#      feature uses CUDA virtual-memory-management APIs this vGPU doesn't
#      expose, and fails on a plain model.to(device) call. Full-A100 instances
#      can use it fine (helps with allocator fragmentation); this one can't.
# If running on another partial/virtualized GPU in the future, try this same
# combination first before assuming it's a NCCL-specific problem.
set -eo pipefail
cd "$(dirname "$0")/.."

MERGED="data/archs4/mixed_5k_v2_merged/expression.parquet"
if [ ! -f "$MERGED" ]; then
    echo "ERROR: $MERGED not found. Run runs/preprocess_5k_v2.sh first (or copy it from another instance)."
    exit 1
fi

export DDP_BACKEND=gloo
unset PYTORCH_CUDA_ALLOC_CONF
DATASET_VARIANT=mixed_5k_v2 torchrun --standalone --nproc_per_node=1 core/train_single.py
echo "Done: checkpoints/mixed_5k_v2/best_model.pt"
