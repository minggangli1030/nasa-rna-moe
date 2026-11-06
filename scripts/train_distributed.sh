#!/usr/bin/env bash
# Portable launcher; provision the documented input data before training.
set -euo pipefail
cd "$(dirname "$0")/../research/specialization"
export DATASET_VARIANT="${DATASET_VARIANT:-human_20k_v3}"
exec torchrun \
  --nnodes="${NNODES:-1}" \
  --nproc_per_node="${NPROC_PER_NODE:-1}" \
  --node_rank="${NODE_RANK:-0}" \
  --master_addr="${MASTER_ADDR:-localhost}" \
  --master_port="${MASTER_PORT:-29500}" \
  core/train_single.py
