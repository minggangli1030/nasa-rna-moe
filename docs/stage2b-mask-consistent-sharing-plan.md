# Stage 2B: mask-consistent sharing and refusal plan

**Status:** converged execution plan; Phase A complete, Phase B implementation next

**Reviewed:** 2026-07-30 by Claude and Codex through four recorded rounds

**Input note:** [`../CLAUDE.md`](../CLAUDE.md)

## Decision

The external organ-expert result remains the validated benchmark. Stage 2 has also
established that indiscriminate cross-organ sharing is unsafe: same-budget
substitution was harmful for all 56 directed pairs, helpful additive effects were
not stable across trunk and optimization seeds, and the coefficient-supervised
shared path harmed skin in two of three seeds.

The next phase should therefore target a **safe sharing/refusal policy**, not a
high-rank representation for its own sake. Utility and reproducibility of the
share/decline decision are primary. Biological interpretation and coefficient rank
are secondary diagnostics.

The critique in `CLAUDE.md` materially improves the plan in four ways:

1. repair the multi-phase training harness before another scientific run;
2. remove the partial-mask/full-mask mismatch on both the shared input and target;
3. measure stability on functional gain/harm decisions, not only individual
   coordinates; and
4. treat reproducible refusal of harmful sharing as a valid deliverable.

The review is now converged. `CLAUDE.md` Sections 15 and 16 accept the corrections,
add a cross-trunk oracle-transfer audit, and close planning. This document is
canonical for implementation. It is still not a frozen scientific protocol; Phase A
and the training-only diagnostic freeze come first.

Claude's final implementation review in Section 17 is also accepted. It does not
change the scientific design. It closes mechanical failure modes that would be
expensive or silent:

- canonical caches bind sample, trunk, manifest, score-index, decoder, mask-token,
  preprocessing, ridge, and dtype identities and are never partially reused;
- extraction is deterministic, fixed-batch, evaluation-mode, and bitwise repeated
  on a 32-sample probe;
- one ridge value is selected in gene space and shared by every trunk;
- standardized coefficient supervision uses uniform component weights;
- the sharing gate starts near closed but outside sigmoid saturation and must move;
- every rank result carries both rank definitions, spectrum, convention,
  aggregation unit, ridge, effective degrees of freedom, and attainable ceiling;
- every fitted normalization uses training donors only; and
- a cross-host smoke determines whether the two-host split may use hash equality or
  must fall back to a recorded numerical tolerance.

## Corrections to the advisory brief

### Donor rank was not capped at seven

The current evaluator averages coefficients within each donor and computes rank
across the resulting donor vectors. It does **not** reduce the data to eight organ
centroids. Its rank is therefore not capped at \(K-1=7\); the existing oracle donor
ranks of 7.00, 7.68, and 8.05 directly disprove that claimed cap.

The old donor-rank threshold may still be poorly calibrated, but it cannot be
retired using the proposed closed-form argument. The read-only audit will estimate
an attainable empirical ceiling under the exact aggregation and scaling convention.
Donor rank will be descriptive in Stage 2B; the primary gates will concern utility,
safety, and functional policy stability.

The implementation also uses entropy effective rank,
\(\exp[-\sum_i p_i \log p_i]\), whereas the advisory derivation used participation
ratio. Future reports will name the metric and scaling convention and show the
eigenvalue spectrum rather than treating different definitions as interchangeable.

### Canonical input requires a canonical forward pass

Pooling only non-score hidden states is not sufficient. In the transformer, those
hidden states can attend to visible score genes and therefore still change with the
draw-specific mask.

For the shared path, every sample must receive a **full-score-mask canonical
forward pass** through the frozen trunk. The head input is a summary of non-score
hidden states from that canonical pass, cached by sample ID, trunk hash, manifest
hash, and score-index hash. The score genes are absent from both the direct input
and its attention context.

### Pathway outputs may include score genes

The input must not reveal score genes. The fixed decoder is an output map into
score-gene residuals and may necessarily contain score-gene pathway membership.
The leakage firewall applies to head inputs and to the donors used to fit a basis,
not to the biological annotation of the prediction target.

### Raw substitution harm is not pair-specific interference

The 56-edge substitution estimand replaced half of recipient exposure, so its raw
harm includes the ordinary cost of seeing less recipient data. A refusal predictor
must not learn that quantity as if it were pure donor incompatibility.

The refusal audit will separately model:

- **opportunity cost:** named A750+B750 versus A1500; and
- **donor-specific excess effect:** named donor versus its exposure-matched random
  auxiliary controls.

Only the second quantity is eligible to support a pair-specific refusal rule. The
eight additive edges remain an independent, small validation set. Failure to
generalize produces a conservative list of replicated harmful edges, not a
graph-wide learned policy.

Skin appearing once as a harmful recipient and once as a harmful donor is not, by
itself, evidence for a recipient-only rule.

### Five trunks are a confirmation resource, not imaginary inputs

Only pooled trunks 17, 42, and 101 are currently hash-pinned for this lineage.
Two additional trunk seeds require full prospective trunk training; optimization
replicates 211, 223, and 227 are not substitutes.

The code will support five trunks, but compute is staged:

1. freeze the complete architecture and gates;
2. run the existing three trunks as a development screen without changing the
   protocol; and
3. only if the screen clears its prespecified continuation gate, train two
   prospectively fixed additional trunks and complete the five-trunk analysis.

No five-seed stability claim is permitted until those two trunks exist and all five
are reported.

## Execution sequence

### Phase A — fail-closed harness repair

This is blocking and changes no scientific result.

1. Construct a fresh optimizer and scheduler for every phase.
2. Before the first update of a phase, assert every trainable parameter group has a
   positive learning rate.
3. After a small fixed number of updates, require a nonzero parameter delta for
   every module declared trainable.
4. Hash trainable tensors at each phase boundary and fail if a phase that was
   supposed to train produced an identical state.
5. Make seed-by-organ performance matrices mandatory evaluator outputs.
6. Add tests that deliberately use a zero learning rate and an unchanged second
   phase; both must fail closed.
7. Preserve the legitimate possibility that a cosine schedule reaches zero at its
   predetermined final step. The assertion is on phase initialization and actual
   parameter movement, not on the terminal scheduled learning rate.

**Acceptance:** the full focused suite passes, both deliberately broken toy phases
abort, and no scientific VM run starts before these checks pass.

**Completed:** commit `b4100a1efd0090064a1a079fe658d7f116526373`
implements the reusable guards, constructs fresh optimizers for the repaired second
phase, and makes the full seed-by-organ condition matrix mandatory. The local Stage
2-focused suite passes 38 tests. A seed-17 mechanical VM smoke is the final Phase A
runtime check; it creates no scientific result.

### Phase B — one frozen, read-only diagnostic protocol

Use GTEx training donors only. Do not access ARCHS4 or the donor-disjoint calibration
split. Reconstruct every label from the hash-pinned manifest and write immutable
checksums.

#### B0. Cross-trunk oracle-transfer audit

This tests whether the existing high-rank expression-PCA oracle target is shared
across trunks or is merely seed-specific internal bookkeeping. It performs no
neural-checkpoint updates, but its donor-grouped ridge probes are statistical fits
and remain inside training-donor folds.

Use the same canonical full-score-mask extraction as B1:

1. compute canonical non-score hidden summaries and full-score post-private oracle
   coefficients for trunks 17, 42, and 101;
2. run all within-seed and ordered cross-seed grouped ridge probes;
3. compare coefficient targets directly and by principal angles/CCA against a
   frozen random-basis null; and
4. report predicted rank, component correlation, and recoverable residual error.

An implementation-regression check may reproduce the old seed-17 probe on its exact
immutable arrays, but it cannot select a branch. New B0 conclusions use training
donors only and their own frozen thresholds.

Interpretation:

- high target agreement and high cross-seed probes: cross-trunk reproducible,
  sample-associated structure; empirical rank ceilings may remain secondary gates;
- high agreement and low cross-seed probes: shared target but trunk-specific map;
  keep per-trunk heads and interpret coordinate comparison cautiously; or
- low target agreement: the oracle target is trunk-specific; rank becomes
  descriptive only.

None of these branches blocks the primary utility/safety/refusal experiment. They
control only the meaning of representation rank. They do not establish intrinsic
biology.

#### B1. Mask-source decomposition

For repeated partial masks and the full score mask, measure coefficient agreement
for the same sample. Separate:

- **behavioral variation:** rerun the frozen trunk under each mask; and
- **geometric variation:** hold the full-mask residual fixed and change only the
  decoder rows used in the solve.

Report mask-to-mask cosine, partial-to-full cosine, per-component
mask-variance/sample-variance, Gram condition number, and leverage. Report every
organ, including whether skin is unusually unstable. This is explanatory; Stage 2B
will remove both sources by construction regardless of the result.

#### B2. Rank and scaling audit

Recompute learned and oracle spectra using:

- raw coefficients;
- per-component standardized coefficients; and
- decoder-whitened coordinates.

For each, report entropy effective rank, participation ratio, eigenvalues,
cumulative variance, aggregation unit, and ridge strength. State explicitly that
the frozen Stage 2 gate used entropy effective rank on unstandardized outputs.

#### B3. Empirical attainable ceiling

Bootstrap donors to estimate oracle sample, donor, and within-organ rank under the
same conventions. Use the lower confidence bound of the within-organ oracle rank as
the denominator of any later relative-rank diagnostic only if B0 supports a
cross-trunk target. Otherwise report it descriptively. Do not assume a \(K-1\)
donor ceiling.

#### B4. Metadata inventory and variance decomposition

First inventory which training-only fields are genuinely available and reliable.
Then use donor-grouped/nested cross-validation to compare organ with supported
attributes such as tissue site, sex, age bracket, RIN, ischemic time, detected-gene
count, and library depth. Do not invent platform or study variation if GTEx does not
contain an estimable contrast.

Model pooled reconstruction error and post-private residual structure separately.
Report cross-validated incremental \(R^2\), uncertainty, missingness, and correlation
with organ.

**Pause condition:** if a non-organ attribute reproducibly explains more held-out
residual variation than organ, write a short axis-selection amendment for human
review before choosing the Stage 2B primary conditioning axis.

#### B5. Refusal audit

Run this from already frozen numeric results:

1. fit recipient-only, donor-only, and recipient+donor null models;
2. repeat them for donor-specific excess effect versus matched random auxiliaries;
3. use leave-one-organ-out validation, removing every edge touching the held-out
   organ;
4. only if the null is beaten, fit at most three outcome-independent features
   frozen before fitting; and
5. evaluate ranking on the eight additive edges using named-versus-random effect,
   while reporting the A2250 comparison separately.

Report precision, recall, specificity, and the fraction of eligible edges flagged.
Freeze a maximum non-vacuous flagged fraction before fitting; a refuse-everything
rule cannot pass.

If no feature model beats the null, the deliverable is “private by default” plus
the already replicated harmful edges. It is not a failed analysis.

### Phase C — freeze the Stage 2B scientific design

Phase C begins only after the Phase B report selects the conditioning axis and
basis arms. Nothing below is fit before the protocol JSON and SHA256 are recorded.

#### Canonical input and target

For each seed and training sample:

1. replace every score gene with the mask token;
2. run the frozen trunk once;
3. summarize only non-score hidden states from that full-score-mask pass;
4. obtain the pooled and frozen-private full-score predictions;
5. form the full score-gene residual;
6. project it through a fixed-row ridge solve into the candidate decoder; and
7. cache input, target, and integrity keys.

The same sample must yield bitwise-identical cached input and target across epochs.
No draw-specific row subset or partial-mask hidden summary is allowed in the shared
path.

Ridge strength is selected by donor-grouped cross-fitting on training donors only,
using held-out residual reconstruction—not coefficient rank or a Stage 2B outcome.

#### Primary representation arms

- **Expression-PCA basis:** the exact existing common decoder is the primary causal
  repair arm. Keeping it fixed isolates whether canonical input/target construction
  fixes the Stage 2 failure.
- **Random basis:** matched dimension and scale; always required.
- **Residual and pathway bases:** deferred. They are not automatically launched
  after a scientific failure of the canonical expression-PCA candidate.

Do not launch two unrelated architectures simultaneously. First run a mechanical
smoke, then the exact-PCA causal repair against its controls. A residual basis or
gated shared-expert architecture requires a later, separately approved protocol
rather than serving as an automatic positive-result search.

#### Architecture and routing

For trunks 17, 42, and 101, reuse the hash-pinned valid phase-1 organ-private states
from the completed repair lineage; the zero-learning-rate defect affected only the
nominal extended phase. Add the exact fixed-decoder shared residual path with a
bounded organ/axis-specific gate initialized to decline sharing. Freeze the private
state and train only the shared head and gates. Any future new trunk receives a
private path under the same frozen phase-1 contract.

Because organ identity may be unavailable at deployment, evaluate:

- revealed-organ dispatch as a mechanistic upper bound; and
- the already frozen input-only hard/soft router as the deployable sensitivity
  analysis.

A design that succeeds only with revealed labels does not establish an automatic
sharing policy.

The no-harm objective uses only donor-balanced training folds and their
cross-fitted private reference. Calibration outcomes never enter the loss.

#### Controls

Required in every reported trunk:

- pooled trunk;
- frozen organ-private path;
- valid extended-private and extended-generic controls using fresh phase
  optimizers;
- random decoder/basis;
- random conditioning labels; and
- parameter- and update-matched generic capacity.

### Phase D — staged execution

1. Local unit and integration tests.
2. One real-data GPU mechanical smoke with deliberately checked phase transitions
   and canonical-cache round trips.
3. Three existing trunks, all conditions, no selection.
4. Frozen development continuation gate:
   - positive aggregate utility versus private in at least two of three trunks;
   - no organ worse than the frozen safety limit in any trunk; and
   - functional gain/harm direction concordant across the three trunks.
   Passing continues unchanged to two new trunks. Scientifically failing after all
   mechanical preconditions pass stops the shared-coordinate program and ships
   Stage 1 plus the refusal deliverable.
5. If and only if that gate passes, prospectively derive two new trunk seeds,
   train their pooled trunks from scratch under the unchanged Stage 1 contract, and
   run the identical Stage 2B conditions.
6. Evaluate all five trunks and produce immutable compact outputs.
7. Access a new untouched study-disjoint multisource cohort only after the complete
   five-trunk gate passes.

The three-trunk screen controls compute; it is not confirmation and cannot be used
to revise architecture, thresholds, basis, or loss.

#### Mechanical preconditions before interpreting utility

- cached pooled and private predictions round-trip direct full-score-mask inference
  on a hash-pinned smoke set within a frozen tolerance;
- candidate predictions with the shared contribution forced off equal the frozen
  private condition within that tolerance;
- every canonical input has every score gene replaced by the mask token; and
- all phase LR, parameter-delta, and tensor-hash guards pass.

Failure is mechanical, not scientific. Preserve the failed path and repair only in a
new output path.

#### VM topology

Verified on 2026-07-30:

- primary `moe-reboot`: idle A100 40 GB, 35 GB free, complete repair lineage;
- secondary `149.165.168.111`: idle A100 20 GB, 13 GB free, exact expression table
  and pooled trunks already present.

After the exact commit and protocol hashes are frozen:

1. primary runs seeds 17 and 42;
2. secondary runs seed 101;
3. transfer only the compact valid seed-101 private state needed for initialization,
   plus the exact code/protocol, to the secondary;
4. transfer back compact caches, scores, metadata, logs, and checksums—not redundant
   expression data or unnecessary checkpoints; and
5. evaluate all three lineages together on primary in a new immutable result path.

Worktree and result names must include the eventual full scientific commit. Neither
host may reuse or overwrite a prior result.

## Gates to freeze before Phase D

Exact numerical thresholds require the Phase B null distributions and empirical
ceilings, but their meanings are fixed now.

- **Utility:** the shared policy beats pooled and frozen organ-private references.
  The final five-trunk requirement is at least four positive trunks with
  donor-bootstrap intervals above zero and a positive random-effects estimate.
- **Safety:** no organ exceeds the preregistered harm boundary versus its frozen
  private reference in any trunk. Report every organ-by-trunk cell.
- **Functional stability:** gain/harm vectors and binary share/decline decisions
  agree across trunks. Thresholds are frozen from training-only random-label/null
  distributions, not chosen after candidate outcomes.
- **Control dominance:** candidate beats matched random-basis and random-label
  controls without seed selection.
- **Representation:** within-organ learned rank is reported relative to the
  bootstrapped oracle ceiling under the same metric and scaling. It is secondary:
  safe, useful, stable low-dimensional sharing may pass with an honest
  low-dimensional claim.
- **Subspace alignment:** compare fixed-basis coefficient subspaces with principal
  angles/CCA and a frozen random-basis null. Coordinate-wise correlations remain
  descriptive.
- **Automatic routing:** the input-only route must preserve the direction and most
  of the utility of the revealed-label policy before external confirmation.

## Stopping rules

- No post-outcome threshold, basis, seed, organ, or checkpoint selection.
- One bounded safety repair is allowed only if utility and functional stability
  pass but the learned gate fails to protect an organ. The repair must be specified
  before inspecting any repair outcome.
- If mask-consistent sharing fails utility, stop the shared-coordinate program.
- If utility is positive but the policy remains unstable after the five trunks,
  stop claiming learnable helpful transfer and ship the conservative refusal rule.
- No Stage 2B development access to ARCHS4.

## Immediate implementation backlog

1. Add and test the optimizer/phase-state guards.
2. Implement one canonical full-score-mask extractor reused by B0, B1, and Phase C.
3. Implement a strict diagnostic freezer and evaluator for B0–B4.
4. Implement the random-adjusted refusal audit B5, including flagged coverage.
5. Produce the Phase B report and freeze its checksum manifest.
6. Freeze the exact-PCA Stage 2B protocol and decision thresholds.
7. Implement the gated shared path around the hash-pinned private states.
8. Run local tests, VM smoke, then the frozen three-trunk screen.

No VM scientific run should begin before items 1–7 reach their stated freeze point.

## Concrete implementation map

Names below are the planned interfaces; final paths may be adjusted before the first
commit to match repository conventions, but each responsibility remains separate.

### Work package A — reusable phase guards

- add a small reusable guard module under `core/` for optimizer-LR validation,
  trainable-state snapshots, parameter-delta checks, and deterministic tensor hashes;
- integrate it into `core/train_stage2_aligned_program_repair.py` without changing
  any immutable prior result;
- construct fresh phase-2 optimizers/schedulers for the extended controls; and
- add focused tests covering positive training, deliberate zero LR, declared
  trainable modules that do not move, terminal cosine LR zero, and identical
  phase-boundary hashes.

Acceptance is mechanical. Prior artifacts are not regenerated or relabeled.

### Work package B — frozen diagnostic lineage

- `evaluation/freeze_stage2b_diagnostic_protocol.py`: bind input hashes, training
  donors, mask replicates, probe folds, ridge grid, rank definitions, metadata
  availability rules, refusal features/nulls, random nulls, and every B0–B5 branch;
- `evaluation/extract_stage2b_canonical_training_cache.py`: one full-score-mask
  forward pass per sample/trunk, plus repeated partial-mask B1 ablations, with
  pooled/private round trips and no calibration/ARCHS4 access;
- `evaluation/evaluate_stage2b_diagnostics.py`: B0–B4, spectra, probes, ceilings,
  metadata inventory, and the written branch decision;
- `evaluation/evaluate_stage2b_refusal.py`: random-adjusted 56-edge analysis and
  eight-edge additive holdout, including flagged fraction; and
- `runs/run_stage2b_diagnostics.sh`: strict clean-commit launcher and immutable
  checksum finalizer.

The extractor writes numeric arrays only. Text labels are reconstructed from the
hash-pinned manifest. The evaluator never enables pickle loading.

### Work package C — frozen scientific candidate

- extend `core/stage2_program_model.py` with a bounded organ gate and an explicit
  shared-off path;
- implement a Stage 2B trainer that loads the exact valid phase-1 private state,
  freezes it, trains the exact-PCA coefficient head and gate from canonical caches,
  and trains matched random-basis/random-label controls;
- implement the evaluator with pooled/private/control comparisons, functional
  gate-off effects, per-organ matrices, rank spectra, random-effects summaries, and
  the bidirectional three-trunk decision;
- add a protocol freezer that binds the B0–B5 decision, exact thresholds, all
  checkpoint/cache hashes, phase budgets, and the prospective new-trunk seed
  derivation rule; and
- add strict smoke/full launchers that create new output roots and refuse a dirty or
  mismatched commit.

The revealed-organ condition is primary for the mechanistic question. Existing
input-only hard/soft routing is evaluated only after the three-trunk candidate
passes and before any external cohort is opened.

### Freeze and commit boundaries

1. **A-commit:** harness guards and tests only.
2. **B-freeze:** diagnostic protocol JSON and SHA256 before any new training-donor
   diagnostic output.
3. **B-result commit:** compact B0–B5 results, checksums, and the deterministic
   branch; no candidate model yet.
4. **C-freeze:** exact candidate protocol and gates after B, before candidate
   calibration outcomes.
5. **C-commit:** clean deployable trainer/evaluator/launchers and frozen protocol.
6. **VM result commit:** compact verified evaluation and documentation after the
   frozen three-trunk decision.

### VM launch order

1. Push the clean C-commit.
2. Create new detached worktrees on both hosts named from its short SHA.
3. Verify exact SHA256 for expression, manifest, axis definitions, PCA/random
   decoders, pooled trunks, and valid private states.
4. Transfer the compact seed-101 private state and frozen code/protocol to the
   secondary; do not recopy the expression table or pooled trunks.
5. Run one seed-17 real-data smoke on primary and verify every mechanical
   precondition.
6. Launch seeds 17/42 sequentially on primary and seed 101 on secondary in detached
   sessions.
7. Verify per-seed metadata, completed update counts, tensor hashes, score/cache
   hashes, GPU/process exit, and immutable manifests.
8. Transfer the compact seed-101 lineage into a distinct primary path.
9. Run the frozen evaluator once across the three exact roots.
10. Apply the recorded pass/stop rule. A pass starts the separately frozen two-trunk
    extension; a scientific fail ends the shared-coordinate program.

The smoke determines the operational ETA. The previous repair required roughly two
hours per seed, but canonical extraction and new controls change the workload, so
that historical rate is planning context rather than a promise.

## Claim boundary

All Phase B and Stage 2B development evidence is donor-disjoint or training-only
GTEx evidence. It does not establish study universality, a disease or spaceflight
benefit, or biological mechanism. Stage 1 remains the only completed external
organ-specialization result. A new untouched study-disjoint cohort is required for
confirmation of any learned sharing/refusal policy.
