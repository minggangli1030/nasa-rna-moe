# Bridge-RNA Project Report: Corrected Interspecies MoE Evaluation

**Updated:** 2026-07-15 13:16 PDT / 2026-07-15 20:16 UTC

## Executive Status

This project tests masked reconstruction of bulk RNA-seq expression with a
SLiMPerformer (`ExpressionPerformer`) and asks whether human-, mouse-, and
mixed-trained experts contain enough complementary signal for mixture routing to
beat a pooled model or a fixed ensemble.

The 20k human/mouse scale-up and corrected paired 5k-versus-20k evaluation are
complete. The result supports a practically convincing frozen, true-species
routing ceiling, while stopping short of claiming that an unknown-species blind
gate or a compute-matched production MoE has been demonstrated.

## Historical Work, Condensed

### Foundation and Independent Contribution

The repository continues Walter Alvarado's UChicago `bridge-rna` work within the
NASA Ames / Berkeley Data Discovery project. The inherited foundation includes
SLiMPerformer attention, `ExpressionPerformer`, ARCHS4 preprocessing, and the
base single-expert training loop.

This continuation added:

- NASA OSDR zero-shot evaluation and alignment diagnostics;
- human, mouse, and mixed expert variants at 5k and 20k scales;
- shared human/mouse canonical vocabulary and ortholog alignment;
- frozen-expert MoE gating and training-free routing-ceiling analysis;
- Jetstream A100 infrastructure and reproducible launchers;
- the corrected ARCHS4 holdout, study-overlap audit, exact train-only baselines,
  paired scale statistics, backup automation, and report validation used here.

Detailed chronological implementation logs remain in Git history through commit
`10a5e0e` and are summarized in `progress.md`.

### Findings That Motivated the Current Experiment

- The original mouse OSDR evaluation showed species-aligned ordering, but it is
  mouse-only and therefore cannot test interspecies routing.
- Early 5k models showed narrow generalization and output collapse toward static
  gene profiles. Scaling a v1 human model from 5k to 20k substantially improved
  validation loss and mouse-OSDR Pearson, motivating a controlled V3 scale test.
- Naive MoE was initially invalid because independently preprocessed experts had
  incompatible gene vocabularies. V2/V3 use one shared 15,448-gene vocabulary.
- A preliminary balanced ARCHS4 evaluation appeared to show little headroom,
  but its methodology was later found faulty and its numerical conclusions are
  not current evidence.

## Why the Previous Balanced Results Are Superseded

The old balanced-ARCHS4 path:

1. fed raw TPM to checkpoints trained on `log1p(TPM)`;
2. fitted blend weights on the same samples used for reporting;
3. computed the gene-mean baseline from the final test cohort;
4. treated hard expert selection as the oracle despite a soft convex gate;
5. used sample-weighted estimates despite GEO study-size imbalance.

Therefore the earlier balanced headroom and gene-mean values must not be cited as
method evidence. They are retained only in Git history as part of the debugging
trail.

## Corrected Evaluation Design

### Frozen Cohorts

- **Full diagnostic:** 667 ARCHS4 samples, 331 human / 336 mouse. It is
  sample-disjoint but contains GEO-series overlap with training, so it measures
  held-out samples rather than unseen-study OOD generalization.
- **Strict sensitivity:** exact reconstruction of all V2/V3 train+validation
  splits followed by global GEO-series exclusion leaves 103 samples, 50 human /
  53 mouse, each in a distinct connected series component.

Frozen ordered ID hashes:

- full: `84c607dd83f93964430877f572291836fddd7315dd4f7eae3bcbf12f70fc0d65`
- strict: `e52a695f5e518be24803dcb1fba266c7a67b7d4696520dba35466f5f38da2b18`

### Model-Space and Statistical Corrections

- Validate raw TPM and apply exactly one `log1p` transform.
- Use the training-matched 30% mask rate and identical masks for 5k and 20k.
- Keep connected GEO-series groups intact during cross-fitting.
- Fit fixed blends and true-species metadata routers only on other folds.
- Report hard Pearson, hard MSE, and exact soft convex MSE oracles separately.
- Use exact mixed-model training rows for global and species-specific mean
  baselines; never derive a baseline from final evaluation samples.
- Give every study equal weight within species, then human and mouse equal weight.
- Use paired clustered bootstrap intervals for headroom and scale comparisons.
- Require identical sample, gene, fold, mask, and filter identities before a
  20k-minus-5k comparison is accepted.

### Claims This Design Can and Cannot Support

A positive per-sample oracle establishes complementary frozen predictions only
when it clears the practical threshold against the fixed blend. A metadata soft
router beating pooled `mixed` alone shows ensemble benefit; it establishes
adaptive known-species usefulness only when it clears the strict fixed-blend
criteria below. Neither result proves that a blind learned gate will succeed.

The pooled mixed expert is also not parameter, data-exposure, or inference-cost
matched to a three-model ensemble. In addition, the current mixed V3 training run
used species-contiguous row-group batch order. A weak pooled result is diagnostic
but cannot alone establish method failure; a globally shuffled mixed retrain is
the first required control.

## Validated Inputs Before Overnight Inference

- 34/34 local tests pass, including adaptive-usefulness thresholds and the
  automated report renderer.
- Full/strict cohorts and exact 5k/20k train means reproduce frozen hashes.
- Local and central evaluator source hashes match.
- Selected 5k checkpoints are checksum-identical locally and on `moe-reboot`.
- Current-best 20k snapshots are checksum-verified on the Mac and central
  persistent storage, so completed training hours are already recoverable.
- Real 5k and 20k snapshots load through the final checkpoint loader with 15,448
  genes, `log1p_tpm`, mask ratio `0.3`, and mask token `-10`.

## Overnight Sequence

**Armed:** 2026-07-14 22:30 PDT / 2026-07-15 05:30 UTC

1. Wait until all human, mouse, and mixed training logs contain
   `Training complete!` and their training PIDs exit.
2. Freeze final checkpoints; verify remote/local checksums; archive logs and run
   metadata; mirror human/mouse finals into persistent `moe-reboot` storage.
3. Confirm `moe-reboot2` and `moe-reboot-partial` have no training PID or GPU
   compute process. They are then safe to shelve.
4. On the freed central A100, run the corrected **5k evaluation first**.
5. Run **20k evaluation second** with the identical full cohort and mask, then
   analyze the strict subset from the cached predictions.
6. Compute paired full/strict 20k-minus-5k scale and routing-headroom changes.
7. Validate cohort hashes, schema, masks, paired identities, and finite outputs;
   copy the complete result bundle to the Mac.
8. Append a timestamped result section below with tables, confidence intervals,
   diagnosis, limitations, and a conditional future plan.
9. Commit and push the updated code, `progress.md`, and this report to
   `origin/main`.

The Mac watchers run in detached `screen` sessions under `caffeinate`. The Mac
must remain powered, lid open, and online until completion.

## Interpretation Framework

The final diagnosis will prioritize the 103-sample study-disjoint sensitivity
cohort while treating its uncertainty honestly. The 667-sample cohort provides a
higher-powered held-out-sample diagnostic but is not independent at study level.

Every paired comparison reports absolute MSE improvement with its existing
clustered-bootstrap interval plus relative MSE reduction. Beating pooled `mixed`
alone is an ensemble benefit. A promising adaptive MoE ceiling requires the
metadata soft router to beat the out-of-fold fixed blend on strict 20k with a
positive absolute-MSE CI and at least 3% relative MSE reduction. At least 5% plus
a positive residual-Pearson CI is practically convincing. The soft oracle must
also clear the positive-interval and 3% criteria for meaningful routing headroom.
This path evaluates frozen-expert ceilings only; it does not implement a corrected
blind learned gate, and `train_moe.py` remains an older softmax proof of concept.

Decision branches:

1. **Strict metadata soft routing clears the fixed-blend threshold:** the frozen
   ceiling is promising; consider implementing a new blind expression-derived
   gate and quantify the gap to the true-species ceiling.
2. **Soft oracle is positive but species metadata routing is weak:** experts are
   complementary along another biological/technical axis. Learn latent state,
   not species identity.
3. **No strict routing headroom but scale improves individual models:** species
   is the wrong expert partition. Correct the mixed control, then test organ
   specialists using the same frozen-ceiling methodology.
4. **No headroom and 20k remains weak:** prioritize sampler order, backbone, data
   diversity, and objective design before gate or organ training.

## Future Work Required Regardless of Outcome

1. Retrain mixed with globally shuffled cross-species batches.
2. Train a pooled union-data control matched more fairly to specialist exposure.
3. Add parameter- and inference-budget-matched single-model controls.
4. Require profile-controlled improvement in MSE and residual Pearson, not raw
   across-gene Pearson alone.
5. Expand the prospective study-disjoint cohort beyond 103 studies.
6. Only then extend to human organs: build organ-disjoint experts and a frozen
   organ-balanced holdout, measure soft/hard and true-organ ceilings, and train an
   unknown-organ gate only if those ceilings justify it.

## Automated Result Addendum

After `EVALUATION_COMPLETE_AND_VALIDATED`, the report generator appended the
final full/strict tables, paired confidence intervals, scale changes, diagnosis,
limitations, and recommended experiments below. The append is fingerprinted and
idempotent.

---

<!-- corrected-interspecies-report:ae87c68280b09bd8844d743c32b2428e80408e1c1ba52a6e365bf483bd24f270 -->
## Corrected Interspecies MoE Evaluation - 2026-07-15T09:31:07-07:00

> This append-only addendum supersedes the earlier balanced-ARCHS4 and gene-mean conclusions above. The historical text is retained for provenance, but its old headroom numbers used raw TPM in a log1p-TPM model, test-fitted blends, and a test-derived mean baseline.

### Executive conclusion

**Practically convincing adaptive MoE ceiling:** on the strict 20k cohort, the metadata soft router beats the out-of-fold fixed blend by at least 5% relative MSE and has a positive residual-Pearson confidence-interval lower bound. The metadata-soft versus pooled-`mixed` comparison remains a pooled-model control; it is not sufficient by itself to justify MoE. The per-sample soft oracle also exceeds the fixed blend by at least 3% relative MSE with a positive absolute-MSE interval, indicating a meaningful routing ceiling.

The result must still be interpreted with two design constraints: the metadata router receives the true species label and is an upper bound rather than a learned blind gate; and the pooled mixed model is not compute/data/parameter matched to a three-model ensemble. The mixed V3 run also used species-contiguous row-group ordering, so a weak pooled checkpoint cannot by itself establish method failure.

### Frozen protocol

- Full held-out-sample diagnostic: 667 samples; strict study-disjoint sensitivity: 103 samples.
- Shared common space: 15,448 genes; masked positions per sample: 4,634 (training-matched 30%).
- Primary estimand: species-balanced study-macro mean; uncertainty: paired study bootstrap.
- Fixed blend and metadata routing weights are fitted out of fold with connected GEO-series groups.
- Baselines use exact mixed-model training rows only, with separate human/mouse means.
- The full cohort has study overlap with training and is diagnostic; the 103-sample strict cohort is the cleaner sensitivity analysis and has wider intervals.

### 5K Full results

| Condition | Pearson* | Residual Pearson* | MSE* |
|---|---:|---:|---:|
| Human expert | 0.8759 | 0.5673 | 0.74731 |
| Mouse expert | 0.8608 | 0.4810 | 0.82752 |
| Pooled mixed expert | 0.8680 | 0.4784 | 0.78746 |
| OOF fixed blend | 0.8996 | 0.5987 | 0.61290 |
| Metadata-species soft router | 0.9231 | 0.7055 | 0.47045 |
| Per-sample soft MSE oracle | 0.9237 | 0.7076 | 0.46702 |
| Species train-mean baseline | 0.8380 | 0.0000 | 1.07974 |

- **OOF fixed blend vs pooled mixed:** Pearson +0.0316 CI [+0.0299, +0.0333]; MSE improvement +0.17456 CI [+0.16737, +0.18258]; relative MSE reduction 22.2%, residual Pearson +0.1203 CI [+0.1153, +0.1256].
- **Metadata-species soft router vs pooled mixed:** Pearson +0.0551 CI [+0.0532, +0.0572]; MSE improvement +0.31700 CI [+0.30831, +0.32637]; relative MSE reduction 40.3%, residual Pearson +0.2271 CI [+0.2204, +0.2333].
- **Metadata-species soft router vs OOF fixed blend:** Pearson +0.0236 CI [+0.0228, +0.0243]; MSE improvement +0.14245 CI [+0.13819, +0.14651]; relative MSE reduction 23.2%, residual Pearson +0.1068 CI [+0.1038, +0.1097].
- **Per-sample soft oracle vs OOF fixed blend:** Pearson +0.0242 CI [+0.0235, +0.0249]; MSE improvement +0.14589 CI [+0.14201, +0.14983]; relative MSE reduction 23.8%, residual Pearson +0.1089 CI [+0.1062, +0.1117].

### 20K Full results

| Condition | Pearson* | Residual Pearson* | MSE* |
|---|---:|---:|---:|
| Human expert | 0.8953 | 0.6504 | 0.63648 |
| Mouse expert | 0.8920 | 0.6319 | 0.65382 |
| Pooled mixed expert | 0.9112 | 0.7022 | 0.55773 |
| OOF fixed blend | 0.9309 | 0.7375 | 0.43036 |
| Metadata-species soft router | 0.9582 | 0.8473 | 0.26210 |
| Per-sample soft MSE oracle | 0.9585 | 0.8482 | 0.26065 |
| Species train-mean baseline | 0.8380 | 0.0000 | 1.07927 |

- **OOF fixed blend vs pooled mixed:** Pearson +0.0197 CI [+0.0188, +0.0207]; MSE improvement +0.12737 CI [+0.12205, +0.13264]; relative MSE reduction 22.8%, residual Pearson +0.0353 CI [+0.0324, +0.0382].
- **Metadata-species soft router vs pooled mixed:** Pearson +0.0470 CI [+0.0458, +0.0484]; MSE improvement +0.29563 CI [+0.28866, +0.30263]; relative MSE reduction 53.0%, residual Pearson +0.1451 CI [+0.1408, +0.1493].
- **Metadata-species soft router vs OOF fixed blend:** Pearson +0.0273 CI [+0.0267, +0.0280]; MSE improvement +0.16827 CI [+0.16474, +0.17157]; relative MSE reduction 39.1%, residual Pearson +0.1098 CI [+0.1072, +0.1124].
- **Per-sample soft oracle vs OOF fixed blend:** Pearson +0.0275 CI [+0.0269, +0.0282]; MSE improvement +0.16972 CI [+0.16628, +0.17316]; relative MSE reduction 39.4%, residual Pearson +0.1107 CI [+0.1081, +0.1134].

### 5K Strict results

| Condition | Pearson* | Residual Pearson* | MSE* |
|---|---:|---:|---:|
| Human expert | 0.8725 | 0.5293 | 0.78741 |
| Mouse expert | 0.8561 | 0.4170 | 0.88078 |
| Pooled mixed expert | 0.8630 | 0.4101 | 0.84009 |
| OOF fixed blend | 0.8932 | 0.5426 | 0.66561 |
| Metadata-species soft router | 0.9135 | 0.6462 | 0.54132 |
| Per-sample soft MSE oracle | 0.9143 | 0.6492 | 0.53689 |
| Species train-mean baseline | 0.8526 | 0.0000 | 1.02541 |

- **OOF fixed blend vs pooled mixed:** Pearson +0.0302 CI [+0.0273, +0.0333]; MSE improvement +0.17448 CI [+0.16006, +0.18929]; relative MSE reduction 20.8%, residual Pearson +0.1325 CI [+0.1189, +0.1462].
- **Metadata-species soft router vs pooled mixed:** Pearson +0.0506 CI [+0.0472, +0.0541]; MSE improvement +0.29876 CI [+0.28256, +0.31534]; relative MSE reduction 35.6%, residual Pearson +0.2361 CI [+0.2210, +0.2511].
- **Metadata-species soft router vs OOF fixed blend:** Pearson +0.0203 CI [+0.0190, +0.0217]; MSE improvement +0.12429 CI [+0.11651, +0.13232]; relative MSE reduction 18.7%, residual Pearson +0.1036 CI [+0.0957, +0.1113].
- **Per-sample soft oracle vs OOF fixed blend:** Pearson +0.0211 CI [+0.0198, +0.0226]; MSE improvement +0.12872 CI [+0.12097, +0.13694]; relative MSE reduction 19.3%, residual Pearson +0.1066 CI [+0.0990, +0.1140].

### 20K Strict results

| Condition | Pearson* | Residual Pearson* | MSE* |
|---|---:|---:|---:|
| Human expert | 0.8898 | 0.6094 | 0.68534 |
| Mouse expert | 0.8911 | 0.5886 | 0.67952 |
| Pooled mixed expert | 0.9032 | 0.6571 | 0.61934 |
| OOF fixed blend | 0.9253 | 0.6908 | 0.47541 |
| Metadata-species soft router | 0.9512 | 0.8106 | 0.31049 |
| Per-sample soft MSE oracle | 0.9515 | 0.8117 | 0.30883 |
| Species train-mean baseline | 0.8527 | 0.0000 | 1.02478 |

- **OOF fixed blend vs pooled mixed:** Pearson +0.0221 CI [+0.0201, +0.0242]; MSE improvement +0.14393 CI [+0.13323, +0.15566]; relative MSE reduction 23.2%, residual Pearson +0.0337 CI [+0.0263, +0.0415].
- **Metadata-species soft router vs pooled mixed:** Pearson +0.0480 CI [+0.0455, +0.0506]; MSE improvement +0.30885 CI [+0.29535, +0.32167]; relative MSE reduction 49.9%, residual Pearson +0.1535 CI [+0.1454, +0.1620].
- **Metadata-species soft router vs OOF fixed blend:** Pearson +0.0259 CI [+0.0248, +0.0269]; MSE improvement +0.16493 CI [+0.15751, +0.17255]; relative MSE reduction 34.7%, residual Pearson +0.1198 CI [+0.1130, +0.1267].
- **Per-sample soft oracle vs OOF fixed blend:** Pearson +0.0261 CI [+0.0251, +0.0273]; MSE improvement +0.16659 CI [+0.15946, +0.17409]; relative MSE reduction 35.0%, residual Pearson +0.1209 CI [+0.1143, +0.1278].

### Paired scale effect: 20k minus 5k

**Full cohort**
- Human expert: Pearson +0.0195 CI [+0.0181, +0.0208]; MSE improvement +0.11083 CI [+0.10454, +0.11776].
- Mouse expert: Pearson +0.0313 CI [+0.0292, +0.0337]; MSE improvement +0.17370 CI [+0.16243, +0.18589].
- Pooled mixed expert: Pearson +0.0432 CI [+0.0404, +0.0461]; MSE improvement +0.22973 CI [+0.21596, +0.24590].
- OOF fixed blend: Pearson +0.0313 CI [+0.0296, +0.0333]; MSE improvement +0.18254 CI [+0.17364, +0.19223].
- Metadata-species soft router: Pearson +0.0351 CI [+0.0328, +0.0376]; MSE improvement +0.20836 CI [+0.19663, +0.22048].

**Strict cohort**
- Human expert: Pearson +0.0174 CI [+0.0147, +0.0204]; MSE improvement +0.10206 CI [+0.08873, +0.11680].
- Mouse expert: Pearson +0.0351 CI [+0.0298, +0.0411]; MSE improvement +0.20126 CI [+0.17365, +0.23013].
- Pooled mixed expert: Pearson +0.0402 CI [+0.0345, +0.0467]; MSE improvement +0.22075 CI [+0.18974, +0.25101].
- OOF fixed blend: Pearson +0.0321 CI [+0.0280, +0.0366]; MSE improvement +0.19020 CI [+0.16879, +0.21200].
- Metadata-species soft router: Pearson +0.0376 CI [+0.0330, +0.0426]; MSE improvement +0.23083 CI [+0.20310, +0.25932].

### Diagnosis

- **20k strict metadata router vs pooled mixed:** Pearson +0.0480 CI [+0.0455, +0.0506]; MSE improvement +0.30885 CI [+0.29535, +0.32167]; relative MSE reduction 49.9%, residual Pearson +0.1535 CI [+0.1454, +0.1620].
- **20k strict metadata router vs fixed blend:** Pearson +0.0259 CI [+0.0248, +0.0269]; MSE improvement +0.16493 CI [+0.15751, +0.17255]; relative MSE reduction 34.7%, residual Pearson +0.1198 CI [+0.1130, +0.1267].
- **20k strict soft oracle vs fixed blend:** Pearson +0.0261 CI [+0.0251, +0.0273]; MSE improvement +0.16659 CI [+0.15946, +0.17409]; relative MSE reduction 35.0%, residual Pearson +0.1209 CI [+0.1143, +0.1278].

These are frozen-expert ceiling measurements. No corrected blind learned gate is implemented in this overnight path; `train_moe.py` remains an older softmax proof of concept. A positive metadata comparison against pooled `mixed` alone is an ensemble result, while adaptive-routing evidence requires improvement over the out-of-fold fixed blend.

### Recommended next work

1. **Correct the mixed sampler and rerun the pooled control.** Shuffle batches globally across species, preserve the frozen holdouts, and reproduce this report before rejecting the method.
2. **Add fair controls.** Compare against a pooled model trained on the union of specialist data and against parameter/inference-budget-matched single models; report ensemble cost explicitly.
3. **Test a blind learned router only when the ceiling warrants it.** Train routing on calibration studies, never the final cohort, and evaluate on the strict grouped split. Compare with the true-species metadata ceiling to measure how much routable signal is learnable from expression alone.
4. **Use profile-controlled endpoints.** Require paired improvement in MSE and residual Pearson, not raw across-gene Pearson alone, because static gene profiles can dominate that metric.
5. **Then evaluate the human-organ hypothesis.** Build organ-disjoint specialists and a frozen organ-balanced holdout. First measure hard/soft oracle and true-organ metadata ceilings; proceed to an unknown-organ gate only if those ceilings clearly exceed the corrected species result.
6. **Treat the strict cohort as uncertainty-limited.** Its 103 studies are clean but small; repeat the grouped sampling or build a larger prospective study-disjoint holdout before a definitive claim.

### Reproducibility artifacts

- Result fingerprint: `ae87c68280b09bd8844d743c32b2428e80408e1c1ba52a6e365bf483bd24f270`
- Full mask SHA256: `0092b55fe7e8e23c0448a6957fd741369f77f3916f93d4e17d434a9119999e34`
- Strict mask SHA256: `739709804e7d56f54dc8a08e38fe0547e97b44d35b42fc5df4c02fd78e1a1059`
- Validation artifact: `results/corrected_interspecies_eval.validation.json`
- Scale reports: `results/interspecies_scale_change_full.json` and `results/interspecies_scale_change_strict_study_disjoint.json`

## V2-to-V3 Interpretation and the MoE Claim

### What V3 changed

V3 did not introduce a new backbone or gating architecture. Both V2 and V3 use
the same four-layer `ExpressionPerformer`, shared 15,448-gene ordering,
`log1p_tpm` input space, 30% masking objective, and weight decay `0.01`. The main
change was four times more training and validation rows per expert:

| Dimension | V2 5k | V3 20k |
|---|---:|---:|
| Training rows | 4,000 | 16,000 |
| Validation rows | 800 | 3,200 |
| Epochs | human 30; mouse/mixed 20 | 15 |
| Batch size | 8 | 8 |
| Preprocessing draw | original seeded draw | seed 123 with 667 frozen IDs excluded |

This is a controlled scale comparison in architecture and objective, but not a
perfect single-variable experiment: data draws, epoch budgets, and explicit
holdout exclusion differ. The V3 mixed run also inherited species-contiguous
row-group ordering, so it remains necessary to retrain that pooled control with
globally shuffled cross-species batches.

### Why the conclusion changed

The old near-zero-headroom conclusion was not a valid V2 baseline. It came from
raw TPM being passed into models trained on `log1p(TPM)`, test-fitted ensemble
weights, a test-derived gene mean, sample-weighted aggregation, and a hard
per-sample selector being treated as the only oracle. Correcting those problems
changes the qualitative result even for the unchanged V2 5k checkpoints.

On the strict study-disjoint cohort:

| Condition versus OOF fixed blend | V2 5k relative MSE reduction | V3 20k relative MSE reduction |
|---|---:|---:|
| True-species hard router | 17.9% | 33.5% |
| True-species soft router | 18.7% | 34.7% |
| Hard MSE oracle | 17.9% | 33.8% |
| Soft convex MSE oracle | 19.3% | 35.0% |

The discovery is therefore not mainly caused by replacing a hard oracle with a
soft oracle. Hard true-species routing already produces most of the improvement.
Soft routing improves MSE over hard routing by about 0.9% at 5k and 1.8% at 20k;
the soft oracle provides a similarly modest refinement over the hard MSE oracle.
The large effect comes from correctly evaluating species-conditioned routing in
model space and comparing it with an out-of-fold fixed ensemble.

The pooled `mixed` checkpoint is not an oracle. It is one jointly trained expert:
on strict 20k its MSE is `0.61934`, versus `0.47541` for the fixed ensemble,
`0.31611` for the hard true-species router, `0.31049` for the soft true-species
router, and `0.30883` for the soft oracle.

### What scale contributed

V3 improves every principal condition and increases adaptive headroom beyond the
evaluation-only discovery. On the paired strict cohort, metadata-soft MSE
headroom over the fixed blend rises from `0.12429` at 5k to `0.16493` at 20k, a
20k-minus-5k increase of `0.04064` with 95% CI `[0.03210, 0.04928]`. Pearson
headroom rises by `0.00552`, CI `[0.00413, 0.00693]`. Thus scale strengthens both
the experts and the value of species-conditioned routing.

### Defensible conclusion

This experiment shows that a **frozen, species-conditioned MoE works in the
corrected offline setting**: using true species metadata to select or softly mix
experts beats a pooled single expert and a cross-fitted fixed ensemble on a
study-disjoint cohort, with practically large effects and positive clustered
confidence intervals. The near equality of metadata-soft routing and the
per-sample soft oracle shows that species explains almost all measured routing
ceiling for these experts.

At the time of this frozen-evaluation addendum, it did not yet show that a blind
learned gate could infer the correct mixture from RNA expression alone, nor that
three full experts beat a parameter-, data-, and inference-matched single model.
The timestamped Stage 1.5 addendum below resolves the first question; the fair
pooled control remains active.

## Stage 1.5 Blind Gate and Stage 2 Pilot - 2026-07-15T11:35:00-07:00

### Blind expression-derived species gate

The previously missing deployment test now succeeds on the frozen 20k experts.
A balanced logistic classifier was trained only on the masked expression seen by
the experts; reconstruction targets were replaced by the mask token. Its 564
calibration samples (518 connected studies) have zero study-group overlap with
the unchanged strict test of 103 samples/103 studies.

The gate achieved 99.03% strict species accuracy, balanced accuracy 0.99, and
AUC 1.0. Blind-soft routing reached MSE `0.31404`, compared with `0.47547` for
the calibration-fitted fixed blend and `0.31059` for the true-species soft
router. Versus fixed blending, that is a 33.95% relative MSE reduction,
absolute improvement `0.16143` with 95% clustered CI `[0.15336, 0.16926]`, and
residual-Pearson improvement `+0.11450` with CI `[0.10768, 0.12144]`. Blind
soft is only 1.11% worse than metadata soft. Therefore, for species, the useful
routing signal is recoverable from expression without being told the answer.

This closes the blind-gate ceiling test but not the fair-general-model control.
The original pooled checkpoint used locality-aware streaming in which shuffled
row groups still emitted single-species batches. A separate
`mixed_20k_v3_shuffled` retrain now uses the identical V3 dataset split and
hyperparameters with global individual-row shuffling; 1,983/2,000 inspected
epoch-0 batches mix species. It is actively training on the persistent
`moe-reboot` A100. A remote completion watcher will immediately evaluate its
best checkpoint on the same frozen full/strict masks and rerun the blind gate.

### Data-driven organ pilot

The first conservative ARCHS4 audit found 14,096 bulk-tissue candidates across
603 connected GEO study groups. After excluding tumor-like rows and groups that
span more than one candidate organ, and capping each study at 20 samples, the
preregistered availability rule (at least 45 groups and 300 capped samples)
selects `K=5`: brain, skin, liver, colon, and lung. This is evidence-based `K`
selection, not a fixed request for four experts.

The study-disjoint V2 pilot manifest contains 2,856 samples from 317 groups,
including 1,998 training rows. The pooled model's sorted training-ID hash is
identical to the union of all specialist training IDs
(`6d0e274b994ad3c9e1e93d671824d7c879651e2524b0ff95543bb8a642bc396a`).
This enforces the primary fair-data comparison: one general model sees exactly
the same total samples as the five specialists collectively.

The manifest is suitable for pipeline development, not yet for a definitive
biological conclusion. Manual spot checking exposed residual shorthand and
cell-source ambiguity, including GBM and HSAEpC examples, and the specialist
training sets range from only 220 to 783 rows. The next Stage 2 work is therefore
manual/ontology-backed label validation and coverage expansion, followed by a
small end-to-end smoke run. A full organ training campaign should wait for that
review and for the shuffled pooled Stage 1 control.

Reproducible outputs are versioned under
`artifacts/stage1_5_blind_gate/` and `artifacts/stage2_organ_pilot/`.

## Stage 3 Proposed Direction (planned, not yet run) - 2026-07-15

Stage 3 is scoped after a quick prior-art review (recorded with arXiv IDs in
`related-works.md`). It is gated on Stage 2: it runs regardless of the Stage 2
outcome, but a Stage 2 win makes it the headline follow-up while a Stage 2 null
makes it the *explanation* for why organ specialization did not help.

### Motivation

"Router + K experts beats one dense model" is, by itself, a confirmatory instance
of an established pattern: mixture-of-experts theory shows MoE beats a matched dense
model when the data has genuine latent cluster structure, and dense multi-task
models are known to suffer negative transfer across conflicting objectives. Bulk
RNA-seq has strong tissue structure, so a modest Stage 2 win is expected and
low-surprise. The generative question is not *whether* organ specialization helps
but *where and why* it does.

### D1 — organ-by-organ transfer/interference matrix (default)

For each ordered organ pair `(A, B)`, measure how much adding organ `B`'s data to
joint training changes masked-gene reconstruction on a held-out, study-disjoint test
set of organ `A`, relative to an `A`-only specialist. Report a signed `K x K` matrix
(negative = interference, positive = beneficial transfer).

- **Inherited protocol.** Same extractor, shared 15,448-gene space, one `log1p`, one
  deterministic 30% mask, study-disjoint splits, study-macro estimand, and paired
  clustered bootstrap as Stage 1/2. Each organ `A` uses a fixed strict test set for
  every cell in its row.
- **Cells and asymmetry.** A single joint `A+B` model yields both `M[A,B]` (on `A`'s
  test) and `M[B,A]` (on `B`'s test); donor/recipient asymmetry is a first-class
  result.
- **Size-confound control (critical).** Adding `B` also adds data. Each `M[A,B]` is
  measured against a size-matched neutral-filler control (`A + B` vs `A` + an
  equal-size draw of more `A`, or a size-matched random global draw when `A` is
  small), so the matrix isolates `B`'s biological identity from its volume. The raw
  matrix is reported too.
- **Statistics.** Per-cell clustered bootstrap over `A`'s test studies; flag cells
  whose CI excludes zero; Benjamini-Hochberg across the `K^2` cells.
- **Cost at K=5.** ~15-25 small Performer runs plus the existing full-pool model;
  feasible on one A100. Scale to leave-one-organ-out marginals if `K` grows.
- **Novelty.** The task-affinity / task-grouping methodology is established and cited;
  no located work builds a per-organ interference matrix from a masked bulk-expression
  reconstruction model. The contribution is the measurement in genomics, not a new
  method. Exploratory follow-ups (clustering the matrix, regressing interference on a
  biological-distance axis) are labeled as such.

### D2 — learned expert partition vs organ ontology (backup)

Let experts be learnable/soft rather than hard-assigned by organ and test whether the
emergent partition matches the organ taxonomy or a different biological axis (germ
layer, epithelial vs non-epithelial, cell composition). Scoop risk is real — MoE
expert-specialization interpretability is an active LLM-side topic — so the framing
must be strictly the biological alternative hypothesis in the genomics setting.

### Archived

Router-weights-as-deconvolution was archived: bulk deconvolution is a mature field
(CIBERSORT, Scaden, and neural/Bayesian methods) and MoE-for-cell-type already
exists, so only an "emergent, unsupervised byproduct of reconstruction routing"
framing survived, and even that competes with unsupervised deconvolution. A
data-dependent samples-per-organ phase boundary was also dropped as non-unifiable.
