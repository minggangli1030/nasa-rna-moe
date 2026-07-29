# Stage 2 aligned shared/private program heads

**Status:** three-seed development evaluation complete

**Scientific commit:** `93e5a9b5b95652e37b563c8bc649bb058524b20b`

**Protocol SHA256:** `5cecd43fd75bd832c6be7fa57c9c56fc752e01288184e9100758c09768952fd8`

## Why this pivot exists

Stage 1 established a reproducible aggregate advantage for organ specialists.
Stage 2 did not find a reproducible rule for sharing training signal:

- 0/8 tested organ-to-organ additions were stable helpful in the crossed
  trunk-by-optimization diagnosis;
- exact-gene corrections were not aligned across the three trunks; and
- only adipose passed the coarser module/site audit.

The limitation is therefore not evidence that organ specialists are ineffective.
It is that the internal coordinates learned by independent specialists are not
identifiable enough to compare or reuse directly.

## Model

The new model aligns the shared coordinates by construction:

1. freeze each seed-specific Stage 1 pooled trunk;
2. freeze the same 32-component expression basis derived from GTEx training donors
   before this experiment;
3. use expression input alone to predict a 32-value shared coefficient vector;
4. decode that vector through the fixed basis into score-gene residuals; and
5. add a hard-dispatched organ-private residual path.

Only the private path receives the organ label. The shared path remains
input-derived. The fixed decoder makes coefficient 7 mean the same mathematical
direction in every seed, while the private branch protects organ-specific
corrections that should not be shared.

## Frozen comparisons

All six conditions consume the same fitting rows, schedule, masks, update budget,
optimizer, and frozen trunk within a seed:

- parameter-matched generic adapter;
- organ-private adapters only;
- shared program path only;
- shared program plus organ-private path;
- random orthonormal basis plus organ-private path; and
- shared program plus donor-balanced random-private labels.

The generic control is within 2% of the shared-plus-private trainable parameter
count. The random-basis and random-label conditions distinguish useful fixed
structure from capacity and arbitrary partitioning.

## Decision gate

The model advances only if it satisfies both sides:

- **utility:** positive versus pooled in every seed, at least 90% of the
  organ-private gain preserved, and all-seed donor-bootstrap superiority to both
  the random-basis and matched generic controls; and
- **alignment:** minimum flattened cross-seed donor-coefficient correlation of
  0.5, minimum pairwise median component correlation of 0.3, and coefficient
  effective rank of at least 8.

Utility without alignment is not a stable representation. Alignment without
utility is not a useful model.

## Execution

- Detached VM worktree:
  `/media/volume/moe-reboot/worktrees/stage2_aligned_program_93e5a9b`
- Mechanical smoke:
  `/media/volume/moe-reboot/results/stage2_aligned_program_smoke_93e5a9b`
- Smoke session: `stage2-aligned-program-smoke`
- Planned full result root:
  `/media/volume/moe-reboot/results/stage2_aligned_program_93e5a9b`
- Full-run continuation session: `stage2-aligned-program`

The launcher will not start the full run unless the exact three-seed mechanical
smoke completes. It verifies the clean commit, protocol hash, input/checkpoint
hashes, basis and decoder hashes, K8 label coverage, capacity match, finite losses,
score-cache shapes, and checkpoint hashes.

The continuation session is already active. It starts the full run automatically
after a complete smoke marker and exits instead if the smoke status becomes
`FAILED`.

## Claim boundary

This remains donor-disjoint GTEx development evidence. A pass would justify a
prospective independent-study confirmation; it would not establish biological
mechanism, study universality, or spaceflight/disease utility.

## Completed result

All three fixed seeds completed 1,500 updates and the full donor-disjoint
calibration:

| Comparison | Seed 17 | Seed 42 | Seed 101 |
|---|---:|---:|---:|
| Shared+private vs pooled | +36.620% | +35.082% | +30.051% |
| Shared+private vs organ-private | +6.811% | +18.775% | +4.500% |
| Shared+private vs random-basis+private | +6.296% | +12.460% | +9.426% |
| Shared+private vs matched generic | +38.268% | +35.168% | +31.740% |

Every reported donor-bootstrap interval was above zero. The shared+private model
retained 131.7% of the organ-private gain on average.

The aligned coefficients were reproducible but collapsed:

- minimum flattened donor-coefficient correlation: 0.834;
- minimum pairwise median component correlation: 0.900; and
- effective rank: 1.22–1.31, below the frozen minimum of 8.

Decision:
`utility_pass_alignment_fail_revise_coefficient_identifiability`.

The next permitted step is one bounded identifiability revision. It should preserve
the fixed decoder and successful utility controls while preventing the shared head
from concentrating nearly all variation into one program direction. No claim of a
32-program biological representation is supported yet.

Compact result:
`artifacts/stage2_organ_expert_mechanism/aligned_program_evaluation_ba07442/`.

## Read-only collapse diagnosis

The fixed decoder itself has effective rank 29.00, and least-squares projection of
the actual post-private residual into the same decoder span has sample-level
effective rank 12.89–14.34 and within-organ rank 16.48–17.04. The learned
coefficients remain rank 1.42–1.66 at sample level. The representational target is
therefore not intrinsically one-dimensional.

All three seeds instead learned nearly the same organ/difficulty shortcut. The
leading direction is strongly associated with organ and tissue site, separates
brain most sharply, and carries approximately 75–78% of decoded coefficient energy.
This is a reproducible optimization outcome, not random collapse.

For seed 17, a five-fold donor-grouped linear probe using the exact existing hidden
summary predicted oracle coefficients at effective rank 12.40, with median
component correlation 0.963, and removed 69.8% of private-path error. The trained
nonlinear head removed 33.6%. Thus neither input information nor head capacity is
the primary bottleneck.

The detailed evidence and bounded repair are in
[`stage2-aligned-program-collapse-diagnosis.md`](stage2-aligned-program-collapse-diagnosis.md).
