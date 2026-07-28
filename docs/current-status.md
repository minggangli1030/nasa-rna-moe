# NASA RNA MoE: current canonical status

**Updated:** 2026-07-28 13:44 PDT / 2026-07-28 20:44 UTC

This is the operational handoff. Historical detail remains in Git through commit
`2bc1bef`; concise milestones are in [`../progress.md`](../progress.md).

## Current phase

Stage 2 is running a frozen seed-factorized stability diagnosis. The purpose is to
decide whether recipient-preserving cross-organ transfer contains a reproducible
helpful rule or whether Stage 2 should pivot to negative-transfer avoidance,
recipient-protected sharing, or broader representation axes.

No best seed, favorable pair, or post-outcome schedule change is allowed.

## Active diagnosis

Crossed factors:

- pooled-trunk seeds: 17, 42, 101;
- optimization/mask/loader replicates: 211, 223, 227;
- unchanged named additive edges: eight;
- arms per crossed combination: 24; and
- training mode: deterministic FP32.

Each combination contains:

- eight A1500 target-organ references;
- eight A1500+B750 named-donor additions; and
- eight A2250 additional-target-organ controls.

Frozen identifiers:

- exact input-bound commit:
  `3a27ffabdcb6d2a4209006452958b30cf0fff520`;
- schedule SHA256:
  `066144402245cac3114fee71a7dd8e0cfc4a6f4f74b9df405510e9b4e7b0c9a3`;
- arm-definition SHA256:
  `e206e20ae46721d6d353f0179afd9f4acbc0a19cb81d9d89e8b7018d24063c9d`;
- protocol SHA256:
  `cb6d32c5b96bb510c58e45bb6787feef3a8b088f069a7d3efce21d48631c7262`.

Execution:

- launched: 2026-07-28 19:52 UTC;
- primary 40 GB A100 screen: `stage2-seed-stability-primary`;
- primary result root:
  `/media/volume/moe-reboot/results/stage2_seed_stability_3a27ffa_primary`;
- parallel 20 GB A100 screen: `stage2-seed-stability-parallel`;
- parallel result root:
  `/home/exouser/stage2_parallel/results/stage2_seed_stability_3a27ffa_parallel`;
- active monitor: `stage-2-seed-stability-diagnosis`.

Prespecified decision:

1. **Raw addition viable:** at least three stable-helpful edges.
2. **Reproducible but mostly harmful:** at least six stable signs but fewer than
   three helpful edges; pivot to negative-transfer avoidance/selective sharing.
3. **Optimization instability:** fewer than six stable signs; test one
   recipient-protected sharing implementation and pivot if stability still fails.

See [`stage2-seed-stability-diagnosis.md`](stage2-seed-stability-diagnosis.md).

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
- recipient-preserving donor additions may contain directional information.

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
- concise content brief: `presentation/2026-07-30-content-brief.md`;
- numeric/claim checklist: `presentation/2026-07-30-readiness.md`;
- Stage 2 heatmap:
  `presentation/2026-07-30-stage2-directed-transfer-heatmap.png`; and
- additive chart: `presentation/2026-07-30-stage2-additive-effects.png`.

All current and future decks use
`presentation/atrium-theme-template.md`. Presentations are audience-first,
visual-first, and script-free. Biweekly updates use plan → results → next, with
results occupying most of the talk. The template now enforces a 14 px minimum for
center content, frameless chart-dominant result slides, and centered progress dots
with the active slide darkened. July 9 and July 16 rendered decks remain unchanged
historical artifacts.

## Preserved recovery assets

Do not delete:

- `backups/stage1_gtex_to_archs4_training_98e2cba/`;
- `backups/stage1_k4_final_refit_e8c0383/`;
- `backups/stage1_k4_gtex_v11_6cc8095/`;
- `backups/stage1_k4_external_scout_182207b/`;
- current `checkpoints/`, `data/archs4/`, and final tracked `artifacts/`; or
- any active Stage 2 result root or immutable checksum manifest.

Large data, checkpoints, runtime results, and backups remain ignored by Git.
