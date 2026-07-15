#!/bin/bash
# Corrected, paired 5k-vs-20k interspecies headroom evaluation.
set -euo pipefail
cd "$(dirname "$0")/.."

HOLDOUT=${HOLDOUT:-data/holdout_eval/mixed_holdout_grouped.parquet}
STRICT_HOLDOUT=${STRICT_HOLDOUT:-data/holdout_eval/mixed_holdout_strict_study_disjoint.parquet}
STRICT_IDS=${STRICT_IDS:-data/holdout_eval/strict_study_disjoint_ids.txt}
MEAN_5K=${MEAN_5K:-data/holdout_eval/mixed_5k_v2_gene_mean.npz}
MEAN_20K=${MEAN_20K:-data/holdout_eval/mixed_20k_v3_gene_mean.npz}
OUT_5K=${OUT_5K:-results/interspecies_headroom_5k_v2_corrected}
OUT_20K=${OUT_20K:-results/interspecies_headroom_20k_v3_corrected}
OUT_5K_STRICT=${OUT_5K_STRICT:-results/interspecies_headroom_5k_v2_strict_study_disjoint}
OUT_20K_STRICT=${OUT_20K_STRICT:-results/interspecies_headroom_20k_v3_strict_study_disjoint}
DEVICE=${DEVICE:-cuda:0}
BATCH_SIZE=${BATCH_SIZE:-16}
PYTHON=${PYTHON:-python3}
MASK_RATIO=${MASK_RATIO:-0.30}
EXPECTED_FULL_ID_SHA256=84c607dd83f93964430877f572291836fddd7315dd4f7eae3bcbf12f70fc0d65
EXPECTED_STRICT_ID_SHA256=e52a695f5e518be24803dcb1fba266c7a67b7d4696520dba35466f5f38da2b18

HUMAN_5K=checkpoints/human_5k_v2/best_model.pt
MOUSE_5K=checkpoints/mouse_5k_v2/best_model.pt
MIXED_5K=checkpoints/mixed_5k_v2/best_model.pt
HUMAN_20K=checkpoints/human_20k_v3/best_model.pt
MOUSE_20K=checkpoints/mouse_20k_v3/best_model.pt
MIXED_20K=checkpoints/mixed_20k_v3/best_model.pt

for path in "$HOLDOUT" "$STRICT_HOLDOUT" "$STRICT_IDS" "$MEAN_5K" "$MEAN_20K" \
    "$HUMAN_5K" "$MOUSE_5K" "$MIXED_5K" \
    "$HUMAN_20K" "$MOUSE_20K" "$MIXED_20K"; do
    [ -f "$path" ] || { echo "ERROR: required artifact missing: $path"; exit 1; }
done

"$PYTHON" - "$HOLDOUT" "$STRICT_HOLDOUT" "$STRICT_IDS" \
    "$EXPECTED_FULL_ID_SHA256" "$EXPECTED_STRICT_ID_SHA256" <<'PY'
import hashlib
import sys

import pandas as pd

full_path, strict_path, ids_path, expected_full_hash, expected_strict_hash = sys.argv[1:]
required = ["sample_id", "species", "series_group_id"]
full = pd.read_parquet(full_path, columns=required)
strict = pd.read_parquet(strict_path, columns=required)
ids_bytes = open(ids_path, "rb").read()
ids = ids_bytes.decode("utf-8").splitlines()
actual_full_hash = hashlib.sha256(
    ("\n".join(full["sample_id"].astype(str)) + "\n").encode("utf-8")
).hexdigest()
actual_strict_hash = hashlib.sha256(ids_bytes).hexdigest()
if actual_full_hash != expected_full_hash:
    raise SystemExit(
        f"ERROR: full ID hash {actual_full_hash} != frozen protocol {expected_full_hash}"
    )
if actual_strict_hash != expected_strict_hash:
    raise SystemExit(
        f"ERROR: strict ID hash {actual_strict_hash} != frozen protocol {expected_strict_hash}"
    )
if full["species"].value_counts().to_dict() != {"mouse": 336, "human": 331}:
    raise SystemExit("ERROR: grouped full holdout is not the frozen 667-sample cohort")
if strict["species"].value_counts().to_dict() != {"mouse": 53, "human": 50}:
    raise SystemExit("ERROR: strict holdout is not the frozen 103-sample cohort")
if strict["sample_id"].astype(str).tolist() != ids:
    raise SystemExit("ERROR: strict parquet order differs from strict ID artifact")
for label, frame in (("full", full), ("strict", strict)):
    groups = frame["series_group_id"].astype(str)
    if groups.isin(["", "nan"]).any():
        raise SystemExit(f"ERROR: {label} holdout has missing series_group_id values")
    if frame.assign(_group=groups).groupby("_group")["species"].nunique().max() != 1:
        raise SystemExit(f"ERROR: {label} series components span multiple species")
print(
    f"[protocol] full={len(full)} strict={len(strict)} "
    f"full_sha256={actual_full_hash} strict_sha256={actual_strict_hash}"
)
PY

for output in "$OUT_5K" "$OUT_20K" "$OUT_5K_STRICT" "$OUT_20K_STRICT"; do
    [ ! -e "$output" ] || { echo "ERROR: output already exists: $output"; exit 1; }
done
mkdir -p "$OUT_5K" "$OUT_20K" "$OUT_5K_STRICT" "$OUT_20K_STRICT"

"$PYTHON" evaluation/analyze_moe_headroom.py \
    --eval-parquet "$HOLDOUT" \
    --input-space tpm \
    --human-ckpt "$HUMAN_5K" \
    --mouse-ckpt "$MOUSE_5K" \
    --mixed-ckpt "$MIXED_5K" \
    --baseline-mean-npz "$MEAN_5K" \
    --output-dir "$OUT_5K" \
    --run-label 5k_v2_corrected \
    --group-column series_group_id \
    --mask-ratio "$MASK_RATIO" \
    --seed 42 \
    --cv-folds 5 \
    --bootstrap-reps 2000 \
    --batch-size "$BATCH_SIZE" \
    --device "$DEVICE" | tee "$OUT_5K/run.log"

"$PYTHON" evaluation/analyze_moe_headroom.py \
    --eval-parquet "$HOLDOUT" \
    --input-space tpm \
    --human-ckpt "$HUMAN_20K" \
    --mouse-ckpt "$MOUSE_20K" \
    --mixed-ckpt "$MIXED_20K" \
    --baseline-mean-npz "$MEAN_20K" \
    --mask-artifact "$OUT_5K/mask_artifact.npz" \
    --output-dir "$OUT_20K" \
    --run-label 20k_v3_corrected \
    --group-column series_group_id \
    --mask-ratio "$MASK_RATIO" \
    --seed 42 \
    --cv-folds 5 \
    --bootstrap-reps 2000 \
    --batch-size "$BATCH_SIZE" \
    --device "$DEVICE" | tee "$OUT_20K/run.log"

"$PYTHON" evaluation/analyze_moe_headroom.py \
    --eval-parquet "$STRICT_HOLDOUT" \
    --input-space tpm \
    --human-ckpt "$HUMAN_5K" \
    --mouse-ckpt "$MOUSE_5K" \
    --mixed-ckpt "$MIXED_5K" \
    --baseline-mean-npz "$MEAN_5K" \
    --cache-path "$OUT_5K/predictions.npz" \
    --sample-ids-file "$STRICT_IDS" \
    --output-dir "$OUT_5K_STRICT" \
    --run-label 5k_v2_strict_study_disjoint \
    --group-column series_group_id \
    --mask-ratio "$MASK_RATIO" \
    --seed 42 \
    --cv-folds 5 \
    --bootstrap-reps 2000 \
    --batch-size "$BATCH_SIZE" \
    --device "$DEVICE" \
    --analyze-only | tee "$OUT_5K_STRICT/run.log"

"$PYTHON" evaluation/analyze_moe_headroom.py \
    --eval-parquet "$STRICT_HOLDOUT" \
    --input-space tpm \
    --human-ckpt "$HUMAN_20K" \
    --mouse-ckpt "$MOUSE_20K" \
    --mixed-ckpt "$MIXED_20K" \
    --baseline-mean-npz "$MEAN_20K" \
    --cache-path "$OUT_20K/predictions.npz" \
    --sample-ids-file "$STRICT_IDS" \
    --output-dir "$OUT_20K_STRICT" \
    --run-label 20k_v3_strict_study_disjoint \
    --group-column series_group_id \
    --mask-ratio "$MASK_RATIO" \
    --seed 42 \
    --cv-folds 5 \
    --bootstrap-reps 2000 \
    --batch-size "$BATCH_SIZE" \
    --device "$DEVICE" \
    --analyze-only | tee "$OUT_20K_STRICT/run.log"

"$PYTHON" evaluation/compare_scales.py \
    --five-k-dir "$OUT_5K" \
    --twenty-k-dir "$OUT_20K" \
    --group-column series_group_id \
    --bootstrap-reps 2000 \
    --output results/interspecies_scale_change_full.json

"$PYTHON" evaluation/compare_scales.py \
    --five-k-dir "$OUT_5K_STRICT" \
    --twenty-k-dir "$OUT_20K_STRICT" \
    --group-column series_group_id \
    --bootstrap-reps 2000 \
    --output results/interspecies_scale_change_strict_study_disjoint.json

"$PYTHON" - "$OUT_5K/report.json" "$OUT_20K/report.json" \
    "$OUT_5K_STRICT/report.json" "$OUT_20K_STRICT/report.json" <<'PY'
import json
import sys

for path in sys.argv[1:]:
    report = json.load(open(path))
    print("\n", report["run_label"], report["mask_sha256"])
    for name in ("human", "mouse", "mixed", "fixed_blend_mse_crossfit",
                 "metadata_species_soft_mse_crossfit", "soft_oracle_mse"):
        row = report["conditions"][name]
        print(f"  {name:38s} Pearson*={row['primary_pearson_study_macro']:.5f} "
              f"MSE*={row['primary_mse_study_macro']:.6f}")
PY
