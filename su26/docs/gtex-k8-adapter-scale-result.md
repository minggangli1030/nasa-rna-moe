# Frozen-trunk K8 adapter data-diversity result

**Completed:** 2026-08-04 03:35 PDT / 2026-08-04 10:35 UTC

**Evidence role:** donor-disjoint GTEx development; not external confirmation or a
full end-to-end scaling law

**Decision:** `STABLE_SPECIALIZATION_AT_ALL_BUDGETS__NO_ROBUST_MONOTONIC_SLOPE`

## Question

With the pooled trunk frozen, does an eight-organ adapter bank outperform a single
pooled adapter as the number of unique training donors per organ increases?

The frozen curve used exactly 25, 50, 100, 150, and 200 donors per organ, with one
expression-blind sample per donor. Organ K8 and pooled-adapter controls received the
same samples, 1,500 updates, and 12,000 total training draws at each budget. All three
fixed seeds were evaluated on the same untouched donor-disjoint GTEx calibration
cohort. The pooled control is matched for active adapter width and compute, but not for
total stored parameter count: K8 retains eight 64-dimensional adapters and the pooled
control retains one.

## Result

Values below are percent MSE reduction for organ K8 relative to the pooled adapter.
Positive is better. Brackets are prespecified 95% donor-bootstrap intervals.

| Donors per organ | Seed 17 | Seed 42 | Seed 101 |
|---:|---:|---:|---:|
| 25 | 6.819 [6.662, 6.975] | 10.652 [10.388, 10.906] | 10.292 [10.136, 10.449] |
| 50 | 4.565 [4.426, 4.706] | 12.455 [12.221, 12.697] | 8.562 [8.408, 8.721] |
| 100 | 6.643 [6.522, 6.766] | 11.360 [11.100, 11.613] | 10.625 [10.451, 10.800] |
| 150 | 6.802 [6.665, 6.928] | 11.964 [11.756, 12.194] | 6.902 [6.762, 7.041] |
| 200 | 5.926 [5.826, 6.030] | 11.161 [10.951, 11.375] | 9.028 [8.848, 9.203] |

All 15 point estimates are positive, and all 15 intervals are entirely above zero.
Every one of the five budgets therefore satisfies the frozen stable-positive gate
across all seeds. The observed gains span 4.565% to 12.455%, with an unweighted mean
of 8.917% across the 15 prespecified runs.

The per-organ safety gate also passes. No organ is harmed by more than the frozen 2%
tolerance. Two colon estimates are trivially below zero in seed 17 (−0.0036% at 100
donors and −0.0211% at 200 donors); these are effectively neutral and far inside the
prespecified safety bound.

## What does not pass

The effect is not monotonic with unique-donor budget. Gain per log budget is:

- seed 17: +0.098 percentage points [0.026, 0.172];
- seed 42: +0.170 [0.089, 0.252];
- seed 101: −0.784 [−0.859, −0.715].

Because the slope direction reverses across fixed seeds, the frozen decision is
`NO_ROBUST_MONOTONIC_CLAIM`. More unique donors did not systematically enlarge the
specialization advantage over the tested 25–200 range.

## Takeaway

This is strong development evidence that organ-specific residual adapters are useful
even with a shared frozen trunk: specialization beats generic pooling at every tested
budget and in every fixed seed. It is not evidence for a data scaling law or a
budget-dependent crossover. The most defensible interpretation is that the organ
partition supplies a robust conditional correction whose size is established by 25
donors per organ under this fixed-update protocol, while additional donor diversity
does not change that advantage consistently.

The 4.565–12.455% GTEx development gains should not be compared numerically as if they
were the same estimand as the 3.797% external ARCHS4 gain. The cohorts, controls, and
evaluation roles differ. The new curve freezes the trunk, uses accessed GTEx
calibration data, and compares against a newly trained pooled adapter; the ARCHS4 test
measures external reconstruction against the original pooled model.

Exact scientific commit is
`f21e40ffa86fa17f0e1a29881a2efb0be74c508c`. Protocol SHA256 is
`0a93107daa1a916a1ce58fecc3c5992c0f1ea7e7e0f59afd21c0f9d8f8d9f22a`;
master manifest SHA256 is
`5f1f8bd62371ad993a2d4016c94e1ee252a18b795fc73e1c4b5f51570cdf66fc`.
The immutable evaluation-report SHA256 is
`7f0802bf3b5bdfea4829a56b50fd5fbf431d34db8689c53958870d1e9baaeb24`.
The compact immutable report is under
`artifacts/final_evaluation/gtex_k8_adapter_scale/evaluation_f21e40f/`.
