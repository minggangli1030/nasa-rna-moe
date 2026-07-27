# NASA RNA MoE: current canonical status

**Updated:** 2026-07-27 13:51 PDT / 2026-07-27 20:51 UTC

Read this file first. It is the compact operational and scientific handoff. Use
`docs/stage1-k4-final-refit.md` for the full Stage 1 decision history and
`docs/stage-1-end-result.md` for the final Stage 1 synthesis. Use `progress.md` only
when older chronology or exact intermediate results are needed.

## Current state

- Stage 0 interspecies training and corrected evaluations are complete.
- Stage 1 development nominated K4-EPE: brain, liver, skeletal-muscle, and skin
  specialists with pooled fallback for adipose.
- The final train+calibration-only K4 refit is complete, frozen, checksummed, and
  independently backed up. It produced no internal efficacy comparison.
- The prespecified GTEx V11 secondary donor-controlled validation is complete. The
  frozen K4 candidate passed every gate on 6,795 samples from 930 donors.
- The metadata-only external-cohort feasibility scout completed successfully and
  found ample candidate study coverage for every target organ.
- The first 250-row metadata review **failed the automated eligibility gate**:
  nominal high-confidence labels still included cell models, non-bulk assays,
  diseased/tumor tissue, nonhuman samples, and active interventions. No cohort has
  been frozen.
- The conservative v3 resolver and donor/power audit are complete. They provide 40
  pending study decisions and 574 pending sample decisions; they are not an accepted
  cohort and have not opened expression.
- The audit passed the structural gate for drafting the final evaluator protocol, but
  not the manual-metadata, lockbox-freeze, or expression-access gates. Most donor keys
  remain title proxies rather than verified donor identities.
- The mentor recommended GTEx for non-diseased-tissue validation, ARCHS4 for a
  cross-processing robustness analysis, and TCGA only as a secondary disease-domain
  analysis.
- GTEx V11 intake, exact-header cohort sealing, extraction, frozen scoring, and
  donor-bootstrap evaluation are complete. The final cohort has 6,795 official
  `RNASEQ` samples from 930 donors after globally excluding four historical EN-TEx
  donors.
- True K4 reduced donor-balanced equal-organ MSE by 3.301% versus pooled (95% CI
  3.262%–3.341%); target-hidden blind K4 reduced it by 3.157% (95% CI
  3.113%–3.202%). Router accuracy was 98.03%, with 95.63% oracle-gain recovery.
- Every prespecified GTEx gate passed. The exact decision is
  `full_external_pass`.
- This is secondary donor-controlled evidence under one harmonized GTEx
  STAR/RNASeQC pipeline and postmortem/organ-donor regime, not multisource
  cross-study confirmation. That result remains frozen and was not altered to
  rescue or amplify the later GTEx-to-ARCHS4 extension.
- A prospective clean-to-heterogeneous extension is now authorized: train a new
  GTEx-only pooled/organ/random/router family and evaluate frozen candidates on
  staged, study-disjoint ARCHS4 cohorts. This preserves the completed result while
  making GTEx development data for the new candidate.
- The frozen metadata-only intersection selects eight organs:
  adipose, brain, colon, heart, liver, lung, skeletal muscle, and skin. The exact
  GTEx development cohort contains 9,195 exact-header samples from 938 globally
  donor-disjoint donors.
- The plan and frozen GTEx-development contract are
  `docs/gtex-to-archs4-training-plan.md` and
  `artifacts/stage1_gtex_to_archs4/protocol.json`. The organ inventory is
  `artifacts/stage1_gtex_to_archs4/organ_inventory.csv`.
- The K8 GTEx extractor and donor-disjoint, donor-atomic manifest builder are
  implemented. The focused extraction, cohort, inventory, and manifest suite passes
  22 tests. ARCHS4 expression remains sealed.
- The exact manifest is complete: 7,369 samples/750 donors in training and 1,826
  samples/188 donors in calibration, with zero donor crossover. A metric-free K8
  router refit and a coverage-complete real-data smoke fixture are implemented; the
  expanded focused suite passes 26 tests.
- Full K8 GTEx TPM extraction completed from clean detached commit
  `529c0c3a8d651b935b5e8e5f23d916de196749fa` under
  `/media/volume/moe-reboot/results/stage1_gtex_to_archs4_529c0c3`. It contains
  9,195 samples, 938 donors, and 15,448 genes; expression SHA256 is
  `ef5949975e8139d0a29f6fca003da6098a308677f2ab34d7f589851b5ea36550`.
- The first real-data smoke caught and corrected a wide-parquet loader scaling bug
  before any model metric was produced. The corrected loader reduced the 235×15,448
  fixture load from minutes to 0.29 seconds while preserving exact values/order.
- The corrected pooled/K8/random/pooled-adapter/router real-data smoke passed from
  clean commit `98e2cbab7e94f101feb33e83cff0712834c38ee3`.
- Full three-seed GTEx-only training completed at 2026-07-27T05:38:49Z under
  `/media/volume/moe-reboot/results/stage1_gtex_to_archs4_training_98e2cba`.
  Every pooled trunk completed 7,350 updates; every seed completed the organ K8,
  three random K8, and pooled-adapter banks; and the metric-free target-hidden
  router completed without ARCHS4 or test access.
- The remote `FULL_SHA256SUMS` passes, and the complete 1.8 GB bundle is independently
  checksum-verified at
  `backups/stage1_gtex_to_archs4_training_98e2cba/`. The checksum-manifest SHA256 is
  `009920173cff2c0eaa9d880c8bc1fbe4ffbe61a9ffc9df5ba8c6795cf90dcc7b`.
  All 281 repository tests pass when pytest capture is disabled; the default capture
  mode trips a macOS sandbox/Arrow stderr-descriptor issue in one otherwise-passing
  metadata test.
- The current post-v11 K8 metadata universe is pinned at 10,041 samples from 391
  unique connected study groups. Official GEO Series metadata was fetched for 160
  top-ranked organ/group rows without accessing supplementary expression files.
  This confirmed that automated priority labels are unsafe: nominal clean candidates
  include cell models, interventions, tumors, and disease-context controls.
- A conservative K8 shortlist now resolves exactly 64 connected study groups and 827
  sample accessions: eight groups for each of adipose, brain, colon, heart, liver,
  lung, skeletal muscle, and skin. Selectors retain only explicit healthy/control,
  untreated/baseline, or transparently labeled disease-context control tissue and
  remove the known duplicate VUHD073 lung library.
- The metadata-only K8 donor/power audit passes every structural readiness check:
  no repeated sample IDs, no duplicate derived within-group donor keys, no explicit
  cross-group donor/BioSample identifier reuse, and all 64 study clusters present.
  The exact one-sided sign diagnostic rejects at 41 positive studies of 64
  (`alpha=0.025`, achieved null tail 0.01638). Most donor identities are still
  documented title proxies, not verified donor IDs.
- The production K8 lockbox pipeline is now implemented at
  `73f9bd1d6fff097811f879766e9a68a05aebe850`: exact membership freeze,
  one-time extractor, deterministic all-seed scorer, equal-organ/equal-study
  evaluator, protocol freezer, and hash-verified two-host launcher. Its focused
  fail-closed suite passes 11 tests.
- The frozen candidate ledger SHA256 is
  `1bd0e2de4b45f3e1ba4cfe4ca898db9f9b3ef5e0b60fd64ccfcf80bbb3e1a2a8`;
  the GTEx-calibration-only random-control mapping SHA256 is
  `4386f372002dc14591d7e2a0203bf794bacf39cacc50736abc339b89a4f99496`.
  Every prespecified seed is required and best-seed selection is forbidden.
- The 62,257,385,524-byte current human H5 completed locally with SHA256
  `284855959248f249ddef5a9a5b780c72b86ef99240ed1403f08b01609778ed56`.
  The final lockbox protocol is frozen with SHA256
  `dd73e11f39c02b9a5375f24e098c8118260ccac35f3a608a23e90a0eb76e9bfc`,
  and exact membership froze at 827 samples from 64 connected studies.
- The first real expression access failed closed at the prespecified 14,000-nonzero
  QC floor. Five liver samples from GSE277232 had only 19–304 nonzero genes, and one
  lung sample from GSE227136 had 11,235. The extractor published zero expression
  rows and no efficacy metric existed at that point.
- The user explicitly authorized a versioned QC amendment: exclude exactly those six
  failures, add no replacements, retain the 14,000-gene threshold, perform no
  fine-tuning or best-seed selection, and label the result
  `post_access_qc_amended_external_evaluation`. The amended cohort retains all eight
  organs, 821 samples, and 63 connected studies; liver retains 42 passing samples
  from seven studies and every other organ retains eight studies.
- The amended extraction and all-three-seed scoring completed. The evaluator then
  failed closed before producing metrics because its cache loader tried to validate
  three hash-bound ancillary arrays it had not loaded. The caches independently
  passed their hashes. A code-only correction at
  `6822c453637b2b3fe5c8bd50e23060bd13a9b4a6` now explicitly binds the immutable
  caches to their source protocol; no cache, membership, QC rule, checkpoint, or
  scientific estimand changed.
- The corrected post-access QC-amended external evaluation is complete. Across all
  prespecified seeds, pooled MSE was 0.909261, true-organ K8 was 0.874738 (3.797%
  lower), target-hidden hard routing was 0.876228 (3.633% lower), and target-hidden
  soft routing was 0.875840 (3.676% lower). Every seed improved for all three K8
  conditions; each paired study bootstrap CI versus pooled excluded zero. The pooled
  adapter and all three random K8 controls were effectively neutral on average.
- Nothing is currently training locally or on the GPU VM. The amended evaluation is
  complete; Stage 2 protocol/scheduler implementation and presentation drafting are
  active locally. A new untouched lockbox remains the appropriate future route to a
  pristine preregistered confirmation.
- The preliminary result is already available ahead of the Thursday-morning
  deadline. Presentation preparation is now the active operational task. The
  content draft is `presentation/2026-07-30-biweekly-draft.md`; an automated
  readiness check runs every two hours from 08:00 through 22:00 PDT and ends
  Thursday morning after the rendered deck, claim audit, and speaking notes are
  verified.

The strongest defensible conclusion is now: organ identity is the strongest tested
conditional specialization axis; target-hidden conditional routing has replicated
against pooled and capacity-matched controls in GTEx and in a multisource ARCHS4
evaluation. The ARCHS4 result is supportive cross-study evidence, but because six QC
failures were excluded after first expression access it is explicitly not a pristine
preregistered confirmation. A new untouched lockbox is still required for that
stronger claim.

## GTEx-to-ARCHS4 post-access QC-amended evaluation

The final evaluator-correction protocol SHA256 is
`c5aaed24de62347747e815c02e0cda7793adc15c33b0b67f841c7c6896b48632`.
It binds the unchanged score caches created under source protocol SHA256
`8fce7b949cad0049def8bf1bb7383f871bfab34c825c8f85526acc6894042763`.
The primary estimand gives equal weight to organs and then connected studies within
organ; uncertainty is a paired 10,000-repetition connected-study bootstrap within
organ.

| Condition | Equal-organ/study MSE | Reduction vs pooled |
| --- | ---: | ---: |
| pooled | 0.909261 | — |
| true-organ K8 | 0.874738 | 3.797% |
| target-hidden hard K8 | 0.876228 | 3.633% |
| target-hidden soft K8 | 0.875840 | 3.676% |
| pooled residual adapter | 0.909304 | -0.005% |
| mean of three random K8 axes | 0.909273 | -0.001% |

Per-seed true-organ reductions were 2.778%, 3.243%, and 5.384%; hard-router
reductions were 2.619%, 3.067%, and 5.226%; and soft-router reductions were 2.649%,
3.103%, and 5.289% for seeds 17, 42, and 101, respectively. No seed was selected.
The report SHA256 is
`b4a77268c642709b2ae33a0a4d95f38bb9029734f5ffffd0ba1d3f9be1fc15cb`;
the compact score-cache report SHA256 is
`8a7d3d7c78791ff29cd1fc96d2b277e437d18f15bb715de9ebd1b216936aef99`.

## Stage 1 synthesis and Stage 2 direction

The Stage 1 synthesis is:

> Organ-specialized models beat pooled whether dispatch uses the revealed organ, a
> hard target-hidden route, or a soft target-hidden route.

For the new reverse-direction evaluation, those gains are 3.797%, 3.633%, and
3.676%. All three conditions are positive in every prespecified seed, their
study-bootstrap intervals versus pooled exclude zero, and their random-K8 and
pooled-adapter controls are neutral. Similar 3–4% effects appear in the earlier
ARCHS4 development setup and the pristine ARCHS4-to-GTEx validation. The supported
language is therefore **robust across routing form, seed, setup, and
training/evaluation direction, with positive study-balanced evidence**. It is not
invariant in every individual study or every organ-by-seed cell.

Stage 2 remains centered on the organ experts. Its primary objective is to determine
what functional corrections different organ experts learn and whether those
differences predict directed cross-organ transfer or interference on held-out
studies. Label-free routing entered the earlier plan as a novelty extension linking a
co-routing map to a transfer map; it was never evidence that organ identity should be
discarded. Because the completed label-free pilots failed their utility and
anti-confound gates, de novo label-free discovery is now optional and secondary.

The current plan is `docs/stage2-organ-expert-mechanism-plan.md`: first audit frozen
expert residuals/pathways, then measure a controlled directed organ-to-organ transfer
matrix, then test whether expert/router structure predicts held-out transfer. The
matrix now separates two estimands: A1500 versus A750+B750 tests use of a fixed
compute budget, while A1500 versus A1500+B750 tests added donor information at fixed
recipient exposure. Random-auxiliary and A2250 controls distinguish organ identity
from generic heterogeneity and extra updates. Only after those phases pass may a
within-organ or label-free extension proceed.

The practical Stage 2 objective is to learn which organs should share training
information and which should remain isolated. This can guide data selection for
low-resource organs, prevent negative transfer, and inform hierarchical expert
sharing. The underexplored contribution is the prospective link among independently
validated expert signatures, controlled directed transfer, and input-only router
compatibility on held-out studies; none of those individual methods is claimed as new
by itself.

The first development-only Stage 2 audit is complete from implementation commit
`9fad92a`. It uses only the existing GTEx calibration score caches: 1,826 samples
from 188 held-out GTEx donors, with no ARCHS4 expression access or model fitting.
When each frozen expert is cross-dispatched to every recipient organ, the correctly
named expert ranks first for all eight recipient organs after averaging all three
seeds. Every off-diagonal expert is harmful on average; 23 of 24 named
organ-by-seed cells are positive, versus only 2 of 168 off-diagonal seed cells.
This is strong development evidence of distinct organ-aligned expert function, not
the causal effect of adding donor-organ training data. The controlled transfer
experiment remains separate.

The deterministic transfer-schedule compiler is implemented and focused tests pass.
The final schedule implementation at commit `d3eb358` matches each organ's
deterministic donor/sample sequence and source-local mask index across arms and
enforces the frozen source ratio within every six-sample batch. The exact GTEx
development manifest SHA256 is
`d37023f08fabf5059a886501ab416feb5caabbce9aa719086832f6d2579ed2e6`.
The compiled substitution design at
`/media/volume/moe-reboot/results/stage2_directed_transfer_d3eb358/substitution_schedules`
contains 60 arms and 90,000 draws: 8 recipient-only arms, 28 unordered organ pairs
(56 directed evaluation effects), and 24 donor-atomic random-auxiliary controls.
The training-schedule SHA256 is
`6390071cdc463a12e2bbf533b931235c17c6a40d75aacc61dbbd881b8c46ed20`;
the arm-definition SHA256 is
`b4cae61170614a83bc9fc2a7222a0f824557985bba8130c91750cddc963c8774`.

The schedule-bound K1 trainer is implemented at commit `00e37e3`; the combined
focused Stage 2 suite passes 12 tests. A real-data mechanical GPU smoke completed
two arms and two batches per arm in 161 seconds, including frozen-trunk loading,
identical semantic initialization, scheduled masks, checkpoint publication, and
calibration score-cache publication. Those two-batch outputs are mechanical only and
must not be interpreted as efficacy. The next gates are the aggregate evaluator,
prospective additive-edge freeze, and a full all-three-seed launcher.

This first transfer matrix is donor-disjoint GTEx development evidence, not
study-disjoint confirmation: GTEx does not provide independent contributing studies.
Any final “held-out studies” claim requires a new untouched multisource lockbox after
the development protocol and predictions are frozen.

## Thursday presentation readiness plan

Decision rule: the completed amended evaluation is the only new efficacy result to
enter the deck. No additional ARCHS4 analysis may tune the story or promote the
result to pristine confirmation. Organ-level heterogeneity may be described only as
diagnostic context; it cannot be used to select organs, seeds, or conditions.

| Deadline | Required state | Status |
| --- | --- | --- |
| Sunday | preliminary result, bounded claim, content outline | complete |
| Monday | complete HTML slide draft and primary-result figures | next |
| Tuesday | numeric cross-check against frozen JSON and visual QA | pending |
| Wednesday | final speaking notes, likely questions, rehearsal pass | pending |
| Thursday 08:00 PDT | presentation-ready package and readiness summary | pending |

The deck must always show the 821-sample/63-study amended cohort, all three retained
seeds, the neutral pooled-adapter/random controls, and the post-access QC-amended
label. It must not claim universal per-organ improvement, verified ARCHS4 donor
identity, downstream spaceflight benefit, or clinical validity.

## GTEx V11 external-validation result

The run used clean detached implementation commit
`6cc8095431bf422926496a6c1dfea3b6cdeb9eb3`, protocol SHA256
`295a38f70ded3059ccce4a4308978921ace76d00ee72608b84042483c141115c`,
and frozen candidate-manifest SHA256
`c941504037d885b74a1555d97109ff31ada9a60545b52e8c244fdccafe3ad9ee`.
No external target contributed to fitting, checkpoint selection, cohort rescue, or
protocol modification.

| Condition | Donor-balanced equal-organ MSE | Reduction vs pooled | 95% CI |
| --- | ---: | ---: | ---: |
| pooled | 0.955366 | — | — |
| true K4 | 0.923828 | 3.301% | 3.262%–3.341% |
| target-hidden blind K4 | 0.925205 | 3.157% | 3.113%–3.202% |

The estimator averaged seeds within sample, samples/sites within donor and organ,
donors within organ, and organs equally. Uncertainty used 10,000 paired global-donor
bootstrap draws preserving cross-organ donor correlation. Both primary one-sided
bootstrap p-values were `0.00009999`. Blind routing improved residual Pearson by
`0.009614` (95% CI `0.009220`–`0.010003`). All three seeds were positive, all active
organ effects were nonnegative, and the true/blind conditions passed every matched
random and pooled-adapter control.

Canonical artifacts:

- tracked summary:
  `artifacts/stage1_k4_gtex_evaluation/result_summary.json`
- frozen protocol:
  `artifacts/stage1_k4_gtex_evaluation/protocol.json`
- remote result:
  `/media/volume/moe-reboot/results/stage1_k4_gtex_v11_b9a15f2`
- local checksum-verified backup:
  `backups/stage1_k4_gtex_v11_6cc8095/`
- evaluation-report SHA256:
  `c90adfee81aa31241502d69bfdf1e92d41d66574e5f9a1c5bdd2b9877d1e38c6`
- compact score-cache SHA256:
  `d5c82fab815fca50487c520aa32faccf5660d972a23c18f571d828f18d8395b0`

## Frozen Stage 1 candidate

Architecture and fit contract:

- pooled trunk frozen from the Stage 1 pooled checkpoint;
- four independent dimension-64 residual adapters for brain, liver, skeletal muscle,
  and skin;
- adipose dispatches to the pooled fallback;
- target-hidden five-class observed-input router;
- training seeds 17, 42, and 101 retained with no best-seed selection;
- 2,657 development-only rows: 1,815 training plus 842 calibration;
- exactly 1,500 updates per seed, batch size 8, 12,000 deterministic balanced draws;
- controls: three study-atomic random K4 banks plus one pooled residual adapter; and
- no old-test access, external access, early stopping, or internal efficacy scoring.

Final-refit implementation commit:
`e8c0383fd1833f180f26af56f09e83a5b3f676d9`.

Canonical artifacts:

- VM result:
  `/media/volume/moe-reboot/results/stage1_k4_final_refit_e8c0383`
- local verified backup:
  `backups/stage1_k4_final_refit_e8c0383/`
- full checksum-manifest SHA256:
  `db17084f813abd19dd11297570a2befc48aa9c7d93f9755216780c3418f0aca0`
- candidate-manifest SHA256:
  `c941504037d885b74a1555d97109ff31ada9a60545b52e8c244fdccafe3ad9ee`
- router-report SHA256:
  `2f5600eabe7a9c48af0f55b86beeea9a0fe6a629e5863fe5aea2257b36e16a15`

Completion markers include `FINAL_REFIT_COMPLETE`, `ROUTER_FROZEN`,
`FINAL_CANDIDATE_FROZEN`, and `READY_FOR_VERIFIED_BACKUP`. The portable-candidate
validator and the full 184-file checksum manifest pass centrally and on the Mac.

## Completed metadata-only external scout

Purpose: determine whether an untouched, multisource, post-v11 cohort can cover all
five organs before any expression access.

Production code commit:
`182207bbc85c30df80f17cd45784d5c87f8a52a7`.

Runtime:

- clean checkout: `/home/exouser/nasa-rna-moe-182207b`
- tmux: `stage1_k4_ext_scout_182207b`
- result root:
  `/media/volume/moe-reboot/results/stage1_k4_external_scout_182207b`
- protocol: `artifacts/stage1_k4_external_scout/protocol.json`
- protocol SHA256:
  `1ab183ba9d31851a2f605d51d29eb9a282b7581b63a56e6eacdd9693276dc1c4`

The scout reads only `meta/info` and `meta/samples` from the pinned current ARCHS4
human HDF5 object through HTTP byte ranges. The 62,257,385,524-byte object is bound by
its ETag and 2026-07-07 Last-Modified value. Its metadata describes 1,098,771 human
samples. `data/expression` is never indexed.

Before organ classification, the scout excludes:

- every accession present in ARCHS4 v11; and
- every sample sharing any GEO-series token with v11.

Historical firewall hashes:

- ordered v11 accession SHA256:
  `784035aa00284f2a8c0c500a391f88d9c6986621c22dd7f622a06284d731eba0`
- v11 accession/series mapping SHA256:
  `ffce20e908770672571d3e75755cb00643c330da8899424255b6a245e9936523`

The scout completed at 2026-07-23 03:53:11 UTC. All checksum entries pass on the VM
and in the local verified backup at
`backups/stage1_k4_external_scout_182207b/`.

It found 13,845 candidate samples across 457 connected series groups:

| Organ | Candidate samples | Series groups | Post-cutoff samples | Post-cutoff series |
| --- | ---: | ---: | ---: | ---: |
| adipose | 1,577 | 55 | 1,047 | 44 |
| brain | 2,537 | 102 | 2,225 | 82 |
| liver | 2,631 | 100 | 2,154 | 78 |
| skeletal muscle | 2,981 | 65 | 2,488 | 50 |
| skin | 4,119 | 144 | 3,296 | 115 |

Every organ clears both the minimum five-series and preferred eight-series feasibility
thresholds after the v11 sample-and-series firewall. The largest connected group is
only 6.98%–13.19% of each organ pool, so no organ is provisionally dominated by one
study. The output includes exactly 50 deterministic manual-review rows per organ
(250 total). It is explicitly **not** a frozen external lockbox and computes no model
score.

Scout report SHA256:
`68ea1bdabb57c63ecea5d8636873e628db606c59b76bd75a94462b216a737786`.

### Round-1 review outcome and repair

Manual inspection showed that the generic organ-label classifier is not precise enough
to select an external cohort. Representative failures included adipose-derived stem
cells, HepG2/stellate/immune cells, Ribo-seq and single-nucleus/spatial assays, mouse
liver, tumor-adjacent tissue, and disease or treatment cohorts whose abbreviations
escaped the original vocabulary. After expanding the parser and exclusion vocabulary,
110 of the 250 nominally eligible round-1 rows are now conservatively downgraded:
adipose 20/50, brain 24/50, liver 30/50, skeletal muscle 9/50, and skin 27/50.
These are triage counts, not an efficacy result or a final precision estimate.

The repair therefore does not try to prove that another regex list is a curator.
`evaluation/build_stage1_k4_external_curation.py` builds a connected-study workbook
with positive healthy/control markers, conservative exclusion/context flags, GEO
links, and explicit blank review fields. Automated A/B/excluded values only prioritize
manual work and can never accept a study or freeze a sample.

Full-pool preflight produced 466 organ-by-connected-study rows (457 unique connected
groups). Strict all-sample priority-A counts are adipose 2, brain 8, liver 12,
skeletal muscle 4, and skin 10; the remaining viable groups are priority B and require
manual review. This confirms that broad feasibility remains, while also showing why
study-level curation—not automatic label recovery—is the current bottleneck.

The production workbook completed from isolated code commit
`f307108a5d3e9325b014d9171aa6522ebc6751bc` at 2026-07-23 05:24:34 UTC:

- VM result:
  `/media/volume/moe-reboot/results/stage1_k4_external_curation_f307108`
- local verified backup:
  `backups/stage1_k4_external_curation_f307108/`
- workbook SHA256:
  `965b4a2f40f28d94a1de7317fbaa4c97ae4014426195b287c125e92dc5c7b5e0`
- sample-triage SHA256:
  `b2645444af6ceb65df5d4b927057934ee9c4c37c3ab6912a978cf1a0568d7085`

Every checksum passes remotely and locally.

### Expanded GEO and exact-sample review

The GEO series-level review was expanded to the first 40 non-excluded connected
groups per organ: 200 organ/group rows and 226 pinned GEO series records. It reads
only public series title, summary, design, PubMed, BioProject, and sample count; it
does not request supplementary files, SRA objects, or expression.

- implementation commit:
  `a89e2e988e8e8e5467a56d16a85a5f173dd3dff6`
- VM result:
  `/media/volume/moe-reboot/results/stage1_k4_geo_review_a89e2e9`
- local verified backup:
  `backups/stage1_k4_geo_review_a89e2e9/`
- selected-study review SHA256:
  `19373eafa0e5d1fdf1127033a669c79232616adbe1d28fd26b6bd01c274cfc3b`
- GEO-series metadata SHA256:
  `9abf44b3a5f0d4511fd9636d2707a300f1206f7efa579a75a49f2c8ffa824edb`

Manual reading of the pinned designs produced a provisional eight-group shortlist
per organ. The review caught a likely cross-series donor reuse between adipose
`GSE306796` and `GSE287627`; the latter was removed and replaced before sample
resolution. This is evidence that GEO connected components alone do not establish
donor independence.

The current conservative v3 metadata-only resolver binds the source hashes, requires
post-v11 samples, rejects classifier-ineligible matches, and leaves all study,
sample, donor, and near-duplicate decisions pending. It resolved:

| Organ | Provisional studies | Provisional selector matches |
| --- | ---: | ---: |
| adipose | 8 | 61 |
| brain | 8 | 126 |
| liver | 8 | 47 |
| skeletal muscle | 8 | 263 |
| skin | 8 | 77 |

These 574 rows are a review workload, not the final analysis size. Ambiguous cases
such as technical/biological replicates, tissue regions, graft donors, and skin
compartments are explicitly marked unresolved.

The initial 601-row v1 result remains preserved for audit at the paths below, but it
is no longer the current review sheet:

- implementation commit:
  `8e6d95b66d4ee26e2b226ee6ddab839e712b9e24`
- shortlist SHA256:
  `e7569661edbccc7d0ad075a184851b969c019b12067c19a1458012d7aa1de3f8`
- VM result:
  `/media/volume/moe-reboot/results/stage1_k4_external_sample_review_8e6d95b`
- local verified backup:
  `backups/stage1_k4_external_sample_review_8e6d95b/`
- full checksum-manifest SHA256:
  `da0ff1b8e5ae5e4d49e3699e176d88037467bfde41627d2fedfd549960feaca3`
- provisional sample-review SHA256:
  `4b5dead31111c8ae80c3d079d6ee73db4da45e6a61d7cc1a4233ae9fb4dcd3e8`
- provisional study-review SHA256:
  `9c6712ccc9772de39388dd846f446db2391eb809695924854739ccc5f5605fb5`

All checksum entries pass on the VM and Mac. The report states
`expression_values_read=false`, `efficacy_scoring_performed=false`, and
`external_lockbox_frozen=false`.

### Liver reserve amendment

Publication/series review rejected provisional liver group `GSE304242`: its official
design centers on hepatic cell-model comparisons, while the three liver-RNA samples
do not provide defensible donor or health semantics for this strict cohort. The
rejection is preserved rather than silently relabeling those samples.

A targeted metadata-only reserve fetch pinned `GSE284901`, an ENCODE4 unreplicated
bulk total-RNA sample from the right lobe of one adult liver. ARCHS4 metadata gives
BioSample `SAMN45079858` and donor `ENCDO757VPQ`; hypertension is explicitly retained
as a non-hepatic comorbidity rather than calling this a nominally healthy donor.

- reserve-fetch implementation commit:
  `119ed2d0f12f391d28c20a0dd9ed54a5f1c4b573`
- reserve VM result:
  `/media/volume/moe-reboot/results/stage1_k4_geo_reserve_review_119ed2d`
- reserve local verified backup:
  `backups/stage1_k4_geo_reserve_review_119ed2d/`
- reserve selected-study SHA256:
  `9afb4067935f5602241f0d4355c8a052f72475d655607c981fbbb4ec6702cf84`

The amended v2 resolver replaces the three ambiguous `GSE304242` rows with exact
sample `GSM8693930`, reducing liver from 49 to 47 pending rows and the total from
601 to 599 without changing the eight-groups-per-organ review target.

- v2 implementation commit:
  `8734e5e1486713850ab71cb386b51cc785fbfef7`
- amendment SHA256:
  `6cd1451da17e2d5877de6617e22e31ff3e1c6e97877cb8890407038a828c75a8`
- v2 VM result:
  `/media/volume/moe-reboot/results/stage1_k4_external_sample_review_v2_8734e5e`
- v2 local verified backup:
  `backups/stage1_k4_external_sample_review_v2_8734e5e/`
- v2 full checksum-manifest SHA256:
  `a3f5a58122fd58acc5f0c9ba2a56898de8e1bad53f44d8b7b9669ee15765ddcc`
- v2 provisional sample-review SHA256:
  `54d58c415568d73a8d962bb1b0e47eb75bd02393ad7a5f9ea1da839fff8594fd`
- v2 provisional study-review SHA256:
  `b4b133386a3b487a87739829932df4ea76d534fca5c41865c5f9a79897dd2bae`

Every v2 checksum passes centrally and locally. All 224 repository tests pass. The
v2 report still states `manual_decisions_complete=false`; this is a better review
sheet, not a cohort freeze.

### Conservative v3 donor and power gate

Before protocol drafting, the v3 amendment narrows two skin groups without changing
the eight-groups-per-organ target:

- `GSE235570` retains healthy-control epidermis only, avoiding an
  epidermis/dermis compartment mixture; and
- `GSE297863` retains one deterministic healthy sample until its `rep` labels can be
  resolved as biological or technical.

The production workflow rebuilt the exact v3 sheet and verified these hashes:

- amendment SHA256:
  `de2d9e63588d777498fc736ef6da30f860fa14859f7c83bbbf44a7d3c441990a`
- provisional sample-review SHA256:
  `ab8a5751abbf680bb34e2e96cc8fe40e93016c06c9ecaaa37e7c273724d39418`
- provisional study-review SHA256:
  `3b0d5d3c1036d6084f02f47ab7582793782fefaa6ceff89b8e2ddb3ae88b6e41`
- donor/power protocol SHA256:
  `d1afa13e634d0a750a5d659c9bd49f96a49aacd17dd3aff264dcff7b116caa14`

The primary unit is the connected-study group: 40 total, eight per organ. Sample rows
are not treated as independent power units. Primary weighting is equal study within
organ and then equal organ, with at least 10,000 paired connected-study bootstrap
draws required after the outcomes are opened.

The audit derived 574 unique within-study keys and found no explicit identifier reused
across connected-study groups. This is only a partial donor check: 19 rows expose an
explicit identifier in the pinned metadata, while the remaining groups use unique
titles as proxies. A title proxy is not verified donor identity, so manual decisions
remain incomplete.

The exact one-sided sign-test design sensitivity at alpha 0.025 requires 27 of 40
studies to favor K4. Power is 21.1% if the true positive-study probability is 0.60,
44.1% at 0.65, 70.3% at 0.70, 89.7% at 0.75, and 98.1% at 0.80. This evaluates only
the cluster-count design; it is not relative-MSE power.

- implementation commit:
  `8d26e847419462152781c992fa5b9848846c4864`
- VM result:
  `/media/volume/moe-reboot/results/stage1_k4_external_donor_power_audit_8d26e84`
- local verified backup:
  `backups/stage1_k4_external_donor_power_audit_8d26e84/`
- full checksum-manifest SHA256:
  `77eb82e393b886200aa959e0292057066bac4ce146624c61b90b42af5655df97`
- donor/power report SHA256:
  `919bca4a210b40ff5ae7257217d11bb5073aa815479dac65df3e89992cf15640`

The exact gate is `ready_for_protocol_drafting_not_lockbox`.
`ready_for_lockbox_freeze=false` and `ready_for_expression_access=false`.

## Historical GTEx V11 metadata-only intake

The mentor-recommended GTEx resource is assigned to
`secondary_donor_controlled_validation`: it covers all five organs with explicit
donor IDs and a harmonized consortium pipeline, but one consortium cannot establish
the multisource cross-study generalization targeted by the 40-study ARCHS4 design.
The official GTEx catalog now exposes V11, which contains no new donors or samples
relative to V10 but updates annotation to GENCODE 47.

The pinned intake selected only `RNA:Total RNA` / `TruSeq.v1` rows for intact target
tissues. It excludes spinal cord, cultured fibroblasts, the liver LCM compartments,
the BMS/LCM pilot, and non-bulk expression batches. The official LCM-excluded V11
RNASeQC gene-read object is catalog-bound by URL, size, GCS generation, Last-Modified,
and ETag. At this metadata-only stage it had not been downloaded.

Historical Stage 1 metadata contains nine GTEx-derived ENCODE rows from four EN-TEx
donors. The public ENCODE aliases resolve them exactly:

| ENCODE donor | GTEx donor |
| --- | --- |
| `ENCDO271OUW` | `GTEX-1LVAN` |
| `ENCDO451RUA` | `GTEX-1K2DA` |
| `ENCDO793LXB` | `GTEX-1LGRB` |
| `ENCDO845WKR` | `GTEX-1JKYN` |

All four donors are excluded globally from every GTEx organ, removing 22 samples.
The remaining metadata-only pool is:

| Organ | Provisional samples | Donors |
| --- | ---: | ---: |
| adipose | 1,472 | 878 |
| brain | 3,509 | 405 |
| liver | 304 | 284 |
| skeletal muscle | 961 | 892 |
| skin | 1,599 | 908 |

The GTEx estimator is donor-first: average seeds within sample, samples/sites within
donor and organ, donors within organ, and then the five organs equally. This prevents
donors with multiple brain regions, skin sites, or adipose depots from receiving extra
mass. The cohort is described as adult human postmortem or organ-donor tissue from
GTEx non-diseased tissue sites, not as clinically healthy living donors.

- implementation commit:
  `c6133358355429dc1b8f3e3d9c1a534cf365011c`
- protocol SHA256:
  `35ddc3506561f2427613af8acebb5facc9efd7bc88bb6a0afe3fd15a5c6beed6`
- local verified result:
  `backups/stage1_k4_gtex_intake_c613335/`
- full checksum-manifest SHA256:
  `1eaf59d6caf84babdd0cb765551b85ded2e9b2f20f789c9cf908dd57b8ee0582`
- intake-report SHA256:
  `c966576ba84c47c9c42627b1c4e7094c7d5a3acb5b83d521e90204d5f5b194e2`
- provisional-cohort SHA256:
  `a88aa72acf4d40702b1b0ad3d13c4767308aa6ebf5e93bbb1440651696b04308`

This historical intake report states `expression_file_downloaded=false`,
`expression_values_read=false`, `ready_for_lockbox_freeze=false`, and
`ready_for_expression_access=false`. Those downstream gates were subsequently
completed under the separately frozen evaluation protocol summarized at the top of
this document; these flags describe the intake checkpoint, not the current state.

Quick verification commands:

```bash
ssh moe-reboot 'cat /media/volume/moe-reboot/results/stage1_k4_external_scout_182207b/SCOUT_STATUS'
ssh moe-reboot 'cd /media/volume/moe-reboot/results/stage1_k4_external_scout_182207b && sha256sum -c FULL_SHA256SUMS'
```

## Next decision tree

1. **GTEx secondary validation passed:** preserve the frozen cohort, protocol,
   candidate, and all controls; do not tune or rescore GTEx.
2. **Keep the claim bounded:** use GTEx as donor-controlled domain-shift evidence,
   not multisource confirmation or a clinically healthy living-donor cohort.
3. **Multisource feasibility passed:** every organ has 44–115 temporally new connected
   series, far above the preferred eight-series bar.
4. **Automated ARCHS4 eligibility failed:** preserve round 1 as the rule-development
   audit; do not treat its broad candidate pool as confirmation data.
5. **Current multisource gate — finish metadata signoff:** retain the already drafted
   evaluator semantics, candidate/checkpoint/router ledger, random-control dispatch,
   mask, cluster estimator, and mutually exclusive decision branches. In parallel,
   verify every pending study/sample/donor decision and replace failures from reserves.
6. **Freeze only after both pass:** hash exact ordered sample IDs, organ labels,
   connected-group IDs, gene mapping, the accepted donor ledger, and the complete
   evaluator implementation. Do not inspect expression.
7. **One-time multisource confirmation:** only then request expression, build the score cache once,
   and evaluate blind K4, true dispatch, pooled, pooled-residual, and all matched random
   controls. K5 and K4-total are not rescue candidates on that lockbox.

## Non-negotiable safeguards

- The previously inspected 1,018-row internal test is historical only and may never
  confirm or tune the final K4 model.
- Do not select a best seed, average weights, reopen K, or retune gates after seeing an
  external effect.
- Do not treat the metadata scout as evidence for or against organ specialization.
- Do not delete or relabel the failed organ-fixed averaging control.
- A favorable external result would support the Stage 1 architecture, not automatically
  establish Stage 2 biological mechanisms.

## Read order and source of truth

1. `docs/current-status.md` — current state, paths, hashes, next action.
2. `docs/stage1-k4-final-refit.md` — scientific reasoning, completed evidence, frozen
   external estimands and branches.
3. `docs/external-validation-intake-plan.md` — dataset-arrival gates and the
   one-time validation procedure.
4. `artifacts/stage1_k4_final_refit/protocol.json` — final-refit machine contract.
5. `artifacts/stage1_k4_external_scout/protocol.json` — metadata-scout machine contract.
6. `artifacts/stage1_k4_external_scout/sample_review_shortlist.json` — provisional,
   metadata-only sample selectors; not a frozen cohort.
7. `artifacts/stage1_k4_external_scout/sample_review_amendment_v3.json` —
   conservative liver replacement and skin selector narrowing.
8. `artifacts/stage1_k4_external_scout/donor_power_audit_protocol.json` —
   metadata-only analysis-unit and design-sensitivity contract.
9. `artifacts/stage1_k4_gtex_intake/protocol.json` — pinned GTEx V11 metadata,
   donor-overlap exclusions, tissue mapping, and donor-balanced secondary estimand.
10. `artifacts/stage1_k4_gtex_evaluation/protocol.json` — frozen GTEx cohort,
    extraction, scoring, controls, estimator, and decision contract.
11. `artifacts/stage1_k4_gtex_evaluation/result_summary.json` — completed GTEx
    decision, primary effects, hashes, and claim boundary.
12. `progress.md` — append-only historical chronology and older experiment detail.
