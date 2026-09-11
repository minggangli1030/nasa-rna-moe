# GTEx training variance-decomposition result

**Status:** complete descriptive diagnostic
**Date:** 2026-08-17

## Question

How does the squared-error reconstruction objective allocate variance across stable
gene levels, tissue structure, donor differences within tissue, and repeated-sample
residual variation in the actual GTEx training distribution?

This does **not** measure where perturbation-state information resides. GTEx has no
perturbation labels, within-tissue variance contains several biological and technical
sources, condition effects need not be confined to that stratum, and variance share is
not an information bound.

## Conventions resolved before the run

- cohort: 7,369 manifest rows with `split=train`;
- organs: eight;
- expression: TPM transformed exactly once to unstandardized `log1p(TPM)`;
- genes: all 15,448 genes present in the GTEx training expression table;
- aggregation: sample level; and
- nested grouping: donor within organ, because GTEx donors contribute multiple tissues.

## Result

| Component | Fraction of total variance |
|---|---:|
| Between gene | 71.557% |
| Between tissue, within gene | 19.192% |
| Between donor, within tissue | 4.976% |
| Residual within donor and tissue | 4.275% |
| **All within-tissue variation** | **9.251%** |

The exact variance identity closed with relative error `7.50e-15`.

Using each organ's own total-variance denominator, the within-tissue fraction was
5.478% in skeletal muscle and 14.826% in brain. The other organs ranged from 4.926% to
12.005%.

## Interpretation

The result crosses the prespecified descriptive threshold of roughly 10%: most
variance rewarded by the unstandardized reconstruction loss comes from stable gene-
and tissue-level structure, while deviations within tissue compete for a relatively
small share of the objective. This corroborates objective mismatch as a plausible
explanation for weak downstream transfer.

It does not show that 9.251% is perturbation state, that state is unlearnable, or that
changing the objective will necessarily improve downstream performance. A labeled
within-tissue condition decomposition is required for the stronger state-specific
claim.

## Per-gene-standardized sensitivity

The same cohort was decomposed a second time after fitting a population mean and
standard deviation separately for every gene on the 7,369 training rows. Twenty-seven
constant genes could not be standardized and were excluded, leaving 15,421 genes.

| Component | Unstandardized | Per-gene standardized |
|---|---:|---:|
| Between gene | 71.557% | effectively 0% |
| Between tissue, within gene | 19.192% | 53.362% |
| Between donor, within tissue | 4.976% | 25.704% |
| Residual within donor and tissue | 4.275% | 20.934% |
| **All within-tissue variation** | **9.251%** | **46.638%** |

The exact standardized identity closed with relative error `3.54e-15`. The measured
within-tissue share is 5.04 times the unstandardized share and is materially larger
than the rough 32.5% estimate that assumes the tissue-to-within-tissue ratio remains
fixed. Gene-specific scaling does not preserve that ratio.

This makes train-only per-gene standardization a high-priority, inexpensive objective
intervention to test before contrastive or multi-head retraining. It is still not
downstream evidence. A training pilot must define how inputs, targets, mask tokens,
zero-variance genes, inference-time transforms, and any de-standardized reconstruction
metric are handled. Scaling may also amplify noisy low-variance genes, so a variance
floor or robust-scale sensitivity should be considered.

## Reproducibility

- evaluator: `evaluation/evaluate_training_variance_decomposition.py`;
- standardized evaluator:
  `evaluation/evaluate_standardized_training_variance_decomposition.py`;
- expression SHA256: `ef5949975e8139d0a29f6fca003da6098a308677f2ab34d7f589851b5ea36550`;
- manifest SHA256: `d37023f08fabf5059a886501ab416feb5caabbce9aa719086832f6d2579ed2e6`.

The full JSON report remains on the VM at
`artifacts/final_evaluation/training_variance_decomposition/report.json`; the
standardized report is beside it at `standardized_report.json`.
