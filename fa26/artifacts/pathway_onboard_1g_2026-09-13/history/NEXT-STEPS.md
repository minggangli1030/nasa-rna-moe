# Fall next steps — updated September 12, 2026

The [general survey is complete](artifacts/general_survey_2026-09-12/REPORT.md).
The immediate deliverable is the [Monday discussion brief](artifacts/general_survey_2026-09-12/MONDAY-DISCUSSION.md),
not a full predictive evaluation. The general survey is complete. The authorized repeat-flight computation, scientific review and brief update are
complete.

## Repeat-flight check completed September 13

The [reviewed GSE298393 comparison](artifacts/muscle_repeat_flight_2026-09-12/REPORT.md)
is complete. Broad response directions disagree across flights in expression and both
model summaries. Chip deletion and expression-only source-FPKM sensitivity retain the
main negative result. MYH1 decrease persists in both donor pools in both flights,
including all single-chip deletions. The data do not establish a universal signature
or model superiority. Shared donors, hardware/duration differences, and source-unit
uncertainty remain limits.

## Next decision for Monday

Discuss whether the narrower shared MYH1 pattern is worth a small related-gene or
independent-context follow-up, and whether the global differences reflect experimental
conditions. Alternatively, prioritize a human onboard-1g comparison or the mouse
collection-time audit below. No additional cohort run or training is queued. The
15-minute watcher is paused after completion of this comparison.

## Other leads to discuss

- Audit collection times, handling, animal links, and cell composition for recurrent
  mouse-muscle Cdkn1a/Dbp/Mmp14 and mapped Mt2 patterns. Twelve accessions collapse to
  four missions. Keep the mapped mouse names explicit when using canonical human labels.
- Inspect another thymus/adipose flight cohort to challenge the MHU-3 tissue pattern.
  Tissue samples from one animal do not count as independent flight replications.
- For a question specifically about microgravity, revisit human studies with onboard
  1g controls (GSE157937, GSE224805) after compatible expression access is resolved.
  Their metadata were inventoried; no model results from those studies are included.

## Decision rule

Choose a specific biological question and its cleanest validation design. Preserve
raw-expression comparators, mission/donor grouping, and failed contrasts. Do not
fine-tune, add MoE, or claim model superiority merely because a model plot separates
groups. A larger predictive benchmark is a later decision, after an interesting
pattern survives the next check.

## Reproduction and history

Survey scripts: `survey_inventory.py`, `general_space_survey.py`,
`analyze_general_survey.py`, and `summarize_survey_leads.py`.
Saved results: `artifacts/general_survey_2026-09-12/`.
VM: `moe-reboot`, 149.165.175.241, isolated run
`/media/volume/moe-reboot/fa26_general_survey_20260912`.
The second VM was not needed for this bounded survey.

The [original September 11 plan](artifacts/general_survey_2026-09-12/INITIAL-PLAN-2026-09-11.md)
is retained as historical planning text; its pending-source and GPU-mismatch statements
are not current status. See the contract audit and completed reports for resolved checks.
