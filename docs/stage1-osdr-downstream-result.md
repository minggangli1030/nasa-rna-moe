# Stage 1 OSDR downstream-development result

**Completed:** 2026-07-30 21:26 PDT / 2026-07-31 04:26 UTC

**Role:** external cross-species downstream development; not an untouched final
confirmation

## Decision

The prespecified positive gate failed. Frozen Stage 1 organ-specialist
representations did not improve spaceflight-versus-ground AUROC over the
same-seed pooled trunk in all three seeds. Raw expression and fold-fit PCA were
substantially stronger than every learned Stage 1 condition.

This result does not undo the Stage 1 reconstruction result. It separates two
claims:

- organ specialization reproducibly improves masked-gene reconstruction on
  external human ARCHS4 data; but
- the current masked score-panel predictions are not a competitive frozen
  representation for this cross-species OSDR classification task.

The next model must therefore preserve the validated reconstruction result while
optimizing and testing a representation intended for downstream use. A
reconstruction-only improvement is not sufficient evidence of biological
decision utility.

## Frozen cohort and execution

- 892 exact structured flight/ground rows were requested from 43 OSDR studies.
- The frozen 14,000-nonzero-gene rule retained 297 rows.
- Requiring both classes within each study-organ unit retained 292 samples from
  18 studies.
- No failed sample was replaced.
- Evaluation used identical five-fold study-grouped outer splits, training-study
  grouped three-fold inner selection, the same 12-point elastic-net grid, and all
  fixed Stage 1 seeds 17, 42, and 101.
- No checkpoint was updated and no best seed was selected.
- Cohort protocol SHA256:
  `04e8354b1417c2f4bb4459f053a4e343dce1e65a9b552e16f7fea08c52d8abb9`.
- Exact evaluator commit: `61766ee`.

## Primary result

Out-of-fold metrics are pooled across the same 292 samples. Learned-condition
values are the mean across all three fixed seeds, with the seed range in
parentheses.

| Representation | AUROC | AUPRC | Balanced accuracy | Macro-F1 |
|---|---:|---:|---:|---:|
| Raw expression | **0.726** | 0.653 | **0.723** | **0.723** |
| PCA-64 | **0.733** | **0.720** | 0.709 | 0.709 |
| Pooled trunk | 0.605 (0.570–0.631) | 0.579 (0.543–0.608) | 0.562 (0.538–0.579) | 0.560 (0.537–0.577) |
| Pooled adapter | 0.605 (0.570–0.631) | 0.579 (0.542–0.608) | 0.562 (0.538–0.579) | 0.560 (0.537–0.577) |
| Pooled + revealed organ label | 0.604 (0.572–0.625) | 0.579 (0.545–0.606) | 0.564 (0.541–0.583) | 0.563 (0.541–0.581) |
| True-organ specialist | 0.594 (0.580–0.613) | 0.578 (0.557–0.591) | 0.561 (0.535–0.586) | 0.557 (0.532–0.586) |
| Input-only hard router | 0.590 (0.554–0.630) | 0.599 (0.551–0.655) | 0.532 (0.490–0.575) | 0.531 (0.487–0.575) |
| Input-only soft router | 0.595 (0.567–0.615) | 0.601 (0.558–0.636) | 0.553 (0.541–0.568) | 0.552 (0.541–0.568) |

True-organ minus pooled AUROC was −0.051, −0.003, and +0.018 for seeds 17,
42, and 101. Hard-router deltas were −0.046, +0.015, and −0.016; soft-router
deltas were −0.028, approximately 0.000, and −0.003. Thus none of the three
specialist modes passed the frozen all-seed direction gate.

The highest learned AUROC was 0.631, still below raw expression at 0.726 and
PCA-64 at 0.733. The routers showed higher mean AUPRC than the pooled trunk, but
the primary AUROC direction was unstable and their balanced accuracy and macro-F1
were not improved. This is not an actionable downstream win.

## Interpretation

The most plausible bounded explanation is a task-representation mismatch. Stage 1
was trained to reconstruct a fixed masked gene panel in human GTEx, whereas this
benchmark asks those predicted panel values to classify mouse spaceflight status.
Raw expression and fold-fit PCA retain broad observed response programs that the
masked reconstruction output can smooth away. Cross-species orthology, the severe
QC contraction, heterogeneous spaceflight protocols, and the fact that organ
identity is not the target can all increase that mismatch.

This result does **not** show that organ experts are generally unhelpful, that the
ARCHS4 reconstruction gain was false, or that no learned representation can help
OSDR. It shows that this particular frozen Stage 1 output contract is not yet a
downstream representation advantage.

## Prioritized response

1. Keep raw expression and fold-fit PCA as mandatory gates for every later
   downstream claim.
2. Do not select an organ specialist, router, or seed from this cohort.
3. Complete the training-only tissue-site, age/sex, and Hallmark-50 screens, but
   require an independently measured downstream-label probe before adding an axis.
4. Close the architecture by 2026-08-02. If no secondary axis clears all frozen
   gates, use the validated organ MoE plus pooled fallback.
5. For final training, expose and freeze a downstream-facing embedding or
   multi-task objective rather than treating masked score-panel predictions as the
   only representation.
6. Reuse this now-validated study-grouped harness for development, then require a
   new untouched grouped cohort for the final claim.

## Verified artifacts

Compact reports and out-of-fold predictions are under
`artifacts/final_evaluation/stage1_osdr_downstream_evaluation_61766ee/`.
The full report and predictions have SHA256
`1366d7dedabbac99b8cb80126e7660f91f9238e3355bfc8fb4042d835b41547b`
and
`1313b52d26d74b080f8fc0b1b8e9648c6e3ba5e8d50e16cf620753bd03d6ad3d`,
respectively.

## 2026-08-01 interpretation audit addendum

The frozen D1 audit's original machine verdict was
`ENCODER_TRANSFERS_OBJECTIVE_LIMIT`, but its executed brain-versus-skeletal-muscle
control is now reclassified `D1B_CONFOUNDED_UNINFORMATIVE`: organ is completely
aliased with OSDR study for that contrast. The 1.000 raw and 0.996 pooled-hidden
balanced accuracies remain recorded but support no organ-transfer inference. D1a
instead shows mild compression without global degeneration, and D1c passes mapping,
missing-input, and normalization checks. The negative result above is therefore not
explained by gross encoder or pipeline failure, but fine-grained cross-species
biological retention remains unresolved pending the frozen GTEx-trained replacement.
