#!/usr/bin/env bash
# Wrapper for wandb sweep to launch DDP single-parquet training with torchrun.
# NOTE: leftover from the Savio/conda era (was WANDB_PROJECT="bridge-rna" sweeps
# on a shared cluster env) -- path fixed to the current repo layout, but this
# hasn't been re-run since the move to Jetstream. Verify it still works before
# relying on it for a real sweep.
cd "$(dirname "$0")/.."
echo "[SWEEP] Starting single-parquet training with torchrun..." >&2

# Ensure conda env libs take precedence (fixes GLIBCXX version mismatch) -- only
# relevant if running under conda; harmless no-op otherwise.
export LD_LIBRARY_PATH=$CONDA_PREFIX/lib:$LD_LIBRARY_PATH

# wandb agent sets CUDA_VISIBLE_DEVICES which breaks torchrun DDP — unset it
unset CUDA_VISIBLE_DEVICES
N_GPUS=$(nvidia-smi --query-gpu=name --format=csv,noheader | wc -l)
echo "[SWEEP] Detected $N_GPUS GPUs" >&2

# Pick a random free port to avoid collisions when multiple jobs share a node
PORT=$(shuf -i 29500-29999 -n 1)

exec torchrun --nproc_per_node=$N_GPUS --master_port=$PORT \
  core/train_single.py "$@"
