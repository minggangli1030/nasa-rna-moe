# Stage 2 result: frozen organ-expert representation audit

**Status:** complete; organ-only exact-gene representation gate failed  
**Evidence stage:** GTEx donor-disjoint development analysis  
**Decision:** pivot to a frozen multi-scale, multi-attribute audit

## Question

After raw organ-to-organ transfer failed the seed-factorized stability test, do the
already validated organ experts nevertheless learn the same gene-level functional
correction program across three independently trained pooled trunks?

The audit was frozen before opening gene-level outputs. It used all 1,826 GTEx
calibration samples from 188 held-out donors, the fixed 4,634 score genes, and seeds
17, 42, and 101. No model was fit, no seed was selected, and ARCHS4 was not accessed.

## Result

The aggregate organ benefit remained real:

- all 8/8 organ experts beat the generic pooled adapter with 95% donor-bootstrap
  lower bounds above zero;
- all 8/8 beat the mean of three manifest-assigned random-K8 controls by the same
  criterion; and
- effect magnitudes were largest for skin, liver, and brain in the log-expression
  squared-error scale.

The exact functional program did not reproduce:

- 0/8 organs passed every frozen representation gate;
- minimum pairwise correction cosine ranged from −0.051 to 0.350, below the
  prespecified 0.5 threshold;
- minimum pairwise efficacy rank correlation ranged from −0.318 to 0.322, with only
  skin exceeding the 0.3 threshold;
- minimum top-100 absolute-gene overlap ranged from 0 to 0.143, below the 0.15
  threshold for every organ; and
- even the strongest candidates, skin and lung, failed the complete gate.

The frozen decision is:
`organ_axis_insufficient_pivot_multi_attribute`.

## Interpretation

Stage 1 remains supported: organ supervision reproducibly improves aggregate masked
reconstruction. The new result limits the mechanistic claim. Independently trained
models can achieve the same aggregate benefit through different detailed correction
patterns, so exact gene rankings and raw organ-pair additions are not stable enough
to guide sharing.

This may reflect redundant solutions in the frozen trunks and adapters, gene-level
noise, or a biological signal that is stable only after aggregation into broader
programs. The current audit cannot distinguish those explanations.

Hundreds of genes per organ met the exploratory sign/bootstrap screen, but those
counts must not be presented as gene discoveries. The screen is not
multiplicity-controlled, while cross-seed rankings and top-gene overlap failed.

## Next experiment

Freeze a shared, outcome-independent representation basis from GTEx training donors
only, then re-evaluate the existing frozen predictions at two levels:

1. continuous expression modules rather than individual genes; and
2. tissue site nested within organ wherever calibration donor support is adequate.

All eligible sites and all prespecified modules must be reported. If the coarser
programs reproduce, they can define a prospective sharing predictor. If they do not,
stop treating organ or organ subsite as the primary Stage 2 representation and move
to a new factorized architecture with explicitly shared canonical program heads.

## Integrity and artifacts

- implementation commit:
  `d90550eac1df7b1fe1bba72dd96f059b9ad402af`;
- protocol SHA256:
  `a1ae007be01bb480f6649a6dfac6102b3359c5e3fa51393160c6469de67a5312`;
- local compact result:
  `artifacts/stage2_organ_expert_mechanism/representation_evaluation_d90550e/`;
- checksum-manifest SHA256:
  `0fca3aa432c37668e26e5f1006983b71126510a1056e5a6329bab7aae80650ea`;
- corrected run root:
  `/media/volume/moe-reboot/results/stage2_representation_pivot_d90550e`; and
- preserved fail-closed mechanical lineage:
  `/media/volume/moe-reboot/results/stage2_representation_pivot_46ca2ed`.

This is donor-disjoint GTEx development evidence, not independent-study
universality.

## Multi-scale follow-up

The frozen follow-up projected the same immutable predictions into 32 continuous
expression components fit on GTEx training donors only and evaluated all 23
manifest-eligible tissue sites.

- 1/8 organs passed the full module gate: adipose.
- 2/23 tissue sites passed: subcutaneous and visceral adipose.
- Those two sites span only one organ, so the hierarchical-site branch failed.
- Skin passed correction-cosine and efficacy-rank thresholds but missed the frozen
  top-eight-module overlap threshold.
- Decision:
  `no_stable_existing_representation_design_explicit_program_heads`.

The threshold is not lowered after observing skin. Adipose remains a bounded
mechanistic hypothesis, not a project-wide sharing rule.

Canonical artifact:
`artifacts/stage2_organ_expert_mechanism/multiscale_evaluation_39cf87f/`.
Its checksum-manifest SHA256 is
`a6a26cde213b66b07758498590fa5948bd8450bd4cee0de3fe117ee83dfe5edd`.

The next model should align representations by construction: decode residuals
through a fixed training-derived program basis, learn shared per-sample program
coefficients, and retain an organ-private residual path. This makes program
coordinates comparable across seeds while preserving a safe private path. It must
be compared with pooled, generic-adapter, organ-private, random-label, and
parameter/update-matched controls across all three seeds.
