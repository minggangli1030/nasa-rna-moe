# Meeting and decision index

## September 14, 2026 — PI discussion

Source: [`2026-09-14-MEETING-NOTES.md`](2026-09-14-MEETING-NOTES.md)

Decisions and ownership:

| Topic | Decision / status | Owner |
| --- | --- | --- |
| Batch and preparation effects | Separate workstream; preserve biological distinctions while testing technical preparation effects | Brain |
| Spaceflight prediction | Start with a simple frozen-model head, then explain response programs and supporting genes | Minggang |
| Human–mouse question | Objective, matching design, success metric, and owner remain unresolved | Unassigned |
| Fine-tuning method | No method selected; head baseline must precede bounded encoder adaptation | Minggang for spaceflight only |
| Radiation or microgravity claims | Require controlled labels and independent matched contexts; a flight head alone is insufficient | Open validation requirement |

Post-meeting execution status:

- The frozen-head baseline, diagnostics, gene attribution, response explanation, controlled
  exposure validation, radiation robustness audit, and muscle specificity control are complete.
- The current evidence does not justify a radiation-driven flight claim.
- Brain's workstream remains separately owned; the human–mouse workstream remains unassigned.
- No new run is queued.

Open questions for the next meeting:

1. Which bounded biological question has priority: cross-flight muscle remodeling,
   controlled-gravity inflammatory/repair response, or a different mentor-selected target?
2. What independent study, biological unit, and primary endpoint will define success?
3. Is the goal response detection, exposure identification, or causal interpretation?
   These require different labels and controls.
4. Who owns the human–mouse task, and is its target species prediction, conserved-response
   transfer, or representation alignment?

## Documentation rule for future meetings

Create one dated file under `fa26/docs/` containing attendees/context, decisions, owners,
open questions, and explicit authorization boundaries. Add a short entry here and update
the roadmap only when a decision changes future work. Do not rewrite historical statements;
append a dated status note or link to the superseding decision.

