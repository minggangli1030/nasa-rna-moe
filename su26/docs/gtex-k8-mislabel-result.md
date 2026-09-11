# Frozen K8 organ-label compatibility result

**Completed:** 2026-08-03 20:20 PDT / 2026-08-04 03:20 UTC

**Evidence role:** accessed GTEx calibration development; not confirmation

**Decision:** `MISLABEL_UTILITY_DOES_NOT_BEAT_RAW_AND_PCA_ALL_SEEDS`

## Question

Can the frozen organ experts detect an incorrect assigned organ label better than
simple expression-space compatibility scores?

Each calibration sample was paired with its correct organ assignment and all seven
wrong assignments. The score was assigned-label error minus the best error across all
eight possible labels. The expert score used the already frozen calibration MSE cache;
the controls were train-only raw-centroid and fold-fit PCA64-centroid margins. AUROC
was averaged equally across organs and uncertainty resampled GTEx donors within organ.

## Result

| Condition | Equal-organ label-swap AUROC |
|---|---:|
| raw centroid | 0.997778 |
| PCA64 centroid | 0.999967 |
| expert seed 17 | 0.998610 |
| expert seed 42 | 0.979082 |
| expert seed 101 | 0.999468 |

The experts recognize organ-label incompatibility very accurately, but the task is
nearly saturated by PCA64. Every expert seed is below PCA64, and every paired donor-
bootstrap interval for expert minus PCA64 is entirely negative:

- seed 17: −0.002004 to −0.000813;
- seed 42: −0.022324 to −0.019452;
- seed 101: −0.000854 to −0.000204.

Against raw centroids, seed 101 is robustly positive, seed 17 is inconclusive, and
seed 42 is robustly negative. Therefore the prespecified all-seed gate fails.

## Takeaway

This is a useful boundary, not a model win. Organ-conditioned reconstruction contains
strong organ compatibility information, but a cheap PCA baseline already solves this
synthetic label-swap task almost perfectly. The result does not justify deploying the
MoE for label QC, and no corruption strength, seed, baseline, or threshold will be
changed post hoc to rescue it. Expression-anomaly mixtures remain a distinct possible
question, but they are not substituted onto the critical path after this failure.

The failed implementation-only lineage at commit `6afe4a5` is preserved; it emitted no
result because it used a different array-hash encoding than the historical trainer.
The versioned hash-only correction ran at exact commit `d20cab1b70c2e60459c123e292304697accb6753`.
Protocol SHA256 is
`b8de39a7b87c6d3f09976b822e49135186c94a5be2f75f7843090a938d3b9fd6`;
evaluator SHA256 is
`ec1e0b799280cbdebc478537055b28abf6ae15fa169878d5769a477680ab017e`.
The compact immutable result is under
`artifacts/final_evaluation/gtex_k8_mislabel/evaluation_d20cab1/`.
