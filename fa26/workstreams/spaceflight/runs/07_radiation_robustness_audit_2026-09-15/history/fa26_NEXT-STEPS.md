# Fall next steps — updated September 14, 2026

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

## Priority after the PI discussion

The [head pilot](artifacts/space_head_pilot_2026-09-14/REPORT.md),
[diagnosis/remedies](artifacts/space_head_diagnostics_2026-09-14/REPORT.md) and
[experiment-specific gene attribution](artifacts/space_head_attribution_2026-09-14/REPORT.md)
are complete. Forty-four BridgeRNA gene contributors survive the descriptive top-100,
sign and chip-deletion criteria across two head/pool directions and two references.
Top genes include MUSK, USF1, SETD7, BGN and RGS14; BGN decreases while supporting the
flight score, illustrating why attribution sign is not expression direction.

Next priority, clarified by Minggang: explain which biological stress-response programs
the flight classifier notices and uses, with genes as supporting evidence. Follow the
[response-level explanation plan](workstreams/spaceflight/PLAN.md#goal-clarification--response-level-explanations-september-14):
first test program evidence and reliance in the existing head, then validate exposure-associated
signatures using appropriate independent radiation/gravity controls. Compare
with expression-model evidence rather than assuming the BridgeRNA list is biologically
superior. Global cross-pool attribution correlation is only moderate (0.416–0.431),
and gene-set rankings are not pathway activation or radiation-exposure evidence.

Unseen-flight transfer remains unresolved; calibration and general biomarkers remain
outside the demonstrated result. Brain's batch work and human-versus-mouse ownership
stay as recorded in the [meeting notes](docs/2026-09-14-MEETING-NOTES.md).
The response-level pilot is complete and verified; see [current status](workstreams/spaceflight/STATUS.md). The frozen encoder and heads were not
updated during attribution; scripts, per-gene data, figures and checks are in the report.

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

The earlier cohort survey and its local review are complete. The response-level pilot and its retrieval, verification and report review are also
complete; the watcher is paused and no encoder or head training is queued.

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
