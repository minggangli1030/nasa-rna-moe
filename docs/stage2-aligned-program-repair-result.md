# Stage 2 coefficient-supervision repair result

**Status:** complete; frozen decision is to pivot representation

**Scientific commit:** `51ab2f58ee683cd7b10f0d62c86e8e77354009dc`

**Protocol SHA256:** `89f6e97218a1871782e08725104e04ae8d1d40001d74ec4e09e01a32e80c5764`

## Question

The first aligned shared/private model was useful but nearly one-dimensional. This
single bounded repair asked whether training the organ-private path first and then
supervising the unchanged shared head on explicit residual-projection coefficients
would recover a useful, seed-aligned, non-collapsed representation without harming
individual organs.

All three fixed seeds completed 1,500 private-phase and 1,500 coefficient-phase
updates. No seed, component, organ, or checkpoint was selected.

## Frozen result

The repair retained strong predictive utility:

| Comparison | Seed 17 | Seed 42 | Seed 101 |
|---|---:|---:|---:|
| candidate vs pooled | +37.756% | +34.145% | +35.769% |
| candidate vs phase-1 private | +3.207% | +5.885% | +6.385% |
| candidate vs random basis | +3.090% | +5.795% | +6.308% |
| candidate vs generic control | +39.393% | +34.202% | +37.387% |

Every displayed bootstrap interval was above zero. The candidate retained 111.4%
of the phase-1 private gain on average.

However, the representation remained collapsed:

| Diagnostic | Frozen minimum | Observed minimum |
|---|---:|---:|
| sample coefficient effective rank | 8.0 | 1.815 |
| donor coefficient effective rank | 6.0 | 1.392 |
| within-organ coefficient effective rank | 8.0 | 1.952 |
| flattened donor coefficient correlation | 0.5 | 0.271 |
| median component correlation | 0.3 | 0.580 |

Direct coefficient supervision increased sample rank only modestly—from 1.42–1.66
in the original run to 1.81–2.18—and did not recover the 8+ stable coordinates
required by the protocol. Component-wise correlations were often positive, but the
overall coefficient geometry and relative amplitudes differed substantially across
trunks.

Per-organ safety also failed. Relative to the phase-1 private path, skin changed by
−5.890%, −2.307%, and −6.478% in seeds 17, 42, and 101. The frozen maximum harm was
5%. Brain received the largest gain in every seed (+13.006% to +28.411%), and liver
received +24.361% in seed 101. The aggregate improvement therefore remains
concentrated rather than uniformly safe.

Frozen evaluator decision:
`coefficient_supervision_repair_fail_pivot_representation`.

## Extended-control integrity audit

The immutable evaluator marked superiority to the “extended private” and “extended
generic” controls as passing. Those two labels must not be interpreted literally.

After phase 1, the cosine scheduler had reduced the reused optimizer learning rate
to zero. Phase 2 attached a new scheduler to the same zero-learning-rate optimizer
without restoring its base learning rate. Consequently:

- the phase-1 and “extended” private checkpoint tensors are exactly identical in
  seeds 17, 42, and 101;
- their calibration-score arrays are exactly identical in all three seeds; and
- the generic control followed the same zero-learning-rate code path.

The extended-budget controls are invalid and no claim of beating additional
private or generic optimization is supported. The candidate shared head and
random-basis head used newly created nonzero-learning-rate optimizers and are not
affected.

This flaw does not change the decision. The candidate independently fails three
non-collapse gates, flattened cross-seed alignment, and per-organ safety. The
protocol authorized one bounded identifiability repair; rerunning solely to repair
an already non-decisive control would not rescue this representation and risks
post-outcome tuning.

## Interpretation

The experiment separates two conclusions:

1. A shared residual path can improve aggregate reconstruction beyond a frozen
   organ-private path.
2. The current 32-coordinate expression-PCA parameterization does not turn that
   utility into a stable, safe, multi-program representation.

The likely remaining issue is target invariance. Training projected residuals from
draws where 30% of score genes were masked, while calibration masked all score
genes. The earlier linear probe was trained and tested within the full-mask
calibration distribution and therefore did not test this partial-to-full-mask
shift. Subset-specific least-squares targets can agree mainly on the few dominant
tissue/difficulty axes and disagree on weaker coordinates.

This explanation is a post-result hypothesis, not a confirmed mechanism.

## Prioritized future plan

Stop repairing this expression-PCA coordinate system. Preserve the independently
validated organ experts as the benchmark and run a representation pivot:

1. **Read-only mask-invariance audit.** On training donors only, measure
   same-sample coefficient agreement across repeated partial masks and between
   partial-mask and full-mask targets. Quantify whether skin harm aligns with the
   dominant shared directions.
2. **Remove the train/evaluation mismatch.** A future shared head may pool only
   non-score genes, which are visible under both fitting and evaluation. Its target
   can then use all score-gene residuals without visible-target leakage.
3. **Replace raw-expression PCA.** Freeze a common decoder from cross-fitted,
   training-only reconstruction residuals or preregistered pathway aggregates.
   Coordinates should describe correctable model error rather than the largest
   axes of ordinary expression variation.
4. **Broaden beyond organ alone.** Test nested tissue site and cross-cutting
   pathway, platform, and quality attributes where metadata are adequate. Organ
   remains the validated benchmark, not a permanent restriction.
5. **Require prospective confirmation.** Any new representation must pass
   seed/donor alignment, random and capacity controls, per-organ safety, and then a
   new study-disjoint multisource cohort before guiding data sharing.

The scientific objective remains unchanged: learn a reproducible rule that decides
which biological domains should share training information and when sharing should
be declined.

## Integrity

- all three seed metadata records bind the exact commit and protocol;
- root immutable entries verified: 35/35;
- root checksum-manifest SHA256:
  `c32516239f98d3542a2b2292a726df75d4a27552542245bb2e9b5a6d96eb960a`;
- compact evaluation entries verified: 4/4; and
- evaluation checksum-manifest SHA256:
  `46865c1c4443f970d16f49f132a01e56478068b651190dc2b24a09ab7467dff4`.

Compact result:
`artifacts/stage2_organ_expert_mechanism/aligned_program_repair_evaluation_51ab2f5/`.

