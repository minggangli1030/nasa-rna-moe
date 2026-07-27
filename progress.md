# NASA RNA MoE: Progress and Operating Context

**Last updated:** 2026-07-27 13:37 PDT / 2026-07-27 20:37 UTC

> **Start with `docs/current-status.md`.** It is the compact canonical handoff with the
> current candidate, live workflow, hashes, safeguards, and next decision. This file is
> now the append-only chronological record; its older “Current Objective” sections are
> preserved for audit history and must not be mistaken for the current project state.

Older detailed logs remain recoverable in Git history through commit `10a5e0e`;
obsolete evaluation numbers are intentionally not repeated as current evidence.

## 2026-07-27 — Stage 2 practical value, novelty, and two-estimand design frozen

Stage 2 now has an explicit practical objective: learn which biological domains
should share training information and which should remain isolated. A directed
organ-to-organ transfer map can guide training-data selection for rare organs,
identify negative transfer, motivate hierarchical or partially shared MoE modules,
and preregister rational adaptation sources for scarce disease or spaceflight
datasets. The latter remains a source-selection hypothesis, not a spaceflight
performance claim.

The scientific contribution is not that expert interpretation, transfer learning, or
router analysis is individually new. The underexplored combination is to use
independently validated organ experts to derive mechanistic signatures, measure a
controlled directed training-transfer matrix, and prospectively test whether the
expert or input-only router structure predicts those transfer effects on held-out
studies.

The transfer protocol now separates two questions:

1. **Same total compute / substitution:** A1500 versus A750+B750 asks whether donor B
   is a better use of a limited training budget than more recipient-A data.
2. **Same recipient exposure / addition:** A1500 versus A1500+B750 asks whether B adds
   information while preserving all A exposure.

The additive arms also require A1500+random750 and A2250 self/update controls so an
organ-specific effect cannot be attributed to generic heterogeneity or simply more
optimization. The full 56-edge matrix is the compute-matched discovery analysis; a
small additive confirmation set must be frozen prospectively from development-only
expert/router predictions, not chosen after transfer outcomes are seen.

Transfer is not automatically biological. Platform, study composition, sample
quality, disease context, label error, unequal exposure, and generic expression
similarity remain alternative explanations. Study-disjoint evaluation, donor-atomic
sampling, random donors, seed replication, and platform/study controls are therefore
part of the primary protocol rather than optional follow-ups.

Execution has begun: `evaluation/build_stage2_directed_transfer_schedules.py` now
compiles exact deterministic schedules without reading expression or efficacy
results. The focused suite passes nine tests across this compiler and the frozen
expert audit. The substitution design contains 8 recipient-only arms, 28 unordered
organ-pair arms that yield all 56 directed effects at evaluation, and 24
donor-atomic random-auxiliary arms. The compiler supports additive named-donor,
random-auxiliary, and A2250 self controls, but fails closed unless additive edges are
prospectively supplied.

## 2026-07-27 — Stage 2 execution began with frozen-expert cross-dispatch

The dedicated final synthesis is now `docs/stage-1-end-result.md`. It records the
cautious study language: the Stage 1 result is study-robust in aggregate under
equal-study/equal-organ weighting, not invariant in every study. Study-specific
label quality, sequencing/processing quality, biological context, sample size,
gene-detection completeness, and donor-metadata quality can all produce genuine
heterogeneity.

The first executable Stage 2 audit is implemented and tested at commit `9fad92a` in
`evaluation/audit_stage2_gtex_k8_frozen_experts.py`. It reads only the checksum-bound
GTEx K8 calibration score caches, performs no model fitting or best-seed selection,
and does not load the completed ARCHS4 lockbox.

The completed audit contains 1,826 calibration samples from 188 held-out GTEx donors.
The named expert ranks first among all eight experts for every recipient organ after
averaging all three seeds. All 56 off-diagonal recipient/expert mean effects are
negative versus pooled. Named expert dispatch is positive in 23 of 24
organ-by-seed cells, while an off-diagonal expert is positive in only 2 of 168 cells.
The named-expert mean effects range from 0.921% for colon to 21.718% for skin.

This is strong development evidence that the experts learned distinct organ-aligned
functions. It is not controlled transfer: applying a frozen organ-B expert to organ A
does not estimate the effect of adding organ-B examples to a controlled
recipient-A training run. Gene/pathway residual caching and the directed-transfer
protocol are the next phases.

Canonical result:
`artifacts/stage2_organ_expert_mechanism/frozen_expert_audit_9fad92a/`
(audit-report SHA256
`87a210abfd4b06f3570c2a1e057d7c1f1ddb4182010c3afc25b098a36a663748`).

## 2026-07-27 — Stage 1 synthesis recorded; Stage 2 restored to organ experts

The user identified the central Stage 1 takeaway: the new reverse-direction
GTEx-to-ARCHS4 gain survives revealed-organ dispatch, hard target-hidden routing, and
soft target-hidden routing. The exact reductions are 3.797%, 3.633%, and 3.676%;
every condition is positive in seeds 17, 42, and 101. Together with the earlier
ARCHS4 development result and pristine ARCHS4-to-GTEx validation, the evidence is
robust across routing form, seed, setup, and training/evaluation direction.

The claim is deliberately not “invariant in every study.” The primary estimator
balances connected studies within organ and its paired study-bootstrap intervals are
positive, but individual study and organ-by-seed effects remain heterogeneous. The
canonical wording is “positive study-balanced evidence across heterogeneous studies.”

Stage 2 is now explicitly organ-anchored in
`docs/stage2-organ-expert-mechanism-plan.md`. Its primary objective is to identify
what functional corrections the frozen organ experts learn differently and test
whether those differences predict directed cross-organ transfer or interference on
held-out studies. The earlier label-free component was introduced to add novelty by
linking co-routing and transfer maps; it did not replace the organ hypothesis. Since
the completed label-free pilots failed their utility, collapse, or confound gates,
de novo label-free routing is optional and secondary rather than the primary Stage 2
experiment.

## 2026-07-27 — Thursday presentation readiness activated

The preliminary GTEx-to-ARCHS4 result is complete three days before the
Thursday-morning readiness deadline. The active task has therefore moved from model
execution to presentation production. The bounded eight-slide content and speaking
draft is `presentation/2026-07-30-biweekly-draft.md`.

The delivery plan is:

1. Sunday: freeze the result narrative and claim boundary — complete.
2. Monday: build the actual HTML deck and primary-result visuals.
3. Tuesday: cross-check every displayed number against the frozen evaluation JSON
   and perform visual overflow/readability QA.
4. Wednesday: finalize speaking notes, likely questions, and rehearsal timing.
5. Thursday by 08:00 PDT: publish a concise readiness summary and verified
   presentation package for the afternoon talk.

Automation `thursday-archs4-presentation-readiness` is active every two hours from
08:00 through 22:00 PDT until Thursday morning. It advances safe local drafting and
QA, keeps this file and `docs/current-status.md` synchronized, and pauses only for a
critical scientific-validity issue or a story choice that materially requires the
user. It must preserve the post-access QC-amended evidence label and may not turn
diagnostic organ/study heterogeneity into post-hoc selection.

## 2026-07-27 — Post-access QC-amended ARCHS4 evaluation completed

After the efficacy-blind QC stop, the user explicitly authorized a versioned
amendment that excluded exactly the six samples failing the unchanged
14,000-nonzero-gene rule. No replacements were added. The frozen amended cohort
therefore contains 821 samples from 63 connected studies while retaining all eight
organs: seven liver studies and eight studies for every other organ. The evidence is
labeled `post_access_qc_amended_external_evaluation`, not a pristine preregistered
confirmation.

Repeat mechanical extraction passed all 821 rows. Frozen inference then completed
for seeds 17, 42, and 101 with no training, fine-tuning, checkpoint selection, or
best-seed selection. The first evaluator attempt stopped before publishing metrics:
the cache loader validated every hash-bound array but had omitted three ancillary
router arrays from its load set, so it reported the first omitted name as a content
hash mismatch. Independent reloads showed that the immutable cache files and their
stored content hashes matched exactly.

The fail-closed loader correction and protocol-lineage guard pass the focused suite
and are deployed from clean code-only commit
`6822c453637b2b3fe5c8bd50e23060bd13a9b4a6`. Corrected protocol SHA256
`c5aaed24de62347747e815c02e0cda7793adc15c33b0b67f841c7c6896b48632`
explicitly binds the unchanged caches to source protocol SHA256
`8fce7b949cad0049def8bf1bb7383f871bfab34c825c8f85526acc6894042763`
and records that no efficacy output existed before the correction.

The corrected 10,000-repetition connected-study bootstrap evaluation completed:

- pooled equal-organ/study MSE: 0.909261;
- true-organ K8: 0.874738, a 3.797% reduction;
- target-hidden hard K8: 0.876228, a 3.633% reduction;
- target-hidden soft K8: 0.875840, a 3.676% reduction;
- pooled-adapter control: 0.909304, effectively neutral; and
- mean across the three random K8 axes: 0.909273, effectively neutral.

Every prespecified seed improved versus pooled for true-organ, hard-router, and
soft-router K8, and every corresponding paired-study bootstrap 95% interval excluded
zero. No seed was selected. The evaluation-report SHA256 is
`b4a77268c642709b2ae33a0a4d95f38bb9029734f5ffffd0ba1d3f9be1fc15cb`;
the score-cache report SHA256 is
`8a7d3d7c78791ff29cd1fc96d2b277e437d18f15bb715de9ebd1b216936aef99`.
The result supports organ-conditional routing across heterogeneous external studies,
but the post-access exclusion means a new untouched cohort is still needed for a
pristine preregistered confirmation.

## 2026-07-27 — First lockbox access failed closed at sample QC

The current ARCHS4 human H5 completed at exactly 62,257,385,524 bytes with SHA256
`284855959248f249ddef5a9a5b780c72b86ef99240ed1403f08b01609778ed56`.
The final implementation-bound lockbox protocol SHA256 is
`dd73e11f39c02b9a5375f24e098c8118260ccac35f3a608a23e90a0eb76e9bfc`.
Membership froze at the intended 827 accessions and 64 connected study groups.

The extractor then stopped at its prespecified 14,000-nonzero-gene gate. Five liver
samples in GSE277232 had 19, 49, 170, 240, and 304 nonzero genes; one lung sample in
GSE227136 had 11,235. The other-sample median was represented by the all-row median
of 31,144. The extractor published zero expression rows and no handoff, GPU scoring,
efficacy evaluation, fine-tuning, best-seed selection, sample removal, or threshold
relaxation occurred. Both local screen sessions exited and the GPU VM is idle.

This is the required critical pause. Membership and QC cannot be changed silently
after expression access. The compact failure artifact is
`artifacts/stage1_gtex_to_archs4/lockbox_qc_failure.json`; the complete unpublished
extraction audit remains under the ignored runtime directory
`artifacts/stage1_gtex_to_archs4/lockbox_run_73f9bd1/expression/`.

## 2026-07-27 — ARCHS4 K8 lockbox implementation frozen; current H5 acquisition running

The production GTEx-to-ARCHS4 lockbox path is implemented and tested. Commit
`73f9bd1d6fff097811f879766e9a68a05aebe850` binds the exact membership freezer,
one-time extractor, deterministic all-seed score cache, study-macro evaluator, final
protocol freezer, and two-phase launcher. The focused fail-closed suite passes 11
tests. The launcher supports a hash-verified extraction handoff because the GPU VM
cannot store the 62.26 GB current human matrix.

The corrected all-seed candidate ledger SHA256 is
`1bd0e2de4b45f3e1ba4cfe4ca898db9f9b3ef5e0b60fd64ccfcf80bbb3e1a2a8`.
It binds pooled trunks, organ K8, three random K8 banks, pooled adapters,
calibration-score files, and the target-hidden router for seeds 17, 42, and 101.
The GTEx-calibration-only random-control mapping SHA256 is
`4386f372002dc14591d7e2a0203bf794bacf39cacc50736abc339b89a4f99496`.
Best-seed selection and ARCHS4-driven expert selection are forbidden.

The reachable GPU VM is idle. Its only human ARCHS4 file is the historical v11
matrix, which cannot contain the frozen post-v11 cohort; the current object is
62,257,385,524 bytes while that VM has only 33 GB free. A resumable current-matrix
download is therefore running locally in screen session
`archs4-current-download`. Automatic continuation session
`archs4-lockbox-continuation` will verify the exact byte count and SHA256, freeze the
final protocol, extract the exact 827 rows from 64 connected study groups locally,
transfer the compact handoff, and resume all three seeds on the GPU in a separate
clean detached worktree. Any hash, membership, source, or scientific-contract
failure stops the chain. ARCHS4 expression remains unopened at this update.

## 2026-07-24 — GTEx-to-ARCHS4 reversal authorized and implementation started

The completed ARCHS4-to-GTEx `full_external_pass` remains frozen evidence. The next
Stage 1 extension reverses the direction: train a new organ-specialized family on
cleaner donor-controlled GTEx, then evaluate once on staged, study-disjoint ARCHS4
human cohorts. GTEx becomes development data for the new candidate and cannot
externally validate it.

The scientific and operational plan is
`docs/gtex-to-archs4-training-plan.md`; the frozen GTEx-development contract is
`artifacts/stage1_gtex_to_archs4/protocol.json`. The primary family must be
strictly GTEx-only, including its pooled trunk. A secondary practical sensitivity
may reuse the existing ARCHS4 trunk and refit GTEx adapters, but it must be labeled
ARCHS4-pretrained rather than a clean train/test reversal.

An expression-blind inventory over the existing audited UBERON map froze K=8 using
at least 250 exact-header GTEx donors and at least 500
post-historical-firewall current-ARCHS4 high-confidence samples from 30 connected
studies. The resulting organs are adipose, brain, colon, heart, liver, lung,
skeletal muscle, and skin. GTEx contributes 261–842 donors per selected organ;
the post-firewall ARCHS4 metadata contributes 601–2,291 samples across 34–77
connected studies. These are automated metadata candidates, not a frozen ARCHS4
lockbox. Kidney fails GTEx donor depth, placenta is absent from adult GTEx, and
breast lacks the required independent ARCHS4 studies. The exact selected GTEx cohort
contains 9,195 matrix-header-present samples from 938 donors. Cohort SHA256 is
`12aa4b408ebcfdf9c0a372e4c2ca689ad95f39bf4f993f550f5cdb9b76c849fd`;
the reproducible inventory SHA256 is
`2a6f272716fc1acf391be47a1bbf60654857209813da40ab28feb729d1278d9e`.

The implementation now includes
`evaluation/build_gtex_to_archs4_training_manifest.py`, creates global
donor-disjoint GTEx train/calibration splits and three donor-atomic, organ-balanced
random K controls without accepting expression. The separate
`evaluation/extract_gtex_to_archs4_training_expression.py` binds the exact counts,
cohort, GENCODE mappings, exon lengths, canonical genes, and target-hidden axis
definitions, and emits unlogged canonical-universe TPM. The focused extraction,
cohort, inventory, and manifest suite passes 22 tests,
including deterministic row-order invariance, complete organ/shard coverage, donor
atomicity, and fail-closed protocol/hash/firewall checks.

The one allowed strict architecture is now frozen before GTEx expression fitting:
the established 15,448-gene, 768-hidden, four-layer, eight-head ExpressionPerformer
trained from random initialization for 7,350 fixed updates, followed by dimension-64
organ/random/pooled-control adapters for 1,500 fixed updates. Calibration may select
a checkpoint within the fixed pooled run but cannot change K, architecture, or
budget. Seeds are 17, 42, and 101; best-seed selection is forbidden.

The planned ARCHS4 evaluation is a human-first ladder: core intact bulk tissue,
non-diseased versus disease, tumor stress, and a separately supported
spaceflight/space-analog stratum. Nested fine-tuning doses may use only frozen
ARCHS4 development studies; the lockbox is never a fine-tuning source. Mouse is an
optional ortholog-mapped sensitivity and may not be mixed into the primary human
estimand.

The frozen donor split has now been materialized without reading expression:
7,369 samples from 750 donors are training rows and 1,826 samples from 188 donors
are calibration rows, with zero donor crossover. All eight organs retain at least
48 calibration donors. Three donor-atomic random K8 assignments are complete and
balanced across organ, sample, and donor loads.

Clean detached commit `529c0c3a8d651b935b5e8e5f23d916de196749fa` is deployed at
`/media/volume/moe-reboot/worktrees/gtex-train-529c0c3`. Its manifest was reproduced
on the GPU host and the checksum-bound K8 count-to-TPM extraction is running in
tmux session `gtex_k8_extract_529c0c3` under
`/media/volume/moe-reboot/results/stage1_gtex_to_archs4_529c0c3`. The operation reads
only GTEx development expression; ARCHS4 expression remains sealed.

A coverage-complete real-GTEx smoke-fixture builder, a metric-free generic K8 router
refit, and the pooled/banks/router smoke workflow are implemented. Smoke artifacts
are explicitly `mechanical_only`; no smoke loss may select K, capacity, update
budget, or a seed. The expanded focused suite passes 26 tests.

The first real-data smoke exposed a loader scaling defect before any model metric was
produced: schema validation performed repeated name lookups over all 15,448 columns
and expression loading converted every column separately. On the 235-row smoke
fixture, the corrected one-pass schema validation plus vectorized Arrow/pandas
conversion loads the exact requested matrix in 0.29 seconds and preserves requested
sample order, gene order, float32 values, finiteness checks, and C-contiguous layout.
The slow attempt is retained as a mechanical audit artifact and is not scientific
evidence.

The full K8 GTEx extraction then completed with 9,195 samples, 938 donors, 15,448
canonical genes, 4,634 target-hidden score genes, and exactly the frozen 22 absent
canonical / 10 absent score genes. Every sample exceeded the 14,000-gene expression
QC floor; the observed nonzero length-mapped range was 22,040–51,653. Expression
SHA256 is
`ef5949975e8139d0a29f6fca003da6098a308677f2ab34d7f589851b5ea36550`.

The corrected real-data smoke passed end to end from clean commit
`98e2cbab7e94f101feb33e83cff0712834c38ee3`: pooled checkpoint creation and
round trip, one true-organ K8 bank, all three donor-atomic random K8 banks, the pooled
residual control, finite final adapter tensors, and the eight-class target-hidden
router. Router fitting generated no accuracy or reconstruction metric. All
two-update bank scores remain mechanical-only and cannot influence the frozen
configuration.

The full strict three-seed campaign launched at 2026-07-24T05:29:12Z in tmux session
`gtex_k8_train_98e2cba`. It is running under
`/media/volume/moe-reboot/results/stage1_gtex_to_archs4_training_98e2cba`, starting
with the seed-17 GTEx-only pooled trunk. Each seed uses the frozen 7,350 pooled
updates followed by one packed 1,500-update organ/random/control adapter pass.
ARCHS4 expression remains sealed.

The recovered campaign completed at 2026-07-27T05:38:49Z. Seeds 17, 42, and 101
each completed the 7,350-update pooled trunk and the full packed organ K8, three
random K8, and pooled-adapter bank family; the metric-free target-hidden router also
completed. The complete remote checksum manifest passes. The 1.8 GB result was copied
to `backups/stage1_gtex_to_archs4_training_98e2cba/` and independently verified;
its `FULL_SHA256SUMS` SHA256 is
`009920173cff2c0eaa9d880c8bc1fbe4ffbe61a9ffc9df5ba8c6795cf90dcc7b`.
All 261 repository tests pass with pytest capture disabled. ARCHS4 expression was not
accessed. Candidate/evaluator freezing may proceed, but the one-time ARCHS4 test
remains blocked until manual study/sample/donor signoff and the exact lockbox,
strata, fine-tuning doses, and decision gates are frozen.

The immediate post-training lockbox audit then closed the missing-K8-coverage gap.
The pinned post-v11, historical-accession/series-disjoint metadata universe contains
10,041 samples from 391 unique connected studies across all eight trained organs.
Official GEO Series metadata for 160 top-ranked organ/group rows proved that
automatic priority-A acceptance is unsafe: nominal positives include cell models,
active interventions, tumors, and disease studies. No supplementary expression or
efficacy value was accessed.

The existing five-organ shortlist was conservatively extended to colon, heart, and
lung. Exact fail-closed selectors now resolve 64 connected study groups and 827
samples, eight groups per organ. The K8 donor/power audit found no duplicate selected
sample IDs, no duplicate derived donor keys within a group, and no explicit
cross-group donor/BioSample identifier reuse. It is structurally
`ready_for_protocol_drafting_not_lockbox`; all source decisions remain pending and
ARCHS4 expression remains sealed. With 64 study clusters, the one-sided exact sign
diagnostic at alpha 0.025 requires 41 positive studies and has null tail 0.01638.

This work changes the blocker precisely: the test is no longer waiting for colon,
heart, or lung study coverage. It is waiting for the all-seed candidate hash ledger,
the exact ARCHS4 extraction/scoring implementation, development-versus-lockbox roles,
frozen strata and any development-only exposure doses, the decision tree, and final
metadata signoff. No production ARCHS4 lockbox evaluator or launcher exists yet, so
opening expression now would be an unpreregistered test rather than the planned
one-time confirmation.

## 2026-07-23 — GTEx V11 frozen external validation passed

The mentor-directed GTEx analysis is complete. It was executed once from clean
detached implementation commit `6cc8095431bf422926496a6c1dfea3b6cdeb9eb3`
under the checksum-frozen protocol
`artifacts/stage1_k4_gtex_evaluation/protocol.json` (SHA256
`295a38f70ded3059ccce4a4308978921ace76d00ee72608b84042483c141115c`).
No external target was used for fitting, checkpoint selection, cohort rescue, or
protocol changes after scoring.

The exact GTEx V11 RNASeQC header reduced the metadata-provisional 7,845 rows to
6,795 official `RNASEQ` samples from 930 donors after the historical four-donor
EN-TEx exclusion. The sealed counts are adipose 1,293/817 samples/donors, brain
3,030/385, liver 261/261, skeletal muscle 814/814, and skin 1,397/842. The
sealed-cohort SHA256 is
`a0b070354a15b89cf174079326283b6492bb189995fdbc82be550dce5afd0246`.
GENCODE stable-ID reconciliation recovered renamed symbols across the development
and GTEx releases. Ten structurally unavailable frozen targets were excluded from
metrics, leaving 4,624 scored genes while all original 4,634 targets remained
masked for both router and models.

The primary equal-organ, donor-balanced estimand averaged the three prespecified
training seeds within sample, tissue sites within donor and organ, donors within
organ, then the five organs equally. Paired global-donor bootstrap uncertainty used
10,000 draws and preserved cross-organ donor correlation. Results:

| Condition | MSE | Reduction vs pooled | 95% CI |
| --- | ---: | ---: | ---: |
| pooled | 0.955366 | — | — |
| true K4 | 0.923828 | 3.301% | 3.262%–3.341% |
| target-hidden blind K4 | 0.925205 | 3.157% | 3.113%–3.202% |

Both primary one-sided bootstrap p-values are `0.00009999`. Blind routing also
improved residual Pearson by `0.009614` (95% CI `0.009220`–`0.010003`), achieved
98.03% organ accuracy, and recovered 95.63% of the true-routing gain. All three
training seeds were positive. True-K4 organ effects were nonnegative for every
active specialist: brain 1.84%, liver 4.34%, skeletal muscle 4.78%, and skin 5.56%.
Every frozen gate passed, including true and blind comparisons against all matched
random controls, the pooled residual-adapter control, seed stability, router
recovery, and active-organ safety. The prespecified decision is
`full_external_pass`.

The evaluation remains secondary donor-controlled domain-shift evidence. GTEx is
one harmonized STAR/RNASeQC consortium collected postmortem or from organ donors;
it is not multisource cross-study confirmation and not evidence from clinically
healthy living donors. The 40-study ARCHS4 design remains the independent
multisource confirmation path and must not be retrofitted to rescue or amplify this
result.

Canonical tracked summary:
`artifacts/stage1_k4_gtex_evaluation/result_summary.json`. Raw reports and the
compact score cache are checksum-verified locally at
`backups/stage1_k4_gtex_v11_6cc8095/` and remain centrally at
`/media/volume/moe-reboot/results/stage1_k4_gtex_v11_b9a15f2`.
Evaluation-report SHA256:
`c90adfee81aa31241502d69bfdf1e92d41d66574e5f9a1c5bdd2b9877d1e38c6`.
Score-cache SHA256:
`d5c82fab815fca50487c520aa32faccf5660d972a23c18f571d828f18d8395b0`.

## 2026-07-23 — pause checkpoint awaiting PI dataset recommendation

The development search, genuine K4/K5 retraining, final train+calibration-only K4
refit, external feasibility scout, conservative v3 sample sheet, and donor/power
structural audit are complete and backed up. No training or scoring job is currently
required. The frozen candidate remains K4-EPE with brain, liver, skeletal-muscle, and
skin specialists, pooled adipose fallback, seeds 17/42/101, the frozen target-hidden
router, three matched random K4 controls, and the pooled-residual control. K5 and the
higher-exposure K4 sensitivity are not external rescue candidates.

A PI recommendation for a cleaner independent human bulk multi-organ dataset is
pending. The arrival of a dataset will not trigger immediate scoring. The complete
intake-to-validation sequence is preserved in
`docs/external-validation-intake-plan.md`: metadata and provenance first, historical
overlap audit, evidence-role assignment, exact cohort and evaluator freeze,
synthetic/development-only smoke, then one checksum-bound external extraction and
evaluation. A single clean consortium can serve as donor-controlled validation but
does not by itself establish the multisource generalization targeted by the current
40-study design.

## 2026-07-22 — conservative v3 donor/power audit completed

The v2 sheet was narrowed before any expression access. Skin `GSE235570` now retains
only healthy-control epidermis, avoiding an epidermis/dermis compartment mixture.
Skin `GSE297863` now retains one deterministic healthy sample because its `rep`
labels do not establish biological versus technical replication. Together with the
previous liver replacement, the v3 resolver produces 574 pending rows: 61 adipose,
126 brain, 47 liver, 263 skeletal muscle, and 77 skin. It preserves exactly eight
connected-study groups per organ.

The metadata-only audit is frozen in
`artifacts/stage1_k4_external_scout/donor_power_audit_protocol.json`. Its primary
analysis unit is the connected-study group, not a sample row or provisional donor
proxy. Weighting is equal study within organ followed by equal organ, and final
uncertainty must use at least 10,000 paired connected-study bootstrap draws. The
exact one-sided sign-test design calculation requires at least 27 of 40 studies to
favor K4 at alpha 0.025. Its sensitivity is 21.1%, 44.1%, 70.3%, 89.7%, and 98.1%
when the true probability that a study favors K4 is respectively 0.60, 0.65, 0.70,
0.75, and 0.80. This is a design diagnostic, not outcome-scale power.

Commit `8d26e847419462152781c992fa5b9848846c4864` is pushed and was deployed from
clean checkout `/home/exouser/nasa-rna-moe-8d26e84`. Production completed at
2026-07-23 06:27:30 UTC under
`/media/volume/moe-reboot/results/stage1_k4_external_donor_power_audit_8d26e84`.
All checksums pass there and in
`backups/stage1_k4_external_donor_power_audit_8d26e84/`. The portable
`FULL_SHA256SUMS` SHA256 is
`77eb82e393b886200aa959e0292057066bac4ce146624c61b90b42af5655df97`;
the donor/power report SHA256 is
`919bca4a210b40ff5ae7257217d11bb5073aa815479dac65df3e89992cf15640`.

The audit found no explicit identifier shared across connected-study groups and no
duplicate derived key within a group. However, only 19 sample rows expose an explicit
identifier in the pinned metadata; the other groups use unique-title proxies, which
are explicitly not verified donor identities. Therefore the exact status is
`ready_for_protocol_drafting_not_lockbox`: manual decisions are incomplete,
expression remains sealed, and neither lockbox freeze nor expression access is
authorized. All 227 repository tests pass. The next action is to draft the
evaluator/checkpoint/control contract, then complete final metadata signoff and hash
the accepted cohort before any expression request.

## 2026-07-22 — expanded GEO review and provisional exact sample sheet completed

The public GEO series-metadata review was expanded to 40 non-excluded connected
groups per organ. Commit `a89e2e988e8e8e5467a56d16a85a5f173dd3dff6`
produced 200 organ/group review rows and 226 pinned series records at
`/media/volume/moe-reboot/results/stage1_k4_geo_review_a89e2e9`; the verified Mac
copy is `backups/stage1_k4_geo_review_a89e2e9/`. The selected-study review SHA256
is `19373eafa0e5d1fdf1127033a669c79232616adbe1d28fd26b6bd01c274cfc3b`.
Only series title, summary, design, PubMed, BioProject, and sample count were read.
No supplementary file, SRA object, expression value, or efficacy score was accessed.

Manual reading yielded eight provisional groups per organ with explicit healthy,
control, untreated, or baseline sample selectors. A likely donor reuse between
adipose `GSE306796` and `GSE287627` was caught from matching donor metadata;
`GSE287627` was omitted and replaced. This demonstrates that connected GEO-series
grouping is necessary but not sufficient for cross-publication donor independence.

The selector resolver in commit
`8e6d95b66d4ee26e2b226ee6ddab839e712b9e24` is pushed and deployed from clean
checkout `/home/exouser/nasa-rna-moe-8e6d95b`. Its production run completed at
2026-07-23 05:59:48 UTC under
`/media/volume/moe-reboot/results/stage1_k4_external_sample_review_8e6d95b`.
It binds the source metadata hashes, requires post-v11 samples, rejects
classifier-ineligible matches, and leaves every manual decision pending.

The resulting review sheet contains 40 study rows and 601 exact sample rows:
61 adipose, 126 brain, 49 liver, 263 skeletal muscle, and 102 skin. These are
selector matches for review, not accepted sample counts. Unresolved replicate,
regional, compartment, and graft-donor cases are labeled in the study sheet.
The result reports no repeated PubMed or BioProject identifier among the 40
provisional groups, but that does not complete the donor/near-duplicate audit.

Both the VM result and
`backups/stage1_k4_external_sample_review_8e6d95b/` pass every checksum entry.
The full checksum-manifest SHA256 is
`da0ff1b8e5ae5e4d49e3699e176d88037467bfde41627d2fedfd549960feaca3`;
sample-review SHA256 is
`4b5dead31111c8ae80c3d079d6ee73db4da45e6a61d7cc1a4233ae9fb4dcd3e8`;
study-review SHA256 is
`9c6712ccc9772de39388dd846f446db2391eb809695924854739ccc5f5605fb5`.
The current gate is manual exact-sample/donor/near-duplicate resolution, followed by
cluster-aware power calculation and preregistration. Expression remains sealed and
the external lockbox remains unfrozen.

The next donor audit rejected liver `GSE304242` because the official study design
centers on hepatic cell models and its three liver-RNA rows lack defensible donor and
health semantics. A targeted metadata-only reserve review was committed as
`119ed2d0f12f391d28c20a0dd9ed54a5f1c4b573` and completed at 06:08:10 UTC,
pinning ENCODE4 `GSE284901`. Its single bulk adult right-lobe liver sample has exact
BioSample `SAMN45079858` and donor `ENCDO757VPQ`; recorded hypertension is retained
as a non-hepatic comorbidity. The reserve result is checksum-verified at
`/media/volume/moe-reboot/results/stage1_k4_geo_reserve_review_119ed2d` and
`backups/stage1_k4_geo_reserve_review_119ed2d/`.

The auditable amendment leaves the original 601-row sheet intact and resolves a v2
sheet from commit `8734e5e1486713850ab71cb386b51cc785fbfef7`. Production completed
at 06:11:57 UTC under
`/media/volume/moe-reboot/results/stage1_k4_external_sample_review_v2_8734e5e`.
It contains 599 pending rows: 61 adipose, 126 brain, 47 liver, 263 skeletal muscle,
and 102 skin. The verified local copy is
`backups/stage1_k4_external_sample_review_v2_8734e5e/`; full checksum-manifest
SHA256 is
`a3f5a58122fd58acc5f0c9ba2a56898de8e1bad53f44d8b7b9669ee15765ddcc`.
All 224 tests pass. Expression and efficacy remain untouched, and every manual
decision remains pending unless explicitly recorded in the amendment.

## 2026-07-22 — external metadata scout completed

The pinned metadata-only scout at code commit
`182207bbc85c30df80f17cd45784d5c87f8a52a7` completed successfully on
`moe-reboot` at 2026-07-23 03:53:11 UTC. It did not read expression values, compute
efficacy scores, or freeze an external lockbox.

After excluding every ARCHS4 v11 accession and every current sample sharing any
v11 GEO-series token, the scout found 13,845 candidate samples in 457 connected
series groups. All five organs passed both the minimum five-series and preferred
eight-series feasibility thresholds. Temporally new sample/series counts were:
adipose 1,047/44, brain 2,225/82, liver 2,154/78, skeletal muscle 2,488/50, and
skin 3,296/115. The deterministic review sheet contains 50 rows per organ.

The complete 53 MiB result is preserved both at
`/media/volume/moe-reboot/results/stage1_k4_external_scout_182207b` and
`backups/stage1_k4_external_scout_182207b/`; every entry in `FULL_SHA256SUMS`
passes at both locations. The current gate is manual metadata label/leakage review,
followed by freezing exact sample IDs and the full evaluation contract before any
expression request. These counts establish feasibility only, not evidence that K4 or
organ specialization works externally.

### Manual gate audit: broad feasibility passed, automated eligibility failed

Inspection of all 250 deterministic review rows found that the nominal
`high_confidence` tier was still admitting cell models, cellular fractions,
single-cell/single-nucleus/spatial and Ribo-seq assays, nonhuman records, diseased or
tumor-adjacent tissue, and treated samples hidden behind uncontrolled abbreviations.
Examples included adipose-derived mesenchymal stem cells, HepG2 and hepatic stellate
cells, mouse liver, Human_GBM_RNA, MAIT cells, Visium, and ribosome-protected RNA.
This is a metadata-selection failure; no expression or model score was accessed.

The parser now handles ARCHS4's comma-separated key/value representation and
underscore-delimited titles, and the ontology has conservative cell-source,
assay-mismatch, nonhuman, tumor, and disease exclusions. Focused classifier/scout/
curation tests pass 25/25. With the revised rules, 110/250 round-1 rows are
conservatively downgraded (20 adipose, 24 brain, 30 liver, 9 skeletal muscle, and
27 skin).

Because a growing blacklist cannot establish cohort validity, the workflow has been
changed from automatic acceptance to connected-study triage. The new metadata-only
curation workbook exposes positive reference markers, exclusion and context flags,
cross-organ connected groups, GEO links, and explicit manual review fields. Its
automated priorities are never final. A full-pool preflight retains 457 unique
connected groups and yields strict all-sample priority-A group counts of 2 adipose,
8 brain, 12 liver, 4 skeletal muscle, and 10 skin; priority-B groups remain available
for manual curation. The next action is to deploy this workbook generator and manually
verify at least eight independent studies per organ before freezing any sample IDs.

The production curation workbook then completed at 2026-07-23 05:24:34 UTC from
isolated commit `f307108a5d3e9325b014d9171aa6522ebc6751bc`. The result is stored at
`/media/volume/moe-reboot/results/stage1_k4_external_curation_f307108` and in the
verified local backup `backups/stage1_k4_external_curation_f307108/`. The workbook
SHA256 is
`965b4a2f40f28d94a1de7317fbaa4c97ae4014426195b287c125e92dc5c7b5e0`;
every manifest entry passes at both locations.

The next implementation pins public GEO series-level SOFT metadata for the first
40 non-excluded connected groups per organ. It records title, summary, overall design,
PubMed, BioProject, sample count, and conservative context flags while explicitly
forbidding supplementary files, SRA downloads, expression values, model scoring, and
automated study acceptance. Its focused test suite passes 27/27.

## Historical chronology — not the current handoff

**Vocabulary:** `Stage` is the research phase: **Stage 0** is inherited
human/mouse/mixed completion, **Stage 1** is the original organ-specialization
work, and **Stage 2** is transfer-validated label-free discovery. `V1/V2/V3`
remain independent data/model/debugging generations inside Stage 0; they are not
renumbered. `D1/D2/D3` remain candidate research directions.

## PI meeting agenda (next meeting ~2026-07-30)

Questions to raise about scaling Stage 1 past the ARCHS4 regex-recovery bootstrap:

1. **Which organs matter for the biological hypothesis?** Keep K science-driven, not
   data-availability-driven — heart/colon/lung currently move in/out purely on clean-row
   counts (functional test is K=5: brain, adipose, liver, skin, skeletal_muscle).
2. **GTEx (or recount3) access/preference?** Gold-standard curated organ labels (~17k
   bulk RNA-seq, ~54 tissues) would replace regex labels and skip the Gate 0 manual
   precision review — is there a lab pipeline/access, or pull the open tables directly?
3. **Any lab-internal curated cohort or target tissue panel** to align to?

Bring to the meeting: the completed K=5 organ smoke and full single-seed behavior
results (`results/stage1_organ_k5_smoke_20260717T061947Z/` and
`results/stage1_organ_k5_train_20260717T165507Z/`), emphasizing the strong routed
gain and the failed organ-fixed versus random-fixed control rather than presenting
the run as a definitive biological claim.

## Current Objective

The core Stage 0 interspecies work, including the final globally shuffled pooled
control, is complete and validated. The full K=5 Stage 1 human-organ three-seed
replication is also complete. Its frozen result is amber `organ_is_wrong_axis`: the
routed system is strong and stable, but organ partitioning fails the preregistered
fixed-average control and does not establish the intended biological-specialization
claim.

Key completed checkpoints:

1. **Complete — shuffled 20k pooled control:** training finished at epoch 15 with
   best validation loss `0.296133697` and checkpoint SHA256
   `cb24c4f00047e198ca083f8880b28584952557c2d99ff7c63449ea4ae2701f4a`.
   Freeze and corrected full/strict/blind evaluations all exited 0; frozen
   shuffled-pool validation passed at 2026-07-17 06:19 UTC.
2. **The shuffled 20k behaved as expected and repaired the confound:** on the
   strict 103-study cohort, pooled mixed MSE improved from `0.619339` to
   `0.361734`, and the fixed blend's advantage over pooled shrank from 23.24% to
   2.03%. Thus the original species-contiguous batch order materially weakened
   the old pooled control. Adaptive headroom survived the stronger control: the
   blind soft router beat the fixed blend by 11.42% relative MSE, with MSE-gain
   CI `[0.03352, 0.04820]` and residual-Pearson-gain CI
   `[0.02330, 0.03275]`; blind species balanced accuracy was 99.0%. This clears
   the preregistered practically-convincing threshold for Stage 0 cross-species
   routing, while remaining distinct from the Stage 1 organ claim.
3. **Pilot frozen:** the K=5 set is brain, adipose, liver, skin, and
   skeletal_muscle, with a study-disjoint train/calibration/test manifest.
4. **K=5 real-data smoke passed:** `runs/run_organ_k5_when_eval_complete.sh`
   completed `results/stage1_organ_k5_smoke_20260717T061947Z` at 2026-07-17
   16:51 UTC with exit code 0. `mechanical_health.json` reports `status=pass`, no
   issues, leakage-free connected-study splits, verified gene/sample/mask hashes,
   prediction-mask identity, and five matched random shards. The report correctly
   labels this 300-update run `mechanical_only=true` and
   `biological_evidence=false`.
5. **Full K=5 single-seed behavior run completed:**
   `results/stage1_organ_k5_train_20260717T165507Z` finished at 2026-07-19
   03:55 UTC with exit code 0. All 22,500 scheduled updates completed (7,500
   pooled; 1,500 each for five organ specialists and five matched random shards),
   followed by prediction caching and a 2,000-replicate clustered bootstrap.
   The 1,018-sample/87-study test is leakage-free, and all gene, sample, mask,
   prediction-cache, and random-shard checks pass.
6. **Single-seed routed result is strong:** blind-router balanced accuracy is
   90.67%. Blind hard routing reduces primary MSE versus pooled by 16.95%
   (`0.700827 -> 0.582042`), with positive MSE, Pearson, and residual-Pearson
   intervals, and recovers 119.3% of the true-organ hard gain. Blind soft routing
   reduces MSE by 19.45% (`0.700827 -> 0.564497`). True-organ hard routing reduces
   MSE by 14.21% (`0.700827 -> 0.601255`), although its residual-Pearson interval
   crosses zero. Soft-oracle headroom is large: 41.09% versus organ-fixed
   (`0.907481 -> 0.534600`). All five matched specialists beat their train-only
   organ gene-mean MSE baselines with positive intervals.
7. **The biological-versus-generic-sharding control failed:** organ-fixed MSE is
   `0.907481` versus `0.899724` for random-fixed, a -0.862% relative reduction
   (organ-fixed is worse). The paired absolute-MSE improvement is `-0.007757`,
   CI `[-0.011027, -0.004397]`, so this is not a within-seed statistical tie.
   The preregistered requirement was at least +3% with a positive interval.
   Random-shard soft-oracle headroom is only 1.09%, versus 41.09% for organ experts,
   which shows much stronger sample-dependent complementarity in the organ experts
   but does not replace the failed preregistered fixed-ensemble control.
8. **Engineering complete:** the exact extractor, deterministic manifest trainer,
   balanced random controls, prediction cache, five-class blind router/evaluator,
   decision script, and fail-fast launcher are implemented and synthetic-tested
   end to end. All 105 current local test functions pass.
9. **Next data:** manually validate and expand organ labels before treating the
   single-seed specialist run as definitive biological evidence. The bottleneck
   is label/QC coverage and independent studies, not total ARCHS4 profile count.
10. **Label-recovery track (started 2026-07-16, runs concurrently, no GPU):** a
   metadata-only reconciliation pass mines `characteristics_ch1` tissue fields
   and separates disease/tumor/cell-source status from the organ label. See the
   result below; it materially relaxes the row-count blocker behind the NO-GO.

### Interpretation of organ-fixed versus random-fixed

`organ_fixed` is not true-organ routing. The evaluator fits one simplex of weights
over the five organ specialists on calibration studies, freezes it, and applies the
same mixture to every test sample. `random_fixed` independently fits and freezes the
same kind of mixture over five size/exposure-matched random-shard experts. The
comparison therefore asks whether organ partitioning produces intrinsically better
*ungated ensemble ingredients* than arbitrary partitioning.

The negative result means that, once sample identity and routing are removed, the
organ specialists do not form a better global fixed average than random shards in
this run. A plausible mechanism is that organ experts are deliberately narrow:
each is strong on its matching organ and poor out of domain, so averaging them for
every sample washes out their advantage. Random-shard experts see broader organ
mixtures and can be slightly safer ingredients for a fixed global average. The
separately calibrated weights support this geometry: organ-fixed is near-uniform
(`0.170-0.226`), while random-fixed concentrates more weight on two shards
(`0.299` and `0.341`).

This does **not** say the organ labels or specialists are useless. Correctly routed
organ experts beat pooled by 14.21%, the blind hard router beats pooled by 16.95%,
and organ-expert soft-oracle headroom is 41.09% while random-expert oracle headroom
is only 1.09%. Those results say the organ experts contain strong, structured,
sample-dependent complementarity that must be routed; fixed averaging cannot use
it. Blind routing exceeding true-organ hard routing is possible because some test
samples are better reconstructed by a non-label expert and the five organ labels
are coarse relative to biological heterogeneity.

The preregistered interpretation must nevertheless remain conservative. Gate 2.3
requires organ-fixed to beat random-fixed by at least 3%, so this seed fails the
biological-versus-generic-sharding gate. Gate 1 also requires three training seeds,
and the true-organ residual-Pearson interval is not wholly positive. Therefore this
run is a promising routed-system result, not a green biological-specialization or
Stage 2 expansion result. If the same pattern survives the two replication seeds,
the frozen decision logic places it on the amber `organ_is_wrong_axis` branch: at
most a bounded shared-trunk label-free feasibility pilot, while diagnosing why the
organ axis helps routing but not the preregistered fixed-ensemble control. Do not
change or substitute the failed control post hoc; additional random-router or
per-organ analyses may be labeled exploratory diagnostics only.

### Three-seed replication checkpoint (frozen 2026-07-19)

The next experiment was approved after reviewing seed 42 and is frozen in
`artifacts/stage1_organ_k5/replication_protocol.json`. Train exactly seeds 43 and
44, then evaluate seeds 42/43/44 once. Do not add seeds to chase a pass. Across
seeds, keep the recovered source manifest, connected-study protocol seed 314159,
random-shard assignments, mask seed 271828, architecture, balanced sampler,
7,500 pooled updates, 1,500 updates per organ/random expert, 150-update validation,
and 2,000 bootstrap replicates fixed. Only initialization and training-sampler RNGs
change. The frozen manifest SHA256 is
`25c62b071720117721a24930945fbd4c8c7cdc4a2a81ae003a920e9402441d5b`.

The original decision logic and +3% organ-fixed versus random-fixed gate remain
unchanged. A new report-schema-v2 diagnostic directly compares each matching organ
specialist with all five random experts and with the calibration-selected best
random expert for that organ. The selected random expert uses calibration targets
only and true-organ routing on test; it never uses test reconstruction targets.
This diagnostic is explicitly `gating=false`: it can explain the fixed-control
geometry but cannot rescue or replace the preregistered gate.

The decision code distinguishes reproducibility from direction: an effect with a
consistent negative sign, an interval excluding zero, and acceptable seed SD is
stable but fails its positive gate. Thus, if organ-fixed remains reproducibly worse
than random-fixed while the other effects are stable, the formal branch is amber
`organ_is_wrong_axis`, not the inaccurate label `seed_instability`. Thresholds and
branch authorization are unchanged.

Automation: `runs/run_organ_k5_replication_seeds.sh` first re-evaluates the frozen
seed-42 prediction cache under schema v2, trains/evaluates seeds 43 and 44
sequentially, verifies identical cache-input fingerprints across all reports, and
then writes the one three-seed decision to
`results/stage1_organ_k5_replication/three_seed_decision.json`. Runtime status is
`results/stage1_organ_k5_replication/STATUS`; per-seed outputs are
`results/stage1_organ_k5_train_seed43_v1/` and
`results/stage1_organ_k5_train_seed44_v1/`. The launcher requires at least 40 GiB
free at start and 20 GiB before each new seed. The VM had 74 GiB free before launch;
the two expected ~16 GiB outputs fit with headroom. Expected sequential compute is
about 70 A100-hours.

Launch checkpoint: commit `8b2312c` is pushed to `origin/main`, the committed files
were checksum-deployed to `moe-reboot`, and the launcher preflight passed with
77,238,124 KiB available. The persistent tmux session
`stage1_organ_k5_replicates_20260719` started at 2026-07-19 05:07:45 UTC and
recorded the commit and manifest hash in
`results/stage1_organ_k5_replication/launch_provenance.json`. It first re-evaluates
the frozen seed-42 cache under schema v2, then starts seed 43 automatically.

The seed-42 schema-v2 diagnostic completed before seed 43 launched. The matching
true-organ experts beat the calibration-selected best random expert for each organ
by 33.02% primary MSE overall (`0.897672 -> 0.601255`), with absolute-MSE CI
`[0.228346, 0.356657]`. Every organ is positive against its calibration-selected
best random comparator: adipose 20.76%, brain 43.27%, liver 35.80%,
skeletal_muscle 36.00%, and skin 25.48%, all with positive paired intervals. This
strongly suggests that the seed-42 fixed-control failure is an averaging geometry
issue rather than random experts directly outperforming matched organ specialists,
but it remains exploratory and non-gating until the frozen three-seed analysis.
Seed 43 entered preprocessing at 2026-07-19 05:08:42 UTC.

Parallel seed-44 launch checkpoint: `moe-reboot2` was unshelved with public IP
`149.165.169.55`. Its fresh working copy was checksum-deployed from local commit
`08562b0`; the seven critical code/protocol files and the frozen manifest hash match
the local repository. Because the VM's 60 GiB ephemeral root has only 13 GiB free and
the shared `/software` Ceph mount is read-only, the exact 18,182,709,422-byte central
human H5 was transferred directly into the VM's 58 GiB `/dev/shm`, and the seed-44
output is also RAM-backed. This avoids deleting prior checkpoints; the VM has 115 GiB
RAM and retained about 93 GiB available after extraction began. Preflight passed, and
tmux session `stage1_organ_k5_seed44_20260719` launched at 2026-07-19 05:27:48 UTC
with training seed 44, protocol seed 314159, mask seed 271828, 1,500 updates per
expert, validation every 150 updates, and 2,000 bootstrap replicates. Provenance/logs
are under `results/stage1_organ_k5_parallel_seed44/` on `moe-reboot2`; live output is
`/dev/shm/stage1_organ_k5_train_seed44_v1`. The central coordinator PID 325868 was
SIGSTOP-paused while its seed-43 child remained active on the A100, preventing an
automatic duplicate seed-44 launch. A caffeinated local watcher (PID 16534) was
launched from `runs/collect_parallel_seed44.sh`; its premature exit and the verified
manual recovery are recorded below.

Final replication checkpoint: seed 43 completed at 2026-07-20 16:08:34 UTC and
seed 44 completed at 16:26:50 UTC; both mechanical-health reports pass with no
issues. The local persistence watcher had exited before observing completion, so
the intact seed-44 RAM output was recovered directly VM-to-VM. All 107 entries
(`16,628,819,434` bytes) were content-checksum verified against the RAM source,
atomically installed on central persistent storage, and the coordinator resumed.
The frozen decision completed with exit code 0 at 2026-07-20 18:48:05 UTC in
`results/stage1_organ_k5_replication/three_seed_decision.json`.

The formal result is `status=amber_axis`, `branch=organ_is_wrong_axis`. Technical
validity, all cohort/content fingerprints, backbone health, three-seed stability,
blind hard/soft routing, blind recovery, and soft-oracle headroom pass. True-organ
hard routing reduces MSE versus pooled by 14.28% on average (per seed 14.21%,
15.89%, 12.75%), but its combined residual-Pearson interval crosses zero, so the
full known-organ ceiling gate fails. More decisively, organ-fixed is reproducibly
worse than random-fixed by 0.914% mean relative MSE (per seed -0.862%, -0.846%,
-1.033%); the absolute-MSE interval is entirely negative
`[-0.011724, -0.004617]`. This is a stable directional failure, not a seed-42
anomaly.

The routed signal remains strong: blind hard reduces MSE versus pooled by 16.97%
mean (16.95%, 18.53%, 15.42% by seed), with positive combined MSE and
residual-Pearson intervals, and recovers 118.77% of the true-organ gain. Soft-oracle
headroom versus organ-fixed is 41.08%. The explicitly non-gating direct diagnostic
is also exceptionally stable: matching organ experts beat the calibration-selected
best random expert by 33.02% mean MSE, with positive intervals globally and for all
five organs. Thus the result supports an averaging-geometry explanation—narrow organ
experts are useful when routed but poor ingredients for one global fixed average—yet
cannot rescue the preregistered organ-versus-random gate. The frozen authorization
is at most a bounded shared-trunk label-free feasibility pilot, not full Stage 2
expansion or a biological organ-specialization claim.

### Stage 2 latent-axis discovery pilot (frozen 2026-07-20)

The next experiment pivots from assuming that organ identity is the correct
specialization axis to asking whether a label-free router can discover a more useful,
replicable partition. The bounded pilot is frozen in
`artifacts/stage2_latent_axis_pilot/protocol.json`. It uses the exact Stage 1
train/calibration cohort and the frozen seed-42 pooled trunk; the Stage 1 test split
remains sealed unless the calibration-only screen passes. Only small residual expert
adapters and the router are trainable.

The matched design has three modes at seeds 17, 42, and 101: supervised organ
partitioning as a known-label anchor, balanced-random partitioning as the null, and
label-free routing as the candidate discovery axis. Every run has K=5 experts,
adapter dimension 64, router hidden dimension 128, 1,500 updates, the same masking and
training exposure, and three repeated calibration masks. The label-free mode receives
no organ, study, platform, disease, sex, age, or treatment labels. Its learned routes
are later probed against those metadata only for interpretation and confound checks.

The primary screen asks whether label-free hard routing beats (1) the frozen pooled
trunk, (2) perfect-dispatch organ adapters, and (3) a calibration-optimized fixed
mixture and assigned-partition dispatch from matched random adapters. Passing
requires at least 3% relative MSE
improvement, positive study-clustered intervals and all-seed direction, acceptable
seed variance, seed/mask route AMI at least 0.5, effective K at least 3, no route below
2%, and no route with more than 50% of its samples from one study. A pass authorizes
one frozen test confirmation; failure keeps the test sealed and distinguishes route
collapse/instability, technical-confound capture, organ recovery, or no useful latent
axis. This is a discovery screen, not yet a claim that any route is biological.

Implementation adds `core/train_latent_moe.py`,
`evaluation/evaluate_latent_axis_pilot.py`, and fail-fast worker/aggregation launchers.
The frozen pooled checkpoint, expression table, and manifest hashes are pinned in the
protocol. Local focused tests, Python/shell syntax checks, and `git diff --check` pass.
A two-update real-data smoke on `moe-reboot` confirmed the exact frozen inputs,
15,448-gene model, 1,815 training/842 calibration samples, frozen trunk, and 347,018
trainable adapter/router parameters. The first pass exposed an SLSQP iteration-limit
failure in the fixed-mixture diagnostic; before any full run, it was replaced by a
deterministic exact simplex-face solver and covered by collinearity and sample-weight
tests. The repaired smoke completed end to end in 309 seconds of model/evaluation time
after data loading, writing the adapter, route, metric, hash, and completion artifacts.
Its one-route collapse after only two updates is expected and is mechanical-only; the
full screen has explicit utilization/stability gates. The nine full runs are allocated
across the two A100 VMs: organ seeds plus two label-free seeds on `moe-reboot`, and
random seeds plus the third label-free seed on `moe-reboot2`.

Launch checkpoint: commit `4bd3fea` is pushed to `origin/main`; both VMs have
checksum-identical trainer, evaluator, worker, and protocol files, and both frozen
input preflights passed. The exact seed-42 pooled checkpoint was transferred directly
to `moe-reboot2` RAM and verified at SHA256
`080a8a36d2090c3a823cd3995d758d1205b0ad02c1c38c06e6763c5a7ebfd789`.
Persistent tmux session `stage2_latent_axis_pilot_20260720` launched on both A100s at
2026-07-20 19:47:47 UTC. Central began `organ_supervised:17`; the second VM began
`balanced_random:17`. Worker status and logs are under
`results/stage2_latent_axis_pilot/` and
`results/stage2_latent_axis_pilot_worker_20260720.log` on each VM.

Final calibration checkpoint: all nine runs completed without training errors. The
four second-VM outputs were checksum-verified after transfer to central, and the
frozen three-seed evaluator completed with `status=screen_fail`. The versioned result
is `artifacts/stage2_latent_axis_pilot/calibration_decision.json` (SHA256
`56dc2ef8c02367a5fae7085df9cd2c1f31a52211e6c495520f59750d21438677`).
The Stage 1 test split was not accessed and must remain sealed.

Label-free hard routing produced only +0.0067% mean relative MSE reduction versus the
pooled trunk (seed results +0.0199%, -0.0026%, +0.0030%), with mixed signs and a
study-clustered interval crossing zero. It was 5.54% worse than perfect organ dispatch
on average, and was statistically indistinguishable from both assigned random
dispatch (+0.0071%) and the optimized random fixed mixture (+0.0054%). Thus it misses
the preregistered 3% practical-effect threshold by roughly three orders of magnitude.

The routes were reproducible but not useful: minimum seed AMI was 0.567 and minimum
repeated-mask AMI was 0.813, so the stability gate passed. Utilization failed: effective
K was 2.29-2.98, two seeds left at least one route completely unused, and the third had
a minimum route fraction of only 0.36%, all below the K>=3/minimum-2% requirements.
The study-confound gate also failed: one study supplied 66.7% and 67.2% of a route in
seeds 17 and 101. Study AMI was 0.308-0.325, versus organ AMI 0.182-0.242. The cautious
interpretation is a stable, partially study-associated partition with no reconstruction
value—not discovery of a superior biological specialization axis.

Aggregation initially exposed a metadata serialization mismatch: pandas string
columns had been stored as trusted NumPy object arrays while the evaluator required
non-object arrays. Numeric predictions and routes were intact. Commit `1db590c`
normalizes future string serialization, tests the completed-run format, and safely
loads these self-generated artifacts; it is pushed and deployed. This engineering fix
did not alter any model output, threshold, comparison, or test-access decision.

### Stage 2 competitive utility-axis follow-up (frozen 2026-07-20 PDT / 2026-07-21 UTC)

The `screen_fail` was reviewed from the router, expert, checkpoint, data, and objective
levels before authorizing another run. The decisive diagnostic is not merely the flat
top-1 result: the target-aware hard expert oracle improved over the pooled trunk by only
0.047-0.108% across the three label-free seeds. Inspection of every saved validation
checkpoint found a maximum oracle gain below 0.158%, still far below the 3% screen.
Thus neither a different checkpoint nor a better selector can recover useful behavior
from the completed expert set. Routes were stable, but their effective K collapsed and
their association with study exceeded their association with organ. The proximal
failure is functional expert redundancy despite stable, partly study-associated
routing.

The training objective supplies a concrete mechanism. Label-free training minimized
MSE only after taking a soft probability-weighted average of all five expert outputs.
Consequently every expert received a scaled version of the same blended residual;
load-balance and entropy terms shaped traffic but did not require different expert
functions. This is consistent with the cooperative-solution mechanism described in
the competitive-mixture literature, but the completed run cannot establish that
mechanism causally. A second audit also narrows an earlier protocol statement: organ
and study were not router inputs, targets, or expert labels, but they did control the
organ-then-study-balanced training sampler in all modes. This sampling use likely did
not create the negligible oracle—it controlled exposure—but future descriptions must
not claim that those metadata were absent from the entire optimization procedure.

This does not overturn the positive organ anchor. The shared-trunk supervised-organ
condition specialized under the same adapter capacity, and the full Stage 1 routed
organ experts remain strongly better than pooled and directly matched random experts.
The failed organ-fixed versus random-fixed gate remains frozen, but it measures global
ungated averaging geometry rather than the conditional-dispatch behavior for which the
organ experts are useful. The five-organ plan therefore remains the main biological
anchor; this follow-up asks whether a task-error state should replace it or augment it
hierarchically.

The revised calibration-only protocol is frozen in
`artifacts/stage2_utility_axis_pilot/protocol.json`. The candidate axes are
metadata-label-free with respect to organ and study, but they are target-aware: their
assignments consume truth from a disjoint probe-gene panel. They are diagnostic
dispatch labels rather than deployable blind routes. A pass would establish expert
headroom on separately hidden score genes, not yet demonstrate that a router can infer
the assignment. The protocol separates the questions that the failed joint model
attempted to solve simultaneously:

1. Deterministically reserve 10% of checkpoint genes as an axis-probe panel and 30% as
   the disjoint primary score panel. Both panels are masked while fingerprints are
   computed; only probe truth enters axis construction, so calibration score targets
   cannot determine their own dispatch label.
2. On training studies only, construct signed probe-residual and exact output-head
   gradient fingerprints, apply train-fitted standardization/PCA, and fit capacity-
   balanced K=2/K=3 partitions. Apply frozen train centroids to calibration without
   refitting. `head_gradient_k2` is the sole primary; the other three candidates are
   exploratory and cannot open the sealed test without a new confirmation.
3. Hard-train independent residual expert banks with no router, blended-output loss,
   entropy loss, or balance loss. Use a fixed final update and target-matched exposure
   budgets (with realized per-expert exposure constrained within 5%):
   600 updates for K=2, 900 for K=3, and 1,500 for a newly matched organ-K5 anchor.
   Matched random K=2/K=3 banks use the identical architecture and budget; realized
   natural-schedule exposure may deviate by no more than 5% from 2,400 per expert.
4. Pack all seven independent banks into one frozen-trunk pass per expert seed. Banks
   have separate parameters, optimizers, schedules, and stop updates; the shared
   natural sample schedule uses neither organ nor study. This reduces 21 redundant
   standalone jobs to three seed jobs. The banks share a schedule and AMP scaler but
   have no shared trainable parameters or direct gradient cross-talk under finite
   losses.
5. Before any router is trained, require candidate dispatch to beat pooled by at least
   3%, beat matched random with a positive study-clustered interval, and show at least
   3% hard-oracle headroom over a study-cross-fitted fixed mixture. Also require all-seed
   direction, acceptable seed variance, stable train clustering, effective utilization,
   at least five studies per partition, and no study dominance. Beating organ-K5 by 3%
   is a separate replacement gate; otherwise a passing factor can only motivate an
   `organ -> state` augmentation.

The decision is deliberately terminal for this bounded residual/gradient K=2/K=3
branch under the current frozen-trunk random-gene objective. A primary pass authorizes
only a separately frozen confirmation, not automatic test access. An exploratory
winner must be confirmed again. If no candidate has hard-dispatch/oracle headroom,
stop discrete label-free MoE for the current random-gene reconstruction objective and
retain organ routing or move to continuous conditional adapters. More seeds, longer
training, a larger router, or balance-loss tuning are not authorized substitutes for
absent expert complementarity.

#### Implementation, launch, and completion checkpoint (2026-07-20/21 PDT)

- Code commit `f8ab3cdc9527e3c5002e225a3e181a1599cc1d13` is clean, pushed to
  `origin/main`, and deployed to the isolated directory
  `/home/exouser/nasa-rna-moe-f8ab3cd` on both VMs. The full local suite passed
  (105 test functions), including exact analytic-gradient versus autograd checks,
  target-panel separation, balanced deterministic partitions, hard-dispatch gradient
  isolation, the packed integration smoke, and evaluator decision branches. Protocol
  SHA256 is `308f15c212cd07d87674f0617db2be00ffbcde2f9778ddb792adacab610b18bd`;
  deployment archive SHA256 is
  `0f8a55ed3b63174878ab5cc8f987351b0b724d2cf796d6f1dff5b0ae419e1e36`.
- Target-hidden axis discovery ran on `moe-reboot` from 04:29:57 to 04:42:32 UTC
  (12 minutes 35 seconds) over 1,815 training and 842 calibration samples, 15,448
  genes, and no test rows. The realized firewall is 1,544 probe / 4,634 score /
  9,270 context genes. `head_gradient_k2` remains the sole primary: its minimum
  KMeans-restart AMI is 0.9938; calibration effective K is 1.992, minimum partition
  fraction 0.469, coverage 35-36 connected studies per partition, and maximum
  one-study fraction 0.101. `head_gradient_k3` is also structurally healthy
  (minimum restart AMI 1.0; calibration effective K 2.464 and minimum fraction
  0.114). Both residual-PCA candidates already fail the frozen restart-stability gate
  (minimum AMI about 0.189); they remain in the run as explicitly exploratory negative
  evidence and cannot qualify by performance alone. Restart AMI establishes optimizer
  stability on this training cohort, not biological replication or freedom from batch
  confounding.
- Discovery artifacts are complete with `test_accessed=false` and were copied through
  a local staging directory to `moe-reboot2`; hashes match on both hosts:
  `partition_manifest.parquet` = `e07faa42fbc899a4338b2ac603b9abee9991cf97a163f13c2a49ade6ee1fd8c7`,
  `partition_report.json` = `62f4b19e0fd111d99f265f8b1bd7beba9b5af7edf8bf35ffdce2ce98d0e33b16`,
  and `axis_definitions.npz` = `1d7fba55d00f3fe363932abfba2a0e0d76e70e8dedf71aa46c69e29679b0b7cb`.
  The two extraction-report file hashes differ only because they record host-specific
  paths and H5 modification times; removing `*_path` and `*_mtime_ns` fields makes the
  JSON identical (normalized SHA256
  `e764e9fdd23fb9edfe30bc42dff3dfbfc7494bed6ca1fdcbae92f8e6637050bb`), while
  the expression, manifest, gene-order, and checkpoint content hashes match exactly.
- The separate real-data smoke ran at
  `results/stage2_utility_axis_pilot_f8ab3cd/smoke` from 04:59:11 to 05:22:13 UTC
  (1,078.5 seconds). All seven banks completed two updates, full calibration scoring,
  cross-fit fixed-mixture evaluation, and artifact serialization with finite numeric
  outputs, per-bank and top-level `COMPLETE` markers, `mechanical_only=true`, and
  `test_accessed=false`. Its effect sizes are not research evidence and will not enter
  the final evaluator.
- The full three-seed run launched at 05:40:19 UTC (22:40:19 PDT). Seed 42 completed
  on `moe-reboot2` at 06:32:38 UTC; seeds 17 and 101 completed sequentially on
  `moe-reboot` at 07:25:17 UTC. Each packed seed took 2,843-2,850 seconds. All 21
  non-smoke banks reached their frozen 600/900/1,500-update budgets, have finite
  outputs and `COMPLETE` markers, and retain `mechanical_only=false` and
  `test_accessed=false`. The worst realized per-expert exposure deviation was 0.92%,
  well below the frozen 5% limit. Seed 42's 31-file, 4.2 MB directory was copied
  through local staging into persistent central storage; the source, staging, and
  destination file-manifest SHA256 is
  `84991fa7040c2fb466ee5cc14ffb350ef291309fc7789c90cbce21d04baa0369`.

#### Competitive utility-axis result (completed 2026-07-21)

The exact frozen evaluator completed at 12:23:07 UTC with formal status
`screen_fail`, decision branch `stop_discrete_utility_axis`, and authorized next step
`do not access test; stop this discrete label-free utility-axis branch`. No secondary
candidate passed, `test_accessed=false`, and `test_access_authorized=false`. Decision
SHA256 is `05923e678014a39f3fd465fb021391eb722868721ea0cf9886e5caa8ea02c51b`.
The deployed and local evaluator SHA256 values match
(`6561aa73f65cfc54a4047f37869c29865a258e350bd54c3893af778f8224aee4`), as do the
wrapper hashes
(`3fde08868f67e2f297d6c7f776f61d86728f1276cf858cba0eebdead94e468c8`).
Minor auditability gap: the decision JSON does not itself embed those code hashes or
machine-compare CLI thresholds with the protocol; the pinned wrapper was manually
verified to supply the frozen values. This does not change the decision, but future
evaluators should write that provenance directly.

- The sole primary, `head_gradient_k2`, passes every structural gate but fails every
  utility gate. Its true dispatch improves over pooled by only 0.0411% on average
  (study-clustered absolute-MSE interval crosses zero), improves over matched random
  by only 0.0140% with one negative seed, and has only 0.1848% oracle headroom over
  the cross-fit fixed mixture. The oracle seed-SD/mean ratio is also 0.608, over the
  0.5 limit. Thus the axis is reproducible geometry, not a useful specialization
  boundary; no better router can recover a counterfactual ceiling this small.
- `head_gradient_k3` is similarly stable but weak: 0.0672% over pooled and 0.3648%
  oracle headroom. Residual-PCA K=2 reaches 0.367% over pooled and 1.016% oracle
  headroom but fails restart stability and its random-control interval. Residual-PCA
  K=3 is the strongest alternative: 1.453% over pooled, 1.428% over matched random
  with a positive interval, and 2.091% oracle headroom. It still misses both 3%
  practical gates, has minimum restart AMI 0.189, and is 2.094% worse than organ-K5.
  This is consistent with a diffuse or continuous residual factor, not a robust
  discrete replacement axis.
- The newly hard-trained organ-K5 anchor is the only tested configuration that clears
  the practical conditional-specialization magnitudes: true-organ dispatch improves
  over pooled by 3.436%, 3.785%, and 3.198% across seeds (mean 3.473%), while its
  oracle improves over study-cross-fitted fixed averaging by 4.239% on average. The
  shared frozen trunk, adapter capacity, hard individual loss, and packed execution
  can therefore produce complementary experts; the bottleneck is localized to these
  proposed task-error partitions rather than router mechanics, blended-loss mechanics,
  seed anomaly, or a general inability of the adapters to specialize.

This strengthens but does not retroactively rescue the five-organ claim. The old
preregistered organ-fixed versus random-fixed failure remains a failure, and this
screen's organ K=5 versus task-error K=2/K=3 contrast is not a pure axis-only match:
K=5 has more total adapters and updates, though per-expert exposure is matched. The
justified conclusion is narrower: organ is the only tested partition with practical,
seed-consistent conditional dispatch and oracle headroom; neither task-error family
can replace it. The next experiment should be a separately preregistered five-organ
confirmation on untouched, study-disjoint data, with an observed-input blind organ
router compared against pooled and a K=5/budget-matched random-routing control, and
true-organ dispatch retained as the ceiling. Cross-fit fixed averaging should be
secondary rather than the sole specialization estimand. Do not tune another discrete
gradient/residual split or open the sealed test under this failed utility-axis
protocol; a continuous factor-conditioned adapter is a later exploratory option.

### Locked organ-K confirmation and deployed-K search (frozen 2026-07-21)

The next experiment is now frozen in
`artifacts/stage1_organ_k_confirmation/protocol.json`. It follows from two findings
that must remain separate: (1) the old organ-fixed-versus-random-fixed failure is real
for a single global average and is not being erased; (2) the newer hard-dispatch organ
anchor is the only tested partition with practical, seed-stable conditional headroom.
The confirmation therefore tests the conditional architecture directly instead of
using global fixed averaging as a veto on specialization.

There is no genuinely untouched same-five-organ cohort in the current recovered-label
snapshot. Every eligible single-organ connected study is already assigned to the
existing train/calibration/test manifest; the remaining rows either share a used
connected group or are multi-organ. The existing 1,018-sample test is study-disjoint,
but its outcomes were inspected in earlier Stage 1 work. Consequently Track A is
truthfully labeled a **locked internal replication** (`independent_confirmation=false`),
not a final biological confirmation. A new external cohort/lockbox remains mandatory
before claiming that organ identity is the biological specialization axis.

Track A trains five banks together at seeds 17, 42, and 101: five organ adapters,
the exact already-frozen row-random shards retained as a non-gating diagnostic, and
three new preregistered random K5 partitions (partition seeds 17/42/101) that keep each
connected study inside one expert while balancing total and per-organ sample counts.
The group-random controls fix an audit finding: the legacy assignment split 202 of 225
balanced-training studies across random experts, so training-seed replication alone
could not test random-partition variability or match study coverage. All banks use the
frozen pooled trunk, independent dimension-64 residual adapters, a common natural
sample schedule, 2,400 target exposures per expert, and the predetermined 1,500th
update. Before any
test scoring, a StandardScaler plus balanced multinomial logistic router is fitted on
calibration expression with every one of the 4,634 score genes replaced by the mask
token. The router parameters, train/calibration assignments, and separate sealed test
assignment metadata are serialized and hash-pinned first.

The primary Track-A estimand is blind hard organ routing versus pooled on the
equal-organ/equal-study test MSE. Gates also require true-organ hard routing to beat
pooled and **each** study-preserving assigned random-K5 control by at least 3%, and
true-organ routing to beat the calibration-selected best random expert per organ in
each partition with a positive clustered interval, at least 3% calibration hard-oracle
headroom over a study-cross-fitted fixed mixture,
at least 80% recovery of the true-organ gain by the blind router, consistent signs,
seed SD no more than half the mean effect, positive pooled-comparison residual-Pearson
intervals, and exposure deviation no greater than 5%. The decision distinguishes a
full internal pass, a router bottleneck, generic random-capacity failure, absence of
useful specialization, and a technical failure. Blind soft routing and the old global
fixed-average contrast are reported but non-gating.

Track B addresses the separate point that K=5 is not assumed final. In this immediate
search, K means the number of the same five known organs that receive a deployed
specialist; all five organs remain in the calibration estimand and unselected organs
fall back to pooled. It evaluates all 31 nonempty organ subsets, not only one arbitrary
availability-ordered path. For each K and held connected-study fold, the best subset is
chosen using strict four-fold inner-OOF blind MSE from the other four outer folds and
then scored by an outer-fit router on the held fold. Every fold is required to contain
all five organs. K=1..5 reuses the same
K5-trained organ/random banks, so it tests deployment and coverage, not a separately
retrained K-specific architecture. One common five-class router is fit per fold;
smaller subsets deterministically collapse undeployed-organ probability mass into an
`other` pooled-fallback class rather than fitting a different-capacity router. For each
of the three study-preserving random partitions, the matched null receives the same
exhaustive `C(5,K)` outer-fold subset-selection budget plus pooled fallback. Paired
study-level sign-flip tests replace a less defensible uncentered-bootstrap p-value;
Holm correction covers five pooled comparisons and all 15 K-by-random-partition
comparisons. Among candidates passing every corrected control, the smallest K within
one standard error of the best outer-fold mean is nominated; a full-calibration subset
is named only for a future frozen run. Any nomination is development-only and requires
K-specific retraining plus a new untouched confirmation.
It therefore cannot identify the globally optimal MoE expert count or partition
granularity. That broader hyperparameter question requires separately trained,
budget-matched K-specific candidates with an explicit rule for merging or subdividing
organ populations, followed by a new untouched lockbox.

Heart/colon K>5 expansion is not silently folded into this run: the current expression
table contains only the five frozen organs. Valid K6/K7 work requires manual label
precision review, rebuilt connected-group splits and expression extraction, a common
expanded development population, matched random K6/K7 controls, and a new lockbox.

Implementation is complete for the partition/seal builder, target-hidden cross-fit and
deployable router, paired packed-bank trainer, strict locked-test prediction cache,
Track-A decision evaluator, calibration-only K search, and fail-fast orchestration.
The implementation directly records evaluator/code hashes and the internal-versus-
independent evidence label in result artifacts. A prelaunch adversarial audit caught
and repaired the study-randomization, missing-organ fold, one-path K-search, diagnostic,
and terminal-provenance gaps before GPU use. A second prelaunch audit then caught
and repaired an unfair first-K random comparator, outer-fold information reuse during
subset selection, stale-protocol test-cache access, and missing cache/checkpoint
provenance binding. The repaired focused suite (54 tests) and complete 158-test
repository suite pass. Deployment,
real-data smoke, and the two-VM full launch are the next checkpoint and must record the
final code commit and artifact hashes here before effects are interpreted.

Launch checkpoint: implementation commit `53ec6c4` is pushed to `origin/main` and
was archive-deployed to `/home/exouser/nasa-rna-moe-53ec6c4` on both VMs. The
protocol was frozen at 2026-07-21 14:43:41 UTC with SHA256
`bf469479199a6a6c77b1137b5734235a9da2ca29110e6770125e99e65c69d4a9`.
Preparation completed at 16:24:20 UTC and the byte-identical frozen inputs were
verified on both hosts: partition manifest
`43f1ca70c6c0aa8033c9f826b6f24be5b7db9e45ec3943ff784ba7b5bcbdcedd`,
partition report `70aab83817b17b06bb4ca50685216f476bb0ed8e2be84b028e133b76b32a39a5`,
sealed assignments `947523c047aecba40c80ccd8d3363a46419c2f5a041e3926cdf6e85a8afc38b5`,
sealed report `8ae90f24960a2fd673d6fb4825a23acdf61d9afdf8a5aae726a6f38f9c609595`,
router artifact `92f28dd9b58e7f9e1fd12fa5b87b7ae7f41aff14c9a61c827f9f0b2bdd45e160`,
and router report `edb3ce457896789f225554025f55ad430bbea621f669de9dee0d7b2f6a81aed1`.
Two independent real-data smokes completed at 16:43:26/16:43:34 UTC: seeds 17
and 42 each finished all five banks at two updates, wrote five complete artifact
sets, remained `mechanical_only=true`, and did not access test data.

The full two-VM run launched at 2026-07-21 16:45:00 UTC after both worker
preflights passed. Central tmux session `organ_k_17101_53ec6c4` trains seeds 17
then 101 under
`/media/volume/moe-reboot/results/stage1_organ_k_confirmation_53ec6c4`; VM2
session `organ_k_42_53ec6c4` trains seed 42 under
`/dev/shm/stage1_organ_k_confirmation_53ec6c4`. Each pipeline automatically
creates its single locked-test score cache only after its bank training completes.
Runtime provenance records the full commit
`53ec6c483783eede3b0e92a08e0382853cbc4ed7` and `test_accessed=false` at launch.
No effect estimate has yet been inspected. Based on the smoke initialization plus
five-bank evaluation time and the 1,500-update training budget, the provisional
critical-path ETA is about 11:15-11:45 PDT (18:15-18:45 UTC); replace this estimate
after the first full seed supplies an observed throughput.

Completion checkpoint: all three packed runs and locked score caches completed
without error. Seed 42 finished training/cache at 17:33:01/17:46:09 UTC; central
seeds 17 and 101 both required about 43 minutes of bank training, the central
worker finished at 18:20:41 UTC, and its caches finished at 18:33:37/18:46:41 UTC.
The 26 seed-42 bank/cache files were transferred to persistent central storage and
verified byte-identical before evaluation. The frozen evaluator preflight passed,
then Track A and Track B completed in the required order at 19:23:42 UTC.

Track A is technically valid but returns `decision_branch=pooled_fail`, a narrow
preregistered magnitude failure rather than a directional or random-control
reversal. All provenance, alignment, exposure, matched-bank, and router-freeze
checks pass. Blind hard organ routing reduces equal-organ/equal-study test MSE by
3.357% versus pooled (`0.704988 -> 0.681319` mean; per-seed gains 3.189%, 3.499%,
3.384%), with absolute-MSE CI `[0.016458, 0.032434]`, positive residual-Pearson
CI, 89.94% router balanced accuracy, and 126.1% recovery of the true-organ gain.
True-organ dispatch is positive and exceptionally seed-stable but improves over
pooled by only 2.662% (per seed 2.616%, 2.704%, 2.665%; absolute-MSE CI
`[0.006700, 0.029913]`), below the frozen 3% gate. It also beats every
study-preserving assigned-random K5 control with positive intervals, but the
least-favorable mean relative gain is 2.626%, again below the frozen 3% gate.
Calibration hard-oracle headroom is 4.210% and passes. Thus blind routing,
headroom, recovery, stability, and directional organ-over-random evidence all
pass; only the prespecified 3% true-dispatch magnitude gates fail. The legacy
global organ-fixed comparison remains slightly negative and non-gating, consistent
with averaging geometry rather than random specialists outperforming correctly
dispatched organ specialists. This is still an internal locked replication, not
independent confirmation; a new external lockbox is required.

Track B remained calibration-only and nominates **K=4** by the frozen one-standard-
error rule, while K=5 has the numerically best MSE. K=4 deploys brain, skin,
skeletal-muscle, and liver specialists with pooled fallback for adipose; it improves
blind MSE by 2.721% versus pooled and at least 2.686% versus the matched random
families, passing the Holm-adjusted pooled (`p=0.009995`) and random
(`p=0.027986`) comparisons. K=5 improves by 2.841% versus pooled and at least
2.807% versus random and also passes; K=4 is selected only because it is the
smallest eligible model within one standard error of K=5. K=1/2 fail both adjusted
control families and K=3 fails the adjusted random family. This nomination is a
deployment/coverage result using the already-trained K5 bank, not proof that four
separately trained experts are globally optimal. It requires frozen K4-specific,
budget-matched retraining and a new untouched confirmation before changing the
final architecture.

VM2 shelf-safety checkpoint (2026-07-22 04:13 UTC): `moe-reboot2` has no tmux
sessions, no running GPU workload, and zero GPU memory in use. Its unique seed-42
packed bank and 438 MiB locked-test cache had already been copied into the complete
1.3 GiB persistent central result at
`/media/volume/moe-reboot/results/stage1_organ_k_confirmation_53ec6c4`; all 26
seed-42 files were reverified byte-identical against the RAM source. The VM2-only
worker log, cache log/status, launch provenance, extraction report, and transfer
manifest were additionally preserved under the central result's
`vm2_seed42_runtime/` directory and their eight hashes match the source. The older
16 GiB seed-44 run is also present on central persistent storage at
`/media/volume/moe-reboot/results/stage1_organ_k5_train_seed44_v1`; its original
manual recovery was content-checksum verified before installation, as recorded in
the final replication checkpoint above.

A complete independent local backup of the confirmation result now exists at
`backups/stage1_organ_k_confirmation_53ec6c4/` (git-ignored). Its 118-file manifest
is `FULL_SHA256SUMS`, manifest SHA256
`da95d011993b89077284120b712f859e89797702e2c791028d225f5de81758c5`, and a local
`sha256sum -c` check passed for every file, including all trained adapters, all
three raw score caches, frozen partitions/router, Track A/B reports, and VM2
runtime records. The VM is therefore data-safe to shelf. No configured OpenStack
client or cloud credentials are available in the local environment, so shelving
itself must be performed through the cloud dashboard/control plane; do not mistake
an in-guest shutdown for a billable-resource shelf operation.

### Label-recovery result (2026-07-16, automated pass — precision review pending)

The full ARCHS4 human `meta/samples` (441,356 rows) was exported read-only to
`artifacts/stage1_label_recovery/human_sample_metadata.parquet` (23 MB) and run
through `evaluation/recover_organ_labels.py` against the frozen
`data/ontology/uberon_organ_map.json`. Tiers: **18,331 high_confidence / 83,170
ambiguous / 339,855 unlabeled**. Ambiguous is dominated by exactly the contaminants
we want excluded (cell_source ~42k, single_cell ~29k, tumor ~7k, disease ~2k).

**Seven organs now clear the Gate 0 structural bar** (≥1,000 high-confidence training
rows AND ≥30 high-confidence series): brain (4,334 rows / 154 series), liver (2,656 /
96), skin (2,379 / 115), adipose (2,055 / 56), skeletal_muscle (1,949 / 65), colon
(1,226 / 86), heart (1,215 / 87). This is the row-count blocker the original NO-GO
rested on — previously no organ cleared 1,000 clean rows (best was brain 783).
Caveats before any decision flip: (a) these are automated tiers — Gate 0 rule 4 still
requires ≥50 stratified manual reviews per organ at ≥95% precision (spot-check of 8 was
clean); (b) counts use raw series, not connected study groups — the 55 needed
train/calib/test groups must be reconfirmed after `connected_series_groups` merging;
(c) the ontology UBERON ids are recalled and flagged `verify_before_freeze`.
Outputs: `tier_summary.csv`, `pi_ambiguity_sheet.csv` (1,874 stratified edge cases),
`recovery_report.json`.

### First functional cohort: K=5 organ set (frozen 2026-07-16)

**Chosen five: brain, adipose, liver, skin, skeletal_muscle.** This is the first
real router+experts behavior test, not the definitive claim.

Why these five (not the original pilot's brain/skin/liver/lung/colon): the recovery
pass scored all 15 organs against the Gate 0 bar and the eligible set *changed* rather
than merely grew. Lung fell out (only 707 clean rows; it is swamped by tumor/cell-line
samples — 10,177 ambiguous), while adipose, skeletal_muscle, and heart entered because
mining `characteristics_ch1` and separating contamination surfaced clean structural/
metabolic tissues that are rarely cell lines (adipose 603 ambiguous, skeletal_muscle
209). Among all passing sets, **K=5 = {brain, adipose, liver, skin, skeletal_muscle}
maximizes balanced clean data**: balanced-cohort size is `K x (smallest organ)`, which
peaks at 5 x 1,949 = 9,745 rows (vs 8,505 at K=7, where heart+colon drag the floor to
~1,215). It gives the highest per-organ floor of any multi-organ set, zero imbalance
after capping, biologically diverse tissues (neural / metabolic-fat / hepatic /
epithelial-skin / muscle) so specialization should be detectable if it exists, and all
five clear the 30-train-group requirement.

Frozen manifest: `artifacts/stage1_organ_k5/organ_pilot_manifest.csv` (5,628 samples;
study-disjoint; `pooled == specialist-union` verified; multi-organ groups excluded).
Per-organ train groups 34-65, test 14-26; skeletal_muscle is 1 short of the 10-calib/
15-test Gate 0 minimum (boundary — fine for a functional test, expand for definitive).
Training imbalance is handled by the `organ_balanced` sampler, so manifest row counts
(2.2x spread) only set each organ's unique-sample pool. Built via
`evaluation/build_recovered_candidates.py` -> `evaluation/build_organ_pilot_manifest.py`.

Future expansion path: **K=7** adds heart + colon (both ready now, ~1,215-row floor) at
the cost of balance; **kidney + lung** need more clean rows (currently 854 / 707,
recoverable from the ambiguous pool via manual review of the tumor/cell-line demotions);
the remaining organs (pancreas, placenta, prostate, breast, testis, ovary) are row- or
group-limited and need further recovery or are deferred. Any expansion re-runs
`build_recovered_candidates.py --organs ...`.

### Pre-K5 Stage 1 -> Stage 2 decision snapshot (frozen 2026-07-15)

This is retained as the pre-recovery baseline; the completed K=5 single-seed
interpretation above is the current result and does not yet supersede the required
three-seed machine decision.

- **Current decision: definitive Stage 1 is NO-GO; pipeline smoke testing is
  allowed.** The five specialist training sets contain only 783 brain, 409 skin,
  345 liver, 241 lung, and 220 colon rows, with 7-15 final-test connected groups
  per organ. At least 94/2,856 manifest rows match obvious residual exclusion
  terms or ambiguous cell-source descriptions. The cohort must be cleaned and
  expanded before a biological MoE conclusion.
- **Green boundary for the primary Stage 2 experiment:** zero connected-study
  leakage; deterministic masks and exact pooled/specialist sample equality;
  healthy pooled and specialist backbones; three seed-stable runs; true-organ
  routing over pooled by at least 5%; organ-fixed over matched random-fixed by at
  least 3%; soft oracle over organ-fixed by at least 3%; and blind top-1 over
  pooled by at least 5%, with positive MSE/residual-Pearson intervals and at
  least 80% recovery of the true-organ gain.
- **Conditional branches:** if specialists and oracle pass but the blind router
  fails, run only selected controlled-transfer confirmations and repair the
  router. If oracle complementarity exists but organ identity fails against
  pooled/random controls, permit only a bounded label-free feasibility pilot.
  If the backbone, provenance, strict-study result, oracle headroom, or seed
  stability fails, stop Stage 2 and repair Stage 1.
- **Post-green execution order:** emit a machine-readable Stage 1 decision;
  freeze equal-budget transfer blocks; run one development-only affinity screen;
  preregister positive, negative, and near-zero pairs; confirm `A1+A2` versus
  `A1+B1` across three seeds; validate the shared-trunk architecture with
  supervised and random routing; run the frozen-trunk label-free MoE; then test
  route-transfer agreement and route-derived grouping function on the untouched
  discovery lockbox.

The authoritative thresholds, remaining data gaps, artifact contracts, compute
guardrails, and command order are backed up in
`stage1-stage2-experiment-plan.md`. The Stage 1 mechanical smoke command is now
runnable after its Stage 0 completion marker and remote-data preflight; definitive
Stage 1 and Stage 2 commands remain gated or planned.

### Research scheduling note (late 2026, evidence first)

A late-2026 submission window (roughly September-December) is a useful horizon,
not a reason to force a paper before the central results exist. Stage 1 cohort
quality, the end-to-end organ experiment, and a bounded Stage 2 feasibility pilot
remain the decision gates. Reassess venues only after those results establish a
defensible claim; until then, spend writing effort on protocols, experiment logs,
and the continuously updated citation ledger in `related-works.md`. Do not tune
cohort rules, claims, or success criteria to meet a venue date.

NASA OSDR is secondary because the current OSDR cohort is mouse-only. It cannot
serve as the primary interspecies-routing benchmark.

## Current Runtime Status

- The bounded competitive utility-axis follow-up is complete under commit
  `f8ab3cdc9527e3c5002e225a3e181a1599cc1d13`. Its formal result is
  `screen_fail` / `stop_discrete_utility_axis`; all three seeded outputs and the
  decision are on `moe-reboot` at
  `results/stage2_utility_axis_pilot_f8ab3cd/`. Both A100s are idle.
  The Stage 1 test split remains sealed and no test confirmation is authorized.
- `moe-reboot2` contains the original four small run outputs in addition to their
  checksum-verified central copies. `moe-reboot-partial` remains shelved.

### Archived July 16 runtime notes

- The corrected pooled control is running in remote tmux session
  `mixed20k_shuffled_20260715`. It uses the same 16,000 train / 3,200
  validation rows and V3 architecture, but `data_mode=preload` makes the
  `DistributedSampler` shuffle individual rows globally. Remote preflight found
  1,983/2,000 epoch-0 batches contained both species. At 23:05 UTC on July 16 it
  was at epoch 13, batch 500/2,000, at about 4.11 seconds/batch. The latest
  finalized best is epoch 12, validation loss `0.313560`,
  versus `0.5455396` for the original mixed V3 checkpoint. The live estimate is
  roughly 6.6 hours to training completion, around 22:41 PDT July 16 / 05:41 UTC
  July 17, followed
  automatically by freeze and frozen evaluation.
  Logs are in `results/mixed_20k_v3_shuffled_train.log`; checkpoints write
  directly to persistent
  `/media/volume/moe-reboot/checkpoints/mixed_20k_v3_shuffled`.
- Remote tmux session `mixed20k_shuffled_eval_watch_20260715` is waiting for a
  clean training exit. It will immediately run full, strict, and blind-gate
  evaluation with the frozen sample order and masks, write separate shuffled
  result directories, and refuse to overwrite any existing output.
- Remote tmux session `mixed20k_shuffled_freeze_watch_20260715` is independently
  waiting for the same clean training exit. It will atomically copy the completed
  checkpoint directory to persistent
  `checkpoints/mixed_20k_v3_shuffled_frozen`, verify every copied file with
  SHA256, and refuse to overwrite an existing freeze.
- The July 16 ten-minute update is ready in
  `presentation/2026-07-16-biweekly.html`, with timed notes in
  `presentation/2026-07-16-biweekly-script.md`. Reorganized 2026-07-15 into a
  ten-slide arc: slides 1-2 recap last semester and last week's apparent negative
  result for anyone who missed that meeting; slides 3-5 present the corrected
  Stage 0 headroom result, blind gate, and bounded interpretation; slides 6-8 the
  overarching goal and fair Stage 1 organ design, with
  slide 7 the near-full-bleed PaperPlot figure
  (`presentation/human-organ-moe-overarching-plan.png`, source prompt
  `presentation/paperplot-human-organ-moe-prompt.md`) with the embedded labels
  corrected to Stage 0/Stage 1 and the hard 32.94% result, beneath the exact fair
  comparison question; slide 9 the related-work novelty boundary and D1/D2/D3
  experiment choice; and slide 10 the selected gated Stage 2 experiment:
  controlled transfer, label-free routing, and a held-out agreement/functional test. Slide 8 now
  separates cohort, smoke-test, and Stage 2 decision gates. The current pooled
  retrain remains labeled ongoing on slide 5 and in the script.
  Desktop (1440x900), laptop (1280x720), and mobile (390x844) render checks passed
  after this reorganization: the desktop/laptop slides have no clipping, and
  mobile uses vertical scrolling without horizontal overflow. The HTML contains
  ten balanced slide sections. Repository validation also passes 70/70 tests;
  the four emitted warnings are existing PyTorch AMP deprecations.
- **Future presentation-script rule (requested 2026-07-16):** write the main
  narration for a nontechnical audience in short, conversational sentences. Lead
  with one plain-language takeaway per slide, define any necessary ML/biology term
  before using it, and move dense thresholds, acronyms, and methodological caveats
  into the slide, speaker backup, or Q&A. Prefer phrasing that is easy to say aloud
  over paper-style prose. This is a forward-looking rule; the July 16 script does
  not need another rewrite before this week's meeting.
- Keep `moe-reboot-partial` shelved for now. The active shuffled 20k control is
  the decision-critical GPU experiment; organ progress is currently limited by
  manual label/QC work and smoke staging, not missing evaluator code. Reassess the
  partial VM after shuffled evaluation determines whether the next GPU run
  should be a replication/control or a frozen-cohort Stage 1 pilot. If it is
  reused, write all checkpoints and results directly to persistent storage
  because the partial VM is ephemeral.
- The original V3 checkpoints and all prior evaluation artifacts remain
  untouched on persistent storage.
- **Original three 20k runs and backups complete.** Final epoch-15 checkpoints are human
  val `0.2791703`, MD5 `2bfad4ab0fa14ea7dd5a7ca5207b8df1`; mouse val
  `0.2310176`, MD5 `9d5a4c342a566f8bcfc5e9d186020d01`; mixed val
  `0.5455396`, MD5 `5d7f6fe24bd750f6b3fd1dd38916375e`. Each is verified
  on the Mac and central persistent storage with metadata archived. Human and
  mouse workers are idle and safe to shelve.
- **Corrected 5k/20k evaluation complete and validated.** GPU inference exited
  successfully. A transient watcher validation error was reproduced manually
  with the same copied bundle and passed; frozen sample/mask/schema checks are
  valid and the timestamped report addendum is generated.
- **Strict 20k diagnosis: practically convincing frozen adaptive ceiling.** The
  metadata-species soft router beats the out-of-fold fixed blend by `34.7%`
  relative MSE (absolute improvement `0.16493`, 95% CI `[0.15751, 0.17255]`)
  and residual Pearson `+0.1198` (95% CI `[0.1130, 0.1267]`). The soft oracle
  reaches `35.0%` relative MSE reduction, showing the metadata router captures
  nearly all measured routing ceiling on this cohort.
- **Blind species gating is now validated.** A leakage-protected logistic gate
  saw only the masked expression input, trained on 564 calibration samples from
  518 groups, and was evaluated on the unchanged 103-study strict cohort with
  zero group overlap. Strict accuracy was `99.03%` (49/50 human, 53/53 mouse;
  AUC `1.0`). Blind-soft routing reached MSE `0.31404`, versus `0.47547` for the
  calibration-fitted fixed blend: `33.95%` relative reduction, absolute gain
  `0.16143` with 95% CI `[0.15336, 0.16926]`, and residual-Pearson gain
  `+0.11450` with CI `[0.10768, 0.12144]`. It is only 1.11% worse in MSE than
  the true-species soft router (`0.31059`), so expression recovers nearly all of
  the measured routing ceiling.
- **Organ audit/pilot manifest complete.** Conservative ARCHS4 normalization
  produced 14,096 candidates across 603 connected study groups. After removing
  tumor-like rows, multi-organ groups, and capping each group at 20 samples, the
  data-driven criteria (at least 45 groups and 300 capped samples) select five
  organs: brain, skin, liver, colon, and lung. The organ-pilot manifest has 2,856 samples,
  317 groups, and 1,998 training rows. Studies are split atomically; calibration
  and test sample counts are balanced within each organ; and the pooled training
  hash exactly equals the union of specialist training IDs.
- **The raw archive is not the size bottleneck.** The mounted ARCHS4 v11 human H5
  contains 441,356 samples and 35,238 gene rows. The conservative audit retained
  only 14,096 candidates (3.2%): 195,698 rows were removed by the single-cell
  probability filter, 165,331 as cell/culture-like, and 66,231 because the current
  metadata regex did not assign one clear organ. ARCHS4's current official human
  gene-level release is larger still. The limiting resource is therefore validated
  bulk-organ labels distributed across enough independent studies, compounded by
  the age of the local v11 snapshot—not raw expression availability.
- The organ manifest is a **pipeline pilot**, not a frozen scientific cohort.
  Manual spot checking found residual acronym/cell-source ambiguity (for
  example GBM and HSAEpC metadata). Label review or ontology-backed expansion is
  required before definitive organ-model training. Current specialist train counts are also
  small (brain 783, skin 409, liver 345, lung 241, colon 220).
- **Class-balanced smoke protocol frozen.** The primary engineering subset contains
  exactly 220 training rows for each of brain, colon, liver, lung, and skin. Each
  of five matched random shards also contains 220 rows—exactly 44 from each organ—
  while the full 2,856-row natural cohort is retained for secondary reporting.
  Pooled, specialist, and random-control training use the same organ/study-balanced
  rule; checkpoint selection, blind-router fitting, and primary evaluation are also
  organ/study balanced, so brain frequency cannot win the comparison by itself. This
  removes frequency bias but does not manufacture label accuracy,
  statistical power, or independent studies.

## What Changed from V2 to V3

V3 is primarily a data-scale experiment, not a new MoE architecture:

| Dimension | V2 5k | V3 20k | Interpretation |
|---|---|---|---|
| Train / validation rows per expert | 4,000 / 800 | 16,000 / 3,200 | 4x more rows |
| Model | 4-layer `ExpressionPerformer` | Same | Architecture held fixed |
| Gene space | Shared 15,448 genes | Same | All six checkpoints are compatible |
| Objective | `log1p_tpm`, 30% mask, wd 0.01 | Same | Same reconstruction task |
| Training | V2 seed/draw; 20-30 epochs | seed 123; 15 epochs, batch 8 | Not a perfectly single-variable scale test |
| Holdout | Removed retrospectively for corrected evaluation | 667 IDs excluded during preprocessing | V3 explicitly protects the frozen cohort |

The qualitative discovery is mostly an **evaluation correction**, because the
same V2 checkpoints that previously appeared to have approximately zero routing
headroom show a strong effect under the corrected protocol. V3 then amplifies
that effect:

| Strict study-disjoint comparison vs OOF fixed blend | V2 5k | V3 20k |
|---|---:|---:|
| True-species hard router: relative MSE reduction | 17.9% | 33.5% |
| True-species soft router: relative MSE reduction | 18.7% | 34.7% |
| Hard MSE oracle: relative MSE reduction | 17.9% | 33.8% |
| Soft MSE oracle: relative MSE reduction | 19.3% | 35.0% |

Thus this is not mainly a soft-oracle artifact. Hard true-species routing already
works; soft mixing adds about 0.9% relative MSE over hard routing at 5k and 1.8%
at 20k. The important changes were applying the training-space `log1p` transform,
using grouped out-of-fold comparisons and train-only baselines, distinguishing a
pooled single expert from a fixed ensemble, and measuring routing against that
fixed ensemble. The `mixed` checkpoint is one pooled expert, not an oracle.

V3 contributes a real scale result on top: on the strict paired cohort, adaptive
MSE headroom over the fixed blend increases by `0.04064` from 5k to 20k (95% CI
`[0.03210, 0.04928]`), and Pearson headroom increases by `0.00552` (95% CI
`[0.00413, 0.00693]`).

## Stage 1 Hypothesis and Experimental Design

### Primary hypothesis

Given a human bulk RNA-seq sample with no organ label, a gate using only the
observed expression input can select an organ-specialized expert whose masked-
gene reconstruction is better than one general human model trained on the exact
same union of samples.

The number of experts is a data-driven `K`, not a fixed four. Include only organs
with enough samples and independent GEO studies to support specialist training
and a genuinely study-disjoint test. If expert `k` receives `N_k` training rows,
the fair-data constraint is:

```text
sum(N_k for k in 1..K) = N
general model training rows = the identical N-sample union
```

### Fair training and inference

- Use the same human gene vocabulary, architecture, masking, optimizer, and
  number of sample exposures for the pooled model and every specialist.
- Each training sample belongs to exactly one organ expert and also appears in
  the general model's union; no specialist receives extra data.
- The primary practical system uses a blind top-1 gate, so each sample executes
  one expert plus a small classifier, approximately matching general-model
  inference FLOPs. Report the `K`-fold storage/parameter cost separately.
- The gate sees only the same masked/observed expression available to the expert,
  never the reconstruction targets. Train/calibrate it on studies excluded from
  the final test.
- Add a confidence threshold and general-model fallback for ambiguous, mixed, or
  out-of-taxonomy organs.

### Required comparison ladder

1. **One pooled general human model on all `N` samples:** practical baseline.
2. **`K` random-shard experts with fixed weights:** controls for generic
   sharding, extra stored parameters, and ensembling without organ specialization.
3. **`K` organ experts with fixed weights:** isolates biological specialization
   from random-shard ensembling, but evaluates all experts at inference.
4. **True-organ hard/soft routing:** metadata-conditioned specialization ceiling.
5. **Blind expression-derived top-1/soft gate:** deployable unknown-organ system.
6. **Per-sample soft oracle:** non-deployable upper bound using target values.

The primary effectiveness comparison is blind top-1 organ MoE versus the pooled
general model. Blind versus fixed organ ensemble isolates adaptive routing; organ
versus random-shard ensemble isolates organ specialization; blind versus
true-organ and oracle conditions measures unrealized routing headroom.

### Proposed success criterion

The primary Stage 1 claim is practically convincing only if blind top-1 routing:

1. beats the pooled general model by at least 5% relative MSE reduction;
2. has a paired absolute-MSE improvement CI with lower bound above zero;
3. has a residual-Pearson improvement CI with lower bound above zero; and
4. recovers at least 80% of the true-organ hard-routing improvement over the
   pooled model, using the same strict test samples.

Biological specialization additionally requires the organ fixed ensemble to beat
the random-shard fixed ensemble by at least 3% relative MSE with a positive
absolute-MSE CI. Adaptive soft-routing evidence requires blind soft routing to
beat the organ fixed ensemble by at least 3% with a positive absolute-MSE CI.
Organ-classifier accuracy is diagnostic, not a substitute for end-to-end
reconstruction performance.

## Stage Transition Decision

Stage 0 is strong enough to begin Stage 1 dataset auditing, cohort freezing, and
a small organ pilot now. The strict result is large, statistically separated from
zero, present under hard routing, and stronger at 20k, so further species-only
ceiling analysis has diminishing value.

Two Stage 0 experiments were required before a definitive Stage 0 claim or a
full-scale `K`-organ training campaign:

1. **Blind species gate: complete.** The expression-only gate recovers almost all
   of the true-species ceiling and strongly beats both the pooled model and fixed
   ensemble on the strict study-disjoint cohort.
2. **Corrected pooled mixed retrain: running.** Global row shuffling removes the
   known V3 pooled-control weakness; rerun the frozen evaluation after its best
   checkpoint is finalized.

The successful blind gate is strong enough to continue organ metadata cleanup
and pipeline development. The active pooled retrain and organ label validation
still block the strongest publication claim and major Stage 1 compute spending.

## Active Run Completion Runbook

This section is the source of truth for the next agent. Do not launch a duplicate
training, freeze, or evaluation process without checking these states first.

### First status check

Run from a machine with the existing SSH alias:

```bash
ssh moe-reboot 'cd /home/exouser/nasa-rna-moe && \
  date -Is && nvidia-smi && tmux list-sessions && \
  tail -30 results/mixed_20k_v3_shuffled_train.log && \
  cat results/mixed_20k_v3_shuffled_freeze.status && \
  cat results/mixed_20k_v3_shuffled_eval.status'
```

Expected while training: three tmux sessions named
`mixed20k_shuffled_20260715`, `mixed20k_shuffled_freeze_watch_20260715`, and
`mixed20k_shuffled_eval_watch_20260715`. Both watchers should say
`WAITING_FOR_TRAINING`. Closing the local terminal/computer does not stop them.

### Automated sequence after training

1. `runs/train_mixed_20k_v3_shuffled.sh` writes the best checkpoint under the
   persistent `checkpoints/mixed_20k_v3_shuffled` directory and writes
   `results/mixed_20k_v3_shuffled_train.exit_code` when the tmux wrapper exits.
2. `runs/freeze_shuffled_mixed_when_complete.sh` requires exit code zero and
   `best_model.pt`, copies the entire stable checkpoint directory through an
   `.incomplete` staging directory, verifies `SHA256SUMS`, and creates:
   - `checkpoints/mixed_20k_v3_shuffled_frozen/`
   - `results/mixed_20k_v3_shuffled_freeze.COMPLETE`
   - `results/mixed_20k_v3_shuffled_freeze.status`
3. `runs/evaluate_shuffled_mixed_when_complete.sh` independently requires the
   same clean exit and checkpoint, then runs:
   - corrected full-cohort inference with the original frozen mask;
   - strict 103-study analysis from that cache;
   - the leakage-protected blind species gate on the new three-expert cache;
   - frozen mask, sample count/order, and checkpoint-path validation.
4. Successful evaluation creates:
   - `results/interspecies_headroom_20k_v3_shuffled_corrected/report.json`
   - `results/interspecies_headroom_20k_v3_shuffled_strict_study_disjoint/report.json`
   - `results/blind_species_gate_20k_v3_shuffled/report.json`
   - `results/mixed_20k_v3_shuffled_eval.COMPLETE`
   - `results/mixed_20k_v3_shuffled_eval.status`
   - `results/mixed_20k_v3_shuffled_eval.log`

The watchers do **not** update `progress.md`, `report.md`, the presentation, or
Git, and they do not copy reports back to the Mac. Those are required manual
post-completion steps below.

### Stage 0 decision after shuffled evaluation

Use the **strict 103-study result** as primary; full-cohort results are diagnostic.
In `results/blind_species_gate_20k_v3_shuffled/report.json`, inspect
`blind_soft_vs_fixed`, `blind_soft_vs_mixed`, `metadata_soft_vs_fixed`, and
`soft_oracle_vs_fixed`.

- **Practically convincing Stage 0:** blind soft beats both the out-of-fold fixed
  blend and shuffled pooled model by at least 5% relative MSE; both absolute-MSE
  CIs have lower bounds above zero; blind-soft residual-Pearson versus fixed has
  a CI lower bound above zero; and soft oracle versus fixed clears 3%.
- **Promising but not yet practical:** blind soft beats fixed with positive
  absolute-MSE CI and at least 3% relative MSE, but misses the 5% or
  residual-Pearson criterion.
- **Ensemble-only benefit:** blind routing beats the pooled model but not the
  fixed blend. Do not describe this as useful adaptive MoE routing.
- **Adaptive ensemble benefit but no general-model win:** blind routing beats
  fixed but not the shuffled pooled model. The router improves the ensemble but
  is not a better practical system than the fairer general control.
- **No meaningful routing ceiling:** soft oracle versus fixed is below 3% or its
  absolute-MSE CI includes zero. Stop gate tuning and revisit expert/data design.
- **Study-generalization failure:** a positive full-cohort result disappears on
  strict. Treat this as study leakage/domain dependence, not evidence for MoE.

Classifier accuracy/AUC is secondary. The deployment claim is reconstruction
improvement from a gate that sees only masked expression.

### Required manual steps after both COMPLETE markers

1. Verify both exit codes are zero and run `sha256sum -c` inside the frozen
   checkpoint directory once more.
2. Record best epoch, train/validation loss, checkpoint SHA256, runtime, and the
   three strict comparisons above.
3. Copy the small report JSON files, freeze metadata, and SHA256 manifest to a
   new local `artifacts/stage0_shuffled_control/` directory. Do not commit model
   weights to Git.
4. Compare old versus shuffled pooled MSE on identical strict samples and state
   whether the Stage 0 conclusion survives. Do not compare different masks,
   cohorts, or estimands.
5. Append a timestamped result to `report.md`; update current status and decision
   in `progress.md`; replace the slide 5 current-run sentence only if the complete
   frozen evaluation is available.
6. Run syntax checks, focused tests, the full suite, and `git diff --check`, then
   commit and push. The current baseline is 70/70 tests.
7. `moe-reboot` is safe to shelve only after training, freeze, and evaluation
   have all exited and both COMPLETE markers/checksums are verified. Persistent
   volume paths must resolve before shelving.

### Failure recovery without destroying artifacts

- **Training exit nonzero:** both watchers intentionally become `BLOCKED`. Keep
  every checkpoint and inspect the training log. Resume only from the newest
  verified per-epoch file under
  `checkpoints/mixed_20k_v3_shuffled/<run_id>/epoch_*.pt` using
  `RESUME_FROM=<path>` with `DATASET_VARIANT=mixed_20k_v3_shuffled`. Launch the
  resume under tmux and point new versioned watchers at its exit marker; never
  delete or overwrite the failed run.
- **Freeze FAILED/BLOCKED:** inspect
  `results/mixed_20k_v3_shuffled_freeze.log` and any `.incomplete` directory.
  Verify the source checkpoint before moving the incomplete copy to a timestamped
  quarantine path and starting a versioned retry. Do not remove it blindly.
- **Evaluation FAILED:** inspect `results/mixed_20k_v3_shuffled_eval.log` first.
  The watcher refuses to overwrite partial output directories. Preserve them by
  moving them to timestamped diagnostic names, correct the underlying issue,
  then use new versioned output paths for a retry. Reuse the exact frozen masks
  and strict IDs.
- **Watcher missing while training continues:** training is independent. Recopy
  the committed watcher script and relaunch only the missing tmux session after
  confirming no process with the same script is alive.

## Stage 1 Organ Execution Runbook

Do not launch the definitive organ models from the current organ-pilot manifest.
It is sufficient for pipeline smoke testing but still contains label ambiguity
and only 220-783 training rows per specialist.

### Cohort readiness gate

Before a definitive GPU campaign:

1. retain enough raw metadata to audit each label, including characteristics;
2. replace or supplement regex labels with ontology-backed normalization;
3. exclude cell lines, cultures, organoids, xenografts, tumors, ambiguous organs,
   and connected study groups spanning multiple organ labels;
4. manually review at least 50 stratified samples per selected organ and require
   at least 95% label precision before freezing;
5. require at least 1,000 clean training samples and 30 independent training
   study groups per included organ for the definitive run; organs below this can
   remain in a smoke test but must not drive the primary claim;
6. choose `K` only from these preregistered availability rules, not from model
   performance; and
7. freeze sample order, connected-group splits, hashes, exclusions, and the exact
   pooled/specialist union before training.

### Ordered Stage 1 execution plan

1. **Label audit and expansion — still open:** retain auditable metadata and produce
   stratified manual-review sheets. Resolve GBM, HSAEpC, tumor acronyms, and tissue-
   versus-derived-cell ambiguity. Use ARCHS4 tissue-atlas groupings only as candidate
   expansion, then validate against source GEO metadata/ontologies before freezing.
2. **Exact dataset extraction — implemented:**
   `preprocessing/extract_manifest_expression.py` extracts only frozen manifest IDs
   into the shared 15,448-gene raw-TPM space, preserves row order, records hashes,
   and fails on missing/duplicate IDs, gene mismatches, connected-study leakage, or
   explicit expression QC failures. It never silently drops rows.
3. **Balanced controls and training — implemented for the smoke:**
   `evaluation/build_balanced_organ_protocol.py` freezes equal organ subsets and
   exactly matched random shards. `core/train_manifest.py` trains pooled, organ, and
   random roles from explicit splits with deterministic masks/RNGs, fixed update
   budgets, balanced sampling/checkpoint selection, and full prediction export. The
   pooled smoke receives `K` times one specialist's updates, matching exposure to the
   collective specialist system.
4. **Frozen prediction/evaluation — implemented:**
   `evaluation/cache_organ_predictions.py` checks sample/gene/mask identity before
   caching. `evaluation/evaluate_organ_moe.py` reports pooled, individual experts,
   organ/random fixed ensembles, true-organ hard/soft, blind hard/soft, and hard/soft
   oracle conditions using equal-organ/equal-study primary metrics, natural-frequency
   secondary metrics, and study-clustered uncertainty.
5. **Blind gate — implemented for the closed five-organ smoke:** the five-class
   logistic router is fit only on calibration rows, receives the target-hidden masked
   expression, and uses balanced class plus equal-study weights. Unknown-organ
   abstention/fallback remains a definitive-cohort extension because the current
   closed taxonomy contains only the five selected organs.
6. **Mechanical smoke — ready but not launched:** `runs/run_organ_smoke.sh` performs
   dependency/marker preflight, balances the cohort, runs an explicit QC-and-rebalance
   pass if necessary, trains every matched model, builds the cache, evaluates, and
   writes `SMOKE_ONLY` plus `COMPLETE`. It refuses to overwrite outputs and waits by
   default for the Stage 0 shuffled-evaluation completion marker.
7. **Definitive run and decision — still gated:** build an expanded, manually audited
   five-way manifest (model train, model validation, gate calibration, final test,
   discovery lockbox), add the definitive launcher, run three seeds, and apply the
   preregistered criteria without tuning after test access.

### Approved progressive Stage 1 pilot design

1. **Micro overfit test:** use 64-128 samples and 20-50 updates to verify target
   hiding, loss decrease, gradient flow, deterministic masks, checkpoint resume,
   and cached-prediction identity.
2. **Five-organ mechanical smoke:** use the current `K=5` manifest, one seed, and
   approximately 50 updates per model. Exercise pooled, five organ specialists,
   matched random shards, fixed blend, true-organ routing, blind routing, and
   oracle evaluation end to end. Passing means the machinery is correct; the
   result has no biological interpretation.
3. **Two-organ feasibility pilot:** after removing obvious label failures, select
   brain and skin prospectively because they have the greatest sample/study
   support. Use the production backbone, matched 3-5 epoch exposure, and seeds
   17, 42, and 101. Compare pooled, organ specialists, and size/study-matched
   random shards using one frozen mask and equal-organ/equal-study macro metrics.
   This estimates wall time, seed variance, oracle headroom, and whether the
   longer definitive campaign is worth running.

The current pilot test studies are engineering data and become burned after this
inspection. A definitive Stage 1 cohort must receive newly frozen model-validation,
gate-calibration, final-test, and discovery-lockbox partitions after label cleanup
and expansion. Approximate 5%/3% effect thresholds guide feasibility, but only the
powered definitive run supports a biological claim.

### Stage 1 outcome interpretation

- **Full success:** all primary blind-top-1 criteria pass, organ fixed beats
  random fixed, and blind routing recovers at least 80% of the true-organ hard
  ceiling. This supports an accurate, inference-efficient organ MoE, with extra
  storage reported as a cost.
- **Experts work, gate fails:** true-organ routing passes but blind routing does
  not. Improve router inputs/calibration or fallback logic; do not retrain experts
  first unless their ceiling is also weak.
- **Generic ensemble only:** organ fixed does not beat random fixed. Any gain is
  attributable to sharding/ensembling, not organ biology.
- **No organ specialization:** true-organ hard routing fails to beat pooled by
  at least 5% with positive MSE/residual intervals. Revisit labels, data scale,
  organ granularity, or architecture; do not claim transfer from Stage 0.
- **Statistically positive but practically small:** MSE CI is positive but the
  primary gain is below 5%. Report it as preliminary and do not scale solely on
  that basis.
- **Strict-only failure:** full cohort passes but strict study-disjoint test does
  not. Treat as study/domain leakage and improve cohort diversity.
- **Efficiency failure:** accuracy passes but top-1 inference is not roughly one
  expert plus a small gate, or fallback activates excessively. Report as an
  ensemble result rather than an efficient MoE system.

### Stage 1 artifacts already available

- Audit code: `evaluation/audit_archs4_organs.py`
- Manifest builder: `evaluation/build_organ_pilot_manifest.py`
- Pilot reports/manifest: `artifacts/stage1_organ_pilot/`
- Exact expression extractor: `preprocessing/extract_manifest_expression.py`
- Deterministic role-aware trainer: `core/train_manifest.py`
- Balanced organ/random protocol:
  `evaluation/build_balanced_organ_protocol.py` and
  `artifacts/stage1_organ_smoke_protocol/`
- Explicit QC filter/rebalance pass:
  `evaluation/filter_manifest_by_expression_qc.py`
- Frozen prediction cache, five-class blind router, full comparison ladder, and
  decision emitter: `evaluation/cache_organ_predictions.py`,
  `evaluation/evaluate_organ_moe.py`, and
  `evaluation/decide_organ_specialization.py`
- End-to-end fail-fast launcher: `runs/run_organ_smoke.sh`
- Overarching figure prompt:
  `presentation/paperplot-human-organ-moe-prompt.md`
- Current organ pilot: brain, skin, liver, colon, lung; 2,856 samples; 317 groups;
  exact pooled/specialist train-union hash
  `332760cf8ca98535e3d0a4f3548e733a0723d6c8ea985e4268e9a7c06990c35d`.
- A 2026-07-15 cap-sensitivity check on the same conservative candidates, after
  tumor and multi-organ-group exclusion, confirms that simply raising the
  per-study cap does not rescue the definitive `K=5` cohort. At cap 60, capped
  totals are brain 2,039, skeletal muscle 1,246, skin 971, liver 707, adipose
  670, colon 446, and lung 418; an approximate 70% training allocation leaves
  only brain above 1,000. Removing the cap would let a few organs cross 1,000
  but reintroduces severe single-study dominance. The practical options are
  ontology-backed label expansion, a prospectively justified lower threshold,
  or a smaller `K`—never a post-result threshold change.

## Stage 2 Research Direction (prepare during Stage 1; run after readiness gates)

### Scientific aim

Use MoE specialization as a probe of what structure a masked RNA-seq model learns:
which human expression domains should share parameters, which interfere, and whether
label-free routing recovers reproducible biological programs that were never supplied
as training labels. The organ interference matrix remains valuable, but it is an
anchor measurement rather than the entire Stage 2 claim.

Stage 1 remains the immediate priority and the calibration experiment: first establish
whether explicit, audited organ specialists and a blind gate beat the fair pooled and
random-shard controls. Stage 2 infrastructure, deterministic smoke tests, a separate
lockbox, and a small variance/cost pilot may be prepared in parallel. Definitive
Stage 2 analyses must not inspect a test set already used to choose a Stage 1 story.

The organ strata all optimize the same masked-reconstruction objective, so describe
D1 precisely as **cross-domain transfer/interference**, not literally distinct-task
multi-task learning. Task-affinity methods are methodological ancestors, not evidence
that the biological result is already known.

### Practicality and novelty decision

Claude's full pairwise D1 is not the unconditional default. The current best bet is a
**hybrid**: use a cheap development-only gradient-affinity screen to identify likely
positive and negative transfer edges, confirm a small number with controlled pair
training, and ask whether a label-free MoE independently learns the same grouping.
Scale to a full matrix only if the cohort and pilot justify it.

| Candidate | Novelty if successful | Data / implementation | Compute / storage | Decision |
|---|---|---|---|---|
| Full `K x K` organ transfer matrix | Moderate: useful genomics measurement, but task/domain affinity is established | Needs at least four well-powered organs and all Stage 1 infrastructure | Roughly 60-105+ seeded runs; current 434 MB checkpoints make per-epoch retention infeasible | Conditional follow-up, not first Stage 2 run |
| Gradient-affinity screen + selected pair confirmation | Moderate alone; strong as a bridge from optimization to biology | One balanced pooled development run plus 2-4 prespecified pairs | Approximately 10-20 runs including seeds/controls | Recommended D1 implementation |
| Label-free shared-trunk MoE | Higher upside: asks whether routing discovers stable RNA-seq structure without organ labels | Can use the full clean pooled cohort; requires a new router/expert path and strict batch controls | Frozen-trunk pilot first; at least three full-cohort runs only after its gate | Recommended Stage 2 core pilot |
| Hierarchical organ -> latent-state MoE | High discovery upside if it finds a replicated within-organ program rather than rediscovering tissue | Brain is currently the only plausible first organ; requires curated disease/age/treatment/sex/composition metadata and independent studies | Small `K=2-3`, but validation and metadata work dominate | Conditional follow-up after the label-free pilot, not an immediate run |
| Pathway- or cell-type-supervised experts | Lower discovery value because the answer is injected through labels; mature neighboring literature | Requires external annotations/deconvolution and a different task definition | Moderate | Interpretation control only |

The exciting claim is not "MoE works on RNA-seq." It is that label-free routing finds a
reproducible biological organization, that the organization predicts measured transfer,
and that it improves reconstruction under fair active-compute controls. If only the
first or second component holds, narrow the claim accordingly.

### D1 — Directed organ transfer graph (screen first, confirm selected edges)

First estimate a directed domain-affinity graph on development studies during one
balanced pooled-training run: measure how an update from donor-domain `B` changes the
held-out development loss for recipient `A`, following established gradient-affinity
work. Use this only to screen and preregister a small number of strongest positive,
negative, and near-zero pairs. Confirm those edges by training joint `A+B` models and
evaluating on a fixed, study-disjoint test set for `A`. One unordered pair model supplies
both directions, but the effects need not be symmetric. The screen is not a substitute
for actual pair-training confirmation.

**Estimands and sign (freeze before results).** Let `L_A(f)` be study-macro masked MSE
of model `f` on recipient `A`. Positive values always mean beneficial transfer:

```text
raw_transfer[A <- B] = (L_A(f_A) - L_A(f_A+B)) / L_A(f_A)
controlled_transfer[A <- B] =
    (L_A(f_A1+A2) - L_A(f_A1+B1)) / L_A(f_A1+A2)
```

For the primary controlled comparison, split eligible development/training studies
within each organ into fixed blocks. `A1+A2` and `A1+B1` have matched sample counts,
study-count targets, optimizer updates, and sampling weights. This changes the question
from "does adding any data help?" to "is the same budget better spent on another block
of the recipient or on donor `B`?" If an organ cannot supply a credible `A2` reserve,
omit the confirmatory cell rather than silently substitute an unmatched global pool.
Also report two transparent secondary controls:

1. an `A1`-replay exposure control, which controls optimization budget but not the
   information in new unique samples; and
2. deterministic matched random-pseudogroup blocks, which test whether apparent
   structure arises from arbitrary sample sharding rather than organ identity.

**Protocol requirements.**

1. Freeze a global connected-study split and a discovery lockbox before Stage 1 test
   inspection. No recipient or donor test study may enter any model's training,
   validation, gate calibration, or reference-donor pool.
2. Require a prospective test-study/power gate per recipient; the current 7-15 test
   groups per organ are not automatically adequate for 20 off-diagonal comparisons.
3. Fix optimizer updates, recipient:donor sampling ratio, loss weighting, LR schedule,
   deterministic validation mask, and checkpoint-selection rule. Equal epochs are not
   an equal exposure budget when pair datasets differ.
4. Use at least three explicit training seeds for definitive cells. Clustered bootstrap
   over test studies measures cohort uncertainty but not model-training stochasticity;
   report both. Apply Benjamini-Hochberg to the `K(K-1)` off-diagonal hypotheses, not
   structural diagonal cells, and preregister a practical effect threshold.
5. Report absolute and recipient-standardized effects, train-only organ gene-mean and
   pooled baselines, residual correlation, and gene-module-stratified errors. Otherwise
   a heatmap may mostly rediscover organ expression means.
6. Test an omnibus organ-identity effect against the pseudogroup null before treating
   individual edges as biological. Add leave-one-organ-out models or use the
   development-only affinity graph to choose grouped
   experts and validate that grouping on the untouched lockbox. Pairwise effects alone
   do not establish the higher-order behavior of a full pooled model.

**Cost gate.** The earlier 15-25-run estimate was too optimistic. At `K=5`, five solo
models, ten pair models, controls, and three seeds can easily become 60-105+ runs. A
current inference/training checkpoint is about 434 MB, so retaining per-epoch files for
that grid would also exceed the 117 GB currently free on the central volume. First run
one two-organ, three-seed pilot; measure wall time and seed variance; keep only
checksum-verified best/last inference artifacts plus compact histories; then freeze a
complete run table and compute/storage budget. The default is to confirm selected edges,
not to launch the full grid.

### D2 — Label-free MoE routing as a biological representation probe

This is the linked discovery experiment, not a claim that can be made from the current
organ experts. Experts trained from organ labels can validate a gate, but they cannot
show that organ or hidden biological structure *emerged*.

1. Reuse `ExpressionPerformer` through its final hidden states as a shared trunk. Pool
   only observed-gene hidden states to drive a sample-level router; attach `K` small
   residual FFN adapters plus scalar reconstruction heads. Train soft routing first and
   evaluate top-1 dispatch, with an explicit load-balancing term and capacity limit.
   Do not provide organ, study, platform, disease, or other phenotype labels to the
   router or experts. Choose `K`, balancing strength, and adapter size on development
   studies only.
2. Use a two-step feasibility path: first freeze a Stage 1 pooled trunk and train only
   adapters/router (cheap test of routing signal); then fine-tune the full model only if
   routes are non-collapsed and cross-study stable. The current `train_moe.py` blends
   frozen, predefined expert predictions and cannot answer this emergence question.
3. Compare against the pooled model, matched active-parameter/FLOP controls,
   random/permuted routing, random-shard experts, and the supervised organ-expert
   ceiling. For claimed representation structure, also compare raw expression, PCA,
   NMF, and shared-trunk geometry. Track collapse, expert utilization, storage, and
   total training compute.
4. Measure routing/expert-advantage stability across seeds, masking realizations, and
   held-out studies before interpreting clusters. Evaluate every sample against every
   expert to report counterfactual routing regret, not only router assignments. Known-
   organ recovery is a positive control, not a hidden discovery.
5. Test whether routing aligns with study, platform, library size, and other technical
   variables. A route that identifies GEO study or processing protocol is a confound,
   not biology. Require cross-study replication and conditional analyses within organ;
   retain multi-organ studies when a global group split can use them as technically
   valuable controls.
6. Attribute route decisions to observed genes, test frozen pathway/gene-program
   enrichments, and validate any beyond-organ pattern against independent metadata or
   an external cohort. Findings chosen after looking remain explicitly exploratory.
7. Compare the learned route co-assignment graph with D1 transfer effects on held-out
   data. The strongest joint result would be that label-free routes group domains that
   demonstrably transfer, and separate domains that interfere.

**Claim ladder.**

- If routing is unstable across seeds or dominated by study/platform, make no latent-
  biology claim.
- If it reproducibly recovers only organ, report recovery of known tissue structure as
  validation, not discovery.
- A hidden-pattern claim requires a stable beyond-organ association, technical-confound
  controls, pathway-level interpretation, and independent replication.
- A useful MoE claim additionally requires reconstruction improvement over the fair
  pooled/random controls at matched active inference compute; interpretability alone
  does not establish a better predictive system.

**Conditional within-organ discovery branch.** If the first label-free router mostly
recovers the dominant organ axis, do not call that hidden biology. If brain remains the
only sufficiently powered organ, a later `K=2-3` brain-only pilot may remove/condition
on organ identity and ask whether routes reproduce a disease, age, treatment, cell-
composition, or pathway state across independent studies. Freeze the route definition
before metadata association, require within-study and cross-study replication, and
compare against PCA/NMF/clustering baselines. Do not start this branch until the relevant
metadata are curated well enough to distinguish biology from study design.

### D4 — Spaceflight organ-perturbation localizer (NASA transfer to OSDR)

The NASA-facing application arm. Prepared during Stage 1; run only once audited organ
experts exist and after Stage 1 test decisions are frozen. Added 2026-07-16.

**Scientific aim.** Reuse the Stage 1 ground-trained organ experts as instruments to
localize *where and how* the spaceflight transcriptome departs from its terrestrial
organ baseline. Ground ARCHS4 organ experts supply a well-powered, organ-conditional
expectation; applied to NASA OSDR/GeneLab flight samples and their matched ground
controls, the structured, control-subtracted reconstruction residual becomes a
per-organ, per-pathway measure of spaceflight perturbation. This turns NASA's actual
data reality (huge ground corpus, tiny space corpus, no need for flight labels) into
the method's strength.

**Why this is not just "how good is the expert."** Absolute reconstruction error on a
flight sample is dominated by the expert's intrinsic quality (the liver expert is weak
regardless of spaceflight) and by space-vs-ground batch. The estimand must cancel both.
Decompose per-sample masked error as `expert_floor(organ) + batch(cohort) +
biology(condition) + noise`. `expert_floor` is identical for flight and matched control,
so it cancels in a within-expert, within-tissue contrast; organs are ranked by the
control-subtracted delta, never by absolute error.

**Estimand (freeze before results).** For organ/expert `e`, with flight set `F_e` and
matched ground-control set `C_e` from the same OSDR study/processing:

```text
Delta_e = z_e(residual(F_e)) - z_e(residual(C_e))
```

where `z_e` standardizes against expert `e`'s held-out ground residual distribution
(so "liver expert is bad" is already in the null). `Delta_e > 0` means flight departs
from the organ baseline more than its own ground control does. Characterize the residual
as a gene/pathway vector, not only a scalar: a real perturbation produces reproducible,
pathway-coherent residuals across flight replicates; a merely weak expert produces
high-variance unstructured residuals. Report a router-shift readout (did the gate
reassign the flight sample vs ground samples of that tissue?) separately from the
reconstruction residual — input geometry moving is a distinct axis from expert failure.

**Win condition and the null.** Good reconstruction of flight data is the *null*, not the
result: if the ground expert reconstructs flight perfectly, flight looks like ground and
no effect is detected. The signal is differential, structured reconstruction failure that
is larger and more coherent under flight than under matched control. Never frame "we can
reconstruct spaceflight transcriptomes" as success.

**Controls (mandatory).**

1. Matched ground control per flight sample (habitat/vivarium controls, shared
   processing). No control pairing -> no claim.
2. Ground-vs-ground negative control: run the identical pipeline on two ground cohorts
   from different labs/platforms; the flight delta must exceed this batch-only delta.
3. Benchmark against plain flight-vs-control differential expression (limma/DESeq2) on
   the same OSDR study. The model only earns its place if borrowing strength from the
   ground corpus gives a better-powered, better-calibrated, cross-organ-comparable
   perturbation readout than tiny-study DE. If DE matches it, report that the model adds
   nothing.

**Feasibility / reuse.** Largely an inference-time analysis on top of existing machinery:
`train_moe.py` already computes per-expert, per-variant masked-MSE, which is the exact
primitive the residual score generalizes. Requires audited Stage 1 organ experts; an
OSDR/GeneLab flight+matched-control cohort with tissue labels mapped to the expert organ
set and to the ARCHS4 gene space; and confirmation of matched-tissue counts (check the
OSDR catalog before committing — human matched tissue is scarce; rodent missions carry
most matched multi-organ samples).

**Novelty boundary.** Routing/residual as an OOD/anomaly signal is established in ML
(vision-FM+MoE OOD 2510.10584, MoECLIP, the DLR multimodal-anomaly MoE) and is NOT novel
as a mechanism. Spaceflight transcriptomics ML exists but is task-specific (npj
Microgravity 2026 retinal-damage ensemble; NASA GeneLab authors) or non-MoE
representation learning on plants (GLARE, in `related-works.md` block C). The open
contribution is the rigorous biological application — ground-pretrained organ experts as
a control-subtracted, cross-study, pathway-resolved spaceflight-perturbation localizer on
OSDR — not the anomaly mechanism. Positions naturally with D1: do organs that are coupled
in the interference graph also co-respond to spaceflight?

### Ordered Stage 1 -> Stage 2 execution

1. **Cohort feasibility and audit:** retain auditable metadata, validate labels, and
   determine `K` from frozen quality/study/power rules. The current pilot fails the
   definitive 1,000-training-sample rule for every organ and is not a final cohort.
   Reconsider automatic deletion of multi-organ studies: keep them when sample labels
   are valid and assign the entire connected group to one split; they provide unusually
   strong within-study technical controls.
2. **Split design:** prefer study-disjoint model-validation and discovery-lockbox
   partitions distinct from gate calibration and final Stage 1 test. If study counts
   cannot support a separate lockbox, freeze all Stage 2 hypotheses before the first
   Stage 1 test access and require independent external replication for discovery claims.
3. **Shared infrastructure:** the manifest-driven extractor, manifest-aware seeded
   trainer, deterministic Stage 1 evaluator, and hashed smoke artifacts are complete.
   Extend their frozen contracts rather than creating an untracked alternate path.
4. **Smoke and variance pilot:** run the five-organ mechanical smoke, then a two-organ,
   three-seed pilot
   solely to estimate variance, power, and cost. Do not elevate pilot biology to a
   claim.
5. **Definitive Stage 1:** run the preregistered pooled, random-shard, organ-specialist,
   metadata, blind-gate, and oracle ladder.
6. **Stage 2 screen:** compute development-only gradient affinity, preregister selected
   positive/negative/null edges, and run their matched-block confirmation. Do not infer
   biology from the screen alone.
7. **Label-free pilot:** run the frozen-trunk adapter/router experiment if Stage 1
   infrastructure is stable; scale it only if routes are non-collapsed, cross-study
   stable, and not explained by technical metadata.
8. **Expansion decision:** build the full D1 matrix only if the selected-edge pilot is
   seed-stable, clears the practical-effect threshold, and the powered organ count is
   sufficient. Otherwise spend compute on replication and biological validation of the
   smaller, stronger result.

The exact Stage 1 decision boundaries, remaining data/code gaps, CLI contracts,
artifact schema, and post-Stage-1 command order are in
`stage1-stage2-experiment-plan.md`. The mechanical smoke is implemented; commands
explicitly marked `PLANNED` there remain non-runnable specifications.

### Archived (not planned)

- **D3 — router weights as deconvolution.** Bulk RNA-seq deconvolution is a mature
  field (CIBERSORT, Scaden, and the neural/Bayesian methods in `related-works.md` D3
  block), and MoE-for-cell-type already exists (GC-MoE). Only the "emergent,
  unsupervised byproduct of reconstruction routing" framing was defensible, and it
  still competes with unsupervised deconvolution. Archived; if revisited, run it only
  as a router interpretability check benchmarked against an established method, never
  as a new deconvolution claim.
- **Data-dependent phase boundary.** A "samples-per-organ crossover where specialists
  overtake pooling" was dropped: the crossover depends heavily on dataset, organ
  granularity, and gene space, so it does not generalize into a unifiable claim.

## Repository and Compute

- Local repo: `/Users/minggangli/Projects/nasa-rna-moe`
- Central persistent VM: `moe-reboot`
- Shelved human VM: `moe-reboot2` (ephemeral root disk)
- Shelved mouse VM: `moe-reboot-partial` (hostname `moe-reboot3`, ephemeral)
- Central paths `data/archs4`, `checkpoints`, and `results` use the persistent
  `/media/volume/moe-reboot` volume.
- Training runs inside VM tmux. Never launch long work through a bare SSH shell.

## Archived Milestones

- Migrated the project from the `sp26_nasa` monorepo to a standalone repository
  and Jetstream A100 instances.
- Rebuilt the shared canonical human/mouse vocabulary (15,448 genes), downloaded
  ARCHS4 v11 H5 matrices, and generated V2 5k datasets.
- Trained shared-vocabulary 5k human, mouse, and mixed experts.
- Diagnosed the original MoE failure modes: incompatible vocabularies, narrow
  expert generalization, and almost no routing ceiling on mouse-only OSDR.
- Built a balanced 667-sample ARCHS4 human+mouse holdout and launched V3 20k
  human, mouse, and mixed scale-up runs.
- Commit `10a5e0e` backs up the corrected evaluation and automation code on
  `origin/main`.

## Why the Old Balanced Evaluation Is Invalid

Do not use the previously reported balanced-ARCHS4 `+0.0031` headroom or `0.686`
gene-mean result. The old evaluator:

- fed raw TPM into models trained on `log1p(TPM)`;
- tuned a fixed blend on the samples used for reporting;
- derived the gene-mean baseline from the test cohort;
- labeled a hard expert selector as the oracle even though a soft convex gate
  has a higher ceiling;
- used sample-weighted summaries despite large GEO study-size imbalance.

The current experiment exists to replace, not refine, those numbers.

## Corrected Frozen Protocol

### Cohorts

- **Full diagnostic:** 667 samples, 331 human / 336 mouse. Ordered sample-ID
  SHA256: `84c607dd83f93964430877f572291836fddd7315dd4f7eae3bcbf12f70fc0d65`.
  It is sample-disjoint but overlaps training GEO series, so it is not an
  unseen-study OOD cohort.
- **Strict sensitivity:** reconstructed every V2/V3 train+validation split and
  excluded the global union of whitespace-tokenized GEO series. Remaining: 103
  samples, 50 human / 53 mouse. Ordered SHA256:
  `e52a695f5e518be24803dcb1fba266c7a67b7d4696520dba35466f5f38da2b18`.

### Evaluation

- Explicit raw-TPM validation followed by exactly one `log1p` transform.
- Training-matched 30% mask rate and one deterministic shared mask artifact.
- Connected GEO-series components remain together across cross-validation folds.
- Out-of-fold fixed blend and true-species metadata hard/soft routers.
- Separate hard Pearson oracle, hard MSE oracle, and exact per-sample soft
  convex MSE oracle.
- Exact mixed-model training-row global and species gene means; no test-derived
  baseline.
- Primary estimate: equal study weight within species, then equal species
  weight. Confidence intervals use paired clustered bootstrap.
- Cross-scale comparison requires identical sample order, folds, common genes,
  masks, and sample filters. Cross-scale residual-Pearson differences are not
  reported because 5k and 20k have different train-derived centering profiles.

### Interpretation Guardrails

- The true-species soft router is a metadata-conditioned ceiling, not a learned
  blind gate for RNA-seq with unknown species or organ. `train_moe.py` is only an
  older softmax proof of concept and is not part of the corrected overnight path.
- Beating the one pooled `mixed` expert measures ensemble benefit. Adaptive MoE
  usefulness requires the metadata soft router to beat the out-of-fold fixed
  blend on strict 20k: positive absolute-MSE CI plus at least 3% relative MSE
  reduction is promising; at least 5% plus positive residual-Pearson CI is
  practically convincing. The soft oracle must also clear 3% to establish a
  meaningful routing ceiling.
- The pooled mixed model is not parameter, training-exposure, or inference-cost
  matched to a three-model ensemble.
- The strict cohort is cleaner but only 103 studies; wide intervals are expected.
- The current mixed V3 run inherited species-contiguous row-group batch order.
  A weak mixed result cannot by itself establish that MoE fails. Correcting and
  retraining that control is the first follow-up before a definitive claim.

## Validated Artifacts

- Current local suite: all 105 test functions pass, including utility-axis discovery,
  fixed hard-partition training/evaluation, packed-bank integration, utility-axis
  decision branches, latent-axis training/evaluation,
  label-recovery normalization/tiering,
  exact extraction, deterministic
  manifest training, balanced random controls, prediction-cache/mask identity,
  target-hidden multiclass routing, decision branches, smoke-launcher guards,
  adaptive-usefulness thresholds, and organ-manifest invariants. Python and shell
  syntax checks and `git diff --check` pass.
- Versioned result summaries:
  `artifacts/stage0_blind_gate/report.json` and
  `artifacts/stage1_organ_pilot/`.
- Local and central evaluator source SHA256 values match.
- Real 5k and 20k snapshots load through the final evaluator with 15,448 genes,
  `log1p_tpm`, mask ratio `0.3`, and mask token `-10`.
- 5k exact mean: 4,000 train rows (2,024 human / 1,976 mouse), artifact SHA256
  `2cef96f9cd0eb52c2e0ee527183880d86fce6e300c82350d7f7f5282b533fd77`.
- 20k exact mean: 16,000 train rows (7,989 human / 8,011 mouse), artifact SHA256
  `35bfe19a9a5d4f3c84279cdb88219e1720384080169ae658a64d332ed56ad51f`.

Selected 5k checkpoint MD5s, identical locally and on `moe-reboot`:

- human: `9de5e05bc66efd253b50063bf3810a90`, epoch 30, val `0.4290946`
- mouse: `a8276b020808a08eeabf581333a7b448`, epoch 19, val `0.5165973`
- mixed: `fdea7d4d16e4f0e6d58ab152a8c83edb`, epoch 20, val `0.8046928`

Pre-completion 20k snapshots are checksum-verified on the Mac and central
persistent storage, so completed training hours are already recoverable:

- human epoch-13: `079aac312215539be8e259363912bd61`
- mouse epoch-14: `07d2714f85d2f2807bae3a82bc7b4227`
- mixed epoch-13: `2f11bc192701b006437d6997281715cc`

## Completed Overnight Automation

- All three final V3 checkpoints and metadata archives are checksum-verified on
  the Mac and persistent `moe-reboot` storage. Human and mouse workers are safe
  to shelve.
- Corrected 5k/20k full and strict evaluations completed, the copied bundle
  passed frozen hash/schema validation, and the timestamped report was generated.
- All backup/evaluation/report/Git watchers exited. Final markers include
  `ALL_SAFE_TO_SHELVE`, `EVALUATION_COMPLETE_AND_VALIDATED`, `REPORT_READY`, and
  `GIT_BACKUP_PUSHED`.
- The completed Stage 0 code, reports, and interpretation are pushed to
  `origin/main`.

### Genuine K4/K5 retraining launch checkpoint (2026-07-22)

The next adaptive-development run is frozen in
`artifacts/stage1_organ_k45_retraining/protocol.json`. It retrains the nominated
four-organ subset (brain, liver, skeletal muscle, skin; adipose pooled fallback)
against K5 under two prespecified views: equal per-expert active exposure (2,400
specialist rows/expert, 1,500 shared-schedule updates) and an equal active-adapter
exposure sensitivity (3,000 rows/expert, 1,875 updates). The latter is an
active-exposure/adapter-compute proxy, not equal end-to-end FLOPs. Three new
connected-study-atomic random K4 families and three reused K5 random families are
trained on the same train/calibration rows. K4/K5 shared organ adapters use exact
semantic initialization keys, and full-run exposure deviation is fail-fast capped at
5%.

The result remains development-only and cannot repair the earlier organ-fixed
averaging failure or authorize external test access. The evaluator keeps the frozen
3% point-estimate gates with positive clustered evidence, Holm families, paired K4
noninferiority bounds, and explicit adaptive branches: `k4_robust` nominates the
lower-exposure K4-EPE artifact; `k4_budget_dependent` nominates only the active-total
sensitivity; `k4_efficient` covers EPE-only support; `k5_retained` is a conservative
default when K4 is not noninferior; and `no_supported_split` requires all three
organ candidates to fail. No branch is a biological confirmation.

Implementation commit `191192e` (workflow-resume fix `baa1acf`) is pushed to
`origin/main`; the exact production tree plus wrapper fix is deployed at
`/home/exouser/nasa-rna-moe-191192e` on `moe-reboot`. The frozen protocol hash is
`77dd4d780b2412b043f6f9c01778b043ca1b747fbf79836d82fbce7da791b079`.
Preparation completed with train/calibration counts 1,815/842 and partition
manifest hash `09c45edc5dd6389020495f8fd4718995cd82ee7828197a96c0fa44ef46e98bf2`.
The all-12-axis two-update smoke completed at 05:43 UTC with `mechanical_only=true`,
no test access, and exact shared K5/K4-EPE brain/liver/skeletal-muscle/skin expert
state hashes. Full seed 17/42/101 training is now running in tmux session
`organ_k45_baa1acf`; calibration evaluation follows automatically after all banks
complete. No effect estimate has been inspected.

### Genuine K4/K5 retraining result (completed 2026-07-22)

The development-only K45 workflow completed cleanly at 09:27:44 UTC under
`/media/volume/moe-reboot/results/stage1_organ_k45_retraining_191192e`. All three
training seeds, all 12 banks per seed, preparation, smoke, calibration evaluation, and
technical gates completed with no test access. The frozen branch is `k4_robust`; the
single candidate for final fitting is `k4_epe` (brain, liver, skeletal muscle, and skin
adapters with adipose pooled fallback).

K4-EPE achieved 3.339% blind gain versus pooled, 3.983% true-dispatch gain versus
pooled, and at least 3.945% true-dispatch gain versus every assigned random K4 control.
Its relative-MSE penalty versus K5 was only 0.184%, with simultaneous one-sided 97.5%
upper bound 0.299% against the frozen 1% noninferiority margin. Both K4 arms and K5
passed their development gates, so K4-EPE was chosen for its lower active exposure and
one fewer deployed expert, not because it had the numerically lowest MSE. This is a
development nomination, not independent confirmation and not a repair or erasure of
the earlier organ-fixed-averaging failure.

The evidence report SHA256 is
`4733d3eaab205d7421577d43460bf3b15a9a98803cdcaf8b040526c859049d1b`; decision-score
SHA256 is `70ecb74de141a89fc885ef457c3cfda42dcde12596cdfa551037953cad77ae8b`.
The exact 229-file, 44 MB result has a portable checksum manifest SHA256
`f287a6a83f39708f595cd59cbeec9abb3e82fff69ac49390d568644a6c58c27b`, verified both
on `moe-reboot` and in `backups/stage1_organ_k45_retraining_191192e/` on the Mac.

### Stage 1 K4 final-refit checkpoint (2026-07-22)

The complete decision history, failed controls, K-search interpretation, selected
parameters, hash ledger, final-fitting contract, and future external decision tree are
recorded in `docs/stage1-k4-final-refit.md`. The machine-readable refit protocol is
`artifacts/stage1_k4_final_refit/protocol.json` (SHA256
`718f4a876ba641e53aaff3ad75db8c70c727db0a086477b13c17487672cbb85b`).

The final fitting pool is exactly the frozen 1,815 balanced training rows plus 842
calibration rows (2,657 total). The previously inspected internal test remains excluded.
The pooled trunk stays frozen. For seeds 17/42/101, the refit trains from-scratch
dimension-64 adapters for one K4 organ bank, the exact three K45 study-atomic random K4
assignments, and one single-adapter pooled-residual control. All banks share a
deterministic 12,000-draw organ-then-sample balanced stream, batch size 8, 1,500 fixed
updates, LR 0.001, weight decay 0.01, 30% masks, cosine scheduling, and final-update-only
checkpointing. No calibration efficacy artifact, early stopping, best seed, or best
checkpoint is permitted. A five-class target-hidden router is refit on all 2,657 rows;
random deployment mappings are frozen beforehand from the completed held-out K45
calibration caches.

The real metadata preflight reproduced all 2,657 rows and exact frozen random labels.
For every training seed the proposed schedule covers every fitting row, gives exactly
2,400 draws to each organ role, and keeps each random expert within the frozen 5%
exposure bound (worst observed 3.83%). The final partition manifest is deterministic
with VM-runtime SHA256 `c6173aa4c7d5e8d62923a046c521a45a6e734f5f83017003b68f4afeb06261ba`.
The implementation includes fail-closed manifest/mapping/router/candidate freezers,
exposure ledgers, a metric-free final-refit trainer mode, a two-update real-data smoke,
and persistent-VM orchestration. External confirmation remains a later one-time run on
new study-disjoint data; K5 and K4-total may not be reopened on that lockbox.

A final adversarial audit then caught that the earlier loader still opened the
historical combined manifest/expression container before selecting the 2,657 fitting
rows. No test row reached training, but this did not justify the stronger physical
firewall claim. Launch was paused. A new 160 MB development-only expression artifact
was extracted directly from ARCHS4 H5 using only the frozen K45 train+calibration
manifest and verified on `moe-reboot` at
`/media/volume/moe-reboot/results/stage1_k4_final_refit_development_data_v1`.
Its expression SHA256 is
`74ee6438a32bf62c0227af4a3e73f853697b95e8bea80d844cabd67f261c7df0`, firewall-report
SHA256 is `d26edcbc9cdee9c809c0a56e999bc7ebd7a6b473855cd3741df2d6c9d77cca36`, and verified
relative checksum-manifest SHA256 is
`5bcd0c2973aecd7ac1ab119cddf37fd35b674b7a1c4f68b366449260c10c1ee2`.
The refrozen protocol and workflow forbid the combined container at runtime, bind the
full clean Git commit, serialize every ordered draw and per-draw mask seed, cross-check
all exposure/schedule hashes, and write the terminal completion marker last.

The repaired implementation passed three independent launch audits and the focused
integrated test suite, then was committed and pushed as
`e8c0383fd1833f180f26af56f09e83a5b3f676d9`. A complete Git bundle was checksum-verified
and cloned on `moe-reboot` into the new clean detached checkout
`/home/exouser/nasa-rna-moe-e8c0383`; the older dirty VM checkout was left untouched.
The production workflow ran in tmux session `stage1_k4_final_e8c0383` with persistent
result root
`/media/volume/moe-reboot/results/stage1_k4_final_refit_e8c0383`. Preflight,
development-only preparation, and the all-five-bank two-update smoke passed; the smoke
wrote `SMOKE_COMPLETE` at 2026-07-22T20:27:59Z with finite losses and no test or
external access. Full seed 17 started at 2026-07-22T20:28:02Z. All three 1,500-update
seeds, the target-hidden router refit, portable candidate freeze, and full checksum
validation completed at 2026-07-22T22:16:41Z. This final fit emitted no internal
efficacy comparison.

The complete 333 MB, 184-file result was copied to
`backups/stage1_k4_final_refit_e8c0383/`. Its relative `FULL_SHA256SUMS` validates both
on persistent `moe-reboot` storage and independently on the Mac; that manifest's SHA256
is `db17084f813abd19dd11297570a2befc48aa9c7d93f9755216780c3418f0aca0`. The portable
candidate validator passes against code commit
`e8c0383fd1833f180f26af56f09e83a5b3f676d9`. Candidate-manifest SHA256 is
`c941504037d885b74a1555d97109ff31ada9a60545b52e8c244fdccafe3ad9ee`; router-report
SHA256 is `2f5600eabe7a9c48af0f55b86beeea9a0fe6a629e5863fe5aea2257b36e16a15`.

### Post-refit external metadata scout (2026-07-22)

The next operation is intentionally metadata-only, not external evaluation. The pinned
scouting protocol is `artifacts/stage1_k4_external_scout/protocol.json` (SHA256
`1ab183ba9d31851a2f605d51d29eb9a282b7581b63a56e6eacdd9693276dc1c4`). It binds the
current ARCHS4 human gene-level object by URL, 62,257,385,524-byte length, multipart
ETag, and 2026-07-07 Last-Modified value. Remote HDF5 inspection observed 1,098,771
human samples and 67,186 genes, versus 441,356 samples in the development-era v11
snapshot created 2021-11-13.

The scout reads only HDF5 metadata through HTTP range requests. Before label recovery it
excludes every v11 accession and any row sharing any v11 GEO-series token. The v11
accession-order SHA256 is
`784035aa00284f2a8c0c500a391f88d9c6986621c22dd7f622a06284d731eba0`; the independently
matched accession/series mapping SHA256 is
`ffce20e908770672571d3e75755cb00643c330da8899424255b6a245e9936523`. Remaining bulk
RNA-seq metadata is conservatively classified for adipose, brain, liver, skeletal
muscle, and skin. The output will report whether each organ has at least five, preferably
eight, temporally new connected studies and will produce 50 deterministic review rows
per organ. It is not a frozen lockbox and performs no expression access or efficacy
scoring. Exact IDs may be frozen only after manual label review and publication,
BioProject, donor, connected-group, and near-duplicate audits.

The tested scout was committed and pushed as
`182207bbc85c30df80f17cd45784d5c87f8a52a7`, deployed from a clean detached checkout at
`/home/exouser/nasa-rna-moe-182207b`, and launched in tmux session
`stage1_k4_ext_scout_182207b`. Its persistent result root is
`/media/volume/moe-reboot/results/stage1_k4_external_scout_182207b`. The historical v11
metadata export completed, and the pinned current-object metadata range scan began at
2026-07-23T02:47:54Z. The scan logs ordered progress by 20,000-row chunks and remains
explicitly nonconfirmatory and expression-sealed.

### Mentor-directed GTEx V11 metadata intake (2026-07-23)

The mentor recommended GTEx as the healthy/non-diseased human bulk RNA-seq validation
resource, ARCHS4 as a cross-processing-pipeline robustness analysis, and TCGA only as
a disease-domain secondary analysis. GTEx is therefore frozen prospectively as
`secondary_donor_controlled_validation`; the existing 40-study ARCHS4 design remains
the planned multisource confirmation and the two datasets may not be merged after
effects are visible.

The official GTEx catalog now exposes V11. V11 adds no donors or samples relative to
V10, updates annotation to GENCODE 47, and provides an LCM-excluded RNASeQC bulk-count
object. Four open-access metadata/data-dictionary files were downloaded and pinned;
no expression object was downloaded or opened. The intake selects exact
`RNA:Total RNA` / `TruSeq.v1` target-tissue rows and excludes spinal cord, cultured
fibroblasts, liver LCM compartments, BMS/LCM rows, and other assay batches.

The historical Stage 1 manifest contains nine GTEx-derived ENCODE rows. Public ENCODE
aliases resolve their four donors as:

- `ENCDO271OUW` → `GTEX-1LVAN`
- `ENCDO451RUA` → `GTEX-1K2DA`
- `ENCDO793LXB` → `GTEX-1LGRB`
- `ENCDO845WKR` → `GTEX-1JKYN`

All four donors are excluded globally, removing 22 samples. The remaining provisional
pool contains 7,845 samples from 973 donors: adipose 1,472/878 samples/donors, brain
3,509/405, liver 304/284, skeletal muscle 961/892, and skin 1,599/908. The frozen
secondary estimator averages seeds within sample, samples/sites within donor and
organ, donors within organ, and then organs equally.

The metadata-only builder and firewall tests were committed as
`c6133358355429dc1b8f3e3d9c1a534cf365011c`; all 13 external-intake regression tests
pass. Protocol SHA256 is
`35ddc3506561f2427613af8acebb5facc9efd7bc88bb6a0afe3fd15a5c6beed6`.
The verified local result is `backups/stage1_k4_gtex_intake_c613335/`, with
checksum-manifest SHA256
`1eaf59d6caf84babdd0cb765551b85ded2e9b2f20f789c9cf908dd57b8ee0582`,
intake-report SHA256
`c966576ba84c47c9c42627b1c4e7094c7d5a3acb5b83d521e90204d5f5b194e2`,
and provisional-cohort SHA256
`a88aa72acf4d40702b1b0ad3d13c4767308aa6ebf5e93bbb1440651696b04308`.

The result explicitly states `expression_file_downloaded=false`,
`expression_values_read=false`, `external_lockbox_frozen=false`, and
`ready_for_expression_access=false`. Next gates are a synthetic/historical-data-tested
V11-count-to-canonical-TPM extractor, donor-clustered evaluator, exact matrix-header
membership freeze, and a full ARCHS4-pretraining donor/near-duplicate overlap audit.
