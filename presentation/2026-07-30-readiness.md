# July 30 presentation readiness

**Updated:** 2026-07-28 14:10 PDT

## Readiness decision

The presentation is provisionally ready from the completed Stage 1 external
evaluation and completed Stage 2 substitution and additive development results.
The additive heatmap is explicitly preliminary and satisfactory for this week's
progress presentation; it is not the accepted Stage 2 final product. A frozen
seed-factorized diagnosis is the active next experiment.

## Current package

- `presentation/2026-07-30-biweekly.html`: ten-slide presentation deck with
  keyboard navigation and print CSS.
- `presentation/2026-07-30-content-brief.md`: concise slide purpose, essential facts,
  and visual direction; no talking script.
- `presentation/design.md`: canonical Anthropic-inspired scientific field-journal
  design, narrative, accessibility, and visual-QA specification.
- `presentation/2026-07-30-stage2-directed-transfer-heatmap.png`: checksum-verified
  8×8 directed same-compute substitution heatmap.
- `presentation/2026-07-30-stage2-additive-effects.png`: compact eight-edge
  recipient-preserving additive result with uncertainty and seed signs.
- `docs/stage-1-end-result.md`: canonical Stage 1 synthesis.
- `docs/stage2-directed-transfer-preliminary-result.md`: canonical Stage 2
  substitution interpretation and correction audit.

Static checks pass: ten slides, ten section closures, the heatmap asset exists,
keyboard navigation and print CSS are present, and the bounded-claim text is in the
deck. Center-content typography now has a 16 px CSS floor, the standard content
canvas is 1720 px at 1920×1080, the dense result figures on slides 8–9 use a wide
frameless layout, and centered pagination dots identify the current slide. The
complete deck was rendered at 1920×1080 after the Anthropic
palette and Source Serif 4/Inter implementation was applied; no slide clipping or
chart-background regression was observed. A follow-up pass restored restrained
Sage, Soft Sage, and Muted Blue data accents and raised every retained footnote or
interpretive caption to at least 16 px. Muted Blue now marks the verified winner
(correct organ specialist, +3.797%) through a semantic `.winner` class; the
automatic single-choice condition uses Sage.

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

### Stage 2 recipient-preserving addition

- Estimand: A1500+B750 versus A1500 on held-out recipient-A donors.
- Five of eight mean effects are positive.
- Liver ← skin is the only edge positive in all three seeds with its interval above
  zero: +1.956%, 95% CI +1.647% to +2.244%.
- Four edges beat all random auxiliaries in all three seeds.
- Zero of eight named donors beat A2250 in all three seeds.
- Result checksum-manifest SHA256:
  `0c005678d312ac8924e498249f215f45d33153704fc5fc646248596b32e5bf7b`.

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

- [x] Incorporate the checksum-verified additive result with bounded claims.
- [x] Perform final visual QA of slides 1–9 at 1920×1080; figures and embedded
  labels are legible, no decorative window frame remains, plot backgrounds blend
  into the parchment canvas, and the new serif metrics do not clip content.
- [x] Render and inspect the dedicated slide 10 future-work decision tree at
  1920×1080; all three branches, the target end product, and ten-dot pagination fit
  without clipping.
- [ ] Verify the plan → results → next balance at 8–10 minutes.
- [ ] Confirm every technical comparison has a plain-language explanation.
- [ ] Export or print the final delivery copy and verify the file opens.
- [ ] Mark this checklist final and record the delivery artifact hashes.
