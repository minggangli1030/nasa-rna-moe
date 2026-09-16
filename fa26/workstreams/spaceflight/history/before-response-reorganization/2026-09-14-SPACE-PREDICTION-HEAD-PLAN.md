# Minggang's plan — spaceflight prediction and stress-response explanations

Date: September 14, 2026. Owner: Minggang.
Status update: the head pilot, diagnosis/remedies and [experiment-specific attribution](../artifacts/space_head_attribution_2026-09-14/REPORT.md)
are complete. Forty-four gene contributors meet the stated descriptive stability filter;
perturbation and numerical checks support their role in the GSE298393 classifier.
Cross-flight prediction still fails, and whole-ranking agreement across pools is moderate.
The next explanation priority is to identify biological response programs used by the
flight classifier, with genes as supporting evidence. Independent biological validation,
additional comparable flight experiments and supported calibration remain necessary. No encoder update was performed; nothing
remains running.
A [per-sample evidence-share example](../artifacts/space_prediction_explanations_2026-09-14/EXAMPLE.md)
now provides prediction scores, supporting/opposing gene percentages and overlap-adjusted
pathway allocations. Calibration and causal exposure decomposition remain separate tasks.
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

## Goal clarification — response-level explanations (September 14)

Minggang clarified the desired result: **given a flight prediction, explain which stress
responses the model noticed and relied on**, including evidence consistent with radiation,
microgravity or other stressors. Genes support this explanation; gene lists are not the
main deliverable. This is the next-stage priority. The completed attribution case is an
initial technical check, not the completed biological explanation.

For every response, distinguish:

1. Is the signature present relative to appropriate controls?
2. Does it support or oppose this flight classifier's score?
3. Do independent controlled experiments justify calling it radiation-associated,
   gravity-associated or another exposure-associated signature?

A separate response probe answers question 1 only. It does not establish reliance by the
flight head. Flight/control labels alone cannot validate radiation-versus-gravity inference.
Response association, model reliance and biological causation are separate claims.

### Next bounded pilot: explain the existing classifier in response terms

- Prespecify a small panel: mitochondrial-expression, DNA-damage/repair, oxidative-stress,
  inflammatory, proteostasis and muscle-remodeling programs. These are candidate concepts,
  not established findings or exposure-specific labels.
- Combine existing signed gene attributions with independently defined response scores.
  Report response expression and model attribution separately; pathway membership does
  not establish activation. This provides pathway-associated explanations initially.
- Test each program's effect on the unchanged flight score with reference replacement,
  matched random panels and alternative baselines. Report overlap and input-distribution
  limitations. Perturbations test model sensitivity, not biological causality; overlapping
  program effects need not add to 100%.
- Compare pools/references as development checks and seek independent biological units
  and studies for validation. Retain the failed cross-flight transfer result.
- Report response direction, support/opposition, stability, representative genes and
  unassigned evidence per sample. Percentages need an explicit allocation rule; do not
  force all evidence into radiation/microgravity categories.

### Exposure validation and optional response-based head

Audit controlled radiation/sham and altered-gravity/matched-control datasets for exposure,
dose/time, tissue/species and independent units. Existing onboard-1g studies are gravity
comparison candidates in their own domains, not automatic validation for muscle chips.
Unknown exposures remain unlabeled. Include other stressors as specificity controls where
available, and prevent study/tissue/preparation shortcuts and held-out label leakage.

With suitable independent concept data, fit small response probes on frozen BRIDGE and
test their relationship to the existing flight predictor. [TCAV](https://proceedings.mlr.press/v80/kim18d.html)
is a concept-sensitivity approach, but its sensitivity score is not an additive per-sample
percentage. For our linear terminal head, a fixed concept direction has a constant
directional derivative, so that statistic alone cannot explain sample-specific variation.

If the next classifier should explicitly decide through biological responses, compare a
[concept bottleneck](https://proceedings.mlr.press/v119/koh20a.html): expression -> frozen
BRIDGE -> validated response scores -> regularized flight head. This is a new classifier,
not proof of what the existing one learned. An additive final logit exposes signed response
contributions relative to documented references. Correlated concepts can make allocations
unstable; validate both concept meaning and contribution stability. Any direct residual
embedding route must appear as unexplained evidence rather than being assigned a named response.

Do not fit numerous stress heads on the six-chip training sets or derive radiation labels
from flight status. LoRA remains optional after independent evidence of need. The immediate
gap is response definitions, controls and faithful explanation.

Deliverable: **flight prediction + response evidence + model reliance + exposure
specificity + uncertainty**, with genes as drill-down evidence. This clarification updates
planning only; no new training, inference or watcher was launched.

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

The original meeting request was documentation only. Subsequent explicit requests authorized
the completed head pilot, diagnosis/remedy analysis and experiment-specific attribution.
The remaining stages are proposals;
no further run or watcher is queued.
