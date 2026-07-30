# August 17 final: downstream utility and multi-axis expert plan

**Final presentation:** 2026-08-17

**Status:** planning record; exact downstream datasets, splits, checkpoints, and
gates must be frozen before model comparison

## Why this is now required

Stage 1 establishes that organ specialists reduce hidden-gene reconstruction error
by 3.6–3.8% versus one pooled model on an independent ARCHS4 cohort, including
input-only hard and soft routing. That is meaningful evidence that organ
specialization survives a direction and dataset change.

It is not yet evidence that the representation helps a biological decision. The
August 17 result should therefore separate two questions:

1. **Reconstruction:** does the model recover hidden expression more accurately?
2. **Downstream utility:** do its frozen representations improve prediction of an
   unseen phenotype, condition, or outcome under patient/study-disjoint evaluation?

The second question must compare against Walt's BulkFormer architecture and simple
baselines. Otherwise a gain over this project's own pooled trunk cannot establish
competitive value.

## Downstream benchmark: primary design

### Tasks

Prioritize tasks that are not a restatement of the organ labels used to construct
the experts.

1. **Within-organ disease or state prediction.** Examples include tumor versus
   normal or molecular subtype within a tissue. Patient-level splitting is
   mandatory. A cross-organ cancer-type task is secondary because organ identity
   can dominate it.
2. **Spaceflight or stress-condition prediction.** Use OSDR flight versus ground or
   related exposure labels only where study design and sample size permit.
   Leave-one-study-out or study-grouped evaluation is preferred; a random
   sample split is not sufficient.
3. **Low-resource adaptation.** Deliberately limit labeled examples in a recipient
   organ and measure whether the organ expert or a frozen safe-sharing policy
   improves sample efficiency.
4. **Clinical outcome or survival.** Include only if endpoint definitions,
   censoring, and patient grouping can be made reliable. Do not add it merely to
   increase the task count.

Organ classification may be retained as a positive-control sanity check, but it
cannot be the primary downstream claim.

### Baselines

Every representation receives the same splits, preprocessing firewall, downstream
head, hyperparameter budget, and seed policy.

1. log1p expression with a regularized linear model;
2. PCA and, if feasible, NMF;
3. this project's frozen pooled trunk;
4. frozen known-organ experts as a mechanistic upper bound;
5. input-only hard and soft organ routing as deployable MoE conditions;
6. Walt's BulkFormer using its exact released preprocessing, checkpoint, and
   embedding contract; and
7. optional recent bulk-expression comparators only after the direct BulkFormer
   comparison is reproducible.

The repository already contains a TCGA analysis notebook that imports BulkFormer,
but the BulkFormer implementation/checkpoint is not currently tracked here. Before
freezing the benchmark, obtain and hash-pin Walt's exact code, checkpoint, gene
mapping, normalization, and embedding layer. Notebook output alone is not a valid
baseline lineage.

Use two clearly separated comparison tiers:

- **frozen representation + fixed linear probe:** the primary representation test;
- **matched fine-tuning:** secondary, with equal update and parameter budgets.

Do not compare a fine-tuned MoE with a frozen BulkFormer, or tune one model on the
test cohort more extensively than another.

### Splits, metrics, and gates

- Split by patient/donor and, when possible, by study.
- Fit normalization, feature selection, PCA/NMF, and downstream heads on training
  folds only.
- Report every predetermined seed; select none.
- Classification: AUROC, AUPRC, balanced accuracy, macro-F1, and calibration.
- Regression: MAE, \(R^2\), and rank correlation.
- Low-resource curves: performance versus labeled examples per organ.
- Use paired donor/study bootstrap intervals for MoE minus each baseline.
- A downstream advantage requires improvement over both the pooled trunk and the
  strongest simple/deep baseline, not only a positive point estimate.
- Report parameter count, inference cost, and whether organ identity was supplied.

## Biological axes beyond organ

Organ remains the validated primary expert axis. Additional axes are candidates only
if they explain held-out residual variation beyond organ and remain reproducible
across donors, seeds, and preferably studies.

### Candidate biological axes

1. **Anatomical hierarchy:** organ family, organ, tissue site, and subregion.
   Tissue site is already available in the current GTEx manifest.
2. **Cell-type composition:** immune, epithelial, stromal, neuronal, and other
   estimated cellular mixtures. This can explain variation shared across organs.
3. **Disease or physiological state:** healthy/disease, tumor/normal, inflammation,
   hypoxia, injury, infection, treatment, and spaceflight/stress exposure.
4. **Developmental and demographic state:** age, developmental stage, and sex where
   labels are reliable and scientifically appropriate.
5. **Molecular program activity:** mitochondrial, immune, metabolic, contractile,
   extracellular-matrix, cell-cycle, and stress-response scores. These are
   continuous shared programs rather than mutually exclusive sample labels.
6. **Genetic background:** genotype or ancestry only where consent, sample size,
   confounding control, and interpretation are adequate. This is not a near-term
   default axis.

Platform, library preparation, sequencing depth, RIN, ischemic time, study, and
batch are essential nuisance variables, but they should be modeled as technical
domain controls/adapters—not described as biological specialists.

## How to combine them with organ experts

Avoid a sparse Cartesian expert for every organ × disease × sex × platform
combination. Use a factorized hierarchy:

```text
pooled trunk
  + protected organ expert
  + optional tissue-site refinement
  + gated cross-organ biological-program experts
  + technical nuisance/domain correction
```

Recommended implementation order:

1. freeze the organ expert as the protected reference;
2. measure training-only residual variance after organ correction;
3. test each candidate axis for incremental held-out value beyond organ;
4. retain only axes that beat random-label and technical-confound controls;
5. add factorized residual adapters with separate gates, rather than cross-product
   experts;
6. require every added axis to preserve per-organ safety;
7. compare revealed-label routing with input-only routing; and
8. validate downstream usefulness under the benchmark above.

Three useful architectures follow from this decomposition:

- **hierarchical MoE:** pooled trunk → organ family → organ/site specialist;
- **factorized additive MoE:** independent organ, condition, and pathway adapters
  whose gated residuals add to the protected organ prediction; and
- **shared-program experts:** a small set of cross-organ pathway experts with
  organ-specific gates that can decline incompatible sharing.

The key scientific test is incremental:

> After the organ expert has explained organ structure, does another axis provide a
> reproducible, safe, downstream-useful correction?

## Execution priorities toward August 17

1. Complete and interpret the frozen Stage 2B B0–B5 diagnostic.
2. Freeze the downstream benchmark datasets, splits, tasks, and BulkFormer lineage.
3. Run frozen linear-probe comparisons before any model-specific fine-tuning.
4. Inventory reliable biological and technical metadata in the selected downstream
   cohorts.
5. Run an organ-conditional residual-variance screen for candidate axes.
6. Implement only the strongest factorized secondary axis; preserve organ experts
   as the reference.
7. Reserve the final days for immutable evaluation, visual summaries, and the
   August 17 deck rather than opening additional architectures.

Minimum final deliverables:

- Stage 1 external reconstruction result;
- frozen Stage 2 stability/refusal conclusion;
- downstream comparison table including BulkFormer, pooled, organ-MoE, raw, and
  PCA;
- one sample-efficiency or study-transfer figure;
- organ-conditional candidate-axis summary;
- limitations and a precise next experiment.
