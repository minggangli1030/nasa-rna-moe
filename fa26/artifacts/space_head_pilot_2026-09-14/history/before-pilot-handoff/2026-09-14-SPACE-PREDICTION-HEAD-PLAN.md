# Minggang's plan — spaceflight prediction head and gene attribution

Date: September 14, 2026. Owner: Minggang.
Status: proposed plan only; no execution authorized by this document.
See the [meeting notes](2026-09-14-MEETING-NOTES.md) for task ownership.

## Objective and scope

Build and evaluate a prediction head that recognizes a precisely defined
spaceflight-related condition, then identify the genes and pathways supporting its
predictions. Begin with the existing frozen BridgeRNA representation. Batch correction
belongs to Brain; human–mouse work is a separate, currently unassigned task.

First research question: within a supported tissue/context, can a model distinguish
flight from its specified matched ground control on independent data, and are its
attributions reproducible? A universal spaceflight or stress-cause classifier is not
an assumed outcome.

## Proposed sequence

### 1. Define one prediction case and its independent evaluation

Prepare a cohort specification before implementation: exact accessions, expression source,
flight/control definitions, species, tissue, mission/study, donor/animal/pool identities,
preparation metadata, label provenance and available independent sample counts.

Review existing survey cohorts for repeated compatible flight/control contrasts. Human
muscle chips are a candidate for a repeat-flight exploratory case, but donor pooling and
limited independent flights constrain validation. MG63 microgravity versus onboard 1g is
a separate gravity-treatment question; both groups flew, so it cannot supply positive
and negative labels for “was in space.” Neither candidate is selected automatically.

Select the narrowest case with valid controls and feasible independent evaluation. If
there are too few compatible studies, record that limitation and plan a feasibility
pilot or additional data instead of claiming cross-study validation.

Keep related libraries, technical replicates, donor pools and repeat measurements in
the same partition. Fit preprocessing and select hyperparameters only within training
and validation partitions. Hold out studies/missions where feasible; donor-held-out
performance within one study answers a weaker question. Reuse the same partitions for
all models. Data previously explored are development evidence, not pristine confirmation.

Deliverable: cohort/label specification, independent-unit counts and split protocol.

### 2. Establish the smallest useful head baseline

| Model | Trainable part | Purpose |
|---|---|---|
| Expression + regularized logistic regression | Classifier | Direct expression baseline |
| Training-fitted PCA + same classifier | Classifier | Low-dimensional expression baseline |
| Frozen BridgeRNA + regularized linear head | Head only | Primary starting model |
| Frozen BridgeRNA + small MLP | Head only | Bounded nonlinear comparison, if sample size permits |

Use the same compatible inputs and labels across comparisons. Inspect the existing
layer/readout benchmark first; limit any new layer selection to development data.
Head training changes the classifier, not the pretrained encoder. Store the exact
checkpoint, preprocessing contract, pooling and selected layer with every result.

Report balanced accuracy, AUROC/AUPRC where class counts allow, confusion counts,
class prevalence and biological-unit uncertainty. Compare against label-shuffled and
metadata-only baselines where the grouping/design makes them valid, to investigate
study/preparation shortcuts. Prefer descriptive results when tiny independent N makes
estimates unreliable; do not treat repeated seeds or splits as additional samples.

Deliverable: comparison table and held-out predictions, retaining failures.

### 3. Decide whether encoder fine-tuning adds value

Only after the baseline establishes a meaningful test, compare a bounded last-block
update with one small LoRA configuration under the same labels, grouped splits and
configuration budget. Keep the frozen-head baseline. Use validation-based stopping,
report trainable parameter counts, and choose any further search using development data.

Choose sample requirements from independent-unit learning curves and uncertainty;
do not set a universal minimum or assume LoRA is best. If the head already suffices,
retain it. If batch confounding explains prediction, refine the design before increasing
capacity. When Brain supplies a representation, evaluate it with the same head protocol
alongside the original encoder rather than assuming correction improves flight prediction.

Deliverable: decision on whether to retain the frozen encoder, update its last block,
or use LoRA. No update strategy is selected as the winner in this plan.

### 4. Identify the genes and pathways used by the predictor

Attribute the selected prediction to input genes using a gradient-enabled path through
the frozen or adapted encoder and head. Frozen weights can still permit input gradients;
cached sample embeddings alone cannot recover input-gene contributions. Proposed initial
method: Integrated Gradients on the selected logit with documented reference baselines.

Compare signed contributions across reasonable baselines, held-out biological units,
seeds and studies. Check important-gene perturbations against expression-matched random
gene panels, reporting masking/perturbation limitations. Compare with the expression
classifier's gene contributions. Summarize stable contributions in predefined pathways
with an appropriate measured-gene background and overlapping gene sets accounted for.
Layer activation or attention plots are supporting diagnostics, not causal explanations.

Keep mitochondrial-expression signatures distinct from functional mitochondrial dysfunction.
Likewise, DNA-repair expression does not by itself identify radiation exposure. Existing
survey pathway findings are hypotheses to examine, not independent ground-truth labels.

Deliverable: per-case gene-contribution plot, pathway summary and attribution-stability checks.

### 5. Add calibrated outputs and decide the next biological target

If independent predictive performance is credible and validation data are sufficient,
calibrate scores using grouped validation data and assess reliability/Brier score on
held-out data. Otherwise label outputs as uncalibrated model scores.

A sample report should state the exact target/control comparison, score or calibrated
probability, supported tissue/domain, leading positive/negative gene contributions,
pathway associations and uncertainty. Interpretation: evidence supporting the model's
prediction, not the fraction of stress caused by a mechanism.

Later, propose separate radiation or microgravity heads only with verified exposure and
control labels, including dose/time or gravity context. Such exposures may co-occur;
unknown labels must not become negatives. Add a functional mitochondrial target only
when suitable independent phenotype labels exist. Human–mouse transfer remains a
separate task until its owner and objective are defined.

## Success and handoff

A useful first result establishes whether prediction generalizes beyond the training
context, whether it compares favorably with expression/PCA, and whether gene/pathway
contributions are stable enough to discuss. An honest negative result or a demonstrated
metadata shortcut is also informative. Numerical acceptance thresholds will be defined
before viewing new adaptation outcomes, after cohort feasibility is established.

Planned outputs: cohort/split specification; baseline and adaptation comparison;
held-out score/calibration plots; gene/pathway attribution figures; a short discussion
of supported findings, failures and the next experiment.

This turn creates documentation only. Do not launch VM jobs, downloads, training,
inference, scheduled watchers or evaluations until the user requests execution.
