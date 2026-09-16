# Fall next steps — updated September 14, 2026

The authorized **pathway survey and two human onboard-1g comparisons are complete**.
Use the [Monday brief](artifacts/general_survey_2026-09-12/MONDAY-DISCUSSION.md),
[new pathway figure](artifacts/pathway_onboard_1g_2026-09-13/pathway_discovery.pdf), and
[full follow-up report](artifacts/pathway_onboard_1g_2026-09-13/REPORT.md).

## Priority after the PI discussion

The user authorized the exploratory head pilot after the planning-only meeting.
That [pilot is now complete](artifacts/space_head_pilot_2026-09-14/REPORT.md): within-flight
held-out-pool classification works substantially better than cross-flight transfer.
Both frozen BridgeRNA readouts score 0.500 balanced accuracy and 0.000 AUROC in both
cross-flight directions at C=1. Expression/PCA fail too. Regularization and chip-deletion
sensitivities do not rescue transfer. No encoder update or BridgeRNA gene attribution ran.

Proposed next discussion: distinguish processing/input sensitivity from experiment-specific
responses, then choose a more compatible independent flight/control case before deeper
tuning. Compare Brain's eventual correction on the same frozen protocol, without assuming
batch is the cause. Gene attribution can describe a clearly labeled within-study classifier
if that becomes the chosen question; it cannot currently explain transferable flight detection.

The [meeting notes](docs/2026-09-14-MEETING-NOTES.md) assign batch/contrastive work to Brain,
spaceflight prediction/gene attribution to Minggang, and leave human-versus-mouse ownership
open. The [personal plan](docs/2026-09-14-SPACE-PREDICTION-HEAD-PLAN.md) remains the broader
scope. No additional experiment, fine-tuning or watcher is queued.

## Decision for Monday

Choose between two bounded biological questions:

1. **Muscle-chip mitochondrial-expression program:** its average increases across both
   flights and donor pools, surviving source, sample and scoring checks, but individual
   gene responses agree weakly. Audit which genes and experimental conditions explain
   this combination before testing an independent matched context. Do not infer
   increased respiration from expression scores.
2. **Controlled MG63 inflammatory/repair-associated response:** higher TNF/NF-kB and
   inflammatory gene-set expression and lower DNA-repair gene-set expression survive
   source and sample checks. Prioritize an independent onboard-1g experiment, preferably
   primary bone cells, before extending an osteosarcoma-derived cell-line observation.

The endothelial study illustrates control dependence and limited stability with only
2 onboard-1g cultures. Its unfolded-protein-response score is a smaller gravity-specific
lead; total flight versus Earth is not equivalent to microgravity versus onboard 1g.
Do not attribute the onboard-versus-Earth contrast solely to radiation.

## Completed evidence to retain

- [General survey](artifacts/general_survey_2026-09-12/REPORT.md): 559 samples,
  28 accessions, 54 contrasts, 11 broad tissue groups.
- [Repeat-flight check](artifacts/muscle_repeat_flight_2026-09-12/REPORT.md): 12
  additional non-stimulated chips. Broad expression/model directions disagree;
  MYH1 decrease survives both pools/flights and single-chip deletion.
- [Current follow-up](artifacts/pathway_onboard_1g_2026-09-13/REPORT.md): ten
  predefined sets across 60 primary contrasts, plus one processing sensitivity.
  Two new human studies add 14 biological samples. All 19 model inputs completed;
  five are alternate processing of the same MG63 samples. Sixteen tests passed.
- Recurrent mouse Cdkn1a/Dbp/Mmp14/mapped Mt2 candidates remain context-specific;
  none of the ten program scores keeps one mission-average direction in all four
  muscle missions. Collection time, handling and animal links remain audit targets.

No additional cohort run or training is queued. The previous 15-minute watcher is
paused after completion; the current bounded follow-up was completed in the active
session. Both inference and local review are finished.

## Decision rule

Choose a specific biological question and the cleanest independent test. Preserve
expression comparators, failed contrasts, mission/donor grouping and source checks.
Do not fine-tune or add MoE merely because a model plot separates groups. Consistent
within-study model directions do not demonstrate predictive superiority.

## Reproduction and history

New scripts: `pathway_onboard_survey.py`, `review_pathway_onboard.py`,
`plot_pathway_onboard.py`. Sources and hashes are retained in the new artifact folder.
The A100 run is on moe-reboot (149.165.175.241), isolated directory
`/media/volume/moe-reboot/fa26_pathway_onboard_20260913`; the second VM was not needed.
Prior handoff versions are preserved in the current artifact folder's `history/`.
The [September 11 initial plan](artifacts/general_survey_2026-09-12/INITIAL-PLAN-2026-09-11.md)
is historical; its source-access/GPU blockers have since been resolved.
