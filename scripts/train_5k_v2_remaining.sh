#!/bin/bash
# For a SECOND GPU instance running in parallel with the main one.
# Trains mouse_5k_v2 then mixed_5k_v2 only (human_5k_v2 is assumed to already
# be training on the primary instance -- don't duplicate it here).
#
# Both variants are capped at 12 epochs (see VARIANT_CONFIGS in train_single.py)
# instead of the base 30, so that both provably fit inside a ~16h budget using
# human_5k_v2's actual measured per-epoch time (~35 min/epoch) as the basis --
# not a hoped-for speedup. Early stopping (patience=5) may end a run sooner;
# the epoch cap is the guaranteed upper bound either way.
set -eo pipefail
cd "$(dirname "$0")/.."

for VARIANT in mouse_5k_v2 mixed_5k_v2; do
    MERGED="data/archs4/${VARIANT}_merged/expression.parquet"
    if [ ! -f "$MERGED" ]; then
        echo "ERROR: $MERGED not found. Copy it from the primary instance first (see PROGRESS.md)."
        exit 1
    fi
    echo "========================================"
    echo "=== Training $VARIANT (capped at 12 epochs) ==="
    echo "========================================"
    DATASET_VARIANT="$VARIANT" torchrun --standalone --nproc_per_node=1 train_single.py
    echo "Done: checkpoints/${VARIANT}/best_model.pt"
done
