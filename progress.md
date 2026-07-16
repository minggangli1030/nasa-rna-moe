# NASA RNA MoE: Progress and Operating Context

**Last updated:** 2026-07-16 12:50 PDT / 2026-07-16 19:50 UTC

This is the compact handoff document for the current experiment. Older detailed
logs remain recoverable in Git history through commit `10a5e0e`; obsolete
evaluation numbers are intentionally not repeated as current evidence.

**Vocabulary:** `Stage` is the research phase: **Stage 0** is inherited
human/mouse/mixed completion, **Stage 1** is the original organ-specialization
work, and **Stage 2** is transfer-validated label-free discovery. `V1/V2/V3`
remain independent data/model/debugging generations inside Stage 0; they are not
renumbered. `D1/D2/D3` remain candidate research directions.

## Current Objective

The core Stage 0 interspecies training, backup, evaluation, reporting, and Git
archival are complete. The next objective is to close the final fair pooled
Stage 0 control while
beginning a bounded Stage 1 human-organ pilot:

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

### Stage 1 -> Stage 2 decision snapshot (frozen 2026-07-15)

- **Current decision: definitive Stage 1 is NO-GO; pipeline smoke testing is
  allowed.** The five specialist training sets contain only 783 brain, 409 skin,
  345 liver, 241 lung, and 220 colon rows, with 7-15 final-test connected groups
  per organ. At least 94/2,856 manifest rows match obvious residual exclusion
  terms or ambiguous cell-source descriptions. The cohort must be cleaned and
  expanded before a biological MoE conclusion.
- **Green boundary for the primary Stage 2 experiment:** zero connected-study
  leakage; deterministic masks and exact pooled/specialist sample equality;
  healthy pooled and specialist backbones; three seed-stable runs; true-organ
  routing over pooled by at least 5%; organ-fixed over matched random-fixed by at
  least 3%; soft oracle over organ-fixed by at least 3%; and blind top-1 over
  pooled by at least 5%, with positive MSE/residual-Pearson intervals and at
  least 80% recovery of the true-organ gain.
- **Conditional branches:** if specialists and oracle pass but the blind router
  fails, run only selected controlled-transfer confirmations and repair the
  router. If oracle complementarity exists but organ identity fails against
  pooled/random controls, permit only a bounded label-free feasibility pilot.
  If the backbone, provenance, strict-study result, oracle headroom, or seed
  stability fails, stop Stage 2 and repair Stage 1.
- **Post-green execution order:** emit a machine-readable Stage 1 decision;
  freeze equal-budget transfer blocks; run one development-only affinity screen;
  preregister positive, negative, and near-zero pairs; confirm `A1+A2` versus
  `A1+B1` across three seeds; validate the shared-trunk architecture with
  supervised and random routing; run the frozen-trunk label-free MoE; then test
  route-transfer agreement and route-derived grouping function on the untouched
  discovery lockbox.

The authoritative thresholds, code gaps, artifact contracts, compute guardrails,
and exact proposed command order are backed up in
`stage1-stage2-experiment-plan.md`. Its commands marked `PLANNED` describe files
that must still be implemented; they are not runnable today.

### Research scheduling note (late 2026, evidence first)

A late-2026 submission window (roughly September-December) is a useful horizon,
not a reason to force a paper before the central results exist. Stage 1 cohort
quality, the end-to-end organ experiment, and a bounded Stage 2 feasibility pilot
remain the decision gates. Reassess venues only after those results establish a
defensible claim; until then, spend writing effort on protocols, experiment logs,
and the continuously updated citation ledger in `related-works.md`. Do not tune
cohort rules, claims, or success criteria to meet a venue date.

NASA OSDR is secondary because the current OSDR cohort is mouse-only. It cannot
serve as the primary interspecies-routing benchmark.

## Current Runtime Status

- `moe-reboot` is the only active VM. `moe-reboot2` and
  `moe-reboot-partial` are shelved and are not referenced by current work.
- The corrected pooled control is running in remote tmux session
  `mixed20k_shuffled_20260715`. It uses the same 16,000 train / 3,200
  validation rows and V3 architecture, but `data_mode=preload` makes the
  `DistributedSampler` shuffle individual rows globally. Remote preflight found
  1,983/2,000 epoch-0 batches contained both species. At 21:32 UTC on July 16 it
  was at epoch 12, batch 1,000/2,000, at about 4.11 seconds/batch and 100% A100
  utilization. The latest finalized best is epoch 11, validation loss `0.324663`,
  versus `0.5455396` for the original mixed V3 checkpoint. The live estimate is
  roughly 8.4 hours to training completion, around 22:55 PDT July 16 / 05:55 UTC
  July 17, followed
  automatically by freeze and frozen evaluation.
  Logs are in `results/mixed_20k_v3_shuffled_train.log`; checkpoints write
  directly to persistent
  `/media/volume/moe-reboot/checkpoints/mixed_20k_v3_shuffled`.
- Remote tmux session `mixed20k_shuffled_eval_watch_20260715` is waiting for a
  clean training exit. It will immediately run full, strict, and blind-gate
  evaluation with the frozen sample order and masks, write separate shuffled
  result directories, and refuse to overwrite any existing output.
- Remote tmux session `mixed20k_shuffled_freeze_watch_20260715` is independently
  waiting for the same clean training exit. It will atomically copy the completed
  checkpoint directory to persistent
  `checkpoints/mixed_20k_v3_shuffled_frozen`, verify every copied file with
  SHA256, and refuse to overwrite an existing freeze.
- The July 16 ten-minute update is ready in
  `presentation/2026-07-16-biweekly.html`, with timed notes in
  `presentation/2026-07-16-biweekly-script.md`. Reorganized 2026-07-15 into a
  ten-slide arc: slides 1-2 recap last semester and last week's apparent negative
  result for anyone who missed that meeting; slides 3-5 present the corrected
  Stage 0 headroom result, blind gate, and bounded interpretation; slides 6-8 the
  overarching goal and fair Stage 1 organ design, with
  slide 7 the near-full-bleed PaperPlot figure
  (`presentation/human-organ-moe-overarching-plan.png`, source prompt
  `presentation/paperplot-human-organ-moe-prompt.md`) with the embedded labels
  corrected to Stage 0/Stage 1 and the hard 32.94% result, beneath the exact fair
  comparison question; slide 9 the related-work novelty boundary and D1/D2/D3
  experiment choice; and slide 10 the selected gated Stage 2 experiment:
  controlled transfer, label-free routing, and a held-out agreement/functional test. Slide 8 now
  separates cohort, smoke-test, and Stage 2 decision gates. The current pooled
  retrain remains labeled ongoing on slide 5 and in the script.
  Desktop (1440x900), laptop (1280x720), and mobile (390x844) render checks passed
  after this reorganization: the desktop/laptop slides have no clipping, and
  mobile uses vertical scrolling without horizontal overflow. The HTML contains
  ten balanced slide sections. Repository validation also passes 41/41 tests;
  the four emitted warnings are existing PyTorch AMP deprecations.
- Keep `moe-reboot-partial` shelved for now. The active shuffled 20k control is
  the decision-critical GPU experiment; organ progress is currently limited by
  manual label/QC work and evaluator preparation, not compute. Reassess the
  partial VM after shuffled evaluation determines whether the next GPU run
  should be a replication/control or a frozen-cohort Stage 1 pilot. If it is
  reused, write all checkpoints and results directly to persistent storage
  because the partial VM is ephemeral.
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
  organs: brain, skin, liver, colon, and lung. The organ-pilot manifest has 2,856 samples,
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

## Stage 1 Hypothesis and Experimental Design

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

The primary Stage 1 claim is practically convincing only if blind top-1 routing:

1. beats the pooled general model by at least 5% relative MSE reduction;
2. has a paired absolute-MSE improvement CI with lower bound above zero;
3. has a residual-Pearson improvement CI with lower bound above zero; and
4. recovers at least 80% of the true-organ hard-routing improvement over the
   pooled model, using the same strict test samples.

Biological specialization additionally requires the organ fixed ensemble to beat
the random-shard fixed ensemble by at least 3% relative MSE with a positive
absolute-MSE CI. Adaptive soft-routing evidence requires blind soft routing to
beat the organ fixed ensemble by at least 3% with a positive absolute-MSE CI.
Organ-classifier accuracy is diagnostic, not a substitute for end-to-end
reconstruction performance.

## Stage Transition Decision

Stage 0 is strong enough to begin Stage 1 dataset auditing, cohort freezing, and
a small organ pilot now. The strict result is large, statistically separated from
zero, present under hard routing, and stronger at 20k, so further species-only
ceiling analysis has diminishing value.

Two Stage 0 experiments were required before a definitive Stage 0 claim or a
full-scale `K`-organ training campaign:

1. **Blind species gate: complete.** The expression-only gate recovers almost all
   of the true-species ceiling and strongly beats both the pooled model and fixed
   ensemble on the strict study-disjoint cohort.
2. **Corrected pooled mixed retrain: running.** Global row shuffling removes the
   known V3 pooled-control weakness; rerun the frozen evaluation after its best
   checkpoint is finalized.

The successful blind gate is strong enough to continue organ metadata cleanup
and pipeline development. The active pooled retrain and organ label validation
still block the strongest publication claim and major Stage 1 compute spending.

## Active Run Completion Runbook

This section is the source of truth for the next agent. Do not launch a duplicate
training, freeze, or evaluation process without checking these states first.

### First status check

Run from a machine with the existing SSH alias:

```bash
ssh moe-reboot 'cd /home/exouser/nasa-rna-moe && \
  date -Is && nvidia-smi && tmux list-sessions && \
  tail -30 results/mixed_20k_v3_shuffled_train.log && \
  cat results/mixed_20k_v3_shuffled_freeze.status && \
  cat results/mixed_20k_v3_shuffled_eval.status'
```

Expected while training: three tmux sessions named
`mixed20k_shuffled_20260715`, `mixed20k_shuffled_freeze_watch_20260715`, and
`mixed20k_shuffled_eval_watch_20260715`. Both watchers should say
`WAITING_FOR_TRAINING`. Closing the local terminal/computer does not stop them.

### Automated sequence after training

1. `runs/train_mixed_20k_v3_shuffled.sh` writes the best checkpoint under the
   persistent `checkpoints/mixed_20k_v3_shuffled` directory and writes
   `results/mixed_20k_v3_shuffled_train.exit_code` when the tmux wrapper exits.
2. `runs/freeze_shuffled_mixed_when_complete.sh` requires exit code zero and
   `best_model.pt`, copies the entire stable checkpoint directory through an
   `.incomplete` staging directory, verifies `SHA256SUMS`, and creates:
   - `checkpoints/mixed_20k_v3_shuffled_frozen/`
   - `results/mixed_20k_v3_shuffled_freeze.COMPLETE`
   - `results/mixed_20k_v3_shuffled_freeze.status`
3. `runs/evaluate_shuffled_mixed_when_complete.sh` independently requires the
   same clean exit and checkpoint, then runs:
   - corrected full-cohort inference with the original frozen mask;
   - strict 103-study analysis from that cache;
   - the leakage-protected blind species gate on the new three-expert cache;
   - frozen mask, sample count/order, and checkpoint-path validation.
4. Successful evaluation creates:
   - `results/interspecies_headroom_20k_v3_shuffled_corrected/report.json`
   - `results/interspecies_headroom_20k_v3_shuffled_strict_study_disjoint/report.json`
   - `results/blind_species_gate_20k_v3_shuffled/report.json`
   - `results/mixed_20k_v3_shuffled_eval.COMPLETE`
   - `results/mixed_20k_v3_shuffled_eval.status`
   - `results/mixed_20k_v3_shuffled_eval.log`

The watchers do **not** update `progress.md`, `report.md`, the presentation, or
Git, and they do not copy reports back to the Mac. Those are required manual
post-completion steps below.

### Stage 0 decision after shuffled evaluation

Use the **strict 103-study result** as primary; full-cohort results are diagnostic.
In `results/blind_species_gate_20k_v3_shuffled/report.json`, inspect
`blind_soft_vs_fixed`, `blind_soft_vs_mixed`, `metadata_soft_vs_fixed`, and
`soft_oracle_vs_fixed`.

- **Practically convincing Stage 0:** blind soft beats both the out-of-fold fixed
  blend and shuffled pooled model by at least 5% relative MSE; both absolute-MSE
  CIs have lower bounds above zero; blind-soft residual-Pearson versus fixed has
  a CI lower bound above zero; and soft oracle versus fixed clears 3%.
- **Promising but not yet practical:** blind soft beats fixed with positive
  absolute-MSE CI and at least 3% relative MSE, but misses the 5% or
  residual-Pearson criterion.
- **Ensemble-only benefit:** blind routing beats the pooled model but not the
  fixed blend. Do not describe this as useful adaptive MoE routing.
- **Adaptive ensemble benefit but no general-model win:** blind routing beats
  fixed but not the shuffled pooled model. The router improves the ensemble but
  is not a better practical system than the fairer general control.
- **No meaningful routing ceiling:** soft oracle versus fixed is below 3% or its
  absolute-MSE CI includes zero. Stop gate tuning and revisit expert/data design.
- **Study-generalization failure:** a positive full-cohort result disappears on
  strict. Treat this as study leakage/domain dependence, not evidence for MoE.

Classifier accuracy/AUC is secondary. The deployment claim is reconstruction
improvement from a gate that sees only masked expression.

### Required manual steps after both COMPLETE markers

1. Verify both exit codes are zero and run `sha256sum -c` inside the frozen
   checkpoint directory once more.
2. Record best epoch, train/validation loss, checkpoint SHA256, runtime, and the
   three strict comparisons above.
3. Copy the small report JSON files, freeze metadata, and SHA256 manifest to a
   new local `artifacts/stage0_shuffled_control/` directory. Do not commit model
   weights to Git.
4. Compare old versus shuffled pooled MSE on identical strict samples and state
   whether the Stage 0 conclusion survives. Do not compare different masks,
   cohorts, or estimands.
5. Append a timestamped result to `report.md`; update current status and decision
   in `progress.md`; replace the slide 5 current-run sentence only if the complete
   frozen evaluation is available.
6. Run syntax checks, focused tests, the full suite, and `git diff --check`, then
   commit and push. The current baseline is 41/41 tests.
7. `moe-reboot` is safe to shelve only after training, freeze, and evaluation
   have all exited and both COMPLETE markers/checksums are verified. Persistent
   volume paths must resolve before shelving.

### Failure recovery without destroying artifacts

- **Training exit nonzero:** both watchers intentionally become `BLOCKED`. Keep
  every checkpoint and inspect the training log. Resume only from the newest
  verified per-epoch file under
  `checkpoints/mixed_20k_v3_shuffled/<run_id>/epoch_*.pt` using
  `RESUME_FROM=<path>` with `DATASET_VARIANT=mixed_20k_v3_shuffled`. Launch the
  resume under tmux and point new versioned watchers at its exit marker; never
  delete or overwrite the failed run.
- **Freeze FAILED/BLOCKED:** inspect
  `results/mixed_20k_v3_shuffled_freeze.log` and any `.incomplete` directory.
  Verify the source checkpoint before moving the incomplete copy to a timestamped
  quarantine path and starting a versioned retry. Do not remove it blindly.
- **Evaluation FAILED:** inspect `results/mixed_20k_v3_shuffled_eval.log` first.
  The watcher refuses to overwrite partial output directories. Preserve them by
  moving them to timestamped diagnostic names, correct the underlying issue,
  then use new versioned output paths for a retry. Reuse the exact frozen masks
  and strict IDs.
- **Watcher missing while training continues:** training is independent. Recopy
  the committed watcher script and relaunch only the missing tmux session after
  confirming no process with the same script is alive.

## Stage 1 Organ Execution Runbook

Do not launch the definitive organ models from the current organ-pilot manifest.
It is sufficient for pipeline smoke testing but still contains label ambiguity
and only 220-783 training rows per specialist.

### Cohort readiness gate

Before a definitive GPU campaign:

1. retain enough raw metadata to audit each label, including characteristics;
2. replace or supplement regex labels with ontology-backed normalization;
3. exclude cell lines, cultures, organoids, xenografts, tumors, ambiguous organs,
   and connected study groups spanning multiple organ labels;
4. manually review at least 50 stratified samples per selected organ and require
   at least 95% label precision before freezing;
5. require at least 1,000 clean training samples and 30 independent training
   study groups per included organ for the definitive run; organs below this can
   remain in a smoke test but must not drive the primary claim;
6. choose `K` only from these preregistered availability rules, not from model
   performance; and
7. freeze sample order, connected-group splits, hashes, exclusions, and the exact
   pooled/specialist union before training.

### Ordered implementation plan

1. **Label audit and expansion:** extend `evaluation/audit_archs4_organs.py` to retain
   auditable metadata and produce stratified manual-review sheets. Resolve GBM,
   HSAEpC, tumor acronyms, and tissue-versus-derived-cell ambiguity. Rerun
   `evaluation/build_organ_pilot_manifest.py` only after the rules are frozen.
2. **Exact dataset extraction:** implement a manifest-driven extractor from the
   human ARCHS4 H5 into the shared 15,448-gene raw-TPM space. It must assert no
   duplicate sample IDs, no train/calibration/test study overlap, identical gene
   order, and exact equality between pooled train IDs and the union of specialist
   train IDs. This extractor does not yet exist.
3. **Training controls:** train one pooled human model on the exact union, `K`
   organ specialists on disjoint partitions of that union, and `K` size-matched
   random-shard experts. Use the same architecture, optimizer, mask rate, epoch
   exposure, gene order, and globally shuffled pooled batches. Store/freeze each
   run on persistent storage with hashes.
4. **Frozen evaluation:** implement an organ evaluator using the corrected
   interspecies conventions: exactly one `log1p`, one deterministic 30% mask,
   train-only gene mean, study-macro estimand, paired clustered bootstrap, and
   strict study-disjoint test. Required conditions are pooled general, random
   fixed ensemble, organ fixed ensemble, true-organ hard/soft, blind top-1/soft,
   and per-sample soft oracle.
5. **Blind gate:** train/calibrate only on calibration studies. The gate receives
   the same masked expression as the expert, never hidden target values. True
   organ labels may supervise calibration but are unavailable at test. Include a
   confidence threshold and pooled-model fallback for ambiguous/out-of-taxonomy
   samples.
6. **Progressive smoke before scale:** use the three-rung design below. Each rung
   has a different purpose; do not treat a mechanical smoke result as biology.
7. **Definitive run and decision:** launch only after the readiness gate and
   smoke tests pass. Apply the preregistered criteria below without tuning them
   after seeing test outcomes.

### Approved progressive Stage 1 pilot design

1. **Micro overfit test:** use 64-128 samples and 20-50 updates to verify target
   hiding, loss decrease, gradient flow, deterministic masks, checkpoint resume,
   and cached-prediction identity.
2. **Five-organ mechanical smoke:** use the current `K=5` manifest, one seed, and
   approximately 50 updates per model. Exercise pooled, five organ specialists,
   matched random shards, fixed blend, true-organ routing, blind routing, and
   oracle evaluation end to end. Passing means the machinery is correct; the
   result has no biological interpretation.
3. **Two-organ feasibility pilot:** after removing obvious label failures, select
   brain and skin prospectively because they have the greatest sample/study
   support. Use the production backbone, matched 3-5 epoch exposure, and seeds
   17, 42, and 101. Compare pooled, organ specialists, and size/study-matched
   random shards using one frozen mask and equal-organ/equal-study macro metrics.
   This estimates wall time, seed variance, oracle headroom, and whether the
   longer definitive campaign is worth running.

The current pilot test studies are engineering data and become burned after this
inspection. A definitive Stage 1 cohort must receive newly frozen model-validation,
gate-calibration, final-test, and discovery-lockbox partitions after label cleanup
and expansion. Approximate 5%/3% effect thresholds guide feasibility, but only the
powered definitive run supports a biological claim.

### Stage 1 outcome interpretation

- **Full success:** all primary blind-top-1 criteria pass, organ fixed beats
  random fixed, and blind routing recovers at least 80% of the true-organ hard
  ceiling. This supports an accurate, inference-efficient organ MoE, with extra
  storage reported as a cost.
- **Experts work, gate fails:** true-organ routing passes but blind routing does
  not. Improve router inputs/calibration or fallback logic; do not retrain experts
  first unless their ceiling is also weak.
- **Generic ensemble only:** organ fixed does not beat random fixed. Any gain is
  attributable to sharding/ensembling, not organ biology.
- **No organ specialization:** true-organ hard routing fails to beat pooled by
  at least 5% with positive MSE/residual intervals. Revisit labels, data scale,
  organ granularity, or architecture; do not claim transfer from Stage 0.
- **Statistically positive but practically small:** MSE CI is positive but the
  primary gain is below 5%. Report it as preliminary and do not scale solely on
  that basis.
- **Strict-only failure:** full cohort passes but strict study-disjoint test does
  not. Treat as study/domain leakage and improve cohort diversity.
- **Efficiency failure:** accuracy passes but top-1 inference is not roughly one
  expert plus a small gate, or fallback activates excessively. Report as an
  ensemble result rather than an efficient MoE system.

### Stage 1 artifacts already available

- Audit code: `evaluation/audit_archs4_organs.py`
- Manifest builder: `evaluation/build_organ_pilot_manifest.py`
- Pilot reports/manifest: `artifacts/stage1_organ_pilot/`
- Overarching figure prompt:
  `presentation/paperplot-human-organ-moe-prompt.md`
- Current organ pilot: brain, skin, liver, colon, lung; 2,856 samples; 317 groups;
  exact pooled/specialist train-union hash
  `332760cf8ca98535e3d0a4f3548e733a0723d6c8ea985e4268e9a7c06990c35d`.
- A 2026-07-15 cap-sensitivity check on the same conservative candidates, after
  tumor and multi-organ-group exclusion, confirms that simply raising the
  per-study cap does not rescue the definitive `K=5` cohort. At cap 60, capped
  totals are brain 2,039, skeletal muscle 1,246, skin 971, liver 707, adipose
  670, colon 446, and lung 418; an approximate 70% training allocation leaves
  only brain above 1,000. Removing the cap would let a few organs cross 1,000
  but reintroduces severe single-study dominance. The practical options are
  ontology-backed label expansion, a prospectively justified lower threshold,
  or a smaller `K`—never a post-result threshold change.

## Stage 2 Research Direction (prepare during Stage 1; run after readiness gates)

### Scientific aim

Use MoE specialization as a probe of what structure a masked RNA-seq model learns:
which human expression domains should share parameters, which interfere, and whether
label-free routing recovers reproducible biological programs that were never supplied
as training labels. The organ interference matrix remains valuable, but it is an
anchor measurement rather than the entire Stage 2 claim.

Stage 1 remains the immediate priority and the calibration experiment: first establish
whether explicit, audited organ specialists and a blind gate beat the fair pooled and
random-shard controls. Stage 2 infrastructure, deterministic smoke tests, a separate
lockbox, and a small variance/cost pilot may be prepared in parallel. Definitive
Stage 2 analyses must not inspect a test set already used to choose a Stage 1 story.

The organ strata all optimize the same masked-reconstruction objective, so describe
D1 precisely as **cross-domain transfer/interference**, not literally distinct-task
multi-task learning. Task-affinity methods are methodological ancestors, not evidence
that the biological result is already known.

### Practicality and novelty decision

Claude's full pairwise D1 is not the unconditional default. The current best bet is a
**hybrid**: use a cheap development-only gradient-affinity screen to identify likely
positive and negative transfer edges, confirm a small number with controlled pair
training, and ask whether a label-free MoE independently learns the same grouping.
Scale to a full matrix only if the cohort and pilot justify it.

| Candidate | Novelty if successful | Data / implementation | Compute / storage | Decision |
|---|---|---|---|---|
| Full `K x K` organ transfer matrix | Moderate: useful genomics measurement, but task/domain affinity is established | Needs at least four well-powered organs and all Stage 1 infrastructure | Roughly 60-105+ seeded runs; current 434 MB checkpoints make per-epoch retention infeasible | Conditional follow-up, not first Stage 2 run |
| Gradient-affinity screen + selected pair confirmation | Moderate alone; strong as a bridge from optimization to biology | One balanced pooled development run plus 2-4 prespecified pairs | Approximately 10-20 runs including seeds/controls | Recommended D1 implementation |
| Label-free shared-trunk MoE | Higher upside: asks whether routing discovers stable RNA-seq structure without organ labels | Can use the full clean pooled cohort; requires a new router/expert path and strict batch controls | Frozen-trunk pilot first; at least three full-cohort runs only after its gate | Recommended Stage 2 core pilot |
| Hierarchical organ -> latent-state MoE | High discovery upside if it finds a replicated within-organ program rather than rediscovering tissue | Brain is currently the only plausible first organ; requires curated disease/age/treatment/sex/composition metadata and independent studies | Small `K=2-3`, but validation and metadata work dominate | Conditional follow-up after the label-free pilot, not an immediate run |
| Pathway- or cell-type-supervised experts | Lower discovery value because the answer is injected through labels; mature neighboring literature | Requires external annotations/deconvolution and a different task definition | Moderate | Interpretation control only |

The exciting claim is not "MoE works on RNA-seq." It is that label-free routing finds a
reproducible biological organization, that the organization predicts measured transfer,
and that it improves reconstruction under fair active-compute controls. If only the
first or second component holds, narrow the claim accordingly.

### D1 — Directed organ transfer graph (screen first, confirm selected edges)

First estimate a directed domain-affinity graph on development studies during one
balanced pooled-training run: measure how an update from donor-domain `B` changes the
held-out development loss for recipient `A`, following established gradient-affinity
work. Use this only to screen and preregister a small number of strongest positive,
negative, and near-zero pairs. Confirm those edges by training joint `A+B` models and
evaluating on a fixed, study-disjoint test set for `A`. One unordered pair model supplies
both directions, but the effects need not be symmetric. The screen is not a substitute
for actual pair-training confirmation.

**Estimands and sign (freeze before results).** Let `L_A(f)` be study-macro masked MSE
of model `f` on recipient `A`. Positive values always mean beneficial transfer:

```text
raw_transfer[A <- B] = (L_A(f_A) - L_A(f_A+B)) / L_A(f_A)
controlled_transfer[A <- B] =
    (L_A(f_A1+A2) - L_A(f_A1+B1)) / L_A(f_A1+A2)
```

For the primary controlled comparison, split eligible development/training studies
within each organ into fixed blocks. `A1+A2` and `A1+B1` have matched sample counts,
study-count targets, optimizer updates, and sampling weights. This changes the question
from "does adding any data help?" to "is the same budget better spent on another block
of the recipient or on donor `B`?" If an organ cannot supply a credible `A2` reserve,
omit the confirmatory cell rather than silently substitute an unmatched global pool.
Also report two transparent secondary controls:

1. an `A1`-replay exposure control, which controls optimization budget but not the
   information in new unique samples; and
2. deterministic matched random-pseudogroup blocks, which test whether apparent
   structure arises from arbitrary sample sharding rather than organ identity.

**Protocol requirements.**

1. Freeze a global connected-study split and a discovery lockbox before Stage 1 test
   inspection. No recipient or donor test study may enter any model's training,
   validation, gate calibration, or reference-donor pool.
2. Require a prospective test-study/power gate per recipient; the current 7-15 test
   groups per organ are not automatically adequate for 20 off-diagonal comparisons.
3. Fix optimizer updates, recipient:donor sampling ratio, loss weighting, LR schedule,
   deterministic validation mask, and checkpoint-selection rule. Equal epochs are not
   an equal exposure budget when pair datasets differ.
4. Use at least three explicit training seeds for definitive cells. Clustered bootstrap
   over test studies measures cohort uncertainty but not model-training stochasticity;
   report both. Apply Benjamini-Hochberg to the `K(K-1)` off-diagonal hypotheses, not
   structural diagonal cells, and preregister a practical effect threshold.
5. Report absolute and recipient-standardized effects, train-only organ gene-mean and
   pooled baselines, residual correlation, and gene-module-stratified errors. Otherwise
   a heatmap may mostly rediscover organ expression means.
6. Test an omnibus organ-identity effect against the pseudogroup null before treating
   individual edges as biological. Add leave-one-organ-out models or use the
   development-only affinity graph to choose grouped
   experts and validate that grouping on the untouched lockbox. Pairwise effects alone
   do not establish the higher-order behavior of a full pooled model.

**Cost gate.** The earlier 15-25-run estimate was too optimistic. At `K=5`, five solo
models, ten pair models, controls, and three seeds can easily become 60-105+ runs. A
current inference/training checkpoint is about 434 MB, so retaining per-epoch files for
that grid would also exceed the 117 GB currently free on the central volume. First run
one two-organ, three-seed pilot; measure wall time and seed variance; keep only
checksum-verified best/last inference artifacts plus compact histories; then freeze a
complete run table and compute/storage budget. The default is to confirm selected edges,
not to launch the full grid.

### D2 — Label-free MoE routing as a biological representation probe

This is the linked discovery experiment, not a claim that can be made from the current
organ experts. Experts trained from organ labels can validate a gate, but they cannot
show that organ or hidden biological structure *emerged*.

1. Reuse `ExpressionPerformer` through its final hidden states as a shared trunk. Pool
   only observed-gene hidden states to drive a sample-level router; attach `K` small
   residual FFN adapters plus scalar reconstruction heads. Train soft routing first and
   evaluate top-1 dispatch, with an explicit load-balancing term and capacity limit.
   Do not provide organ, study, platform, disease, or other phenotype labels to the
   router or experts. Choose `K`, balancing strength, and adapter size on development
   studies only.
2. Use a two-step feasibility path: first freeze a Stage 1 pooled trunk and train only
   adapters/router (cheap test of routing signal); then fine-tune the full model only if
   routes are non-collapsed and cross-study stable. The current `train_moe.py` blends
   frozen, predefined expert predictions and cannot answer this emergence question.
3. Compare against the pooled model, matched active-parameter/FLOP controls,
   random/permuted routing, random-shard experts, and the supervised organ-expert
   ceiling. For claimed representation structure, also compare raw expression, PCA,
   NMF, and shared-trunk geometry. Track collapse, expert utilization, storage, and
   total training compute.
4. Measure routing/expert-advantage stability across seeds, masking realizations, and
   held-out studies before interpreting clusters. Evaluate every sample against every
   expert to report counterfactual routing regret, not only router assignments. Known-
   organ recovery is a positive control, not a hidden discovery.
5. Test whether routing aligns with study, platform, library size, and other technical
   variables. A route that identifies GEO study or processing protocol is a confound,
   not biology. Require cross-study replication and conditional analyses within organ;
   retain multi-organ studies when a global group split can use them as technically
   valuable controls.
6. Attribute route decisions to observed genes, test frozen pathway/gene-program
   enrichments, and validate any beyond-organ pattern against independent metadata or
   an external cohort. Findings chosen after looking remain explicitly exploratory.
7. Compare the learned route co-assignment graph with D1 transfer effects on held-out
   data. The strongest joint result would be that label-free routes group domains that
   demonstrably transfer, and separate domains that interfere.

**Claim ladder.**

- If routing is unstable across seeds or dominated by study/platform, make no latent-
  biology claim.
- If it reproducibly recovers only organ, report recovery of known tissue structure as
  validation, not discovery.
- A hidden-pattern claim requires a stable beyond-organ association, technical-confound
  controls, pathway-level interpretation, and independent replication.
- A useful MoE claim additionally requires reconstruction improvement over the fair
  pooled/random controls at matched active inference compute; interpretability alone
  does not establish a better predictive system.

**Conditional within-organ discovery branch.** If the first label-free router mostly
recovers the dominant organ axis, do not call that hidden biology. If brain remains the
only sufficiently powered organ, a later `K=2-3` brain-only pilot may remove/condition
on organ identity and ask whether routes reproduce a disease, age, treatment, cell-
composition, or pathway state across independent studies. Freeze the route definition
before metadata association, require within-study and cross-study replication, and
compare against PCA/NMF/clustering baselines. Do not start this branch until the relevant
metadata are curated well enough to distinguish biology from study design.

### Ordered Stage 1 -> Stage 2 execution

1. **Cohort feasibility and audit:** retain auditable metadata, validate labels, and
   determine `K` from frozen quality/study/power rules. The current pilot fails the
   definitive 1,000-training-sample rule for every organ and is not a final cohort.
   Reconsider automatic deletion of multi-organ studies: keep them when sample labels
   are valid and assign the entire connected group to one split; they provide unusually
   strong within-study technical controls.
2. **Split design:** prefer study-disjoint model-validation and discovery-lockbox
   partitions distinct from gate calibration and final Stage 1 test. If study counts
   cannot support a separate lockbox, freeze all Stage 2 hypotheses before the first
   Stage 1 test access and require independent external replication for discovery claims.
3. **Shared infrastructure:** implement the manifest-driven extractor, manifest-aware
   seeded trainer, deterministic evaluator, and artifact/run manifests with code/data/
   split hashes.
4. **Smoke and variance pilot:** run schema tests, then a two-organ, three-seed pilot
   solely to estimate variance, power, and cost. Do not elevate pilot biology to a
   claim.
5. **Definitive Stage 1:** run the preregistered pooled, random-shard, organ-specialist,
   metadata, blind-gate, and oracle ladder.
6. **Stage 2 screen:** compute development-only gradient affinity, preregister selected
   positive/negative/null edges, and run their matched-block confirmation. Do not infer
   biology from the screen alone.
7. **Label-free pilot:** run the frozen-trunk adapter/router experiment if Stage 1
   infrastructure is stable; scale it only if routes are non-collapsed, cross-study
   stable, and not explained by technical metadata.
8. **Expansion decision:** build the full D1 matrix only if the selected-edge pilot is
   seed-stable, clears the practical-effect threshold, and the powered organ count is
   sufficient. Otherwise spend compute on replication and biological validation of the
   smaller, stronger result.

The exact Stage 1 decision boundaries, current code gaps, proposed CLI contracts,
artifact schema, and post-Stage-1 command order are in
`stage1-stage2-experiment-plan.md`. Commands marked `PLANNED` there are not runnable
until their named files and tests exist.

### Archived (not planned)

- **D3 — router weights as deconvolution.** Bulk RNA-seq deconvolution is a mature
  field (CIBERSORT, Scaden, and the neural/Bayesian methods in `related-works.md` D3
  block), and MoE-for-cell-type already exists (GC-MoE). Only the "emergent,
  unsupervised byproduct of reconstruction routing" framing was defensible, and it
  still competes with unsupervised deconvolution. Archived; if revisited, run it only
  as a router interpretability check benchmarked against an established method, never
  as a new deconvolution claim.
- **Data-dependent phase boundary.** A "samples-per-organ crossover where specialists
  overtake pooling" was dropped: the crossover depends heavily on dataset, organ
  granularity, and gene space, so it does not generalize into a unifiable claim.

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
  `artifacts/stage0_blind_gate/report.json` and
  `artifacts/stage1_organ_pilot/`.
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
- The completed Stage 0 code, reports, and interpretation are pushed to
  `origin/main`.
