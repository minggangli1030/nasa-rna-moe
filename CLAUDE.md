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
