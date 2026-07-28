# Stage 0 final result: interspecies routing

**Status:** complete

## Question

Can a model that chooses between human-, mouse-, and mixed-species RNA specialists
predict masked gene expression better than one fixed combination of those models?

## Final design

- All models use the same 15,448-gene vocabulary.
- Inputs receive exactly one `log1p` transformation.
- Calibration and evaluation groups are separated by connected study.
- The primary evaluation gives equal weight to studies within species, then equal
  weight to human and mouse.
- Fixed blend weights are fit out of fold.
- The learned blind router sees masked expression only; it never sees the hidden
  reconstruction targets.
- A globally row-shuffled mixed-species model repairs the earlier species-contiguous
  training-order confound.

## Result

On the strict 103-study evaluation:

- the expression-only router identifies species with 99.0% balanced accuracy;
- before the stronger shuffled pooled control, blind soft routing reduced MSE by
  33.95% versus the out-of-fold fixed blend and was only 1.11% worse than the
  true-species soft route;
- after the globally shuffled pooled control strengthened the general baseline,
  blind soft routing still reduced MSE by 11.42% versus the fixed blend, with positive
  MSE and residual-correlation intervals; and
- the shuffled pooled model reduced the earlier fixed-blend advantage over pooled
  from 23.24% to 2.03%, confirming that training order had materially weakened the
  original pooled control.

The defensible conclusion is that expression contains enough species signal for
adaptive routing to outperform a fixed mixture under the corrected study-aware
evaluation. It does not establish a parameter-matched systems advantage, biological
mechanism, or downstream utility.

## Superseded result

Do not use the early balanced-ARCHS4 `+0.0031` headroom or `0.686` gene-mean result.
That evaluation used raw TPM for `log1p(TPM)` models, fit ensemble weights on the
reporting cohort, derived a baseline from the test cohort, and used sample-weighted
summaries. It is retained only in Git history.

## Canonical artifacts

- blind-gate report: `artifacts/stage0_blind_gate/report.json`;
- corrected 5k and 20k evaluation bundles: local `results/` paths referenced in
  `docs/current-status.md`;
- final Stage 0 model backups: `backups/20k_v3_final/`; and
- full pre-cleanup narrative: Git commit `2bc1bef`.
