# nasa-rna-moe

ExpressionBERT-style masked gene-expression modeling with a SLiMPerformer Transformer, extended to explore mixture-of-experts (MoE) routing over human, mouse, and mixed RNA-seq experts.

This repo is a personal, standalone continuation of the MoE work originally developed inside the `sp26_nasa` team monorepo (itself a fork of Walter Alvarado's `bridge-rna` work). Split out 2026-07-08 to keep scope to just what this project needs going forward — see `progress.md` for the full migration history and current status.

## Status

Active development, running on Jetstream Cloud VMs (not Savio — see `progress.md` for the environment and current instance assignments). Large generated datasets, local W&B run directories, full checkpoints, and scratch parquet files are intentionally excluded from Git; small reference gene files needed to run the pipeline are kept.

**Current stage (2026-07-16):** Stage 0 (the inherited interspecies work) is completing its final fair-baseline control: a globally shuffled 20k pooled human-mouse retrain. Stage 1 (the first original summer work, a fair human-organ MoE) now has a synthetic-tested, manifest-driven five-organ smoke path, but its current definitive decision is **NO-GO**: the cohort needs label cleanup and expansion before biological training claims. The present 220-per-organ balanced protocol is for software validation only. Stage 2 is the gated discovery phase: selected directed-transfer confirmations plus label-free MoE routing, with a full organ matrix only if data, variance, and compute justify it. The authoritative dated status is in `progress.md`; concrete Stage 1/2 gates and commands are in `stage1-stage2-experiment-plan.md`; results live in `report.md`; prior art lives in `related-works.md`.

**Vocabulary:** `Stage` denotes the research phase: **Stage 0 = inherited human/mouse/mixed completion**, **Stage 1 = organ-specialization tests**, and **Stage 2 = transfer-validated label-free discovery**. `V1`, `V2`, and `V3` independently denote data/model/debugging generations inside Stage 0 and are never renumbered. `D1`, `D2`, and `D3` denote candidate research directions, not stages.

## Research Goal

The project studies masked reconstruction of bulk RNA-seq expression and, on top of it, when a routed specialist beats one general model:

- Train `ExpressionPerformer` models on ARCHS4 human, mouse, and mixed human/mouse RNA-seq under one shared 15,448-gene vocabulary.
- Under a corrected, study-aware evaluation, test whether species-specialized experts carry enough complementary signal that adaptive routing beats a cross-fitted fixed ensemble — and whether a blind expression-only gate recovers that route (**Stage 0: yes**).
- Transfer the same testable logic within human biology: does blind organ-specialist routing reconstruct masked genes better than one general human model trained on the identical sample union (**Stage 1, in progress**)?
- Probe *what structure the model learns*: screen and confirm directed organ transfer,
  then test whether label-free expert routing recovers the same cross-study biological
  organization rather than technical batch structure (**Stage 2, conditional**).

## Model And Data Pipeline

The repository pipeline is organized into four code components—not research stages. See `progress.md` for the full directory tree and import notes.

- **`preprocessing/`** — `preprocessing.py` builds the Stage 0 sampled datasets. `extract_manifest_expression.py` instead extracts the exact Stage 1 manifest IDs, verifies their frozen split/provenance, and writes canonical-gene raw TPM so the trainer applies `log1p` exactly once.
- **`core/`** — `train_single.py` trains the Stage 0 variants with distributed data parallelism. `train_manifest.py` is the deterministic Stage 1 trainer: it accepts explicit splits and roles, fixed update budgets, balanced sampling, and frozen prediction exports. `slim_performer_model.py` and `numerator_and_denominator.py` implement the SLiMPerformer attention machinery.
- **`evaluation/`** — Stage 0 diagnostics coexist with the Stage 1 balanced-protocol builder, prediction cache, five-class blind router, pooled/fixed/true-organ/oracle/random-control evaluator, and automatic decision script.
- **`runs/`** — fail-fast launchers tie each workflow together. `run_organ_smoke.sh` exercises the entire Stage 1 mechanical path and marks its output `SMOKE_ONLY` so it cannot be mistaken for biological evidence.

## Key Findings

**Superseded early result (historical).** The first 5k experts trained with per-variant vocabularies, an invalid MoE assumption because `gene_embedding[i]` referred to different genes in different experts. A training-free headroom analysis on those v1 experts appeared to show almost no per-species routing headroom. That analysis was later found methodologically invalid — it fed raw TPM to `log1p(TPM)` models, fit blend weights on the reporting cohort, and used a test-derived gene mean — so its numbers are **not** current evidence and are retained only in Git history. See `report.md` §"Why the Previous Balanced Results Are Superseded".

**Current Stage 0 result (corrected evaluation).** With one shared 15,448-gene vocabulary and a rebuilt study-aware protocol (one `log1p`, out-of-fold weights, study-macro estimand, clustered-bootstrap intervals, a 103-study strict cohort disjoint from every training study), species routing shows large headroom over a cross-fitted **fixed ensemble** — the bar that actually indicates adaptive MoE value, versus merely beating one pooled model:

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
| Stage 0 — interspecies routing | Complete; one shuffled pooled-baseline control still running |
| Stage 1 — human-organ MoE | End-to-end smoke code implemented and synthetic-tested; definitive decision remains NO-GO pending label cleanup, cohort expansion, five-way lockbox splitting, and multi-seed evidence |
| Stage 2 — transfer + label-free structure | Conditional after Stage 1; selected edges first, full matrix only if gated; see `progress.md` §"Stage 2 Research Direction" |

See `progress.md` for live run status, the completion runbooks, and per-instance quirks.

## Repository Layout

```text
.
├── preprocessing/               # Raw ARCHS4/OSDR -> canonical-vocab parquet
├── core/                        # Model definitions and training
├── evaluation/                  # Diagnostics, routing, and zero-shot evaluation
├── runs/                        # Per-variant launcher scripts
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
├── stage1-stage2-experiment-plan.md # Stage 1 runnable smoke/gates + planned Stage 2 commands
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

Check the Stage 1 five-organ smoke environment without launching training:

```bash
runs/run_organ_smoke.sh --preflight
```

The launcher will not run by default until the Stage 0 shuffled-control evaluation
has written its completion marker. Its current five-organ input is deliberately
balanced to 220 training samples per organ and is an engineering smoke cohort, not
a definitive biological dataset.

## Notes

- `data/` is gitignored by default (`data/*`), except `data/ensembl/`, `data/gencode/`, `data/osdr/` which hold small reference files needed to run the pipeline and are explicitly un-ignored.
- Full `.pt` checkpoints, ARCHS4 `.h5` matrices, generated parquet, W&B run directories, and eval results live on an attached volume (see `progress.md`), not in Git.
- The checked-in checkpoint metadata under `checkpoints_performer/` is lightweight run-history context (config/loss curves) from the original v1 sweep, not full model weights.
