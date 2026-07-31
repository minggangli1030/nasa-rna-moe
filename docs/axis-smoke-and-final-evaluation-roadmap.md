# Axis smoke tests and final evaluation roadmap

**Final presentation:** 2026-08-17

**MoE design target:** close by 2026-08-02

**Final training target:** launch by 2026-08-07

**Downstream harness start:** 2026-07-30

**Final-model swap/evaluation window:** 2026-08-10 through 2026-08-14

## Priority decision

The downstream harness is now a parallel critical path rather than final-week work.
Frozen Stage 1 checkpoints are the stand-in representation until the final model is
available.

The first complete OSDR run is now a validated negative development result:
PCA-64 AUROC was 0.733 and raw expression 0.726, while learned Stage 1 conditions
averaged 0.590–0.605 and no specialist mode improved over pooled in all three
seeds. This establishes the harness and a strict baseline floor. It also changes
the final representation requirement: the final model must expose an explicit
downstream-facing embedding or objective and beat raw/PCA, rather than assuming
that better masked-gene predictions will transfer automatically. Canonical result:
[`stage1-osdr-downstream-result.md`](stage1-osdr-downstream-result.md).

The full multiaxis Tier-1 gate is also complete. Tissue site is the only axis that
passes every frozen training and downstream-development gate and therefore the
only candidate authorized for Tier 2. Hallmark-50 is not advanced despite its
strong aggregate signal because it exceeded the prespecified per-organ harm
limit in two seeds. Age and sex failed bootstrap stability. See
[`multiaxis-tier1-result.md`](multiaxis-tier1-result.md).

Tier 2 is now complete and the matched-capacity gate failed in every seed. The
input-only site adapter was consistently slightly worse than the parameter-matched
generic adapter (−0.461%, −0.534%, and −0.544%), even though it beat the protected
base and shuffled-site control. The final architecture is therefore frozen as the
validated K8 organ MoE with pooled fallback/reference and no secondary axis. See
[`tissue-site-tier2-result.md`](tissue-site-tier2-result.md).

Before final refit, the frozen model now exposes a downstream-facing representation:
the pooled sample hidden summary, the selected or router-weighted organ-adapter
bottleneck, and router probabilities. The existing OSDR development harness will
test this contract without changing any checkpoint. Raw expression and fold-fit PCA
remain mandatory gates, and this accessed cohort cannot provide final confirmation.

1. Freeze one defensible labeled cohort and build its complete downstream harness
   against Stage 1 now.
2. Reuse immutable Stage 2B caches to screen candidate axes cheaply in parallel.
3. Select at most one additional axis beyond the protected organ expert by August 2.
4. Freeze the final architecture and launch final training by Friday, August 7.
5. Swap the final embeddings into the already validated harness in the final week.

This order prevents a large baseline-integration task from delaying the model whose
representation must actually be evaluated.

## Fast axis-screen funnel

The screen asks one incremental question:

> After organ has been accounted for, does this axis explain reproducible held-out
> residual structure or improve a protected prediction?

Every screen uses donor-grouped or study-grouped folds, training-fold-only fitting,
all three fixed seeds, random-label controls, technical covariates, and a per-organ
safety report. A promising point estimate in one seed is insufficient.

### Tier 0 — availability and leakage audit

Before fitting:

- count nonmissing samples, donors, studies, organs, and levels;
- identify whether a field is biological, technical, or a downstream target;
- quantify correlation with organ, tissue site, study, library depth, and detected
  genes;
- reject axes with insufficient repeated levels or no group-disjoint contrast; and
- freeze all bins, score definitions, marker sets, and missing-data rules.

### Tier 1 — cheap residual probes

No new neural expert is trained. Use the Stage 2B canonical training-donor caches
and fit the same small grouped-CV probe for every axis:

- base model: organ plus technical nuisance covariates;
- candidate model: base model plus one candidate axis;
- outcomes: pooled reconstruction error, post-private residual coefficients, and
  protected-organ residual error, plus a downstream label in a separate development
  cohort;
- outputs: incremental cross-validated \(R^2\), donor-bootstrap interval, permutation
  null, seed signs, organ-stratified effects, and coverage. The null permutes the
  candidate axis **within organ**, never globally.

An axis advances only if incremental cross-validated \(R^2\) is positive in all
three seeds, the pooled donor-bootstrap lower bound is above zero, its point
estimate exceeds the 95th percentile of the within-organ permutation null, every
retained level has at least 20 donors and appears in at least five organs, and it
retains value after organ plus technical nuisances. Rank passing axes by the frozen
effect and take at most two.

### Tier 2 — protected adapter smoke

Only the strongest one or two Tier-1 candidates receive a small factorized residual
adapter. The organ path remains frozen or otherwise protected. Use a short
mechanical run, followed by a fixed-budget three-seed smoke. Require:

- positive incremental utility beyond organ in all seeds;
- no material per-organ harm;
- noncollapsed use of the candidate axis;
- benefit beyond a shuffled-axis adapter and matched generic-capacity adapter; and
- input-only routing or scoring where the deployment setting does not reveal the
  attribute.

### Tier 3 — final model

Train at most one selected secondary axis with the organ experts. If no axis clears
Tier 2, final training uses the validated organ MoE with a pooled fallback. A
well-supported refusal to add an unstable axis is a valid result.

## Candidate axes and their fastest valid test

| Axis | Near-term source | Fast test | Role |
|---|---|---|---|
| Tissue site / anatomical subregion | Existing GTEx manifest | Stage 2B B4 plus organ-conditional grouped-CV probe | Immediate axis candidate |
| Age, developmental stage, sex | GTEx subject/sample attributes after ID-safe join | Organ-conditional grouped-CV probe with missingness and confound audit | Candidate if sufficiently powered |
| Immune, metabolic, mitochondrial, contractile, ECM, cell-cycle, stress programs | Hash-pinned MSigDB Hallmark 50 gene sets scored on training-fold-visible expression | Continuous program scores beyond organ, within-organ permutations, technical-proxy partial correlations | Candidate shared program |
| Disease, treatment, inflammation, hypoxia | Independent development studies with repeated within-organ contrasts | Leave-one-study-out residual/downstream probe | Primarily downstream targets; expert axis only after independent support |
| Spaceflight state | OSDR studies with mission/experiment grouping | Leave-one-mission or leave-one-study-out probe with permutations | NASA downstream target; not selected on the final test set |

Disease, treatment, and spaceflight labels must not be used to design an expert on
the same cohort later reported as its final evaluation. Use a separate development
cohort or nested training folds.

Cell-type composition is cut from this cycle: it is the most implementation-heavy
and organ-confounded candidate. It remains a post–August 17 extension.

## Calendar and stop/go gates

### July 30

- complete Stage 2B seed 42, transfer the verified seed-101 cache, and run frozen
  B0–B5 evaluation;
- treat B4 tissue-site output as the first axis smoke;
- freeze the generic multiaxis screen interface and data-inventory schema.

### July 30–August 2

- answer, for every downstream task, the exact cohort, samples, independent groups,
  label source, and local-expression status; cut tasks that cannot answer all five
  by July 31;
- freeze and build the OSDR spaceflight harness against Stage 1;
- add ID-safe GTEx age/sex/developmental metadata if available;
- derive frozen Hallmark pathway/program scores;
- run Tier-0 and Tier-1 screens in parallel on cached arrays;
- select no more than two candidates for Tier 2;
- run short protected-adapter smokes; and
- close the architecture decision by Sunday, August 2.

### August 3–6

- implement the final selected architecture;
- run fail-closed mechanical, determinism, leakage, and split checks;
- freeze exact cohort, schedule, seeds, thresholds, and evaluation protocol.

### August 7–9

- launch and complete final training;
- verify all seeds and immutable checksums;
- cache frozen embeddings and predictions once for downstream reuse.

### August 10–14

- swap final-model embeddings into the already validated downstream heads and
  baseline ladder;
- complete paired statistics, low-label curves, routing-safety results, and
  compute/parameter accounting;
- freeze figures and the final interpretation.

### August 15–17

- render and verify the final deck;
- reserve August 16 for review and correction, not new model selection.

## Final downstream evaluation pipeline

### Primary tasks

1. OSDR spaceflight-versus-ground prediction with exact structured labels and
   held-out studies; this is the first executable task.
2. Low-label learning curves at 1%, 5%, 10%, 25%, 50%, and 100% of labeled training
   data.
3. Within-organ ARCHS4 disease-versus-control only after independently curated,
   study-disjoint labels exist; otherwise it is cut from the core.

Secondary tasks are organ-specific survival prediction and drug response, only if
the primary pipeline is complete and their cohort contracts are defensible.

### Representation and model ladder

All methods receive identical patient/donor/study-disjoint splits, preprocessing
firewalls, downstream heads, tuning budgets, and seed reporting.

1. raw expression plus elastic net and a fixed small MLP;
2. PCA plus the same heads;
3. the matched pooled trunk;
4. pooled trunk plus organ label as an explicit conditioning control;
5. known-organ experts;
6. hard router, soft router, and pooled fallback;
7. published BulkRNABert on a cohort outside its disclosed pretraining set;
8. published BulkFormer-147M as a practical SOTA ceiling, not an apples-to-apples
    causal comparison.

No single comparator is simultaneously dataset-matched, capacity-matched,
architecturally matched, and current SOTA. The ladder makes each comparison answer
a named question instead of collapsing them into one ranking.

For schedule control, the core set is raw expression, PCA, pooled,
pooled-plus-organ-label, the three deployable MoE modes, published BulkRNABert on a
non-overlap cohort, and published BulkFormer-147M. Matched-data BulkRNABert
retraining and BulkFormer-37M retraining are extensions and cannot delay the core
table. Raw expression and PCA receive the same hyperparameter grid density, folds,
seeds, and stopping policy as MoE representations.

### Evaluation modes

- frozen encoder plus identical linear probe: primary representation test;
- frozen encoder plus identical small MLP: limited-nonlinearity check;
- parameter-efficient adapters: secondary;
- full fine-tuning: optional and only for sufficiently powered cohorts.

Cache every frozen embedding once so all heads consume identical inputs. Freeze
splits, metrics, hyperparameter grids, early stopping, and seed policy before test
access. Never select the best seed.

### Metrics and decision

Classification reports AUROC, AUPRC, balanced accuracy, macro-F1, and calibration.
Low-label results are curves over labeled sample count. Spaceflight analyses add
permutation tests. Survival uses concordance and integrated Brier score. Drug
response uses per-drug Pearson/Spearman correlation and RMSE.

A final downstream advantage requires:

- improvement over the matched pooled trunk;
- improvement over raw expression/PCA or the strongest simple baseline;
- a competitive result versus the closest external architectural peer;
- consistent direction across fixed seeds and held-out groups;
- no unacceptable organ-specific safety failure; and
- explicit reporting of organ-label availability and fallback behavior.

BulkFormer answers whether the complete system is competitive with a current
large-scale bulk-RNA model. It does not replace the matched pooled comparison,
which remains the causal test of specialization.

## Public baseline status

BulkRNABert has an official public implementation, checkpoints, preprocessing
example, and ordered gene list. The public models include TCGA, GTEx+ENCODE, and
combined pretraining variants. The core comparison uses a published checkpoint only
on a downstream cohort outside its disclosed pretraining set; matched-data
retraining is demoted to an extension. Official resources:

- [implementation and preprocessing](https://github.com/instadeepai/multiomics-open-research)
- [peer-reviewed paper](https://proceedings.mlr.press/v259/gelard25a.html)
- [published model configuration](https://huggingface.co/InstaDeepAI/BulkRNABert/blob/main/config.json)

BulkFormer also has public source, gene order, preprocessing, and five pretrained
scales. Its 37M model is the first capacity-oriented integration target; its 147M
model is the SOTA ceiling. Exact revisions and weight hashes will be pinned during
the August 3–9 pipeline preparation, before downstream test access. Official
resources:

- [implementation and model links](https://github.com/KangBoming/BulkFormer)
- [Cell Systems paper](https://www.sciencedirect.com/science/article/pii/S2405471226001390)
