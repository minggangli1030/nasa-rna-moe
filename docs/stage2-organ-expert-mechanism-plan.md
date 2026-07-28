# Stage 2: organ-expert mechanism and directed transfer

**Status:** planning after Stage 1 cross-direction replication  
**Updated:** 2026-07-27

## Decision

Stage 2 remains anchored on the organ experts. Its primary objective is not to replace
organ identity with another label-free partition. It is to determine what the
replicated organ specialists learn differently, whether those differences predict
helpful or harmful transfer between organs, and whether the input-only router uses the
same functional structure.

Label-free discovery is demoted to an optional secondary analysis. It may test for
continuous or within-organ structure after the organ-expert mechanism is established,
but it cannot replace the organ axis or control the primary Stage 2 decision.

## Stage 1 premise

The following statement is now supported:

> Organ-specialized models improve the balanced masked-reconstruction estimand versus
> pooled whether dispatch uses the revealed organ, a hard target-hidden router, or a
> soft target-hidden router.

In the GTEx-to-ARCHS4 evaluation, the gains were 3.797%, 3.633%, and 3.676%,
respectively. Every condition was positive in all three prespecified seeds; the
study-bootstrap intervals versus pooled excluded zero; random K8 and pooled-adapter
controls were neutral. The reverse ARCHS4-to-GTEx evaluation and earlier ARCHS4
development experiments produced similar 3–4% effects.

This is routing-form, seed, setup, and training/evaluation-direction robustness.
Because individual organ-by-seed and study-level effects are heterogeneous, it must
not be described as improvement in every study or every organ cell.

## Why label-free routing appeared in the earlier Stage 2 concept

Organ-specific MoE and masked transcriptomic representation learning already have
substantial related work. The earlier novelty plan therefore proposed linking two
independently measured structures:

1. a directed transfer map measuring whether training signal from organ B helps or
   harms held-out organ A; and
2. a label-free co-routing map that would ideally predict that transfer map.

That was a novelty extension, not a finding that organ identity was unimportant.
Subsequent label-free pilots did not establish a useful alternative axis: their
reconstruction gains were near zero or below the frozen practical threshold, some
routes collapsed, and study association exceeded organ association. Those failures
remain valid. Stage 2 should therefore preserve the transfer question while restoring
the organ experts as the primary scientific object.

## Primary Stage 2 objective

> Determine whether reproducible functional differences among frozen organ experts
> explain their conditional reconstruction gains and predict directed cross-organ
> transfer or interference on donor-disjoint development data and, ultimately, a new
> untouched study-disjoint cohort.

Three linked questions implement that objective:

1. **Expert mechanism:** Which genes, pathways, and residual directions are changed by
   each organ adapter relative to the shared pooled trunk?
2. **Directed transfer:** Under both compute-matched substitution and
   recipient-exposure-matched addition, does donor-organ B data improve or degrade
   performance on untouched recipient-organ A studies?
3. **Router alignment:** Do hard/soft routing preferences and expert residuals agree
   with the independently measured transfer relationships?

The transfer matrix is directed: B may help A even when A does not help B. Similarity
or co-routing is symmetric unless explicitly modeled otherwise, so the first test
should use preregistered signs/ranks for selected edges rather than claiming a
graph-wide correlation from too few pairs.

## Proposed experiment sequence

### Completed precursor — frozen cross-dispatch utility audit

Implementation commit `9fad92a` audited the existing GTEx calibration score caches
without model fitting or ARCHS4 access. It covers 1,826 calibration samples from 188
held-out GTEx donors and applies every frozen expert to every recipient organ.

- the correctly named expert ranks first for all eight recipient organs after
  averaging seeds 17, 42, and 101;
- all 56 off-diagonal recipient/expert means are worse than pooled;
- 23 of 24 named organ-by-seed cells improve over pooled;
- only 2 of 168 off-diagonal organ/expert/seed cells improve; and
- named-expert mean gains range from 0.921% for colon to 21.718% for skin.

This confirms that the frozen experts are functionally organ-aligned on development
data. It is a cross-dispatch audit, not the Phase 2 transfer estimand: applying organ
B's already-trained expert to organ A is different from measuring whether adding
organ-B training examples changes a newly controlled recipient-A model.

Canonical artifact:
`artifacts/stage2_organ_expert_mechanism/frozen_expert_audit_9fad92a/`.

### Phase 1 — frozen-expert mechanism audit

- Keep the pooled trunks, organ adapters, routers, genes, masks, and seeds frozen.
- Use development/calibration studies only.
- Measure expert-minus-pooled residuals, gene-level consistency across seeds, pathway
  coherence, and concentration by organ, study, platform, and disease context.
- Require direction stability across seeds and reject signatures dominated by a
  single study or obvious technical covariate.

This phase interprets existing experts; it does not retrain against the completed
ARCHS4 lockbox.

### Phase 2 — controlled directed-transfer matrix

- Define recipient organ A and donor organ B using development studies only.
- Hold adapter capacity, initialization, masking, sampling units, and evaluation
  constant.
- Estimate two complementary effects rather than forcing total compute and recipient
  exposure to be constant in one impossible comparison:
  1. **Substitution / same total compute:** compare 1,500 recipient-A draws with
     750 A + 750 B draws. This asks whether B is a better use of a limited training
     budget than additional A exposure.
  2. **Addition / same recipient-A exposure:** compare 1,500 A draws with
     1,500 A + 750 B draws. This asks whether B adds information beyond preserving
     the full recipient exposure.
- Evaluate on recipient-A studies excluded from both fitting and model selection.
- Include exposure-matched random-donor, self/additional-A, and pooled controls.
- Repeat every selected edge for seeds 17, 42, and 101.

The two estimands are the changes in recipient-A study-balanced MSE caused by
substituting B for half of A under a fixed budget and by adding B while preserving A
exposure. Positive values mean helpful transfer; negative values mean interference.
Reporting both prevents “more updates” and “less recipient data” from being mistaken
for organ-specific transfer.

Candidate packed implementation for the full substitution matrix:

- eight recipient-only K1 adapters;
- 28 unordered two-organ K1 adapters, evaluated separately on each recipient to
  produce 56 directed effects;
- the same semantic initialization key within each training seed;
- 1,500 active draws for every adapter;
- pair adapters receive 750 draws from each organ, so organ B replaces half of
  organ A's exposure rather than increasing total adapter exposure; and
- three donor-atomic random-auxiliary controls per recipient with exactly matched
  750-recipient/750-auxiliary exposure.

The primary directed effect is recipient-A MSE for the A+B adapter versus the
recipient-only A adapter under matched total active exposure. The random-auxiliary
arms test whether a specific donor organ is more useful than generic heterogeneous
auxiliary data.

The additive confirmation is deliberately staged to control compute. Before any
additive result is opened, freeze a small set of candidate positive, neutral, and
negative edges using development-only mechanism/router predictions—not the
substitution test outcomes. For each frozen edge, compare:

- A1500+B750 against A1500 alone;
- A1500+B750 against A1500+random750; and
- A1500+B750 against an A2250 self/additional-update control.

This separates donor identity from generic heterogeneity and from the benefit of
simply taking 750 more optimization draws. The all-56-edge substitution matrix is
the discovery map; the prospectively frozen additive subset is the stronger
information-addition test.

Implementation must not launch until the donor-atomic random scheduler proves exact
exposure matching. Otherwise a nominal transfer effect could be confounded by unequal
recipient exposure or total gradient mass.

Implementation checkpoint: the deterministic compiler
`evaluation/build_stage2_directed_transfer_schedules.py` now enforces these exact
source quotas and donor-atomic random-shard membership without loading expression or
efficacy results. Commit `d3eb358` pairs each source's deterministic donor/sample
sequence and source-local mask index across comparison arms and enforces the source
ratio within every six-sample update. The exact 60-arm/90,000-draw substitution
schedule is frozen from GTEx
manifest SHA256 `d37023f08fabf5059a886501ab416feb5caabbce9aa719086832f6d2579ed2e6`;
schedule SHA256 is
`6390071cdc463a12e2bbf533b931235c17c6a40d75aacc61dbbd881b8c46ed20`.
The schedule-bound K1 trainer at `00e37e3` passes the combined focused suite, and its
two-arm/two-batch real-data GPU smoke completed successfully. The aggregate
evaluator, prospective additive-edge freeze, and strict all-three-seed launcher were
then frozen at `229dfa6`; the full substitution run completed for all three distinct
seeds. The checksum-verified preliminary result is
`docs/stage2-directed-transfer-preliminary-result.md`.

All 56 directed substitution edges are negative in all three seeds and have paired
donor-bootstrap intervals below zero. The mean effect is −3.273% for A750+B750
versus A1500. This means another organ is not a better use of half the recipient
budget; it does not answer whether B adds information when A1500 exposure is
preserved. The prospectively frozen additive subset remains the next discriminating
experiment.

The recipient-exposure-preserving additive subset is now frozen as a separate
additive-only schedule before any additive outcome. It contains 40 arms and 90,000
training draws: eight A1500+B750 named-donor arms, eight A2250 self controls, and
24 A1500+random750 controls. Schedule SHA256 is
`fe71a83a9eb60529aef8f1c66dff5072dbc2ba1c6f508284e3568a862f35a75c`;
arm-definition SHA256 is
`78edd164f8c5444299da7ab5bf45cd35eed3d513f772b6a7fab11b9aef60d3fb`.
The evaluator and explicit-seed launcher are frozen with the schedule, the outputs
were independently regenerated to the same hashes, and 18 focused Stage 2 tests
pass. The next result will answer whether a selected donor adds information while
recipient exposure is preserved; it must not be conflated with the already-complete
substitution matrix.

The full transfer matrix is a GTEx donor-disjoint development analysis. It can
measure controlled transfer and freeze predictions, but GTEx cannot establish
multisource study robustness. A final Stage 2 confirmation must use a genuinely new
untouched study-disjoint cohort.

### Phase 3 — frozen correspondence test

- Freeze a small set of positive, neutral, and negative transfer edges without using
  final-test outcomes.
- Test whether organ-expert residual similarity and router co-preference predict the
  transfer sign/rank.
- Compare against random partitions, sample-count similarity, study/platform
  similarity, and baseline expression similarity.

Passing requires more than an interpretable heatmap: the frozen predictor must beat
the controls on held-out edges or studies.

## Why this experiment has practical value

The immediate product is a rule for deciding which biological domains should share
training information and which should remain separated.

1. **Choose useful training data.** For a rare recipient organ, identify abundant
   donor organs that improve held-out recipient studies instead of pooling all
   available RNA-seq indiscriminately.
2. **Prevent negative transfer.** Use reproducible harmful edges to motivate separate
   adapters, gradient-conflict controls, organ-balanced curricula, or router-enforced
   isolation.
3. **Design a more efficient MoE.** Mutually helpful organs may share an intermediate
   module; asymmetric pairs may support one-way initialization; interfering organs
   should remain separate; organ families may form a hierarchy from pooled trunk to
   family to specific organ.
4. **Predefine adaptation sources for scarce downstream domains.** A reliable
   ordinary-study transfer edge can nominate a source organ for a rare disease or
   spaceflight dataset. This is a rational preregistered source-selection rule, not
   evidence of downstream spaceflight benefit by itself.

The biological value is that transfer measures a functional consequence—whether
learning from organ B changes generalization on organ A—rather than expression
similarity alone. The strongest evidence links three independently measured objects:

- expert-minus-pooled gene and pathway signatures;
- controlled directed transfer effects; and
- input-only router compatibility.

Agreement among all three on study-disjoint data would be stronger than a descriptive
cluster map. Disagreement is also useful because it reveals when visual or expression
similarity does not translate into beneficial optimization.

## Preliminary end deliverable — directed organ-transfer heatmap

The primary Stage 2 development figure is a directed 8×8 organ-by-organ heatmap:

- **rows:** recipient organ A whose donor-disjoint calibration performance is
  measured;
- **columns:** donor organ B whose training examples replace half of A under the
  same-compute substitution estimand;
- **cell value:** percentage change in recipient-A donor-balanced MSE for A750+B750
  relative to A1500, with positive values denoting helpful transfer and negative
  values denoting interference/negative transfer;
- **diagonal:** the recipient-only reference, displayed as zero or visually masked;
  and
- **annotations:** mean across seeds, seed-sign count out of three, donor-bootstrap
  interval, and an indicator for beating the matched random-auxiliary controls.

A companion stability panel must keep separate questions separate:

1. **Seed stability:** does the edge retain its sign in seeds 17, 42, and 101?
2. **Donor robustness:** does a paired donor bootstrap exclude zero in
   donor-disjoint GTEx calibration?
3. **Edge universality:** what fraction of the 56 directed edges meet both gates, and
   are failures concentrated in particular recipients or donors?
4. **Study universality:** does the frozen sign generalize to independent studies in
   a new untouched multisource cohort?

Seed agreement is necessary but does not establish universality. GTEx can address
seed and donor robustness, not study universality. The heatmap must show heterogeneous
or uncertain cells honestly; it is not acceptable to select only favorable edges or
describe all organ pairs as invariant unless every prespecified gate actually passes.

## Novelty and confound boundary

Expert interpretation, transfer learning, and router analysis are individually
established methods. The more novel and underexplored contribution is their
prospectively tested combination:

> Use independently validated organ experts to derive mechanistic expert signatures,
> measure a controlled directed organ-to-organ training-transfer matrix, and test
> prospectively whether expert or router structure predicts those transfer effects on
> held-out studies.

Transfer is not automatically biological. Apparent edges may instead reflect
sequencing platform, study composition, sample quality, disease context, organ-label
error, unequal exposure, or generic expression similarity. The protocol therefore
requires study-disjoint evaluation, seed replication, organ-balanced and
donor-atomic sampling, platform/study controls, random donor controls, and both the
same-compute and same-recipient-exposure comparisons above.

### Phase 4 — optional within-organ/label-free extension

Only after Phases 1–3 pass:

- ask whether continuous residual factors explain variation left within an organ;
- require anti-collapse, effective-K, seed/mask stability, and study-confound gates;
- compare against the organ router rather than treating organ identity as a nuisance;
- keep this result secondary unless it improves held-out utility and predicts
  transfer.

Do not repeat the failed de novo label-free soft-mixture configuration as the primary
Stage 2 experiment.

## Entry and stopping rules

Stage 2 implementation and development-only analysis may begin now. A final Stage 2
lockbox may be opened only after:

- the transfer estimand, selected edges, masks, seeds, and multiplicity rule are
  frozen;
- real-data mechanical smoke tests pass without final-test access;
- organ-expert signatures and transfer effects are seed-stable on development data;
- random/capacity/study-confound controls are implemented; and
- a genuinely untouched evaluation cohort is frozen.

Stop or redesign before the lockbox if transfer effects are negligible, dominated by
one study, unstable across seeds, or indistinguishable from random donor partitions.

## Claim boundary

A successful Stage 2 would support:

> Organ experts learn reproducibly different functional corrections, and those
> differences predict when training information transfers helpfully or interferes
> across organs.

It would not by itself establish a causal biological mechanism, a new organ taxonomy,
spaceflight benefit, or clinical utility. Those require separate interventions and
task-specific evaluation.

## Adjacent novel directions

These remain secondary to the approved mechanism/transfer sequence. They are ranked by
their current combination of novelty, feasibility, and dependence on existing
evidence.

| Priority | Direction | Novel question | Entry condition |
| ---: | --- | --- | --- |
| 1 | Directed transfer and interference | Can frozen expert differences predict which organ’s training signal helps or harms another organ? | approved primary Stage 2 |
| 2 | Pathway-resolved expert mechanisms | Do independently trained organ adapters converge on reproducible pathway-specific residual corrections? | seed-stable Phase 1 signatures |
| 3 | Hierarchical organ → state MoE | After choosing an organ expert, is there useful within-organ disease, stress, sex, age, or donor-state specialization? | organ effect preserved; anti-confound design |
| 4 | OOD-aware fallback routing | Can router uncertainty identify mislabeled, low-quality, mixed, or out-of-taxonomy samples and safely fall back to pooled? | frozen uncertainty rule and untouched OOD cohort |
| 5 | Compositional expert reuse | Can sparse combinations of organ experts model mixed tissues or shared physiological programs better than a flat K8? | parameter/compute-matched controls |
| 6 | Platform-invariant organ routing | Can adversarial or invariant training retain organ gain while suppressing study/platform predictability? | separate development studies and confound audit |
| 7 | Minimal gene-panel routing | What is the smallest observed-gene panel that preserves organ routing and reconstruction benefit? | target-hiding and acquisition-cost protocol |
| 8 | Disease/perturbation transfer | Do organ experts predict which disease or perturbation responses transfer across tissues? | curated perturbation metadata and untouched task |
| 9 | Spaceflight adaptation | Does organ-aware pretraining improve a separately frozen spaceflight task under severe data scarcity? | task-specific protocol; no reconstruction-to-outcome leap |
| 10 | Parameter-efficient expert systems | Can shared low-rank or compositional adapters preserve the 3–4% gain with less storage and active compute? | same-data, same-update systems benchmark |

The strongest near-term novelty is not another clustering visualization. It is the
held-out predictive link between expert mechanism and directed transfer. Hierarchical
or label-free discovery becomes compelling only if it adds utility beyond the
replicated organ route and survives study/platform confounding.
