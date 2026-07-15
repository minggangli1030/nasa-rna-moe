# NASA RNA MoE: Progress and Operating Context

**Last updated:** 2026-07-15 09:37 PDT / 2026-07-15 16:37 UTC

This is the compact handoff document for the current experiment. Older detailed
logs remain recoverable in Git history through commit `10a5e0e`; obsolete
evaluation numbers are intentionally not repeated as current evidence.

## Current Objective

Finish the human/mouse interspecies experiment before starting human-organ MoE:

1. Complete all human, mouse, and mixed V3 20k training.
2. Freeze and back up final checkpoints from ephemeral instances.
3. Evaluate corrected 5k models on a frozen human+mouse ARCHS4 holdout.
4. Evaluate 20k models on the identical samples, genes, folds, and masks.
5. Quantify routing headroom and paired 20k-minus-5k changes.
6. Append a timestamped diagnosis and future plan to `report.md`, then push Git.

NASA OSDR is secondary because the current OSDR cohort is mouse-only. It cannot
serve as the primary interspecies-routing benchmark.

## Live Overnight Status

- **All 20k training and backup complete.** Final epoch-15 checkpoints are human
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
- This is not yet a blind learned gate result. It establishes that known species
  is a useful routing variable for the frozen experts; fair pooled/sampler
  controls and a newly implemented blind gate remain required.

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

## Repository and Compute

- Local repo: `/Users/minggangli/Projects/nasa-rna-moe`
- Central persistent VM: `moe-reboot`
- Human training VM: `moe-reboot2` (ephemeral root disk)
- Mouse training VM: `moe-reboot-partial` (hostname `moe-reboot3`, ephemeral)
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

- Local test suite: 34/34 passing, including adaptive-usefulness thresholds and
  the automated report renderer.
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

## Overnight Automation

The Mac must remain powered, lid open, and online. Closing Terminal is safe;
closing the laptop lid or shutting down is not. Backup, report, and Git run in
detached macOS `screen` sessions. The evaluation watcher is an init-adopted
detached process after its obsolete screen socket was removed; it remains alive
under `caffeinate -dims` and intentionally was not restarted. All four are
independent of an open Terminal window.

### 1. `nasa_moe_backup_final`

- Waits for `Training complete!` and zero `train_single.py` PIDs.
- Downloads each final checkpoint atomically and verifies remote/local MD5.
- Archives loss history, metadata, and training logs.
- Mirrors human/mouse final models into persistent `moe-reboot` storage.
- Writes `<run>.SAFE_TO_SHELVE`; after all three, `ALL_SAFE_TO_SHELVE`.

### 2. Evaluation watcher (live detached process)

- Waits for `ALL_SAFE_TO_SHELVE`.
- Confirms `moe-reboot2` and partial have no training PID or GPU compute process;
  writes `WORKER_INSTANCES_IDLE`.
- Starts corrected evaluation on `moe-reboot` only. The launcher runs 5k first,
  then 20k, then strict subset analyses and paired scale comparisons.
- Copies the complete result bundle to the Mac and validates hashes/schema.
- Writes `EVALUATION_COMPLETE_AND_VALIDATED`.

### 3. `nasa_moe_report`

- Waits for validated evaluation.
- Appends an idempotent timestamped addendum to `report.md` containing result
  tables, paired confidence intervals, diagnosis, limitations, and future plans.
- Writes `REPORT_READY`.

### 4. `nasa_moe_git`

- Waits for `REPORT_READY`.
- Stages only repository code/docs/scripts/tests, validates the staged diff,
  commits, and retries `git push origin main` until successful.
- Data, checkpoints, results, and backup logs are explicitly Git-ignored.
- Writes `GIT_BACKUP_PUSHED` with the final commit SHA.

Monitor without attaching:

```bash
screen -ls
pgrep -af evaluate_after_20k_backup
tail -f backups/20k_v3_final/backup_watcher.log
tail -f backups/20k_v3_final/evaluation_watcher.log
tail -f backups/20k_v3_final/report_watcher.log
tail -f backups/20k_v3_final/git_backup_watcher.log
```

Do not shelve an instance until its own `SAFE_TO_SHELVE` marker exists. The final
overnight success marker is `EVALUATION_COMPLETE_AND_VALIDATED`; the final report
and Git markers are `REPORT_READY` and `GIT_BACKUP_PUSHED`.

## Decision Framework for Tomorrow

1. **Metadata soft router clears the strict fixed-blend threshold:** consider a
   new blind learned gate, but compare it with the true-species ceiling and fair
   pooled controls; no corrected blind gate exists yet.
2. **Soft oracle positive, metadata router weak:** complementary signal exists
   but is not species-aligned; learn expression state rather than species.
3. **No strict oracle headroom, models improve with scale:** species is the wrong
   specialization axis; move to organ experts after correcting the mixed control.
4. **No headroom and weak 20k models:** prioritize sampler/backbone/data quality
   before spending compute on organs or gate training.

Regardless of outcome, the next defensible controls are: globally shuffled mixed
retraining, union-data pooled training, parameter/inference-budget matching, and
profile-controlled metrics. Only then extend the same frozen-ceiling methodology
to human organs and an unknown-organ RNA-seq gate.
