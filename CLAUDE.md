# NASA RNA MoE: bottleneck and decision brief

**Updated:** 2026-08-01
**Purpose:** concise Codex–Claude review document. This replaces the previous
accumulated discussion. Frozen protocols, immutable artifacts, and canonical result
documents remain authoritative.

## TL;DR

The organ MoE works for the task it was trained to solve: reconstructing masked gene
expression. On an external ARCHS4 cohort, the correct organ expert improved MSE by
3.797% over the pooled model; input-only hard and soft routing retained 3.633% and
3.676% gains. All three fixed seeds improved. This is useful, reproducible evidence
for organ-specialized reconstruction, although the accessed cohort is correctly
described as a post-access QC-amended external evaluation rather than a pristine
confirmation.

The bottleneck is that this reconstruction advantage has not become a reliable
general-purpose representation advantage. On the study-grouped OSDR development
task, raw expression (AUROC 0.726) and fold-fit PCA-64 (0.733) beat every learned
representation. The explicit organ embedding also failed: blind hard AUROC was
0.531/0.561/0.533 and blind soft was 0.557/0.566/0.507 across seeds 17/42/101.
Neither condition improved over the pooled hidden representation in every seed.

The most defensible solution is therefore to split the claims. Preserve the frozen
three-seed K8 organ MoE as a validated reconstruction model and confirm it once on a
new untouched study-grouped cohort. If downstream utility remains a goal, build it as
a separately supervised, downstream-facing extension with explicit tasks and strong
raw-expression/PCA/SOTA baselines. Do not keep tuning the existing reconstruction
embedding until it happens to pass.

## 1. What is established

### Stage 1: organ specialization is useful for reconstruction

- GTEx-trained K8 organ experts were evaluated on 821 ARCHS4 samples from 63 studies.
- Relative to one pooled model:
  - revealed true-organ routing improved MSE by 3.797%;
  - automatic hard routing improved MSE by 3.633%;
  - automatic soft routing improved MSE by 3.676%.
- All three fixed seeds improved.
- Random-K8 and pooled-adapter controls were effectively neutral.
- The bounded conclusion is that organ-conditioned corrections generalize across a
  heterogeneous external study aggregate and remain useful when routing is automatic.
- This does **not** establish improvement within every individual study or universal
  downstream utility.

### Stage 2: indiscriminate cross-organ sharing is not reliable

- Helpful directed transfer edges were unstable across optimization seeds.
- Same-budget donor substitution was consistently harmful across the 56 directed
  organ pairs.
- Recipient-preserving addition did not robustly beat simply providing more recipient
  data.
- The stable lesson is negative-transfer risk: organ-private paths should be the
  default, and sharing must earn authorization through matched controls and safety
  gates.

### Secondary biological axes did not justify architecture expansion

- Tissue site passed the linear Tier-1 screen, but its neural adapter lost to a
  parameter-matched generic adapter in all three seeds. Its apparent benefit was
  primarily extra generic capacity, not site-specific information.
- Hallmark-50 had strong aggregate signal but harmed skeletal muscle in two seeds and
  failed the frozen per-organ safety gate.
- Age and sex did not pass all-seed bootstrap gates.
- The architecture is therefore closed as K8 organ MoE plus pooled fallback/reference,
  with no secondary axis.

### The final package is frozen

- All three externally evaluated seed families—17, 42, and 101—are packaged.
- The package contains each pooled trunk, K8 organ bank, and the frozen input-only
  router.
- No best seed was selected and no post-lockbox refit was performed.
- Refitting would create a new weight family without the existing external validation.
- Hidden states, bottlenecks, and router probabilities are diagnostic outputs only;
  they do not carry a downstream-benefit claim.

## 2. The current bottleneck

The bottleneck is an **objective and evaluation mismatch**, not evidence that organ
biology is absent.

The model was optimized to infer masked genes from observed expression. It learned
organ-conditioned corrections that improve that reconstruction objective. A compact
hidden state that supports reconstruction, however, is not automatically a good
feature space for a different label such as spaceflight state, disease, treatment,
or survival—especially across species and studies.

Several effects compound this mismatch:

1. **The training loss does not reward downstream separation.** Information useful
   for a phenotype can be discarded if it is unnecessary for masked-gene prediction.
2. **The bottleneck is compressed toward the decoder's needs.** Raw expression and
   PCA retain broad variation that the reconstruction head may suppress.
3. **OSDR is a hard domain shift.** The development benchmark is mouse, cross-species,
   study heterogeneous, and small after strict QC: 292 samples from 18 studies.
4. **Labels and technical factors vary by study.** Organ signal can be real while a
   learned embedding still fails to preserve the particular within-organ contrast.
5. **Three-seed inconsistency rules out a dependable downstream claim.** A few
   favorable seed-condition combinations cannot be selected after outcomes are seen.
6. **The development cohort is already accessed.** It can guide architecture and
   output-contract decisions, but it cannot later serve as pristine confirmation.

The correct interpretation is:

> The model is validated as an organ-specialized reconstruction system. General
> downstream representation quality is a separate hypothesis that the current
> objective and outputs did not support.

## 3. Why the attempted fixes did not solve it

We tested increasingly explicit ways to expose potentially useful structure:

- organ-to-organ transfer matrices;
- seed-factorized stability diagnosis;
- shared residual programs and coefficient-supervised repair;
- additional axes such as tissue site, Hallmark programs, age, and sex;
- pooled hidden summaries;
- true-organ, hard-router, and soft-router bottleneck embeddings; and
- router probabilities concatenated with pooled features.

Some of these found real structure, but none produced an all-seed downstream output
that beat raw expression and fold-fit PCA. The tissue-site result also demonstrated
why matched-capacity controls matter: a large improvement over the protected base
was not axis-specific because an equally sized generic adapter performed better.

More post-hoc repair of this same embedding would now risk optimizing to the accessed
OSDR cohort. It would also blur the strong reconstruction result with a weaker and
different claim.

## 4. Proposed solution

### Track A — finish the reconstruction claim cleanly

This is the high-confidence core result and should remain frozen.

1. Preserve the exact packaged three-seed K8 model; do not refit or select a seed.
2. Construct a **new untouched, study-grouped multisource reconstruction cohort**
   with the eight organ labels and existing gene/QC contract.
3. Freeze membership, exclusions, routing conditions, baselines, estimands, and
   thresholds before opening expression outcomes.
4. Compare pooled, true-organ explanatory routing, blind hard routing, blind soft
   routing, random experts, and matched-capacity generic adapters.
5. Report all seeds, organ-level safety, study bootstrap intervals, and aggregate
   effects. Do not claim invariance within every study.
6. Treat this as the pristine confirmation of the central claim: organ specialists
   improve masked-expression reconstruction and can be selected automatically.

This track does not require a new architecture. It requires a better confirmation
cohort and careful frozen evaluation.

### Track B — make downstream utility an explicit learning problem

If downstream performance is important for the final product, start a distinct
extension rather than reusing the reconstruction bottleneck unchanged.

1. **Define executable tasks before training.** For every candidate task record:
   cohort, sample count, study/donor groups, label source, and whether the expression
   matrix is available. Drop any task that cannot answer all five.
2. **Use study- or donor-grouped splits.** Labels must vary within organ where
   possible, so an organ classifier cannot solve the task indirectly.
3. **Train an explicit downstream-facing output.** Reasonable bounded options are:
   - a multi-task organ-conditioned encoder trained jointly on reconstruction and
     curated phenotype labels;
   - supervised contrastive learning with study and organ nuisance controls; or
   - frozen reconstruction experts plus small task-specific heads, tested before any
     end-to-end fine-tuning.
4. **Protect the validated reconstruction path.** Begin with frozen trunks/experts and
   gated residual downstream heads. Only allow shared updates after demonstrating no
   material reconstruction or per-organ harm.
5. **Benchmark against simple and published models under identical splits.** Required
   comparisons are raw expression, fold-fit PCA, elastic net, the pooled model,
   organ-MoE outputs, BulkRNABert where the input/gene contract is compatible, and
   BulkFormer only when its exact preprocessing and checkpoint contract can be
   reproduced.
6. **Use equal tuning budgets.** PCA plus elastic net must receive the same nested
   tuning discipline as learned representations.
7. **Hold back a new final cohort.** Development data may select the output contract;
   the final claim must use a new untouched grouped cohort.

The first downstream experiment should be small and diagnostic. It should answer:
does explicit downstream supervision produce an all-seed gain over raw/PCA under
grouped evaluation? If not, stop before final-scale training.

## 5. How to use biological axes going forward

Organ remains the strongest validated specialization axis. Other axes should be
treated as candidate labels, nuisance variables, or continuous programs—not as new
experts merely because they correlate with reconstruction residuals.

Promising candidates include:

- anatomical subregion or tissue site;
- disease, treatment, inflammation, hypoxia, or spaceflight state;
- age, developmental stage, and sex; and
- continuous immune, metabolic, mitochondrial, contractile, extracellular-matrix,
  cell-cycle, and stress-response programs.

For each axis, advancement should require:

- incremental predictive value beyond organ plus technical nuisance variables;
- within-organ permutation controls;
- donor/study bootstrap support;
- all-seed direction consistency;
- per-organ safety;
- comparison with a parameter-matched generic-capacity control; and
- improvement on a separately measured downstream task.

Continuous pathway programs may be more useful initially as interpretable probe
targets or covariates than as discrete routing labels. Cell-type composition should
remain deferred unless a reliable deconvolution/reference contract becomes
available and organ confounding can be controlled.

## 6. Recommended near-term course

Recommended strategy: **lock Stage 1 as the completed core contribution, pursue a
pristine reconstruction confirmation, and scope downstream representation learning
as a separate extension with an early fail-fast benchmark.**

Ordered actions:

1. Write the final reconstruction confirmation cohort contract and readiness audit.
2. Inventory downstream tasks using the five required fields; choose one primary task
   with adequate within-organ labels and grouped splits.
3. Build the downstream harness first against the already frozen package.
4. Establish raw-expression, PCA, elastic-net, pooled, and public-model baselines.
5. Freeze a small explicitly supervised organ-conditioned representation smoke.
6. Advance to final training only if the smoke beats raw/PCA in every fixed seed
   without harming reconstruction or protected organs.
7. If it fails, keep the reconstruction contribution and report the downstream result
   as a bounded negative finding rather than initiating another repair loop.

## 7. Decision requested from Minggang

Choose the emphasis before more large runs:

### Option 1 — reconstruction-first final story

Prioritize pristine external confirmation, model packaging, organ-level analysis,
and presentation/publication of the 3.6–3.8% automatically routed gain. Downstream
learning remains future work.

### Option 2 — downstream-first extension

Allocate time to curate a task-specific cohort and train an explicitly supervised
representation, accepting that this is a new experimental claim with new failure
risk and a required untouched confirmation set.

### Recommended — staged hybrid

Do not reopen the validated reconstruction model. Secure the reconstruction claim
with a new untouched cohort while building one small downstream-supervised smoke in
parallel. Continue downstream work only if it clears raw/PCA and all-seed gates.

## 8. Questions for Claude's next review

1. Is the claim split scientifically appropriate, or is there a stronger way to
   connect reconstruction specialization to downstream value without overclaiming?
2. Which single downstream objective is most defensible and executable given the
   available cohorts and the August 17 presentation deadline?
3. Should the first supervised extension freeze the organ experts and train only a
   task head, or jointly fine-tune through a strongly gated residual path?
4. What is the smallest public-model baseline set that is fair, reproducible, and
   compatible with the same genes, samples, and grouped splits?
5. What untouched human or multisource cohort is realistic for pristine Stage 1
   confirmation without repeating the ARCHS4 access problem?

## 9. Claude review — 2026-08-01

> **Execution plan:** [`docs/downstream-negative-result-audit-plan.md`](docs/downstream-negative-result-audit-plan.md)
> contains the file-level, function-level implementation of D1 through D4 below,
> including frozen interpretation thresholds, the decision tree, reuse points in the
> existing evaluators, and required documentation changes. Codex should execute from
> that document. This section is the reasoning behind it.

**Bottom line.** The claim split is right and I endorse Option 1 for August 17. But
**do not write the negative result yet.** Three cheap diagnostics stand between the
current evidence and the conclusion the brief draws, and one of them could invalidate
the OSDR result entirely. Together they cost under a week and none requires retraining.

The brief treats "the representation is not downstream-useful" as established. What is
actually established is "these embeddings lose to raw/PCA **on one small cross-species
cohort**." Those are different claims, and the gap between them is where the remaining
two weeks should go.

### 9.1 D1. Positive control on the embedding (run today, roughly one hour)

**This is the highest-value hour left in the project and it is currently missing.**

Pooled hidden scores AUROC 0.525 to 0.607 on OSDR. That is near chance for a model
that demonstrably reconstructs well. Before accepting that as a statement about
representation quality, verify the encoder produces *anything* meaningful on mouse
ortholog-mapped input.

**Procedure.** Take the same frozen embeddings on the same 292 OSDR samples and
predict **organ**, which is known, and which the model is explicitly built to encode.
Same study-grouped folds. Report balanced accuracy and macro-F1 against a raw-expression
organ classifier on identical splits.

**Interpretation, fix before running:**

| Embedding predicts organ | Meaning |
|---|---|
| well, comparable to raw | the encoder transfers to mouse; the spaceflight failure is a real representation limit; the brief's conclusion stands and can be written with confidence |
| poorly, near chance | **the encoder is out of distribution on mouse input and the entire OSDR evaluation is invalid as a representation test.** The negative result would be measuring cross-species breakdown, not objective mismatch |

The second branch is live. The model was trained on human GTEx expression
distributions and is being fed mouse orthologs. A human-trained encoder can produce
degenerate output on shifted input while raw expression, which passes through no
learned weights, is unaffected. That asymmetry alone could produce the observed
0.726 versus 0.53 gap without any of the objective-mismatch reasoning in Section 2.

Also check, at the same time, that the raw expression fed to the encoder uses the exact
normalization the model was trained with. A preprocessing mismatch produces the same
signature and is a one-line fix.

### 9.2 D2. Re-scope Hallmark-50 from expert axis to downstream features (one day)

Hallmark-50 produced **the only downstream-positive signal anywhere in this project**:
OSDR AUROC delta +0.1013, study-bootstrap interval +0.0267 to +0.2049. It was then
discarded.

The rejection was correct **for the question it was asked**. Hallmark failed the
per-organ *reconstruction* safety gate, harming skeletal muscle by −0.0568 and −0.0396
against a −0.02 limit. That gate protects the reconstruction model, and it was written
when reconstruction was the deliverable.

But Hallmark program scores used as **downstream features** never touch the
reconstruction model. No expert is routed, no adapter is trained, no organ can be
harmed. Per-organ reconstruction safety is simply not the applicable gate, so
Hallmark-as-features has never been evaluated by any gate at all.

**What has not been run, and should be:** Hallmark-50 scores as a standalone
representation in the existing OSDR harness, against raw expression and fold-fit
PCA-64 directly. Tier 1 measured an incremental delta over a probe base, **not**
against the mandatory baselines, so the comparison that decides the matter does not
exist yet. Run three conditions: Hallmark-50 alone, Hallmark-50 concatenated with
PCA-64, and PCA-64 alone as the reference.

If Hallmark beats 0.733, the project has a positive downstream result. Note it would
be a result about **biologically structured features**, not about the learned model,
since Hallmark scores are a deterministic function of expression. That is still a real
and reportable finding, and an interesting one: biology-informed features beating both
raw expression and learned representations is a cleaner story than most positive
results in this literature. Report it as what it is.

Cost is low because the scores already exist from Tier 1 and the harness is validated.

### 9.3 D3. Isolate cross-species from objective mismatch (two to three days)

Section 2 lists cross-species shift as one of six compounding effects. It is the only
one that is both plausibly dominant and cheaply testable, and D1 gives a partial read
on it. D3 settles it.

**Procedure.** Build one **human**, study-grouped, within-organ binary downstream task
from ARCHS4 held-out studies, using `data/holdout_eval/strict_study_disjoint_ids.txt`
as the starting membership. Any binary contrast with adequate per-study counts is
acceptable; the label matters less than the species. Run the identical harness and the
identical baseline ladder.

**Interpretation:**

- learned representations still lose to raw/PCA on a human task, then objective
  mismatch is confirmed, the brief's Section 2 reasoning is validated, and the negative
  result is general and worth stating strongly;
- learned representations are competitive on a human task, then **the story changes
  completely**: the representation works within the training domain and OSDR measured a
  cross-species limit. That is a better, more precise, and more honest talk than either
  the current negative or a weak positive, and it converts a failure into a
  characterized boundary condition.

Either outcome is presentable. Not knowing which one is true, and presenting the
stronger claim anyway, is the outcome to avoid.

### 9.4 D4, optional. Run one external model as a framing device (one day)

Only if D1 to D3 finish early. The reason to run published BulkFormer-147M is no longer
to see whether you beat it. Your problem is that you lose to PCA.

Run it to find out **whether it also loses to PCA on this cohort.** I would expect it
does. If so, the finding stops being "our model is weak" and becomes "this task defeats
learned representations generally, including current SOTA, while simple baselines
hold up." That is a substantially stronger and more interesting result, and it costs
one inference pass with no training.

### 9.5 Answers to Section 8

**Q1. Is the claim split appropriate?** Yes, and it is the only honest option given
current evidence. The stronger framing you asked for is not a better connection between
reconstruction and downstream value. It is to stop presenting a bare negative and
present a **characterized** negative: what breaks, at which boundary, and verified by
controls. D1 and D3 supply exactly that. A negative result with a mechanism is a
contribution; a negative result without one reads as an unfinished project.

**Q2. Which downstream objective is defensible and executable by August 17?** None that
requires new training. There is no version of Track B that completes credibly in
sixteen days including deck preparation, and attempting it risks the parts that already
work. For August 17, run D1 to D3 and present Option 1. For the future work slide, the
defensible objective is a **human, within-organ, study-grouped binary phenotype task**,
because it removes the cross-species confound while keeping organ conditioning
meaningful.

**Q3. Freeze experts and train a head, or gated joint fine-tuning?** Freeze, always,
and first. Three reasons. It is the only configuration that tests the representation
claim, since fine-tuning tests whether the initialization helps, which is a weaker and
different claim. It preserves the externally validated package, whereas fine-tuning
creates a new weight family with no external validation, which your own guardrails
forbid. And it is far cheaper. Do not fine-tune before August 17 under any
circumstances.

**Q4. Smallest fair public-baseline set?** Given that you lose to PCA, external
foundation models are now a **lower** priority, not a higher one. Adding BulkFormer to a
table that PCA already tops does not strengthen anything on its own. The minimum honest
set is raw expression, fold-fit PCA, elastic net, the matched pooled trunk, and the
three deployable MoE modes, which you have. Add exactly one external model, published
BulkFormer-147M, and only for the framing purpose in D4. Equal tuning budget for the
simple baselines is non-negotiable and is the first thing a skeptical reader checks.

**Q5. Untouched cohort for pristine Stage 1 confirmation?** Not achievable by August 17,
and attempting it would produce a rushed cohort that is not actually pristine, which is
worse than no confirmation. ARCHS4 holds far more studies than the 63 used in the Stage
1 external evaluation, so the natural candidate is a study-disjoint ARCHS4 partition
with no overlap against those 63, with recount3 as an alternative source. **Write and
freeze the cohort contract before August 17, execute after.** Having a written,
pre-registered confirmation protocol is itself a presentable artifact and is more
credible than a hurried result.

### 9.6 Recommended decision and calendar

**Option 1, reconstruction-first, plus the three diagnostics.** Not the staged hybrid.
The hybrid's parallel downstream smoke is Track B in disguise and there is not enough
time for it to clear its own gates honestly.

| Dates | Work |
|---|---|
| Aug 1 | **D1 positive control.** Gate everything else on the result |
| Aug 2 to 3 | D2 Hallmark as downstream features against raw and PCA |
| Aug 4 to 6 | D3 human downstream control |
| Aug 7 to 8 | D4 if time permits; otherwise begin consolidation |
| Aug 9 to 11 | freeze figures, write the Stage 1 confirmation cohort contract |
| Aug 12 to 17 | deck, with August 16 reserved for correction only |

Every item after D1 is independently droppable without breaking the talk.

### 9.7 What the talk becomes

Worth stating now, because it determines which diagnostics matter.

The presentation has three established results already: organ specialization improves
reconstruction on external human data with automatic routing, cross-organ sharing is
reproducibly harmful while helpful transfer is not reproducible, and secondary axes do
not survive matched-capacity controls. Those are real, they are done, and they are
defensible.

The fourth result is the downstream negative, and its value depends entirely on whether
you can say **why**. Right now you cannot, because D1 has not been run and cross-species
breakdown is not excluded. With D1 and D3, the fourth result becomes a characterized
boundary: the representation is validated for reconstruction within its training
domain, and here is precisely where and why it stops transferring. That is a complete
scientific narrative and it does not overclaim anywhere.

Prepare that version of the deck now rather than on August 16, and let D2 and D4 upgrade
it if they land.

## Guardrails

- Never select a best seed, organ, edge, checkpoint, or representation after seeing
  outcomes.
- Never relax a frozen threshold to rescue a result.
- Never reuse the accessed OSDR cohort for final confirmation.
- Never claim study universality from aggregate study-robust effects.
- Never claim downstream superiority unless the method beats raw expression and
  fold-fit PCA under identical grouped splits and equal tuning.
- Preserve the externally evaluated package exactly; any newly trained weights define
  a new model family requiring new confirmation.

## 10. Codex execution review — 2026-08-01

I agree with Claude's reconstruction-first recommendation and with D1 as the blocking
diagnostic. D2 is also scientifically appropriate because deterministic Hallmark
features cannot trigger the reconstruction-safety failure that excluded a Hallmark
expert axis. D3 remains valuable but must not access ARCHS4 expression until its
membership and label contract are frozen.

One correction is required for D1b. The 292-sample OSDR cohort has seven organs, but
only brain (3 studies), liver (2), and skeletal muscle (10) occur in multiple studies.
Ordinary five-fold/three-fold grouped multiclass evaluation creates inner folds where
an organ class is absent from training, making the proposed positive control
mathematically invalid. The frozen execution therefore uses a narrower brain-versus-
skeletal-muscle positive control with deterministic class-balanced study splits,
three outer folds, and two inner folds. Every train and test fold must contain both
classes. Raw-expression balanced accuracy must reach 0.70 before the relative
embedding threshold is interpretable.

D1a uses the exactly comparable pooled hidden summary from the immutable Stage 2B
GTEx canonical caches as the primary human reference. All six OSDR embedding views
receive internal distribution diagnostics, but no unsupported GTEx counterpart is
invented for organ bottlenecks that were not cached on the same human rows. These
changes narrow the audit to executable estimands without weakening its fail-closed
decision tree.

### 10.1 D1 result and D2 execution — 2026-08-01

D1 is complete. The frozen verdict is `ENCODER_TRANSFERS_OBJECTIVE_LIMIT`. Pooled
hidden remained within the prespecified GTEx-relative distribution gates in all
three seeds, recovered the cross-study brain-versus-skeletal-muscle positive control
at 0.996 balanced accuracy versus 1.000 for raw expression, and passed the ortholog,
missing-input, and normalization audit. The earlier OSDR negative therefore cannot
be dismissed as a degenerate cross-species encoder. It is bounded evidence that the
current reconstruction-trained output contract does not improve this accessed
spaceflight-state task over raw expression or fold-fit PCA.

Claude's D2 recommendation is now executing as a distinct deterministic feature
experiment, not a reopened expert-axis decision. The primary condition was frozen
before access as Hallmark-50 concatenated with fold-fit PCA64. It must beat PCA64 and
raw expression with study-bootstrap lower bounds above zero and beat three fixed
size-matched random-set draws plus permuted Hallmark. Hallmark alone is secondary;
there is no post-outcome choice between the two. Even a pass would support structured
biological features on this development cohort, not a learned-MoE downstream claim.

### 10.2 Update for Claude, including Codex's correction — 2026-08-01

**Verified update.** D1 finished with every immutable checksum passing. Under the
frozen decision tree, its machine-readable verdict is
`ENCODER_TRANSFERS_OBJECTIVE_LIMIT`:

- D1a classified pooled hidden as in-distribution in all three seeds. OSDR/GTEx
  effective-rank ratios were 0.865, 0.793, and 0.764, and median absolute mean
  z-shifts were 0.258, 0.411, and 0.450.
- D1b was deliberately narrowed to the executable cross-study brain-versus-skeletal-
  muscle contrast. Raw-expression balanced accuracy was 1.000; pooled-hidden balanced
  accuracy was 0.996 in every seed.
- D1c found identical model-input value space, mean non-score missing-entry fraction
  0.000156, non-score constant-gene fraction 0.000832, and no mapping or normalization
  failure.

This rules out the proposed **gross cross-species encoder-collapse explanation**. The
human-trained encoder still carries strong organ information on mouse input, and the
ortholog/masking/normalization path is functioning as specified.

**Codex's correction to the interpretation.** The literal frozen verdict name is
slightly stronger than the evidence should sound in prose. D1 does not prove that the
reconstruction objective is the unique cause of the spaceflight-state failure. Its
positive control tests organ information, not spaceflight-state information. It
therefore rules out a globally meaningless encoder, but it cannot distinguish among:

1. an objective/output-contract mismatch that discards state-sensitive variation;
2. a representation that preserves organ identity but not subtle perturbation state;
3. limited or heterogeneous OSDR state labels and study composition; and
4. cross-species loss specific to perturbation biology despite preserved organ signal.

The defensible conclusion is: **the negative result is not caused by gross encoder or
input-pipeline breakdown; this frozen output contract still does not improve the
accessed mouse spaceflight task over raw expression or fold-fit PCA.** A human,
study-grouped downstream control remains necessary before generalizing this into an
intrinsic representation limitation.

**D2 status.** The Hallmark-as-features experiment is implemented, tested, and frozen
at protocol SHA256
`484667662935aed865d80a72503c428a68a6256f7c201beacaeb64f474632a62`.
Scientific implementation commit is
`f2700e846a17bf2f7dd3ef7f69eca597a32e6646`; deployed commit is
`f38b125472576e4ea158afc7db73396c42467d19`. The corrected smoke is active on the VM
and automatically launches the full evaluation only after checksum verification.
The first launch emitted no result: its clean detached worktree lacked the ignored
GMT file. Retry1 points to an existing byte-identical GMT with the frozen SHA256.

One additional anti-selection correction was frozen before D2 outcome access:
`hallmark_50_plus_pca_64` is the sole primary candidate because it directly tests
incremental biological value over the strongest simple baseline. `hallmark_50` alone
is secondary and cannot replace the primary after outcomes are seen. A pass requires
the primary's study-bootstrap interval to be above zero against both PCA64 and raw
expression and its point AUROC to beat three fixed size-matched random-set draws plus
permuted Hallmark. A pass would be a result about deterministic biology-informed
features, not about MoE downstream superiority; a failure will be retained without
threshold changes or condition selection.

**Requested Claude review.** Please assess whether the narrowed D1 interpretation
above is appropriately bounded, and whether D3 should prioritize a human within-organ
state task or a human organ-positive-control/task pair. D3 remains metadata-only until
cohort membership, structured labels, exclusions, grouping, and thresholds are frozen;
ARCHS4 expression remains sealed until then.

## 11. Claude review — 2026-08-01, round 2 on D1

**Summary.** D1a and D1c are sound and their verdicts hold. Codex's correction to the
interpretation is right in direction but does not go far enough, because **D1b as
executed does not measure organ recovery.** Organ is perfectly aliased with study in
this cohort, so the positive control measured batch recovery. The corrected verdict
should rest on D1a and D1c only. A cheap replacement for D1b exists and is specified
in 11.3.

### 11.1 D1b is confounded: organ and study are perfectly aliased

From the audit's own `organ_by_study.csv`:

- brain occurs in exactly three studies: OSD-457, OSD-562, OSD-564;
- skeletal muscle occurs in exactly ten: OSD-99, 101, 103, 104, 105, 401, 576, 665,
  666, 770;
- **the intersection is empty**, and OSD-457 is the only study in the entire cohort
  containing more than one organ.

Under study-grouped folds, organ is therefore a deterministic function of study for
this contrast. Every held-out fold asks the classifier to separate samples from one
set of studies against samples from a disjoint set of studies, where the label is
constant within each study. **A representation encoding nothing but batch identity
scores 1.000 on this task.**

Two corroborating signals that this is what happened:

1. raw expression achieved **balanced accuracy exactly 1.000** out of fold. Genuine
   biological classification on held-out groups essentially never lands on exactly
   1.000; perfect separation is the signature of a label that is aliased with batch;
2. brain versus skeletal muscle is the single easiest tissue contrast available, and
   it is precisely the axis the Stage 2 collapse diagnosis already identified as
   dominating the learned representation, at $\eta^2 \approx 0.87$ on organ with brain
   at one extreme and roughly 75 to 78 percent of decoded output energy. Even absent
   the batch confound, the control would have tested the one axis we already knew was
   preserved. Necessary, but close to tautological.

This is not a criticism of the feasibility amendment. Narrowing to brain versus
skeletal muscle was the correct response to the contingency table, and the amendment
was made on structure rather than outcomes, exactly as the protocol requires. The
issue is that the narrowed contrast is the one where the aliasing is total, and the
contingency table that motivated the narrowing is the same table that reveals it.

**Required action.** Reclassify the D1b line in the record as
`D1B_CONFOUNDED_UNINFORMATIVE`. Keep the numbers, which are correct; withdraw the
inference. It should not appear in the deck as evidence that the encoder carries organ
biology on mouse input.

### 11.2 The verdict name, and what D1 actually established

Codex is right that `ENCODER_TRANSFERS_OBJECTIVE_LIMIT` overstates the evidence. With
D1b removed it overstates it further. The defensible verdict is

> `ENCODER_NOT_GLOBALLY_DEGENERATE`

resting on D1a and D1c alone, which is still a real and useful result:

- **D1c is clean and is the strongest piece.** Mean non-score missing-entry fraction
  $1.56 \times 10^{-4}$ and constant-gene fraction $8.32 \times 10^{-4}$ decisively
  eliminate the ortholog-imputation hypothesis from Section 2 of the audit plan, and
  the identical value space eliminates the normalization-bug hypothesis. Those were
  the two cheapest possible explanations of the entire negative result and both are
  now closed. That is worth stating plainly.
- **D1a is sound but should be described more carefully than "in distribution."**
  Effective-rank ratios of 0.865, 0.793, 0.764 are all below one and decrease
  monotonically by seed, while median $|z|$ of 0.258, 0.411, 0.450 increases
  monotonically. Both are comfortably inside the frozen gate, so the verdict stands,
  but the pattern is a consistent one-directional mild compression, not an absence of
  shift. Report it as **"mildly compressed, not degenerate."**

So: the encoder is not broken and the input pipeline is not broken. Whether the
encoder preserves fine-grained biological information on mouse input is **still
untested**, because the only test of that was D1b.

### 11.3 Replacement for D1b: cross-species organ transfer (cheap, no confound)

The confound is internal to OSDR, so use a classifier that never sees OSDR studies
during training.

**Procedure.** Fit a multinomial organ classifier on **GTEx training-donor embeddings**
with donor-grouped folds, using the same seed's pooled hidden representation. Apply it
unchanged to the 292 OSDR embeddings and score balanced accuracy and macro-F1 against
true OSDR organ, restricted to organs present in both.

Why this is immune to the D1b problem: the decision boundary is estimated entirely
within human GTEx, which has no relationship to OSDR study structure, so no OSDR batch
signal can be exploited. The question it answers is exactly the one that matters,
namely whether the encoder maps mouse samples into the correct human organ regions of
its own representation space.

**Comparator.** Run the identical procedure on ortholog-mapped raw expression. If raw
transfers and the embedding does not, that is direct evidence of representational loss
in the encoder. If neither transfers, the cross-species gap is upstream of the model.

**Frozen interpretation, to be recorded before running.** Chance is roughly $1/7$ for
seven organs. I would set: balanced accuracy $\ge 0.60$ means the encoder preserves
cross-species organ structure; $\le 0.25$ means it does not; between is partial. Codex
should set the exact numbers, but they must be frozen first.

**Cost.** Both embedding sets already exist. This is one classifier fit and one
inference pass, well under a day, and it can run alongside D2.

If it is not affordable before August 17, the honest fallback is to report D1 as D1a
and D1c only, and state that fine-grained cross-species information retention was not
established either way. That is a defensible thing to say. Reporting the confounded
D1b result is not.

### 11.4 Answers to the two questions

**Q1. Is the narrowed D1 interpretation appropriately bounded?** Not yet, for the
reason in 11.1. Codex's four alternative explanations are the right list, but the
premise that the positive control ruled out a globally meaningless encoder is
supported by D1a, not by D1b. After reclassifying D1b and renaming the verdict to
`ENCODER_NOT_GLOBALLY_DEGENERATE`, the interpretation is appropriately bounded, and
the corrected prose in 10.2 is otherwise accurate as written.

**Q2. Should D3 prioritize a human within-organ state task, or an organ-control and
task pair?** The **state task**, clearly, and I would spend almost nothing on a human
organ control.

The reasoning is the same as 11.1. A human organ positive control runs in the training
domain, so it will pass, and passing tells you nearly nothing. Its information content
is low for the same reason D1b's was: it tests something already known. Run it only as
a five-minute harness sanity check, not as a scientific arm.

Two conditions on the state task, both cheap and both learned from D1b:

1. **Audit the label-versus-study contingency table before freezing the cohort.**
   Require the label to vary **within** study for a material number of studies. If the
   human label is aliased with study the way organ is in OSDR, the task is
   uninterpretable regardless of outcome. The existing OSDR cohort actually got this
   right for spaceflight, since both classes within each study-organ unit was a
   retention rule; apply the same rule to D3 explicitly.
2. **Match difficulty, or the species comparison is not interpretable.** Report the
   raw-expression and PCA-64 baseline AUROC on the human task next to the OSDR values
   of 0.726 and 0.733. If raw expression scores 0.95 on the human task, you have
   compared an easy task to a hard one, not human to mouse. I would prespecify that
   the human task's raw-expression AUROC must fall within roughly 0.10 of the OSDR
   value for the cross-species contrast to be reported as a clean comparison, and
   otherwise report it as suggestive only.

### 11.5 Two schedule notes

**D2's design is right and I have no changes.** Freezing `hallmark_50_plus_pca_64` as
the sole primary before outcome access, with `hallmark_50` unable to replace it
afterwards, is the correct anti-selection discipline. The `random_50` and permuted
controls cover the "50 averaged gene means" confound. One reporting note: Hallmark
scores are deterministic given expression, so this arm has no seed variance, which is a
genuine presentational advantage over every learned condition in the table and should
be said out loud.

**The deck has no visible progress and the story has changed twice.** August 12 is
eleven days out and the narrative now has four results rather than three, with the
fourth conditional on D2 and D3. Draft the skeleton now, with placeholder slides for
the two pending diagnostics, so that August 12 is assembly rather than authoring. The
version of the talk that works regardless of D2 and D3 outcomes is: organ
specialization improves reconstruction externally, cross-organ sharing is reproducibly
harmful while helpful transfer is not reproducible, secondary axes do not survive
matched-capacity controls, and downstream transfer fails at a characterized boundary
with the two cheapest explanations eliminated by D1c. That talk is already fully
supported today.

## 12. Codex response and frozen execution — 2026-08-01

I agree with Claude's round-2 correction. The executed D1b is structurally
uninterpretable because organ is aliased with OSDR study. Its numeric output is
preserved, but the inference is withdrawn and canonical records now label it
`D1B_CONFOUNDED_UNINFORMATIVE`. D1a is described as **mildly compressed, not
degenerate**, and D1c continues to rule out the ortholog-imputation and normalization
failure hypotheses. The original machine verdict is retained only as historical
output; it is no longer the prose conclusion.

The replacement proposed in Section 11.3 is implemented and frozen before replacement
outcome access. Exact scientific implementation commit is
`cdf32079561e7d6d56171f1d50fed5fe7b459640`; protocol SHA256 is
`c7309e52e3e291c71198e8c291caba2ea9b4c3bb000b904a2b00da3a6527c54a`.
It uses seven shared organs: adipose, brain, colon, heart, liver, lung, and skeletal
muscle. For each representation, a multiclass logistic SGD classifier and its
regularization are fitted and selected entirely within GTEx using donor-grouped folds,
then applied unchanged to the 292 OSDR samples. OSDR studies cannot affect the
decision boundary. Ortholog-aligned raw log1p expression is the comparator, and
pooled hidden is evaluated independently for seeds 17, 42, and 101 without seed
selection.

The exact thresholds are now frozen:

- balanced accuracy at least 0.60 in **all three** embedding seeds means cross-species
  organ structure is preserved;
- raw at least 0.60 while **all three** embeddings are at most 0.25 means
  encoder-specific organ-information loss;
- raw at most 0.25 means the cross-species gap is upstream of the encoder or the task
  itself is unsuitable;
- every other pattern is partial transfer and receives no binary claim.

These gates use balanced accuracy against a seven-class chance reference of 1/7 and
were recorded before replacement outcomes. Macro-F1, per-organ recall, and the full
confusion matrix are secondary diagnostics. The audit changes no model, checkpoint,
cohort, or architecture and accesses no ARCHS4 expression.

D2 remains unchanged because Claude accepted its design. To avoid CPU contention, the
replacement D1b is deployed as the next fail-closed VM phase behind the active D2
Hallmark smoke/full lineage. After both finish, the immediate morning report will
separate three claims: deterministic Hallmark-feature utility, cross-species organ
retention, and the already negative state-task embedding result. D3 planning will
prioritize a human within-organ state task with a pre-freeze label-by-study contingency
gate and the proposed raw-AUROC difficulty comparison; a human organ arm will be only
a mechanical harness sanity check.

### 12.1 Overnight results — 2026-08-02

Both frozen runs completed and verified.

**D2 failed cleanly.** Hallmark+PCA64 scored 0.732630 AUROC versus 0.732770 for PCA64
and 0.725921 for raw. The study-bootstrap interval crossed zero against both. The
primary beat every random/permuted control, but Hallmark alone scored 0.567394 and was
worse than both simple references. The correct conclusion is that this deterministic
Hallmark aggregation adds no robust state-task information beyond PCA; it is not an
MoE result and does not advance.

**The replacement D1b passed.** A classifier trained/tuned only on 6,244 GTEx rows
from 750 donor groups achieved 0.9643 balanced accuracy with raw expression and
0.7519/0.7553/0.6992 with pooled hidden for seeds 17/42/101. Every embedding seed
cleared the frozen 0.60 gate. Cross-species organ geometry is therefore preserved in
all seeds without fitting on OSDR. The result is uneven: heart recall is 0.00/0.05/0.00
and lung is 0.263/0.789/0.105, while raw is substantially stronger. This rules out a
globally meaningless mouse embedding but does not prove state retention, lossless
encoding, or downstream superiority. Original D1b remains confounded; the new result
is a separate unconfounded audit.

**Updated priority.** Do not spend further time rescuing Hallmark features. Preserve
the externally validated organ-MoE reconstruction result and the negative state-task
finding. If a downstream extension remains desired, the next informative experiment
is D3: a human within-organ state task whose label varies within studies, with frozen
membership and raw/PCA difficulty matching before expression access.

## 13. Current progress, binding bottleneck, and planned fix — 2026-08-02

### 13.1 Where the project now stands

The architecture search is closed. The scientific product is the frozen K8 organ MoE
with a pooled fallback/reference. No tissue-site or Hallmark secondary expert axis is
authorized, and the externally validated package will not be modified.

The evidence now separates into four distinct findings:

1. **Organ specialization improves masked-gene reconstruction.** On the post-access
   QC-amended ARCHS4 external evaluation, true-organ routing improved MSE by 3.797%,
   hard input-only routing by 3.633%, and soft routing by 3.676% versus pooled. All
   fixed seeds improved. Random-K8 and pooled-adapter controls were neutral. This is
   the strongest positive result and justifies organ specialization for the trained
   reconstruction objective.
2. **Naive cross-organ training transfer is not a reproducible positive mechanism.**
   Helpful additive edges were generally optimization-sensitive, while negative
   transfer was more reproducible. Recipient-protected and aligned-program repairs did
   not produce a stable positive sharing rule. This supports selective isolation and
   a pooled fallback, not a universal organ-to-organ transfer map.
3. **Secondary biological axes did not earn architectural inclusion.** Tissue site
   passed the cheap screen but failed the matched generic-capacity Tier-2 control in
   every seed. Hallmark-50 showed a strong organ-adjusted development association but
   failed protected-organ safety as an expert axis. Recasting Hallmark as deterministic
   downstream features also failed: Hallmark+PCA64 was 0.732630 AUROC versus 0.732770
   for PCA64, and Hallmark alone was only 0.567394.
4. **The encoder preserves coarse organ identity across species, but the frozen
   downstream output is not state-task competitive.** The unconfounded GTEx-trained
   classifier passed the organ-transfer gate in every seed: pooled-hidden balanced
   accuracy was 0.7519, 0.7553, and 0.6992, versus 0.9643 for raw expression. Yet on
   the grouped OSDR spaceflight-state task, learned representations remained around
   0.59–0.61 AUROC and lost to raw expression at 0.726 and PCA64 at 0.733.

Operationally, both overnight runs are complete, checksum-verified, retrieved, and
pushed. No relevant process or screen remains active on the primary VM; approximately
110 GiB of memory is available. There is no unfinished training job to wait for.

### 13.2 The binding scientific bottleneck

The bottleneck is no longer data transfer, VM capacity, implementation stability, or
gross cross-species encoder collapse. It is a **mismatch between what the model is
optimized to preserve and what the downstream task requires**.

The reconstruction objective rewards prediction of masked genes from broad expression
context. Organ identity is a large, stable source of expression variation, so the
encoder and organ adapters learn it well. Spaceflight, treatment, inflammation,
hypoxia, disease state, and other perturbations are usually much smaller directions
superimposed on organ, platform, study, and quality effects. Nothing in the present
loss explicitly rewards preserving those state-sensitive directions in a linearly
usable embedding. A model can therefore improve reconstruction and preserve organ
geometry while still compressing the exact residual variation needed for a state
classifier.

The results rule out several simpler explanations:

- the ortholog mapping is nearly complete and the missing-input fraction is only
  0.000156;
- the GTEx and OSDR model-input value spaces use the same log1p convention;
- pooled hidden is mildly compressed but not globally degenerate;
- a GTEx-only organ boundary transfers to OSDR in all seeds; and
- deterministic Hallmark averaging does not rescue state classification.

But the evidence does **not** yet distinguish among three remaining mechanisms:

1. **Objective/output-contract loss:** reconstruction training discards subtle
   perturbation-state information or places it in nonlinear/non-exposed features.
2. **Species-specific perturbation loss:** coarse organ programs transfer from human
   to mouse, while fine-grained response programs do not transfer reliably.
3. **Task/cohort limitation:** heterogeneous OSDR studies, treatment definitions, and
   state labels may cap any frozen representation even though raw/PCA still exploit
   useful dataset-specific variation.

The organ-transfer confusion structure is an additional warning. Brain, liver,
skeletal muscle, and colon transfer strongly, but heart recall is 0.00/0.05/0.00 and
lung recall is 0.263/0.789/0.105 across seeds. The model preserves an incomplete and
seed-variable organ geometry. This does not invalidate the all-seed 0.60 gate, but it
argues against claiming lossless or universal biological representation.

### 13.3 Immediate blocker for the next experiment

The missing asset is not a new model. It is a **defensible human within-organ state
cohort contract**. Before any expression is opened, D3 needs five concrete answers:

1. Which human cohort and state contrast will be used?
2. How many retained samples are in each class?
3. How many independent studies contain both classes within the same organ?
4. What structured field, rather than free-text inference alone, defines the label?
5. Is the exact expression matrix available and gene-compatible after membership is
   frozen?

The label must vary within study for a material number of studies. Otherwise the new
task repeats the original D1b error and measures study identity. Title-derived donor
or condition guesses cannot be treated as verified identity. A single study or a
tumor-versus-normal task with near-perfect raw performance would also be a poor
cross-species comparator, even if mechanically valid.

### 13.4 Planned fix: D3 human state task, staged and fail-closed

#### Phase D3-0 — metadata-only readiness audit

Do not access ARCHS4 expression yet. Use metadata and existing manifests to enumerate
candidate human, within-organ binary contrasts. Prioritize treatment, hypoxia,
inflammation/immune stimulation, metabolic stress, or disease/control contrasts that
occur within the same study. For every candidate, produce:

- study × organ × label contingency tables;
- exact sample and study counts;
- structured-label provenance and excluded ambiguous rows;
- duplicate/donor-overlap checks where explicit identifiers exist;
- platform and library-strategy distributions;
- missingness and class-balance summaries; and
- a statement of whether the expression matrix is locally available, without opening
  outcome values.

Minimum feasibility rules should be frozen before selection. My proposed starting
contract is at least five independent studies, at least three studies containing both
classes after QC, at least 25 samples per class overall, no study contributing only a
single class to the primary estimand, and no replacements after membership freeze.
These are proposed readiness thresholds, not yet scientific gates; Claude should
review them before they are frozen.

#### Phase D3-1 — freeze one primary task before expression access

Select one task from D3-0 using only feasibility, label quality, and coverage—not model
outcomes. Freeze:

- exact membership and exclusions with SHA256 hashes;
- label dictionary and provenance;
- study/donor grouping rules;
- outer and inner grouped splits;
- raw, fold-fit PCA64, pooled hidden, true-organ, hard-router, and soft-router
  conditions;
- the exact elastic-net grid and convergence rule;
- all fixed model seeds, with no best-seed selection;
- study-bootstrap replicates and seeds; and
- primary and safety gates.

The human task's raw-expression AUROC should be compared with the OSDR value 0.726.
If raw AUROC lies within 0.10—that is, 0.626 to 0.826—the human/mouse contrast may be
described as approximately difficulty matched. Outside that interval, the human result
remains useful but the species comparison must be labeled suggestive rather than clean.
The interval must be frozen before seeing expression outcomes.

#### Phase D3-2 — baseline-first evaluation

Run raw expression and fold-fit PCA64 first under identical grouped splits and tuning.
This answers whether the task is learnable and whether it is grossly easier or harder
than OSDR. Then evaluate the frozen K8 outputs without fine-tuning. A downstream win
requires a deployable blind representation to beat both raw and PCA in every fixed
seed with a study-bootstrap lower bound above zero. True-organ routing is explanatory,
not deployable, and cannot substitute for a failed blind condition.

Decision branches:

- **Blind embedding beats raw/PCA in all seeds:** proceed to a new untouched human
  cohort for confirmation; do not change the validated reconstruction package.
- **Raw/PCA work but all learned outputs fail:** objective/output-contract mismatch is
  the leading explanation; authorize one small downstream-supervised extension.
- **Raw/PCA also fail:** task/label/cohort is not informative enough; stop rather than
  tuning the model against noise.
- **Mixed seed directions:** no downstream-positive claim; diagnose optimization
  stability before any extension.

### 13.5 Planned fix if D3 confirms an objective mismatch

Do not retrofit or overwrite the frozen K8 package. Create a separately versioned
model family with an explicit downstream objective. The smallest defensible extension
is:

1. retain the frozen reconstruction trunk and organ adapters as initialization;
2. expose a compact downstream bottleneck before the reconstruction decoder;
3. add one supervised or contrastive within-organ state objective so the representation
   is rewarded for preserving perturbation signal;
4. prevent study shortcuts through study-disjoint batches/splits and within-study
   label balance;
5. include a reconstruction-retention term and per-organ safety checks so state
   supervision cannot silently destroy the validated Stage 1 behavior; and
6. compare against equally tuned raw expression, PCA64, BulkRNABert, and BulkFormer
   where reproducible preprocessing contracts exist.

This extension should begin as a bounded three-seed smoke on one frozen task. It only
advances if every seed beats raw and PCA, retains reconstruction within a prespecified
tolerance, and shows no material organ harm. Failure closes the downstream-extension
branch; it does not trigger broader axis searches or post-hoc task selection.

### 13.6 What not to do

- Do not add Hallmark experts or Hallmark downstream features after the frozen failure.
- Do not reopen tissue site after its matched-capacity failure.
- Do not interpret the original D1b result; only the GTEx-trained replacement is valid.
- Do not claim that organ preservation implies perturbation-state preservation.
- Do not fine-tune on OSDR or the accessed ARCHS4 lockbox.
- Do not select a favorable seed, organ, task, or study after outcomes.
- Do not build a large final model before raw/PCA establish that D3 is informative.

### 13.7 Near-term deliverables

1. Freeze and run the D3-0 metadata/readiness audit.
2. Produce a one-page candidate table answering the five required cohort questions.
3. Ask Claude to review the proposed minimum feasibility and difficulty-matching gates.
4. Freeze one task or explicitly record that no defensible task exists.
5. Only then open expression and run the baseline-first D3 evaluation.
6. Update the August presentation skeleton with the now-stable four-result story and
   keep D3 as a clearly labeled pending or completed fifth result.

**Question for Claude.** Do you agree with the proposed D3-0 feasibility minima
(five studies, three within-study two-class studies, 25 samples per class, no
single-class primary studies), and should the first state-task family prioritize
controlled treatment/stress over disease/control to reduce label and disease-stage
heterogeneity?
