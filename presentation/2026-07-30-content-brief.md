# July 30 biweekly presentation content brief

**Audience:** scientific collaborators who may not know mixture-of-experts modeling.

**Purpose:** show the completed external result, the preliminary Stage 2 result, and
the immediate stability decision.

**Structure:** plan → results → next. This is a content and visual brief, not a
talking script.

## 1. Main finding

Takeaway: organ-specialized models improve hidden-gene prediction across independent
studies.

Essential number: 3.6–3.8% lower prediction error than one general model.

Visual: one large result statement with minimal metadata.

## 2. Plan

Takeaway: train in GTEx, lock every choice, and test once in ARCHS4.

Essential facts: 9,195 GTEx samples, 938 separate donors, eight organ specialists,
three independent repeat trainings.

Visual: five-step train → lock → test → compare → repeat diagram.

## 3. What was completed

Takeaway: the external evaluation ran end to end without tuning to test outcomes.

Essential facts: 821 final samples, 63 connected studies, all eight organs, all three
repeats retained.

Required qualification: six rows failed the unchanged coverage rule and were
excluded without replacement; label the result post-access QC-amended.

Visual: two large blocks—completed workflow and final evaluation set.

## 4. Evaluation coverage

Takeaway: every target organ remains represented across multiple external studies.

Essential facts: 821 samples, 63 study groups, eight organs, 10,000 uncertainty
resamples; liver has seven studies and every other organ has eight.

Visual: four large number tokens plus a simple liver/other-organs comparison.

## 5. Main external result

Takeaway: specialists beat one general model even when the organ is not provided.

Essential values:

- correct organ specialist: +3.797%;
- automatic single specialist: +3.633%;
- automatic soft blend: +3.676%.

Visual: one four-condition bar chart. State that higher means a larger reduction in
prediction error.

## 6. Repeatability and controls

Takeaway: every repeat improves, while equal extra capacity and random specialists do
not.

Essential values:

- repeat improvements span roughly 2.6–5.4%;
- equal-capacity general control: −0.005%;
- random specialists: −0.001%.

Visual: three repeat cards plus two neutral control cards.

## 7. Meaning and boundary

Takeaway: organ specialization is useful, but the result is not a universal or
downstream biological claim.

Supported: transfer across heterogeneous studies, automatic specialist choice, and
organ-specific benefit beyond capacity controls.

Not supported: benefit in every individual study, causal mechanism, clinical value,
or spaceflight-task improvement.

Visual: supported / not established comparison.

## 8. Stage 2 fixed-budget result

Takeaway: replacing target-organ data with another organ hurts prediction across all
56 tested directions.

Essential values: 56/56 negative in all three repeats; mean −3.27%.

Plain-language comparison: 750 target-organ plus 750 other-organ samples versus 1,500
target-organ samples.

Visual: a large, frameless directed eight-by-eight heatmap beside a short
plain-language interpretation. Preserve enough width for cell values, organ labels,
and uncertainty intervals to be read without zooming.

## 9. Stage 2 additive result

Takeaway: another organ sometimes adds information, but the helpful pattern is not
stable enough to guide training.

Essential values: one of eight pairs is positive in all three repeats; zero of eight
beats adding more target-organ data in every repeat.

Decision: the preliminary map is useful evidence but not yet a training policy. The
frozen three-by-three stability diagnosis determines whether Stage 2 continues or
pivots.

Visual: a large, frameless additive-effect chart beside a compact three-branch
interpretation. Preserve enough width for the chart's embedded labels to be read
without zooming.

## 10. Next step and future-work decision

Takeaway: the next objective is not to find a lucky organ pair; it is to learn a
reproducible rule for when biological specialists should share training information
and when they should remain isolated.

Immediate experiment: complete the frozen eight-edge diagnosis across three
independently trained base models and three fresh training runs.

Prespecified branches:

- several helpful pairs repeat → build a selective sharing/data-selection rule and
  validate it on a new multi-study cohort;
- signs repeat but helpful transfer is rare → use the map to prevent negative
  transfer through protected or selective sharing; or
- the map changes across runs → test one protected-sharing design, then broaden the
  specialist representation beyond organ labels while retaining organ and pooled
  controls.

Visual: three equal decision cards ending in one shared target end product.
