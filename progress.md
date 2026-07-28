# NASA RNA MoE: concise milestone chronology

**Last updated:** 2026-07-28 14:16 PDT / 2026-07-28 21:16 UTC

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
[`presentation/design.md`](presentation/design.md).
The presentation workflow is now:

- audience-first: assume no technical background;
- visual-first: use charts and diagrams when they clarify the result;
- script-free: make the rendered deck self-contained rather than maintaining
  narration;
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

The active July 30 deck and reusable presentation specification were tightened
after visual review:

- the prior 11 px minimum in the main content region was raised to 14 px;
- slides 8–9 now reserve roughly three quarters of a wider canvas for their result
  figures, without the decorative arch/window frame or a contrasting white chart
  canvas;
- the heatmap and additive-effect chart were checked at 1920×1080 for embedded-label
  legibility; and
- bottom-right page tokens were replaced by centered progress dots, with the active
  slide enlarged and darkened while keyboard and 180 ms slide transitions remain.

## 2026-07-28 — Anthropic field-journal design merge

The prior Atrium instructions were merged into a more detailed
[`presentation/design.md`](presentation/design.md), using the supplied Anthropic
scientific-field-journal reference as the primary visual authority. The canonical
system now specifies:

- Ivory Medium parchment, layered ivory/oat/manilla paper surfaces, Slate Dark ink,
  Stone rules, and one restrained Clay accent;
- Anthropic Serif/Sans/Mono family tokens with portable Source Serif 4, Inter, and
  technical-monospace fallbacks;
- serif editorial body copy with sans-serif reserved for navigation, labels, and
  compact metadata;
- flat elevation without shadows, restrained 24 px cards, and the former Atrium arch
  only as a sparse functional project adaptation; and
- all previously frozen audience, narrative, chart-legibility, pagination,
  transition, and scientific-claim safeguards.

The July 30 deck was updated to this palette and type system. July 9 and July 16
remain unchanged historical artifacts.

## 2026-07-28 — Restrained color and readable-note correction

The Anthropic merge was corrected so it does not flatten scientific comparisons
into gray:

- the main Stage 1 bar chart now uses neutral baseline, Atrium Sage for the known
  specialist, Muted Blue for automatic hard routing, and Soft Sage for the blend;
- sage and muted blue are canonical functional data accents but remain prohibited
  as gratuitous surface decoration; and
- every retained footnote, caveat, evidence label, and interpretive chart caption is
  now at least 16 px. Notes are kept only when they change interpretation; otherwise
  they should be removed.

Slides 4–6 and 8–9 were rerendered at 1920×1080. The larger notes remain clear of
content and centered pagination.

## 2026-07-28 — Twenty-percent central scale increase

The active deck was enlarged as a complete visual system:

- standard content width increased from 1440 px to 1720 px at 1920×1080, while
  result slides may use up to 1760 px;
- peripheral padding decreased from 3vw/30 px to 2vw/22 px;
- the center-content floor increased from 14 px to 16 px;
- headlines, body text, cards, statistics, bars, labels, gaps, and chart captions
  were enlarged together rather than scaling headlines alone; and
- important notes now render at 17 px in the active deck, above the universal 16 px
  minimum.

All nine slides were rerendered at 1920×1080. The measured content canvases are
1720 px and 1760 px, the minimum visible center text is 16 px, and no slide reports
horizontal or vertical overflow.

## 2026-07-28 — Semantic winner highlight

The Stage 1 comparison chart now assigns Muted Blue to the verified numerical winner
(correct organ specialist, +3.797%), Sage to automatic single choice, Soft Sage to
the automatic blend, and neutral gray to baseline. The design specification now
requires a semantic `.winner` class so the highlight follows the result rather than
a hard-coded bar position. It also records the exact current canvas, typography,
card, caption, transition, pagination, and spacing values for reuse.

## 2026-07-28 — Dedicated future-work closer

The July 30 deck now ends with a tenth slide rather than embedding the entire next
step in the additive-result slide. The closer states the active frozen diagnosis and
three prespecified branches:

- reproducible helpful transfer → selective sharing and untouched multi-study
  validation;
- reproducible but mostly harmful transfer → negative-transfer prevention and
  protected/selective sharing; or
- optimization instability → one protected-sharing test, then broader pathway,
  biological-state, or expert-residual representations if needed.

The shared end product is a reproducible rule for which biological domains should
share training information and which should remain isolated. The slide passed
1920×1080 visual and overflow checks, and pagination now generates ten dots
automatically.

## 2026-07-28 — Presentation package consolidation

The presentation package was reduced to the rendered decks, the assets those decks
load, and the canonical design specification. Removed:

- the July 30 content brief;
- the July 30 readiness checklist;
- the completed one-use additive-chart renderer; and
- the superseded July 16 image-generation prompt.

Two `.DS_Store` metadata files and the ignored July 15 corrected-interspecies driver
log were also removed locally. The log's decision-relevant results are preserved in
`docs/stage0-final-result.md`.

The July 9, July 16, and July 30 decks, the historical July 16 plan image, both
current Stage 2 result figures, and `presentation/design.md` remain. Deleted files
remain recoverable from Git history.
