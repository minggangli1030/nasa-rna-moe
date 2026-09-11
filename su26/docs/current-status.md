# Current status

**Updated:** 2026-08-17
**State:** summer project closed; no active run

The canonical handoff is now [`project-closeout.md`](project-closeout.md). Public-data
and VM recovery instructions are in [`recovery-and-data.md`](recovery-and-data.md).

## Final decisions

- Stage 0 human/mouse specialization: positive.
- Stage 1 eight-organ reconstruction: positive, 3.6–3.8% lower error with automatic
  routing retaining about 96–97% of the revealed-organ gain.
- Stage 2 simple cross-organ sharing: no reliable benefit.
- Frozen OSDR downstream classification: no improvement over raw expression or PCA.
- Training diagnosis: reconstruction emphasizes stable gene/tissue patterns and can
  use typical-value shortcuts; per-gene scaling is an untested future intervention.
- Untouched Track A reconstruction confirmation: frozen and unexecuted.

## Next action if work resumes

1. Restore and checksum-verify the final K8 package.
2. Rebuild public data from the frozen source contracts.
3. Run the untouched reconstruction confirmation without changing membership or
   gates after expression access.
4. Test one predeclared objective-alignment pilot and evaluate it against raw/PCA on
   a stronger downstream benchmark.

Do not reopen seed, organ, layer, or cohort selection on already accessed evidence.
