# nasa-rna-moe

ExpressionBERT-style masked gene-expression modeling with a SLiMPerformer Transformer, extended to explore mixture-of-experts (MoE) routing over human, mouse, and mixed RNA-seq experts.

This repo is a personal, standalone continuation of the MoE work originally developed inside the `sp26_nasa` team monorepo (itself a fork of Walter Alvarado's `bridge-rna` work). Split out 2026-07-08 to keep scope to just what this project needs going forward — see `progress.md` for the full migration history and current status.

## Status

Active development, running on Jetstream Cloud VMs (not Savio — see `progress.md` for the environment and current instance assignments). Large generated datasets, local W&B run directories, full checkpoints, and scratch parquet files are intentionally excluded from Git; small reference gene files needed to run the pipeline are kept.

**Current stage (2026-07-15):** Stage 1 (interspecies routing) is complete and, under a rebuilt leakage-resistant evaluation, shows a large study-disjoint routing headroom that a blind expression-only gate recovers. One fair-baseline control (a globally shuffled pooled retrain) is still running. Stage 2 (a fair human-organ MoE) is designed with a five-organ pipeline pilot frozen and awaiting label cleanup. Stage 3 is scoped to D1, an organ-by-organ interference matrix. The authoritative, detailed record is `progress.md`; results live in `report.md`; the prior-art record is `related-works.md`.

## Research Goal

The project studies masked reconstruction of bulk RNA-seq expression and, on top of it, when a routed specialist beats one general model:

- Train `ExpressionPerformer` models on ARCHS4 human, mouse, and mixed human/mouse RNA-seq under one shared 15,448-gene vocabulary.
- Under a corrected, study-aware evaluation, test whether species-specialized experts carry enough complementary signal that adaptive routing beats a cross-fitted fixed ensemble — and whether a blind expression-only gate recovers that route (**Stage 1: yes**).
- Transfer the same testable logic within human biology: does blind organ-specialist routing reconstruct masked genes better than one general human model trained on the identical sample union (**Stage 2, in progress**)?
- Map *where and why* specialization helps via an organ-by-organ transfer/interference matrix (**Stage 3, planned**).

## Model And Data Pipeline

The repo is organized into 4 stages — see `progress.md` for the full directory tree and import notes.

- **`preprocessing/`** — `preprocessing.py` streams ARCHS4 H5 matrices, applies QC, converts counts to TPM, applies `log1p`, aligns orthologous genes, and writes parquet batches. `merge.py` merges parquet batches into an `expression.parquet` per dataset variant.
- **`core/`** — `train_single.py` trains one SLiMPerformer variant with distributed data parallelism; the variant is selected by `DATASET_VARIANT`. `slim_performer_model.py` and `numerator_and_denominator.py` implement the SLiMPerformer attention machinery. `train_moe.py` trains a lightweight gate over frozen experts when the experts share a compatible gene order.
- **`evaluation/`** — `evaluate_osdr.py` evaluates checkpoints on OSDR with several masking strategies; `check_alignment.py`, `analyze_moe_headroom.py`, `check_moe_gene_counts.py` are diagnostic scripts.
- **`runs/`** — plain-bash launcher scripts, one per variant, that tie the above together end to end.

## Key Findings

**Superseded early result (historical).** The first 5k experts trained with per-variant vocabularies, an invalid MoE assumption because `gene_embedding[i]` referred to different genes in different experts. A training-free headroom analysis on those v1 experts appeared to show almost no per-species routing headroom. That analysis was later found methodologically invalid — it fed raw TPM to `log1p(TPM)` models, fit blend weights on the reporting cohort, and used a test-derived gene mean — so its numbers are **not** current evidence and are retained only in Git history. See `report.md` §"Why the Previous Balanced Results Are Superseded".

**Current Stage 1 result (corrected evaluation).** With one shared 15,448-gene vocabulary and a rebuilt study-aware protocol (one `log1p`, out-of-fold weights, study-macro estimand, clustered-bootstrap intervals, a 103-study strict cohort disjoint from every training study), species routing shows large headroom over a cross-fitted **fixed ensemble** — the bar that actually indicates adaptive MoE value, versus merely beating one pooled model:

| Strict 20k condition vs out-of-fold fixed blend | Relative MSE reduction |
| --- | ---: |
| True-species hard router | 33.5% |
| True-species soft router | 34.7% |
| Soft convex MSE oracle | 35.0% |
| **Blind expression-only gate (soft)** | **33.95%** |

The blind gate sees only masked expression (targets hidden) and lands within 1.11% of the true-species router, so expression alone recovers nearly the whole measured ceiling. Full tables, confidence intervals, and the 5k→20k scale effect are in `report.md`.

## Current MoE State

All three experts use the shared 15,448-gene vocabulary from `preprocessing/compute_shared_canonical.py`. Both the V2 5k and V3 20k human/mouse/mixed experts are trained and checksum-verified; V3 is a deliberate **scale** experiment (same backbone/objective, 4× data), not a new architecture. The frozen interspecies evaluation and blind-gate test are complete.

| Stage | State |
| --- | --- |
| Stage 1 — interspecies routing | Complete; one shuffled pooled-baseline control still running |
| Stage 2 — human-organ MoE | Designed; five-organ pilot manifest (`K=5`: brain, skin, liver, colon, lung) frozen, awaiting label cleanup before a definitive run |
| Stage 3 — organ interference matrix (D1) | Planned; see `progress.md` §"Stage 3 Research Directions" |

See `progress.md` for live run status, the completion runbooks, and per-instance quirks.

## Repository Layout

```text
.
├── preprocessing/               # Stage 1: raw ARCHS4/OSDR -> canonical-vocab parquet
├── core/                        # Stage 2: model + training
├── evaluation/                  # Stage 3: diagnostics and zero-shot eval
├── runs/                        # Stage 4: per-variant launcher scripts
├── checkpoints_performer/       # Lightweight tracked run metadata + plots (v1 sweep history)
├── configs/                     # W&B sweep config and launch scripts
├── data/
│   ├── ensembl/                 # Ortholog, protein-coding, and canonical gene reference files
│   ├── gencode/                 # Exon-length reference tables
│   ├── osdr/                    # OSDR metadata/reference mapping
│   └── archs4/                  # ARCHS4 .h5 + generated parquet (gitignored, symlinked to a volume)
├── examples/                    # Analysis notebooks
├── results/                     # Evaluation output (gitignored, symlinked to a volume)
├── checkpoints/, checkpoints_moe/  # Model weights (gitignored, symlinked to a volume)
├── progress.md                   # Repo orientation + current status and archived milestones
└── presentation/                # Biweekly progress-report slides (HTML)
```

See `progress.md` for the full tree with every file inside each stage, plus a note on the two files that import across stage folders.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

See `progress.md` for the full VM bring-up sequence (GPU driver check, volume mount, reference-data fetch) — that's the part worth reading before re-running this from a fresh machine.

## Common Workflows

Generate the shared canonical gene list (pure function of already-fetched reference files, re-run only if those change):

```bash
python preprocessing/compute_shared_canonical.py
```

Build the 3 v2 5k datasets (human / mouse / mixed), train each (one variant per script — see `progress.md` for why), then run diagnostics — each script checks that its inputs exist and fails fast with a clear message if not:

```bash
runs/preprocess_5k_v2.sh
runs/train_human_5k_v2.sh    # or train_mouse_5k_v2.sh / train_mixed_5k_v2.sh
runs/run_diagnostics.sh
```

Evaluate an MoE gate once trained:

```bash
python evaluation/evaluate_osdr_moe.py --gate checkpoints_moe/best_gate.pt
```

## Notes

- `data/` is gitignored by default (`data/*`), except `data/ensembl/`, `data/gencode/`, `data/osdr/` which hold small reference files needed to run the pipeline and are explicitly un-ignored.
- Full `.pt` checkpoints, ARCHS4 `.h5` matrices, generated parquet, W&B run directories, and eval results live on an attached volume (see `progress.md`), not in Git.
- The checked-in checkpoint metadata under `checkpoints_performer/` is lightweight run-history context (config/loss curves) from the original v1 sweep, not full model weights.
