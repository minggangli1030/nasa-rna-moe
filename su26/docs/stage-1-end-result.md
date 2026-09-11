# Stage 1 end result: organ-specialized RNA MoE

**Status:** complete  
**Evidence cutoff:** 2026-07-27  
**Next stage:** organ-expert mechanism and directed transfer

## Final Stage 1 conclusion

> Organ-specialized models improve balanced masked-expression reconstruction versus
> a pooled model whether dispatch uses a revealed organ label, a hard target-hidden
> router, or a soft target-hidden router.

The result is robust across all prespecified training seeds, multiple experimental
setups, and both directions of the GTEx/ARCHS4 domain shift. It is also positive under
estimators that balance heterogeneous studies or GTEx donors rather than allowing the
largest source to dominate.

The result should **not** be described as invariant in every study. Study-level
invariance would be unnecessarily strong and is unlikely given:

- variable tissue-label specificity and metadata quality;
- differences in sequencing platform, library preparation, coverage, and processing;
- healthy, control, disease-context, postmortem, and donor-regime variation;
- unequal study sample sizes and gene-detection completeness;
- imperfectly verified donor identities in portions of ARCHS4; and
- genuine biological heterogeneity within nominally shared organ labels.

The supported wording is:

> The improvement is study-robust in aggregate under equal-study/equal-organ
> weighting, with positive study-clustered uncertainty, while individual studies may
> be neutral or negative.

The ARCHS4 estimator does not simply pool every sample. It first summarizes samples
within connected studies, weights studies equally within organ, and then weights
organs equally. The bootstrap resamples connected studies within organ. This prevents
one large study from creating the overall result but does not assert that every study
benefits.

## New reverse-direction result

The GTEx-to-ARCHS4 candidate was trained without ARCHS4-derived weights and evaluated
on 821 QC-passing samples from 63 connected studies across all eight organs.

| Condition | Equal-organ/study MSE | Reduction vs pooled |
| --- | ---: | ---: |
| pooled | 0.909261 | — |
| true-organ K8 | 0.874738 | 3.797% |
| target-hidden hard K8 | 0.876228 | 3.633% |
| target-hidden soft K8 | 0.875840 | 3.676% |
| pooled residual adapter | 0.909304 | -0.005% |
| mean of three random K8 axes | 0.909273 | -0.001% |

Every true-organ, hard-router, and soft-router comparison was positive in seeds 17,
42, and 101. The paired connected-study bootstrap interval versus pooled excluded zero
for every seed-level comparison. No best seed was selected.

Hard target-hidden routing retains approximately 95.7% of the true-organ gain; soft
target-hidden routing retains approximately 96.8%. Thus most of the benefit remains
when the test-time organ label is not supplied.

This result is labeled
`post_access_qc_amended_external_evaluation`. Six samples failing the unchanged
14,000-nonzero-gene QC rule were excluded after the first expression-access attempt.
No efficacy metric existed before the amendment, no replacement was added, and no
model was tuned, but the membership change prevents a pristine preregistration claim.

## Cross-setup evidence

| Evidence setting | Training → evaluation | Blind gain | True-organ gain | Role |
| --- | --- | ---: | ---: | --- |
| K4-EPE development | ARCHS4 → ARCHS4 development/calibration | 3.339% | 3.983% | architecture nomination |
| pristine K4 external validation | ARCHS4 → GTEx | 3.157% | 3.301% | donor-controlled external pass |
| QC-amended K8 reverse validation | GTEx → ARCHS4 | 3.633% hard / 3.676% soft | 3.797% | multisource cross-processing support |

These percentages are not a direct leaderboard: K, cohorts, training sources, and
aggregation units differ. Their value is directional replication. The organ advantage
does not disappear when the training and evaluation sources are reversed.

## What Stage 1 establishes

1. **Organ experts are conditionally useful.** Correctly dispatched organ specialists
   outperform the pooled baseline on the balanced reconstruction estimand.
2. **The route is recoverable from observed expression.** A target-hidden router
   retains nearly all of the revealed-organ benefit.
3. **The gain is not generic adapter capacity.** The pooled residual adapter and
   matched random K controls are neutral.
4. **The result is seed-robust.** All three frozen seeds have the same positive
   direction without best-seed selection.
5. **The signal transfers across processing domains.** Both ARCHS4-to-GTEx and
   GTEx-to-ARCHS4 evaluations are positive.
6. **Conditional dispatch is the supported mechanism.** The earlier failure of one
   global fixed average of organ experts remains valid and does not contradict routed
   specialization.

## What Stage 1 does not establish

- improvement in every individual study or every organ-by-seed cell;
- that every organ has equal specialist headroom;
- a causal biological mechanism for the expert differences;
- a novel label-free taxonomy;
- verified donor-level independence for every ARCHS4 study;
- improvement on downstream spaceflight tasks; or
- clinical usefulness.

The primary effect is a reproducible 3–4% masked-reconstruction improvement. It is
scientifically useful and consistent, but it should not be inflated into a large
downstream or mechanistic claim.

## Stage 1 decision

Stage 1 is sufficiently positive to proceed to an organ-anchored Stage 2.

This authorizes:

- frozen-expert residual and pathway analysis on development/calibration data;
- controlled organ-to-organ transfer/interference experiments;
- tests of whether expert/router structure predicts independently measured transfer;
  and
- implementation and mechanical validation of a new untouched Stage 2 lockbox.

It does not authorize:

- tuning against the completed 821-sample ARCHS4 evaluation;
- repeating failed de novo label-free mixtures as the primary experiment;
- selecting favorable organs, seeds, studies, or pathways from final-test efficacy;
  or
- making Stage 2 biological claims before a separate frozen evaluation.

The approved Stage 2 sequence is:

1. compare frozen organ-expert residuals, affected genes, and pathway signatures
   against the pooled trunk;
2. construct a controlled directed transfer matrix asking whether donor organ B helps
   or harms untouched recipient-organ A studies;
3. test whether expert similarity and router preference predict the independent
   transfer relationships; and
4. only afterward consider within-organ or label-free structure as a secondary
   extension.

The detailed protocol direction is
`docs/stage2-organ-expert-mechanism-plan.md`.

## Canonical evidence

- current status: `docs/current-status.md`
- K4 final-refit history and gates: `docs/stage1-k4-final-refit.md`
- Stage 2 plan: `docs/stage2-organ-expert-mechanism-plan.md`
- GTEx-to-ARCHS4 evaluation report SHA256:
  `b4a77268c642709b2ae33a0a4d95f38bb9029734f5ffffd0ba1d3f9be1fc15cb`
- final evaluator-correction protocol SHA256:
  `c5aaed24de62347747e815c02e0cda7793adc15c33b0b67f841c7c6896b48632`
- pristine K4 GTEx evaluation report SHA256:
  `c90adfee81aa31241502d69bfdf1e92d41d66574e5f9a1c5bdd2b9877d1e38c6`
