# NASA RNA MoE: concise milestone chronology

**Last updated:** 2026-07-28 13:46 PDT / 2026-07-28 20:46 UTC

Start with [`docs/current-status.md`](docs/current-status.md). It is the canonical
operational handoff. This file retains only decision-relevant milestones; the
2,800-line pre-cleanup chronology remains recoverable from Git commit `2bc1bef`.

## Active — Stage 2 seed-stability diagnosis

The preliminary additive transfer map is not accepted as the final Stage 2 product.
Only liver ← skin was positive in all three original seeds, while several small
mean-positive effects changed sign.

The frozen diagnosis crosses three pooled trunks (17, 42, 101) with three independent
optimization/mask/loader replicates (211, 223, 227). Every combination runs the same
24-arm FP32 schedule across the unchanged eight additive edges:

- eight target-organ-only references;
- eight target-organ plus named-donor additions; and
- eight additional-target-organ controls.

Frozen identifiers:

- input-bound implementation:
  `3a27ffabdcb6d2a4209006452958b30cf0fff520`;
- schedule SHA256:
  `066144402245cac3114fee71a7dd8e0cfc4a6f4f74b9df405510e9b4e7b0c9a3`;
- arm-definition SHA256:
  `e206e20ae46721d6d353f0179afd9f4acbc0a19cb81d9d89e8b7018d24063c9d`;
- protocol SHA256:
  `cb6d32c5b96bb510c58e45bb6787feef3a8b088f069a7d3efce21d48631c7262`.

The experiment launched on both A100 hosts at 2026-07-28 19:52 UTC. It does not
select a best seed or favorable edge.

Prespecified branches:

1. continue raw addition only with at least three stable-helpful edges;
2. if signs are reproducible but mostly harmful, pivot to negative-transfer
   avoidance/selective sharing; or
3. if optimization instability dominates, test one recipient-protected sharing
   implementation and then pivot if stability still fails.

Organ is the strongest validated starting axis, not a permanent restriction.
Post-diagnosis alternatives may include hierarchical metadata, pathway programs, or
continuous expert-residual representations under the same stability and confound
gates.

## 2026-07-28 — Stage 2 recipient-preserving addition

All three prespecified seeds completed and passed immutable checksum verification.
The evaluation checksum-manifest SHA256 is
`0c005678d312ac8924e498249f215f45d33153704fc5fc646248596b32e5bf7b`.

Results for adding 750 donor-organ draws while retaining 1,500 target-organ draws:

- five of eight mean effects were positive;
- only liver ← skin was positive in all three seeds with its interval above zero:
  +1.956%, 95% CI +1.647% to +2.244%;
- four edges beat all three random auxiliaries in all three seeds; and
- zero of eight named donors beat 2,250 target-organ draws in all three seeds.

Decision: protect target-organ exposure first. Cross-organ addition requires a
validated directional rule.

## 2026-07-28 — Stage 2 same-budget substitution

The complete 56-edge directed matrix compared 750 target-organ plus 750 donor-organ
draws with 1,500 target-organ draws.

- all 56 edges were negative in all three seeds;
- all paired donor-bootstrap intervals were below zero;
- mean effect was −3.273%;
- the independent seed-101 operational replication reproduced the scientific
  matrices and heatmap hashes exactly.

Decision: under a fixed budget, another organ is not a better use of training draws
than additional target-organ exposure. This does not imply that all parameter sharing
is harmful.

## 2026-07-27 — GTEx-to-ARCHS4 external evaluation

The models were trained only on GTEx and evaluated once across heterogeneous ARCHS4
studies.

The first expression access enforced the frozen 14,000-nonzero-gene floor. Exactly
six failing rows were excluded without replacement or threshold change, so the final
evidence is labeled `post_access_qc_amended_external_evaluation`.

Final cohort:

- 821 samples;
- 63 connected studies;
- all eight target organs; and
- all seeds 17, 42, and 101 retained.

Results versus the general pooled model:

- correct organ specialist: 3.797% lower MSE;
- target-hidden hard route: 3.633% lower;
- target-hidden soft route: 3.676% lower;
- equal-capacity pooled adapter: effectively neutral; and
- random K8 partitions: effectively neutral.

Every routed condition improved in every retained seed, and paired connected-study
bootstrap intervals excluded zero. A new untouched cohort remains necessary for a
pristine preregistered confirmation.

## 2026-07-23 — Stage 1 GTEx validation

The final K4-EPE candidate used brain, liver, skeletal-muscle, and skin specialists
with pooled fallback for adipose. It passed the prespecified GTEx V11
donor-controlled validation on 6,795 samples from 930 donors.

- true K4: 3.301% lower donor-balanced equal-organ MSE than pooled;
- target-hidden blind K4: 3.157% lower;
- router accuracy: 98.03%; and
- 95.63% of the true-routing gain recovered.

Random, capacity, seed-stability, active-organ-safety, residual-correlation, and
router-recovery gates passed.

## 2026-07-22 — Stage 1 development decision

The initial K5 organ experiment showed strong routed gains but failed to establish
that the proposed organ partition itself was better than matched random structure.
Controlled K4/K5 retraining, exposure matching, and external validation resolved
that ambiguity and nominated K4-EPE.

Important lesson: routed performance alone does not prove that a named biological
partition is meaningful. Capacity-matched random and pooled controls are required.

## 2026-07-17 — Stage 0 interspecies result

The corrected study-aware evaluation repaired normalization, test-fitting,
test-derived-baseline, and sample-weighting errors from the early analysis.

An expression-only species router achieved 99.0% balanced accuracy. After the
globally shuffled pooled model strengthened the general baseline, blind soft routing
still reduced MSE by 11.42% versus the fixed blend with positive MSE and
residual-correlation intervals.

See [`docs/stage0-final-result.md`](docs/stage0-final-result.md). The invalid early
balanced-evaluation numbers remain only in Git history.

## 2026-07-28 — Presentation and repository consolidation

The July 30 deck and all future decks use
[`presentation/atrium-theme-template.md`](presentation/atrium-theme-template.md).
The presentation workflow is now:

- audience-first: assume no technical background;
- visual-first: use charts and diagrams when they clarify the result;
- script-free: maintain a concise content brief rather than narration;
- plan → results → next, with results occupying most of a biweekly update.

Historical rendered decks remain unchanged. Obsolete talking scripts, completed
watcher/report-generation code, invalid early result files, redundant plots, stale
root planning/report documents, duplicate run bundles, and redundant local backups
were removed after their crucial conclusions were consolidated into canonical docs.

## Preservation policy

Kept:

- active training/evaluation code and tests;
- frozen protocols, manifests, hashes, and final result summaries;
- canonical Stage 0/1/2 result documents;
- final or still-scientifically-useful model backups;
- historical rendered presentation decks and assets they require; and
- full pre-cleanup history in Git.

Removed:

- narration scripts;
- completed one-use watcher/report-generation utilities;
- superseded root plans and reports;
- invalid early tracked outputs;
- generated sweep plots; and
- byte-identical or clearly superseded local backup copies.

## 2026-07-28 — July 30 deck legibility pass

The active July 30 deck and reusable Atrium template were tightened after visual
review:

- the prior 11 px minimum in the main content region was raised to 14 px;
- slides 8–9 now reserve roughly three quarters of a wider canvas for their result
  figures, without the decorative arch/window frame or a contrasting white chart
  canvas;
- the heatmap and additive-effect chart were checked at 1920×1080 for embedded-label
  legibility; and
- bottom-right page tokens were replaced by centered progress dots, with the active
  slide enlarged and darkened while keyboard and 180 ms slide transitions remain.
