# Bridge-RNA Mid-Project Report: Model Architecture Experiments

## Summary

This project explores masked reconstruction of bulk RNA-seq expression with a SLiMPerformer (`ExpressionPerformer`), trained on ARCHS4 human and mouse data and evaluated zero-shot on NASA OSDR spaceflight expression. The architecture-side experiments compared three single-expert variants (human-only, mouse-only, 50/50 mixed) at two scales (5k and 20k samples), and one mixture-of-experts (MoE) attempt that routes between species-specialized experts. The four headline findings are:

1. Single-expert variants do capture species-specific signal — model performance on mouse OSDR ranks `mouse > mixed > human`, consistent with training-species alignment driving zero-shot transfer.
2. At 5k scale, all three variants suffered gene-mean collapse: predictions are no more correlated with the true expression than they are with the dataset gene-mean baseline (Pearson 0.687 vs 0.847 for human).
3. Scaling 5k → 20k samples (under fixed v1 architecture) closes most of the OSDR gap — Pearson rises from 0.687 to 0.813, val_loss falls from 0.7177 to 0.317. Scale is the dominant lever; holding 5k fixed and switching to v2 architecture only closes a small fraction of the val_loss gap.
4. A naïve MoE over the three 5k experts is not viable — two distinct issues had to be fixed (vocabulary incompatibility and expert collapse) before MoE has any chance of working. A v2 retrain under shared vocabulary just completed (`human_5k_v2` best val_loss 0.6564); the MoE-vs-best-single comparison is the next decision point.

---

## 1. Setup

- **Model:** SLiMPerformer-based `ExpressionPerformer`, masked-language-modeling objective on log1p-TPM gene expression vectors.
- **Training data:** ARCHS4 bulk RNA-seq, three species splits — human-only, mouse-only, and 50/50 human+mouse mixed.
- **Scales:** 5k samples per variant (v1 + v2) and 20k samples (human only).
- **Evaluation:** zero-shot reconstruction on NASA OSDR spaceflight expression (predominantly mouse). Metric is per-sample Pearson correlation on masked positions vs. ground-truth expression. The reference baseline is `gene_mean` — predicting the dataset-wide mean for every masked gene yields per-sample Pearson ≈ 0.85, so any model below this is "worse than predicting the mean".

### Provenance: inherited foundation vs. this work

This repo is a fork of Walter Alvarado's `bridge-rna` (UChicago, March 14–23, 2026, 14 commits ending at `4e18975 osdr review`). Walt established the model and the 5k human baseline; this report covers what was built on top of that foundation.

**Inherited from Walt (the foundation):**

- The SLiMPerformer architecture and attention machinery — `slim_performer_model.py` (516 lines), `numerator_and_denominator.py` (211 lines). The `ExpressionPerformer` wrapper class.
- The ARCHS4 preprocessing pipeline — `preprocessing.py` (1024 lines) for H5 streaming, QC, TPM, log1p, ortholog alignment, parquet batching. `merge.py` for parquet consolidation.
- The base single-expert training loop — `train_single.py` (1010 lines), DDP, W&B sweep integration.
- An initial Bayes hyperparameter sweep at 5k human scale (~60 W&B runs preserved in `checkpoints_performer/`).
- Walt's final commit was titled "osdr review" but did not implement OSDR evaluation — only flagged it as a target.

**Added independently in this work (April 4 – May 3, 2026):**

| Direction | Files / changes (all confirmed not in Walt's tree at `4e18975`) |
|---|---|
| Zero-shot OSDR evaluation | `evaluate_osdr.py`, `prep_osdr_from_kmeng.py`, `evaluate_osdr_moe.py`, `build_mixed_eval.py`, `prep_tcga.py` |
| Diagnostics | `check_alignment.py` (gene-mean collapse check), `analyze_moe_headroom.py` (training-free oracle ceiling), `check_moe_gene_counts.py` (vocab mismatch) |
| Scale-up A/B | `human_20k` and `human_20k_v2` variant configs; +204 lines to `train_single.py` for variant routing, `RESUME_FROM`, walltime-fallback resume |
| v2 architecture | 4-layer / mask-0.30 / weight-decay variants `human_5k_v2`, `mouse_5k_v2`, `mixed_5k_v2`, `human_20k_v2` |
| MoE pipeline | `train_moe.py` (gate over frozen experts), `compute_shared_canonical.py` (shared 15,581-gene vocab), +158 lines to `preprocessing.py` for `--canonical-genes-file` path |
| Compute infrastructure | All 17 Savio sbatch wrappers in `scripts/` (no `scripts/` directory existed at handoff); distributed-training fixes (DDP device handling, port collisions, AMP dtype, GLIBCXX, S3 streaming fallback for ARCHS4 v11) |
| Reference data | `fetch_reference_data.py` for ortholog/gencode references |

In short: Walt provided the model and the human-only 5k baseline + sweep. **The independent contribution covers everything downstream of that foundation** — the OSDR evaluation pipeline, the discovery of gene-mean collapse, the 5k → 20k scale-up A/B, the v2 architectural retrains, the entire MoE exploration (including the discovery of two distinct failure modes — per-variant vocabularies and expert collapse — and the methodology to detect each), and the Savio infrastructure that makes any of these experiments reproducible. Sections 2–7 below describe and quantify that work.

---

## 2. Single-Expert Architecture: Human / Mouse / 50-50

Three variants were trained at 5k samples with identical architecture (v1: 2-layer SLiMPerformer, mask ratio 0.15, no weight decay). OSDR zero-shot results, mouse OSDR random_15pct masking, per-sample Pearson:

| Variant   | Training species   | OSDR Pearson | vs. gene_mean (0.85) |
|-----------|--------------------|--------------:|----------------------|
| `mouse_5k`  | mouse           | **0.781**     | below baseline       |
| `mixed_5k`  | 50/50 human+mouse | 0.758        | below baseline       |
| `human_5k`  | human           | 0.687         | below baseline       |

### Findings

- **Species specialization signal is real.** The ordering `mouse > mixed > human` on a mouse-evaluation set is consistent with training-species alignment — the mixed model is *not* the average, it sits between, and the cross-species (human → mouse OSDR) transfer is the worst. This is the most defensible empirical signal in the architecture side of the project.
- **All three variants underperform the gene-mean baseline (0.85).** Diagnostic alignment checks (`check_alignment.py`) confirm `corr(pred, true) ≈ corr(pred, gene_mean)` across all three — predictions are essentially constant, just at the dataset mean. The model is not learning per-sample structure, it is regurgitating the marginal distribution.

This collapse motivated everything that follows: it is the dominant failure mode at 5k scale with a shallow architecture, and it is what makes any MoE over these experts uninformative.

---

## 3. Issue Encountered: Gene-Mean Collapse

`check_alignment.py` runs the trained model on OSDR and compares two correlations per sample:

- `corr(pred, true)` — the metric we care about
- `corr(pred, gene_mean)` — how much the prediction tracks the dataset mean

If those numbers are ~equal, the model is producing the gene-mean as its prediction regardless of input. That is what we observe at 5k scale across all three species splits. This is not a bug in evaluation; it is the model finding a low-loss solution that ignores the input sample.

Likely contributing factors:

- **Shallow architecture:** v1 used 2 transformer layers. Likely insufficient depth to encode per-sample gene-gene structure.
- **Low mask ratio:** 0.15 — too little signal, easy to land on the mean and not lose much loss.
- **No weight decay.**
- **Limited data:** 5k samples is modest given the gene-vocabulary size (~14k–15k genes).

---

## 4. Scaling Up: 5k → 20k (v1 architecture)

To isolate the effect of scale, both `human_5k` and `human_20k` were trained under the **same v1 architecture** (24.4M params, 14,818 genes, AdamW lr=2e-4, 30-epoch budget). The only difference between runs is training-set size (4k vs 16k samples).

### Validation-loss trajectory comparison

`human_5k` v1 plateaus around epoch 26 at val_loss ≈ 0.72; `human_20k` v1 was still descending at epoch 28 at val_loss ≈ 0.32. Selected milestones:

| Epoch | `human_5k` val_loss | `human_20k` val_loss |
|------:|--------------------:|---------------------:|
| 1     | 1.008               | 0.947                |
| 5     | 0.934               | 0.736                |
| 10    | 0.891               | 0.490                |
| 15    | 0.868               | 0.398                |
| 20    | 0.762               | 0.348                |
| 25    | 0.724               | 0.323                |
| 28    | 0.719               | **0.317** (still descending) |
| Best  | **0.7177** (ep. 26) | **0.317** (ep. 28)   |

`human_5k` triggered the early-stopping no-improvement counter for 4 of its last 5 epochs — the model effectively saturated at this data scale. `human_20k` showed no overfitting signal (train 0.301, val 0.317 closely tracking) and was still improving when the run ended.

### Zero-shot OSDR comparison (the bio-signal test)

Per-sample Pearson on NASA OSDR spaceflight expression, masked-reconstruction. Gene-mean baseline ≈ 0.85 (predicting the dataset mean for every masked gene).

| Variant       | Samples | Best val_loss | OSDR Pearson (random_15pct) | Gap vs gene_mean (0.847) |
|---------------|---------|--------------:|----------------------------:|-------------------------:|
| `human_5k`    | 5k      | 0.7177        | **0.687**                   | −0.160 (severely under)  |
| `human_20k`   | 20k     | 0.317         | **0.8131**                  | −0.034 (closing in)      |

### `human_20k` v1 OSDR by masking strategy

| Masking      | Pearson  | Spearman | MSE    | Gene-mean Pearson |
|--------------|---------:|---------:|-------:|------------------:|
| random_15pct | **0.8131** | 0.8114 | 1.083  | 0.8466            |
| random_50pct | 0.7937   | 0.7950   | 1.257  | 0.8465            |
| random_80pct | 0.6781   | 0.6946   | 1.986  | 0.8467            |
| block_50     | 0.7914   | 0.7691   | 1.098  | 0.8404            |

### Findings

- **Scaling 5k → 20k buys ~5× reduction in the OSDR gene-mean gap.** `human_5k` was 0.16 below the gene-mean baseline on OSDR; `human_20k` is only 0.034 below. The 4× increase in data closed most of the distance to the trivial baseline under the same v1 architecture.
- **Validation loss tells a much stronger story than OSDR alone.** Held-out human val_loss dropped from 0.7177 → 0.317 — more than a 2× reduction. The OSDR gain is real but smaller because OSDR is a different distribution (mostly mouse, spaceflight) and the v1 architecture still doesn't cleanly model per-sample structure.
- **20k still hasn't cleared the gene-mean baseline.** Pearson 0.813 < 0.847 means a learned model is still slightly worse than just predicting the dataset mean for every masked gene. Scaling alone is not sufficient to escape the baseline at v1 architecture; closing the last ~0.03 gap requires either further scale (40k, 80k human-only) or architectural changes.
- **Performance degrades gracefully with masking ratio.** Pearson 0.81 / 0.79 / 0.68 across 15/50/80% random masking confirms the 20k model is doing something context-dependent — it is *not* a constant-output collapse. This is meaningful improvement over the 5k regime, even though the absolute number is still below baseline.

### Architecture vs scale at 5k: scale wins

A v2 retrain at the original 5k scale (`human_5k_v2`: 4-layer, mask 0.30, weight decay 0.01, 38M params, shared 15,581-gene vocab) lets us isolate the architectural axis from the scale axis.

| Variant         | Samples | Arch        | Params | Mask | Best val_loss |
|-----------------|--------:|-------------|-------:|------:|--------------:|
| `human_5k`      | 5k      | v1 (2-layer) | 24M    | 0.15  | 0.7177        |
| `human_5k_v2`   | 5k      | v2 (4-layer) | 38M    | 0.30  | **0.6564** (ep. 29, run cut mid-ep. 30) |
| `human_20k`     | 20k     | v1 (2-layer) | 24M    | 0.15  | **0.317** (still descending)            |

Caveat: `human_5k_v2` uses a *harder* training task (mask 0.30 reconstructs 2× more positions than mask 0.15), so the val_losses are not strictly comparable across rows. The qualitative pattern is still informative:

- **At fixed 5k scale, v2 architecture closes ~0.06 of the val_loss gap** despite the harder objective. Architectural depth + weight decay help, but the gain is modest.
- **At fixed v1 architecture, 4× scale closes ~0.40 of the val_loss gap.** Order-of-magnitude larger improvement.
- **Implication for compute allocation:** under this regime, sample scale is the dominant lever. The v2 architectural changes are still important (they enable shared-vocabulary MoE — see section 5), but expect them to amplify scaling gains rather than substitute for them.

---

## 5. MoE Attempt

Hypothesis: if mouse-only and human-only experts each carry species-specific bio knowledge that the mixed expert dilutes, a per-sample softmax gate over the three experts should outperform the best single expert.

### Implementation

`train_moe.py` loads the three 5k checkpoints with `eval()` + `requires_grad=False`, learns only a small per-sample softmax gate (Linear → GELU → Dropout → Linear → softmax, ~3.8M params), and trains for ~30 epochs with the same masked-reconstruction loss. Single-GPU is sufficient because only the gate has gradients.

### Issue 1: Vocabulary Incompatibility

The v1 5k variants were each trained with their own per-variant gene vocabulary. This silently breaks the MoE assumption: `gene_embedding[i]` does not refer to the same gene across the three experts, so combining their outputs at index `i` is meaningless. This is a methodological lesson — naïve MoE over per-dataset-trained genomics experts requires a shared vocabulary.

**Fix:** `compute_shared_canonical.py` generates a canonical 15,581-gene vocabulary from the intersection of human and mouse orthologs, used through `preprocessing.py --canonical-genes-file`. The v2 retrain (`human_5k_v2`, `mouse_5k_v2`, `mixed_5k_v2`) uses this shared vocab — column order is now identical across variants.

### Issue 2: Expert Collapse Bounds the MoE Ceiling

Training a gate over collapsed experts cannot recover signal that none of the experts have. To check this without committing 24–48h to gate training, `analyze_moe_headroom.py` runs all three experts on OSDR in a common gene space and computes a *training-free oracle* — for each sample, cheat by picking the best expert. This is an upper bound on what any learned gate could achieve.

V1 oracle headroom (oracle minus best single expert, per-sample Pearson):

| Evaluation split    | Best single | Oracle  | Gap        |
|---------------------|------------:|--------:|------------|
| Human TCGA          | 0.7989      | 0.7992  | **+0.0003** |
| Mouse OSDR          | 0.7822      | 0.7835  | **+0.0014** |
| Global mixed        | 0.7715      | 0.7914  | +0.0199    |

The per-species gaps are at noise level. A *trained* gate would land below oracle, so the practical ceiling for v1 MoE is ≈ +0.001. The +0.0199 on the mixed set was attributed to species-ID leakage — the gate would learn "this looks like a human sample → human expert", not real per-sample routing.

**Conclusion on v1 MoE:** not worth gate-training. The oracle headroom analysis itself is a reusable methodology contribution — it lets you decide whether MoE is worth the compute *before* spending it.

### V2 Status

The three v2 5k experts just finished training under the shared vocabulary. The MoE pipeline now runs on a methodologically valid foundation. Two diagnostics determine whether gate training is justified:

1. `check_alignment.py` on each v2 checkpoint — did v2 escape gene-mean collapse? (1h GPU job × 3, can run in parallel)
2. `analyze_moe_headroom.py` on the three v2 experts — what is the oracle ceiling now? (~4h CPU job)

If oracle headroom on a single-species split (e.g. mouse OSDR) is meaningfully above the v1 figure (>~+0.01), gate training is justified. If it is still ~+0.001, MoE is not the right shape of method for this data and the next move is single-expert scaling, not routing.

---

## 6. Key Takeaways

1. **Species-specialization signal exists in single-expert models.** `mouse > mixed > human` on mouse OSDR is the cleanest empirical finding from this work.
2. **Gene-mean collapse is the dominant failure mode at 5k + shallow architecture.** Architectural depth + higher mask ratio + weight decay (the v2 changes) + scale up to 20k together appear to address it — confirmed on val_loss; pending OSDR alignment confirmation.
3. **20k > 5k by a wide margin, but 20k still does not clear the gene-mean baseline on OSDR.** Val_loss dropped from 0.7177 → 0.317 (2.3×) with 4× the data; OSDR Pearson improved from 0.687 → 0.813 (gap to baseline closed from −0.160 to −0.034). Scaling helps enormously but is not sufficient at v1 architecture.
4. **At 5k scale, sample scale dominates architecture.** Holding architecture fixed at v1 and scaling 5k → 20k closed ~0.40 of val_loss; holding scale fixed at 5k and going from v1 (2-layer) → v2 (4-layer + shared vocab + weight decay) closed only ~0.06, despite the v2 task being harder (mask 0.30 vs 0.15). The pragmatic takeaway: prioritize data scale over architectural depth at this regime.
5. **MoE on per-dataset experts requires shared vocabulary.** Per-variant vocabs make `gene_embedding[i]` semantically inconsistent across experts. This is a methodological lesson that transfers to any future MoE work over genomics models.
6. **Oracle headroom is a cheap pre-flight check before committing compute to gate training.** v1 MoE was killed on a 4h CPU job rather than a 48h GPU run.

---

## 7. What To Do Next

**Immediate (this week):**

- Run `check_alignment.py` on `human_5k_v2`, `mouse_5k_v2`, `mixed_5k_v2` checkpoints — confirm whether the v2 architecture (4 layers, mask 0.30, weight decay) breaks the gene-mean ceiling at 5k scale. The 20k v1 result shows that pure scaling under v1 arch closes most but not all of the OSDR gap; the v2 retrains test whether deeper architecture at the original 5k scale gets there from a different angle.
- Run `analyze_moe_headroom.py` on the three v2 experts — determine the per-species oracle ceiling under the corrected setup. Compare against v1 numbers (+0.0003 / +0.0014 / +0.0199) to decide whether gate training is justified.
- Run OSDR evaluation on `human_5k_v2` to enable a clean "5k v1 vs 5k v2" comparison alongside the "5k v1 vs 20k v1" comparison already in section 4. This isolates the architectural contribution from the data-scale contribution.

**Conditional next step (if v2 oracle headroom is meaningful):**

- Train the MoE gate (`train_moe.py`, 24–48h on a single GPU). The script needs a small edit to point its hardcoded data paths at the v2 parquet files before submission.
- Compare MoE OSDR Pearson against the best single v2 expert.

**Conditional next step (if v2 still collapses or oracle headroom is still ~0):**

- Drop MoE for now. Push single-expert scaling further (20k mouse, 20k mixed) under the v2 architecture.
- Reframe MoE in writeup as a negative result with a clear methodological contribution: oracle headroom analysis as a pre-flight diagnostic, plus the shared-vocab requirement.

**Open questions:**

- Why is mouse the strongest single-species expert on mouse OSDR but human is the worst on the same eval — even after accounting for species mismatch? Is the gap closed by 20k mouse?
- Does the mixed model's intermediate position survive at 20k, or does mixed approach the species-matched expert?
- Is there a route to per-sample routing signal that doesn't rely on species ID — for instance, tissue or condition?
