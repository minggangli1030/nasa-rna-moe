# Multiaxis Tier-1 result

**Completed:** 2026-07-30 23:19 PDT / 2026-07-31 06:19 UTC

**Role:** training-donor and OSDR development screening; not final confirmation

## Decision

Tissue site is the only candidate that clears every frozen Tier-1 gate and is the
only axis authorized for the bounded Tier-2 protected-adapter smoke.

Hallmark-50 produced the largest aggregate signal and the clearest OSDR signal,
but it failed the prespecified per-organ safety gate. Age and sex were too small
to clear the all-seed donor-bootstrap gate. No threshold, seed, or candidate was
selected post hoc.

## Exact result

| Candidate | Mean primary incremental R² | OSDR AUROC delta | Training gate | Decision |
|---|---:|---:|---|---|
| Tissue site | **0.2764** | +0.0045 | Passed every gate in 3/3 seeds | Advance to Tier 2 |
| Hallmark-50 | **0.5233** | **+0.1013** | Failed per-organ safety in seeds 42 and 101 | Stop |
| Age bracket | +0.00064 | +0.0068 | Bootstrap lower bound crossed zero in seeds 42 and 101 | Stop |
| Sex | +0.00013 | +0.0071 | Bootstrap lower bound crossed zero in 3/3 seeds | Stop |

The primary outcome is held-out post-private coefficient prediction after the
organ-plus-technical-nuisance base. Tissue-site incremental R² was 0.2837,
0.2715, and 0.2739 for seeds 17, 42, and 101. Its donor-bootstrap lower bounds
were 0.2725, 0.2595, and 0.2618; every real effect exceeded the within-organ
permutation 95th percentile. All three auxiliary outcomes were positive, the
technical-proxy gate passed, and every protected-organ effect was nonnegative.

Hallmark-50 was highly predictive in aggregate: primary incremental R² was
0.5380, 0.5136, and 0.5183, and its OSDR AUROC delta was +0.1013 with a
study-bootstrap interval of +0.0267 to +0.2049. It nevertheless harmed protected
skeletal-muscle prediction by −0.0568 in seed 42 and −0.0396 in seed 101, beyond
the frozen −0.02 safety limit. Aggregate usefulness is therefore insufficient to
authorize an expert axis that produces reproducible organ-specific harm.

The OSDR probe used the exact 292-sample/18-study no-replacement development
cohort. All four point deltas were positive under the frozen downstream gate, but
only Hallmark-50 had a bootstrap interval above zero. Tissue site's OSDR effect
is therefore weak supporting evidence; its authorization comes from satisfying
the complete joint gate, not from claiming a strong downstream win.

## Integrity and limitations

- Training protocol SHA256:
  `cd1d3dab63689cd3d534533f37e48f5d0c05e4a7d9f407ec57ee0b49c6c5e4f1`.
- Exact scientific training commit:
  `9de77e040f3b69421b65ed6d780a007e9256501e`.
- OSDR probe protocol SHA256:
  `531438c0361501954a7eee1a49c9ea97ba53e67d339db53a13bd8c426a4198fd`.
- Exact OSDR evaluator commit:
  `b99d5b6a78e2f0522afdba7034230d7356b50ded`.
- Seeds 17, 42, and 101 were all evaluated; no best seed was selected.
- The original concurrent seed-42 process was killed by aggregate memory
  pressure before emitting a report. A first retry had an operational wrapper
  error before outcome access. Both lineages are preserved. The accepted seed-42
  report comes from the exact same frozen execution run alone.
- These are GTEx training-donor and OSDR development results. They do not establish
  universality across independent human studies or confirm a final downstream
  advantage.

## Next step

Run one bounded three-seed Tier-2 smoke for a protected tissue-site adapter. Keep
the organ path protected and compare the site adapter against a within-organ
shuffled-site control and an equal-capacity generic adapter. Require positive
incremental utility in every seed, no material per-organ harm, noncollapsed site
use, and deployable input-only scoring. If it fails, close the final architecture
as the validated organ MoE with pooled fallback. If it passes, at most tissue site
may enter the final model.

Compact seed reports, the OSDR report, and the deterministic aggregate are under
`artifacts/stage2_organ_expert_mechanism/multiaxis_tier1_training_9de77e0/`,
`multiaxis_tier1_osdr_probe_b99d5b6/`, and
`multiaxis_tier1_aggregate_9de77e0/`.
