# NASA RNA MoE: current canonical status

**Updated:** 2026-07-29 10:30 PDT / 2026-07-29 17:30 UTC

This is the operational handoff. Historical detail remains in Git through commit
`2bc1bef`; concise milestones are in [`../progress.md`](../progress.md).

## Current phase

Stage 2 completed the frozen seed-factorized stability diagnosis. Raw
recipient-preserving organ-to-organ addition did not produce an actionable helpful
rule. The user approved the representation-first pivot rather than spending the next
cycle on another organ-pair training implementation.

The active experiment is a read-only audit of the already validated organ experts:

1. extract per-gene functional corrections and reconstruction effects from all three
   frozen GTEx K8 seeds on the same donor-disjoint calibration set;
2. compare the organ expert with the pooled trunk, pooled adapter, and three
   donor-balanced random-K8 controls;
3. require prespecified cross-seed cosine, rank, top-gene overlap, and donor-bootstrap
   gates before calling an organ program reproducible; and
4. only after a representation gate passes, freeze a prospective rule that tests
   whether signature structure predicts safe parameter or data sharing.

The exact protocol is frozen before opening these gene-level outputs at
`artifacts/stage2_organ_expert_mechanism/representation_pivot_protocol.json`.
This audit performs no fitting, no seed selection, and no ARCHS4 access. Organ
experts remain the benchmark, but organ is no longer assumed to be the only useful
representation axis. If the organ programs fail, the next branch is a frozen
multi-attribute audit rather than another search for a lucky organ pair.

## Completed seed-stability diagnosis

The frozen 3×3 design crossed pooled trunks 17, 42, and 101 with independent
optimization/mask/loader replicates 211, 223, and 227. All nine deterministic-FP32
combinations completed 24/24 arms without best-seed or edge selection.

Result:

- stable helpful: **0/8** edges;
- stable harmful: **2/8** edges;
- unstable or negligible: **6/8** edges;
- brain ← skin: −0.883%, 95% factor-bootstrap CI −1.621% to −0.298%;
- skin ← adipose: −3.369%, CI −6.654% to −0.682%; and
- the earlier liver ← skin signal averaged +3.011% but was positive in only 6/9
  combinations and its interval crossed zero (−0.632% to +7.862%).

Every edge remained worse on average than the A2250 additional-recipient-exposure
control. Only 9/72 crossed cells beat A2250; the mean difference was −3.664%.

Prespecified decision:
`optimization_instability_confirmed_test_robust_sharing_then_pivot`.

Integrity:

- exact input-bound commit:
  `3a27ffabdcb6d2a4209006452958b30cf0fff520`;
- primary immutable entries verified: 379/379;
- parallel immutable entries verified: 304/304;
- compact transfer entries verified: 207/207, with no model checkpoints copied;
- evaluation checksum-manifest SHA256:
  `66dc24a0d8541f37dfea99be9553677509cb3523da843609835d36febf7c6801`.

Canonical result:
[`stage2-seed-stability-diagnosis.md`](stage2-seed-stability-diagnosis.md) and
`artifacts/stage2_organ_expert_mechanism/seed_stability_evaluation_3a27ffa/`.

## Completed Stage 2 development results

### Same-budget substitution

Comparison: A750+B750 versus A1500 on held-out target-organ donors.

- all 56 directed edges were negative in all three seeds;
- every donor-bootstrap interval was below zero;
- mean effect: −3.273%; and
- the independent seed-101 lineage reproduced the scientific hashes.

Interpretation: with fixed training draws, target-organ data is more useful than
replacing half of it with another organ.

### Recipient-preserving addition

Comparison: A1500+B750 versus A1500, with A2250 and random auxiliaries as controls.

- five of eight mean effects were positive;
- liver ← skin was the only edge positive in all three seeds with its interval above
  zero: +1.956%, 95% CI +1.647% to +2.244%;
- four edges beat all random auxiliaries in all three seeds; and
- zero of eight named donors beat A2250 in all three seeds.

Interpretation: donor identity can matter, but the helpful map is not stable enough
to guide training. More target-organ exposure remains the best tested use of the
added budget.

Canonical documents:

- [`stage2-directed-transfer-preliminary-result.md`](stage2-directed-transfer-preliminary-result.md)
- [`stage2-additive-transfer-result.md`](stage2-additive-transfer-result.md)
- [`stage2-organ-expert-mechanism-plan.md`](stage2-organ-expert-mechanism-plan.md)

## Completed Stage 1 result

The final GTEx-trained K8 external evaluation used 821 ARCHS4 samples from 63
connected studies across all eight organs.

Results versus pooled:

- correct organ specialist: 3.797% lower MSE;
- target-hidden hard routing: 3.633% lower;
- target-hidden soft routing: 3.676% lower;
- equal-capacity pooled adapter: effectively neutral; and
- random K8 controls: effectively neutral.

All three routed conditions improved in seeds 17, 42, and 101; every paired
connected-study bootstrap interval was above zero.

Evidence label:
`post_access_qc_amended_external_evaluation`.

Reason: exactly six rows failed the frozen 14,000-nonzero-gene rule after expression
access and were excluded without replacement, threshold change, fine-tuning, or
seed selection. A new untouched cohort is required for pristine preregistered
confirmation.

The earlier K4-EPE candidate also passed the GTEx V11 donor-controlled validation on
6,795 samples from 930 donors: 3.301% true-route and 3.157% target-hidden improvement
versus pooled.

Canonical documents:

- [`stage-1-end-result.md`](stage-1-end-result.md)
- [`stage1-k4-final-refit.md`](stage1-k4-final-refit.md)

## Representation-first principle

The intended advance is not to find a lucky organ pair. It is to learn a
reproducible rule that separates helpful shared gradients from domain-specific
interference across trunks, optimization replicates, donors, and eventually
independent studies.

Organ is the strongest independently validated specialization axis and current
benchmark, not a permanent restriction. If organ transfer remains disappointing
after the protected-sharing test, Stage 2 may test hierarchical attributes,
cross-cutting biological programs, or continuous expert-residual representations.
Every alternative must beat organ and pooled controls under donor/study-disjoint,
seed-stability, anti-collapse, utility, and confound gates.

## Claim boundaries

Supported:

- organ-specialized reconstruction improves aggregate balanced external performance;
- expression-only routing preserves most of the known-organ gain;
- same-budget cross-organ substitution causes reproducible negative transfer; and
- raw recipient-preserving organ addition has no stable-helpful edge under the
  crossed diagnosis, while brain ← skin and skin ← adipose are stable harmful.

Not supported:

- improvement in every organ, seed cell, or individual study;
- universal directed-transfer relationships;
- causal biological mechanism;
- verified donor identity within every ARCHS4 study;
- spaceflight, disease, clinical, or downstream task benefit; or
- a claim that all parameter sharing is harmful.

A new untouched multisource study-disjoint cohort is required for Stage 2 study
universality.

## Presentation package

The July 30 package is:

- deck: `presentation/2026-07-30-biweekly.html`;
- canonical design: `presentation/design.md`;
- Stage 2 heatmap:
  `presentation/2026-07-30-stage2-directed-transfer-heatmap.png`; and
- additive chart: `presentation/2026-07-30-stage2-additive-effects.png`.

All current and future decks use
`presentation/design.md`. Its Anthropic-inspired field-journal system uses parchment
surfaces, Anthropic Serif/Sans tokens with portable Source Serif 4/Inter fallbacks,
a restrained clay accent, plus Atrium sage and muted blue only where functional data
distinctions require them. Presentations remain audience-first, visual-first, and
script-free. Biweekly updates use plan → results → next, with results occupying most
of the talk. The specification now uses a 1720 px standard content canvas at
1920×1080—about 20% wider than the original—and enforces a 16 px minimum for center
content and retained footnotes. Result slides remain frameless and chart-dominant;
centered progress dots preserve the active-slide state. Ranked charts use semantic
color assignment: Muted Blue follows the verified winner, rather than a fixed series
position. July 9 and July 16 rendered decks remain unchanged historical artifacts.

The July 30 deck includes the completed nine-run diagnosis on the additive-result
slide. Its closing step still needs the final representation-audit result before the
deck is refrozen. The preliminary heatmap remains visible and explicitly labeled as
non-actionable development evidence.

The obsolete parallel content brief, readiness checklist, one-use additive-chart
renderer, and superseded July 16 image-generation prompt were removed. Rendered
decks and every visual asset they load remain preserved.

## Preserved recovery assets

Do not delete:

- `backups/stage1_gtex_to_archs4_training_98e2cba/`;
- `backups/stage1_k4_final_refit_e8c0383/`;
- `backups/stage1_k4_gtex_v11_6cc8095/`;
- `backups/stage1_k4_external_scout_182207b/`;
- current `checkpoints/`, `data/archs4/`, and final tracked `artifacts/`; or
- any active Stage 2 result root or immutable checksum manifest.

Large data, checkpoints, runtime results, and backups remain ignored by Git.
