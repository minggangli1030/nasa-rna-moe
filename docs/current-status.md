# NASA RNA MoE: current canonical status

**Updated:** 2026-08-03 20:53 PDT / 2026-08-04 03:53 UTC

This is the operational handoff. Historical detail is preserved in Git and in
[`../progress.md`](../progress.md).

## Current phase

The Claude/Codex August 17 dispute is resolved and implementation has started within
the authorized boundary. The exact execution plan is frozen at SHA256
`cab2f979d4387edd3a72241a18780234463f4625aaf0f89831662e984851754f`.
The protected deliverable is now the separate deck
[`../presentation/2026-08-17-final.html`](../presentation/2026-08-17-final.html).
Static validation passes eight slides, unique IDs, no pure white/black, and a minimum
explicit text size of 16 px. The July 30 deck and shared design file were not modified
by this implementation step.

D3-0 metadata readiness is active without candidate expression access. The first
candidate family is human disuse/bed-rest skeletal muscle. Public metadata yielded ten
potentially retainable studies and one prespecified coverage exclusion (`GSE14798`, a
6,681-gene custom array below the unchanged 14,000-gene rule). The rough retained
planning range is 250–300 observations, but this is not a gate pass. Exact paired
membership, structured contrasts, assay/gene coverage, GTEx/ARCHS4 overlap firewalls,
and untouched confirmation reservation remain unresolved. No headroom outcome has
been measured and no supervised training has started. See
[`d3-metadata-readiness-inventory.md`](d3-metadata-readiness-inventory.md).

The future calibration-retention estimand is frozen symbolically, not measured. Exact
organ, pooled-trunk, pooled-adapter, and calibration-score hashes are recorded for all
three seeds. Measurement remains fail-closed because calibration membership, score
panel/mask schedule, evaluator, and the intended matched-pooled comparator are not yet
unambiguous. Until those fields are resolved and the specification is re-hashed,
`G_cal` cannot be computed and partially unfrozen Arm 3 is not authorized. Frozen
encoder Arms 1 and 2 are post-presentation future work, not active execution.

The untouched reconstruction-confirmation contract is drafted but intentionally not
frozen: exact expression source, minimum per-organ coverage, membership, overlap audit,
and evaluator/checkpoint manifests are required first. Exact current planning hashes
are in `artifacts/final_evaluation/aug17_planning/PLANNING_SHA256SUMS`.

The first closeout experiment is complete. The read-only organ-label compatibility evaluator uses
the existing GTEx calibration score caches, all seven wrong label assignments per
sample, and train-only raw/PCA centroid margins. Protocol SHA256 is
`b8de39a7b87c6d3f09976b822e49135186c94a5be2f75f7843090a938d3b9fd6`;
evaluator SHA256 is
`ec1e0b799280cbdebc478537055b28abf6ae15fa169878d5769a477680ab017e`.
Expert AUROC is 0.998610/0.979082/0.999468 for seeds 17/42/101, but PCA64 reaches
0.999967 and raw reaches 0.997778. Every expert-minus-PCA interval is negative, so the
all-seed gate fails. This closes synthetic label-swap utility without tuning. See
[`gtex-k8-mislabel-result.md`](gtex-k8-mislabel-result.md).

The main new closeout experiment is now protocol-frozen but not yet trained: a
frozen-trunk adapter data-diversity curve at exactly 25/50/100/150/200 unique donors
per organ, one expression-blind sample per donor. The immutable scale manifest is
identical across its two metadata-only build lineages and its trainer-compatible hash
is `5f1f8bd62371ad993a2d4016c94e1ee252a18b795fc73e1c4b5f51570cdf66fc`.
The scientific protocol SHA256 is
`0a93107daa1a916a1ce58fecc3c5992c0f1ea7e7e0f59afd21c0f9d8f8d9f22a`.
It compares organ K8 with the active-width/compute-matched pooled adapter on identical
samples, updates, and total exposures across all three seeds; the pooled control has
one adapter and is not matched for K8's total stored parameter count. The first
mechanical lineage failed before training because its combined manifest included
unselected training rows. A replacement then failed before its first update because a
legacy fallback exposure argument was not batch-divisible. The next smoke successfully
completed both finite two-update banks and calibration caches, but its wrapper rejected
the trainer's canonical nested `config.final_update` field. All lineages are preserved;
none is a scale result. Five per-budget manifests pass immutable checksums, and the
versioned validator/resume correction passes all five focused tests. One final
end-to-end GPU smoke is the next gate; no scale outcome exists yet.

## Frozen completed results

### Stage 1: external reconstruction result remains positive

The final GTEx-to-ARCHS4 evaluation used 821 QC-passing samples from 63 connected
studies across eight organs. Against pooled reconstruction:

- true-organ K8 improved equal-organ/equal-study MSE by 3.797%;
- input-only hard routing improved it by 3.633%;
- input-only soft routing improved it by 3.676%;
- pooled-adapter and random-K8 controls were effectively neutral;
- all three fixed seeds improved without best-seed selection.

This is correctly labeled a post-access QC-amended external evaluation, not a pristine
preregistered confirmation. The accessed ARCHS4 expression and its 3.797% result are
never reused for development, tolerance setting, or model selection.

### Stage 2: naive sharing and secondary axes did not clear robust gates

Directed organ transfer did not yield a reproducible helpful sharing rule. All 56
substitution edges were harmful; no additive edge beat extra recipient data, and raw
addition did not produce a stable helpful pattern across the frozen seed-factorized
diagnosis. Tissue site was the only Tier-1 candidate but failed its matched generic-
capacity control in every seed. Hallmark-50 failed per-organ safety. The architecture
therefore remains the validated K8 organ MoE plus pooled fallback/reference, with no
secondary axis.

### Downstream development: current frozen-output branch is closed

The final K8 encoder preserves cross-species organ structure but its tested frozen
outputs do not beat raw expression or fold-fit PCA on the accessed OSDR state task.
Raw/PCA AUROC was 0.726/0.733 on the 292-sample, 18-study development cohort. In the
only adequately powered skeletal-muscle analysis, raw/PCA reached 0.9675/0.9623 while
learned embeddings remained 0.5578–0.7563. Specialization-versus-pooling directions
reversed across seeds. Residual features recovered state prediction but not a stable
organ-specific advantage over pooled residual and centered-expression controls.

At the nominal 5% label floor, raw/PCA mean AUROC was 0.6289/0.6329 versus
0.4890–0.5250 learned. At 10%, raw/PCA was 0.7313/0.7203 versus 0.5074–0.5339 learned.
Every learned-minus-raw mean was negative in every model seed and every 10% interval
was below zero. The bounded conclusion is reduced linear accessibility under the
tested grouped elastic-net contract—not proof of information-theoretic absence.

All E1–E4 gates failed under their frozen protocol. This closes further selection
among existing frozen outputs on accessed OSDR development evidence; it does not
revoke the Stage 1 reconstruction result or prove failure on every downstream task.

## Authorization and next gates

Authorized now:

1. finish the metadata-only D3 membership/label/coverage/overlap audit;
2. reserve a grouped confirmation subset before any supervised development;
3. complete the untouched reconstruction-confirmation contract without accessing its
   expression outcomes;
4. complete and statically/visually verify the August 17 deck using frozen results.

Blocked until exact contracts are frozen:

- candidate expression access and raw/PCA headroom measurement;
- `G_cal` computation;
- any supervised Arm 1/2/3 run;
- any ARCHS4 expression access or final K8 package modification.

If D3 metadata clears every frozen gate, raw/PCA headroom is measured once using the
primary-organ 0.60–0.90 AUROC band, study-bootstrap interval, and single-study
dominance check. If it does not clear, infeasibility is documented without changing
thresholds or substituting samples after access.
