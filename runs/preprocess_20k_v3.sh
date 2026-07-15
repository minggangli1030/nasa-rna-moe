#!/bin/bash
# Build the 3 V3 (20k-scale, v2-arch, shared-canonical-vocab) variants:
# human / mouse / mixed. Same canonical gene vocab as the 5k_v2 experts, so all
# six experts share one 15,448-gene space and the MoE headroom analysis is valid.
#
# Requires BOTH data/archs4/{human,mouse}_matrix_v11.h5 present locally (mixed
# needs both). Run this on the instance that has both .h5 (moe-reboot after the
# human_matrix download), then ship each *_merged/expression.parquet to the
# instance that trains that variant.
#
# Over-draws (24k / 12k-per-species) because ~15% of drawn samples fail QC
# (qc-min-nonzero 14000) and a handful get dropped by --exclude-ids-file; we want
# >=19,200 kept (train_subset 16000 + val_subset 3200). Draws EXCLUDE the 667
# balanced-holdout eval sample IDs so that eval set stays a clean OOD test for V3.
set -eo pipefail
cd "$(dirname "$0")/.."

CANON="data/ensembl/canonical_genes_shared.txt"
EXCLUDE="data/holdout_eval/exclude_holdout_all.txt"
for f in "$CANON" "$EXCLUDE"; do
    if [ ! -f "$f" ]; then echo "ERROR: $f not found."; exit 1; fi
done

VARIANTS=(human_20k_v3 mouse_20k_v3 mixed_20k_v3)
SPECIES=(human mouse both)
MAX_SAMPLES=(24000 24000 12000)   # mixed = 12000/species

for i in "${!VARIANTS[@]}"; do
    VARIANT=${VARIANTS[$i]}
    SP=${SPECIES[$i]}
    N=${MAX_SAMPLES[$i]}
    echo "======================================================"
    echo "=== $VARIANT (species=$SP, max-samples=$N, seed=123) ==="
    echo "======================================================"
    python preprocessing/preprocessing.py \
        --species "$SP" \
        --max-samples "$N" \
        --seed 123 \
        --exclude-ids-file "$EXCLUDE" \
        --output-dir "data/archs4/$VARIANT" \
        --normalization tpm \
        --gene-set shared_orthologs \
        --qc-min-nonzero 14000 \
        --canonical-genes-file "$CANON"
    python preprocessing/merge.py \
        --input-dir "data/archs4/$VARIANT" \
        --output-dir "data/archs4/${VARIANT}_merged"
    echo "Done: data/archs4/${VARIANT}_merged/expression.parquet"
done
