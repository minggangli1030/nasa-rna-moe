# Downstream negative-result audit and correction plan

**Historical record. Execution complete. Superseded for planning by
[`aug17-execution-plan.md`](aug17-execution-plan.md).**

**Status:** completed historical execution plan
**Written:** 2026-08-01
**Review input:** [`../CLAUDE.md`](../CLAUDE.md) Section 9
**Blocks:** any further writing of the downstream negative result, and the
August 17 deck's fourth result slide

## Decision

The downstream negative result recorded in
[`stage1-osdr-downstream-result.md`](stage1-osdr-downstream-result.md) and
[`final-organ-embedding-development-result.md`](final-organ-embedding-development-result.md)
is **premature as an interpretation**, though its numbers are correct and are not
retracted.

What the evidence supports today: these embeddings lose to raw expression and fold-fit
PCA on one small cross-species cohort.

What the documents currently assert: the learned representation lacks general
downstream utility, because of an objective and evaluation mismatch.

The gap between those two statements is not closed by any control that has been run.
This plan closes it. Nothing here reopens the frozen architecture, the frozen package,
or any Stage 1 or Stage 2 claim.

## What was missed, stated precisely

Five items. The first three are the ones that matter.

1. **No positive control on the encoder.** The evaluation concludes that the
   representation is weak without ever verifying that the encoder produces meaningful
   output on OSDR input at all. Pooled hidden scores AUROC 0.525 to 0.607, which is
   near chance for a model that demonstrably reconstructs well on external human data.
   A degenerate encoder and a genuinely uninformative representation produce identical
   numbers, and no run distinguishes them.

2. **No input-domain audit.** A model trained on human GTEx expression is being fed
   mouse ortholog-mapped expression. Neither result document reports what fraction of
   the model's gene panel survives ortholog mapping, nor what happens to the remainder.
   This matters because of an asymmetry that has not been considered: a linear model on
   raw expression is inherently robust to dead or imputed columns, since zero-variance
   features receive zero weight automatically. A deep encoder is not. Off-distribution
   inputs at a subset of positions corrupt internal activations across all dimensions.
   Both arms consume the same gene matrix, so this is not a fairness problem, but it
   would fully explain a large gap without any of the objective-mismatch reasoning.

3. **Hallmark-50 was rejected under a gate that does not apply to it.** It failed the
   per-organ **reconstruction** safety gate, which is correct and decisive for an
   expert axis. Used as downstream features, it routes no expert, trains no adapter,
   and cannot harm any organ's reconstruction, so that gate is not applicable and no
   other gate was ever applied. It carries the only downstream-positive signal in the
   project, AUROC delta $+0.1013$ with study-bootstrap interval $+0.0267$ to $+0.2049$,
   and it was measured against a probe base rather than against raw expression and
   PCA. The comparison that decides the matter has not been run.

4. **The conclusion generalizes past its evidence.** One cohort, 292 samples, 18
   studies, one task, one species direction. The documents state a claim about
   representation quality in general.

5. **The precision of the comparison is not characterized.** Pooled hidden ranges
   0.525 to 0.607 across seeds, a spread of 0.082 from seed alone at $n = 292$. The
   statement that learned conditions sit "0.160 to 0.225 below raw/PCA" is given
   without an interval, while the Tier-1 axis probe correctly reported study-bootstrap
   intervals for its deltas. Apply the same standard here.

None of this is a defect in execution. The runs are clean, immutable, and correctly
gated. The defect is that a general conclusion was drawn from a specific measurement
without the control that separates the two.

## Guardrails, unchanged

- No seed, organ, condition, or checkpoint selection after seeing outcomes.
- No frozen threshold relaxed to rescue a result.
- The OSDR cohort is accessed development data. Nothing in this plan can produce a
  final confirmation, only a development finding requiring a new untouched cohort.
- No downstream superiority claim unless it beats raw expression **and** fold-fit PCA
  under identical grouped splits with equal tuning.
- The frozen K8 package at `final_k8_package_dc562cc` is not modified, refit, or
  reselected. All work here is read-only against existing artifacts.
- Freeze every interpretation threshold in this plan into a protocol JSON with a
  recorded SHA256 **before** running the corresponding diagnostic.

---

## D1. Encoder validity audit (blocking, run first)

Three parts. D1a and D1c are hours of work and require no labels. Run them today.
Everything else in this plan is gated on the D1 verdict.

### Frozen execution amendment after feasibility audit

The literal multiclass D1b design is not executable on this cohort. Adipose, colon,
heart, and lung each occur in one retained study; liver occurs in two; brain in
three; and skeletal muscle in ten. Ordinary nested GroupKFold therefore creates
training folds with missing classes. The implementation uses brain versus skeletal
muscle, deterministic class-balanced study assignment, three outer folds, and two
inner folds. Every train and test fold must contain both classes. It also requires
raw-expression balanced accuracy of at least 0.70 before interpreting an embedding-
to-raw ratio. This change is based only on the organ-by-study contingency table, not
on model outcomes.

D1a's GTEx-relative gate applies to pooled hidden state, the representation with an
exactly comparable immutable human canonical cache. All six OSDR embedding views are
still described internally. The audit does not fabricate human organ-bottleneck
features that were never cached.

### D1a. Embedding distribution audit

**Inputs.** The existing feature archives under
`artifacts/final_evaluation/final_organ_embedding_evaluation_3f681fd/features/`, which
already contain `feature__<condition>` arrays for all six `EMBEDDING_CONDITIONS`, plus
`organs`, `study_id`, and `spaceflight`. Also the Stage 2B canonical GTEx caches for
the same seeds.

**Procedure.** For each of the six embedding conditions and each seed 17, 42, 101,
compute the following on the 292 OSDR rows and on a size-matched random draw of GTEx
training rows, using the same fixed draw seed:

- per-dimension standard deviation, and the count of dead dimensions, defined as
  relative SD below $10^{-6}$;
- entropy effective rank, reusing `_effective_rank` from
  `evaluation/evaluate_stage2_aligned_program_repair.py` so the convention matches
  every other rank number in the project;
- fraction of variance in PC1;
- mean pairwise cosine similarity;
- per-dimension $z$ of the OSDR mean against the GTEx mean and SD, summarized as
  median $|z|$ and the fraction of dimensions with $|z| > 3$.

Report the OSDR-to-GTEx ratio for each quantity.

**Frozen interpretation.** Record thresholds before running.

| Condition | Verdict |
|---|---|
| OSDR effective rank $\ge 0.7 \times$ GTEx, median $|z| \le 2$ | `ENCODER_IN_DISTRIBUTION` |
| OSDR effective rank $< 0.5 \times$ GTEx, or median $|z| > 3$, or dead-dimension fraction $> 0.25$ | `ENCODER_OUT_OF_DISTRIBUTION` |
| otherwise | `ENCODER_MARGINAL` |

### D1b. Organ recovery

Organ is known for every OSDR sample, it is the attribute the model is explicitly
built to encode, and `organs` is already present in the feature archive. If the
embeddings cannot recover it, they are not carrying biology on this input.

**Precondition, run first.** Emit the organ $\times$ study contingency table. Under
`GroupKFold` on study, an organ appearing in only one study cannot be present in both
train and test. Restrict the control to organs appearing in **at least two distinct
studies**. If fewer than two such organs remain, D1b is not runnable; record
`D1B_NOT_RUNNABLE` and rely on D1a and D1c.

**Procedure.** Add `nested_group_evaluate_multiclass` to
`evaluation/evaluate_stage1_osdr_downstream.py`, mirroring the existing
`nested_group_evaluate` exactly: same `_splits`, same `_transform`, same 12-point
grid, same outer and inner fold counts. Change only the estimator to
`LogisticRegression(multi_class="multinomial", penalty="elasticnet", solver="saga",
class_weight="balanced", random_state=1701)` and the inner selection metric to
balanced accuracy, since AUROC is not directly defined for the multiclass case.

Evaluate every embedding condition, plus `raw_expression` and `pca_64`, on identical
splits. Report balanced accuracy and macro-F1.

**Frozen interpretation.**

| Embedding balanced accuracy relative to raw expression | Verdict |
|---|---|
| $\ge 0.70$ | `ENCODER_RECOVERS_ORGAN` |
| $< 0.50$ | `ENCODER_DEGENERATE` |
| otherwise | `ENCODER_PARTIAL` |

### D1c. Input-domain and preprocessing audit

**Procedure.** Inspect `load_ortholog_map` in `core/`, together with
`evaluation/prepare_osdr_downstream_cohort.py` and
`evaluation/cache_stage1_osdr_downstream_features.py`. Report, as numbers, not prose:

1. size of the model's human gene panel;
2. count and fraction with a mouse ortholog in
   `data/osdr/human_mouse_orthologs.csv`, broken out by homology type, since
   `ortholog_one2one` and `one2many`/`many2many` are not equivalent;
3. count and fraction of panel genes actually present in the OSDR matrix after
   mapping;
4. the exact policy applied to absent panel genes, quoted from the code with file and
   line, whether zero-fill, mean-fill, drop, or something else;
5. per-gene mean and SD of the OSDR model input against the GTEx training input, and
   the fraction of the panel that is exactly zero or constant across all 292 samples;
6. confirmation that the normalization pipeline applied to OSDR is identical to the
   GTEx training path, by comparing the transform code path, not by inspection of
   outputs.

**Frozen interpretation.**

| Condition | Verdict |
|---|---|
| imputed or constant fraction of panel $\le 0.05$ and normalization identical | `INPUT_DOMAIN_OK` |
| imputed or constant fraction $> 0.10$, or any normalization difference | `INPUT_DOMAIN_SHIFT` |
| otherwise | `INPUT_DOMAIN_MARGINAL` |

A normalization difference is a one-line fix and would be the cheapest possible
explanation of the entire result. Check it explicitly rather than assuming it.

### D1 output

One JSON with a single frozen `verdict` field plus the three sub-reports and a
checksum manifest, written to
`artifacts/final_evaluation/encoder_validity_audit_<commit>/`.

---

## Decision tree after D1

```
Any of: ENCODER_OUT_OF_DISTRIBUTION, ENCODER_DEGENERATE, INPUT_DOMAIN_SHIFT
├── The OSDR evaluation does NOT support a claim about representation quality.
│   It measured cross-species encoder breakdown.
├── Write an addendum to both result documents. Do not retract the numbers;
│   restate the interpretation as a characterized boundary condition.
├── Revise CLAUDE.md Section 2. The bottleneck is a domain limit, not an
│   objective mismatch, and Section 3's list of six compounding effects must be
│   reordered accordingly.
├── If INPUT_DOMAIN_SHIFT is due to normalization: fix it and rerun the frozen
│   harness once. This is a bug fix, not a new experiment.
├── If it is due to ortholog coverage: do NOT attempt to repair the encoder.
│   Report the boundary. D3 becomes the priority, since a human task removes
│   the confound entirely.
└── D2 still runs; Hallmark features are unaffected by encoder health.

All of: ENCODER_IN_DISTRIBUTION, ENCODER_RECOVERS_ORGAN, INPUT_DOMAIN_OK
├── The encoder transfers. The downstream failure is a real representation limit.
├── The existing conclusion stands and can now be written with confidence and
│   with a stated mechanism.
└── Proceed to D2 and D3 to establish generality.

Mixed or MARGINAL verdicts
└── Report as inconclusive. Proceed to D3, which does not depend on the answer,
    and state in the deck that the cross-species contribution is unresolved.
```

---

## D2. Hallmark-50 as a downstream feature set

**Cost:** about one day. Both halves of the code already exist.

**Reuse.** `parse_hallmark` and `hallmark_features` from
`evaluation/evaluate_multiaxis_tier1_osdr_probe.py`, unchanged, including the existing
score-gene exclusion and the minimum-10-visible-genes rule. `nested_group_evaluate`
and `study_bootstrap_delta` from the existing harness, unchanged.

**Conditions**, all on the frozen 292-sample, 18-study cohort with identical splits,
identical 12-point grid, and identical tuning budget:

1. `hallmark_50` alone, `pca_components=None`;
2. `hallmark_50` concatenated with `pca_64`;
3. `pca_64` alone, reference, expected 0.733;
4. `raw_expression`, reference, expected 0.726.

**Controls, mandatory.** Without these, "50 averaged gene means" could beat PCA for
reasons unrelated to biology.

5. `random_50`: 50 random gene sets with sizes matched to the Hallmark sets, drawn
   from the same visible-gene pool under the same coverage rule, with three fixed
   draw seeds recorded in the protocol;
6. `hallmark_permuted`: Hallmark gene membership shuffled across sets, preserving set
   sizes.

**Statistics.** Report the AUROC difference against `pca_64` with a study bootstrap,
reusing `study_bootstrap_delta`.

**Frozen gate.** A positive result requires all three:

- beats `pca_64` with study-bootstrap interval strictly above zero;
- beats `raw_expression` with study-bootstrap interval strictly above zero;
- beats every `random_50` draw and `hallmark_permuted`.

**Reporting.** If it passes, this is a finding about **biologically structured
features**, not about the learned model, because Hallmark scores are a deterministic
function of expression with no trainable parameters and therefore no seed variance.
Say so explicitly. Biology-informed features beating both raw expression and learned
representations is a clean and interesting result and does not need to be dressed up
as something else. It remains development evidence on an accessed cohort and requires
a new untouched cohort for confirmation.

---

## D3. Human downstream control

**Cost:** two to three days, dominated by label curation, not compute.
**Purpose:** separate cross-species domain shift from objective mismatch. This is the
experiment that determines whether the negative result is general or bounded.

**Cohort requirements**, frozen before any outcome access:

- human, drawn from ARCHS4 studies that are disjoint from both the GTEx training
  donors and the 63 studies used in the Stage 1 external evaluation. Start from
  `data/holdout_eval/strict_study_disjoint_ids.txt` and
  `data/holdout_eval/study_overlap_report.json`;
- at least 8 studies and at least 200 samples after the existing frozen QC rules;
- both classes present in at least 5 studies;
- label derivable from structured metadata fields without manual curation;
- within-organ contrast where the counts permit, so organ identity cannot solve the
  task indirectly.

**Label selection.** Prepare readiness reports for two candidates in parallel and run
whichever clears first, time-boxed to August 4:

- **sex**, cheapest and fully structured. A weaker scientific question but a valid
  representation probe, and it cannot fail for curation reasons;
- **disease versus control**, better science, higher curation cost, and the option
  that may not clear the counts.

Record the readiness report for both regardless of which runs. A documented
infeasibility is a result.

**Execution.** Identical harness, identical baseline ladder, identical grid and fold
counts. No new tuning for any arm.

**Interpretation, frozen before running.**

- Learned representations still lose to raw and PCA on a human task: objective
  mismatch is confirmed, the negative result is general, and CLAUDE.md Section 2 is
  validated as written.
- Learned representations are competitive on a human task: the OSDR result measured a
  cross-species limit, not a representation limit. The claim becomes a characterized
  boundary, which is a stronger and more precise result than either the current
  negative or a weak positive.

---

## D4. External model as a framing device (optional)

Run only if D1 through D3 finish early. One inference pass, no training.

Run published BulkFormer-147M on the same cohort and harness. The question is no
longer whether the project's model beats it. The question is whether **it also loses to
PCA-64**. If it does, the finding changes from "this model is weak" to "this task
defeats learned representations generally, including current large-scale models, while
simple baselines hold up," which is a substantially stronger claim and costs a day.

Pin the exact checkpoint revision and weight hash before test access.

---

## Documentation changes required

Do not edit the recorded numbers or the immutable artifacts. Change interpretation
only, and only after the corresponding diagnostic completes.

1. Append a dated addendum to `docs/stage1-osdr-downstream-result.md` and
   `docs/final-organ-embedding-development-result.md` stating that the interpretation
   is provisional pending the D1 verdict, with a link to this plan. Do this **now**,
   before D1 runs, so no downstream reader treats the current text as settled.
2. After D1, revise CLAUDE.md Section 2 and the ordering of Section 3.
3. Add study-bootstrap intervals to every learned-versus-baseline AUROC gap, per
   item 5 in the missed-items list.
4. Update `docs/current-status.md` once the D1 verdict is recorded.

---

## Calendar and definition of done

| Date | Work | Droppable |
|---|---|---|
| Aug 1 | D1a and D1c; addenda to both result documents; D1b if the contingency table permits | no |
| Aug 2 | record the D1 verdict; branch per the decision tree | no |
| Aug 2 to 3 | D2 Hallmark as downstream features | yes |
| Aug 4 to 6 | D3 human downstream control | yes, but it is the most valuable droppable item |
| Aug 7 to 8 | D4, or begin consolidation | yes |
| Aug 9 to 11 | freeze figures; write the Stage 1 confirmation cohort contract | no |
| Aug 12 to 17 | deck; Aug 16 reserved for correction only | no |

**Definition of done, D1.** Protocol JSON frozen with recorded SHA256 before
execution. One verdict field. Three sub-reports. Checksum manifest. Both result
documents carry their addendum.

**Definition of done, D2.** All six conditions reported with study-bootstrap
intervals against `pca_64`, controls included, gate outcome stated, development-only
status stated.

**Definition of done, D3.** Cohort contract frozen before outcome access. Readiness
reports recorded for both candidate labels. Identical harness and ladder. Verdict
recorded against the frozen interpretation.

## Claim boundary

Everything in this plan produces development evidence on already-accessed cohorts. It
can correct an interpretation, characterize a boundary, and determine what the August
17 deck says. It cannot confirm a downstream advantage. A new untouched study-grouped
cohort remains required for any final downstream claim, and the Stage 1 reconstruction
result remains the only completed external validation in the project.
