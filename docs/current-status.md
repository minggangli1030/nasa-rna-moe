# NASA RNA MoE: current canonical status

**Updated:** 2026-07-30 22:05 PDT / 2026-07-31 05:05 UTC

This is the operational handoff. Historical detail remains in Git through commit
`2bc1bef`; concise milestones are in [`../progress.md`](../progress.md).

## Current phase

The frozen OSDR downstream-development evaluation is complete. Exact evaluator
commit `61766ee` finished at 2026-07-30 21:26 PDT on 292 samples from 18 studies;
all three Stage 1 caches, grouped splits, converged elastic-net fits, and artifact
hashes verify.

The prespecified downstream-positive gate failed. True-organ minus pooled AUROC
was −0.051, −0.003, and +0.018 across seeds 17, 42, and 101. Hard and soft
input-only routing also failed the all-seed direction requirement. Mean learned
AUROC was 0.590–0.605, versus 0.726 for raw expression and 0.733 for fold-fit
PCA-64. No seed or representation was selected.

This does not invalidate the 3.6–3.8% external masked-gene reconstruction gain. It
shows that the current masked score-panel prediction contract does not preserve
enough cross-species spaceflight-state information to beat simple observed
expression baselines. Raw expression and PCA are therefore mandatory gates for
the final model, and downstream utility must be designed explicitly rather than
inferred from reconstruction. Canonical result:
[`stage1-osdr-downstream-result.md`](stage1-osdr-downstream-result.md).

The immediate branch remains bounded: finish the frozen training-only Tier-1
screens for tissue site, age/sex, and Hallmark-50; add at most one axis that clears
within-organ permutation, nuisance, coverage, all-seed, donor-bootstrap,
per-organ safety, and independent downstream-label gates; otherwise close the
August 2 architecture as the validated organ MoE with pooled fallback. Cell
composition remains out of scope for this cycle.

## Completed background

Stage 2B B0–B4 and the multiaxis Tier-0 inventory are complete and locally
checksum-verified. The prespecified target-agreement gate failed: the absolute
cross-trunk coefficient correlations were high, but their margin over the random
basis was only about 0.018–0.020. Cross-seed grouped probes remained strong
(gene-space recovery about 0.58–0.60; median component correlation about
0.977–0.979), so the result is reproducible predictive structure without a unique
shared coordinate interpretation. Phase C was not authorized.

B4 triggered human review because tissue site exceeded organ on both residual
targets in all three seeds. For pooled reconstruction \(R^2\), organ versus site was
0.664 versus 0.809, 0.591 versus 0.775, and 0.596 versus 0.775. For post-private
coefficients it was 0.248 versus 0.538, 0.282 versus 0.559, and 0.285 versus 0.565.
This is a candidate signal, not authorization to train: tissue site must now clear
within-organ permutation, nuisance, coverage, all-seed, donor-bootstrap, and
downstream-label gates.

The schedule was reordered around the binding risk identified in `CLAUDE.md`: the
downstream harness was built against frozen Stage 1 checkpoints rather than
waiting for the final model. A five-field readiness audit found one executable
primary task. Strict eight-organ OSDR mapping yielded 892 labeled metadata rows,
43 studies, and 45 study-organ units with both exact structured `Space Flight` and
`Ground Control` labels. The repository's validated NASA API downloader and strict
mouse-ortholog, log1p-TPM, 14,000-gene QC path prepared the frozen cohort. The
exact candidate metadata and audit are at
`artifacts/final_evaluation/downstream_readiness/`.

The OSDR downstream-development protocol was frozen before download at
`artifacts/final_evaluation/stage1_osdr_downstream/protocol.json`, SHA256
`04e8354b1417c2f4bb4459f053a4e343dce1e65a9b552e16f7fea08c52d8abb9`.
QC failures and study-organ units losing either class are excluded without
replacement. The benchmark uses identical study-grouped splits and equal elastic
net tuning for raw expression, PCA, pooled, pooled-adapter, true-organ, and blind
hard/soft Stage 1 representations. This is cross-species downstream development,
not an untouched final confirmation.

The download and frozen QC completed: 297/892 requested metadata rows survived the
14,000-nonzero-gene rule, and 292 samples from 18 studies retain an exact
two-class study-organ contrast. No replacements were added. The first feature-cache
attempt failed before producing model outcomes because it narrowed to 292 rows
before validating a 297-row coverage artifact. The failed empty lineage is
preserved. A versioned fix validated full coverage order before explicit
subsetting. Later implementation-only lineages corrected safe string
serialization and fail-closed solver convergence without changing the frozen
cohort, splits, representations, seeds, or grid. They emitted no accepted model
result. Exact commit `61766ee` produced the verified evaluation summarized above.

ARCHS4 disease/tumor is cut from the core until free-text candidates receive
independent phenotype curation; its existing keyword flags are not labels. TCGA is
also cut because neither a cohort contract nor expression matrix is local.
Cell-composition screening, matched-data BulkRNABert retraining, BulkFormer-37M
retraining, survival, and drug response are removed from the core calendar.
Hallmark-50 programs, tissue site, and demographics remain candidate screens.

Stage 2 completed the frozen seed-factorized stability diagnosis. Raw
recipient-preserving organ-to-organ addition did not produce an actionable helpful
rule. The user approved the representation-first pivot rather than spending the next
cycle on another organ-pair training implementation.

The read-only audit of the already validated organ experts is complete:

1. extract per-gene functional corrections and reconstruction effects from all three
   frozen GTEx K8 seeds on the same donor-disjoint calibration set;
2. compare the organ expert with the pooled trunk, pooled adapter, and three
   donor-balanced random-K8 controls;
3. all 8/8 organs retained positive donor-bootstrap effects versus both generic and
   random controls; but
4. 0/8 passed the complete exact-gene representation gate.

The exact protocol is frozen before opening these gene-level outputs at
`artifacts/stage2_organ_expert_mechanism/representation_pivot_protocol.json`.
Minimum cross-seed correction cosines ranged from −0.051 to 0.350 and minimum
top-100 overlaps from 0 to 0.143. The frozen decision is
`organ_axis_insufficient_pivot_multi_attribute`.

This audit performed no fitting, no seed selection, and no ARCHS4 access. Organ
experts remain the benchmark, but exact genes and raw organ pairs are not stable
enough to guide sharing. The next branch freezes a training-donor-only continuous
expression basis and tests coarser modules plus tissue site nested within organ.
Canonical result:
[`stage2-representation-pivot-result.md`](stage2-representation-pivot-result.md).

That next audit is now frozen at
`artifacts/stage2_organ_expert_mechanism/multiscale_attribute_protocol.json`
(SHA256 `78d772cb0f171707b8707756cc8e38dd5b286dca85361a8d14daaa2140dace51`).
It uses 32 outcome-independent expression components fit on the 750 GTEx training
donors and reports all 23 manifest-eligible tissue sites. No expert is retrained.

The audit is complete:

- module gate: 1/8 organs passed (adipose);
- tissue-site gate: 2/23 passed (both adipose sites);
- the passing sites span only one organ, below the frozen hierarchical gate; and
- decision:
  `no_stable_existing_representation_design_explicit_program_heads`.

Skin was the closest additional organ but missed the frozen top-module overlap gate;
that threshold is not changed post hoc. The next Stage 2 implementation is an
aligned factorized residual model: a fixed training-derived program decoder, shared
coefficient head, and organ-private residual path, with three-seed donor-disjoint
controls.

That pivot is now implemented and protocol-frozen. Commit
`93e5a9b5b95652e37b563c8bc649bb058524b20b` is deployed to the clean detached VM
worktree
`/media/volume/moe-reboot/worktrees/stage2_aligned_program_93e5a9b`.
The exact protocol SHA256 is
`5cecd43fd75bd832c6be7fa57c9c56fc752e01288184e9100758c09768952fd8`.

The mechanical smoke and all three 1,500-update runs are complete. The full run
finished at 2026-07-29 16:15 PDT; the repaired evaluator and immutable result
finalization completed at 16:17 PDT. Every utility gate passed:

- shared+private versus pooled: +36.620%, +35.082%, and +30.051% in seeds 17, 42,
  and 101;
- shared+private beat organ-private, random-basis+private, and matched generic
  controls in every seed with donor-bootstrap intervals above zero; and
- it retained 131.7% of the organ-private gain on average.

However, the coefficient non-collapse gate failed. Cross-seed coefficients were
highly correlated (minimum flattened donor correlation 0.834; minimum median
component correlation 0.900) but had effective rank only 1.22–1.31 versus the
frozen requirement of 8. Decision:
`utility_pass_alignment_fail_revise_coefficient_identifiability`.

The first evaluator correctly stopped on an object-string serialization mismatch.
No predictions or models changed. Evaluator commit
`ba07442d193d00a11c39546c26eb29954699260c` reconstructed text labels from the
separately hash-pinned manifest, loaded only numeric arrays without pickle, and
produced the verified result in a distinct path. Root checksum-manifest SHA256:
`413cb73ad47db0f400682bc1001bcc426f668f3c690abbe6300b3d3786efc0ac`.
Canonical implementation and result handoff:
[`stage2-aligned-program-heads.md`](stage2-aligned-program-heads.md).

A read-only collapse diagnosis subsequently localized the failure. The fixed
decoder has effective rank 29.00, while the actual post-private residual projected
into that same span has sample-level effective rank 12.89–14.34 and within-organ
rank 16.48–17.04. The learned sample coefficients remain rank 1.42–1.66. Thus the
target is not intrinsically one-dimensional.

The learned leading direction is nevertheless almost identical across seeds and is
strongly associated with organ/site identity, especially a brain-versus-other
contrast, and with pooled reconstruction difficulty. The present joint,
decoded-MSE-only training therefore converged on a stable shortcut. The bounded
repair is private-first residualization and direct per-component standardized
coefficient-target supervision while keeping the existing head and exact decoder.
A five-fold donor-grouped seed-17 probe showed that the current global hidden
summary already predicts high-rank oracle coefficients (rank 12.40, median
component correlation 0.963) and recovers 69.8% of remaining error versus 33.6% for
the trained head. Canonical diagnosis:
[`stage2-aligned-program-collapse-diagnosis.md`](stage2-aligned-program-collapse-diagnosis.md).

The user authorized the bounded repair. It is implemented and protocol-frozen at
commit `51ab2f58ee683cd7b10f0d62c86e8e77354009dc`; protocol SHA256
`89f6e97218a1871782e08725104e04ae8d1d40001d74ec4e09e01a32e80c5764`.
The repair trains the organ-private path first, freezes it, projects only
training-draw masked residuals into the unchanged decoder, and supervises the
unchanged shared head on standardized coefficients. It includes extended-private,
extended-generic, and random-basis controls plus per-organ safety gates.

The three-seed repair and frozen evaluator completed at 2026-07-29 23:14 PDT. It
retained strong utility: +37.756%, +34.145%, and +35.769% versus pooled and
+3.207%, +5.885%, and +6.385% versus the phase-1 private path. It also beat the
random-basis condition in every seed.

It did not recover an acceptable representation. Minimum sample, donor, and
within-organ effective ranks were 1.815, 1.392, and 1.952, versus frozen thresholds
of 8, 6, and 8. Minimum flattened donor correlation was 0.271 versus 0.5. Skin was
harmed by 5.890% and 6.478% in two seeds, crossing the frozen 5% safety boundary.
Decision:
`coefficient_supervision_repair_fail_pivot_representation`.

A post-completion integrity audit also invalidated the two nominal extended-budget
controls: reused optimizers remained at zero learning rate after phase 1. The
phase-1 and “extended” private states and scores are exactly identical in all three
seeds. The candidate and random-basis heads used new optimizers and are unaffected.
The failed rank, alignment, and safety gates independently mandate the same pivot,
so the run is not repeated or tuned.

Canonical result:
[`stage2-aligned-program-repair-result.md`](stage2-aligned-program-repair-result.md).
The next branch stops repairing raw-expression PCA coordinates and first audits
mask-target invariance, then freezes a residual-aligned, mask-consistent,
multi-attribute representation with organ experts retained as the benchmark.

The external methodological review in `CLAUDE.md` has now been evaluated and
translated into a corrected Stage 2B execution plan:
[`stage2b-mask-consistent-sharing-plan.md`](stage2b-mask-consistent-sharing-plan.md).
Its strongest additions are fail-closed phase-transition checks, a canonical
full-score-mask input and target, functional share/decline stability as a primary
gate, and a conservative refusal-rule deliverable.

Two proposed claims were corrected before adoption. The existing donor-rank
calculation is across individual donor vectors and is not capped at seven; existing
oracle donor ranks reach 8.05. Also, pooling non-score hidden states from a partial
mask would remain mask-dependent because transformer states can attend to visible
score genes. Stage 2B must instead cache a full-score-mask forward pass.

Claude's second review accepted the implementation-backed corrections. Codex's
round-3 closure accepts the added cross-trunk oracle-transfer audit, makes the
three-trunk continuation gate a stopping gate, requires canonical-cache round trips
before any utility result is interpreted, and requires refusal coverage so a
refuse-everything policy cannot pass.

The first Stage 2B scientific candidate is now resolved as a clean causal repair:
keep the exact expression-PCA decoder, frozen pooled trunks, valid phase-1 private
paths, donor cohort, and evaluation estimand; change only the mask-dependent
input/target, broken phase controls, and absent safety gate. Residual/pathway bases
and shared experts are deferred rather than run in parallel.

Claude's final implementation-only additions are accepted: exhaustive cache keys,
fixed-batch deterministic cache reproduction, one gene-space-selected ridge value
shared across trunks, a nonsaturated gate with a dead-parameter guard, explicit
rank result records, training-only normalization, organ-balanced loss exposure, and
a cross-host determinism smoke.

Phase A is implemented in commit
`b4100a1efd0090064a1a079fe658d7f116526373` and pushed to `origin/main`.
It adds reusable positive-LR, exact optimizer-coverage, early/final parameter-delta,
and tensor-hash guards; constructs fresh second-phase optimizers; and requires a
complete seed-by-organ condition matrix. The focused local Stage 2 suite passes
38 tests.

The exact commit is deployed in the clean detached primary-VM worktree
`/media/volume/moe-reboot/worktrees/stage2b_phase_a_b4100a1`. The seed-17
mechanical smoke completed at 2026-07-30 13:39 PDT in the new path
`/media/volume/moe-reboot/results/stage2b_phase_a_smoke_b4100a1`. All 11 immutable
entries verify. Both phases completed 2/2 updates; all six declared module-phase
combinations had positive parameter deltas and changed tensor hashes. The session
exited and the A100 returned idle. This smoke reused the old frozen repair inputs
solely to prove the guards execute; it creates no new scientific result.

Phase B is implemented at exact commit
`20d000e0b8055f60d7dee8796b52834bd829ab43`, pushed to `origin/main`, and
deployed to exact detached worktrees on both GPU hosts. The single training-only
B0–B5 protocol was frozen before diagnostic output at SHA256
`db7cd772345272876cd01a603deb720b46c36d0cfb5252e3d245e7e58f5182be`.
It binds all three pooled trunks and valid phase-1 private states, the 7,369
balanced training samples/750 training donors, the exact decoder and score indices,
and every prior transfer input used by the refusal audit. Calibration and ARCHS4
remain sealed, and neural checkpoint updates are prohibited.

The prespecified 256-sample-per-trunk gene-space probe completed and selected one
shared ridge value, lambda 0. The primary real-data cache smoke then passed on 16
seed-17 samples: repeated canonical extraction was bitwise identical, B1 completed,
and all immutable checksums verified. The identical smoke on the secondary host
produced exact matching hashes for every canonical and B1 array despite its
different CUDA/driver stack. This clears the cross-host split gate.

Full read-only extraction is complete for seeds 17, 42, and 101: each contains
7,369 rows, reports bitwise determinism, and passes its immutable checksum manifest.
Seed 42 completed at 2026-07-30 15:18:25 PDT. The independent secondary-host
seed-101 lineage was verified locally and transferred to the distinct primary path
`seed101_secondary`; the primary launcher's future lineage was not overwritten.

Detached fail-closed screen `stage2b-to-multiaxis-010d629` verified all three caches
and launched the exact frozen B0–B4 evaluator at 15:19 PDT. It does not rerun B5.
After B0–B4 checksums verify, the same operational watcher immediately builds the
training-only multiaxis Tier-0 inventory. Its implementation is commit
`010d629be5b273618efa8183c54209f3a173d203`, deployed outside the clean scientific
worktree; the evaluator itself remains exact commit
`20d000e0b8055f60d7dee8796b52834bd829ab43`.

The first independent Tier-0 task also completed while B0–B4 was running. Exact
open-access GTEx v8 subject and sample annotations were joined by sample/donor ID to
all 7,369 training rows and 750 donors. Age bracket and raw sex code are complete;
death Hardy scale is 0.46% missing. RIN and ischemic time are each 15.04% missing
and remain nuisance controls. No residual or efficacy outcome was read. Canonical
compact artifact:
`artifacts/stage2_organ_expert_mechanism/multiaxis_metadata_d265073/`.

The independent B5 refusal evaluator is already complete. The frozen
similarity-aware model reduced leave-one-organ-out MSE to 0.586 versus 0.726 for the
best identity-only null, flagged 25% of directed edges, and had additive-holdout
rank correlation 0.595 across eight edges. This is promising training-development
evidence, not a universal refusal rule; the additive holdout is very small and its
classification recall was weak.

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

The final presentation is scheduled for **2026-08-17**. The execution order is now
time-bounded: build the downstream harness immediately on Stage 1, close the
MoE/secondary-axis design by August 2, launch final training by August 7, and swap
the final model into the validated harness in August 10–14. Canonical
roadmaps:

- [`axis-smoke-and-final-evaluation-roadmap.md`](axis-smoke-and-final-evaluation-roadmap.md)
- [`august-17-downstream-and-multiaxis-plan.md`](august-17-downstream-and-multiaxis-plan.md)

The immediate post-B0–B5 model work is a cheap organ-conditional screen, not full
training of every proposed axis. Tissue site is already covered by Stage 2B B4.
Age/sex and hash-pinned Hallmark immune/metabolic/mitochondrial/contractile/ECM/
cell-cycle/stress programs enter one common grouped-CV residual screen.
Disease, treatment, hypoxia, and spaceflight are primarily downstream targets and
must not be used to select an expert on the same final-test cohort.

The final external ladder now distinguishes BulkRNABert from BulkFormer.
BulkRNABert is the closer public masked-reconstruction architectural peer and its
published checkpoint is used only on a non-overlap downstream cohort.
BulkFormer-147M is a published SOTA ceiling. Retraining either family is an
extension and cannot delay the core table.
The final evidence package will compare raw expression, PCA/NMF, the pooled trunk,
pooled-plus-organ-label conditioning, organ-MoE routing, published BulkRNABert, and
BulkFormer under identical donor/patient/study-disjoint splits. Organ prediction
is only a sanity check; primary tasks must test disease/state, spaceflight/stress,
or low-resource adaptation so the result is not circular.

The same roadmap defines candidate biological axes beyond organ—tissue site,
disease/physiological state, age/development, sex, and continuous pathway
programs—and separates them from technical nuisance variables. Cell composition is
deferred beyond August 17.
The preferred integration is factorized: a protected organ expert plus optional
site/condition/pathway residual adapters, each with its own safety gate, rather than
a sparse Cartesian expert for every attribute combination.

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
slide. Its final future-work slide now states the current limitation directly:
aggregate organ utility survives, but the existing transfer/program map is not
general or stable. It presents the shared-program plus organ-private architecture
as planned work, not as a completed result. The preliminary heatmap remains visible
and explicitly labeled as non-actionable development evidence.

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
