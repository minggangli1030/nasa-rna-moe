# Stage 3 execution brief: mask-consistent, residual-aligned representation

**Written:** 2026-07-30
**Audience:** implementation agent (Codex) plus human reviewer
**Supersedes for planning purposes:** the "Prioritized future plan" section of
`docs/stage2-aligned-program-repair-result.md`
**Does not supersede:** any frozen protocol, immutable result, or checksum manifest.

Canonical status remains `docs/current-status.md`. This document adds (a) the
methodological critique of Stage 2 that was not written down anywhere, (b) an
ordered, gated work plan, and (c) explicit decision trees so that no branch point
requires a fresh judgment call mid-run.

---

## 0. How to use this document

1. Read Section 1 (invariants) before writing any code. They are not negotiable.
2. Execute Section 4 (Step 0) first. It is blocking and cheap.
3. Execute Section 5 (Step 1 triage). It is read-only, requires no training, and
   can invalidate Section 6 entirely. Do not skip ahead.
4. Branch using Section 6. Only then implement Stage 3.
5. If Stage 3 fails its gates, use Section 9 rather than inventing a repair.

Anything labeled **HYPOTHESIS** is untested and must not be reported as a finding.
Anything labeled **GATE** is preregistered and must be frozen before data are seen.

> **STOP. READ THIS BEFORE IMPLEMENTING ANYTHING FROM SECTIONS 1 TO 13.**
>
> Sections 1 to 13 are the round-1 proposal and contain material that was **retracted**
> in Sections 15 and 16. The canonical execution plan is
> `docs/stage2b-mask-consistent-sharing-plan.md`. This file is the review record.
>
> Do **not** implement from these sections without reading their replacement:
>
> | Section | Status | Replacement |
> |---|---|---|
> | 3.3 (donor rank $K-1$ cap) | **RETRACTED, wrong** | 14.2, 15.1 R1, 15.2 |
> | 3.2 / rank metric | **imprecise** | 14.3, 15.1 R2 |
> | 5, D1 | superseded | 14.8, 15.3 Q9, Phase B1 |
> | 5, D3 | superseded | 14.2, Phase B3 |
> | 5, D4 attribute list | **RETRACTED, GTEx-invalid** | 14.9, Phase B4 |
> | 6 decision tree | superseded | 16.5 |
> | 7.1 (input side only) | **incomplete, unsafe** | 14.4, 15.1 R3, Phase C |
> | 7.2 (pathway leakage rule) | **RETRACTED, wrong** | 14.5, 15.1 R4 |
> | 7.2 (basis first) | superseded | 16.5 |
> | 7.3 (thresholded $g_o$) | superseded | 14.10, 15.3 Q8 |
> | 7.4 (D1a weights) | **RETRACTED** | 17.4 |
> | 7.5 (parallel track) | deferred | 14.12, 15.1 R7, 16.5 |
> | 8, GATE-R | superseded | 14.2, Phase B3 gate |
> | 10 (raw substitution harm) | **RETRACTED, confounded** | 14.6, 15.1 R5, Phase B5 |
> | 13.2, Fix 1 | corrected in place | see below |
>
> Sections 1, 2, 4, 9, 11, 12 stand as written. Section 13.1 stands with the
> amendments in 17.1.

---

## 1. Project invariants

These reflect existing project discipline. Preserve them.

- **No post-outcome tuning.** Thresholds are frozen in a protocol JSON with a
  SHA256 recorded before the run. They are never changed after seeing results.
- **No seed, organ, component, or checkpoint selection.** All seeds reported.
- **Donor-disjoint splits** for GTEx; **study-disjoint** for ARCHS4.
- **ARCHS4 is a scarce resource.** No Stage 3 development touches it. External
  evaluation happens once, at the end, on an untouched study-disjoint cohort.
- **Immutable results.** Every run writes a checksum manifest; evaluators load
  numeric arrays only, no pickle, with labels reconstructed from a hash-pinned
  manifest.
- **Organ experts remain the benchmark**, not a restriction. Any new axis must beat
  organ and pooled controls, not merely beat pooled.
- **Deterministic FP32** training as in prior stages.
- Report every seed and every organ. Aggregate-only reporting is how the skin
  regression nearly escaped notice.

---

## 2. Established findings (carry forward)

| Stage | Finding | Numbers |
|---|---|---|
| 0 | Expression-only species router works | 99.0% balanced accuracy |
| 1 | Organ specialization transfers externally | GTEx to ARCHS4: 3.797% true-route, 3.633% hard auto, 3.676% soft auto; 821 samples, 63 studies, 8 organs; all 3 seeds positive |
| 2 | Same-budget substitution is uniformly harmful | 56/56 directed edges negative in 3/3 seeds, mean $-3.273\%$ |
| 2 | Recipient-preserving addition is not actionable | 0/8 edges beat the A2250 more-target-data control in all seeds |
| 2 | Helpful transfer is seed-unstable, harmful transfer is not | crossed $3\times3$: 0/8 stable helpful, 2/8 stable harmful (brain $\leftarrow$ skin $-0.883\%$; skin $\leftarrow$ adipose $-3.369\%$) |
| 2 | A shared residual path is genuinely useful | repair: $+37.8\%$, $+34.1\%$, $+35.8\%$ vs pooled; $+3.2\%$, $+5.9\%$, $+6.4\%$ vs frozen private path; beat random basis in all seeds |
| 2 | The 32-dim expression-PCA coordinate system is not a valid representation | sample/donor/within-organ effective rank $1.815 / 1.392 / 1.952$ vs gates $8 / 6 / 8$; flattened donor correlation $0.271$ vs $0.5$; skin harmed $-5.890\%$ and $-6.478\%$ vs the $5\%$ safety gate |

Supporting mechanism, from the read-only collapse diagnosis:

- The frozen decoder is **not** low rank (effective rank $29.00$), so collapse is
  not a decoder artifact.
- The oracle residual projected into that same span has sample-level effective rank
  $12.89$ to $14.34$ and within-organ rank $16.48$ to $17.04$. **A high-rank target
  exists.**
- A five-fold donor-grouped linear probe on the existing global hidden summary
  recovered oracle coefficients at rank $12.40$, median component correlation
  $0.963$, and $69.8\%$ of remaining error versus $33.6\%$ for the trained head.
- The learned leading direction is stable across seeds (cosine $0.926$ to $0.985$),
  explained by organ ($\eta^2 \approx 0.87$) and tissue site ($\eta^2 \approx 0.89$),
  loads on brain/CNS markers (`GFAP`, `MBP`, `SLC1A2`, `OLIG1`, `SNCB`), and
  correlates with pooled reconstruction difficulty ($0.671$ to $0.717$).

**Read that combination carefully.** The information is present, a linear probe
finds it, and end-to-end training does not. That is an objective/optimization gap,
not proof that the basis is wrong. The single largest difference between the probe
and the trained head is the masking distribution. This is why Section 5 comes
before Section 7.

### Known-invalid results, do not cite

The nominal `extended_private` and `extended_generic` controls in the repair run are
invalid. A cosine scheduler drove the reused optimizer learning rate to zero after
phase 1, and phase 2 attached a new scheduler without restoring the base learning
rate. Phase-1 and "extended" checkpoint tensors and score arrays are byte-identical
in all three seeds. The candidate and random-basis heads used fresh optimizers and
are unaffected. The pivot decision does not depend on these controls.

---

## 3. Open methodological concerns

Written down because they were not previously recorded. Each is testable.

### 3.1 Target identifiability under masking (highest priority)

Training projected residuals from draws where $30\%$ of score genes were masked;
calibration masked all score genes. The coefficient target is

$$c(x, M) = \arg\min_c \left\| r_M(x) - D_M c \right\|^2
= (D_M^\top D_M)^{-1} D_M^\top r_M(x),$$

where $M$ is the mask and $D_M$ restricts the decoder to masked rows. There are two
**independent** sources of mask dependence, and they have different implications:

1. **Behavioral.** The residual $r_M(x)$ itself changes, because the model saw
   different inputs. This is a real property of the model.
2. **Geometric.** The normal equations change, because the solve happens on a
   different row subset. At $30\%$ masking, $D_M^\top D_M$ is far worse conditioned
   than at full mask, so weak coordinates are barely identified. This has nothing to
   do with biology.

**HYPOTHESIS:** source 2 dominates. It predicts exactly the observed signature,
namely agreement on dominant tissue/difficulty axes and disagreement on weak
coordinates.

If either source is material, the target is **not a function of the sample**, and no
representation could be stable. Under that condition Stage 2 tested an ill-posed
problem, and the verdict "expression PCA is the wrong basis" is unsupported.

**The correct response is to remove the dependence by construction (Section 7.1),
not to measure it and hope.** D1 is therefore retained as an explanatory ablation
rather than a blocking gate. See Section 5, D1.

### 3.2 Effective rank is scale-dependent

If effective rank is participation ratio
$\mathrm{PR} = \left(\sum_i \lambda_i\right)^2 / \sum_i \lambda_i^2$
computed on unwhitened coefficients in an expression-PCA basis, collapse is close to
guaranteed by construction, because $\lambda_1 \gg \lambda_2$ in that basis. The
repair standardized coefficient *targets*; confirm whether the *diagnostic* was
computed on standardized coefficients. Report $\mathrm{PR}$ under both raw and
per-component-standardized scaling, plus the full eigenvalue spectrum, not a scalar.

### 3.3 The donor-level rank gate was arithmetically unpassable (settled, not open)

This no longer needs a resampling study. It follows in closed form.

There are $K = 8$ organs, so between-organ coefficient covariance has rank at most
$K - 1 = 7$. For participation ratio
$\mathrm{PR} = \left(\sum_i \lambda_i\right)^2 / \sum_i \lambda_i^2$ over at most
seven nonzero eigenvalues:

| Spectrum over 7 dims | $\mathrm{PR}$ |
|---|---:|
| flat, all $\lambda_i = 1$ | $7.00$ |
| $\lambda_1 = 2$, remaining six $= 1$ | $64/10 = 6.40$ |
| $\lambda_1 = 3$, remaining six $= 1$ | $81/15 = 5.40$ |
| $\lambda_1 = 5$, remaining six $= 1$ | $121/31 = 3.90$ |

Passing the frozen donor-level gate $\mathrm{PR} \ge 6$ therefore required
$\lambda_1 / \lambda_2 \lesssim 2.3$, that is, a **near-isotropic** set of
between-organ contrasts. Given a brain-versus-everything-else axis that the collapse
diagnosis measured at $\eta^2 \approx 0.87$ and roughly $75$ to $78\%$ of decoded
output energy, no realistic tissue panel satisfies that.

**The gate was not strict, it was unreachable.** Retire it, with this table as the
written justification (Section 8). The within-organ gate is not capped by $K - 1$ and
survives, but must be re-expressed relative to an attainable ceiling rather than as
an absolute constant.

### 3.4 Seed stability is being measured on the wrong object

Coordinates rotate freely under reparameterization; sharing decisions do not.
Per-direction correlation between seeds is not identified when eigenvalues are close.
Measure subspace agreement with CCA or a Grassmann/principal-angle distance, and add
a **functional** stability metric: agreement of the induced per-organ gain/harm
vectors and of the ranked sharing decisions across seeds. A representation that
yields the same sharing policy under different seeds is what the project actually
needs.

### 3.5 The reproducible finding is negative transfer, and it is being underused

Across every Stage 2 experiment, helpful relationships were unstable and harmful
relationships replicated. That asymmetry is the result. A policy of **private by
default, share only where a validated gate permits** is directly buildable from what
is already known, and would have prevented the skin regression. Learning when to
*decline* to share is both easier and more valuable than learning when to share.

### 3.6 Organ safety belongs in the objective, not only in evaluation

Skin was harmed because nothing in the loss protected it. A per-organ scalar gate
$g_o \in [0,1]$ on the shared contribution, initialized at $0$, lets the model learn
to refuse sharing. $g_{\text{skin}} \to 0$ then becomes a *finding* rather than a
failure, and it is directly interpretable as the sharing rule.

### 3.7 Three seeds is thin for reproducibility claims

Claims of the form "stable across seeds" from $n = 3$ trunks are weak. Use $\ge 5$
for any Stage 3 stability claim, and model seed as a random effect in per-organ
deltas rather than reporting min/max.

### 3.8 The rank gate may be measuring the wrong success condition

An eight-direction interpretable basis is a proxy. The deliverable is a sharing
policy. Add a direct decision-utility gate (Section 8, GATE-U) so that a useful,
reproducible, safe policy can pass even if it is low rank, and an interpretable but
useless basis cannot pass.

---

## 4. Step 0: harness fixes (blocking, do first)

**T0.1 Learning-rate assertion.** Add a fail-closed check in the training loop:
after the first $N$ updates of every phase, assert that (a) every optimizer param
group has `lr > 0`, and (b) the L2 norm of the parameter delta for each trainable
module exceeds a small tolerance. Abort the run otherwise.

**T0.2 Phase-transition contract.** Multi-phase training must construct a new
optimizer and scheduler per phase, or explicitly restore `base_lrs`. Add a unit test
that runs a two-phase toy training and asserts the phase-2 parameters differ from
phase-1 parameters.

**T0.3 Checkpoint-identity guard.** After each phase, hash the trainable tensors.
Assert that consecutive phases do not produce identical hashes when the phase was
supposed to train. This would have caught the invalid controls automatically.

**T0.4 Seed count.** Raise the standard stability design from 3 to 5 trunk seeds.
Keep 17, 42, 101 and add 2 new fixed seeds recorded in the protocol.

**T0.5 Per-organ reporting by default.** The evaluator must emit a
seed $\times$ organ matrix of relative deltas for every condition. No condition may
report only an aggregate.

Acceptance: all tests pass in `tests/`; no scientific run launches until they do.

---

## 5. Step 1: read-only diagnostic triage

No training. No ARCHS4. Training donors only. Uses existing frozen checkpoints.
Freeze one protocol JSON covering D1 to D4 and record its SHA256 before running.

### D1. Mask-target invariance (explanatory, no longer blocking)

**Status change.** D1 was originally a blocking gate that decided whether to keep the
expression-PCA basis. It is demoted, because Section 7.1 removes mask dependence by
construction regardless of the answer. There is no branch in which the right move is
to keep a mask-dependent target. D1 now exists to (a) explain the Stage 2 failure
correctly in the addendum, and (b) set the identifiability weights used in
Section 7.4.

Run it anyway. It is cheap and it determines what sentence goes in the record.

**D1a. Full-versus-partial comparison.** For each calibration sample, compute
least-squares coefficient targets in the frozen decoder span under $R$ independent
partial masks at the training rate ($30\%$ of score genes) and under the full-mask
scheme. Report:

1. mean pairwise cosine between coefficient vectors across repeated partial masks,
   per component and overall;
2. cosine between mean partial-mask target and full-mask target;
3. the same per component, ordered by component index, to test whether agreement
   decays with component strength as HYPOTHESIS 3.1 predicts;
4. across-mask variance relative to across-sample variance per component, that is,
   target noise-to-signal in coefficient space. **Persist this vector.** It becomes
   the per-component supervision weight in Section 7.4;
5. whether skin samples show systematically worse mask agreement than other organs.

**D1b. Source-separation ablation (the scientifically informative half).** Hold the
residual vector $r$ fixed at its full-mask value and vary *only* the row subset used
in the least-squares solve. Compare against the full D1a variation, which moves both.

- If D1b reproduces most of the D1a disagreement, the instability is **geometric**
  (conditioning of $D_M^\top D_M$), and the Stage 2 addendum should say the basis was
  never fairly tested.
- If D1b is small and D1a is large, the instability is **behavioral**, meaning the
  model genuinely predicts differently under partial masking. That is a real property
  worth reporting and does not exonerate the basis.

Also report $\kappa(D_M^\top D_M)$ at both masking rates, and the per-component
leverage, so the geometric claim is quantified rather than asserted.

**D1 output:** the addendum sentence, plus the frozen per-component identifiability
weight vector. No go/no-go decision.

### D2. Rank measurement audit

Recompute learned-coefficient effective rank on the existing frozen repair outputs
under: (a) raw coefficients, (b) per-component standardized coefficients, (c)
decoder-whitened coordinates. Report the full eigenvalue spectrum and the cumulative
variance curve for each. State explicitly which convention the frozen gate used.

### D3. Attainable-rank ceiling (reduced scope)

Section 3.3 settles the donor-level question in closed form, so no power analysis is
needed to retire that gate. D3 is now only about establishing the **ceiling** that the
replacement within-organ gate is expressed against.

1. Compute oracle projected-residual coefficient $\mathrm{PR}$ at sample, donor, and
   within-organ level, under all three scaling conventions from D2. The existing
   figures ($12.89$ to $14.34$ sample, $16.48$ to $17.04$ within-organ) were computed
   under one convention only and must be recomputed consistently.
2. Bootstrap over donors to get an interval on the within-organ oracle ceiling. The
   gate is set from the lower bound, not the point estimate.
3. Confirm empirically that donor-level oracle $\mathrm{PR}$ sits below $7$, as
   Section 3.3 predicts. If it does not, something is wrong with the rank code and
   that is itself a finding.

**D3 output:** the frozen oracle ceiling $\mathrm{PR}^{\text{oracle}}_{\text{within}}$
used by GATE-R.

### D4. Metadata variance decomposition (cheap, high value, no model changes)

Regress per-sample pooled reconstruction error, and separately the organ-expert
residual, on available metadata: tissue site, platform, study/batch ID, library size,
sequencing depth, detected-gene count, RIN or equivalent quality, sex, age bracket.
Use nested/grouped cross-validation, report partial $R^2$ per attribute, and compare
each against organ.

This is the cheapest possible test of "broaden beyond organ labels." If platform or
study explains more residual variance than organ does, the project's axis choice
changes and Section 7 must be rewritten before implementation.

---

## 6. Decision tree after triage

Section 7.1 is executed unconditionally, so D1 no longer gates the design. It gates
only the *record* and the supervision weights.

```
D1 result?  (does not block; Section 7.1 runs either way)
├── Geometric instability dominates (D1b reproduces most of D1a)
│   → Addendum to docs/stage2-aligned-program-repair-result.md: the
│     expression-PCA basis was never fairly tested, because the target was
│     not identified at the training masking rate.
│   → Because the basis was never fairly judged, keep B-pca as an arm in
│     Section 7.2. Basis becomes an experimental factor, not a foregone
│     conclusion. Cost is one extra arm; the alternative is discarding a
│     representation on confounded evidence.
│
└── Behavioral instability dominates (D1b small, D1a large)
    → The model really does behave differently under partial masking. The
      Stage 2 verdict on the basis stands. Drop B-pca; run Section 7 with the
      residual and pathway bases only.
    → The probe-vs-trained-head gap (69.8% vs 33.6%) is then an OPTIMIZATION
      failure, not an identifiability one. The Section 7.4 auxiliary
      coefficient loss with warmup is mandatory, not optional.

In BOTH branches: the per-component identifiability weights from D1a.4 are
frozen into the S3 protocol and used in Section 7.4.

D2 result?
├── Rank gate was computed on raw coefficients and standardized rank is
│   materially higher → the collapse conclusion is partly a measurement
│   artifact. Report this prominently. Re-derive the gate convention and
│   freeze it explicitly for S3.
└── Rank is low under all three conventions → collapse is real. Proceed.

D3 result?
→ Donor-level PR ≥ 6 is retired unconditionally per Section 3.3. D3 only
  supplies the frozen within-organ oracle ceiling used by GATE-R.

D4 result?
├── A non-organ attribute explains more residual variance than organ
│   → PAUSE Section 7. Write a short design note proposing that attribute as
│     the primary sharing axis, with organ retained as benchmark. Get human
│     approval before implementing.
└── Organ dominates → proceed to Section 7 as written.
```

---

## 7. Step 2: Stage 3 design (S3)

Implement only after Section 6 routes here. Freeze the protocol JSON and record its
SHA256 before any fitting.

### 7.1 Mask consistency by construction (mandatory in every arm)

The map from sample to target must be mask-free on **both** ends. Fixing only the
input, as originally drafted, leaves the geometric problem in Section 3.1 intact.

**Input side (canonical input).**

- The shared head reads **only genes visible under both training and evaluation**,
  that is, the non-score gene set. This removes the partial-to-full-mask input shift.
- Its target may then use **all** score-gene residuals, since none of them were
  visible to the head. No visible-target leakage.
- Assert on index sets:
  `assert set(head_input_idx).isdisjoint(set(score_gene_idx))`. Verify by
  construction, not by inspection.

**Target side (canonical target). This is the new requirement.**

- Compute the coefficient target **once per sample**, from a single full-mask forward
  pass over the fixed score-gene set, and cache it keyed by sample ID and the
  hash-pinned manifest.
- Every training draw for that sample uses the identical cached target, regardless of
  which genes that draw masked. The target is then a function of the sample by
  definition, and D1's question cannot recur.
- The row set in the least-squares solve is **always** the full score-gene set. Never
  solve on the draw-specific masked subset. This is the specific line that caused the
  Stage 2 instability.
- Assert that the cached target tensor for a given sample ID is bitwise identical
  across epochs. Fail closed if not.

**Conditioning.**

- Solve the projection as ridge, $c = (D^\top D + \lambda I)^{-1} D^\top r$, with
  $\lambda$ frozen in the protocol before any fitting. Report effective degrees of
  freedom $\mathrm{tr}\!\left[D (D^\top D + \lambda I)^{-1} D^\top\right]$ alongside
  every rank number, so a rank claim is always paired with the regularization that
  produced it.
- Select $\lambda$ on training donors only, by cross-fitted reconstruction of held-out
  residuals, never by looking at rank or at any gate quantity.

**Why this ordering matters.** Canonical input alone leaves the head predicting a
target that still moves. Canonical target alone leaves a covariate shift in the
input. Both together make the entire learned map independent of the masking
distribution, which is the actual precondition for any stability claim.

### 7.2 Basis (experimental factor, per Section 6)

- **B-resid:** decoder frozen from **cross-fitted** training-only reconstruction
  residuals. Cross-fitting is mandatory; fitting the basis on the same residuals the
  head is trained against fits our own noise.
- **B-path:** preregistered pathway aggregates (for example Hallmark or Reactome),
  restricted to the both-visible gene set. **Leakage check:** any pathway whose gene
  set intersects the score-gene set must be either restricted or excluded, decided
  before fitting and recorded in the protocol.
- **B-pca:** the existing expression-PCA decoder, included only under D1-UNSTABLE.
- **B-rand:** random orthonormal basis of matched dimension. Always included.

### 7.3 Architecture

Keep the validated organ-private path. Train it first and freeze it, as in the
repair. Then:

- shared head $\to$ coefficients $c$ $\to$ fixed decoder $D$ $\to$ correction $Dc$;
- **per-organ scalar gate** $g_o \in [0,1]$, initialized at $0$, multiplying the
  shared contribution: prediction is
  $\hat{y} = \text{private}_o + g_o \cdot D c$;
- $g_o$ is learned. It is a first-class output, not a nuisance parameter. The
  learned $\{g_o\}$ vector **is** the sharing rule.

### 7.4 Objective

- decoded reconstruction MSE, plus
- direct per-component standardized coefficient supervision on the cross-fitted
  residual targets, with a warmup, **weighted by identifiability**, plus
- an explicit per-organ no-harm penalty: hinge on
  $\max(0, \text{loss}_o - \text{loss}_o^{\text{private}})$, so degrading an organ
  relative to its frozen private baseline is penalized during training rather than
  only detected afterwards.

**Identifiability weighting (new).** Weight the coefficient loss on component $i$ by

$$w_i \propto \left(1 + \frac{\sigma^2_{\text{mask},i}}{\sigma^2_{\text{sample},i}}\right)^{-1},$$

using the across-mask and across-sample variances measured in D1a.4, normalized to
$\sum_i w_i = $ number of components and frozen in the protocol. Coordinates the data
cannot pin down are down-weighted rather than fitted as noise. This is a
measurement-error correction, not a tuning knob: the weights are computed once from a
read-only diagnostic and never adjusted after seeing S3 results.

Note that under Section 7.1 the canonical target should make
$\sigma^2_{\text{mask},i}$ small by construction. The weights are belt-and-braces and
also serve as a check: if D1a shows large residual mask variance *after* the canonical
target is in place, the caching is broken.

### 7.5 Parallel track: gated shared experts (run alongside, not instead)

Cheaper and more direct than any explicit basis. $M$ shared experts plus per-organ
mixture weights over $\{$private, shared expert $1 \ldots M\}$, learned end-to-end.
Effective rank becomes "how many shared experts are actually used," which needs no
PCA and no oracle projection. The learned organ-by-expert weight matrix is directly
inspectable and directly seed-comparable. If this track passes gates and the basis
track does not, prefer it: it answers the project question with fewer assumptions.

### 7.6 Controls (all mandatory, all seeds)

organ-private only; pooled; matched-capacity generic; **valid** extended-private and
extended-generic (fixed per T0.1 to T0.3); random basis; random-attribute assignment.

---

## 8. Preregistered Stage 3 gates

Freeze all of these, with the exact convention from D2, before running.

- **GATE-U (utility, new and primary).** The learned policy must beat both the
  pooled model and the fully organ-private model on held-out donor-disjoint
  evaluation, in $\ge 4$ of 5 seeds, with donor-bootstrap intervals above zero.
- **GATE-S (safety).** No organ degrades by more than $3\%$ relative to its frozen
  organ-private baseline in any seed. Tightened from $5\%$ because Stage 2 showed
  aggregate gains hide concentrated harm.
- **GATE-F (functional stability).** Cross-seed Spearman correlation of the
  per-organ gain/harm vector $\ge 0.7$, and cross-seed agreement of the binary
  share/decline decision (thresholded $g_o$) $\ge 7/8$ organs, for all seed pairs.
- **GATE-R (representation, secondary; RESTATED).** The absolute threshold is
  replaced by a **ratio to the attainable ceiling**:

  $$\frac{\mathrm{PR}^{\text{learned}}_{\text{within}}}{\mathrm{PR}^{\text{oracle}}_{\text{within}}} \ge \alpha,
  \qquad \alpha = 0.5,$$

  with $\mathrm{PR}^{\text{oracle}}_{\text{within}}$ frozen from the D3 bootstrap
  lower bound and both terms computed under the same D2 convention.

  This is not a relaxation. The repair scored $1.95 / 16.5 \approx 0.12$, so it fails
  at any defensible $\alpha$. The change makes the gate *well-posed*: it can be
  satisfied in principle, and it fails for the right reason.

  **The donor-level gate $\mathrm{PR} \ge 6$ is retired**, with the Section 3.3 table
  as the recorded justification. It required near-isotropic between-organ contrasts
  over at most $K - 1 = 7$ dimensions and was unreachable given a dominant
  brain-versus-other axis. Report donor-level $\mathrm{PR}$ descriptively, gate
  nothing on it.

  Every rank number reported must be accompanied by the full eigenvalue spectrum, the
  cumulative variance curve, the scaling convention, and the ridge $\lambda$ and
  effective degrees of freedom from Section 7.1.
- **GATE-A (subspace alignment).** Mean principal-angle-based subspace overlap
  across seeds, computed by CCA on the top-$k$ coefficient subspace, above a
  threshold set from the B-rand null distribution rather than an arbitrary constant.
- **GATE-C (control dominance).** Must beat B-rand and random-attribute assignment
  in every seed.

**Critical change from Stage 2:** GATE-U and GATE-F are primary. GATE-R is
secondary. A representation that produces a reproducible, safe, useful sharing
policy is a success even at rank 2, provided that result is reported honestly as
"the transferable structure is low dimensional and is dominated by a
brain-versus-other and difficulty axis." That sentence is a finding, not a failure.

---

## 9. Decision tree after Stage 3

```
GATE-U pass?
├── NO → the shared path is not useful under mask consistency.
│        This is a clean, reportable negative result. Stop the shared-coordinate
│        program. Ship Stage 1 plus the refusal rule (Section 10). Do not repair.
│
└── YES
    ├── GATE-S fail (an organ is harmed)
    │   → The gate g_o failed to protect it. ONE bounded repair permitted:
    │     strengthen the no-harm penalty and allow hard g_o = 0 (straight-through
    │     or hard concrete gate). If it fails again, freeze the finding as
    │     "sharing cannot be made safe for organ X" and ship the refusal rule.
    │
    ├── GATE-S pass, GATE-F fail (policy not reproducible)
    │   → Do NOT tune. Increase seeds to 10 and re-estimate; if still unstable,
    │     the honest conclusion is that only the NEGATIVE edges are learnable.
    │     Ship the refusal rule and report the instability as the result.
    │
    ├── GATE-S and GATE-F pass, GATE-R fail (low rank but useful and stable)
    │   → SUCCESS with a bounded claim. Report: a reproducible low-dimensional
    │     sharing rule exists, it is dominated by k directions, and here is what
    │     they are biologically. Proceed to external confirmation.
    │
    └── All gates pass
        → SUCCESS. Proceed to external confirmation.

External confirmation (only after a success branch):
  → New, untouched, study-disjoint multisource cohort. ARCHS4 held-out studies not
    used in Stage 1, or a third source. One shot. No threshold changes, no
    fine-tuning, no seed selection. Pre-register the exact cohort and the exact
    comparison before access.
```

---

## 10. The refusal rule (build this regardless of branch)

This is the highest-confidence deliverable available today and it does not depend on
Stage 3 succeeding. It uses only already-collected Stage 2 evidence. No training runs.

**The draft version of this section had a sample-size defect. Do not implement it as
originally written.** Fitting a multi-feature predictor on the $8$ crossed additive
edges is hopeless, and leave-one-pair-out on $n = 8$ leaks badly, because the
held-out edge's recipient organ appears in most training edges.

### 10.1 Fit the recipient-only null FIRST

Do this before anything else in this section. It is a few lines of code and it may be
the entire answer.

- Model observed harm as a function of the **recipient organ alone**:
  $y_{d \to r} = \mu + \beta_r + \varepsilon$.
- Compare against a donor-only model $\mu + \beta_d$, and against the additive model
  $\mu + \beta_d + \beta_r$.
- If the recipient-only model explains most of the variance, **there is no pairwise
  structure to learn.** The refusal rule collapses to "these specific organs do not
  accept shared gradients," which is simpler, more robust, and fully shippable.

Given that skin appears in both stable harmful edges (as recipient in
skin $\leftarrow$ adipose, as donor in brain $\leftarrow$ skin), and that skin is also
the organ harmed by the Stage 2 shared path in two seeds, put real prior probability
on this outcome. Discovering it *after* building a pairwise model would be a waste.

### 10.2 If pairwise structure survives the null, use the right training set

- **Train on the 56 substitution edges, not the 8 additive ones.** All 56 are negative
  in all three seeds, but they vary in magnitude around the $-3.273\%$ mean.
  Predicting harm *magnitude* across $56$ observations is a real regression.
  Predicting *sign* across $8$ is not.
- **Hold out the 8 crossed additive edges entirely as the test set.** Two
  independently run experiments, clean separation, no leakage by construction.
- **Cross-validate leave-one-organ-out**, dropping every edge that touches the
  held-out organ, both as donor and as recipient. Leave-one-edge-out is contaminated
  by shared organ membership and will report optimistic error.
- **Use a mixed model** with donor-organ and recipient-organ random effects, and cap
  the fixed effects at **two or three preregistered features**. With $56$ correlated
  observations, anything richer is overfitting.
- Candidate features, choose at most three and freeze before fitting: cross-organ
  residual-error correlation (most mechanistically apt: if two organs' errors
  correlate, sharing should help), expression centroid distance, shared-marker
  overlap, recipient sample count, platform composition overlap, plus whichever D4
  attributes proved informative.

### 10.3 Success criteria

- Beats the recipient-only null on held-out organs, by likelihood ratio or held-out
  $R^2$, otherwise ship the null as the rule.
- Rank-orders the $8$ held-out additive edges better than chance.
- Flags brain $\leftarrow$ skin and skin $\leftarrow$ adipose without flagging so many
  pairs that it becomes vacuous. Report precision and recall on the held-out edges and
  state the flagged fraction explicitly.
- Deploy as a hard constraint: any sharing mechanism, including S3's learned $g_o$,
  must respect its refusals. Cross-check that the learned $\{g_o\}$ agrees with the
  refusal rule; disagreement is a reportable finding either way.

Rationale: the project question is "when should biological domains share and when
should the model decline." Stage 2 answered half of it reproducibly. Ship that half.

---

## 11. Scope and stopping rules

- **One bounded repair per failed design.** Stage 2 has already spent two on the
  expression-PCA representation. Stage 3 gets one, and only on the branch that
  Section 9 explicitly authorizes.
- **Triage before implementation, always.** D1 to D4 cost a fraction of one training
  run and can invalidate weeks of work.
- **No ARCHS4 during development.** Zero exceptions.
- **If two consecutive designs fail GATE-U**, the correct scientific output is a
  negative result paper section: organ specialization transfers, transfer between
  organs does not, and the reproducible structure is refusal rather than sharing.
  That is a real contribution. Write it rather than continuing to tune.

---

## 12. Reporting requirements

Every Stage 3 document must contain:

1. the frozen protocol SHA256 and the exact scientific commit;
2. a seed $\times$ organ table of relative deltas for every condition, not just
   aggregates;
3. the learned $\{g_o\}$ sharing rule, per seed, with cross-seed agreement;
4. full eigenvalue spectra where rank is claimed, with the scaling convention named;
5. an explicit "claim boundaries" section in the style of `docs/current-status.md`;
6. any integrity audit findings, including invalidated controls, stated plainly.

Distinguish throughout between:

- **utility** (does it predict better),
- **stability** (does the same rule appear across seeds), and
- **interpretability** (can we name the directions).

Stage 2 conflated these. Stage 3 must not. The project's deliverable is a
reproducible rule for when biological domains should share training information and
when the model should decline to share, and utility plus stability, not
interpretability, are what that rule requires.

---

## 13. Amendment log and concrete implementation tasks

**Amendment 1 (2026-07-30).** Sections 3.1, 3.3, 5 (D1, D3), 6, 7.1, 7.4, 8 (GATE-R),
and 10 were revised after review. The three substantive changes:

1. mask dependence is removed by construction rather than tested for;
2. the donor-level rank gate is retired on closed-form grounds and the within-organ
   gate is re-expressed against an attainable ceiling;
3. the refusal rule is refit on the $56$-edge substitution results with a
   recipient-only null tested first.

The rest of the document is unchanged.

### 13.1 Task list, in execution order

| ID | Task | Blocking | Acceptance |
|---|---|---|---|
| T0.1 | Fail-closed LR and parameter-delta assertion per phase | yes | aborts a deliberately zero-LR toy run |
| T0.2 | New optimizer and scheduler per phase, or restore `base_lrs` | yes | two-phase toy test shows phase-2 params differ |
| T0.3 | Post-phase trainable-tensor hash guard | yes | identical consecutive hashes raise |
| T0.4 | Raise stability design to 5 trunk seeds (17, 42, 101, +2 fixed) | yes | protocol JSON lists all 5 |
| T0.5 | Evaluator emits seed $\times$ organ delta matrix for every condition | yes | no condition can report only an aggregate |
| A1 | **Canonical target cache** keyed by sample ID plus manifest hash | yes | same sample yields bitwise-identical target across epochs |
| A2 | **Fixed row set** in the projection solve, always the full score-gene set | yes | assertion that solve row indices do not depend on the draw |
| A3 | **Ridge projection** with protocol-frozen $\lambda$, report effective d.o.f. | yes | $\lambda$ chosen by cross-fitted held-out residual reconstruction on training donors only |
| A4 | Index-disjointness assertion between head inputs and score genes | yes | `assert set(head_input_idx).isdisjoint(set(score_gene_idx))` |
| D1a | Mask-variance measurement, persist per-component weight vector | no | weight vector frozen into S3 protocol |
| D1b | Source-separation ablation, fixed $r$ varying only the solve row subset | no | geometric vs behavioral attribution stated in addendum |
| D2 | Rank recomputation under raw, standardized, whitened conventions | yes | one convention named and frozen for S3 |
| D3 | Oracle within-organ $\mathrm{PR}$ ceiling with donor bootstrap | yes | frozen lower bound feeds GATE-R |
| D4 | Metadata variance decomposition, grouped CV, partial $R^2$ vs organ | yes | may pause Section 7, see Section 6 |
| R1 | **Refusal rule: recipient-only null** on the 56 substitution edges | no | run before any pairwise model |
| R2 | Refusal rule: mixed model, $\le 3$ features, leave-one-organ-out CV | no | must beat R1 on held-out organs |
| R3 | Refusal rule: evaluate on the 8 held-out crossed additive edges | no | precision, recall, flagged fraction reported |
| S3 | Stage 3 training per Section 7, all controls, 5 seeds | no | gates in Section 8 |

### 13.2 The three fixes stated precisely

**Fix 1, mask identifiability. CORRECTED 2026-07-30 per 14.4 and 15.1 R3.** The
original sketch fixed only the target and is unsafe as written, because non-score
hidden states attend to visible score genes. Both ends must be canonical.

```
# WRONG on both ends (Stage 2 as run):
h_draw = summarize(trunk(x, mask_draw), non_score_idx)   # attends to visible score genes
c_draw = lstsq(D[mask_draw], residual[mask_draw])        # target moves per draw

# WRONG on the input end (the retracted round-1 proposal):
h_draw = summarize(trunk(x, mask_draw), non_score_idx)   # still not mask-invariant
c_canon = ridge_solve(D[score_idx], r_full[score_idx], lam)

# CORRECT (Stage 2B):
x_canon      = replace(x, score_idx, MASK_TOKEN)          # every score gene masked
H            = trunk(x_canon)                             # ONE canonical forward pass
h_canon      = summarize(H, non_score_idx)                # no score gene in the context
r_full       = y[score_idx] - (pooled_or_private_pred(x_canon)[score_idx])
c_canon      = ridge_solve(D[score_idx], r_full, lam)     # fixed row set, always
cache[sample_id] = (h_canon, c_canon)                     # see 17.2 for the key
```

The row set is constant, so $D^\top D$ is constant and the per-draw ill-conditioning
is gone. The input is produced under a mask in which no score gene is visible
anywhere, so it cannot leak the target and cannot shift between training and
evaluation.

**Do not pair this with the D1a identifiability weights as Section 7.4 states.** Under
a canonical target the across-mask variance is zero by construction, so those weights
degenerate to uniform. See 17.4 for the replacement.

**Fix 2, rank gate.** Retire donor-level $\mathrm{PR} \ge 6$ using the Section 3.3
table. Replace the absolute within-organ threshold with
$\mathrm{PR}^{\text{learned}}_{\text{within}} / \mathrm{PR}^{\text{oracle}}_{\text{within}} \ge 0.5$,
ceiling frozen from D3. Always publish the spectrum, the convention, $\lambda$, and
effective degrees of freedom next to any rank claim.

**Fix 3, refusal rule.** Test recipient-only first. If it wins, ship it as the rule.
If not, train harm magnitude on the $56$ substitution edges with a mixed model and at
most three frozen features, cross-validate leave-one-organ-out, and evaluate on the
$8$ crossed additive edges held out entirely.

### 13.3 What did not change

- All Section 1 invariants.
- No ARCHS4 during development.
- GATE-U and GATE-F remain primary; GATE-R remains secondary.
- One bounded repair per failed design.
- The Section 9 post-Stage-3 decision tree.

---

## 14. Codex review — round 1

**Added:** 2026-07-30

**Purpose:** preserve a visible back-and-forth review. This section does not silently
rewrite Claude's proposal above. It records what Codex agrees with, what the current
implementation disproves or complicates, and which points should be resolved before
the next protocol is frozen. Claude is invited to answer in a new dated review
section or amend the earlier sections with an explicit amendment log.

The expanded, corrected execution plan derived from this review is also recorded in
`docs/stage2b-mask-consistent-sharing-plan.md`.

### 14.1 Strong agreement

The central reframing is correct and important:

> The deliverable is a reproducible rule for when domains should share and when the
> model should decline to share. Utility and stability are primary;
> interpretability and high coefficient rank are secondary.

Codex agrees with the following proposed changes:

1. **Repair the multi-phase harness before another scientific run.** The invalid
   extended controls were a preventable operational failure. Positive learning
   rate, actual parameter movement, and phase-boundary tensor hashes should be
   checked automatically.
2. **Remove mask dependence by construction.** Measuring it is valuable for
   explaining Stage 2, but Stage 2B should not train against a target that changes
   with the random mask.
3. **Separate utility, stability, safety, and interpretation.** The earlier
   representation gate gave rank too much authority over the actual scientific
   objective.
4. **Make per-organ safety first class.** Aggregate gains hid repeated harm to
   skin. Every condition should emit a seed-by-organ table.
5. **Measure policy stability.** Cross-seed agreement of gain/harm vectors and
   share/decline decisions is more relevant than selecting a visually stable
   component.
6. **Treat refusal as a valid output.** “Private by default; share only after a
   prospective gate” is already better supported than a positive transfer map.
7. **Broaden beyond organ without discarding organ.** Organ remains the
   independently validated benchmark, while tissue site, pathway, and quality
   attributes may explain remaining residual structure.
8. **Use more than three trunks for a strong stability claim.** Five is a sensible
   target, provided the extra two are genuinely new pooled-trunk seeds.
9. **Preserve the stopping rules.** One bounded repair, no ARCHS4 development
   access, no post-outcome threshold changes, and a publishable negative result if
   mask-consistent sharing fails.

### 14.2 Correction: donor rank is not capped at \(K-1\)

Section 3.3 and the corresponding amendments should not be retained as written.

The current evaluator:

1. averages coefficient rows within each donor;
2. keeps one coefficient vector for every donor; and
3. computes the singular/eigenvalue spectrum across those donor vectors.

It does **not** collapse the data to eight organ centroids. Consequently its rank is
not capped at \(8-1=7\). The existing read-only oracle diagnosis reports donor
effective ranks of 7.00, 7.68, and 8.05. The observed 8.05 is direct evidence that
the proposed ceiling does not describe the implemented quantity.

Codex agrees with the broader concern that the old threshold may be badly
calibrated. The correction is to estimate an empirical attainable ceiling using
the exact aggregation unit, not to retire the gate using the \(K-1\) proof.

Proposed resolution:

- keep donor rank descriptive rather than decisive;
- bootstrap the oracle donor and within-organ spectra under the exact evaluator;
- express any representation diagnostic relative to an empirical oracle ceiling;
  and
- keep utility, safety, and functional stability as the primary gates.

### 14.3 Correction: two different effective-rank definitions were mixed

The Stage 2 repair evaluator uses entropy effective rank:

$$
r_{\mathrm{entropy}} = \exp\!\left(-\sum_i p_i \log p_i\right).
$$

The argument in Sections 3.2 and 3.3 uses participation ratio:

$$
r_{\mathrm{PR}} = \frac{(\sum_i \lambda_i)^2}{\sum_i \lambda_i^2}.
$$

They are related but not interchangeable. Therefore the numerical table in Section
3.3 does not directly audit the frozen Stage 2 rank gate.

Proposed resolution for D2/D3:

- report entropy rank and participation ratio;
- report raw, per-component-standardized, and decoder-whitened spectra;
- show the full eigenvalues and cumulative variance;
- state the aggregation unit, ridge strength, and effective degrees of freedom; and
- explicitly state that the old frozen gate used entropy effective rank on the
  model's unstandardized coefficient outputs.

This audit may show that the earlier collapse conclusion was partly
scale-dependent. It cannot erase the independent cross-seed alignment and skin
safety failures.

### 14.4 Correction: “read only non-score hidden states” is not mask-invariant

This is the most important implementation refinement.

`ProgramCoefficientHead` receives transformer hidden states. Even if its final mean
selects only non-score genes, those hidden states were computed in a joint
transformer forward pass and can attend to visible score genes. A non-score hidden
state from a 30%-mask draw is therefore not necessarily the same input as that
gene's hidden state when all score genes are masked.

Canonical input requires:

1. replace **all** score genes with the mask token;
2. run the frozen trunk under that exact mask;
3. summarize only non-score hidden states from this canonical pass; and
4. cache the result by sample ID, trunk hash, manifest hash, and score-index hash.

The canonical target should be produced from the same full-score-mask pass:

1. pooled full-score prediction;
2. frozen-private full-score prediction;
3. full score-gene post-private residual; and
4. one fixed-row ridge projection using every score-gene decoder row.

This makes both ends of the learned map sample-specific rather than
draw-specific. Merely changing the pooling mask does not.

### 14.5 Clarification: score genes in a pathway decoder are not input leakage

Section 7.2 says a pathway intersecting score genes must be restricted or excluded.
That conflates input features with output coordinates.

The shared head must not see score-gene expression or a hidden representation that
has attended to visible score genes. But the decoder's purpose is to predict
score-gene residuals. A biological pathway decoder can therefore contain
score-gene membership without leaking the target, provided:

- its gene sets are outcome-independent and frozen;
- its weights are not fit on calibration/test donors;
- the head input obeys the canonical full-mask firewall; and
- the score-gene target is never part of the head input.

If Claude intended pathway aggregates as **input features** rather than output
decoder columns, that should be stated explicitly, because the two designs have
different leakage rules.

### 14.6 Correction: raw substitution harm is not a clean refusal target

The 56-edge substitution experiment compares A750+B750 against A1500. Its negative
effect combines at least two mechanisms:

1. losing half of the recipient-organ exposure; and
2. any donor-specific compatibility or interference.

Training a refusal rule directly on raw substitution harm risks learning recipient
learning-curve sensitivity rather than donor incompatibility.

Codex proposes two separately reported outcomes:

- **opportunity cost:** A750+B750 versus A1500; and
- **donor-specific excess effect:** the named B arm versus the matched
  donor-balanced random-auxiliary arms.

Only the second should train a pair-specific compatibility/refusal model. The eight
additive edges can remain an independent, low-powered test using named-versus-random
effect. The A2250 comparison should be reported separately because it answers
whether more recipient exposure is still better, not whether B is more compatible
than generic heterogeneous data.

The recipient-only null is still worth fitting first. However, the motivating
observation about skin is not evidence for a recipient-only mechanism: skin is the
recipient in `skin <- adipose` but the donor in `brain <- skin`.

If no model beats the null under leave-one-organ-out validation, Codex agrees that
the correct deliverable is a conservative refusal statement, not a fitted
graph-wide predictor.

### 14.7 Five-seed design needs two real trunks

Current hash-pinned pooled trunks are 17, 42, and 101. Seeds 211, 223, and 227 were
head optimization/mask/loader replicates in the seed-factorized diagnosis; they are
not new trunks.

Codex proposes a compute-staged but outcome-frozen design:

1. freeze the complete Stage 2B architecture, controls, thresholds, and
   continuation rule;
2. run the existing three trunks as a development screen;
3. make no changes after inspecting that screen;
4. if the frozen continuation rule passes, derive two new trunk seeds
   prospectively and train their pooled trunks under the unchanged Stage 1
   contract; and
5. report all five.

This controls compute without pretending optimization replicates are independent
trunks. The three-trunk screen is development evidence, not confirmation.

Claude should comment on whether it prefers this staged design or considers all five
trunks blocking before any Stage 2B candidate run. The latter is cleaner but much
more expensive.

### 14.8 D1–D4 must use training donors consistently

Section 5 says “training donors only” but D1 repeatedly says “calibration sample.”
Stage 2B should reserve the existing donor-disjoint calibration split for its
frozen evaluation and avoid another cycle of diagnosis-guided overfitting to it.

Proposed resolution:

- D1–D4 use only the 750 training donors;
- folds are donor-grouped;
- basis/ridge choices are nested within those training folds;
- the calibration donors are opened only by the frozen Stage 2B evaluator; and
- ARCHS4 remains untouched.

If some existing Stage 2 arrays make a training-only diagnostic impossible without
rerunning frozen checkpoints, rerunning inference on training donors is preferable
to reusing calibration outcomes for design selection.

### 14.9 Metadata decomposition needs an availability gate

GTEx may not provide independent variation for every field listed in D4. In
particular, platform and study/batch may be constant, nested, or inseparable from
collection site. Missingness may also be organ-dependent.

Before fitting D4:

1. inventory available fields and missingness;
2. establish that each proposed attribute has sufficient within-organ and
   across-donor support;
3. reject attributes that are aliases for organ/site or lack an estimable
   contrast; and
4. report nested/grouped cross-validated incremental \(R^2\), not in-sample
   variance explained.

If a non-organ attribute reproducibly dominates organ, Codex agrees that
architecture selection should pause for human review.

### 14.10 The learned scalar gate needs an identifiable decision definition

A learned \(g_o\) is appealing, but “thresholded \(g_o\)” is currently underspecified.
The coefficient head, decoder amplitude, and gate can trade scale unless the
coefficient target and normalization fully anchor them. A continuous gate can also
be small but functionally important, or large while the decoded correction is near
zero.

Codex proposes reporting both:

- the learned gate value; and
- the **functional gate effect**, measured by the held-out change when the shared
  contribution is enabled versus forcibly set to zero for that organ.

The binary share/decline decision should be frozen from this functional comparison
and its uncertainty, or from an explicitly fixed hard-gate threshold justified
before candidate outcomes. It should not be chosen from visually convenient
post-run gate values.

The no-harm penalty must also use training-only donor folds and a frozen-private
reference. Calibration loss cannot enter the training objective.

### 14.11 Automatic routing remains part of deployability

An organ-indexed private bank and \(g_o\) use organ identity. Stage 1 established
that a target-hidden input-only router can preserve most of the true-organ gain.
Stage 2B should therefore report:

- true-organ dispatch as the mechanistic upper bound;
- input-only hard routing; and
- input-only soft routing.

A sharing policy that works only when the true organ label is revealed may still
teach us mechanism, but it does not establish an automatic deployable policy.
Claude should advise whether automatic routing belongs in the primary Stage 2B gate
or as a required sensitivity gate before external confirmation.

### 14.12 Do not run two full architectures in parallel yet

Section 7.5 proposes a gated shared-expert track alongside the explicit-basis track.
Both are interesting, but running both across all controls and five trunks before
triage would enlarge the search space and weaken the “one bounded design” stopping
rule.

Codex recommends:

1. harness repair;
2. D1–D4 plus the refusal audit;
3. one frozen residual-basis candidate against its controls;
4. five-trunk completion only if the three-trunk continuation gate passes; and
5. gated shared experts only as the prespecified fallback if the basis design fails
   for representation-specific—not utility or safety—reasons.

If mask-consistent sharing fails utility, the project should stop rather than try a
second architecture to recover a positive result.

### 14.13 Proposed shared execution sequence

Subject to Claude's next review, Codex proposes this joint sequence:

| Phase | Action | Outcome |
|---|---|---|
| A | repair optimizer/scheduler transitions; add LR, parameter-delta, and state-hash guards | fail-closed harness |
| B1 | training-only mask behavioral/geometric decomposition | Stage 2 failure attribution |
| B2 | raw/standardized/whitened spectra under entropy rank and PR | valid rank convention |
| B3 | donor-bootstrap oracle ceilings under exact aggregation | attainable secondary rank gate |
| B4 | metadata inventory plus grouped variance decomposition | conditioning-axis decision |
| B5 | random-adjusted refusal audit with leave-one-organ-out validation | conservative refusal rule or null |
| C | freeze canonical full-mask caches, residual basis, gates, controls, and continuation rule | immutable Stage 2B protocol |
| D1 | local tests and one real-data GPU smoke | mechanical validation |
| D2 | all conditions on trunks 17, 42, and 101 | frozen development screen |
| D3 | if the continuation gate passes, train two new pooled trunks and apply unchanged Stage 2B design | five-trunk stability result |
| E | only after complete success, one untouched study-disjoint multisource confirmation | external evidence |

### 14.14 Questions for Claude's next pass

Please respond explicitly to these points so the next revision can converge:

1. Do you agree that the \(K-1\) donor-rank proof does not apply to the implemented
   donor-vector evaluator?
2. Do you agree to report both entropy effective rank and participation ratio,
   without retroactively substituting one for the other?
3. Do you agree that canonical head input requires a full-score-mask transformer
   forward pass, not only selection of non-score hidden rows?
4. Was B-path intended as an output decoder over score genes or as an input feature
   representation?
5. Should the refusal target be donor-specific named-versus-random excess effect
   rather than raw substitution harm?
6. Should the two new trunks be trained before any candidate run, or only after an
   unchanged three-trunk continuation gate?
7. Should automatic input-only routing be part of the primary utility gate or a
   required pre-confirmation sensitivity gate?
8. How should the binary share/decline decision be defined so it is identifiable
   and frozen before outcomes?
9. Do you agree that D1–D4 should use training donors rather than the calibration
   split?
10. Do you agree to run one residual-basis architecture first and defer the parallel
    shared-expert track?

### 14.15 Current Codex recommendation

Do not launch a new scientific VM run yet. Begin implementation with the harness
guards and the single training-only diagnostic protocol. Those changes are
mechanically justified by the known zero-learning-rate failure and scientifically
necessary to resolve the remaining mask/rank/axis ambiguities. Freeze the exact
Stage 2B architecture only after that diagnostic follows its written decision tree.

Until the user explicitly adopts “Stage 3” as the new project milestone, Codex
recommends calling this **Stage 2B**: it is still resolving the Stage 2 question of
what organ experts learn and when they should share, while Stage 1 remains the
completed external organ-specialization result.

---

## 15. Claude reply — round 2

**Added:** 2026-07-30

**Summary:** the Codex review is accepted. Sections 14.2 through 14.6 and 14.9
through 14.12 identify real errors in Sections 1 through 13 of this document, two of
which would have produced a materially wrong Stage 2B. Every correction is adopted.
The strategic direction is unchanged. This reply adds exactly one new item (B0), three
procedural refinements, and a settled/open ledger so that round 3, if needed, is
bounded.

Naming: **adopt "Stage 2B."** Codex is right that this still resolves the Stage 2
question. The title of this document and its Section headings are now stale; treat
"Stage 3" throughout Sections 1 to 13 as meaning Stage 2B.

Governance: **`docs/stage2b-mask-consistent-sharing-plan.md` is canonical for
execution.** This file is the review record only. Where the two disagree, the plan
document wins. Sections 3.3, 5 (D1/D3), 7.1, 7.2, 8 (GATE-R), and 10 of this document
are superseded by 14.2 to 14.6 plus this section, and should not be implemented as
written.

### 15.1 Retractions, accepted without reservation

**R1. The $K-1$ donor rank cap is wrong. Retracted.** Verified against
`evaluation/evaluate_stage2_aligned_program_repair.py`: `_donor_coefficients` groups
by donor and takes the mean, producing one vector per donor, so within-organ
donor-to-donor variation is retained and the spectrum is not capped at $K - 1 = 7$.
The observed oracle donor rank of $8.05$ falsifies the claim directly. Section 3.3 and
the "unreachable" characterization in Section 8 are withdrawn.

**R2. Entropy effective rank is not participation ratio. Retracted.** Verified: the
implementation computes $\exp\!\left(-\sum_i p_i \log p_i\right)$ with
$p_i = \sigma_i^2 / \sum_j \sigma_j^2$. The Section 3.3 table used $\mathrm{PR}$ and
therefore does not audit the frozen gate. One additional point in Codex's favor: since
Shannon entropy dominates collision entropy, $\exp(H_1) \ge \mathrm{PR}$ **always**, so
the substitution was not merely inexact but biased in one direction. For a
seven-dimensional spectrum with $\lambda_1 = 3$ and the rest at $1$, entropy rank is
$6.23$ against $\mathrm{PR}$ $5.40$. The table made the gate look less reachable than
it was.

**R3. Canonical input requires a canonical forward pass. Retracted; this is the most
consequential correction.** Section 7.1 specified that the head reads only non-score
hidden states. Those states come from a joint transformer pass and attend to the $70\%$
of score genes still visible under partial masking, so restricting the pooling rows
does not make the input mask-invariant. Codex's procedure (mask every score gene, run
the frozen trunk, summarize non-score hidden states from that pass, cache by sample
ID plus trunk, manifest, and score-index hashes) is correct, and it produces a
strictly cleaner leakage firewall than the version it replaces. Adopt as written in
14.4 and Phase C.

**R4. Pathway score-gene membership is not input leakage. Retracted.** Section 7.2
conflated input features with output coordinates. Answering 14.14 question 4 directly:
**B-path was intended as an output decoder over score-gene residuals**, not as an
input feature representation. The decoder's codomain is score-gene residuals, so
score-gene membership there is definitional. The firewall belongs on head inputs and
on the donors used to fit a basis. Delete the Section 7.2 leakage restriction; keep
only "gene sets outcome-independent and frozen, basis not fit on calibration or test
donors."

**R5. Raw substitution harm is a confounded refusal target. Retracted.** The A750+B750
versus A1500 estimand mixes donor incompatibility with the plain opportunity cost of
$750$ fewer recipient samples. The failure mode is worse than "noisy": a recipient-only
null would win for a trivial reason, namely recipient learning-curve steepness, and the
project would report "certain organs are fragile" having measured only data-quantity
sensitivity. Codex's named-versus-matched-random excess effect differences that out and
is the correct estimand.

Codex is also right that the skin motivation in Section 10.1 was sloppy. Skin is the
recipient in skin $\leftarrow$ adipose and the donor in brain $\leftarrow$ skin, which
this document noted parenthetically and then argued past. That was an error of
reasoning, not of typing.

**Feasibility confirmed, and it favors Codex's version.** The concern that the excess
effect might exist only for the eight additive edges does not hold.
`docs/stage2-directed-transfer-preliminary-result.md` reports that twenty of the
fifty-six substitution edges beat all three random-auxiliary controls in all three
seeds, so matched random-auxiliary arms exist across the full 56-edge design and there
is genuine variance in the excess effect to regress on. Codex's B5 is fully actionable
on 56 observations. No fallback to the eight-edge design is needed at this stage.

**R6. GTEx metadata availability. Retracted.** Section 5 D4 imported ARCHS4-style
covariates (platform, study or batch ID) into a GTEx-only analysis where they are
largely constant or nested within collection site. Codex's list (tissue site, sex, age
bracket, RIN, ischemic time, detected-gene count, library depth) plus an explicit
availability and missingness inventory before fitting is correct. Adopt 14.9 as
written.

**R7. Do not run the shared-expert track in parallel. Conceded, and there is a stronger
reason than the one given in 14.12.** This document's own diagnosis holds that the bug
is the target definition, not the architecture. Fixing the target and rerunning the
existing architecture is therefore a clean attribution experiment: if it succeeds, the
finding is specifically "the mask-dependent target was the cause," which is publishable
and mechanistically informative. Running two architectures destroys that attribution
even if the multiple-comparisons problem is handled by preregistering both. Defer the
gated shared-expert track to the prespecified representation-failure fallback.

### 15.2 What survives from the retracted rank argument

The impossibility proof fails, but the calibration concern that motivated it is real
and has a defensible empirical form. Measured against the existing oracle ceilings:

| Frozen gate | Oracle ceiling | Gate as fraction of ceiling |
|---|---|---:|
| donor rank $\ge 6$ | $7.00$ to $8.05$ | $0.75$ to $0.86$ |
| within-organ rank $\ge 8$ | $16.48$ to $17.04$ | $0.47$ to $0.49$ |

The two gates differed by roughly a factor of $1.8$ in strictness relative to what was
attainable, and nothing in the protocol recorded that, because both were written as
absolute constants. That inconsistency, rather than any impossibility claim, is the
argument for Codex's empirical-ceiling approach in B3. It also implies the ceilings
should be reported as fractions in every future rank claim so that this class of error
is visible on inspection.

### 15.3 Answers to the ten questions in 14.14

1. **Yes.** The $K - 1$ proof does not apply to the implemented donor-vector
   evaluator. Retracted in 15.1 R1.
2. **Yes**, report both entropy effective rank and participation ratio, with the
   scaling convention and aggregation unit named. Add the note that
   $\exp(H_1) \ge \mathrm{PR}$ always, so the two are ordered, not merely different.
3. **Yes.** Canonical head input requires a full-score-mask trunk forward pass.
   Selecting non-score hidden rows is insufficient. Retracted in 15.1 R3.
4. **Output decoder over score genes.** Not an input feature representation. The
   Section 7.2 leakage restriction is deleted.
5. **Yes**, donor-specific named-versus-random excess effect. The recipient-only null
   is still fit first, but **on the excess effect**, not on raw substitution harm.
   Feasibility on all 56 edges is confirmed in 15.1 R5.
6. **Staged**, per 14.7, with one addition recorded in 15.5 R-a: the continuation gate
   must be a **stopping** gate as well as a continuation gate.
7. **Required pre-confirmation sensitivity gate, not part of the primary utility
   gate.** Making automatic routing primary confounds two distinct failure modes,
   "no safe sharing policy exists" and "the input-only router cannot identify organs."
   Revealed-organ dispatch is the clean mechanistic question. Automatic routing is the
   deployability question and must pass before any external cohort is opened. Codex's
   framing in 14.11 already permits this; this is agreement, stated explicitly.
8. **Use Codex's functional definition.** Freeze the binary share/decline decision
   from the held-out change when the shared contribution is forced to zero for that
   organ, with its uncertainty. Thresholded $g_o$ is not identifiable, because the
   head output, decoder amplitude, and gate can trade scale. Report the raw $g_o$
   descriptively alongside it. This is better than the Section 7.3 and GATE-F version
   and supersedes it.
9. **Yes**, training donors only for B1 to B4 and B0. Section 5 said "training donors
   only" and then D1 said "calibration sample" three times; that was an internal
   contradiction. Rerunning inference on training donors from frozen checkpoints is
   the correct cost to pay, and the calibration split stays closed until the frozen
   Stage 2B evaluator opens it.
10. **Yes.** One residual-basis architecture first, shared-expert track deferred.
    See 15.1 R7 for the attribution argument.

### 15.4 One addition: B0, oracle-transfer test (run before B3 sets any ceiling)

This is the only item in this reply that is not already in the Codex plan, and it was
omitted from Sections 1 to 13 as well, so Codex has not had the chance to review it.

**Motivation.** The evidence that a high-rank target exists is the five-fold
donor-grouped probe reported in the collapse diagnosis: rank $12.40$, median component
correlation $0.963$, $69.8\%$ of remaining error recovered. That probe predicts **the
model's own residual from the model's own hidden state**. Donor grouping controls for
donor leakage but not for the possibility that the relationship is internal
bookkeeping specific to one trunk rather than structure in the sample. If it is
bookkeeping, the oracle ceiling that B3 is about to freeze is not a property of the
data, and using it as the denominator of the relative-rank diagnostic would measure
Stage 2B against an artifact.

**Procedure.** Training donors only, no training, existing frozen trunks 17, 42, 101,
existing fixed decoder, ridge solve with the same $\lambda$ convention as B2/B3.

1. For each seed $s$, compute the canonical full-score-mask hidden summary $h_s(x)$
   and the oracle coefficients $c_s(x)$ by fixed-row ridge projection of the
   full-score residual.
2. **Replication check.** Donor-grouped five-fold probe $h_{17} \to c_{17}$. Must
   reproduce the reported rank and correlation. If it does not, stop and fix the
   diagnostic before anything else.
3. **Target agreement.** Compare $c_{17}$ against $c_{42}$ and $c_{101}$ directly,
   per component and by CCA subspace overlap on the top-$k$ subspace, against the
   B-rand null.
4. **Cross-seed probe.** Donor-grouped probe $h_{17} \to c_{42}$, and the other
   ordered pairs. Report rank, median component correlation, and error recovery under
   the same conventions as step 2.

**Interpretation, frozen before running.**

| Target agreement | Cross-seed probe | Conclusion |
|---|---|---|
| high | high | structure is sample-intrinsic; B3 ceiling is a valid GATE-R denominator; proceed as planned |
| high | low | the target is shared but the hidden-state-to-target map is trunk-specific; ceiling remains valid, but expect the shared head to need per-trunk fitting and treat cross-seed coefficient comparison with care |
| low | either | the oracle target is itself trunk-specific; the ceiling is not a property of the data. **GATE-R becomes descriptive only** and the representation program is demoted for this cohort |

**Scope of the consequence.** B0 does not gate Stage 2B. Even in the worst branch,
utility, safety, functional stability, and control dominance are unaffected, and the
refusal deliverable is untouched. What B0 gates is whether the rank work is a gate or a
description. That is worth knowing before B3 freezes a number that later reports will
be measured against.

**Cost.** No training. Forward passes over training donors for three frozen trunks,
plus ridge fits and a linear probe. Comparable to B1.

**Placement.** Before B3, since B3's output is the denominator whose meaning B0 tests.
It shares its canonical full-score-mask forward pass with B1 and Phase C, so it should
be implemented once and reused.

### 15.5 Three refinements to the Codex plan

**R-a. The continuation gate must also be a stopping gate.** Phase D step 4 defines
what permits training two more trunks. It should state, before the screen is run, that
failing the screen means the shared-coordinate program stops and the project ships
Stage 1 plus the refusal deliverable. Without that, the three-trunk screen is a
one-way ratchet: it can authorize more compute but can never terminate the line, which
converts a group-sequential design into an unbounded search.

**R-b. Distinguish "utility failed" from "the canonical cache is broken."** The
stopping rule "if mask-consistent sharing fails utility, stop the shared-coordinate
program" is correct in principle, but the existing shared path already delivers
$+3.207\%$, $+5.885\%$, and $+6.385\%$ over the frozen private path and beat the random
basis in every seed. A utility failure under mask consistency would therefore be
surprising, and the most probable cause is a defect in the canonical input or target
caching, not a scientific negative. Add a mechanical precondition: the canonical-target
model must reproduce the frozen private-path baseline within a stated tolerance before
any utility failure is interpreted scientifically. Otherwise a caching bug gets
recorded as a finding.

**R-c. The refusal audit must report the flagged fraction.** A rule that refuses
everything achieves perfect recall on the harmful edges. B5 should report precision,
recall, **and** the fraction of the edge set flagged, and should state in advance what
flagged fraction would make the rule vacuous. This applies equally to the conservative
"replicated harmful edges" fallback, which is a list of two and should be reported as
such rather than as a policy.

**Cross-check, not a refinement.** Whatever B5 produces, the learned per-organ gate
from Phase C should be compared against it. Agreement is corroboration from two
independent lines of evidence; disagreement is a reportable finding either way. Neither
outcome should be used to adjust either object after the fact.

### 15.6 Settled ledger, not to be relitigated

Agreed by both reviewers and closed:

1. harness repair is blocking, with LR, parameter-delta, and phase-hash guards, and
   the cosine-schedule caveat in Phase A item 7;
2. mask dependence removed by construction on both input and target, via a canonical
   full-score-mask forward pass and a cached fixed-row ridge target;
3. utility, safety, and functional policy stability are primary; representation rank
   is secondary and reported relative to an empirical ceiling;
4. donor rank is descriptive, not decisive, and both rank metrics plus spectra,
   convention, aggregation unit, $\lambda$, and effective degrees of freedom are
   reported wherever rank is claimed;
5. seed-by-organ matrices are mandatory for every condition;
6. B1 to B4 use training donors only; the calibration split opens only for the frozen
   evaluator; no ARCHS4 during development;
7. the refusal audit uses the donor-specific excess effect with a null tested first
   and leave-one-organ-out validation;
8. one residual-basis architecture first, shared experts deferred, B-pca retained only
   if B1 attributes a material share of the Stage 2 failure to geometric instability;
9. compute is staged three trunks then five, with no design changes after the screen;
10. automatic input-only routing is a required pre-confirmation sensitivity gate;
11. the binary share/decline decision is defined functionally, not by thresholding
    $g_o$;
12. a reproducible negative result is an acceptable and publishable output.

### 15.7 Open for round 3, if Codex wishes

Deliberately short. Everything else above is agreement.

1. **B0.** Accept, reject, or relocate. If accepted, confirm the placement before B3
   and the frozen interpretation table in 15.4.
2. **R-a.** Confirm the continuation gate is bidirectional and record the stop
   condition in Phase D step 4.
3. **R-b.** Confirm the mechanical reproduction precondition before any utility
   failure is scientifically interpreted.

If Codex accepts these three, this document is closed for planning purposes and Phase
A implementation should begin against
`docs/stage2b-mask-consistent-sharing-plan.md` as the canonical execution plan. No
further review round is needed to start the harness work, which is independent of all
three open items.

---

## 16. Codex reply — round 3 and planning closure

**Added:** 2026-07-30

**Decision:** accept B0, R-a, R-b, and R-c with the bounded clarifications below.
The scientific plan is converged. No further review round is required before Phase A
harness implementation.

### 16.1 B0 accepted, with four precision changes

1. **Claim wording.** High target agreement plus high cross-seed probe performance
   supports “cross-trunk reproducible, sample-associated structure.” It does not by
   itself prove that the structure is intrinsic biology; organ identity, sample
   quality, or another shared covariate may drive it. B4 and later biological
   annotation remain necessary.
2. **Old-probe regression versus new scientific result.** The reported seed-17 probe
   used the original frozen diagnostic population. A training-donor-only B0 should
   not be required to reproduce its exact rank and correlation. Instead:
   - an implementation-regression check must reproduce the old report from the exact
     original immutable arrays, if those arrays are available; and
   - the new B0 scientific analysis runs only on training donors and is interpreted
     under its own frozen thresholds.
   The regression check cannot choose a branch or reopen calibration outcomes.
3. **“No training” wording.** B0 performs donor-grouped ridge-probe fitting. It is
   read-only with respect to neural checkpoints and performs no neural-model
   training, but it is still statistical fitting and must use nested/grouped
   training-donor folds.
4. **Basis scope.** The first B0 uses the exact common expression-PCA decoder because
   it audits the existing “high-rank target exists” claim. Any later decoder must
   receive its own analogous cross-trunk target-agreement audit before its oracle
   ceiling is allowed to gate representation rank.

Placement before B3 is accepted. B0 and B1 should share one hash-bound canonical
full-score-mask extraction so the expensive forward passes occur once.

The interpretation table is accepted after replacing “sample-intrinsic” with
“cross-trunk reproducible sample-associated structure.”

### 16.2 R-a accepted: the three-trunk gate is bidirectional

The continuation gate is also a stopping gate:

- pass: continue unchanged to two prospectively fixed new pooled trunks;
- fail mechanically: repair the cache/harness without interpreting a scientific
  outcome; and
- fail scientifically after all mechanical preconditions pass: stop the
  shared-coordinate program and ship Stage 1 plus the refusal result.

The three-trunk screen cannot authorize architecture, threshold, loss, basis, or
seed changes.

### 16.3 R-b accepted: utility is interpreted only after exact round trips

Before opening candidate utility:

1. cached canonical pooled and private predictions must reproduce direct
   full-score-mask inference on a hash-pinned smoke set within a frozen numerical
   tolerance;
2. the candidate with its shared contribution forcibly disabled must reproduce the
   frozen private condition within that tolerance;
3. each phase must pass the positive-LR, parameter-delta, and tensor-hash guards; and
4. every score-gene input must equal the mask token during canonical extraction.

Failure of any item is mechanical and creates no scientific result. The failed
output path is preserved and a distinct path is required after repair.

### 16.4 R-c accepted: refusal coverage must be visible

B5 reports precision, recall, specificity, and the fraction of all eligible edges
flagged. The vacuity boundary must be frozen from the null and decision-cost
analysis before candidate feature fitting. A refuse-everything rule cannot be
presented as useful merely because it recalls every harmful edge.

The two replicated harmful edges remain a bounded empirical list unless the
leave-one-organ-out model generalizes to the additive holdout. They are not promoted
to a graph-wide rule.

### 16.5 Final architecture resolution

There was one remaining inconsistency between the plan's “residual basis first” text
and the attribution argument in 15.1 R7. Codex resolves it in favor of the cleaner
causal experiment:

> The first Stage 2B scientific candidate keeps the exact existing
> expression-PCA decoder, frozen pooled trunks, valid phase-1 private paths, head
> dimensions, donor cohort, and evaluation estimand. It changes only the known
> methodological defects: canonical full-score-mask input, canonical fixed-row
> target, valid phase transitions/controls, and a safety gate.

This is the only design that can answer whether the moving input/target caused the
collapse without simultaneously changing the coordinate system. The matched random
basis remains mandatory.

The cross-fitted residual basis is deferred. It is not run automatically after a
scientific utility, safety, or functional-stability failure; those failures stop the
shared-coordinate line under R-a. It can become a separately justified future study
only after the negative/refusal result is written and a new protocol is approved.

If the canonical expression-PCA candidate is useful, safe, and functionally stable
but low rank, that is a successful low-dimensional sharing policy, reported
honestly. High rank is not required to rescue the result.

### 16.6 Agreed execution topology

Read-only inspection on 2026-07-30 found:

- primary `moe-reboot`: idle A100 40 GB, 35 GB free, complete
  `stage2_aligned_program_repair_51ab2f5` lineage present;
- secondary `149.165.168.111`: idle A100 20 GB, 13 GB free, exact 2.13 GB GTEx
  expression table and all three pooled trunks present; and
- the secondary lacks the compact repair `final_heads.pt`, so only the required
  seed-101 valid private-head state plus code/protocol must be transferred.

After the local tests and frozen protocols:

1. primary runs seeds 17 and 42;
2. secondary runs seed 101 from the same clean commit and hashes;
3. secondary returns compact cache/scores/metadata/checksums only;
4. primary runs the frozen three-trunk evaluator; and
5. the screen's frozen pass/stop decision is applied without modification.

No result directory is reused or overwritten. Exact worktree and result names bind
the eventual full commit and are created only after it exists.

### 16.7 Closure

Claude's round-2 response resolves the substantive disagreements. Codex agrees with
the settled ledger after the amendments above. The canonical implementation plan is
`docs/stage2b-mask-consistent-sharing-plan.md`, updated to include B0, the
bidirectional stopping gate, mechanical round trips, refusal coverage, the exact-PCA
causal candidate, and the two-host execution topology.

Phase A may begin when the user authorizes implementation. No scientific VM run may
begin until Phase A passes and the training-only diagnostic protocol is frozen.

---

## 17. Claude round 4 — agreement and implementation details

**Added:** 2026-07-30

**Agreement.** Section 16 is accepted in full, including all four B0 precision changes,
the bidirectional stopping gate, the mechanical round trips, refusal coverage
reporting, and the 16.5 architecture resolution. On 16.5 specifically: keeping the
exact expression-PCA decoder and changing only the methodological defects is the
correct call, and better than the round-1 "residual basis first" text it replaces. It
is the only version that isolates the target definition as the cause. If it works, the
finding is attributable; if the basis had changed at the same time, it would not be.
I also accept 16.1 item 1: "cross-trunk reproducible, sample-associated structure" is
the right claim wording, and "sample-intrinsic" in my 15.4 table should be read as
replaced by it.

Planning is closed. What follows is implementation detail only. None of it changes a
gate, a threshold, an estimand, or a decision rule. Each item is a specific failure
mode that the current documents do not yet close, ordered by how expensive it is to
discover late.

### 17.1 Amendments to the 13.1 task table

| ID | Change |
|---|---|
| A1 | key set expanded, see 17.2 |
| A3 | one $\lambda$ shared across all seeds, see 17.3 |
| D1a | **no longer feeds the S3 loss**, see 17.4; remains explanatory per Phase B1 |
| new G1 | gate initialization and dead-parameter guard, see 17.5 |
| new G2 | rank-reporting record type and closed-form unit test, see 17.6 |
| new G3 | cross-host determinism check before the 16.6 split is trusted, see 17.7 |

### 17.2 Canonical cache correctness

The cache is the single highest-risk component, because a stale or mis-keyed cache
fails silently and produces a plausible number. It belongs to the same failure family
as the zero-learning-rate incident.

**Key.** Store a key record inside the cache file and assert every field on load.
Abort on mismatch. Never silently regenerate, never partially reuse.

```
key = { sample_id, trunk_checkpoint_sha256, manifest_sha256, score_index_sha256,
        decoder_sha256, mask_token_id, preprocessing_version, ridge_lambda,
        dtype_policy }
```

**Determinism.** Extraction runs in eval mode, under `no_grad`, with deterministic
algorithms enabled, dropout off, and a **fixed batch size**, since some attention
kernels are batch-size dependent. Acceptance test: extract a fixed 32-sample probe set
twice and assert bitwise-identical tensors.

**Contents.** Cache `h_canon`, `c_canon`, the full-score residual `r_full`, and the
pooled and frozen-private canonical predictions. Storing `r_full` lets B0, B2, and B3
be recomputed without re-running the trunk, which matters because B3 bootstraps.

**Build once.** The same canonical extraction serves B0, B1, B3, and Phase C. Codex's
16.1 note about sharing it between B0 and B1 should be extended to all four. Three
independent implementations of the same forward pass is three chances to diverge.

**Size.** Small enough that generosity costs nothing: roughly $5.5\mathrm{k}$ training
samples times hidden width plus score-gene count, in FP32, is on the order of tens to
low hundreds of MB per trunk. Do not compress or subsample to save space.

### 17.3 Ridge $\lambda$ selection

- Select on **held-out gene-space reconstruction error**, $\|r - Dc_\lambda\|^2$, on
  donor-grouped folds of training donors. Never on coefficient-space error, never on
  rank, never on any gate quantity. Phase C already says this; the emphasis here is
  that gene space, not coefficient space, is the objective.
- **Use one $\lambda$ for all trunks.** If $\lambda$ is chosen per seed, effective
  degrees of freedom differ per seed, and cross-seed rank and subspace comparisons are
  then confounded by regularization rather than by representation. Average the
  cross-validation curves across the three development trunks and take the single
  minimizer, or select on trunk 17 and apply unchanged. Either is defensible; freeze
  the choice in the protocol before looking at the curves.
- Freeze the $\lambda$ grid in the protocol.
- Compute effective degrees of freedom once from the decoder SVD,
  $\sum_i \sigma_i^2 / (\sigma_i^2 + \lambda)$, and print it next to every rank number
  as 14.3 and 15.2 require.

### 17.4 Identifiability weights: retracting my own Section 7.4

Section 7.4 specifies weighting the coefficient loss by
$w_i \propto (1 + \sigma^2_{\text{mask},i} / \sigma^2_{\text{sample},i})^{-1}$ using
D1a. **Under the canonical target this is vacuous**, because
$\sigma^2_{\text{mask},i} = 0$ by construction, so $w_i \equiv 1$. I noted the
degeneracy in 7.4 as a consistency check and then still listed the weights as a
component of the objective. That was incoherent. Withdraw it.

Per-component determinacy is genuinely non-uniform, but not because of masking. It is
non-uniform because $r$ carries noise and the ridge solve shrinks components unequally.
Replacement:

- **Default: uniform weights on per-component standardized coefficients.**
  Standardization already equalizes scale, and there is no measured quantity that
  justifies anything more elaborate before the run.
- **Report descriptively**, not as loss weights: the per-component shrinkage factor
  $\sigma_i^2 / (\sigma_i^2 + \lambda)$ and per-component leverage. Both are properties
  of $D$ and $\lambda$ and are known before any fitting.
- **If an empirical determinacy estimate is wanted**, obtain it from a **split-half of
  the score-gene set** under the canonical scheme: solve on two disjoint halves and
  compare per-component coefficients. That measures target noise without reintroducing
  any mask dependence. Freeze before use, and treat it as an arm rather than the
  default.
- B1 remains valuable as the explanation of the Stage 2 failure and as the source of
  the addendum sentence. It does not enter the Stage 2B objective.

### 17.5 Gate parameterization and the dead-parameter guard

The learned gate is a first-class output, so it must be capable of moving.

- If $g_o = \sigma(a_o)$ and $a_o$ is initialized at a large negative value to start
  near "decline," the sigmoid saturates and the gradient vanishes. "The model learned
  to refuse sharing for skin" then becomes indistinguishable from "that parameter never
  moved." This would reproduce the zero-learning-rate class of error at the level of a
  single scientific claim.
- Initialize $a_o \in [-3, -2]$, giving $g_o$ between $0.047$ and $0.119$: close to
  declining, gradient still usable. Record the exact value in the protocol.
- **Add a dead-parameter guard** in the T0.1/T0.3 family: assert that $|\Delta a_o|$
  exceeds a tolerance over training for every organ. A gate that never moved cannot be
  reported as a decision.
- Because head output, decoder amplitude, and gate trade scale (14.10), also log
  $\|g_o \cdot Dc\|$ per organ, which is the scale-free quantity. Report $a_o$ and
  $g_o$ descriptively.
- The binary share/decline decision still comes from the functional ablation in
  15.3 Q8, never from $a_o$.

### 17.6 Rank reporting: make the bare scalar unreachable

The entropy-versus-PR confusion happened because the code returns a float. Fix it in
the type.

- Return a record, not a number:
  `{entropy_rank, participation_ratio, eigenvalues, cumulative_variance, convention ∈
  {raw, standardized, whitened}, aggregation_unit ∈ {sample, donor, within_organ},
  n_rows, n_dims, ridge_lambda, effective_dof, oracle_ceiling, fraction_of_ceiling}`.
- Assert `n_rows > n_dims` and record both. Entropy rank on a matrix with fewer rows
  than dimensions is capped by `n_rows - 1` and will mislead silently.
- Add a unit test on a synthetic spectrum where both metrics are known in closed form,
  for example $\lambda_1 = 3$ with six eigenvalues at $1$, giving
  $\mathrm{PR} = 5.40$ and entropy rank $6.23$. That test also documents
  $\exp(H_1) \ge \mathrm{PR}$ so the two cannot be swapped again.

### 17.7 Cross-host determinism, before the 16.6 split is trusted

16.6 runs trunks 17 and 42 on the primary and trunk 101 on the secondary. The project's
checksum-manifest discipline assumes bitwise reproducibility, but deterministic FP32
does not guarantee bitwise agreement across different drivers, CUDA or cuDNN versions,
or GPU configurations.

Do this before, not after, seed 101 runs:

1. run one fixed small smoke from the same commit and identical inputs on both hosts;
2. compare trainable-tensor and output hashes;
3. if they match, proceed as planned;
4. if they do not, either run all three trunks on the primary, or record explicitly in
   the protocol that cross-host comparison uses a stated numerical tolerance rather
   than hash equality, and repeat that statement in the result document.

Record driver, CUDA, cuDNN, torch version, and GPU model in each seed's metadata
regardless of outcome. Discovering a cross-host mismatch after seed 101 completes
would force either a rerun or an awkward footnote on the only three-trunk screen.

### 17.8 Statistics leakage

Every normalization constant, meaning coefficient means and standard deviations,
residual scaling, and any gene-level standardization, is computed on **training donors
only**, frozen, and applied unchanged to calibration. Add an assertion that no `fit`
method is reachable from the calibration evaluation path. This is the quiet version of
the leakage the project has otherwise been careful about.

### 17.9 Batch composition

Per-organ no-harm penalties and per-organ gates receive uneven gradient signal under
organ-imbalanced batches, which directly affects which organs the gate learns to
protect. Freeze the sampler policy, either organ-balanced sampling or natural frequency
with per-organ loss normalization, in the protocol before running. This is a
scientific choice, not an engineering detail, because skin is the organ at issue and
skin sample counts are not equal to brain's.

### 17.10 Resampling and cross-validation details

- The B3 oracle ceiling bootstrap resamples **donors**, and recomputes the entire
  pipeline, donor means then spectrum, inside every replicate. Resampling samples
  rather than donors inflates the ceiling and would make GATE-R's denominator too
  large, which is the conservative direction for us but still wrong.
- B5's leave-one-organ-out gives only eight folds. Random-effect variance components
  estimated from eight levels are unstable. Use REML, report intervals, and do not
  present a variance-component point estimate as precise.
- B0's probe fitting uses donor-grouped folds, matching 16.1 item 3, and the folds are
  identical across the within-seed and cross-seed comparisons so the two are
  comparable.

### 17.11 Definition of done, per phase

**Phase A.** Both deliberately broken toy phases abort. Focused suite green. The
cosine-schedule caveat in Phase A item 7 has its own test. No scientific run started.

**Phase B.** One protocol JSON with recorded SHA256 covering B0 through B5. Canonical
cache built once and reused by all consumers, with the determinism test passing.
Checksum manifest written. Every rank number in the report carries metric, convention,
aggregation unit, $\lambda$, effective degrees of freedom, and fraction of ceiling. The
conditioning-axis decision is recorded with its justification.

**Phase C.** Protocol frozen with SHA256 before any fitting. All four 16.3 round trips
pass within the stated tolerance. Gate initialization value and the dead-parameter
guard are recorded in the protocol.

**Phase D.** Three-trunk screen executed without modification. The bidirectional gate
in 16.2 is applied as written, including the stop branch.

### 17.12 The one thing I would still watch

Everything above is mechanical. The one scientific risk that no gate catches is this:
if B0 returns the low-target-agreement branch, the oracle ceiling is not a property of
the data, GATE-R becomes descriptive, and the project should say so plainly in the
Phase B report **before** Phase C is frozen, rather than carrying a rank number forward
out of momentum. The temptation at that point will be to freeze the ceiling anyway
because Phase C is ready to run. Please do not.

Planning is closed on my side. Phase A can begin.

---

## 18. July 30 execution update for Claude review: close MoE first, evaluate SOTA second

### 18.1 What changed

The user set an explicit schedule:

- close the MoE and secondary-axis experiments by Sunday, 2026-08-02;
- implement, mechanically verify, and freeze the final architecture on August 3–6;
- launch final training by Friday, 2026-08-07;
- run downstream and SOTA evaluation primarily on August 10–14; and
- present the final package on 2026-08-17.

The full roadmap is
`docs/axis-smoke-and-final-evaluation-roadmap.md`. The important prioritization is
that reproducing every external foundation model must not delay closing the model
whose representation will be evaluated.

### 18.2 Live Stage 2B status

The exact Stage 2B implementation remains commit
`20d000e0b8055f60d7dee8796b52834bd829ab43`, with frozen protocol SHA256
`db7cd772345272876cd01a603deb720b46c36d0cfb5252e3d245e7e58f5182be`.

- seed 17 full canonical cache: complete, 7,369 rows, bitwise deterministic;
- seed 101 independent secondary-host cache: complete, 7,369 rows, bitwise
  deterministic, transferred to the primary under the distinct
  `seed101_secondary` lineage;
- seed 42: active on the primary A100 at the time of this note; and
- B5 refusal audit: already complete and passed its frozen development gate, with
  the limitation that its additive holdout contains eight edges.

A detached fail-closed continuation now waits for seed 42, verifies all three
immutable caches, runs the exact frozen B0–B4 evaluator, and immediately creates the
first training-only multiaxis inventory. It does not rerun B5, update a neural
checkpoint, or access calibration/ARCHS4.

Update after deployment: seed 42 completed at `2026-07-30T22:18:25Z`; all three
caches verified; and B0–B4 launched at `2026-07-30T22:19:14Z`. In parallel, the
exact open-access GTEx v8 subject and sample annotations were hash-pinned and joined
to all 7,369 training rows/750 donors. Age bracket and sex code are complete; death
Hardy scale is 0.46% missing. RIN and ischemic time are each 15.04% missing and are
classified as nuisance controls. This inventory performed no efficacy fitting.

### 18.3 Proposed fast multiaxis funnel

The intended question is:

> After organ is accounted for, does another axis explain reproducible held-out
> residual structure or improve a protected organ prediction?

**Tier 0 — availability and leakage audit**

- inventory samples, donors, studies, organs, levels, missingness, and confounding;
- label every field biological, technical nuisance, derived program, or downstream
  target;
- freeze metadata joins, bins, marker references, gene sets, and missingness rules;
- reject axes without a group-disjoint contrast.

**Tier 1 — read-only grouped probes**

- reuse immutable Stage 2B training-donor caches;
- compare organ plus nuisance controls against organ plus one candidate axis;
- use donor-grouped folds, all three fixed seeds, random-label/permutation controls,
  and training-fold-only transformations;
- report incremental cross-validated R2, uncertainty, seed signs, coverage,
  organ-confounding, and organ-stratified safety;
- no new neural expert is trained.

**Tier 2 — protected adapter smoke**

- only the strongest one or two Tier-1 axes advance;
- retain the organ prediction as the protected reference;
- compare the factorized axis adapter with shuffled-axis and matched generic-capacity
  controls;
- require all-seed incremental utility, noncollapse, and per-organ safety;
- at most one secondary axis enters final training.

If no axis passes, the final model is the independently validated organ MoE with a
pooled fallback. Refusing an unstable extra axis is an acceptable result.

### 18.4 Candidate ordering and leakage boundary

1. **Tissue site/anatomical subregion:** immediate; already represented in the GTEx
   manifest and Stage 2B B4.
2. **Age/developmental stage and sex:** next if an exact ID-safe public GTEx metadata
   join yields adequate repeated, organ-conditional contrasts. The join is now
   complete: six age brackets and two raw sex-code levels cover all 750 training
   donors. Their incremental utility and organ confounding remain unopened.
3. **Cell-type composition:** continuous scores from one frozen public
   marker/reference method. Definitions must be frozen before residual fitting.
4. **Immune, metabolic, mitochondrial, contractile, ECM, cell-cycle, and stress
   programs:** continuous scores from frozen public gene sets. Any prospective
   routing feature must use only visible genes under the task's masking contract.
5. **Disease, treatment, inflammation, hypoxia, and spaceflight:** primarily
   downstream targets. They must not be used to select the architecture on the same
   final-test cohorts. An expert axis is considered only with a separate development
   cohort or nested training-only procedure.

Technical variables such as RIN, library depth, detected-gene count, ischemic time,
platform, and study are nuisance controls or technical adapters, not biological
experts.

### 18.5 Final evaluation ladder

The public comparison landscape has two different roles:

- **BulkRNABert** is the closer architectural peer: an encoder-only, masked
  bulk-expression reconstruction model. Its architecture should be retrained on the
  exact frozen project partition for the primary same-data comparison, because a
  public GTEx-pretrained checkpoint may overlap held-out GTEx donors.
- **BulkFormer** is the stronger large-scale SOTA reference. Published
  BulkFormer-147M is the practical SOTA ceiling; BulkFormer-37M retraining is an
  optional capacity comparison and must not delay the core table.

Core final-week representations:

1. raw expression;
2. PCA;
3. matched pooled trunk;
4. pooled trunk plus explicit organ label;
5. true-organ specialist;
6. hard router;
7. soft router;
8. pooled fallback;
9. matched-data BulkRNABert; and
10. published BulkFormer-147M.

Primary downstream tasks are within-organ disease/state prediction, low-label
learning curves, and mission/study-held-out spaceflight or stress prediction. Every
model receives the same patient/donor/study splits, linear probe and small-MLP
budgets, seeds, and test-access policy.

### 18.6 Decisions already closed

- Organ remains the protected, independently validated expert axis.
- No best-seed or favorable-organ selection.
- No architecture selection on ARCHS4 or a final downstream test cohort.
- Screen many axes cheaply; train at most one.
- A pooled fallback and per-organ safety report are mandatory.
- BulkRNABert and BulkFormer answer different comparison questions and should not
  be collapsed into one undifferentiated ranking.
- The August 17 core deliverable takes precedence over optional survival,
  drug-response, published-BulkRNABert, and retrained-BulkFormer-37M extensions.

### 18.7 Questions for Claude

Please review this as an execution protocol, not as a request to reopen the completed
Stage 2B design:

1. Is the Tier-0/Tier-1/Tier-2 funnel the fastest valid way to test many biological
   axes without overfitting?
2. What exact pre-outcome gates would you use to advance at most two Tier-1 axes?
   Please distinguish a practical smoke gate from a final confirmatory gate.
3. Which single public, reproducible cell-composition reference and which compact
   public pathway/program collection would you choose under the time limit?
4. For continuous program scores, is organ-conditional incremental R2 plus a
   protected-adapter utility test sufficient, or is another falsification control
   essential?
5. Which failure pattern should force us to stop multiaxis work on August 2 and use
   organ plus pooled fallback?
6. Is matched-data BulkRNABert plus published BulkFormer-147M the correct minimum
   external pair for the final evaluation, given the overlap and schedule concerns?

Please append your response under **18.8 Claude response** and preserve the closed
decisions unless you identify a concrete integrity or scientific-validity problem.

### 18.8 Claude response

Pending.
