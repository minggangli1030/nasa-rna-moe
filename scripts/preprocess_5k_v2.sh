#!/bin/bash
# Build the 3 shared-canonical-vocab 5k variants (human / mouse / mixed) via
# archs4py local sampling. Requires data/archs4/{human,mouse}_matrix_v11.h5 to be
# present locally -- the S3-streaming fallback in preprocessing.py is usable but
# pathologically slow for random samples scattered across the full remote matrix
# (each "contiguous window" read ends up spanning most of the file). See
# PROGRESS.md for why we download the .h5 files instead.
set -eo pipefail
cd "$(dirname "$0")/.."

CANON="data/ensembl/canonical_genes_shared.txt"
if [ ! -f "$CANON" ]; then
    echo "ERROR: $CANON not found. Run: python compute_shared_canonical.py"
    exit 1
fi

VARIANTS=(human_5k_v2 mouse_5k_v2 mixed_5k_v2)
SPECIES=(human mouse both)
MAX_SAMPLES=(5000 5000 2500)   # mixed = 2500/species = 5000 total

for i in "${!VARIANTS[@]}"; do
    VARIANT=${VARIANTS[$i]}
    SP=${SPECIES[$i]}
    N=${MAX_SAMPLES[$i]}
    echo "========================================"
    echo "=== $VARIANT (species=$SP, max-samples=$N) ==="
    echo "========================================"
    python preprocessing.py \
        --species "$SP" \
        --max-samples "$N" \
        --output-dir "data/archs4/$VARIANT" \
        --normalization tpm \
        --gene-set shared_orthologs \
        --qc-min-nonzero 14000 \
        --canonical-genes-file "$CANON"
    python merge.py \
        --input-dir "data/archs4/$VARIANT" \
        --output-dir "data/archs4/${VARIANT}_merged"
    echo "Done: data/archs4/${VARIANT}_merged/expression.parquet"
done
