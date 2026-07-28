# Thursday presentation draft — 2026-07-30

Working title: **Do organ specialists transfer from clean GTEx to heterogeneous
ARCHS4 studies?**

Target: 9 slides, 8–10 minutes. The central result is positive, but every slide and
spoken claim must distinguish the pristine GTEx validation from the
`post_access_qc_amended_external_evaluation` in ARCHS4.

Rendered-deck checkpoint: `presentation/2026-07-30-biweekly.html` now implements
this nine-slide narrative with keyboard navigation and print CSS. Slide 8 reserves a
bounded Stage 2 heatmap panel; replace that placeholder only with the frozen
all-seed evaluator output and retain the GTEx development-only/study-universality
boundary in both slide text and speaker notes.

## Slide 1 — The question

**Can organ specialization learned only from GTEx improve masked-expression
reconstruction across independent ARCHS4 studies?**

- Train on GTEx only: 9,195 samples, 938 globally donor-disjoint donors.
- Freeze pooled, organ-K8, random-K8, pooled-adapter, and target-hidden router
  candidates for seeds 17, 42, and 101.
- Test once across eight organs and heterogeneous connected studies in ARCHS4.

Speaker note: This reverses the earlier ARCHS4-to-GTEx direction. GTEx is development
data here, so only ARCHS4 can test this new candidate.

## Slide 2 — What was frozen before ARCHS4 expression access

Show a left-to-right pipeline:

`GTEx train/calibration → frozen all-seed candidates → frozen ARCHS4 membership →
one-time extraction → immutable score caches → study-macro evaluation`

Safeguards:

- exact membership and source hashes;
- unchanged 14,000-nonzero-gene sample QC floor;
- equal organ weight, then equal connected-study weight within organ;
- 10,000 paired study-bootstrap repetitions;
- no ARCHS4 fine-tuning, no checkpoint selection, and no best-seed selection.

Speaker note: “Freeze” did not mean stopping implementation. It meant completing and
hash-binding the extractor, scorer, evaluator, and decision rules before opening the
test matrix.

## Slide 3 — The lockbox did what it was supposed to do

The first expression access stopped before publishing any expression rows or efficacy
metric:

- five samples from one liver study had only 19–304 nonzero genes;
- one lung sample had 11,235 nonzero genes;
- the fixed minimum was 14,000.

Why metadata screening missed this:

- metadata correctly established organ and study presence;
- per-sample expression coverage is stored only in the sealed H5 matrix;
- inspecting it earlier would itself have opened the test expression.

Decision:

- exclude exactly the six pre-existing QC failures;
- lower no threshold, add no replacements, and drop no organ;
- relabel all resulting evidence as post-access QC-amended.

## Slide 4 — The amended external cohort still covers every organ

Headline numbers:

- **821** passing samples;
- **63** connected studies;
- **8/8** organs retained;
- liver: 42 samples across 7 studies;
- every other organ: 8 studies.

Speaker note: K remains eight. The amendment changed one deficient study and one
sample, not the biological question or trained architecture. Building a new untouched
cohort is a future confirmation, not a rescue of this run.

## Slide 5 — Primary result: organ routing transfers

Use a compact bar chart with pooled normalized to 100, or report the exact MSE table:

| Frozen condition | Equal-organ/study MSE | Reduction vs pooled |
| --- | ---: | ---: |
| pooled | 0.909261 | — |
| true-organ K8 | 0.874738 | **3.797%** |
| target-hidden hard K8 | 0.876228 | **3.633%** |
| target-hidden soft K8 | 0.875840 | **3.676%** |

Speaker note: The target-hidden router recovers almost all of the true-organ gain
without using organ labels or reconstruction targets at test time. Hard routing
activates one organ expert; soft routing is a sensitivity analysis.

Central takeaway: organ specialization beats pooled whether the route is the revealed
organ, a hard target-hidden choice, or a soft target-hidden mixture. This is robust
across every retained seed and across the forward/reverse training-test directions;
describe the study evidence as balanced and heterogeneous, not positive in every
individual study.

## Slide 6 — The gain is seed-consistent and not generic adapter capacity

Per-seed percentage reduction versus that seed’s pooled model:

| Seed | True organ | Hard router | Soft router |
| ---: | ---: | ---: | ---: |
| 17 | 2.778% | 2.619% | 2.649% |
| 42 | 3.243% | 3.067% | 3.103% |
| 101 | 5.384% | 5.226% | 5.289% |

Controls averaged across all seeds:

- pooled residual adapter: **−0.005%** versus pooled;
- mean of three random K8 axes: **−0.001%** versus pooled.

Every true/hard/soft seed comparison had a paired-study bootstrap 95% interval above
zero. No seed was selected.

Speaker note: The strongest interpretation is conditional organ specialization, not
“more adapter parameters always help.” Seed 101 is larger, but all seeds are retained
and averaged.

## Slide 7 — What the result does and does not establish

Supported:

- GTEx-only organ supervision transfers across heterogeneous ARCHS4 studies;
- expression-derived routing preserves most of the known-organ advantage;
- organ-aligned experts beat pooled and capacity-matched random/control conditions.

Not supported:

- a pristine preregistered ARCHS4 confirmation;
- universal improvement in every organ for every seed;
- verified donor-level independence inside every ARCHS4 study;
- downstream spaceflight performance or a clinical claim.

Important nuance: organ-mean true-expert improvements are positive for all eight
organs, but colon is close to neutral and a few organ-by-seed cells are negative.
The prespecified evidence unit is the connected study, aggregated equally within
organ.

## Slide 8 — Why the transfer experiment matters

**Immediate practical objective**

Learn which biological domains should share training information and which should
remain separated.

- Choose useful supplementary organs for rare or undersampled recipients instead of
  indiscriminate pooling.
- Detect negative transfer and justify adapter isolation, balanced curricula, or
  gradient-conflict controls.
- Use mutual, asymmetric, or harmful transfer to design a smaller hierarchical MoE:
  pooled trunk → organ family → organ specialist.
- Predefine rational adaptation sources for scarce disease or spaceflight datasets,
  without claiming downstream benefit before task-specific testing.

**Why the combination is underexplored**

Use independently validated organ experts to derive mechanistic signatures, measure a
controlled directed organ-to-organ transfer matrix, and test prospectively whether
expert or input-only router structure predicts those transfer effects on held-out
studies.

Speaker note: Each method exists individually. The contribution is the independently
measured, prospectively tested link among expert mechanism, functional transfer, and
router compatibility.

## Slide 9 — Conclusion and next experiments

**Bounded conclusion**

Organ identity is the strongest tested conditional specialization axis. A
target-hidden GTEx-trained router reproduces a roughly 3.6–3.7% study-macro MSE gain
in multisource ARCHS4, while random and pooled-adapter controls remain neutral.

**Stage 2: explain and test the organ experts**

1. Characterize the frozen expert-minus-pooled residuals and pathway signatures.
2. Measure a controlled directed transfer matrix on untouched recipient-organ A
   studies using two complementary comparisons:
   - same compute: A1500 versus A750+B750;
   - same A exposure: A1500 versus A1500+B750, with random-auxiliary and
     additional-A controls.
3. Test whether expert similarity and router preferences predict those held-out
   transfer relationships.

Development will first use donor-disjoint GTEx calibration data. The stronger claim
that these predictions generalize across held-out studies requires a newly frozen
multisource cohort; the completed QC-amended ARCHS4 cohort cannot be recycled as a
pristine Stage 2 lockbox.

Planned preliminary Stage 2 figure: a directed 8×8 recipient-organ × donor-organ
heatmap showing helpful transfer versus interference, with three-seed sign counts and
donor-bootstrap uncertainty. Do not call the map universal merely because an edge is
seed-consistent; independent-study universality is a later untouched-cohort test.

Label-free routing is optional and secondary. It was originally included to add
novelty by linking a co-routing map to the transfer map, but the completed de novo
label-free pilots failed their utility/confound gates. Stage 2 therefore remains
centered on the replicated organ experts.

Development-only execution checkpoint: on 1,826 GTEx calibration samples from 188
held-out donors, the correctly named frozen expert ranks first for all 8 recipient
organs after averaging the three seeds. All 56 off-diagonal expert/recipient means are
worse than pooled. Present this only as evidence that the experts learned distinct,
organ-aligned functions—not as the controlled transfer result.

Closing line: “The result is strong enough to continue the organ-routing program,
but the QC amendment stays visible in the evidence label and in every claim.”

Speaker note: Transfer is not automatically biological. Platform, study composition,
sample quality, disease context, label errors, unequal training exposure, and generic
expression similarity are alternative explanations. That is why the primary design
uses study-disjoint evaluation, donor-atomic sampling, equal-budget controls, random
donors, platform controls, and all three seeds.

## Figure checklist

- Primary four-bar result: pooled, true organ, hard router, soft router.
- Small seed-consistency panel with three grouped bars or three connected points.
- Controls shown at zero on the same reduction scale, not hidden in an appendix.
- QC amendment shown as a six-row exclusion from 827 to 821, with all eight organs
  visibly retained.
- Footer on result slides:
  `Post-access QC-amended external evaluation; 821 samples / 63 connected studies;
  no ARCHS4 tuning; all 3 seeds retained.`

## Likely questions

**Did you choose organs after seeing ARCHS4 expression?**

No. The eight-organ intersection was selected from GTEx donor depth and ARCHS4
metadata availability before expression access. The later amendment removed only
six samples that failed the already-frozen expression-coverage rule.

**Why not lower the 14,000-gene threshold?**

That would weaken the test after seeing the failures. The threshold was retained
exactly; the nearly empty samples were excluded.

**Why is this not pristine preregistration?**

Membership changed after the first expression-access attempt, even though no efficacy
metric existed and the change followed the pre-existing QC rule. The honest label is
therefore post-access QC-amended.

**Does the failure mean ARCHS4 organ coverage was inadequate?**

No. All eight organs remain represented. The issue was expression completeness in
six samples, concentrated in one liver study.

**Were models retrained or seeds selected after seeing ARCHS4?**

No. The same three GTEx-only seeds were scored and averaged. No ARCHS4 training,
checkpoint selection, expert selection, or best-seed selection occurred.

**What caused the evaluator retry?**

A fail-closed loader bug validated three ancillary arrays without loading them. The
immutable cache hashes passed independently; a versioned code-only correction loaded
all hash-bound arrays, linked them to the source protocol, and then ran the unchanged
estimator. No metric existed before that correction.
