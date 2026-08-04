# August 17 execution plan and documentation fixes

**Written:** 2026-08-03
**Status:** jointly resolved and ready for hash freeze; no scientific outcome access
authorized by this planning document alone
**Authority:** derived from `../CLAUDE.md` Sections 1 to 15. Where this document and
CLAUDE.md Section 8 disagree on dates, this document governs.
**Supersedes for planning:** `downstream-negative-result-audit-plan.md` (D1 to D4
complete) and `post-d2-roadmap.md` Parts 1 to 3 (Phase 1 complete). Both remain
authoritative as historical records of what was specified and why.

---

## 0. Where the project stands

**Closed.** The frozen-output downstream branch on OSDR. Four convergent prespecified
output contracts, three seeds, full-label and low-label regimes, with and without
organ-conditional centering. No further output engineering on this cohort.

**Established and unaffected.** The Stage 1 external reconstruction result, the Stage 2
negative-transfer result, the matched-capacity refusal of secondary axes, and the frozen
K8 package. None of the downstream work touches any of these.

**Open.** Whether an explicitly supervised organ-aware extension can produce downstream
value on a benchmark chosen in advance to have headroom. This cannot be answered before
August 17 and must not be attempted before it.

**The single largest risk between now and August 17 is not scientific.** It is that the
deck, the only hard-dated deliverable, has no completion criterion while three optional
workstreams compete for the same fourteen days. This plan fixes that by dating the deck
and marking everything else droppable against it.

---

## 1. Immediate documentation fixes (do first, roughly two hours)

These correct how existing results are read. No new computation. Per CLAUDE.md 12.1.

### F1. Reframe the low-label result as the strongest matched-probe evidence

**Current:** CLAUDE.md 3.5 is titled "Low-label learning did not rescue the embeddings"
and reads as one more failed repair.

**Problem:** it is the strongest matched-probe result in Phase 1 and it is filed as a
footnote. A useful compact representation should improve the linear accessibility of
task-relevant structure when labels are scarce. The learned representations instead
landed at 0.4890 to 0.5250 against raw at 0.6289 at the 5% floor, and every 10%
interval was fully below zero.

**Fix.**

1. Retitle 3.5 to **"Low-label probes show reduced linear accessibility of state
   information."**
2. Add to 3.5: *"Under a matched linear probe family, matched label budget, and matched
   grouped splits, the learned representations made the perturbation-state signal less
   linearly accessible than the raw input at the 5% and 10% floors and in every seed.
   This is strong evidence that the reconstruction objective does not preserve the
   state signal in a practically useful form under the frozen output contract. It does
   not establish information-theoretic absence."*
3. Cross-reference 3.5 from Section 4.1 as the direct empirical support for the primary
   causal diagnosis. Section 4.1 currently argues the mechanism from first principles
   with no result attached; 3.5 is that result.

Apply the same change to `post-d2-phase1-interim-result.md` and `current-status.md`.

### F2. State why high residual AUROC is not evidence of an MoE benefit

**Current:** CLAUDE.md 3.4 reports residual conditions at 0.9658 to 0.9820 next to raw
at 0.9675, and concludes correctly that no specialized residual beat pooled. A reader
skimming sees 0.98 and concludes residualization worked.

**Fix.** Insert at the head of 3.4: *"The residual is $y_{\text{obs}} - \hat{y}$ and
therefore retains a direct observed-expression component. Subtraction can still remove,
distort, or amplify task signal, and the score panel is not the full raw vector, so high
AUROC was not guaranteed. It is nevertheless non-diagnostic by itself. The informative
contrast is organ-conditional residual against pooled and fold-fit centered controls,
and that contrast is not robust."*

### F3. Separate the two negative findings

**Current:** Section 4.3 attributes the downstream failure to benchmark ceiling and
uneven power. That is correct and it is also the most comfortable explanation available.

**Problem:** Section 3.6 shows specialization is unstable in the **matched** Q-B
comparison, where ceiling is not the binding constraint because both arms pass through
the same compression. Seed 101 reverses at $-0.0609$ with CI $-0.1102$ to $-0.0054$,
and E4 records the same reversal for hard and soft routing. Merging the two lets a real
weakness hide behind a real benchmark problem.

**Fix.** Report as two separate findings throughout, including on slide 4:

- **Benchmark limitation:** raw expression reaches 0.9675 in the only adequately
  powered organ, leaving no headroom, and other organs are underpowered.
- **Specialization instability:** in the matched comparison, the specialization effect
  reverses sign across seeds with intervals excluding zero in both directions.

### F4. Document hygiene

Add a status line to the top of `downstream-negative-result-audit-plan.md` and
`post-d2-roadmap.md`: *"Historical record. Execution complete. Superseded for planning
by `aug17-execution-plan.md`."* A reviewer opening the docs directory should not have to
infer which plan is live.

**F1 to F4 definition of done:** all four edits committed, `current-status.md` updated,
no numbers changed anywhere.

---

## 2. Calendar

| Dates | Primary, not droppable | Parallel, metadata only | Droppable |
|---|---|---|---|
| Aug 3 | F1 to F4 documentation fixes | D3-0 field inventory | no / yes |
| Aug 3 to 4 | **Deck skeleton: all five slides, real numbers, placeholder figures** | D3-0 field inventory | no / yes |
| Aug 5 to 7 | Figures frozen from existing artifacts | D3-0 candidate screening | no / yes |
| Aug 8 to 9 | Track A confirmation contract, written and frozen, **unexecuted** | D3-0 verdict | contract no / D3-0 yes |
| Aug 10 to 13 | Deck build | B1 headroom baselines **only if** D3-0 cleared by Aug 9 | B1 yes |
| Aug 14 to 15 | Rehearse, tighten | none | no |
| Aug 16 | **Frozen.** Correction only | none | no |
| Aug 17 | Deliver | | |

Three standing rules:

1. **B3, the supervised extension, does not start before August 17.** It cannot be
   implemented, controlled, and evaluated in the remaining time without violating the
   equal-tuning-budget requirement. This is a rule, not a preference.
2. **D3-0 is time-boxed to August 9.** If no cohort qualifies, stop and present the
   frozen contract as the specified first experiment of the next phase. Do not weaken
   the minima to produce a runnable cohort.
3. **August 16 is frozen.** No new number enters the deck on the last working day.

---

## 3. Track 1: the deck (primary)

Create a separate `presentation/2026-08-17-final.html`, preserving the July 30 deck.
It contains one title/objective slide, the five content slides below, and a compact
technical appendix. The narrative does not depend on D3-0 or B1, so the deck can be
built to completion starting today. Use `presentation/design.md`, unchanged.

| # | Claim | Numbers | Figure source |
|---|---|---|---|
| 1 | Organ specialization improves reconstruction on external data | 3.797% true-organ, 3.633% hard, 3.676% soft; 821 samples, 63 studies, all 3 seeds | new bar chart from `docs/stage-1-end-result.md` |
| 2 | Naive cross-organ sharing produced no reproducibly helpful rule | 0/8 stable helpful and 2/8 stable harmful additive edges; 56/56 compute-matched substitution edges negative | **exists:** `presentation/2026-07-30-stage2-directed-transfer-heatmap.png` and `-additive-effects.png` |
| 3 | Secondary axes do not survive matched-capacity controls | tissue site beaten by parameter-matched generic adapter by 0.461%, 0.534%, 0.544%, all seeds | new small chart from `docs/tissue-site-tier2-result.md` |
| 4 | Downstream transfer fails under the frozen output contract; diagnostics narrow the bottleneck | see below | **new, two panels** |
| 5 | What we would do next, specified in advance | D3-0 minima, primary-organ headroom gate 0.60 to 0.90, prospective safeguards | text plus a small gate table |

### Slide 4 specification

This is the slide that distinguishes a project that diagnosed a failure from one that
merely had one. It carries four eliminations and two findings.

**Panel A, the ceiling:** muscle-only AUROC bars. Raw 0.9675, PCA-64 0.9623, learned
representations 0.5578 to 0.7563 with seed range shown. Source
`docs/post-d2-phase1-interim-result.md` E1.

**Panel B, reduced accessibility:** low-label curve, AUROC against labeled fraction at 5% and
10%. Raw 0.6289 and 0.7313, PCA 0.6329 and 0.7203, learned 0.4890 to 0.5339. Source
E3. This panel carries F1's reframe and is the more important of the two.

**Gross failure explanations narrowed by convergent checks, summarized visually:**

- encoder degeneracy: cross-species organ transfer at 0.7519, 0.7553, 0.6992 balanced
  accuracy against $1/7$ chance, GTEx-trained boundary applied unchanged;
- ortholog imputation: missing-entry fraction $1.56\times10^{-4}$;
- normalization mismatch: constant-gene fraction $8.32\times10^{-4}$, identical value
  space;
- pathway feature engineering: Hallmark+PCA 0.732630 against PCA 0.732770.

**Two findings, stated separately per F3:** benchmark ceiling, and specialization
instability across seeds.

**Tone.** Do not apologize for the negative. Convergent prespecified checks narrowed
the bottleneck while sharing one accessed cohort; do not call them statistically
independent or claim that one unique cause has been proven.

**Definition of done, Aug 4:** all five slides exist with real numbers and placeholder
figure boxes. **Aug 7:** all figures final. **Aug 13:** deck complete.

---

## 4. Track 2: Track A confirmation contract (Aug 8 to 9, not droppable)

Write and freeze the untouched-cohort reconstruction confirmation protocol. **Do not
execute it.** A pre-registered, hash-pinned, unexecuted protocol is a credible
deliverable and is the correct answer to "what would make the Stage 1 result pristine."

Contents, frozen before any expression access:

1. overlap firewall: exclude every GTEx training/calibration donor and every external
   study accession used in the 63-study ARCHS4 evaluation; also exclude duplicate
   samples, donors, BioProjects, and accessions across candidate sources;
2. expression source, release, accession normalization, and cross-source de-duplication
   rules fixed before membership is inspected; recount3 is an alternative source only
   if its studies are demonstrably independent of the accessed ARCHS4 studies;
3. organ mapping, exclusions, QC thresholds identical to the existing contract, with
   the 14,000-nonzero-gene rule stated explicitly and no post-access amendment
   permitted;
4. minimum studies and samples per organ, plus a metadata/QC-only deterministic rule
   for excluding an under-covered organ with no replacements;
5. one frozen primary aggregate organ set, or a deterministic metadata-only rule for
   deriving it before outcomes;
6. conditions: pooled, true-organ, hard router, soft router, random-K8, equal-capacity
   generic adapter, each tied to exact immutable checkpoint hashes;
7. all three seeds reported, no best-seed selection;
8. one primary aggregate MSE estimand with paired study-bootstrap intervals; per-organ
   results are mandatory safety/descriptive analyses and may not redefine membership;
9. expression-file, membership, checkpoint, protocol, and evaluator hashes recorded
   before execution.

**Definition of done:** protocol JSON committed with recorded SHA256, plus a short
document explaining that it is deliberately unexecuted and why.

---

## 5. Track 3: D3-0 metadata readiness (parallel, time-boxed to Aug 9)

Metadata only. **No expression access.** Per CLAUDE.md 12.2 Q2, the minima are:

| Requirement | Value |
|---|---|
| two-class studies in the primary estimand | $\ge 10$ |
| samples per class | $\ge 80$ |
| total retained samples | $\ge 200$ |
| samples in the primary organ | $\ge 60$ |
| studies per class within the primary organ | $\ge 3$ |
| single-class studies in the primary estimand | none permitted |
| label varies within study | required |
| per-organ reporting | mandatory from the first analysis |

**Headroom is a deterministic primary-organ rejection gate, not an observation.** The
exact acceptance band is `0.60 <= raw-expression AUROC <= 0.90` in the prespecified
primary organ. Outside it is automatic rejection. The earlier 0.65–0.85 range is
descriptive only and has no selection role. Every adequately powered organ and the
pooled macro-average are reported. A secondary organ above 0.90 cannot contribute to a
pooled headline, although it may remain a labeled secondary ceiling analysis if the
primary organ passes.

Candidate-family order is frozen from metadata only. Evaluate sequentially and stop at
the first candidate satisfying every gate. Record every rejection and never recycle a
rejected development cohort for confirmation. Require a study-bootstrap interval above
chance, a frozen single-study dominance check, and reservation of an untouched grouped
confirmation cohort before supervised training.

**Candidate families, in priority order.** Availability must be confirmed by the audit;
these are selection criteria, not verified accessions.

1. **Human disuse or bed-rest skeletal-muscle atrophy.** First choice, and the only
   family satisfying four conditions at once: it is the established terrestrial
   analogue of spaceflight muscle loss, so the biology matches the one signal this
   project has observed; designs are paired within subject, which guarantees rather
   than hopes for within-study label variation; skeletal muscle is one of the eight
   organs; and the effect is real without being tumor-versus-normal saturated. Risk:
   individual studies are small, so aggregate study count must be checked first.
2. **Acute exercise response in muscle biopsies.** More studies, guaranteed paired
   designs, real ceiling risk that the headroom gate would catch.
3. **Controlled hypoxia or pharmacological challenge** with paired pre/post sampling.

Deprioritize inflammatory-challenge blood cohorts despite their strong designs, since
blood is outside the eight-organ contract.

**Definition of done, Aug 9:** either one frozen cohort contract with all minima
satisfied and hashes recorded, or a written infeasibility record naming which minima
failed and by how much. Both are presentable outcomes. A cohort produced by relaxing a
minimum is not.

---

## 6. After August 17: Track B, supervised readout and representation development

Specified now so the deck's slide 5 is concrete, and so no part of it leaks into the
pre-deadline schedule.

**Design, per CLAUDE.md Sections 14 and 15.** No arm may run until its tensor contract,
configuration count, grouped splits, controls, checkpoints, and gates are independently
hash-frozen.

- **Arm 1 — linear supervised-readout feasibility.** A logistic elastic-net probe on
  the exact concatenation of frozen pooled hidden state and the input-only soft-routed
  `adapter_bottleneck_activation`. It uses the same nested study-grouped harness and
  exact configuration budget as raw and fold-fit PCA.
- **Arm 2 — nonlinear supervised projection.** One prespecified 64-dimensional
  projection, normalization, nonlinearity, and linear classifier on the same frozen
  tensors. It receives an exact configuration count and parameter-matched pooled-only
  and generic-capacity controls. Arm 1 and Arm 2 may run together; Arm 2 failure closes
  these two prespecified frozen-feature approaches on this benchmark, not every
  theoretically possible nonlinear probe.
- **Arm 3 — objective-aligned encoder extension.** A separately protocolled partial
  unfreeze with reconstruction retention. It is a new weight family, is never the
  headline representation-quality result, and may be considered only after Arm 2 fails
  and the calibration-retention reference below is estimable.

E2's `prediction_residual` means observed minus predicted score-panel expression. It is
not an input to Track B and must never be conflated with the routed adapter bottleneck.

**Calibration-retention prerequisite for Arm 3.** Before computing any value, freeze a
separate protocol defining, for each seed, the GTEx donor-disjoint calibration gain

`G_cal = 100 * (MSE_pooled - MSE_true_organ) / MSE_pooled`,

including exact split and membership hash, checkpoint hashes, mask schedule, score
panel, estimator, donor bootstrap, and the fixed 90% retention fraction. If any seed has
`G_cal <= 0` or a donor-bootstrap lower bound at or below zero, the ratio is
`NOT_ESTIMABLE` and Arm 3 is not authorized. No fallback threshold may be invented.
The accessed 3.797% ARCHS4 result is never recomputed or used for development.

**Future Arm-3 tolerances, measured only on the named GTEx development-calibration
split:**

| Tolerance | Value |
|---|---|
| organ-specialization gain retained | $\ge 90\%$ of each seed's valid frozen $G_{\mathrm{cal}}$ |
| absolute reconstruction MSE | $\le 1\%$ worse than the frozen package on the same split |
| per-organ reconstruction safety | no organ worse than $2\%$ relative MSE on the same split, every seed |
| per-organ downstream safety | no organ's AUROC below the matched pooled control by more than $0.05$, every seed |
| reference computation | training folds only, cross-fitted; calibration never enters the loss |

**Mandatory controls and advance gates:** raw expression with a tuned linear model,
fold-fit PCA with an equal tuning budget, pooled encoder with a matched head,
equal-capacity generic adapter, within-organ shuffled state labels, and blind hard and
soft routing. BulkRNABert and BulkFormer enter the final comparison once their exact
preprocessing, gene mapping, checkpoint, and embedding contracts are reproducible.

A branch advances only if blind organ-aware beats matched pooling in every fixed seed
with paired study-bootstrap lower bounds above zero, beats raw and PCA in every seed
for Q-A, has no per-organ safety failure, preserves noncollapsed routing, and is not
matched by generic-capacity or shuffled-state controls. Equal tuning budget means an
exact frozen configuration count under the same nested grouped evaluation—not a prose
promise of comparable effort.

**Report Q-A and Q-B separately and always.** Q-A is whether the blind organ-aware model
beats raw and PCA. Q-B is whether it beats a matched pooled model. Conflating them
produced a negative result that took three review rounds to interpret correctly.

---

## 7. What not to do

- Do not mine OSDR further for a favorable layer, seed, organ, fraction, or residual.
- Do not average away the seed-101 reversals in 3.6 and E4.
- Do not reopen tissue site, Hallmark, age, or sex after their frozen gates failed.
- Do not fine-tune the frozen K8 package and continue calling it the externally
  validated model.
- Do not access ARCHS4 expression while designing the confirmation cohort.
- Do not claim retained organ geometry implies retained state information. The
  cross-species transfer result at 0.70 to 0.76 says nothing about state retention, and
  the low-label result argues directly against it.
- Do not let benchmark ceiling absorb the specialization-instability finding.
- Do not begin B3 before August 17.
- Do not add a number to the deck on August 16.

---

## 8. The one-sentence version

> Organ specialists robustly improve masked-gene reconstruction on external human data,
> but reconstruction alone does not yield a perturbation-state representation under the
> tested frozen output contract, and convergent diagnostics narrowed the bottleneck;
> the next design adds explicit within-organ state supervision on a benchmark selected
> in advance to have measurable headroom.
