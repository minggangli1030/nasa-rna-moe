# Final organ-embedding downstream-development result

**Completed:** 2026-07-31 09:09 PDT / 2026-07-31 16:09 UTC

## Decision

The frozen downstream-positive gate failed. None of the three deployable organ
embedding contracts beat the same-seed pooled hidden summary, raw expression, and
fold-fit PCA in every seed. No seed or output condition is selected.

The validated K8 organ MoE remains the final reconstruction model, with the pooled
prediction retained as fallback/reference. Its package will expose hidden and router
states for analysis, but no learned embedding receives a downstream-benefit claim.
Raw expression and fold-fit PCA remain mandatory downstream baselines.

## AUROC result

The exact 292-sample, 18-study OSDR development cohort and study-grouped nested
elastic-net harness were reused without membership, split, grid, or checkpoint
changes.

| Representation | Seed 17 | Seed 42 | Seed 101 |
|---|---:|---:|---:|
| Pooled hidden | 0.525 | 0.547 | 0.607 |
| Pooled hidden + router probabilities | 0.548 | 0.559 | 0.551 |
| Pooled hidden + revealed organ | 0.546 | 0.546 | 0.596 |
| True-organ bottleneck embedding | 0.571 | 0.537 | 0.546 |
| Input-only hard-router embedding | 0.531 | 0.561 | 0.533 |
| Input-only soft-router embedding | 0.557 | 0.566 | 0.507 |

The seed-independent baselines remained much stronger: raw expression AUROC was
0.726 and fold-fit PCA-64 was 0.733. Soft routing improved over pooled hidden in
seeds 17 and 42 (+0.032 and +0.019) but fell by 0.100 in seed 101. Hard routing and
pooled-plus-router showed the same two-positive/one-negative pattern. Every learned
condition remained 0.160–0.225 below raw/PCA at its relevant seed.

## Interpretation

Changing the output from reconstructed score genes to pooled hidden state plus the
organ-adapter bottleneck did not solve the downstream mismatch. The organ model's
external reconstruction gain remains valid, but this cross-species spaceflight task
does not support a general-purpose downstream embedding claim.

The result strengthens a practical distinction:

> The model is validated as an organ-specialized reconstruction system. Downstream
> utility is a separate claim that must be earned task by task against raw expression
> and PCA.

The OSDR cohort is already accessed development data. These numbers may determine
the package contract but cannot confirm a final claim; a new untouched grouped
cohort is required.

## Final packaging decision

The final package preserves all three validated Stage-1 seeds rather than refitting
after lockbox access. A train-plus-calibration refit would create new weights that no
longer have the existing ARCHS4 external validation, and full union coverage would
require changing the frozen 1,500-exposure-per-expert budget because the brain union
alone has 3,030 samples. Neither change is justified by this negative downstream
result.

The immutable package therefore contains, for every seed, the exact validated pooled
trunk and K8 organ adapter bank, plus the frozen input-only router. It exposes pooled,
true-organ, hard-router, and soft-router reconstruction outputs; pooled hidden and
adapter bottlenecks are diagnostic outputs only. It performs no additional fitting
and makes no downstream-positive assertion.

The frozen package completed under exact clean commit
`dc562cc97d3936c642467a5be563e9bd7e31fc7b` at
`/media/volume/moe-reboot/results/final_k8_package_dc562cc`. Its 17 packaged
artifacts and all checkpoint tensors passed immutable checksum and finiteness
verification. Package-manifest SHA256 is
`8c8e967faa7d63fda80bdb4c301678544290cbeb01f833ae7e6817be6a60e4e9`.

## Immutable evidence

- protocol SHA256:
  `3730da5059691065855c88f25cb79636e07887b7ed7f127e467256e9b848910a`;
- exact repaired execution commit:
  `3f681fdbe818d2f49b03f097f08a5f171b4e35c8`;
- evaluation report SHA256:
  `10c57530ae3f14a8ed210943e41cac5fa71af32b4bef972009cf45a5fc577c8f`;
- frozen summary SHA256:
  `84cc59eeb69b73e72356c34c225ee013adfd85f185ddae7d1523de88b4f26638`; and
- local compact lineage:
  `artifacts/final_evaluation/final_organ_embedding_evaluation_3f681fd/`.
