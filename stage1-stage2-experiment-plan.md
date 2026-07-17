# Stage 1 -> Stage 2 Experiment and Code Runbook

**Last updated:** 2026-07-16.

`Stage` identifies the research phase: Stage 0 is inherited human/mouse/mixed
completion, Stage 1 is original organ specialization, and Stage 2 is biological
discovery. `V1/V2/V3` remain independent Stage 0 data/model/debugging generations;
`D1/D2/D3` remain research directions. This runbook starts at Stage 1. The active
Stage 0 shuffled-pooled control must complete and be evaluated according to
`progress.md` before any long Stage 1 GPU campaign.

This is the implementation contract for deciding whether the basic human-organ MoE
works and, only then, running the transfer-validated label-free routing experiment.
It separates the implemented Stage 1 mechanical-smoke path from definitive-cohort
and Stage 2 commands that still require data work or code.

## Current decision: Stage 1 definitive run is NO-GO

The checked-in `K=5` manifest is useful for pipeline development only.

- Specialist training counts are brain 783, skin 409, liver 345, lung 241, and
  colon 220. Every organ fails the planned 1,000-clean-training-row gate.
- Each organ has only 7-15 final-test connected study groups.
- At least 94 of 2,856 rows match obvious missed exclusions such as `GBM`,
  `glioblastoma`, `U87`, `cell_line`, `organoids`, `HSAEpC`, or `cancerous`.
- The complete manifest-driven mechanical-smoke stack now exists: exact extraction,
  deterministic training, balanced random shards, frozen prediction cache, five-class
  blind gate, full comparison ladder, decision code, and fail-fast launcher. It has
  passed an end-to-end synthetic run but has not yet run on the remote ARCHS4 H5.
- `core/train_single.py` remains unsuitable for Stage 1 because it creates its own
  random row split. Stage 1 uses `core/train_manifest.py` instead.
- `core/train_moe.py` is an older gate over three frozen 5k species experts. It is
  not the shared-trunk latent MoE required for Stage 2.

The current cohort may be used for schema and one-epoch smoke tests. Its losses must
not be interpreted as biological evidence.

### Why the current cohort is small, and how imbalance is controlled

ARCHS4 itself is not small. The mounted human v11 H5 contains 441,356 samples and
35,238 gene rows; the current official human gene-level release lists 1,093,742
samples. The conservative local audit retained only 14,096/441,356 rows (3.2%):
195,698 were removed by the single-cell-probability filter, 165,331 as cell/culture-
like, and 66,231 because the current free-text metadata did not support one clear
organ assignment. The shortage is therefore validated bulk-tissue labels and
independent studies per organ, compounded by an older local snapshot—not raw ARCHS4
expression. See the [ARCHS4 downloads](https://archs4.org/download) and
[tissue-atlas help](https://archs4.org/help) pages.

ARCHS4 does provide a tissue atlas, but its tissue groups are a derived search/atlas
layer over GEO metadata rather than a sample-level ground-truth organ field in this
H5. Use those groups to expand candidate retrieval, then verify source metadata and
ontology mappings before freezing scientific labels.

The smoke comparison prevents brain prevalence from dominating:

- select exactly 220 training rows from each of five organs, spread across studies;
- train five random controls of 220 rows each, every one containing exactly 44 rows
  from each organ;
- use the same organ/study-balanced sampling rule for pooled, specialist, and random
  models, plus equal-organ/equal-study checkpoint selection;
- fit the blind router with balanced class weights and equal-study weights; and
- make equal-organ/equal-study test MSE primary while retaining the natural sample
  distribution only as a secondary sensitivity analysis.

Balancing makes the comparison fair. It cannot create label precision, additional
independent studies, or statistical power, which is why the same cohort remains a
mechanical smoke rather than a biological experiment.

After the smoke, label recovery should proceed as a separate data track:

1. export ARCHS4 atlas assignments and all local `source_name`, title, and
   `characteristics` fields for unmatched/ambiguous samples;
2. normalize explicit anatomy terms to a frozen UBERON-style organ hierarchy and keep
   disease/tumor/cell-source status as separate fields rather than mixing it into organ;
3. query original GEO sample/study metadata only where the local H5 text is missing or
   contradictory;
4. assign `high_confidence`, `ambiguous`, and `unlabeled` tiers with a reason/provenance
   trail, never silently force a label; and
5. give the PI a compact policy sheet for biologically consequential edge cases—such
   as diseased non-tumor tissue, adjacent anatomy, and tissue-derived primary cells—
   after automated reconciliation has reduced the review burden.

Only high-confidence rows enter the definitive cohort. The current smoke does not wait
for this track because it tests software structure, not the biological hypothesis.

## Stage 1 decision boundary

Stage 1 has four distinct questions. A model can be technically valid without being
scientifically useful, and experts can work even when the blind router fails.

### Gate 0 — cohort and label readiness

For a definitive organ claim, freeze these requirements before training:

1. `K >= 3` qualifying organs.
2. Per organ: at least 1,000 clean model-training rows, 30 model-training connected
   study groups, 10 gate-calibration groups, and 15 final-test groups.
3. Recipients used for Stage 2 transfer edges should preferably have at least 20
   final lockbox groups and prospective 80% power for a 5% relative MSE effect.
4. Manually review at least 50 stratified labels per organ and require at least 95%
   observed precision. If the intended claim is that the 95% confidence lower bound
   exceeds 95%, use approximately 72 error-free reviews per organ instead.
5. Retain the original characteristics/source/title metadata, freeze ontology and
   exclusion rules, and rerun the entire audit after any rule change.

Failure means **pipeline pilot only**. An underpowered null cannot decide whether
organ specialization exists.

### Gate 1 — technical validity and backbone health

All conditions below are mandatory. Failure invalidates the result rather than
making it a scientific null.

1. Zero connected-study overlap among model training, model validation, gate
   calibration, final Stage 1 test, and the discovery lockbox.
2. The pooled training-ID set exactly equals the union of specialist training IDs.
3. Identical gene identity/order, one `log1p`, train-only gene means, and a frozen
   deterministic 30% mask for every paired evaluation.
4. Explicitly initialize Python, NumPy, Torch CPU, Torch CUDA, sampler, and mask RNGs;
   store every seed and code/data/split/config hash.
5. The pooled model and every claim-bearing expert beat the appropriate train-only
   gene-mean baseline on strict studies: both the absolute MSE-improvement and
   residual-Pearson 95% CI lower bounds must exceed zero. A relative MSE gain of at
   least 5% is healthy; 0-5% is technically alive but weak.
6. Use three training seeds. The primary effect must have the same sign in all three,
   its study+seed interval must exclude zero, and seed SD should be less than half the
   mean effect. Otherwise add seeds or stop expansion.

### Gate 2 — does organ specialization actually exist?

Let `L(condition)` be equal-organ, equal-study macro masked MSE on the untouched
Stage 1 test.

1. **Known-organ ceiling:** true-organ hard routing must reduce MSE versus pooled by
   at least 5%, with positive MSE and residual-Pearson intervals.
2. **Complementary expert ceiling:** the soft oracle must beat the organ-fixed blend
   by at least 3%, with a positive MSE interval.
3. **Biological rather than generic sharding:** the organ-fixed ensemble must beat a
   size/exposure-matched random-shard-fixed ensemble by at least 3%, with a positive
   interval. Also report the random-shard soft oracle.

If the soft oracle is below 3%, there is no useful sample-dependent routing ceiling:
stop the MoE discovery path. If the oracle works but true-organ routing does not,
organ is probably the wrong partition; only a bounded label-free feasibility pilot
is justified.

### Gate 3 — can a blind router recover the specialization?

The deployable Stage 1 system passes only if blind top-1 routing:

1. reduces MSE versus pooled by at least 5%;
2. has paired absolute-MSE and residual-Pearson CI lower bounds above zero;
3. recovers at least 80% of the true-organ gain:

   ```text
   recovery = (L_pooled - L_blind_top1) / (L_pooled - L_true_organ_hard)
   ```

4. and blind soft routing beats the organ-fixed ensemble by at least 3% with a
   positive MSE interval.

Gate accuracy is diagnostic, not a substitute for end-to-end reconstruction. If the
known-organ ceiling passes but the blind gate fails, freeze the experts and debug
router input, calibration, confidence coverage, and target leakage first.

### Gate 4 — practical top-1 behavior

For an efficient-MoE claim:

- active inference FLOPs must be no more than 1.1 times the pooled model;
- measured p95 latency must be no more than 1.25 times pooled;
- total stored parameters/checkpoint size must be reported; and
- choose the fallback threshold on calibration studies and freeze a minimum coverage
  before test. A fallback-heavy system whose aggregate gain disappears is an ensemble,
  not an efficient top-1 MoE.

### Gate 5 — Stage 2 shared-trunk positive control

Stage 2 introduces a different architecture: a shared trunk with small residual
experts. Before interpreting label-free routes, train the same architecture with an
organ-supervised router as a positive control.

Require, on development/validation studies only:

1. supervised routing beats balanced-random routing by at least 3% relative MSE with
   a positive interval;
2. the effective number of experts is at least `0.6K` and no expert receives fewer
   than 2% of balanced routes;
3. routes and counterfactual expert advantages are stable across three seeds and
   repeated masks (initial permutation-aligned `AMI >= 0.5`); and
4. top-1 dispatch has the intended active-compute budget.

If this positive control cannot recover a known biological partition, do not attach
biological meaning to the label-free version.

## Stage 1 -> Stage 2 outcome table

| Outcome | Evidence | Authorized next experiment |
|---|---|---|
| **Green** | Every technical gate passes; true-organ and oracle ceilings pass; organ-fixed beats random-fixed; blind top-1 passes; three-seed stability | Run selected transfer confirmation and the frozen-trunk label-free pilot |
| **Amber: router failure** | True-organ, oracle, and organ-vs-random pass; blind router fails | Run selected controlled transfer only; diagnose the router before label-free interpretation |
| **Amber: organ is wrong axis** | Oracle clears 3%, but true-organ and/or organ-vs-random fails | Run at most a bounded shared-trunk feasibility pilot; do not run a full organ matrix or claim biology |
| **Amber: ensemble only** | Blind routing beats fixed but not pooled | Mechanistic routing result only; no better-system claim |
| **Red** | Backbone baseline fails, strict study result fails, oracle is below 3%, effects change sign across seeds, or provenance/leakage fails | Stop Stage 2 and repair data/model/evaluation |

Stage 1 therefore need not be a perfect deployable win for every diagnostic Stage 2
pilot. It must at minimum establish that the backbone learns, experts contain stable
complementary information, and the evaluation distinguishes specialization from
random sharding and study leakage.

## Code readiness

### Exists now

| Purpose | Current file | Limitation |
|---|---|---|
| Conservative metadata audit | `evaluation/audit_archs4_organs.py` | Expanded tumor/cell exclusions and retained characteristics; regex labels still need manual/ontology validation |
| Pilot manifest and connected-group split | `evaluation/build_organ_pilot_manifest.py` | Three splits and pilot thresholds; current frozen pilot removed multi-organ groups |
| Balanced smoke/random protocol | `evaluation/build_balanced_organ_protocol.py` | Exactly 220 rows per organ; intentionally underpowered for biological inference |
| Exact expression extraction | `preprocessing/extract_manifest_expression.py` | Reads the frozen manifest and v11 H5; current definitive cohort is not ready |
| Deterministic role-aware training | `core/train_manifest.py` | Implements pooled/organ/random Stage 1 roles; Stage 2 transfer/latent roles remain planned |
| Prediction identity/cache | `evaluation/cache_organ_predictions.py` | Closed-cohort smoke contract; definitive external/unknown-organ handling remains |
| Five-class routing and comparison ladder | `evaluation/evaluate_organ_moe.py` | One report per training seed; smoke results are not decision evidence |
| Frozen decision rules | `evaluation/decide_organ_specialization.py` | Definitive use requires three independent seed reports |
| End-to-end smoke launcher | `runs/run_organ_smoke.sh` | Waits for Stage 0 by default and writes `SMOKE_ONLY`; no definitive launcher yet |
| Tests | `tests/test_*organ*`, `tests/test_extract_manifest_expression.py`, `tests/test_train_manifest.py` | Synthetic end-to-end path passes; the real H5 smoke is the next integration check |

The currently runnable audit commands are:

```bash
python3 evaluation/audit_archs4_organs.py \
  --human-h5 /media/volume/moe-reboot/archs4/human_matrix_v11.h5 \
  --output-dir artifacts/stage1_organ_audit_next

python3 evaluation/build_organ_pilot_manifest.py \
  --candidates artifacts/stage1_organ_audit_next/organ_candidates.parquet \
  --output-dir artifacts/stage1_organ_manifest_next \
  --seed 42 \
  --max-samples-per-group 20 \
  --min-series-groups 45 \
  --min-capped-samples 300 \
  --calibration-fraction 0.15 \
  --test-fraction 0.15
```

The `300` threshold is explicitly a pipeline-pilot threshold, not the definitive
post-split 1,000-training-row rule.

Preflight the implemented smoke without bypassing the Stage 0 execution gate:

```bash
runs/run_organ_smoke.sh --preflight
```

While Stage 0 is still running, `--preflight --allow-stage0-incomplete` may be used
only to inspect dependencies and paths. Do not use that override to launch the actual
smoke. After Stage 0 evaluation writes its completion marker, the default launcher
builds a timestamped, non-overwriting result directory and exercises the full path.

### Progressive Stage 1 pilot approved before definitive training

The small-data sequence intentionally separates software validation from biological
inference:

1. **Micro overfit:** 64-128 samples, 20-50 updates. Verify target hiding, loss
   decrease, gradients, deterministic masks, resume behavior, and cache identity.
2. **Five-organ mechanical smoke:** current `K=5` manifest, one seed, approximately
   50 updates per model. Run pooled, all organ experts, matched random shards, fixed
   blend, known-organ, blind, and oracle paths. This can expose multiclass/path bugs
   but cannot support a biological conclusion.
3. **Two-organ feasibility:** minimally clean brain and skin first, select them only
   because they have the greatest support, and run the production backbone for a
   matched 3-5 epoch exposure with seeds 17, 42, and 101. Estimate wall time, seed
   variance, true-organ headroom, organ-versus-random separation, oracle headroom,
   and blind-route recovery.

Once pilot evaluation is inspected, its studies are burned for engineering. The
definitive cohort must be expanded, re-audited, and assigned new connected-study
partitions, including a never-inspected discovery lockbox. A failure at rung 1 or 2
blocks scale because the implementation is invalid. A weak rung-3 effect blocks a
long campaign under the current design, but is not a powered biological null.

### Implemented smoke stack and remaining definitive work

Implemented on 2026-07-16:

1. `preprocessing/extract_manifest_expression.py` — exact IDs, canonical-gene TPM,
   provenance hashes, split checks, and fail-loud expression QC.
2. `evaluation/build_balanced_organ_protocol.py` — equal organ subsets plus size- and
   mixture-matched random shards while retaining natural-frequency rows.
3. `evaluation/filter_manifest_by_expression_qc.py` — explicit two-pass removal and
   rebalance if the extractor identifies low-information profiles.
4. `core/train_manifest.py` — explicit splits, seeded pooled/organ/random roles, fixed
   masks/updates, best/last retention, balanced validation, and prediction export.
5. `evaluation/cache_organ_predictions.py` and `evaluation/evaluate_organ_moe.py` —
   frozen masks/cache plus pooled, random, fixed, true-organ, blind, and oracle tests.
6. `evaluation/decide_organ_specialization.py` — frozen green/amber/red rules across
   independent seed reports.
7. `runs/run_organ_smoke.sh` — versioned, fail-fast, non-overwriting orchestration.

The local suite passes 70 tests, including exact extraction, split leakage, RNG/mask
determinism, random-shard matching, target-hidden routing, cache identity, evaluator
comparisons, decision branches, and launcher guards. A synthetic mini-H5 was run
through extraction, all model roles, caching, blind routing, and report generation.

Still required before Stage 1 can make a definitive decision:

1. expand and manually/ontology validate the human bulk-organ cohort;
2. implement/freeze `evaluation/build_organ_manifest.py` with separate model-train,
   model-validation, gate-calibration, final-test, and discovery-lockbox studies;
3. add calibrated abstention/pooled fallback and efficiency/latency measurement;
4. add `runs/run_organ_definitive.sh`, persistent remote artifact handling, and the
   exact three-seed campaign; and
5. run the real-H5 mechanical smoke, then the preregistered two-organ variance pilot.

## Planned Stage 2 code

The following commands are a concrete CLI contract, not currently runnable code.
Implement and unit-test the named files before launching GPU work.

### New or refactored components

1. `evaluation/build_transfer_blocks.py`
   - split each eligible domain's training/development studies into fixed equal-budget
     `A1` and `A2` blocks;
   - construct matched `B1` donor blocks and pseudogroup controls;
   - use one global block size when feasible so same-organ controls can be reused;
   - assert matched unique samples, study-count targets, updates, and sampling weights.
2. `core/train_affinity_screen.py`
   - run one balanced development-only pooled training job;
   - log how a donor-domain update changes each recipient-domain development loss;
   - initially measure gradients on the output head and final shared FFN rather than
     retaining all 37.85M parameter gradients;
   - output a directed screening matrix. This is selection evidence only.
3. `evaluation/select_transfer_pairs.py`
   - select a frozen small set of strongest positive, strongest negative, and near-zero
     unordered pairs from development data without lockbox access.
4. Extend `core/train_manifest.py` with `same_organ_control` and `cross_organ_pair`
   roles, then reuse it for same-organ controls and selected cross-organ pairs.
5. `evaluation/evaluate_transfer.py`
   - compute raw and controlled directed transfer on discovery-lockbox studies;
   - combine clustered-study and training-seed uncertainty; apply the frozen practical
     threshold and FDR correction.
6. Refactor `ExpressionPerformer` to expose `encode(x)` and `decode(h)` while keeping
   `forward(x)` numerically unchanged.
7. `core/train_latent_moe.py`
   - shared `ExpressionPerformer` trunk;
   - sample router pooled only from observed-gene hidden states;
   - `K` small residual FFN adapters plus scalar reconstruction heads;
   - `organ_supervised`, `balanced_random`, and `label_free` routing modes;
   - zero/small adapter initialization that reproduces the pooled trunk at step zero;
   - frozen-trunk first, full fine-tuning only after the feasibility gate.
8. `evaluation/evaluate_latent_moe.py`
   - prediction quality, all-expert counterfactual loss/routing regret, utilization,
     collapse, repeated-mask and seed stability, and organ/study/platform probes.
9. `evaluation/compare_route_transfer.py`
   - aggregate label-free route similarity by domain on untouched studies;
   - compare it with the symmetrized transfer compatibility graph;
   - keep directional asymmetry as a separate secondary result.
10. `evaluation/build_route_groups.py`
    - freeze a route-derived grouping for the final functional retraining test.

## Exact post-Stage-1 execution order

Use three fixed training seeds, initially `17`, `42`, and `101`. Freeze different
values before test access if desired; never choose seeds from observed results.

### 0. Machine-readable Stage 1 decision

```bash
# IMPLEMENTED — repeat --report once per independent definitive training seed.
python3 evaluation/decide_organ_specialization.py \
  --report results/stage1_organ_definitive/seed17/report.json \
  --report results/stage1_organ_definitive/seed42/report.json \
  --report results/stage1_organ_definitive/seed101/report.json \
  --output artifacts/stage1_organ_definitive/decision.json
```

- `green`: continue with selected transfer and frozen-trunk latent MoE.
- `amber_router`: run transfer only; pause label-free interpretation.
- `amber_axis`: at most run the small shared-trunk feasibility pilot.
- `amber_ensemble`: retain only the mechanistic ensemble result; do not claim a
  better practical system.
- `red`: stop.

### 1. Freeze equal-budget transfer blocks before screening

```bash
# PLANNED
python3 evaluation/build_transfer_blocks.py \
  --manifest artifacts/stage1_organ_definitive/manifest.parquet \
  --output-dir artifacts/stage2_discovery_protocol/blocks \
  --seed 314159 \
  --require-lockbox
```

The block manifest must be hashed before the affinity screen. The screen may choose
pairs, but it may not change block construction or access the lockbox.

### 2. Run one development-only affinity screen

```bash
# PLANNED
torchrun --standalone --nproc_per_node=1 core/train_affinity_screen.py \
  --config configs/discovery_affinity_screen.json \
  --blocks artifacts/stage2_discovery_protocol/blocks/blocks.parquet \
  --output-dir results/stage2_discovery_affinity_screen

python3 evaluation/select_transfer_pairs.py \
  --affinity results/stage2_discovery_affinity_screen/affinity.json \
  --one-positive --one-negative --one-null \
  --output artifacts/stage2_discovery_protocol/selected_pairs.json
```

The default is three unordered pairs, not a complete matrix. Inspect only development
statistics. Record pair selection, sign definition, practical-effect threshold, and
all hashes before training confirmatory models. Selection is deterministic—strongest
positive, strongest negative, and closest-to-zero eligible pair—so organ names cannot
be manually cherry-picked after viewing the screen.

### 3. Confirm the selected transfer pairs

```bash
# PLANNED launcher; internally calls core/train_manifest.py.
runs/run_discovery_transfer_confirm.sh \
  artifacts/stage2_discovery_protocol/selected_pairs.json \
  --seeds 17 42 101

python3 evaluation/evaluate_transfer.py \
  --runs results/stage2_discovery_transfer_confirm \
  --blocks artifacts/stage2_discovery_protocol/blocks \
  --lockbox-split discovery_lockbox \
  --output results/stage2_discovery_transfer_confirm/report.json
```

For recipient `A`, define positive benefit as:

```text
controlled_transfer[A <- B] =
    (L_A(f_A1+A2) - L_A(f_A1+B1)) / L_A(f_A1+A2)
```

`A1+A2` same-organ controls may be reused across selected donors when every seed,
budget, and block is identical. Keep best/last model artifacts plus compact histories;
do not retain every epoch for this grid. Use a predetermined final update for the
primary checkpoint; never use discovery-lockbox loss for early stopping or selection.

### 4. Validate the Stage 2 architecture with supervised and random routing

```bash
# PLANNED
runs/run_latent_moe_pilot.sh \
  --manifest artifacts/stage1_organ_definitive/manifest.parquet \
  --pooled-checkpoint checkpoints/stage1_organ_pooled/best_model.pt \
  --freeze-trunk \
  --modes organ_supervised balanced_random label_free \
  --seeds 17 42 101

python3 evaluation/evaluate_latent_moe.py \
  --runs results/stage2_discovery_latent_pilot \
  --split model_validation \
  --output results/stage2_discovery_latent_pilot/report.json
```

Do not evaluate label-free biology unless the organ-supervised mode passes Gate 5.
Do not full-fine-tune unless the frozen-trunk label-free routes are non-collapsed,
mask-stable, seed-stable, and not dominated by study/platform.

### 5. Run the definitive label-free model only after the pilot gate

```bash
# PLANNED
runs/run_latent_moe_definitive.sh \
  --manifest artifacts/stage1_organ_definitive/manifest.parquet \
  --config configs/discovery_latent_moe.json \
  --seeds 17 42 101

python3 evaluation/evaluate_latent_moe.py \
  --runs results/stage2_discovery_latent_definitive \
  --split discovery_lockbox \
  --repeated-masks 5 \
  --output results/stage2_discovery_latent_definitive/report.json
```

The router and experts never receive organ, study, platform, disease, sex, age, or
other phenotype labels during label-free training/model selection. Those variables
are used only after freezing for confound and biological validation.

### 6. Test the central route-transfer hypothesis

Route co-assignment is symmetric while transfer is directed. Freeze the primary
compatibility target as:

```text
compatibility[A,B] =
    (controlled_transfer[A <- B] + controlled_transfer[B <- A]) / 2
```

Analyze directional asymmetry separately.

```bash
# PLANNED
python3 evaluation/compare_route_transfer.py \
  --transfer results/stage2_discovery_transfer_confirm/report.json \
  --routes results/stage2_discovery_latent_definitive/routes_lockbox.parquet \
  --symmetrize mean \
  --qap-permutations 10000 \
  --output results/stage2_discovery_joint_test/report.json
```

With only three selected unordered pairs, report preregistered sign and rank
concordance; there are too few edges for a persuasive graph-level correlation test.
Only after the pilot justifies enough additional confirmed edges should the formal
criterion become `rho >= 0.5` with graph-aware permutation `p < 0.05`, consistent
across seeds. Functional retraining remains the stronger validation.

### 7. Perform the functional grouping test

```bash
# PLANNED
python3 evaluation/build_route_groups.py \
  --routes results/stage2_discovery_latent_definitive/routes_development.parquet \
  --output artifacts/stage2_discovery_protocol/route_groups.json

runs/run_route_group_retrain.sh \
  --groups artifacts/stage2_discovery_protocol/route_groups.json \
  --baselines pooled organ random \
  --seeds 17 42 101
```

Freeze groups on development studies, retrain every grouping from scratch, and
evaluate once on the lockbox at matched active compute and sample exposure. This is
the strongest protection against a post-hoc cluster story.

### 8. Conditional within-organ discovery

If label-free routing only recovers organ, that is a successful positive control but
not hidden biology. Brain is the only current plausible first within-organ branch.
Proceed only after curating disease, age, treatment, sex, and cell-composition metadata.
Freeze a small `K=2-3` route definition, test within-study and cross-study recurrence,
compare with raw expression/PCA/NMF, and require external replication before making a
biological-discovery claim.

## Artifact contract

Every Stage 1/2 run directory must contain:

- resolved config and explicit seed;
- Git commit plus dirty diff hash;
- sample, connected-study, split, gene-order, mask, and source-data hashes;
- model role, active/total parameter counts, measured latency, and GPU-hours;
- best/last checkpoint hashes and compact loss history;
- per-sample prediction/route cache keyed by immutable sample ID; and
- an atomic `COMPLETE` marker written only after validation.

New run manifests should record research stage and model generation independently:

```json
{
  "research_stage": "stage1_organs",
  "experiment": "organ_specialization",
  "inherited_backbone": "stage0_v3_expression_performer",
  "protocol_version": 1
}
```

Allowed research-stage values are `stage0_interspecies`, `stage1_organs`, and
`stage2_discovery`. Values `v1`, `v2`, and `v3` are reserved for Stage 0 model/data
generations or explicit inherited-backbone lineage; Stage 1/2 protocols use their own
semantic names and integer schema/protocol versions.

Expected decision artifacts are:

```text
artifacts/stage1_organ_definitive/decision.json
artifacts/stage2_discovery_protocol/blocks/blocks.parquet
artifacts/stage2_discovery_protocol/selected_pairs.json
results/stage2_discovery_transfer_confirm/report.json
results/stage2_discovery_latent_pilot/report.json
results/stage2_discovery_latent_definitive/report.json
results/stage2_discovery_joint_test/report.json
```

## Compute and storage guardrails

- Benchmark a two-organ, three-seed run before reserving the campaign.
- At the currently observed training speed, a matched condition with roughly 1,000
  samples and 15 epochs is expected to take about 2-3 A100 hours; remeasure this in
  the variance pilot rather than treating it as fixed.
- A two-organ, three-seed variance pilot is about nine models or 18-30 GPU-hours.
- The selected-pair default should require roughly 21-24 model runs including
  same-organ controls and three seeds, rather than 60-105+ for a full `K=5` grid.
- Expect roughly 45-95 GPU-hours for three selected pairs, depending on block size;
  benchmark the affinity screen separately.
- Start latent routing with a frozen trunk; full-cohort fine-tuning is at least three
  long runs and may require another 60-100 GPU-hours; it needs a separate go/no-go.
- Keep only checksum-verified best/last full checkpoints. Adapter/router-only
  checkpoints should be stored separately when the trunk is frozen.
- Strip verified inference weights from optimizer state: the current ~433 MB resume
  checkpoint should be about 152 MB as FP32 model weights alone. Twenty-four stripped
  transfer models are roughly 3.6 GB; 15 per-epoch resume checkpoints for each would
  be roughly 156 GB and are infeasible.
- Never launch a full transfer matrix merely because GPU capacity is idle.

## Final interpretation ladder

1. **No backbone health:** pipeline/model failure; stop.
2. **No oracle headroom:** no useful sample-dependent expert complementarity; stop MoE
   discovery.
3. **Organ experts equal random shards:** generic ensemble diversity, not biology.
4. **Known-organ works, blind gate fails:** expert signal exists; router problem.
5. **Label-free routes recover only organ:** known-axis validation, not discovery.
6. **Routes are stable but study/platform dominated:** technical confounding.
7. **Routes predict controlled transfer and route-derived groups improve learning:**
   functional representation result.
8. **A beyond-organ program additionally survives pathway, nuisance, and external
   replication tests:** biological-discovery result.
