# Stage 1 K4 final refit: decision history and confirmation design

Status: **development nomination complete; final refit running on `moe-reboot`
after a passed real-data smoke; external confirmation not yet started.**

This document records why the project arrived at a four-specialist model, what the
completed experiments do and do not establish, and the contract for fitting one final
K4 candidate before a genuinely untouched external confirmation. It does not authorize
reuse of the old internal test, selection on an external lockbox, or a biological claim.

## Keep the three stages separate

| Stage | Data role | Purpose | Current status | Permitted conclusion |
|---|---|---|---|---|
| Development nomination | Frozen train plus calibration | Compare K5, genuine K4 equal-per-expert (K4-EPE), and a higher-exposure K4 sensitivity; nominate one candidate | Complete | K4-EPE is the development candidate |
| Final fitting | Train plus calibration only; old test excluded | Refit exactly one nominated K4 architecture and its matched controls, and freeze one deployable router | Running from exact commit `e8c0383`; preflight and smoke passed | Produces frozen weights and router; adds no confirmation evidence |
| External confirmation | A new, untouched, study-disjoint lockbox | Test the already-frozen K4 model once against pooled and matched controls | Blocked pending external data and a separately frozen protocol | May confirm or fail the K4 Stage 1 claim |

The completed K4/K5 experiment is adaptive to the same calibration cohort that
nominated K4. Its statistical success therefore supports an engineering choice, not an
independent confirmation. Combining train and calibration for the final fit likewise
creates a deployable frozen model; it is not another experiment and must not be reported
as one.

## How the project reached K4

### 1. The original fixed-average control failed

The first troubling result was real: a single global average of organ experts did not
beat a matched global average of random experts. In the later locked replication, the
legacy organ-fixed comparison remained slightly negative. This result must not be
deleted or relabeled as a software error.

It also does not answer the main MoE question. A fixed average applies every narrow
specialist to every sample, whereas a routed MoE conditionally applies one specialist.
The fixed-average result says that random experts are safer global generalists under
unconditional averaging. It does not show that correctly dispatched random experts are
better than correctly dispatched organ experts. Fixed averaging remains an important
diagnostic, but conditional routing is the relevant primary estimand.

### 2. The attempted alternative-axis screen did not replace organ identity

After the fixed-average disappointment, the project explicitly tested whether a
gradient/residual utility axis was a better partition than organ. That screen returned
`screen_fail`. Its hard-trained organ-K5 anchor was the only tested configuration that
cleared the practical development gates. This ruled out the tested discrete utility
axes; it did not prove that organ identity is the globally optimal representation.

The broader scientific position remains:

- organ identity is the strongest tested conditional split so far;
- the space of learned or continuous specialization axes is not exhausted; and
- organ identity must still beat pooled and random controls on new external data.

### 3. Locked K5 replication separated routing from averaging

The next protocol was frozen in
`artifacts/stage1_organ_k_confirmation/protocol.json`. It trained K5 organ banks and
three connected-study-preserving random K5 families at seeds 17, 42, and 101, froze a
target-hidden organ router, and evaluated an already-inspected but study-disjoint
internal test.

The result was directionally strong but formally failed its prespecified magnitude
gate:

- blind hard organ routing improved MSE versus pooled by **3.357%**;
- true-organ dispatch improved MSE versus pooled by **2.662%**;
- true-organ dispatch beat every study-preserving assigned-random K5 control, with the
  least-favorable relative gain **2.626%**; and
- the blind and true effects were seed-stable with positive clustered evidence.

The formal branch was `pooled_fail` because the true-organ and organ-versus-random
effects missed the frozen 3% magnitude threshold. This was a narrow threshold miss, not
a repeat of “random routed experts beat organ routed experts.” The cohort was also an
internal locked replication, not an independent external confirmation.

### 4. The calibration-only K search nominated K4

Track B reused the independently trained K5 bank and evaluated every nonempty subset of
the five specialists with strict nested, connected-study cross-fitting. Undeployed
organs fell back to the pooled model. Matched random families received the same subset
search budget.

K5 had the best numerical calibration MSE. The frozen one-standard-error rule nominated
K4 because it was the smallest eligible candidate within one standard error of K5:

- K4 specialists: **brain, liver, skeletal muscle, and skin**;
- pooled fallback: **adipose**;
- Track-B subset ID: **23**;
- K4 blind gain versus pooled: **2.721%**;
- K4 least-favorable gain versus matched random: **2.686%**;
- K5 blind gain versus pooled: **2.841%**; and
- K5 least-favorable gain versus matched random: **2.807%**.

This was a deployment ablation of K5-trained experts, not a genuine K4 training result.
It justified a separately frozen K4/K5 retraining experiment; it did not authorize
changing the final architecture by itself.

### 5. Genuine K4/K5 retraining selected K4-EPE

The genuine retraining protocol is
`artifacts/stage1_organ_k45_retraining/protocol.json`. It compared three arms:

1. `k5`: five specialists, 2,400 active exposures per expert, 1,500 updates;
2. `k4_epe`: four specialists, 2,400 active exposures per expert, 1,500 updates on the
   common five-organ schedule; and
3. `k4_total_active`: four specialists, 3,000 active exposures per expert, 1,875
   updates, matching K5's total active-adapter exposures as a sensitivity.

Each arm had three connected-study-preserving random controls. The pooled trunk was
frozen, all adapters were independent dimension-64 residual experts, and the common
K4/K5 semantic experts used identical initialization keys. The K4 fallback label was
`-1` for adipose. Training seeds were 17, 42, and 101.

The run completed on 2026-07-22 under the persistent result root
`/media/volume/moe-reboot/results/stage1_organ_k45_retraining_191192e`:

- preparation: 1,815 train and 842 calibration rows;
- all-12-axis, two-update smoke: complete, `mechanical_only=true`, no test access;
- full seeds 17, 42, and 101: complete, approximately 69.7 minutes each;
- calibration evaluation: complete at 2026-07-22 09:27:44 UTC;
- all technical gates: pass, including bitwise equality of the shared K5/K4-EPE
  experts; and
- old test features and targets: not loaded.

The completed evidence is:

| Arm | Blind gain vs pooled | True gain vs pooled | Least-favorable true gain vs random | Max exposure deviation | Holm-adjusted pooled p | K4 penalty vs K5 (upper 97.5%) |
|---|---:|---:|---:|---:|---:|---:|
| K4-EPE | 3.339% | 3.983% | 3.945% | 0.958% | 0.001999 | +0.184% (+0.299%) |
| K4 total-active | 3.629% | 4.324% | 4.284% | 0.733% | 0.001999 | -0.117% (+0.075%) |
| K5 | 3.516% | 4.166% | 4.136% | 0.917% | 0.001499 | reference |

Every arm passed the frozen blind-versus-pooled, true-versus-pooled,
true-versus-every-random, exposure, seed-stability, and multiplicity gates. Each of the
nine arm-by-random tests had Holm-adjusted p = 0.004498. K4-EPE's per-seed blind gains
were 3.669%, 3.170%, and 3.178%. Its 95% clustered interval for the mean absolute blind
improvement was `[0.011347, 0.038704]`.

Both K4 arms passed the 1% noninferiority margin against K5. K4-EPE's relative-MSE
penalty was 0.184%, with paired clustered interval `[0.098%, 0.299%]`; the simultaneous
one-sided upper bound was only 0.299%. K4 total-active was numerically slightly better
than K5, but it spent 25% more active exposure per specialist than K4-EPE.

The frozen branch was therefore `k4_robust`, and the candidate for a future freeze was
`k4_epe`. K4-EPE was selected because it passed every specialization gate, was safely
noninferior to K5, used one fewer expert, and achieved the result without the extra
exposure of the total-active sensitivity. It was not selected because it had the lowest
raw MSE; it did not.

## Completed K45 provenance and hash ledger

Code and launch provenance:

- implementation commit: `191192e`;
- workflow resume fix and recorded run commit: `baa1acf`;
- launch checkpoint commit: `94af531`;
- deployed code directory: `/home/exouser/nasa-rna-moe-191192e`;
- completed result root:
  `/media/volume/moe-reboot/results/stage1_organ_k45_retraining_191192e`;
- result size at completion: 44,755,772 bytes in 229 files; and
- current evidence label: development-only, adaptive to calibration, not independent
  confirmation.

Core hashes:

| Artifact | SHA256 |
|---|---|
| K45 protocol | `77dd4d780b2412b043f6f9c01778b043ca1b747fbf79836d82fbce7da791b079` |
| K45 train/cal partition manifest | `09c45edc5dd6389020495f8fd4718995cd82ee7828197a96c0fa44ef46e98bf2` |
| K45 partition report | `ec9cfd0855d01776ad7b92f68fa82c6286b0cd23ef88557807764dae21f16ed1` |
| K45 evaluation report | `4733d3eaab205d7421577d43460bf3b15a9a98803cdcaf8b040526c859049d1b` |
| K45 decision scores | `70ecb74de141a89fc885ef457c3cfda42dcde12596cdfa551037953cad77ae8b` |
| K45 evaluator source | `6dee00f8b9b7b468f967e26ea6bd4b6f2b27b4d7ea309977610a142299080cca` |
| Frozen target-hidden router | `92f28dd9b58e7f9e1fd12fa5b87b7ae7f41aff14c9a61c827f9f0b2bdd45e160` |
| Router report | `edb3ce457896789f225554025f55ad430bbea621f669de9dee0d7b2f6a81aed1` |
| Source expression | `148776bc2d5bbe4a969103de7abab932b7467c804934fc697366ae2c209c0821` |
| Source manifest | `bc4e8e4e36ab0e869fd885197842dc797edad5a08b8093beb21185dbeda7f9cc` |
| Frozen pooled checkpoint | `080a8a36d2090c3a823cd3995d758d1205b0ad02c1c38c06e6763c5a7ebfd789` |
| Score-axis definitions | `1d7fba55d00f3fe363932abfba2a0e0d76e70e8dedf71aa46c69e29679b0b7cb` |
| Prior Track-B report | `bf890073fdf055e79f0ef86a0351ae6ef43992d9b069a68d36a0bb528aa818bc` |

The selected K4-EPE checkpoint family is:

| Seed | Organ K4-EPE | Random p17 | Random p42 | Random p101 |
|---:|---|---|---|---|
| 17 | `27ccc7a831be86364406cf046e7e113c0e8b7bd84b16b637ddc2c6a3082bd35c` | `2a98676a8224085328d40cdf6898136d315e904d28e3fc5bc85ff231ac542895` | `398636c1f35ad84007c0ca098afcaf955f80c6df746ba736e70b4fd89812ffa0` | `9b27f15ebeb0e484c7181ce23e2accd8136337b30ea4e3ae467154283c84fe86` |
| 42 | `7cafc273810b9a09b9066a57deb9ea712b738e383c6159822366360f8d81d5ed` | `71f5a9570c93d06856b52f475601f724e174000458fb788423284c2291bf0777` | `d6200fe26c6ba6f3ad6d3b6ef7b3b105e5ef84cd96678b5de1748787592a47f4` | `6a646f802d666aa06e5277fad779d4b7964c37cc8064f436554e04af85523396` |
| 101 | `d6cb8cf74e5b6bdc4bd7708793e94b313a6b67695e59d7d0fc5c27e45dabd1c9` | `bd22aff628fdb0327471116c39333cf07edea02d4cbabb3c118de9c3a59f02bd` | `7d1d8f8e5b7708abf8a857caf0ceceee201d43a5b889b6a3c20fb73f3f6b3363` | `3473a69551e57803137380d206eaf72c76c01bccd00c99acf4dab2557a2cf068` |

These hashes describe the completed development artifacts. A final train+cal refit will
produce new checkpoint hashes and requires its own protocol, provenance record, and
verified backup. It must not silently inherit the table above as if the weights were
unchanged.

## Frozen design for the final train+cal-only refit

This section specifies the design that must be implemented and hash-frozen before the
refit starts. The machine-readable contract is frozen in
`artifacts/stage1_k4_final_refit/protocol.json`; it authorizes the pending refit but is
not a completed run or a new performance result.

### Candidate and population

Fit exactly one organ architecture: K4-EPE.

- active specialists: brain, liver, skeletal muscle, skin;
- adipose behavior: pooled fallback, encoded as label `-1`;
- tensor label order: `brain=0`, `liver=1`, `skeletal_muscle=2`, `skin=3`;
- no K5 candidate, K4 total-active sensitivity, subset search, or organ reselection;
  and
- no use of the old internal test for training, routing, diagnostics, checkpointing, or
  scoring.

The final fitting population is the union of the already frozen development train and
calibration rows in the K45 partition artifact. It contains 2,657 rows:

| Organ | Train | Calibration | Final development union |
|---|---:|---:|---:|
| Adipose | 363 | 136 | 499 |
| Brain | 363 | 242 | 605 |
| Liver | 363 | 85 | 448 |
| Skeletal muscle | 363 | 184 | 547 |
| Skin | 363 | 195 | 558 |
| **Total** | **1,815** | **842** | **2,657** |

No result may be chosen on this union after fitting. Training diagnostics are health
checks only, because every row is now part of model fitting.

### Physically separate runtime data firewall

A prelaunch adversarial audit caught an important provenance distinction: selecting
only development IDs in Python was mathematically sufficient, but the original loader
still opened the historical combined train/calibration/test manifest and could read
mixed Parquet row groups. No old-test row reached a model, but the stronger statement
“old-test features were never loaded” was not yet warranted. Launch was stopped before
GPU training and the runtime inputs were hardened.

The authoritative expression is now a separate direct extraction from ARCHS4 H5 using
only the frozen K45 train+calibration manifest. The combined 5,017-row expression and
manifest are forbidden runtime inputs. The development-only artifact is stored at
`/media/volume/moe-reboot/results/stage1_k4_final_refit_development_data_v1` and has:

- 2,657 expression rows, 15,448 canonical genes, and only train/calibration roles;
- expression SHA256
  `74ee6438a32bf62c0227af4a3e73f853697b95e8bea80d844cabd67f261c7df0`;
- extraction-report SHA256
  `5537ff8964415e547962be20ae0dec34171863dffe926fed7b8f6a83ad2a4415`;
- extracted-manifest SHA256
  `3544f37112de62d67f8f844042e61e4029c01df178ab4412ff26d887c3711a58`;
- firewall-report SHA256
  `d26edcbc9cdee9c809c0a56e999bc7ebd7a6b473855cd3741df2d6c9d77cca36`;
- verified relative checksum-manifest SHA256
  `5bcd0c2973aecd7ac1ab119cddf37fd35b674b7a1c4f68b366449260c10c1ee2`;
  and
- VM-generated runtime partition-manifest SHA256
  `c6173aa4c7d5e8d62923a046c521a45a6e734f5f83017003b68f4afeb06261ba`.

The worker and router hash-check these artifacts, never receive the combined manifest
path, and record both `test_accessed=false` and
`external_data_accessed=false`. The final protocol was refrozen after this repair;
its SHA256 is
`718f4a876ba641e53aaff3ad75db8c70c727db0a086477b13c17487672cbb85b`.

### Architecture and optimization

The refit retains the architecture that earned the nomination:

- frozen pooled trunk at update 7,350, SHA256
  `080a8a36d2090c3a823cd3995d758d1205b0ad02c1c38c06e6763c5a7ebfd789`;
- four independent dimension-64 residual adapters;
- hard assigned-expert reconstruction loss during training;
- no trainable router in the expert-fitting graph;
- `log1p(TPM)` inputs, 30% masking, mask token `-10`;
- batch size 8 and validation/inference batch size 8 where applicable;
- AdamW, learning rate 0.001, weight decay 0.01;
- cosine annealing over exactly 1,500 updates;
- AMP on the A100;
- training seeds 17, 42, and 101; and
- semantic initialization keys
  `organ:brain`, `organ:liver`, `organ:skeletal_muscle`, and `organ:skin`.

All residual adapters are initialized from scratch using stable semantic keys. The
frozen trunk is reused, but no K45 adapter is warm-started. This prevents the final fit
from inheriting a seed-specific checkpoint-selection path that was not part of the
final-refit contract.

### Exposure schedule

The final union is not organ-balanced. The final refit must therefore freeze an
explicit deterministic organ-balanced schedule rather than silently apply the old
natural sampler to the imbalanced union.

For each training seed:

1. draw exactly 12,000 rows over 1,500 batches of 8;
2. allocate exactly 2,400 scheduled draws to each of the five organ roles;
3. send brain, liver, skeletal-muscle, and skin rows to their named specialist;
4. send adipose rows to the pooled fallback and give them zero adapter loss;
5. divide active-row loss by the common full batch size, preserving the K4-EPE
   efficiency interpretation; and
6. use the same row order, masks, and trunk activations for the organ, all matched
   random banks, and the pooled residual control within a seed.

The four active organ experts therefore receive 2,400 target exposures each. The
adipose role receives 2,400 scheduled fallback draws. Realized expert exposure must be
exact under the balanced schedule; if the implementation permits small deviations,
the existing 5% maximum remains a fail-fast technical gate, not a tuning target.

The cycle must expose every one of the 2,657 fitting rows at least once. Each seed emits
`fit_schedule.parquet` with all 12,000 ordered draws, update/batch positions, sample and
study IDs, organ, and the exact per-draw 64-bit mask seed. The per-sample exposure
ledger, schedule, and report are cross-hashed by seed metadata and copied into the
portable final candidate before external access.

### Matched controls

Refit three connected-study-preserving random K4 controls at partition seeds 17, 42,
and 101. Copy the exact K45 K4-EPE train and calibration row labels into the final
manifest under `random_group_k4_final_p17`, `random_group_k4_final_p42`, and
`random_group_k4_final_p101`. Merge the two fitting roles without repartitioning,
rebalancing, or relabeling them. Validate the source partition/report/evaluation
hashes, adipose `-1` fallback, active labels 0 through 3, and connected-study
atomicity.

For every control:

- adipose remains pooled fallback `-1`;
- the four active-organ rows map to random labels 0 through 3;
- an entire connected study remains in one random shard;
- the architecture, adapter dimension, initialization policy, optimizer, 1,500-update
  schedule, row order, masks, and 2,400-per-specialist target match the organ arm;
- all three partitions are retained; none may be selected or dropped; and
- assigned-random dispatch is the conservative true-label specialization control. No
  nuisance random router may be tuned to external outcomes.

Also fit one pooled residual control per training seed: a single dimension-64 residual
adapter applied to every row, with label 0 for all 2,657 rows and no router or fallback.
It uses the same 1,500-update stream and receives all 12,000 active exposures. This
tests whether K4's gain needs conditional specialization or merely an extra trainable
residual layer on top of the frozen trunk. The frozen pooled trunk remains the primary
baseline; the pooled residual adapter is an additional capacity/fine-tuning control.

The final fit therefore produces five banks per training seed: one organ K4-EPE bank,
random p17, p42, and p101 banks, and one pooled residual-adapter bank.

Before final refitting, freeze a separate deployment mapping for each random partition
using only the completed K45 held-out calibration `expert_mse` arrays:

1. for each active organ and expert, average sample MSE across training seeds;
2. average samples within connected study;
3. equal-weight connected studies within that organ;
4. choose the minimum-MSE expert, breaking an exact tie by lowest expert index; and
5. map adipose to pooled fallback.

This operation selects an organ-to-expert interpretation for already-frozen random
partitions; it does not create or alter a row assignment. Freeze the source hashes,
aggregation outputs, chosen indices, and tie rule before the final fit. On external
blind evaluation, route as final-router predicted organ to frozen random mapping to
the corresponding final-refit random expert. On true-label evaluation, retain the
original assigned-random comparison. Neither mapping may be recomputed from merged
in-sample losses or external outcomes.

### Router

After the expert refit, fit one deployable target-hidden organ router using development
rows only. It must be frozen before any external expression is loaded.

The router contract is:

- features: observed `log1p(TPM)` expression with all 4,634 score genes replaced by
  mask token `-10` for every sample;
- labels/classes, in canonical order: adipose, brain, liver, skeletal muscle, skin;
- pipeline: `StandardScaler` followed by balanced multinomial logistic regression;
- logistic-regression parameters: `C=1.0`, solver `lbfgs`, `max_iter=2000`;
- class weights: balanced, with sample weights giving equal connected-study mass
  within each class;
- random seed: 271828;
- fit population: the complete 2,657-row train+cal development union;
- K4 dispatch: predictions for brain, liver, skeletal muscle, and skin select the
  matching expert; an adipose prediction selects pooled fallback; and
- no external fit, calibration, normalization update, threshold tuning, or transductive
  use of lockbox features.

Serialize and hash scaler statistics, coefficients, intercepts, class order, training
sample IDs, gene order, hidden-score-gene indices, and the exact source/config. A
cross-fitted development router may be reported as a nonselective diagnostic, but the
full-development router is the single deployment artifact.

### Checkpoint policy

The only authoritative expert checkpoint is the predetermined final state after update
1,500. There is no validation split after train+cal unioning, no early stopping, no
best-loss selection, and no external-loss checkpoint selection.

Do not select a best training seed, average model weights across seeds, or report
in-sample development efficacy as if it were validation. Preserve all three frozen
seed checkpoints. A future external evaluator averages the prespecified seed-level
losses per sample; it does not tune seed weights.

Periodic recovery snapshots are allowed for operational recovery, but they must be
labeled nonselective and may only resume toward the same update-1,500 endpoint. They
cannot become candidate checkpoints. Each final bank must record:

- protocol and code commit;
- pooled-trunk, expression, manifest, partition, score-axis, schedule, and mask hashes;
- training seed, semantic expert keys, update count, and exposure counts;
- `test_accessed=false` and `external_data_accessed=false`;
- final expert-state hashes; and
- a `COMPLETE` marker written only after artifact validation.

The claimed code commit must equal the full 40-character `git rev-parse HEAD` of a
clean tracked checkout; a caller-supplied hash string is not accepted as provenance.

## The old internal test is permanently excluded

The existing 1,018-sample test is study-disjoint from train/calibration, but its effects
were inspected in earlier Stage 1 work. It is no longer an untouched test and cannot be
used to confirm the final K4 model.

The final-refit pipeline must fail closed if it sees:

- the old test split name;
- an old test sample ID or connected group;
- the sealed old-test assignment artifact;
- an old test score cache;
- a manifest containing anything other than the frozen train and calibration roles;
  or
- an attempt to produce a “final” metric from the development union.

The old test may remain preserved for reproducibility of historical reports. It may not
be used for smoke testing, hyperparameter checks, router fitting, checkpoint selection,
threshold revision, or a K4-versus-K5 rescue analysis.

## Final-refit launch record

The audited implementation was committed and pushed as
`e8c0383fd1833f180f26af56f09e83a5b3f676d9`. It was transferred as a complete Git
bundle and cloned into a new clean detached checkout at
`/home/exouser/nasa-rna-moe-e8c0383`; the VM's older modified checkout was not used or
changed. The persistent result root is
`/media/volume/moe-reboot/results/stage1_k4_final_refit_e8c0383`, and the workflow runs
inside tmux session `stage1_k4_final_e8c0383`.

VM preflight and preparation passed. The real-data seed-17 smoke completed at
2026-07-22 20:27:59 UTC for all five banks after exactly two updates per bank. Its
contract check verified finite tensors, final-checkpoint round trips, the full frozen
axis order, `mechanical_only=true`, `internal_efficacy_scoring=false`, and both
`test_accessed=false` and `external_data_accessed=false`. The full 1,500-update refit
then started with seed 17 at 20:28:02 UTC; seeds 42 and 101, router refit, portable
candidate freeze, and a full checksum pass follow automatically. No efficacy estimate
is produced or inspected by this workflow.

## Future external-lockbox firewall

External confirmation requires a new protocol frozen after final fitting and before the
first lockbox feature or target is inspected. No external lockbox is currently present
in the repository or on the central persistent VM.

### Required external artifact contract

Before access, freeze and hash:

- the external source and version;
- extraction code and report;
- exact sample IDs and their order;
- organ labels and mapping rules;
- study, donor, and connected-group IDs;
- the 15,448-gene order and normalization contract;
- overlap audits against all historical train, calibration, and test IDs/groups;
- the external random-control group assignments for all three partition seeds;
- the deterministic score mask; and
- the final refit checkpoint and router hashes.

The lockbox must contain all five organs, at least five connected studies per organ,
and preferably at least eight. Adipose remains part of the estimand even though it uses
pooled fallback. Independence checks must cover accession, publication, BioProject,
biosample, donor, sample, connected group, and near-duplicate expression. A
single-study resource such as GTEx can provide external-domain and donor-level evidence,
but it cannot by itself meet this multisource confirmation design or establish broad
cross-study generalization.

Do not use final-lockbox rows for software smoke. Use synthetic data, historical
development rows, or a staging subset that was permanently excluded before the lockbox
was frozen.

### Final estimands and gates

The primary external estimand first averages the three prespecified seed-level losses
for each sample, then gives equal mass to connected studies within organ and equal mass
to organs. It compares blind hard K4 routing with the frozen pooled trunk. Supporting
conditional-specialization estimands compare true-organ K4 with adipose fallback
against pooled and each assigned-random K4 control. Deployment controls compare blind
K4 with the calibration-frozen mapped-random controls and the pooled residual adapter.

Freeze the existing practical gates unless a prospective power analysis completed
without lockbox access requires a change:

- blind K4 relative-MSE gain versus pooled at least 3%;
- true-organ K4 relative-MSE gain versus pooled at least 3%;
- true-organ K4 relative-MSE gain versus every random partition at least 3%;
- blind K4 gain versus every mapped-random control greater than zero with a positive
  connected-group-clustered interval and Holm-adjusted p no greater than 0.05;
- blind K4 improvement versus the pooled residual adapter with a positive
  connected-group-clustered interval;
- positive connected-group-clustered interval for each gating comparison;
- positive residual-Pearson interval for pooled comparisons;
- blind-router recovery of at least 80% of the true-dispatch gain;
- same positive sign at seeds 17, 42, and 101;
- seed SD no more than half the mean effect;
- nonnegative true-dispatch point effect for every active organ;
- all provenance, overlap, target-hiding, exposure, and artifact-alignment checks; and
- multiplicity control across the three random partitions as frozen in the external
  protocol.

Report natural-frequency estimates, per-organ effects, fixed averaging, oracle
headroom, and router confusion as diagnostics. They do not replace the primary balanced
estimand or rescue a failed gate.

### External decision branches

The external protocol must encode exact precedence and mutually exclusive conditions
for the following frozen branch vocabulary; a favorable secondary result cannot
override a failed primary or technical gate:

1. `technical_fail`: any provenance, independence, alignment, score-hiding, cache,
   exposure, or execution gate fails. Repair without interpreting an effect.
2. `no_external_gain`: K4 does not establish the prespecified pooled improvement. Do
   not proceed with the organ MoE claim.
3. `generic_capacity_or_partition_fail`: the apparent benefit does not survive the
   pooled-residual or matched random controls. Conditional organ identity is not
   externally supported as the useful specialization axis.
4. `router_bottleneck`: true-organ dispatch clears its pooled and random gates, but
   blind routing or recovery fails. Conditional specialization exists, but deployable
   observed-input routing remains the bottleneck.
5. `full_external_pass`: blind routing, true dispatch, mapped and assigned random
   controls, the pooled-residual control, per-organ safety, stability, and every
   technical gate pass. K4-EPE becomes the externally supported Stage 1 architecture.
6. `inconclusive`: a prespecified residual pattern not covered by the directional
   branches above. Preserve the failure transparently; do not improvise a rescue on
   the same lockbox.

K5 and K4 total-active are not rescue candidates in this lockbox. If K4-EPE fails, do
not inspect K5 and switch architectures on the same external data. A different candidate
would require a newly frozen development decision and a new untouched confirmation
cohort.

No branch automatically authorizes Stage 2 biological claims. Stage 2 hypotheses and
lockboxes retain their own firewalls.

## Operational cautions and recovery

- The completed K45 result is on persistent central storage and code is pushed, but a
  portable `FULL_SHA256SUMS` plus independent local backup should be verified before
  final refitting begins.
- Use a new result root keyed by the final code/protocol hash. Never rerun or append to
  the completed K45 root.
- Long work runs inside a named `tmux` session. All outputs, logs, status files, and
  recovery snapshots belong on persistent storage, not `/dev/shm`.
- Preflight must verify exact hashes, available disk, absence of stale processes/locks,
  and an empty output destination.
- A real-data, two-update smoke uses a separate output root, seed 17, all five banks,
  and development rows only. It must finish with the organ, three random, and pooled
  residual bank markers, `mechanical_only=true`, finite diagnostics, correct K4
  fallback `-1`, and no old-test or external access.
- Required phase markers should distinguish protocol freeze, final-input freeze,
  preflight, smoke, refit, router freeze, external-input freeze, one-time score cache,
  evaluation, verified backup, and safe-to-shelve state.
- The completed K45 workflow is not fully idempotent after evaluation; rerunning it can
  encounter the nonempty evaluation output. Final orchestration must short-circuit only
  after hash-validating completed markers.
- On an interrupted fit, first confirm that no `tmux` pane or process remains. Quarantine
  the incomplete seed directory with a UTC suffix; do not overwrite it. Remove a stale
  lock only after that process audit, then resume from a validated recovery snapshot or
  rerun the exact frozen seed.
- External cache and report writes must use a temporary destination and atomic rename.
  Once a score cache is complete and hash-verified, evaluation may be rerun from that
  cache without reopening raw lockbox data.
- A purely technical rerun using identical frozen code is permissible if documented.
  Any change to the model, router, protocol, assignment rule, threshold, or population
  after inspecting an external effect requires a new untouched cohort.
- After final fitting and again after external evaluation, generate a relative-path
  SHA256 manifest, verify it centrally and locally, record its own hash, and only then
  write a shelf-safe marker.

Compute availability and persistent free space must be rechecked at launch; they are
operational constraints rather than scientific evidence. The scientific bottleneck is
freezing and acquiring a valid external lockbox without contaminating it.
