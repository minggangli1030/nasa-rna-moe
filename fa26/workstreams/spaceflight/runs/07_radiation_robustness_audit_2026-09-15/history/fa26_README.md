# Fall 2026 (FA26) — BridgeRNA space-biology direction

## Latest completed step — controlled exposure validation

The [controlled-exposure pilot](workstreams/spaceflight/runs/06_controlled_exposure_validation_2026-09-14/REPORT.md)
added 123 public profiles and tested a radiation-associated probe against other stresses
and an independent lung-chip study. Within-study recognition is strong, but false positives
and inconsistent external transfer prevent assigning radiation contributions to flight
samples. Adding other stresses as negatives improved one challenge and worsened transfer.
The [specificity figure](workstreams/spaceflight/runs/06_controlled_exposure_validation_2026-09-14/specificity_and_transfer.pdf)
and [dataset audit](workstreams/spaceflight/runs/06_controlled_exposure_validation_2026-09-14/dataset_audit.csv)
retain all outcomes. Next: controlled-gravity quantification and tissue-matched response
validation. See [current status](workstreams/spaceflight/STATUS.md). No job is running.

## Completed response-explanation pilot

The [six-program pilot](workstreams/spaceflight/runs/05_response_explanations_2026-09-14/REVIEW.md)
completed 6,048 checks on the A100 in 32.8 minutes. Muscle differentiation/remodeling is
the clearest tested contributor; mitochondrial expression increases but slightly opposes
BRIDGE's flight separation. Other stress programs are weak or unstable across checks.
Most positive attribution remains outside this six-program vocabulary, and radiation/gravity
specificity is unvalidated. See the [worked sample](workstreams/spaceflight/runs/05_response_explanations_2026-09-14/EXAMPLE.md)
and [complete status](workstreams/spaceflight/STATUS.md). No further run is queued.

## Goal

Use the latest BridgeRNA foundation model and compatible public datasets to identify
interpretable space-biology patterns before committing to fine-tuning or a new MoE
experiment.

## Immediate work

Start with the [organized workstreams](workstreams/README.md) and [spaceflight run status](workstreams/spaceflight/STATUS.md).

Minggang's clarified target is a flight prediction explained by the **stress-response
programs the classifier relies on**, with genes as supporting evidence. The next proposed
step is response-level explanation and validation; radiation/microgravity interpretation
requires appropriate exposure controls. See the [updated personal plan](workstreams/spaceflight/PLAN.md#goal-clarification--response-level-explanations-september-14).

The [experiment-specific gene-attribution case](artifacts/space_head_attribution_2026-09-14/REPORT.md)
is complete. For fixed GSE298393 muscle-chip heads, 44 genes meet the descriptive
cross-pool/reference stability filter. Leading contributors include MUSK, USF1, SETD7,
BGN and RGS14. Highly attributed gene replacements change scores more than matched
random panels. All integration, finite-difference and score-reproduction checks pass.
[Summary figure](artifacts/space_head_attribution_2026-09-14/attribution_summary.pdf).
A [per-sample prediction/explanation example](artifacts/space_prediction_explanations_2026-09-14/EXAMPLE.md)
now expresses signed gene evidence as explicitly defined shares. These percentages are
attribution accounting, not calibrated confidence or causal stress fractions.

Reference stability is high, but genome-wide agreement across pools is moderate.
These are model-used genes in one experiment, not causal markers or a general flight
signature. The [cross-flight failure and remedy study](artifacts/space_head_diagnostics_2026-09-14/REPORT.md)
remains unchanged. No encoder/head updates occurred during attribution. The new response-level run is
tracked in the active-run section above.

The [meeting notes](docs/2026-09-14-MEETING-NOTES.md) retain ownership: batch/contrastive
learning (Brain), spaceflight prediction and attribution (Minggang), human versus mouse
(unassigned). See [next steps](NEXT-STEPS.md) for independent validation and interpretation.

## Decision rule

Do not fine-tune or add MoE capacity until the embedding exploration identifies a
specific task, dataset, and success metric. Raw expression and PCA remain required
baselines for any predictive claim.

## Local inputs

`bridge-rna-latest/` contains the downloaded BridgeRNA checkpoint, manifests, and
public reference inputs. Large files in this directory are intentionally ignored by
Git.

## PI direction — September 14, 2026

The [meeting notes](docs/2026-09-14-MEETING-NOTES.md) and
[spaceflight-head plan](workstreams/spaceflight/PLAN.md) supersede the
ownership and sequencing in the [earlier combined pipeline](docs/2026-09-14-FINETUNING-PIPELINE.md).
Retain the [author benchmark review](artifacts/bridge_benchmark_audit_2026-09-14/REVIEW.md)
as technical background.
The linked author repository identifies a controlled 40-donor paired poly(A)/Ribo
benchmark and a 17-animal/34-profile RR1/RR3 remeasurement challenge. Raw inputs and
pairing still need local verification. These are actionable public resources;
additional mentor-provided data remain pending.

Brain owns the batch/contrastive objective. Minggang plans expression/PCA and frozen-model
head baselines, followed by bounded encoder adaptation only if warranted. A prediction head is first trained with the encoder frozen; calibrated
exposure probabilities and gene attributions do not establish causal stress fractions.
Mission identity includes biology and is not automatically a removable batch.
The [earlier PI notes](docs/2026-09-14-PI-BATCH-FINETUNING.md) and
[initial metadata inventory](artifacts/batch_metadata_audit_2026-09-14/summary.json)
retain the discussion and provisional local inventory history.

## Current result — reviewed September 13, 2026

The **general survey, repeat-flight check, pathway survey and both onboard-1g human
comparisons are complete**. Use the [Monday discussion brief](artifacts/general_survey_2026-09-12/MONDAY-DISCUSSION.md),
[new pathway figure](artifacts/pathway_onboard_1g_2026-09-13/pathway_discovery.pdf), and
[current full report](artifacts/pathway_onboard_1g_2026-09-13/REPORT.md).

Two discussion leads survive basic robustness checks: an average oxidative-phosphorylation
gene-set increase in both human muscle-chip flights/pools, and higher inflammatory-associated
plus lower DNA-repair-associated expression in MG63 microgravity versus onboard-1g cultures.
The muscle set's individual gene responses agree weakly across flights; the MG63 result is
from an osteosarcoma-derived cell line. Neither establishes a common mechanism or biomarker.
Endothelial results are weaker and depend on the control comparison.

Frozen checkpoint `r7hnr92k`, the latest available in the inspected author embedding source,
completed all inference on moe-reboot's A100. No training ran. Expression remains the
baseline, and no general model advantage is established. See [next steps](NEXT-STEPS.md)
for two focused biological questions to discuss before committing to deeper evaluation.

## Completed survey history

The [general survey](artifacts/general_survey_2026-09-12/REPORT.md) covered 559 samples,
28 accessions, 54 contrasts and 11 broad tissue groups. The [repeat-flight follow-up](artifacts/muscle_repeat_flight_2026-09-12/REPORT.md)
added 12 human muscle chips: broad expression/model directions oppose across flights,
while MYH1 decrease survives. The current follow-up adds 14 human biological samples
and scores ten predefined gene sets across 60 primary contrasts plus one source sensitivity.
Five alternate-processing model inputs are not extra biological samples.

Hardware/protocol differences, donor pooling, related animals, collection timing and
source processing remain limits. Mouse muscle has recurring gene candidates across four
missions, but none of the ten program scores keeps one mission-average direction across
all four. Failed comparisons are retained in the reports. Those survey runs are complete; the subsequent response-level pilot is also complete as described above.

## Earlier work

The [34-sample mouse-liver pilot](artifacts/osdr_liver_pilot_2026-09-11/REPORT.md)
was a pipeline-development convenience cohort, not a search for the most significant
tissue. It is superseded in scope by the general survey. The
[contract audit](CONTRACT-AUDIT.md) records source/config/vocabulary checks and correction
of the draft model's normalization order. GTEx's unmatched-symbol issue remains a
separate limitation; the general survey uses different human count sources with
explicit mapping, missingness, and sensitivity checks.
