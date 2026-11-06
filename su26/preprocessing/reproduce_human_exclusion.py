#!/usr/bin/env python3
"""Reproduce human_5k_v2's exact 5000-sample draw (seed=42) to get its GSM IDs,
so the held-out eval set can be provably disjoint from it. Read-only against
the h5 (just pulls sample columns via archs4py.data.rand, same call the
original preprocessing run made), does not touch training data or checkpoints.
"""
import archs4py as a4

H5_PATH = "data/archs4/human_matrix_v11.h5"
OUT_PATH = "data/holdout_eval/exclude_human_5k_v2_reproduced.txt"

print("Reproducing human_5k_v2 draw: n=5000, seed=42 ...", flush=True)
df = a4.data.rand(H5_PATH, 5000, seed=42, remove_sc=True)
ids = sorted(df.columns.tolist())
print(f"Reproduced {len(ids)} sample IDs", flush=True)
with open(OUT_PATH, "w") as f:
    f.write("\n".join(ids))
print(f"Saved to {OUT_PATH}", flush=True)
