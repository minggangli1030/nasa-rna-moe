# NASA RNA MoE: Progress and Operating Context

**Last updated:** 2026-07-15 12:00 PDT / 2026-07-15 19:00 UTC

This is the compact handoff document for the current experiment. Older detailed
logs remain recoverable in Git history through commit `10a5e0e`; obsolete
evaluation numbers are intentionally not repeated as current evidence.

## Current Objective

Stage 1 interspecies training, backup, evaluation, reporting, and Git archival are
complete. The next objective is to close two targeted Stage 1 controls while
beginning a bounded Stage 2 human-organ pilot:

1. **Complete:** test a blind expression-derived species gate against the
   true-species ceiling.
2. **Running:** retrain the pooled mixed control with globally shuffled
   cross-species batches.
3. **Pilot frozen:** audit organ labels, choose a data-supported `K`, and build
   study-disjoint train/calibration/test manifests.
4. **Next:** manually validate and expand organ labels before spending a long
   specialist-training run.
5. Compare a pooled human model with fair specialist, fixed-ensemble, metadata,
   blind-gate, and oracle controls.

NASA OSDR is secondary because the current OSDR cohort is mouse-only. It cannot
serve as the primary interspecies-routing benchmark.

## Current Runtime Status

- `moe-reboot` is the only active VM. `moe-reboot2` and
  `moe-reboot-partial` are shelved and are not referenced by current work.
- The corrected pooled control is running in remote tmux session
  `mixed20k_shuffled_20260715`. It uses the same 16,000 train / 3,200
  validation rows and V3 architecture, but `data_mode=preload` makes the
  `DistributedSampler` shuffle individual rows globally. Remote preflight found
  1,983/2,000 epoch-0 batches contained both species. At 19:01 UTC it was at
  epoch 1 batch 1,000/2,000, about 4.11 seconds/batch and 100% A100 utilization,
  with an estimated 33 hours 14 minutes remaining. It is therefore not expected
  to finish within 24 hours or before the July 16 presentation.
  Logs are in `results/mixed_20k_v3_shuffled_train.log`; checkpoints write
  directly to persistent
  `/media/volume/moe-reboot/checkpoints/mixed_20k_v3_shuffled`.
- Remote tmux session `mixed20k_shuffled_eval_watch_20260715` is waiting for a
  clean training exit. It will immediately run full, strict, and blind-gate
  evaluation with the frozen sample order and masks, write separate shuffled
  result directories, and refuse to overwrite any existing output.
- The July 16 ten-minute update is ready in
  `presentation/2026-07-16-biweekly.html`, with timed notes in
  `presentation/2026-07-16-biweekly-script.md`. Its nine-slide story covers the
  corrected evaluation, V3 scale/finding, blind gate, bounded Stage 1 claim, and
  fair Stage 2 organ design. The current pooled retrain is labeled ongoing, not
  presented as a partial result. Desktop/laptop/mobile render checks pass with
  no horizontal overflow or clipped elements.
- The original V3 checkpoints and all prior evaluation artifacts remain
  untouched on persistent storage.
- **Original three 20k runs and backups complete.** Final epoch-15 checkpoints are human
  val `0.2791703`, MD5 `2bfad4ab0fa14ea7dd5a7ca5207b8df1`; mouse val
  `0.2310176`, MD5 `9d5a4c342a566f8bcfc5e9d186020d01`; mixed val
  `0.5455396`, MD5 `5d7f6fe24bd750f6b3fd1dd38916375e`. Each is verified
  on the Mac and central persistent storage with metadata archived. Human and
  mouse workers are idle and safe to shelve.
- **Corrected 5k/20k evaluation complete and validated.** GPU inference exited
  successfully. A transient watcher validation error was reproduced manually
  with the same copied bundle and passed; frozen sample/mask/schema checks are
  valid and the timestamped report addendum is generated.
- **Strict 20k diagnosis: practically convincing frozen adaptive ceiling.** The
  metadata-species soft router beats the out-of-fold fixed blend by `34.7%`
  relative MSE (absolute improvement `0.16493`, 95% CI `[0.15751, 0.17255]`)
  and residual Pearson `+0.1198` (95% CI `[0.1130, 0.1267]`). The soft oracle
  reaches `35.0%` relative MSE reduction, showing the metadata router captures
  nearly all measured routing ceiling on this cohort.
- **Blind species gating is now validated.** A leakage-protected logistic gate
  saw only the masked expression input, trained on 564 calibration samples from
  518 groups, and was evaluated on the unchanged 103-study strict cohort with
  zero group overlap. Strict accuracy was `99.03%` (49/50 human, 53/53 mouse;
  AUC `1.0`). Blind-soft routing reached MSE `0.31404`, versus `0.47547` for the
  calibration-fitted fixed blend: `33.95%` relative reduction, absolute gain
  `0.16143` with 95% CI `[0.15336, 0.16926]`, and residual-Pearson gain
  `+0.11450` with CI `[0.10768, 0.12144]`. It is only 1.11% worse in MSE than
  the true-species soft router (`0.31059`), so expression recovers nearly all of
  the measured routing ceiling.
- **Organ audit/pilot manifest complete.** Conservative ARCHS4 normalization
  produced 14,096 candidates across 603 connected study groups. After removing
  tumor-like rows, multi-organ groups, and capping each group at 20 samples, the
  data-driven criteria (at least 45 groups and 300 capped samples) select five
  organs: brain, skin, liver, colon, and lung. The V2 manifest has 2,856 samples,
  317 groups, and 1,998 training rows. Studies are split atomically; calibration
  and test sample counts are balanced within each organ; and the pooled training
  hash exactly equals the union of specialist training IDs.
- The organ manifest is a **pipeline pilot**, not a frozen scientific cohort.
  Manual spot checking found residual acronym/cell-source ambiguity (for
  example GBM and HSAEpC metadata). Label review or ontology-backed expansion is
  required before organ-model training. Current specialist train counts are also
  small (brain 783, skin 409, liver 345, lung 241, colon 220).

## What Changed from V2 to V3

V3 is primarily a data-scale experiment, not a new MoE architecture:

| Dimension | V2 5k | V3 20k | Interpretation |
|---|---|---|---|
| Train / validation rows per expert | 4,000 / 800 | 16,000 / 3,200 | 4x more rows |
| Model | 4-layer `ExpressionPerformer` | Same | Architecture held fixed |
| Gene space | Shared 15,448 genes | Same | All six checkpoints are compatible |
| Objective | `log1p_tpm`, 30% mask, wd 0.01 | Same | Same reconstruction task |
| Training | V2 seed/draw; 20-30 epochs | seed 123; 15 epochs, batch 8 | Not a perfectly single-variable scale test |
| Holdout | Removed retrospectively for corrected evaluation | 667 IDs excluded during preprocessing | V3 explicitly protects the frozen cohort |

The qualitative discovery is mostly an **evaluation correction**, because the
same V2 checkpoints that previously appeared to have approximately zero routing
headroom show a strong effect under the corrected protocol. V3 then amplifies
that effect:

| Strict study-disjoint comparison vs OOF fixed blend | V2 5k | V3 20k |
|---|---:|---:|
| True-species hard router: relative MSE reduction | 17.9% | 33.5% |
| True-species soft router: relative MSE reduction | 18.7% | 34.7% |
| Hard MSE oracle: relative MSE reduction | 17.9% | 33.8% |
| Soft MSE oracle: relative MSE reduction | 19.3% | 35.0% |

Thus this is not mainly a soft-oracle artifact. Hard true-species routing already
works; soft mixing adds about 0.9% relative MSE over hard routing at 5k and 1.8%
at 20k. The important changes were applying the training-space `log1p` transform,
using grouped out-of-fold comparisons and train-only baselines, distinguishing a
pooled single expert from a fixed ensemble, and measuring routing against that
fixed ensemble. The `mixed` checkpoint is one pooled expert, not an oracle.

V3 contributes a real scale result on top: on the strict paired cohort, adaptive
MSE headroom over the fixed blend increases by `0.04064` from 5k to 20k (95% CI
`[0.03210, 0.04928]`), and Pearson headroom increases by `0.00552` (95% CI
`[0.00413, 0.00693]`).

## Stage 2 Hypothesis and Experimental Design

### Primary hypothesis

Given a human bulk RNA-seq sample with no organ label, a gate using only the
observed expression input can select an organ-specialized expert whose masked-
gene reconstruction is better than one general human model trained on the exact
same union of samples.

The number of experts is a data-driven `K`, not a fixed four. Include only organs
with enough samples and independent GEO studies to support specialist training
and a genuinely study-disjoint test. If expert `k` receives `N_k` training rows,
the fair-data constraint is:

```text
sum(N_k for k in 1..K) = N
general model training rows = the identical N-sample union
```

### Fair training and inference

- Use the same human gene vocabulary, architecture, masking, optimizer, and
  number of sample exposures for the pooled model and every specialist.
- Each training sample belongs to exactly one organ expert and also appears in
  the general model's union; no specialist receives extra data.
- The primary practical system uses a blind top-1 gate, so each sample executes
  one expert plus a small classifier, approximately matching general-model
  inference FLOPs. Report the `K`-fold storage/parameter cost separately.
- The gate sees only the same masked/observed expression available to the expert,
  never the reconstruction targets. Train/calibrate it on studies excluded from
  the final test.
- Add a confidence threshold and general-model fallback for ambiguous, mixed, or
  out-of-taxonomy organs.

### Required comparison ladder

1. **One pooled general human model on all `N` samples:** practical baseline.
2. **`K` random-shard experts with fixed weights:** controls for generic
   sharding, extra stored parameters, and ensembling without organ specialization.
3. **`K` organ experts with fixed weights:** isolates biological specialization
   from random-shard ensembling, but evaluates all experts at inference.
4. **True-organ hard/soft routing:** metadata-conditioned specialization ceiling.
5. **Blind expression-derived top-1/soft gate:** deployable unknown-organ system.
6. **Per-sample soft oracle:** non-deployable upper bound using target values.

The primary effectiveness comparison is blind top-1 organ MoE versus the pooled
general model. Blind versus fixed organ ensemble isolates adaptive routing; organ
versus random-shard ensemble isolates organ specialization; blind versus
true-organ and oracle conditions measures unrealized routing headroom.

### Proposed success criterion

Proceed beyond the pilot if the blind top-1 system beats the pooled general model
and the relevant inference-matched control by at least 5% relative MSE, has a
positive study-bootstrap interval, improves residual Pearson, and captures a
substantial preregistered fraction of the true-organ routing ceiling. Organ-
classifier accuracy is secondary to end-to-end reconstruction performance.

## Stage Transition Decision

Stage 1 is strong enough to begin Stage 2 dataset auditing, cohort freezing, and
a small organ pilot now. The strict result is large, statistically separated from
zero, present under hard routing, and stronger at 20k, so further species-only
ceiling analysis has diminishing value.

Two Stage 1.5 experiments were required before a definitive Stage 1 claim or a
full-scale `K`-organ training campaign:

1. **Blind species gate: complete.** The expression-only gate recovers almost all
   of the true-species ceiling and strongly beats both the pooled model and fixed
   ensemble on the strict study-disjoint cohort.
2. **Corrected pooled mixed retrain: running.** Global row shuffling removes the
   known V3 pooled-control weakness; rerun the frozen evaluation after its best
   checkpoint is finalized.

The successful blind gate is strong enough to continue organ metadata cleanup
and pipeline development. The active pooled retrain and organ label validation
still block the strongest publication claim and major Stage 2 compute spending.

## Repository and Compute

- Local repo: `/Users/minggangli/Projects/nasa-rna-moe`
- Central persistent VM: `moe-reboot`
- Shelved human VM: `moe-reboot2` (ephemeral root disk)
- Shelved mouse VM: `moe-reboot-partial` (hostname `moe-reboot3`, ephemeral)
- Central paths `data/archs4`, `checkpoints`, and `results` use the persistent
  `/media/volume/moe-reboot` volume.
- Training runs inside VM tmux. Never launch long work through a bare SSH shell.

## Archived Milestones

- Migrated the project from the `sp26_nasa` monorepo to a standalone repository
  and Jetstream A100 instances.
- Rebuilt the shared canonical human/mouse vocabulary (15,448 genes), downloaded
  ARCHS4 v11 H5 matrices, and generated V2 5k datasets.
- Trained shared-vocabulary 5k human, mouse, and mixed experts.
- Diagnosed the original MoE failure modes: incompatible vocabularies, narrow
  expert generalization, and almost no routing ceiling on mouse-only OSDR.
- Built a balanced 667-sample ARCHS4 human+mouse holdout and launched V3 20k
  human, mouse, and mixed scale-up runs.
- Commit `10a5e0e` backs up the corrected evaluation and automation code on
  `origin/main`.

## Why the Old Balanced Evaluation Is Invalid

Do not use the previously reported balanced-ARCHS4 `+0.0031` headroom or `0.686`
gene-mean result. The old evaluator:

- fed raw TPM into models trained on `log1p(TPM)`;
- tuned a fixed blend on the samples used for reporting;
- derived the gene-mean baseline from the test cohort;
- labeled a hard expert selector as the oracle even though a soft convex gate
  has a higher ceiling;
- used sample-weighted summaries despite large GEO study-size imbalance.

The current experiment exists to replace, not refine, those numbers.

## Corrected Frozen Protocol

### Cohorts

- **Full diagnostic:** 667 samples, 331 human / 336 mouse. Ordered sample-ID
  SHA256: `84c607dd83f93964430877f572291836fddd7315dd4f7eae3bcbf12f70fc0d65`.
  It is sample-disjoint but overlaps training GEO series, so it is not an
  unseen-study OOD cohort.
- **Strict sensitivity:** reconstructed every V2/V3 train+validation split and
  excluded the global union of whitespace-tokenized GEO series. Remaining: 103
  samples, 50 human / 53 mouse. Ordered SHA256:
  `e52a695f5e518be24803dcb1fba266c7a67b7d4696520dba35466f5f38da2b18`.

### Evaluation

- Explicit raw-TPM validation followed by exactly one `log1p` transform.
- Training-matched 30% mask rate and one deterministic shared mask artifact.
- Connected GEO-series components remain together across cross-validation folds.
- Out-of-fold fixed blend and true-species metadata hard/soft routers.
- Separate hard Pearson oracle, hard MSE oracle, and exact per-sample soft
  convex MSE oracle.
- Exact mixed-model training-row global and species gene means; no test-derived
  baseline.
- Primary estimate: equal study weight within species, then equal species
  weight. Confidence intervals use paired clustered bootstrap.
- Cross-scale comparison requires identical sample order, folds, common genes,
  masks, and sample filters. Cross-scale residual-Pearson differences are not
  reported because 5k and 20k have different train-derived centering profiles.

### Interpretation Guardrails

- The true-species soft router is a metadata-conditioned ceiling, not a learned
  blind gate for RNA-seq with unknown species or organ. `train_moe.py` is only an
  older softmax proof of concept and is not part of the corrected overnight path.
- Beating the one pooled `mixed` expert measures ensemble benefit. Adaptive MoE
  usefulness requires the metadata soft router to beat the out-of-fold fixed
  blend on strict 20k: positive absolute-MSE CI plus at least 3% relative MSE
  reduction is promising; at least 5% plus positive residual-Pearson CI is
  practically convincing. The soft oracle must also clear 3% to establish a
  meaningful routing ceiling.
- The pooled mixed model is not parameter, training-exposure, or inference-cost
  matched to a three-model ensemble.
- The strict cohort is cleaner but only 103 studies; wide intervals are expected.
- The current mixed V3 run inherited species-contiguous row-group batch order.
  A weak mixed result cannot by itself establish that MoE fails. Correcting and
  retraining that control is the first follow-up before a definitive claim.

## Validated Artifacts

- Current local suite: 41/41 passing, including adaptive-usefulness thresholds,
  blind-gate leakage checks, and organ-manifest invariants. Python and shell
  syntax checks and `git diff --check` pass.
- Versioned result summaries:
  `artifacts/stage1_5_blind_gate/report.json` and
  `artifacts/stage2_organ_pilot/`.
- Local and central evaluator source SHA256 values match.
- Real 5k and 20k snapshots load through the final evaluator with 15,448 genes,
  `log1p_tpm`, mask ratio `0.3`, and mask token `-10`.
- 5k exact mean: 4,000 train rows (2,024 human / 1,976 mouse), artifact SHA256
  `2cef96f9cd0eb52c2e0ee527183880d86fce6e300c82350d7f7f5282b533fd77`.
- 20k exact mean: 16,000 train rows (7,989 human / 8,011 mouse), artifact SHA256
  `35bfe19a9a5d4f3c84279cdb88219e1720384080169ae658a64d332ed56ad51f`.

Selected 5k checkpoint MD5s, identical locally and on `moe-reboot`:

- human: `9de5e05bc66efd253b50063bf3810a90`, epoch 30, val `0.4290946`
- mouse: `a8276b020808a08eeabf581333a7b448`, epoch 19, val `0.5165973`
- mixed: `fdea7d4d16e4f0e6d58ab152a8c83edb`, epoch 20, val `0.8046928`

Pre-completion 20k snapshots are checksum-verified on the Mac and central
persistent storage, so completed training hours are already recoverable:

- human epoch-13: `079aac312215539be8e259363912bd61`
- mouse epoch-14: `07d2714f85d2f2807bae3a82bc7b4227`
- mixed epoch-13: `2f11bc192701b006437d6997281715cc`

## Completed Overnight Automation

- All three final V3 checkpoints and metadata archives are checksum-verified on
  the Mac and persistent `moe-reboot` storage. Human and mouse workers are safe
  to shelve.
- Corrected 5k/20k full and strict evaluations completed, the copied bundle
  passed frozen hash/schema validation, and the timestamped report was generated.
- All backup/evaluation/report/Git watchers exited. Final markers include
  `ALL_SAFE_TO_SHELVE`, `EVALUATION_COMPLETE_AND_VALIDATED`, `REPORT_READY`, and
  `GIT_BACKUP_PUSHED`.
- The completed Stage 1 code, reports, and interpretation are pushed to
  `origin/main`.
