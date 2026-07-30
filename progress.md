# NASA RNA MoE: concise milestone chronology

**Last updated:** 2026-07-29 23:30 PDT / 2026-07-30 06:30 UTC

Start with [`docs/current-status.md`](docs/current-status.md). It is the canonical
operational handoff. This file retains only decision-relevant milestones; the
2,800-line pre-cleanup chronology remains recoverable from Git commit `2bc1bef`.

## 2026-07-29 — Aligned shared/private program-head pivot launched

The user approved implementing the next architecture after the raw-transfer and
read-only representation branches failed to produce a general stable rule.

The implementation fixes the representation coordinates by construction: an
input-derived 32-value shared head decodes through the frozen GTEx-training
expression basis, while an organ-private residual branch protects specialization.
It includes shared-only, private-only, matched generic-capacity, random-basis, and
donor-balanced random-label controls. All six conditions share the same fitting
schedule and masks within seed.

The protocol was frozen before scientific training outcomes at SHA256
`5cecd43fd75bd832c6be7fa57c9c56fc752e01288184e9100758c09768952fd8`.
Success requires both utility and coefficient alignment; neither alone is enough.
Exact commit `93e5a9b5b95652e37b563c8bc649bb058524b20b` is deployed to a
clean detached primary-VM worktree. The three-seed mechanical smoke is active in
screen session `stage2-aligned-program-smoke`; seed 17 passed the real finite-loss
GPU update, full calibration-cache, and checkpoint path, while seed 42 is active.
Detached session `stage2-aligned-program` will launch the full frozen run
automatically when the exact smoke completes.

The July 30 deck was changed only on the final future-work slide. It reports the
shortcoming as a limitation—not a failed-result narrative—and presents the
aligned shared/private architecture as the planned pivot.

The smoke and full three-seed run subsequently completed. Shared+private reduced
balanced calibration MSE versus pooled by 36.620%, 35.082%, and 30.051% in seeds
17, 42, and 101. It beat organ-private, random-basis+private, and matched generic
controls in every seed with all donor-bootstrap intervals above zero. Thus every
frozen utility gate passed.

The representation gate did not fully pass. Shared coefficients were strongly
correlated across seeds, but their effective rank was only 1.22–1.31, below the
frozen minimum of 8. The model found a useful, reproducible, nearly one-dimensional
correction rather than a non-collapsed 32-program representation. Prespecified
decision:
`utility_pass_alignment_fail_revise_coefficient_identifiability`.

The first evaluator failed closed because string labels had been serialized as
object arrays. The three model runs and score arrays were intact. A separate clean
evaluator commit reconstructed strings from the hash-pinned manifest and never
enabled pickle loading. Its compact result passed all checksums at
`artifacts/stage2_organ_expert_mechanism/aligned_program_evaluation_ba07442/`.

The subsequent read-only collapse diagnosis showed that the fixed decoder is
high-rank (29.00) and that the actual post-private residual supports sample-level
rank 12.89–14.34 in the same span. The trained head recovered only rank 1.42–1.66.
Its repeated dominant direction primarily encodes organ/site identity and
reconstruction difficulty, with brain at the strongest extreme. The collapse is
therefore a reproducible shortcut caused by the present learning setup, not a
one-dimensional target or a random seed failure.

The bounded repair is to train and freeze the private path first, supervise the
shared head on standardized training-only residual projection coefficients in the
same exact decoder coordinates, retain decoded MSE as an auxiliary loss, and add
overall/within-organ anti-collapse and per-organ safety gates.

A five-fold donor-grouped seed-17 probe then showed that the existing global hidden
summary is already adequate: a simple linear ridge predictor produced rank-12.40
coefficients, median component correlation 0.963, and 69.8% error reduction versus
the private path. The trained nonlinear head achieved only 33.6%. The next repair
therefore changes the training sequence and target, not the model input or decoder.

The user authorized that bounded repair. Commit
`51ab2f58ee683cd7b10f0d62c86e8e77354009dc` and protocol SHA256
`89f6e97218a1871782e08725104e04ae8d1d40001d74ec4e09e01a32e80c5764`
are deployed to a clean detached primary-VM worktree. Seven focused local tests and
the VM projection preflight pass. The three-seed mechanical smoke is active, and a
separate continuation session will automatically start the full frozen run only
after the smoke marker is complete.

The three-seed repair subsequently completed. Aggregate utility remained strong:
35.9% mean reduction versus pooled, 5.2% versus the phase-1 private path, and 5.1%
versus the random basis. Direct supervision raised sample coefficient rank only to
1.81–2.18, far below the frozen minimum of 8; donor and within-organ ranks also
failed, flattened cross-seed correlation fell to 0.271, and skin crossed the 5%
harm boundary in two seeds. Frozen decision:
`coefficient_supervision_repair_fail_pivot_representation`.

The post-completion audit found that nominal extended-private and extended-generic
controls reused optimizers whose learning rate had reached zero after phase 1. The
private states and scores are exactly unchanged in all three seeds, so extended
budget superiority is not claimed. Candidate and random-basis training are
unaffected, and the independent rank/alignment/safety failures already determine
the pivot.

Stage 2 now stops patching expression-PCA coordinates. The prioritized next branch
audits partial-mask versus full-mask target invariance, removes score genes from
the shared-head input to align fit and evaluation, and freezes a common
training-only residual or pathway representation. Organ remains the validated
benchmark while tissue site and cross-cutting platform/quality/pathway attributes
become eligible axes.

## 2026-07-29 — Stage 2 representation-first pivot frozen

The user approved stopping raw organ-pair transfer as the main Stage 2 track. Organ
experts remain the validated benchmark, but Stage 2 now asks whether they express a
seed-stable functional representation before attempting another sharing mechanism.

A read-only protocol was frozen before opening gene-level outputs. It uses the same
1,826 GTEx calibration samples, 188 held-out donors, 4,634 score genes, and all
three Stage 1 seeds. It compares named organ experts with pooled, pooled-adapter,
and three donor-balanced random-K8 controls; requires cross-seed cosine, rank,
top-gene overlap, and donor-bootstrap gates; and forbids fitting, seed selection,
ARCHS4 access, and confirmatory individual-gene claims.

The extractor, evaluator, and strict launcher were implemented. The extractor must
round-trip the original frozen sample-level calibration scores before accepting any
gene program. If at least four organs pass the frozen representation gate, the next
step is a prospective test of whether signature structure predicts safe sharing. If
none pass, Stage 2 broadens beyond organ-only structure to a frozen multi-attribute
audit.

## 2026-07-29 — Exact-gene representation audit completed

All three frozen Stage 1 seeds were re-scored gene by gene on the same 1,826 GTEx
calibration samples and 188 held-out donors. Every seed round-tripped its original
pooled, organ, pooled-adapter, and random-K8 calibration scores before its cache was
published.

All eight organs retained positive donor-bootstrap effects versus the generic
adapter and random controls. However, zero passed the full representation gate:
minimum cross-seed correction cosine ranged from −0.051 to 0.350, efficacy rank
agreement was weak or inconsistent, and minimum top-100 overlap never reached 0.15.

Decision: preserve organ experts as the validated aggregate benchmark, but do not
use exact genes or lucky organ pairs as the Stage 2 sharing rule. The next frozen
audit tests training-donor-derived continuous expression modules and tissue site
nested within organ. Checksum-manifest SHA256:
`0fca3aa432c37668e26e5f1006983b71126510a1056e5a6329bab7aae80650ea`.

The follow-up protocol was frozen before its outputs at SHA256
`78d772cb0f171707b8707756cc8e38dd5b286dca85361a8d14daaa2140dace51`.
It uses 32 training-expression components and all 23 tissue sites meeting the
outcome-independent 30-calibration-donor floor. The evaluator and strict launcher
are implemented; no expert fitting or ARCHS4 access is permitted.

The follow-up completed: adipose was the only organ passing the module gate, and
its subcutaneous and visceral sites were the only 2/23 site passes. Because they
span one organ rather than the required three, the frozen decision is to stop
mining the current experts for a general hidden map and design explicit aligned
program heads. Skin was close but missed the frozen top-module overlap gate; the
threshold was not lowered. Checksum-manifest SHA256:
`a6a26cde213b66b07758498590fa5948bd8450bd4cee0de3fe117ee83dfe5edd`.

## 2026-07-29 — Stage 2 seed-stability diagnosis

All nine frozen trunk-by-optimization combinations completed: pooled trunks 17, 42,
and 101 crossed with optimization/mask/loader replicates 211, 223, and 227. Every
combination used the same 24-arm deterministic-FP32 schedule; no best seed or
favorable edge was selected.

Result:

- 0/8 edges were stable helpful;
- brain ← skin and skin ← adipose were stable harmful;
- 6/8 edges were unstable or negligible;
- liver ← skin averaged +3.011% but was positive in only 6/9 combinations and its
  factor-bootstrap interval crossed zero; and
- all eight named additions remained worse on average than 2,250 recipient-organ
  draws.

The prespecified instability branch therefore fired. Raw cross-organ addition is not
an actionable training policy. The protocol allowed one recipient-protected sharing
implementation, but the user subsequently approved moving directly to the
representation-first audit recorded above. Protected sharing remains a conditional
future option only if a stable representation supplies a prospective sharing rule.

Integrity:

- primary immutable verification: 379/379 entries;
- parallel immutable verification: 304/304 entries;
- compact transfer verification: 207/207 entries, excluding model checkpoints; and
- evaluation checksum-manifest SHA256:
  `66dc24a0d8541f37dfea99be9553677509cb3523da843609835d36febf7c6801`.

This is donor-disjoint GTEx development evidence, not study universality.

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

## 2026-07-29 — Presentation diagnosis update

The July 30 deck reports the completed nine-run stability result without adding a
failure narrative: 0/8 stable-helpful, 2/8 stable-harmful, and 6/8
unstable/negligible relationships. Its future-work slide will be refrozen after the
active representation audit so it reports the verified branch rather than an
obsolete protected-sharing promise.

The preliminary additive heatmap remains visible but is explicitly not a training
policy. Structural checks confirm ten slides, both referenced image assets,
180-millisecond reduced-motion-aware navigation, and centered dynamic pagination.
Pixel-level in-app preview was unavailable because local `file://` navigation was
blocked by browser security policy; that restriction was not bypassed.

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
