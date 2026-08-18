# NASA RNA MoE: agent handoff

The summer project is closed. Read these files before changing code or running an
experiment:

1. `docs/project-closeout.md`
2. `docs/recovery-and-data.md`
3. `docs/current-status.md`
4. the canonical result or frozen protocol for the workflow in question

## Scientific guardrails

- The Stage 1 claim is lower masked-gene reconstruction error, not downstream or
  clinical usefulness.
- Call the ARCHS4 result externally evaluated and pending untouched confirmation.
- Do not tune on the completed 821-sample ARCHS4 result or accessed OSDR cohort.
- Do not select favorable seeds, organs, layers, studies, or label fractions after
  access.
- Raw expression, fold-fit PCA, and an equally capable shared model are mandatory
  controls for downstream claims.
- The GTEx variance decomposition measures reconstruction-loss allocation, not where
  perturbation information resides.
- A better reconstruction score is insufficient unless the representation also
  improves a prespecified downstream task.

## Resume order

1. Verify final-model and backup SHA-256 ledgers.
2. Rebuild public data from `docs/recovery-and-data.md`.
3. Reproduce existing compact reports and focused tests.
4. Run the frozen untouched Track A reconstruction confirmation unchanged.
5. Only then test one separately versioned objective-alignment pilot and a stronger
   downstream benchmark.

## Repository policy

- Keep code, protocols, manifests, compact results, docs, and presentation sources in
  Git.
- Keep public datasets, generated caches, model weights, and recovery bundles out of
  Git.
- Every important ignored artifact needs a checksum ledger and a documented rebuild or
  restore path.
- Historical plans remain evidence, not active instructions. The closeout document
  governs conflicts.

The previous long Claude/Codex decision transcript is preserved in the ignored
pre-cleanup snapshot at
`backups/project-closeout-2026-08-17/pre-cleanup-docs/CLAUDE.md`.
