# July 30 presentation readiness

**Updated:** 2026-07-28 08:06 PDT

## Readiness decision

The presentation is provisionally ready from the completed Stage 1 external
evaluation and completed Stage 2 same-compute substitution result. The active
additive experiment is a bounded development update, not a prerequisite for a
defensible Thursday presentation.

## Current package

- `presentation/2026-07-30-biweekly.html`: nine-slide presentation deck with
  keyboard navigation and print CSS.
- `presentation/2026-07-30-biweekly-draft.md`: slide-by-slide content, speaker
  notes, limitations, and likely questions.
- `presentation/2026-07-30-stage2-directed-transfer-heatmap.png`: checksum-verified
  8×8 directed same-compute substitution heatmap.
- `docs/stage-1-end-result.md`: canonical Stage 1 synthesis.
- `docs/stage2-directed-transfer-preliminary-result.md`: canonical Stage 2
  substitution interpretation and correction audit.

Static checks pass: nine slides, nine section closures, the heatmap asset exists,
keyboard navigation and print CSS are present, and the bounded-claim text is in the
deck.

## Frozen numeric cross-check

### Stage 1 reverse-direction external evaluation

- Cohort: 821 samples, 63 connected studies, all eight organs retained.
- Evidence label: `post_access_qc_amended_external_evaluation`.
- Pooled MSE: 0.909261.
- True-organ K8: 0.874738, 3.797% lower than pooled.
- Target-hidden hard K8: 0.876228, 3.633% lower.
- Target-hidden soft K8: 0.875840, 3.676% lower.
- Pooled adapter: −0.005% versus pooled.
- Mean random-K8 control: −0.001% versus pooled.
- Seeds 17, 42, and 101 are all retained; no best seed was selected.

### Stage 2 same-compute substitution

- Estimand: A750+B750 versus A1500 on held-out recipient-A GTEx donors.
- All 56/56 directed edges are negative in all three seeds.
- All 56 donor-bootstrap intervals exclude zero.
- Mean effect: −3.273%; median: −3.382%; range: −7.086% to −0.450%.
- The independently trained primary seed-101 lineage reproduced the accelerated
  lineage's scientific matrices and heatmap hashes exactly.

## Required claim language

Safe headline:

> Organ specialization beats pooled reconstruction whether dispatch uses the
> revealed organ, hard target-hidden routing, or soft target-hidden routing. Under a
> fixed training budget, replacing recipient-organ exposure with another organ
> causes negative transfer across every tested directed pair.

Always keep visible or spoken:

- ARCHS4 evidence is post-access QC-amended, not pristine preregistration.
- The Stage 1 aggregate is robust across all retained seeds and balanced connected
  studies; it is not claimed positive in every individual study.
- Stage 2 seed consistency and donor-bootstrap stability do not establish
  independent-study universality.
- A new untouched multisource cohort is required for that stronger Stage 2 claim.
- No ARCHS4 fine-tuning, checkpoint selection, organ selection, or best-seed
  selection occurred.

Do not claim:

- universal per-organ or per-study improvement;
- verified donor identity within every ARCHS4 study;
- causal biological mechanism;
- spaceflight, disease, clinical, or downstream task benefit; or
- that all parameter sharing is harmful.

## Remaining before Thursday 08:00 PDT

- [ ] Incorporate the frozen additive result if it completes and passes integrity
  checks; otherwise leave it explicitly as ongoing/future work.
- [ ] Perform final visual QA of all nine slides at presentation resolution.
- [ ] Verify speaker-note timing at 8–10 minutes.
- [ ] Recheck likely-question answers against the final deck.
- [ ] Export or print the final delivery copy and verify the file opens.
- [ ] Mark this checklist final and record the delivery artifact hashes.
