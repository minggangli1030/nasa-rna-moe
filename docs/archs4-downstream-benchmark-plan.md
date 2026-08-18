# ARCHS4 human downstream benchmark: plan

**Written:** 2026-08-04
**Status:** design proposal for the post-August-17 program. Nothing here executes
before the presentation.
**Relationship to existing work:** does not modify the frozen K8 package, does not
reopen the closed secondary-axis question, does not touch the Stage 1 external lockbox.

---

## 1. Why this is a fair retest and OSDR was not

The OSDR result could not answer whether organ specialization helps downstream, for
three specific reasons. This design removes all three.

| OSDR problem | Effect | How this design fixes it |
|---|---|---|
| Mouse data through a human-trained encoder | Domain shift confounds representation quality | ARCHS4 is human, same species as training |
| One informative organ, raw expression at 0.9675 there | No headroom; a perfect model could only tie | Headroom gate applied **within the primary organ** before commitment |
| 292 samples, 18 studies, six near-null organs | Noise band of roughly $\pm 0.08$ swamps any effect | Minimum 200 samples, 10 two-class studies, 60 in the primary organ |

**The design is built so both outcomes are publishable.** If a pre-registered candidate
clears every gate and organ specialists win, that is the downstream result the project
has been looking for. If ten pre-registered candidates are searched under frozen rules
and none clears, that is a substantially stronger negative than OSDR alone: it says a
large public human corpus was searched under discipline and no task was found where
reconstruction-pretrained organ specialists beat simple baselines. Both versions are
worth presenting; only the second is currently available.

**Honest prior.** I put roughly 25 to 30% on the frozen model winning here. The
low-label result, where learned representations made the signal *less* linearly
accessible than the raw input under a matched probe family, is evidence against, and it
is not benchmark-dependent. A failure here would license the supervised extension as
the correct next step rather than leaving it speculative.

---

## 2. What is compared

The user's framing was "compare against a general model with same or similar
parameters." There are two different general models and they answer different
questions. Both are required.

| Arm | What it is | Question it answers |
|---|---|---|
| **Organ K8, blind routing** | frozen package, input-only soft/hard router | the deployable claim |
| **Organ K8, revealed organ** | frozen package, true organ label | mechanistic upper bound |
| **Pooled adapter** | one adapter, matched active width, samples, updates | does splitting help at matched active compute? |
| **Generic K8 bank** | eight adapters, no biological structure, matched total parameters | does splitting **by organ** help, versus splitting arbitrarily? |
| **Raw expression** | elastic net, equal tuning budget | mandatory deployment baseline |
| **Fold-fit PCA-64** | elastic net, equal tuning budget | mandatory deployment baseline |

**The generic K8 bank is what makes a positive result interesting**, and it should be in
from the start rather than deferred. Without it, a win reads as "eight adapters beat one
adapter," which is a capacity claim. With it, a win reads as "organ-structured eight
adapters beat unstructured eight adapters," which is a biology claim. The scale curve
currently carries exactly this limitation and it is the first thing a reviewer will ask
about.

For the generic bank, use the two-control design from CLAUDE.md 19.4 Q3:
expression-cluster K8 as the deployable arm, with adjusted Rand index against the organ
partition reported, plus organ-balanced random K8 under revealed assignment as the
capacity-isolation upper bound.

**Report Q-A and Q-B separately and always.** Q-A is whether the organ model beats raw
and PCA. Q-B is whether it beats its matched pooled or generic control. Conflating them
is what made the OSDR negative take three review rounds to interpret.

---

## 3. Phase 1: build the candidate catalog (metadata only, 1 to 2 days)

**No expression is loaded in this phase.**

The infrastructure exists. `data/archs4/current/human_gene_v2.latest.h5` is local at
58 GB, and `preprocessing/export_archs4_sample_metadata.py` already exports
`geo_accession`, `series_id`, `source_name_ch1`, `title`, and `characteristics_ch1`.

Steps:

1. Export sample metadata for all human samples.
2. **Apply the lockbox filter first.** Exclude every `series_id` used in the Stage 1
   external evaluation, all 63 studies. Record the exclusion list and its hash. Also
   exclude anything overlapping GTEx donors.
3. Map `source_name_ch1` and tissue fields onto the eight organ labels using the
   existing frozen ontology in `data/ontology/`. Samples outside the eight organs are
   dropped, not reassigned.
4. Within each organ, group by `series_id` and parse `characteristics_ch1` for
   candidate binary contrasts: treated versus control, timepoint, exposure, disease
   state, intervention.
5. Emit a catalog table: one row per (organ, series, candidate contrast) with sample
   counts per class.

---

## 4. Phase 2: labeling rules and validation (2 to 3 days)

This is the real work and the place where the experiment most easily goes wrong. GEO
`characteristics_ch1` is unstructured submitter text. **Label noise directly caps
achievable AUROC, so sloppy labeling manufactures a false negative**, which would look
exactly like the result we already have.

Protocol:

1. For each candidate contrast, write a **deterministic extraction rule**, a regex or
   keyword rule over the metadata fields. No model-based labeling in the primary path.
2. **Hand-validate 50 samples per candidate**, drawn at random, before the candidate is
   eligible. Require at least 95% agreement between the rule and the hand label.
   Candidates below 95% are either rewritten once or dropped, and the decision is
   recorded before any expression access.
3. Record inter-rule ambiguity: samples matching both classes or neither are excluded,
   never guessed.
4. Freeze the rule text and its hash alongside the candidate.

An LLM-assisted first pass is acceptable **for proposing** rules and for triaging the
catalog, but the rule that produces the final labels must be deterministic and
inspectable, and the hand validation is not optional.

---

## 5. Phase 3: freeze the ranked candidate list (1 day)

With thousands of eligible studies, free-form searching would guarantee a false
positive eventually. The discipline that makes a large corpus an advantage rather than
a hazard:

1. Rank candidates by **metadata-only** criteria: study count, samples per class,
   within-study label variation, primary-organ sample count, biological interest.
   Never by any measured outcome.
2. Freeze the ranked list of exactly ten candidates in a protocol JSON with a recorded
   SHA256, before any expression is loaded.
3. Evaluate sequentially. **Stop at the first candidate that clears every gate.**
4. Record every rejected candidate with its measured values. Rejected candidates are
   ineligible for later confirmation use.

Minimum eligibility, from CLAUDE.md 12.2 Q2 and 14.3:

| Requirement | Value |
|---|---|
| two-class studies in the primary estimand | $\ge 10$ |
| samples per class | $\ge 80$ |
| total retained samples | $\ge 200$ |
| samples in the primary organ | $\ge 60$ |
| studies per class within the primary organ | $\ge 3$ |
| single-class studies in the primary estimand | none permitted |
| label varies within study | required |

That last requirement is not bureaucratic. In the OSDR cohort, organ was a
deterministic function of study, which meant a positive control I proposed measured
batch recovery rather than biology. Any candidate where the label is aliased with
`series_id` is uninterpretable regardless of outcome.

---

## 6. Phase 4: sequential evaluation

For each candidate in frozen order:

**Step 1, headroom, measured within the primary organ.** Run raw expression and
fold-fit PCA-64 only. Acceptance band $0.60 \le \text{AUROC} \le 0.90$, applied to the
primary organ, not to a pooled number.

This is the gate whose absence produced the OSDR situation. Pooled raw AUROC on OSDR
was 0.726, comfortably inside any reasonable band, while muscle-only raw was 0.9675.
**A pooled headroom gate would have admitted OSDR.** Additionally, reject if any
adequately powered organ exceeds 0.90 even when the pooled value is in band, because
that is precisely the OSDR pattern.

**Step 2, full ladder.** Only if step 1 passes. All six arms from Section 2, identical
study-grouped nested folds, identical elastic-net grid, identical tuning budget,
recorded as an exact configuration count rather than described in prose. Three model
seeds, no best-seed selection.

**Step 3, report.** Per-organ from the first analysis, never on request. Paired
study-bootstrap intervals for both Q-A and Q-B. Low-label learning curves at 5%, 10%,
25%, 50%, 100%, since that regime is where a compact representation should earn its
keep and where the current evidence is most damaging.

**Advance gates.** A downstream claim requires, in every seed:

- blind organ-aware beats raw expression and fold-fit PCA, with study-bootstrap lower
  bound above zero (Q-A);
- blind organ-aware beats both the pooled adapter and the generic K8 bank (Q-B);
- no organ harmed beyond the frozen safety tolerance;
- routing noncollapsed;
- shuffled-label and matched-capacity controls do not reproduce the gain.

**Reserve an untouched confirmation split before any of this runs.** Development
evidence on an accessed cohort cannot be a final claim, which is the same rule that
applies to OSDR now.

---

## 7. Cost and sequencing

| Phase | Duration | Blocking? |
|---|---|---|
| 1, catalog | 1 to 2 days | yes |
| 2, labeling and hand validation | 2 to 3 days | yes |
| 3, freeze ranked list | 1 day | yes |
| 4, first candidate: expression extraction, headroom, ladder | 3 to 4 days | |
| each additional candidate | 2 to 3 days | |

Roughly two weeks to a first verdict, plus two to three days per rejected candidate.
Phases 1 to 3 require no GPU and no expression access, so they can begin the day after
the presentation without contending for compute.

---

## 8. What this does not do

- It does not retrain the model on ARCHS4. The frozen K8 package stays frozen and this
  evaluates its existing outputs. Retraining is a different and much larger project.
- It does not reopen secondary axes. That question is closed.
- It does not substitute for Track A, the untouched reconstruction confirmation, which
  remains the highest-value and cheapest credibility item.
- It does not become a supervised extension. If the frozen outputs fail here, on a
  benchmark chosen for headroom in the right species with adequate power, **that is the
  definitive closure of the frozen-output branch**, and it licenses the supervised
  extension as an evidenced next step rather than a speculative one.

---

## 9. Risks, named in advance

1. **Label noise masquerading as a negative.** Mitigated by the 95% hand-validation
   floor. If validation cannot reach 95% for any candidate, report that as the finding:
   public metadata is insufficient for a clean contrast in the eight organs.
2. **All ten candidates saturated or null.** Plausible. Many easy public contrasts, such
   as tumor versus normal, sit above 0.90. The catalog should deliberately over-sample
   subtle interventions rather than gross disease states.
3. **Study confounding.** Handled by the within-study variation requirement, and it will
   shrink the eligible pool substantially. Expect to lose most candidates here.
4. **Searching until something works.** Handled by the frozen ranked list, sequential
   stopping, and recorded rejections. This is the discipline that turns corpus size from
   a hazard into an advantage.
5. **The generic K8 control is expensive.** It requires training eight unstructured
   adapters at matched capacity. Worth it, because without it a positive result is a
   capacity claim rather than a biology claim.

---

## 10. The actual candidate tasks

Sections 3 to 6 specified the machinery without naming the tasks, which was a gap.
This section names them.

Two task families are proposed, and they have deliberately opposite risk profiles. Run
both. One is likely to produce a clean result with modest novelty; the other is
unlikely to produce a result but is the one worth having.

### 10.1 Family A: within-organ state classification

All candidates are **within-organ**, because the model's specialization is
organ-conditioned and a cross-organ task would be answered by organ identity alone.

The binding constraint is **within-study label variation**, which strongly favors
paired designs where the same subject contributes both classes. The headroom gate
rejects both saturated and null contrasts, so the list deliberately over-samples
subtle-but-real biology and avoids dramatic disease-versus-healthy contrasts that will
sit above 0.90.

| Rank | Organ | Contrast | Design | Why ranked here | Main risk |
|---:|---|---|---|---|---|
| 1 | Colon | IBD inflamed vs uninflamed mucosa | paired within patient | Paired by construction, many studies, moderate effect size | inflammation may be strong enough to saturate |
| 2 | Skin | Atopic dermatitis lesional vs non-lesional | paired within patient | Same paired advantage, less extreme than psoriasis | still may saturate |
| 3 | Muscle | Disuse, bed rest, or immobilization pre vs post | paired within subject | Direct spaceflight analogue, matches the one signal the project has observed | few studies; aggregate count is the open question |
| 4 | Lung | Smoking status in airway epithelium | case-control within study | Large literature, genuinely moderate effect, studies recruit both arms | tissue mapping to the lung expert |
| 5 | Muscle | Acute exercise pre vs post biopsy | paired within subject | Most studies of any muscle contrast, guaranteed pairing | effect is large; saturation likely |
| 6 | Adipose | Weight-loss or dietary intervention pre vs post | paired within subject | Paired, moderate effect | smaller study counts |
| 7 | Liver | NAFLD steatosis present vs absent | case-control within study | Well represented, gradable severity gives a middle band | severe disease arms saturate |
| 8 | Colon | Anti-TNF responder vs non-responder | case-control within study | Clinically valuable, genuinely subtle, typically 0.60 to 0.75 | hardest to reach the sample minima |
| 9 | Muscle | Insulin resistance or T2D vs control | case-control within study | Reasonable counts, moderate effect | subject-level confounding with age and BMI |
| 10 | Brain | Alzheimer's vs control | case-control within study | Many studies | region heterogeneity; often single-class per study |

Deliberately excluded, with reasons recorded so the exclusions are not silently
revisited:

- **any tumor versus adjacent normal**, in any organ. Near-separable, will fail the
  headroom gate at the top end, and it is the exact failure mode that made OSDR muscle
  uninformative;
- **psoriasis lesional versus non-lesional**, for the same saturation reason, despite
  its excellent paired design;
- **age or sex as the label**, since those are subject-level traits and most studies
  recruit a single stratum, so within-study variation fails;
- **major depressive disorder and schizophrenia**, where effect sizes are typically
  below the 0.60 floor and the task would be rejected as null;
- **subcutaneous versus visceral adipose**, which is a tissue-site contrast rather than
  a state contrast, and tissue site is a closed question.

The Phase 1 catalog measures the actual study and sample counts for each row. The
ranking above is a prior based on design properties, not on measured counts, and it is
frozen before any counts are seen so that the ordering cannot be adjusted to whatever
turns out to be convenient.

### 10.2 Family B: masked-panel imputation

**This is the task where the model has a structural advantage, and it has never been
evaluated as a downstream utility.**

The task: given a subset of measured genes, predict the rest. Concretely, hold out a
fixed fraction of the gene panel on held-out human ARCHS4 studies and score
reconstruction of the held-out genes.

Why it is different from everything that has failed:

- it consumes the model's **conditional expectation directly**, with no compression
  bottleneck in the path. Every previous downstream attempt asked a compressed
  embedding to carry state information, and the low-label result shows the compression
  is where the loss happens;
- the 3.797% reconstruction advantage enters the metric directly rather than having to
  survive a probe;
- **no trivial baseline is at ceiling.** Raw expression cannot perform this task at all,
  since there is nothing to regress from without a model. The real baselines are
  PCA-based matrix completion, $k$-nearest-neighbor imputation, and the pooled model;
- the metric is continuous, so it has substantially more statistical power than binary
  AUROC at the same sample size, which directly addresses the effect-size problem in
  CLAUDE.md 16.2;
- it is practically useful. Targeted panels are cheaper than whole-transcriptome
  sequencing, and "measure 2,000 genes, infer 20,000" is a real application.

Baseline ladder, equal tuning budget throughout: PCA matrix completion, $k$-NN
imputation, gene-mean imputation, pooled trunk plus single adapter, generic K8 bank,
organ K8 under blind routing, organ K8 under revealed organ.

Report per-organ and pooled, three seeds, study-grouped, with study-bootstrap intervals
on the organ-minus-pooled difference. Vary the masking fraction, for example 10%, 25%,
50%, and 75%, so the result is a curve rather than a point.

**Honest assessment of novelty.** This is close to the training objective, so a win is
less surprising than a win on state classification, and the writeup must say so plainly
rather than presenting it as an independent validation. It is nonetheless a legitimate
downstream utility with real baselines and a real application, and it is the one task
in this document where I would predict organ specialists win.

### 10.3 Why run both

The two families have opposite risk profiles and together they cover the outcome space.

| | Family A, state classification | Family B, imputation |
|---|---|---|
| Probability of a clean positive | low, roughly 25 to 30% | high |
| Novelty and interest if positive | high | modest |
| Interpretation if negative | closes the frozen-output branch definitively | would indicate a deeper problem |
| Cost | high, dominated by label curation | low, no labels needed at all |

Family B costs almost nothing because it requires no label curation whatsoever, which
is the entire bottleneck for Family A. Run Family B first for that reason: it is
cheap, it is likely to yield a presentable result, and it establishes the evaluation
infrastructure that Family A then reuses.

If Family B fails, that is important information in its own right. It would mean the
organ advantage does not survive even on a task built directly from the training
objective on held-out human studies, which would point at the external-generalization
claim rather than at the downstream-transfer claim.
