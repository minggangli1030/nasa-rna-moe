# Post-D2 roadmap: what remains testable, and what to execute

**Written:** 2026-08-02
**Review input:** [`../CLAUDE.md`](../CLAUDE.md) Sections 13 and 14
**Horizon:** August 17 deliverable, plus a post-deadline research program
**Status:** Phase 1 complete; all frozen downstream gates failed; Phase 2 is
metadata-readiness only until a defensible cohort contract exists

---

## Part 0. Is there still hope? An honest assessment

Asked directly, so answered directly. The answer differs sharply depending on which
question is meant, and the project has been conflating two of them.

### 0.1 The question being asked is not the project's actual claim

Two distinct questions have been merged:

- **Q-A: does the learned representation beat raw expression and fold-fit PCA?**
- **Q-B: does organ specialization beat pooling, holding representation type fixed?**

Q-A is the deployment question and it is the frozen guardrail, correctly. Q-B is the
**scientific claim of the entire project**, and it is a matched comparison between two
things compressed the same way through the same trunk.

Q-A is currently poorly identified on OSDR for a structural reason, not merely a
modeling reason. Per Section 14.1, skeletal muscle is the dominant and only adequately
powered organ-specific signal, where raw expression already reaches 0.989. There is
almost no headroom. Outside muscle, pooled raw expression sits at 0.532. Heart and lung
have high descriptive raw AUROCs but only 40 and 19 samples, respectively, so the
stronger claim that muscle is literally the only detectable signal is not supported
without intervals. The benchmark is nevertheless dominated by one nearly saturated
contrast. **This is primarily a ceiling-and-power problem, and additional modeling on
the same benchmark cannot resolve it.**

Q-B is answerable and has never been reported as its own estimand with intervals.
From the frozen out-of-fold predictions:

| Comparison | Seed 17 | Seed 42 | Seed 101 |
|---|---:|---:|---:|
| true-organ embedding minus pooled hidden | $+0.046$ | $-0.011$ | $-0.061$ |
| hard router minus pooled hidden | $+0.005$ | $+0.014$ | $-0.074$ |
| soft router minus pooled hidden | $+0.032$ | $+0.019$ | $-0.100$ |

Two of three seeds positive, one strongly negative, no interval reported anywhere. On
the earlier score-panel evaluation the same comparison was flat to slightly negative.
So the honest current status of Q-B is **inconclusive, not refuted**, and it has never
been given a proper estimand, a paired study bootstrap, or a per-organ breakdown.

**Recommendation: make Q-B the primary downstream estimand from here forward.** Keep
Q-A as the mandatory deployment gate it already is, but stop treating failure on Q-A as
if it answered Q-B. They are different claims and only one of them is what the project
set out to test.

### 0.2 Where hope actually lies, with priors

My subjective probabilities, stated so they can be held against outcomes later.

| Hypothesis | Prior | Reasoning |
|---|---:|---|
| MoE beats raw/PCA on full-label OSDR | **~10%** | Ceiling effect in muscle, floor everywhere else. Structurally near-impossible |
| Organ-conditional **residuals** beat within-organ-centered raw | **~20%** | Untested and mechanistically motivated, but residuals are a transformation of raw, not new information |
| Specialization beats pooling in the **low-label** regime | **~45%** | The strongest remaining avenue. Compact representations win when $n \ll p$, and this is entirely untested |
| Specialization helps on a better-chosen **human** task | **~35%** | Scientifically the right question, but the cohort does not exist yet |
| The current frozen output contract yields a general-purpose representation | **<5%** | Three independent output contracts have now failed |

The last row is why the claim split in Section 4 of the brief is right. The third row is
why the project is not finished.

### 0.3 The two untested ideas that deserve the remaining time

**Idea 1: the residual is the natural downstream output, and it was never tested.**
Every representation evaluated so far has been a *predicted* quantity: reconstructed
score panel, pooled hidden state, adapter bottleneck, router probabilities. The
quantity an organ MoE is uniquely positioned to produce is the **residual**, meaning
observed minus organ-expert-predicted. That is, by construction, "what this sample does
that its organ does not normally do," which is a definition of perturbation state.

And it is exactly where a reconstruction gain should convert into downstream value: a
3.8% better organ-conditioned expectation means a residual that is more purely
deviation from the organ norm and less contaminated by organ identity.

The honest null, which must be run alongside, is **raw expression centered within
fold-fit organ means**. If the MoE residual does not beat that, then organ
specialization is worth no more than subtracting a group mean, which is the sharpest
possible statement of the negative and far more informative than "loses to PCA."

**Idea 2: the low-label regime has never been examined and is where representations
earn their keep.** At $n = 139$ retained muscle samples with roughly 20,000 genes,
elastic net on raw expression is operating deep in the $n \ll p$ regime where
regularization does the work. At 10 or 20 labels it would degrade sharply, while a
64-dimensional embedding would not. Learning curves are standard practice for
representation evaluation, they are cheap, and their absence is the largest remaining
gap in the evaluation.

### 0.4 What I would tell the mentor

Specialization is established for reconstruction and is not established for downstream
tasks. The reason it is not established is now specific rather than vague: the
available downstream cohort has exactly one informative organ, and in that organ the
simplest possible baseline is already at 0.989, so there is nothing to improve on. That
is a property of the benchmark, not a verdict on the method. The remaining honest
avenues are the low-label regime and a better-chosen task, both of which are named
below with pre-registered gates.

---

## Part 1. Phase 1, execute August 2 to 5, one frozen protocol

All four experiments run on **existing frozen artifacts**. No retraining, no new
cohort, no checkpoint change. Freeze them together in a single protocol JSON with one
recorded SHA256 **before** any outcome access, so that no experiment can be selected
after seeing another.

**Status of everything in Phase 1:** prespecified secondary analysis on an accessed
development cohort. It can characterize, localize, and correct interpretation. It
cannot confirm. Label every output accordingly.

### E1. Muscle-only evaluation (highest priority)

**Rationale.** Section 14.1 shows this is the comparison the project has been making
without knowing it. Running it explicitly gives a powered single-organ result instead
of an aggregate that averages one real effect against six nulls.

**Procedure.** Rerun the existing frozen harness restricted to skeletal muscle: 139
samples, 10 studies, study-grouped, identical grid, identical fold counts, all
conditions and both baselines. Reuse `nested_group_evaluate` unchanged.

**Report.** AUROC per condition per seed, paired study-bootstrap intervals against both
`pooled_hidden` (Q-B) and `raw_expression`/`pca_64` (Q-A), reported as two separate
estimands.

**Note the expected ceiling.** Raw is at 0.989 here. State in advance that Q-A cannot
be won in this organ and that E1's purpose is Q-B plus a precise characterization of
how much state signal the representation retains.

### E2. Organ-conditional residual representation

**Rationale.** Idea 1 in 0.3. Never tested, mechanistically the most natural output of
an organ MoE.

**Inputs, all cached.** `feature__<condition>` arrays from
`cache_stage1_osdr_downstream_features.py` are the predicted score panels for `pooled`,
`true_organ`, `blind_router_hard`, `blind_router_soft`. Observed score-gene expression
is available from the same cohort build.

**New representations.**

1. `residual_pooled` $= y_{\text{score}} - \hat{y}_{\text{pooled}}$;
2. `residual_true_organ`;
3. `residual_hard_router`;
4. `residual_soft_router`.

**Mandatory baselines, and E2 is meaningless without them.**

5. `score_panel_within_organ_centered`: observed score-panel expression minus fold-fit
   organ means, providing the dimension-matched raw null;
6. `full_raw_within_organ_centered`: full raw expression minus fold-fit organ means, where the
   organ means are estimated **on training folds only** and applied to test folds. This
   is the deployment-scale centered null;
7. `raw_expression` and `pca_64` unchanged.

**Frozen gate.** A specialization benefit requires the same fixed specialized residual
to beat both `residual_pooled` and `score_panel_within_organ_centered`, in all three
seeds, with paired study-bootstrap lower bounds above zero. A separate deployment gate
requires a blind residual to beat full raw-centered expression, raw expression, and
PCA-64; the two questions must not be conflated.

**Interpretation if it fails.** Organ specialization is worth no more than subtracting
organ group means for this task. Record that sentence; it is a clean, quotable, and
scientifically meaningful negative.

### E3. Low-label learning curves

**Rationale.** Idea 2 in 0.3. The regime where compact representations are expected to
win, and entirely unexamined.

**Procedure.** Subsample labeled training data within each outer fold at 5%, 10%, 25%,
50%, and 100%, selecting paired classes within randomly ordered training studies and
using at least three studies. Use two grouped inner folds at the low-label points and
fail closed if either class or grouped tuning is infeasible. Ten fixed subsample seeds
per point are recorded in the protocol. Evaluate `raw_expression`, `pca_64`,
`pooled_hidden`, `true_organ_embedding`, and both router embeddings. Run on the
muscle-only cohort from E1, since it is the only organ with a signal to learn.

**Report.** Mean and interval across subsample seeds at each label fraction, per model
seed. Plot AUROC against labeled sample count.

**Frozen gate.** A low-label advantage requires a learned representation to beat
`raw_expression` at the 5% and 10% points with intervals above zero in all three model
seeds. Crossing at low label counts while losing at 100% is a **legitimate and
reportable result**, and it is the outcome I consider most likely if any positive
exists. Prespecify that so it cannot look like post-hoc rescue.

**Completed result.** No gate passes. Raw/PCA mean AUROC is 0.629/0.633 at the nominal
5% floor and 0.731/0.720 at 10%, while learned representations span 0.489-0.525 and
0.507-0.534. Every learned-minus-raw mean delta is negative in every model seed, and
all 10% intervals are below zero. The current downstream-output-contract branch is
closed.

### E4. Q-B as a first-class estimand

**Rationale.** 0.1. This is pure analysis of frozen predictions, costs minutes, and
gives the project its actual scientific claim in reportable form.

**Procedure.** For every existing evaluation, compute specialization-minus-pooling
deltas with paired study-bootstrap intervals: true-organ, hard router, and soft router
each against `pooled_hidden`, and the same for the earlier score-panel conditions
against `pooled`. Report pooled across organs and within skeletal muscle and brain
separately. Do not report organs with $n < 20$.

**Report exactly.** Per seed, never a mean that hides the seed-101 reversal.

---

## Part 2. Phase 2, August 6 to 10, D3 human task

Proceed only if the D3-0 readiness audit clears the revised minima in CLAUDE.md 14.6:
at least 10 two-class studies in the primary estimand, at least 80 samples per class,
at least 200 retained samples, at least 60 in the primary organ, no single-class
primary studies, and the label varying within study.

Prioritize **controlled treatment or acute stress** over disease versus control, for
the three reasons in 14.6.

**Difficulty matching is against the within-organ value, not the pooled 0.726.** Report
the human task's raw-expression within-organ AUROC beside 0.989 for muscle. If the
human contrast cannot reach a comparable within-organ effect size, report the species
comparison as suggestive only and say so on the slide.

**Hard stop.** If the readiness audit fails the minima by August 6, do not build a
weaker cohort to have something to show. Record the infeasibility as a result, and
present D3 as the specified first experiment of the future program. A written,
pre-registered, unexecuted protocol is a credible deliverable; a rushed underpowered
cohort is not.

---

## Part 3. Phase 3, August 11 to 17, consolidation

- Aug 11 to 12: freeze all figures. Write the Stage 1 confirmation cohort contract
  from brief Section 4, Track A, as a pre-registered unexecuted artifact.
- Aug 12 to 15: build the deck.
- Aug 16: correction only. No new analysis, no new selection.
- Aug 17: deliver.

**The talk that is fully supported today**, before any Phase 1 result lands:

1. organ specialization improves masked-gene reconstruction on external human data,
   3.797% true-organ and 3.633%/3.676% under automatic routing, all seeds;
2. cross-organ sharing is reproducibly harmful while helpful transfer is not
   reproducible, 0 of 8 stable helpful against 2 of 8 stable harmful;
3. secondary axes do not survive matched-capacity controls, with tissue site as the
   worked example;
4. downstream transfer fails at a characterized boundary: the encoder preserves
   cross-species organ geometry at 0.70 to 0.76 balanced accuracy against $1/7$ chance,
   the ortholog-imputation and normalization explanations are eliminated by D1c,
   skeletal muscle contains the dominant and only adequately powered signal, and the representation
   retains roughly half of it.

Phase 1 upgrades slide 4 and adds the Q-B estimand. Nothing in Phase 1 is required for
the talk to be coherent.

---

## Part 4. Beyond August 17

Two tracks, in priority order. Neither is startable before the deadline.

### Track A: pristine reconstruction confirmation

Highest value per unit risk, because it confirms the result that already works.
Study-disjoint ARCHS4 partition with no overlap against the 63 studies used in the
Stage 1 external evaluation, or recount3. Contract written and frozen before August 17,
executed after. Nothing about the frozen package changes.

### Track B: supervised downstream extension

Only if downstream utility remains a goal, and only as a **separately versioned model
family**. The design in brief Section 13.5 is sound. Three additions from what has been
learned since:

1. **Choose the benchmark before the model.** The single largest failure in the
   downstream work was evaluating on a cohort where the simplest baseline is at 0.989
   in the only informative organ. Require, before any training, a task where raw
   expression lands between roughly 0.65 and 0.85, so that improvement is possible and
   measurable.
2. **Make the residual an explicit output.** If E2 shows any signal, expose the
   organ-conditional residual as a first-class model output rather than a diagnostic.
3. **Report Q-B and Q-A separately and always.** Specialization versus pooling is the
   scientific claim; beating raw and PCA is the deployment gate. Conflating them is
   what produced a negative result that took three rounds of review to interpret.

---

## Part 5. What would change my mind

Recorded now so it cannot be rationalized later.

- If E3 shows learned representations crossing above raw expression at 5% and 10%
  labels in all three seeds, the representation has demonstrable value in the regime
  that matters for scarce-label biology, and Track B becomes worth real investment.
- If E2's residual beats within-organ-centered raw, organ specialization contributes
  beyond group-mean removal and the reconstruction-to-downstream link is live.
- If E4 shows Q-B positive with intervals above zero in all seeds on the muscle cohort,
  specialization helps downstream even though neither arm beats raw, which is a
  publishable and honest claim.
- If all three fail, the negative is complete, characterized, and worth stating
  strongly, and the project's contribution is the reconstruction result plus a
  well-documented boundary. That is a good outcome for a project of this scope and
  should not be presented as a disappointment.
