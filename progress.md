# NASA RNA MoE: concise milestone chronology

**Last updated:** 2026-08-02 01:42 PDT / 2026-08-02 08:42 UTC

## 2026-08-02 — D2 fails; unconfounded cross-species organ transfer passes

Both overnight evaluations completed automatically and every immutable checksum
verifies locally and on the VM.

D2 returned `HALLMARK_FEATURES_FAIL`. Hallmark+PCA64 AUROC was 0.732630 versus
0.732770 for PCA64 and 0.725921 for raw. Its study-bootstrap interval crossed zero
against both references. It beat permuted Hallmark and all three matched-random sets,
but Hallmark alone scored only 0.567394. Deterministic Hallmark means therefore do not
add robust state-task value beyond PCA under the frozen design.

The GTEx-trained replacement D1b returned
`CROSS_SPECIES_ORGAN_STRUCTURE_PRESERVED`. Raw balanced accuracy was 0.9643; pooled
hidden reached 0.7519/0.7553/0.6992 across seeds 17/42/101, all above the frozen 0.60
gate. This unconfounded result shows that mouse embeddings retain substantial human
organ geometry. It is incomplete—heart recall is near zero, lung is seed-variable,
and raw expression remains much stronger—and it does not establish perturbation-state
retention. The original OSDR-trained D1b remains confounded and uninterpretable.

## 2026-08-01 — Encoder transfers; Hallmark downstream feature audit launched

The full D1 audit completed and all immutable checksums verify. Its frozen verdict is
`ENCODER_TRANSFERS_OBJECTIVE_LIMIT`, not cross-species encoder breakdown. Pooled hidden
remained in distribution against immutable GTEx caches in all seeds (effective-rank
ratios 0.865/0.793/0.764; median absolute mean z 0.258/0.411/0.450). On the class-
balanced cross-study brain-versus-skeletal-muscle positive control, raw expression
balanced accuracy was 1.000 and pooled hidden was 0.996 in all seeds. Ortholog coverage,
missing-input handling, and log1p value space also passed. The OSDR downstream failure
therefore remains a real limitation of this frozen output contract on the accessed
spaceflight-state task, not evidence that mouse input made the encoder meaningless.

D2 was implemented, tested, hash-frozen, and deployed. Protocol SHA256 is
`484667662935aed865d80a72503c428a68a6256f7c201beacaeb64f474632a62`; exact scientific
implementation commit is `f2700e846a17bf2f7dd3ef7f69eca597a32e6646`. The active
retry1 smoke automatically launches the full run only after checksum verification.
Its frozen primary asks whether Hallmark-50 adds study-robust value to fold-fit PCA64
and beats raw, PCA, three fixed matched-random controls, and permuted Hallmark. The
first launch emitted no outcome because the clean worktree lacked the ignored GMT;
the retry points to an existing byte-identical, hash-verified GMT.

### Post-run D1b correction

Claude's review of the emitted organ-by-study table found complete aliasing for the
executed brain-versus-skeletal-muscle control: no study contains both labels. The
numeric balanced accuracies remain correct but cannot distinguish organ biology from
study identity. D1b is therefore reclassified as `D1B_CONFOUNDED_UNINFORMATIVE`, and
the claim that it demonstrated organ recovery is withdrawn. D1a is now described as
"mildly compressed, not degenerate"; D1c still closes the mapping and normalization
failure hypotheses.

A replacement was implemented and frozen before its outcomes. It fits seven-organ
classifiers only on human GTEx donor-grouped data, then applies them unchanged to OSDR
raw expression and each fixed-seed pooled-hidden representation. Protocol SHA256 is
`c7309e52e3e291c71198e8c291caba2ea9b4c3bb000b904a2b00da3a6527c54a`; implementation
commit is `cdf32079561e7d6d56171f1d50fed5fe7b459640`. The prespecified gates require all
embedding seeds to reach balanced accuracy 0.60 for preserved structure; 0.25 or less
is the loss boundary. OSDR is never used for fitting or tuning.

Exact deployed continuation commit is
`dbcabec18402b411e23e1511859ece4b04c8d713`. At 23:42 PDT, the D2 smoke had passed,
the full D2 process was healthy at 154% CPU with 109 GiB memory available, and the
replacement audit was waiting in a detached screen. It will start automatically only
after D2 completion and checksum verification. A two-hour heartbeat is active through
the 08:00 PDT result handoff.

## 2026-08-01 — OSDR encoder-validity audit frozen and running

Claude's review identified a missing positive control: the human-trained encoder
could be out of distribution on mouse ortholog-mapped input, which would make the
OSDR result a cross-species boundary rather than evidence of a general objective
mismatch. The read-only D1 audit now compares pooled hidden distributions against
immutable GTEx caches, tests cross-study brain-versus-skeletal-muscle recovery, and
audits ortholog coverage, missing-input policy, and normalization.

The corrected protocol SHA256 is
`e959ef694a83d2b8b2df6f50d20101ea467967bb30d6c1120b3fac44983b819f`;
exact deployed commit is `5b1bc12282ad6edb8df71b068c311ca09ff62b02`.
The first lineage emitted no outcome because of a direct-import defect and is
preserved. Its import-only replacement passed focused checks and is running a smoke;
a detached fail-closed continuation will launch the full audit only after smoke
checksums pass. No frozen model or scientific threshold changed.

## 2026-07-31 — Explicit organ embedding fails downstream gate; final package frozen

The repaired three-seed embedding extraction and full study-grouped OSDR evaluation
completed at 09:09 PDT. All caches, predictions, reports, and the VM checksum manifest
verify locally. Raw expression AUROC was 0.726 and PCA-64 was 0.733. Pooled-hidden
AUROC was 0.525/0.547/0.607; blind hard was 0.531/0.561/0.533; blind soft was
0.557/0.566/0.507 across seeds 17/42/101. No deployable embedding beat pooled hidden,
raw, and PCA in every seed, so the frozen downstream-positive gate failed without
seed or condition selection.

The final K8 package protocol is now frozen at SHA256
`7243f5345ae6fc2b522905d139ec82036f7854c1dd167e33f64814d8ca495500`.
It packages all three exact externally validated pooled trunks and organ banks plus
the frozen router, with no refit, fine-tuning, efficacy scoring, ARCHS4 access, or
OSDR access. A new train-plus-calibration refit is rejected because it would lose the
current external-weight validation and require changing the fixed exposure budget to
cover the 3,030-row brain union. Hidden and bottleneck outputs remain diagnostic;
raw/PCA remain mandatory downstream gates.

Exact packaging commit `dc562cc97d3936c642467a5be563e9bd7e31fc7b`
completed the immutable 441 MiB package at 09:41 PDT. All 17 packaged artifacts,
checkpoint loads, tensor-finiteness assertions, and checksum entries verify.
Manifest SHA256 is
`8c8e967faa7d63fda80bdb4c301678544290cbeb01f833ae7e6817be6a60e4e9`.
No training, efficacy scoring, ARCHS4/OSDR access, or seed selection occurred.

## 2026-07-31 — Tissue-site Tier 2 fails matched capacity; architecture closed

The frozen three-seed protected tissue-site adapter smoke completed and all compact
artifacts verify. Soft site beat the protected base by 70.70%, 70.56%, and 70.50%,
and beat the within-organ shuffled-site control by 0.149%, 0.199%, and 0.128%.

The parameter-matched generic adapter nevertheless beat soft site in every seed;
soft-site relative effects were −0.461%, −0.534%, and −0.544%, with bootstrap
intervals entirely below zero. The same frozen gates failed in all seeds. The final
architecture is therefore closed exactly as prespecified: validated K8 organ MoE
plus pooled fallback/reference, no tissue-site or Hallmark secondary axis, no
threshold changes, and no seed selection.

Compact evidence is under
`artifacts/stage2_organ_expert_mechanism/tissue_site_tier2_d47ac36/`; aggregate
report SHA256 is
`130d8ab775777a5e4a3d0a31513d3fb6c330add9452fb30c1a6fa73999f0d921`.
The next frozen development protocol exposes pooled hidden state plus the
selected/router-weighted organ bottleneck and router probabilities, and tests this
explicit output in the existing study-grouped OSDR development harness with raw/PCA
mandatory gates. It cannot serve as final confirmation.

The initial implementation lineage at commit `bc3502a` failed before emitting a
feature cache because NumPy router probabilities were FP64 and checkpoint features
were FP32. It is preserved and has no scientific result. A dtype-only correction
leaves the frozen protocol unchanged and adds a direct mixed-dtype assertion. Five
focused assertions and compilation passed at exact commit
`3f681fdbe818d2f49b03f097f08a5f171b4e35c8`. The repaired three-seed extraction,
then smoke and full study-grouped evaluation, launched at 08:15 PDT in screen
`final-organ-embedding-retry1`, result root
`/media/volume/moe-reboot/results/final_organ_embedding_3f681fd`.

## 2026-07-31 — Protected tissue-site Tier-2 smoke frozen and launched

The sole authorized Tier-1 candidate has entered the bounded neural smoke. The
hash-frozen protocol preserves the valid organ-private prediction and fixed decoder,
then tests a small input-only tissue-site residual bank against three references:
the protected base, a within-organ shuffled-site bank, and a parameter-matched
generic residual head. Five donor-grouped folds, all seeds, donor bootstrap,
per-organ safety, and router noncollapse are fixed before outcome access.

Protocol SHA256 is
`d922c1997389aacdc09c032415f0dc8a57ee579530f67f7f539477490eaac410`;
exact clean commit is `d47ac36f11647d3bcd6bd6d3aa3c2dffefc10378`. Nine
focused assertions pass locally and in the VM environment. Sequential seeds 17,
42, and 101 launched at 07:42 PDT in screen `tissue-site-tier2`; seed 17 is
GPU-active. No calibration, ARCHS4, or OSDR outcome is used in this smoke.

## 2026-07-30 — Tissue site alone clears the full multiaxis Tier-1 gate

All three immutable training reports and the OSDR development probe are complete.
Tissue site is the only candidate that passes coverage, organ-plus-nuisance
incremental utility, all three outcomes in all seeds, within-organ permutation,
donor bootstrap, technical-proxy, per-organ safety, and the separately measured
OSDR point-direction gate. Primary incremental R² was 0.2837, 0.2715, and 0.2739
for seeds 17, 42, and 101.

Hallmark-50 had the largest aggregate signal (mean primary incremental R² 0.5233)
and OSDR delta (+0.1013), but failed the frozen safety limit through
skeletal-muscle harm of −0.0568 and −0.0396 in seeds 42 and 101. Age failed the
bootstrap gate in two seeds; sex failed it in all three. No threshold or seed was
selected. Only tissue site advances to the bounded Tier-2 protected-adapter
smoke. Canonical result:
[`docs/multiaxis-tier1-result.md`](docs/multiaxis-tier1-result.md).

## 2026-07-30 — OSDR Tier-1 axis probe complete; seed-42 training retry active

The separately frozen OSDR development probe completed on the exact
292-sample/18-study no-replacement cohort. Protocol SHA256 is
`531438c0361501954a7eee1a49c9ea97ba53e67d339db53a13bd8c426a4198fd`;
exact evaluator commit is `b99d5b6a78e2f0522afdba7034230d7356b50ded`.
The organ-only base AUROC was 0.496. Candidate deltas were +0.0068 for age,
+0.0071 for sex, +0.0045 for tissue site, and +0.1013 for Hallmark-50. Only
Hallmark-50 had a positive study-bootstrap interval (+0.0267 to +0.2049);
age has 75 explicit missing rows. The frozen formal gate is a positive point
delta, so all four pass this one gate, but none can advance without independently
passing every all-seed training gate.

Seeds 17 and 101 completed the training-only Tier-1 screen with immutable
reports. The concurrent seed-42 process was killed with exit 137 from aggregate
memory pressure before writing a report. Its failed lineage is preserved, and
the exact same commit, protocol, cache, and seed were relaunched alone in
`tier1-seed42-retry1`; no scientific setting changed.

## 2026-07-30 — Frozen Tier-1 multiaxis screen launched on all three seeds

The common training-only Tier-1 implementation is frozen and deployed. It tests
exact tissue site, official GTEx v8 sex code and age bracket, and the 50
MSigDB 2026.1.Hs Hallmark programs against the same organ-plus-technical-nuisance
base. The protocol requires donor-grouped nested ridge evaluation, all three fixed
seeds, 100 within-organ permutations, 2,000 donor bootstraps, coverage,
technical-proxy partial correlations, per-organ safety, and a separate OSDR
downstream-label probe. Cell composition remains excluded.

Protocol SHA256 is
`cd1d3dab63689cd3d534533f37e48f5d0c05e4a7d9f407ec57ee0b49c6c5e4f1`.
The exact corrected execution commit is
`9de77e040f3b69421b65ed6d780a007e9256501e`. Two implementation-only smoke
lineages are preserved: the first exposed a missing sample-index assignment and
the second preceded a coverage-join correction; neither opened Tier-1 efficacy
outcomes.

A 128-row feature smoke and then the complete 7,369-row/750-donor feature and
coverage smoke passed before efficacy access. All four candidates clear their
frozen availability gate; every Hallmark set retains at least 19 visible
non-score genes. At 22:35 PDT, seeds 17, 42, and 101 launched concurrently in
detached sessions `tier1-seed17`, `tier1-seed42`, and `tier1-seed101` under
`/media/volume/moe-reboot/results/multiaxis_tier1_9de77e0`. All three processes
were healthy and CPU-active at the initial check.

## 2026-07-30 — OSDR downstream harness complete; Stage 1 output contract fails the downstream gate

The corrected converged evaluator completed at 21:26 PDT using exact commit
`61766ee`. All three frozen Stage 1 feature caches, the 292-sample/18-study
no-replacement cohort, five study-grouped outer folds, three training-study inner
folds, and the fixed 12-point elastic-net grid verified. Compact reports and
out-of-fold predictions were retrieved locally with matching SHA256 values.

The prespecified all-seed gate failed. True-organ minus same-seed pooled AUROC was
−0.051, −0.003, and +0.018 for seeds 17, 42, and 101. Hard-router deltas were
−0.046, +0.015, and −0.016; soft-router deltas were −0.028, approximately zero,
and −0.003. Mean learned AUROC ranged from 0.590 to 0.605, while raw expression
reached 0.726 and fold-fit PCA-64 reached 0.733.

This is a useful negative result: external reconstruction specialization remains
validated, but masked score-panel predictions are not a competitive frozen
representation for mouse spaceflight-versus-ground classification. Raw expression
and PCA are now mandatory final gates. No seed or condition is selected from this
cohort. Canonical result:
[`docs/stage1-osdr-downstream-result.md`](docs/stage1-osdr-downstream-result.md).

## 2026-07-30 — Frozen OSDR downstream run active on the A100

The versioned NASA download and 14,000-gene QC retained 297/892 requested rows.
After removing study-organ units that lost either flight or ground during QC,
292 samples from 18 studies remain; no replacements were added.

The first feature-cache attempt stopped before model outcomes on a coverage-order
assertion: it compared the 292-row contrast subset directly with the complete
297-row coverage artifact. The failed lineage is preserved. Commit `18f408c`
validates the full order first and then applies explicit positions; its frozen
execution-v2 manifest SHA256 is
`7bfc1b08457d1d0e6ff3fec6266a276516fc9a2c5fee7bfc1e38860184549b2b`.
Screen `stage1-osdr-continuation-18f408c` is using the primary A100 to cache seeds
17/42/101, then automatically runs the grouped smoke and full evaluator.

## 2026-07-30 — Downstream harness moved onto the critical path

The completed Stage 2B B0–B4 evaluation did not authorize Phase C. Cross-seed
grouped probes were strong, but the target coordinates did not separate sufficiently
from the random-basis control. Tissue site exceeded organ on both residual targets
in every seed and therefore triggered the frozen human-review pause; it remains a
candidate pending within-organ permutations, nuisance controls, coverage, and a
downstream-label probe.

Claude's schedule critique was accepted. Downstream evaluation now starts against
the immutable Stage 1 checkpoint family rather than waiting until the final week.
The five-field audit found OSDR spaceflight to be the first executable task:
892 exact flight/ground metadata rows, 43 studies, 45 study-organ units, and all
eight target organs. The 43 required matrices are not yet cached locally, but the
validated NASA downloader/preprocessor exists.

The exact OSDR candidate and readiness report are under
`artifacts/final_evaluation/downstream_readiness/`. The development protocol was
frozen before download at SHA256
`04e8354b1417c2f4bb4459f053a4e343dce1e65a9b552e16f7fea08c52d8abb9`.
It fixes no-replacement QC, study-grouped evaluation, all three Stage 1 seeds, and
equal elastic-net tuning for raw expression, PCA, pooled, true-organ, and blind
routing representations.

ARCHS4 free-text disease labels and TCGA are cut from the core until their five
readiness fields are satisfied. Cell composition, matched-data BulkRNABert,
BulkFormer-37M retraining, survival, and drug response are also cut from this
calendar. Hallmark-50 programs, tissue site, and demographics remain the bounded
axis screen.

## 2026-07-30 — Three Stage 2B caches complete; evaluator launched immediately

Seeds 17, 42, and 101 each completed 7,369 canonical training rows with bitwise
determinism and valid immutable manifests. Seed 42 completed at 15:18:25 PDT.
The independent seed-101 cache was transferred through a verified local relay into
the distinct primary `seed101_secondary` lineage without overwriting another run.

Operational commit `010d629be5b273618efa8183c54209f3a173d203` adds a fail-closed
detached continuation. Screen `stage2b-to-multiaxis-010d629` verified all three
caches and launched the frozen B0–B4 evaluator at 15:19 PDT using exact scientific
commit `20d000e0b8055f60d7dee8796b52834bd829ab43`. It preserves the already complete
B5 result. When evaluation finishes, it verifies checksums and immediately creates
the training-only multiaxis Tier-0 inventory.

The existing heartbeat was tightened from two hours to 30 minutes and extended
through Tier-1 multiaxis screening and final architecture selection.

In parallel with B0–B4, the exact open-access GTEx v8 subject and sample annotations
were downloaded, hash-pinned, and joined by exact ID to all 7,369 training rows/750
donors. Age bracket and raw sex code have zero missingness; death Hardy scale is
0.46% missing. RIN and ischemic time are each 15.04% missing and remain technical
nuisance controls. This was a Tier-0 availability audit only; it did not open
residual efficacy. Compact verified artifact:
`artifacts/stage2_organ_expert_mechanism/multiaxis_metadata_d265073/`.

## 2026-07-30 — Critical path changed to close MoE by the weekend

The final presentation remains 2026-08-17. The immediate priority is now explicit:
finish Stage 2B, screen non-organ axes using cached training-donor residuals, close
the MoE architecture by 2026-08-02, and launch final training by 2026-08-07.
Downstream and SOTA evaluation is scheduled for 2026-08-10 through 2026-08-14.

The axis workflow is a screen-many/train-one funnel. Tissue site is already part of
Stage 2B B4. Available demographic metadata, frozen cell-composition scores, and
continuous biological-program scores will use one donor-grouped organ-conditional
probe. At most the strongest one or two axes receive short protected-adapter
smokes; at most one enters final training. Disease, treatment, hypoxia, and
spaceflight are primarily held-out downstream tasks, not axes selected on the same
final cohort.

The final baseline ladder now includes BulkRNABert as the closest public
masked-reconstruction architectural peer, with its architecture retrained on the
exact project split to avoid unknown GTEx overlap. BulkFormer-37M is an approximate
capacity comparator and published BulkFormer-147M is a practical SOTA ceiling.
Raw expression, PCA, matched pooled trunk, pooled-plus-organ-label, known-organ
experts, hard/soft routing, and pooled fallback remain mandatory.

Canonical schedule and protocol:
[`docs/axis-smoke-and-final-evaluation-roadmap.md`](docs/axis-smoke-and-final-evaluation-roadmap.md).

Start with [`docs/current-status.md`](docs/current-status.md). It is the canonical
operational handoff. This file retains only decision-relevant milestones; the
2,800-line pre-cleanup chronology remains recoverable from Git commit `2bc1bef`.

## 2026-07-30 — August 17 downstream and multi-axis evaluation added

The final presentation date is 2026-08-17. Mentor feedback correctly identifies
the next evidence gap: reconstruction improvement over this project's pooled model
does not by itself establish downstream value.

The final evaluation will compare frozen organ-MoE representations against raw
expression, PCA/NMF, the pooled trunk, matched-data BulkRNABert, and published
BulkFormer-147M under identical patient/donor/study-disjoint splits and matched
downstream heads. Primary tasks will test disease/state, spaceflight/stress, or
low-resource adaptation rather than organ prediction, which would be circular.

The plan also broadens candidate expert axes without abandoning the validated organ
experts. Tissue site, cell-type composition, disease/physiological state,
age/development, sex, and continuous pathway programs will be screened for
incremental residual value beyond organ. Technical variables remain nuisance
controls. The preferred architecture is factorized: protected organ experts plus
separately gated site/condition/pathway residual adapters.

Canonical roadmap:
[`docs/august-17-downstream-and-multiaxis-plan.md`](docs/august-17-downstream-and-multiaxis-plan.md).

## 2026-07-30 — Frozen Stage 2B diagnostics pass both smoke gates and start

The complete training-only B0–B5 implementation is commit
`20d000e0b8055f60d7dee8796b52834bd829ab43`. Its protocol was frozen before
opening outputs at SHA256
`db7cd772345272876cd01a603deb720b46c36d0cfb5252e3d245e7e58f5182be`.
It permits no calibration or ARCHS4 access and no neural checkpoint updates.

The frozen three-trunk ridge probe selected one shared lambda of zero by held-out
gene-space reconstruction error. A 16-sample seed-17 cache smoke then passed
bitwise repeated extraction and all immutable checksums on the primary A100. The
same exact smoke on the secondary A100 produced identical hashes for every
canonical and B1 output, clearing the cross-host determinism gate.

Full read-only extraction subsequently completed for all three seeds. The verified
independent seed-101 cache was transferred to the primary, and frozen B0–B4
evaluation launched immediately under a detached fail-closed continuation.
Candidate neural training remains blocked until the frozen Phase B decision is
recorded.

## 2026-07-30 — Stage 2B Phase A guards implemented and deployed

Claude's final implementation review was accepted without changing the settled
scientific plan. It adds exhaustive canonical-cache keys, fixed-batch determinism,
one gene-space-selected ridge value across trunks, a nonsaturated gate that must
move, explicit rank records, training-only normalization, and a cross-host smoke
before work is split.

Phase A commit `b4100a1efd0090064a1a079fe658d7f116526373` adds reusable
positive-learning-rate, exact optimizer-coverage, parameter-movement, and
phase-boundary tensor-hash guards. It also fixes the known second-phase failure by
constructing fresh optimizers and makes the full seed-by-organ condition matrix a
required evaluator output.

The local focused Stage 2 suite passed 38 Phase A tests, including deliberate
zero-LR, unchanged-module, incomplete-optimizer, and identical-hash failures plus
the valid terminal cosine-zero case. The commit was pushed and deployed to a clean
primary-VM worktree.

The seed-17 mechanical smoke completed at 2026-07-30 13:39 PDT. All 11 immutable
entries verify; both phases completed 2/2 updates; every declared module moved and
changed tensor hash; the GPU returned idle. No Stage 2B scientific result was
opened.

Phase B implementation then started with commit
`1990070c13601f5b94dba85868110e3591fc0c1a`. It makes incomplete or stale
canonical-cache keys fail closed and makes ambiguous bare rank scalars impossible.
The expanded Stage 2-focused suite passes 42 tests.

## 2026-07-30 — External Stage 2 critique reviewed and execution plan corrected

The methodological proposal in `CLAUDE.md` was reviewed against the actual Stage 2
trainer, evaluator, and immutable results. The useful core is adopted: fix the
zero-learning-rate phase-transition failure before another run, remove mask
dependence from both the shared input and coefficient target, make per-organ safety
and functional share/decline stability primary, and preserve a refusal rule as a
valid result if helpful sharing remains unstable.

The review also found material corrections. Donor-level rank is computed across
individual donor vectors, not eight organ means, and is not capped at seven; the
existing oracle reaches 8.05. The evaluator uses entropy effective rank, while the
proposal's derivation used participation ratio. Further, selecting only non-score
hidden states from a partial-mask forward pass would not be mask-invariant because
transformer hidden states share context. The next shared input must come from a
canonical full-score-mask forward pass.

The refusal analysis will not treat raw A750+B750 versus A1500 substitution harm as
pure pairwise incompatibility. It will model donor-specific excess effect relative
to matched random auxiliaries, use leave-one-organ-out validation, and retain the
eight additive edges as a small independent check.

The reviewed plan is
[`docs/stage2b-mask-consistent-sharing-plan.md`](docs/stage2b-mask-consistent-sharing-plan.md).
No scientific run has started. Harness repair and a frozen training-only diagnostic
are the blocking next steps; the diagnostic decision tree then fixes the candidate
basis/axis before VM execution.

Claude's round-2 response accepted the corrections and added a useful cross-trunk
oracle-transfer audit. Codex accepted it with bounded wording: cross-seed agreement
supports reproducible sample-associated structure, not intrinsic biology; the old
probe regression uses its exact immutable population, while the new scientific
analysis uses training donors only.

Planning is now closed. The three-trunk continuation gate is bidirectional, cache
round trips are mandatory before scientific interpretation, and the refusal audit
must report the fraction of edges it flags. The first candidate keeps the exact
expression-PCA decoder and valid private states so the mask fix is a clean causal
test; residual/pathway bases are deferred.

Both GPU hosts were verified idle. Primary `moe-reboot` has the complete repair
lineage; secondary `149.165.168.111` already has the expression table and all pooled
trunks and needs only the compact seed-101 private state plus frozen code/protocol.
The planned allocation is seeds 17/42 on primary and seed 101 on secondary.

## 2026-07-29 — Aligned shared/private program-head pivot launched

The user approved implementing the next architecture after the raw-transfer and
read-only representation branches failed to produce a general stable rule.

The implementation fixes the representation coordinates by construction: an
input-derived 32-value shared head decodes through the frozen GTEx-training
expression basis, while an organ-private residual branch protects specialization.
It includes shared-only, private-only, matched generic-capacity, random-basis, and
donor-balanced random-label controls. All six conditions share the same fitting
schedule and masks within seed.

The protocol was frozen before scientific training outcomes at SHA256
`5cecd43fd75bd832c6be7fa57c9c56fc752e01288184e9100758c09768952fd8`.
Success requires both utility and coefficient alignment; neither alone is enough.
Exact commit `93e5a9b5b95652e37b563c8bc649bb058524b20b` is deployed to a
clean detached primary-VM worktree. The three-seed mechanical smoke is active in
screen session `stage2-aligned-program-smoke`; seed 17 passed the real finite-loss
GPU update, full calibration-cache, and checkpoint path, while seed 42 is active.
Detached session `stage2-aligned-program` will launch the full frozen run
automatically when the exact smoke completes.

The July 30 deck was changed only on the final future-work slide. It reports the
shortcoming as a limitation—not a failed-result narrative—and presents the
aligned shared/private architecture as the planned pivot.

The smoke and full three-seed run subsequently completed. Shared+private reduced
balanced calibration MSE versus pooled by 36.620%, 35.082%, and 30.051% in seeds
17, 42, and 101. It beat organ-private, random-basis+private, and matched generic
controls in every seed with all donor-bootstrap intervals above zero. Thus every
frozen utility gate passed.

The representation gate did not fully pass. Shared coefficients were strongly
correlated across seeds, but their effective rank was only 1.22–1.31, below the
frozen minimum of 8. The model found a useful, reproducible, nearly one-dimensional
correction rather than a non-collapsed 32-program representation. Prespecified
decision:
`utility_pass_alignment_fail_revise_coefficient_identifiability`.

The first evaluator failed closed because string labels had been serialized as
object arrays. The three model runs and score arrays were intact. A separate clean
evaluator commit reconstructed strings from the hash-pinned manifest and never
enabled pickle loading. Its compact result passed all checksums at
`artifacts/stage2_organ_expert_mechanism/aligned_program_evaluation_ba07442/`.

The subsequent read-only collapse diagnosis showed that the fixed decoder is
high-rank (29.00) and that the actual post-private residual supports sample-level
rank 12.89–14.34 in the same span. The trained head recovered only rank 1.42–1.66.
Its repeated dominant direction primarily encodes organ/site identity and
reconstruction difficulty, with brain at the strongest extreme. The collapse is
therefore a reproducible shortcut caused by the present learning setup, not a
one-dimensional target or a random seed failure.

The bounded repair is to train and freeze the private path first, supervise the
shared head on standardized training-only residual projection coefficients in the
same exact decoder coordinates, retain decoded MSE as an auxiliary loss, and add
overall/within-organ anti-collapse and per-organ safety gates.

A five-fold donor-grouped seed-17 probe then showed that the existing global hidden
summary is already adequate: a simple linear ridge predictor produced rank-12.40
coefficients, median component correlation 0.963, and 69.8% error reduction versus
the private path. The trained nonlinear head achieved only 33.6%. The next repair
therefore changes the training sequence and target, not the model input or decoder.

The user authorized that bounded repair. Commit
`51ab2f58ee683cd7b10f0d62c86e8e77354009dc` and protocol SHA256
`89f6e97218a1871782e08725104e04ae8d1d40001d74ec4e09e01a32e80c5764`
are deployed to a clean detached primary-VM worktree. Seven focused local tests and
the VM projection preflight pass. The three-seed mechanical smoke is active, and a
separate continuation session will automatically start the full frozen run only
after the smoke marker is complete.

The three-seed repair subsequently completed. Aggregate utility remained strong:
35.9% mean reduction versus pooled, 5.2% versus the phase-1 private path, and 5.1%
versus the random basis. Direct supervision raised sample coefficient rank only to
1.81–2.18, far below the frozen minimum of 8; donor and within-organ ranks also
failed, flattened cross-seed correlation fell to 0.271, and skin crossed the 5%
harm boundary in two seeds. Frozen decision:
`coefficient_supervision_repair_fail_pivot_representation`.

The post-completion audit found that nominal extended-private and extended-generic
controls reused optimizers whose learning rate had reached zero after phase 1. The
private states and scores are exactly unchanged in all three seeds, so extended
budget superiority is not claimed. Candidate and random-basis training are
unaffected, and the independent rank/alignment/safety failures already determine
the pivot.

Stage 2 now stops patching expression-PCA coordinates. The prioritized next branch
audits partial-mask versus full-mask target invariance, removes score genes from
the shared-head input to align fit and evaluation, and freezes a common
training-only residual or pathway representation. Organ remains the validated
benchmark while tissue site and cross-cutting platform/quality/pathway attributes
become eligible axes.

## 2026-07-29 — Stage 2 representation-first pivot frozen

The user approved stopping raw organ-pair transfer as the main Stage 2 track. Organ
experts remain the validated benchmark, but Stage 2 now asks whether they express a
seed-stable functional representation before attempting another sharing mechanism.

A read-only protocol was frozen before opening gene-level outputs. It uses the same
1,826 GTEx calibration samples, 188 held-out donors, 4,634 score genes, and all
three Stage 1 seeds. It compares named organ experts with pooled, pooled-adapter,
and three donor-balanced random-K8 controls; requires cross-seed cosine, rank,
top-gene overlap, and donor-bootstrap gates; and forbids fitting, seed selection,
ARCHS4 access, and confirmatory individual-gene claims.

The extractor, evaluator, and strict launcher were implemented. The extractor must
round-trip the original frozen sample-level calibration scores before accepting any
gene program. If at least four organs pass the frozen representation gate, the next
step is a prospective test of whether signature structure predicts safe sharing. If
none pass, Stage 2 broadens beyond organ-only structure to a frozen multi-attribute
audit.

## 2026-07-29 — Exact-gene representation audit completed

All three frozen Stage 1 seeds were re-scored gene by gene on the same 1,826 GTEx
calibration samples and 188 held-out donors. Every seed round-tripped its original
pooled, organ, pooled-adapter, and random-K8 calibration scores before its cache was
published.

All eight organs retained positive donor-bootstrap effects versus the generic
adapter and random controls. However, zero passed the full representation gate:
minimum cross-seed correction cosine ranged from −0.051 to 0.350, efficacy rank
agreement was weak or inconsistent, and minimum top-100 overlap never reached 0.15.

Decision: preserve organ experts as the validated aggregate benchmark, but do not
use exact genes or lucky organ pairs as the Stage 2 sharing rule. The next frozen
audit tests training-donor-derived continuous expression modules and tissue site
nested within organ. Checksum-manifest SHA256:
`0fca3aa432c37668e26e5f1006983b71126510a1056e5a6329bab7aae80650ea`.

The follow-up protocol was frozen before its outputs at SHA256
`78d772cb0f171707b8707756cc8e38dd5b286dca85361a8d14daaa2140dace51`.
It uses 32 training-expression components and all 23 tissue sites meeting the
outcome-independent 30-calibration-donor floor. The evaluator and strict launcher
are implemented; no expert fitting or ARCHS4 access is permitted.

The follow-up completed: adipose was the only organ passing the module gate, and
its subcutaneous and visceral sites were the only 2/23 site passes. Because they
span one organ rather than the required three, the frozen decision is to stop
mining the current experts for a general hidden map and design explicit aligned
program heads. Skin was close but missed the frozen top-module overlap gate; the
threshold was not lowered. Checksum-manifest SHA256:
`a6a26cde213b66b07758498590fa5948bd8450bd4cee0de3fe117ee83dfe5edd`.

## 2026-07-29 — Stage 2 seed-stability diagnosis

All nine frozen trunk-by-optimization combinations completed: pooled trunks 17, 42,
and 101 crossed with optimization/mask/loader replicates 211, 223, and 227. Every
combination used the same 24-arm deterministic-FP32 schedule; no best seed or
favorable edge was selected.

Result:

- 0/8 edges were stable helpful;
- brain ← skin and skin ← adipose were stable harmful;
- 6/8 edges were unstable or negligible;
- liver ← skin averaged +3.011% but was positive in only 6/9 combinations and its
  factor-bootstrap interval crossed zero; and
- all eight named additions remained worse on average than 2,250 recipient-organ
  draws.

The prespecified instability branch therefore fired. Raw cross-organ addition is not
an actionable training policy. The protocol allowed one recipient-protected sharing
implementation, but the user subsequently approved moving directly to the
representation-first audit recorded above. Protected sharing remains a conditional
future option only if a stable representation supplies a prospective sharing rule.

Integrity:

- primary immutable verification: 379/379 entries;
- parallel immutable verification: 304/304 entries;
- compact transfer verification: 207/207 entries, excluding model checkpoints; and
- evaluation checksum-manifest SHA256:
  `66dc24a0d8541f37dfea99be9553677509cb3523da843609835d36febf7c6801`.

This is donor-disjoint GTEx development evidence, not study universality.

## 2026-07-28 — Stage 2 recipient-preserving addition

All three prespecified seeds completed and passed immutable checksum verification.
The evaluation checksum-manifest SHA256 is
`0c005678d312ac8924e498249f215f45d33153704fc5fc646248596b32e5bf7b`.

Results for adding 750 donor-organ draws while retaining 1,500 target-organ draws:

- five of eight mean effects were positive;
- only liver ← skin was positive in all three seeds with its interval above zero:
  +1.956%, 95% CI +1.647% to +2.244%;
- four edges beat all three random auxiliaries in all three seeds; and
- zero of eight named donors beat 2,250 target-organ draws in all three seeds.

Decision: protect target-organ exposure first. Cross-organ addition requires a
validated directional rule.

## 2026-07-28 — Stage 2 same-budget substitution

The complete 56-edge directed matrix compared 750 target-organ plus 750 donor-organ
draws with 1,500 target-organ draws.

- all 56 edges were negative in all three seeds;
- all paired donor-bootstrap intervals were below zero;
- mean effect was −3.273%;
- the independent seed-101 operational replication reproduced the scientific
  matrices and heatmap hashes exactly.

Decision: under a fixed budget, another organ is not a better use of training draws
than additional target-organ exposure. This does not imply that all parameter sharing
is harmful.

## 2026-07-27 — GTEx-to-ARCHS4 external evaluation

The models were trained only on GTEx and evaluated once across heterogeneous ARCHS4
studies.

The first expression access enforced the frozen 14,000-nonzero-gene floor. Exactly
six failing rows were excluded without replacement or threshold change, so the final
evidence is labeled `post_access_qc_amended_external_evaluation`.

Final cohort:

- 821 samples;
- 63 connected studies;
- all eight target organs; and
- all seeds 17, 42, and 101 retained.

Results versus the general pooled model:

- correct organ specialist: 3.797% lower MSE;
- target-hidden hard route: 3.633% lower;
- target-hidden soft route: 3.676% lower;
- equal-capacity pooled adapter: effectively neutral; and
- random K8 partitions: effectively neutral.

Every routed condition improved in every retained seed, and paired connected-study
bootstrap intervals excluded zero. A new untouched cohort remains necessary for a
pristine preregistered confirmation.

## 2026-07-23 — Stage 1 GTEx validation

The final K4-EPE candidate used brain, liver, skeletal-muscle, and skin specialists
with pooled fallback for adipose. It passed the prespecified GTEx V11
donor-controlled validation on 6,795 samples from 930 donors.

- true K4: 3.301% lower donor-balanced equal-organ MSE than pooled;
- target-hidden blind K4: 3.157% lower;
- router accuracy: 98.03%; and
- 95.63% of the true-routing gain recovered.

Random, capacity, seed-stability, active-organ-safety, residual-correlation, and
router-recovery gates passed.

## 2026-07-22 — Stage 1 development decision

The initial K5 organ experiment showed strong routed gains but failed to establish
that the proposed organ partition itself was better than matched random structure.
Controlled K4/K5 retraining, exposure matching, and external validation resolved
that ambiguity and nominated K4-EPE.

Important lesson: routed performance alone does not prove that a named biological
partition is meaningful. Capacity-matched random and pooled controls are required.

## 2026-07-17 — Stage 0 interspecies result

The corrected study-aware evaluation repaired normalization, test-fitting,
test-derived-baseline, and sample-weighting errors from the early analysis.

An expression-only species router achieved 99.0% balanced accuracy. After the
globally shuffled pooled model strengthened the general baseline, blind soft routing
still reduced MSE by 11.42% versus the fixed blend with positive MSE and
residual-correlation intervals.

See [`docs/stage0-final-result.md`](docs/stage0-final-result.md). The invalid early
balanced-evaluation numbers remain only in Git history.

## 2026-07-28 — Presentation and repository consolidation

The July 30 deck and all future decks use
[`presentation/design.md`](presentation/design.md).
The presentation workflow is now:

- audience-first: assume no technical background;
- visual-first: use charts and diagrams when they clarify the result;
- script-free: make the rendered deck self-contained rather than maintaining
  narration;
- plan → results → next, with results occupying most of a biweekly update.

Historical rendered decks remain unchanged. Obsolete talking scripts, completed
watcher/report-generation code, invalid early result files, redundant plots, stale
root planning/report documents, duplicate run bundles, and redundant local backups
were removed after their crucial conclusions were consolidated into canonical docs.

## Preservation policy

Kept:

- active training/evaluation code and tests;
- frozen protocols, manifests, hashes, and final result summaries;
- canonical Stage 0/1/2 result documents;
- final or still-scientifically-useful model backups;
- historical rendered presentation decks and assets they require; and
- full pre-cleanup history in Git.

Removed:

- narration scripts;
- completed one-use watcher/report-generation utilities;
- superseded root plans and reports;
- invalid early tracked outputs;
- generated sweep plots; and
- byte-identical or clearly superseded local backup copies.

## 2026-07-28 — July 30 deck legibility pass

The active July 30 deck and reusable presentation specification were tightened
after visual review:

- the prior 11 px minimum in the main content region was raised to 14 px;
- slides 8–9 now reserve roughly three quarters of a wider canvas for their result
  figures, without the decorative arch/window frame or a contrasting white chart
  canvas;
- the heatmap and additive-effect chart were checked at 1920×1080 for embedded-label
  legibility; and
- bottom-right page tokens were replaced by centered progress dots, with the active
  slide enlarged and darkened while keyboard and 180 ms slide transitions remain.

## 2026-07-28 — Anthropic field-journal design merge

The prior Atrium instructions were merged into a more detailed
[`presentation/design.md`](presentation/design.md), using the supplied Anthropic
scientific-field-journal reference as the primary visual authority. The canonical
system now specifies:

- Ivory Medium parchment, layered ivory/oat/manilla paper surfaces, Slate Dark ink,
  Stone rules, and one restrained Clay accent;
- Anthropic Serif/Sans/Mono family tokens with portable Source Serif 4, Inter, and
  technical-monospace fallbacks;
- serif editorial body copy with sans-serif reserved for navigation, labels, and
  compact metadata;
- flat elevation without shadows, restrained 24 px cards, and the former Atrium arch
  only as a sparse functional project adaptation; and
- all previously frozen audience, narrative, chart-legibility, pagination,
  transition, and scientific-claim safeguards.

The July 30 deck was updated to this palette and type system. July 9 and July 16
remain unchanged historical artifacts.

## 2026-07-28 — Restrained color and readable-note correction

The Anthropic merge was corrected so it does not flatten scientific comparisons
into gray:

- the main Stage 1 bar chart now uses neutral baseline, Atrium Sage for the known
  specialist, Muted Blue for automatic hard routing, and Soft Sage for the blend;
- sage and muted blue are canonical functional data accents but remain prohibited
  as gratuitous surface decoration; and
- every retained footnote, caveat, evidence label, and interpretive chart caption is
  now at least 16 px. Notes are kept only when they change interpretation; otherwise
  they should be removed.

Slides 4–6 and 8–9 were rerendered at 1920×1080. The larger notes remain clear of
content and centered pagination.

## 2026-07-28 — Twenty-percent central scale increase

The active deck was enlarged as a complete visual system:

- standard content width increased from 1440 px to 1720 px at 1920×1080, while
  result slides may use up to 1760 px;
- peripheral padding decreased from 3vw/30 px to 2vw/22 px;
- the center-content floor increased from 14 px to 16 px;
- headlines, body text, cards, statistics, bars, labels, gaps, and chart captions
  were enlarged together rather than scaling headlines alone; and
- important notes now render at 17 px in the active deck, above the universal 16 px
  minimum.

All nine slides were rerendered at 1920×1080. The measured content canvases are
1720 px and 1760 px, the minimum visible center text is 16 px, and no slide reports
horizontal or vertical overflow.

## 2026-07-28 — Semantic winner highlight

The Stage 1 comparison chart now assigns Muted Blue to the verified numerical winner
(correct organ specialist, +3.797%), Sage to automatic single choice, Soft Sage to
the automatic blend, and neutral gray to baseline. The design specification now
requires a semantic `.winner` class so the highlight follows the result rather than
a hard-coded bar position. It also records the exact current canvas, typography,
card, caption, transition, pagination, and spacing values for reuse.

## 2026-07-28 — Dedicated future-work closer

The July 30 deck now ends with a tenth slide rather than embedding the entire next
step in the additive-result slide. The closer states the active frozen diagnosis and
three prespecified branches:

- reproducible helpful transfer → selective sharing and untouched multi-study
  validation;
- reproducible but mostly harmful transfer → negative-transfer prevention and
  protected/selective sharing; or
- optimization instability → one protected-sharing test, then broader pathway,
  biological-state, or expert-residual representations if needed.

The shared end product is a reproducible rule for which biological domains should
share training information and which should remain isolated. The slide passed
1920×1080 visual and overflow checks, and pagination now generates ten dots
automatically.

## 2026-07-29 — Presentation diagnosis update

The July 30 deck reports the completed nine-run stability result without adding a
failure narrative: 0/8 stable-helpful, 2/8 stable-harmful, and 6/8
unstable/negligible relationships. Its future-work slide will be refrozen after the
active representation audit so it reports the verified branch rather than an
obsolete protected-sharing promise.

The preliminary additive heatmap remains visible but is explicitly not a training
policy. Structural checks confirm ten slides, both referenced image assets,
180-millisecond reduced-motion-aware navigation, and centered dynamic pagination.
Pixel-level in-app preview was unavailable because local `file://` navigation was
blocked by browser security policy; that restriction was not bypassed.

## 2026-07-28 — Presentation package consolidation

The presentation package was reduced to the rendered decks, the assets those decks
load, and the canonical design specification. Removed:

- the July 30 content brief;
- the July 30 readiness checklist;
- the completed one-use additive-chart renderer; and
- the superseded July 16 image-generation prompt.

Two `.DS_Store` metadata files and the ignored July 15 corrected-interspecies driver
log were also removed locally. The log's decision-relevant results are preserved in
`docs/stage0-final-result.md`.

The July 9, July 16, and July 30 decks, the historical July 16 plan image, both
current Stage 2 result figures, and `presentation/design.md` remain. Deleted files
remain recoverable from Git history.
