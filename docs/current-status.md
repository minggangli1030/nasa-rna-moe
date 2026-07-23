# NASA RNA MoE: current canonical status

**Updated:** 2026-07-22 20:03 PDT / 2026-07-23 03:03 UTC

Read this file first. It is the compact operational and scientific handoff. Use
`docs/stage1-k4-final-refit.md` for the full Stage 1 decision history and
`progress.md` only when older chronology or exact intermediate results are needed.

## Current state

- Stage 0 interspecies training and corrected evaluations are complete.
- Stage 1 development nominated K4-EPE: brain, liver, skeletal-muscle, and skin
  specialists with pooled fallback for adipose.
- The final train+calibration-only K4 refit is complete, frozen, checksummed, and
  independently backed up. It produced no internal efficacy comparison.
- External confirmation has **not** started. No external expression value has been
  opened or scored.
- A metadata-only external-cohort feasibility scout is running on `moe-reboot`.

The strongest defensible conclusion remains: organ identity is the strongest tested
conditional specialization axis and K4-EPE is the frozen development candidate. It is
not yet externally confirmed. The old organ-fixed versus random-fixed failure remains
valid; conditional routing, not unconditional averaging, is the primary MoE estimand.

## Frozen Stage 1 candidate

Architecture and fit contract:

- pooled trunk frozen from the Stage 1 pooled checkpoint;
- four independent dimension-64 residual adapters for brain, liver, skeletal muscle,
  and skin;
- adipose dispatches to the pooled fallback;
- target-hidden five-class observed-input router;
- training seeds 17, 42, and 101 retained with no best-seed selection;
- 2,657 development-only rows: 1,815 training plus 842 calibration;
- exactly 1,500 updates per seed, batch size 8, 12,000 deterministic balanced draws;
- controls: three study-atomic random K4 banks plus one pooled residual adapter; and
- no old-test access, external access, early stopping, or internal efficacy scoring.

Final-refit implementation commit:
`e8c0383fd1833f180f26af56f09e83a5b3f676d9`.

Canonical artifacts:

- VM result:
  `/media/volume/moe-reboot/results/stage1_k4_final_refit_e8c0383`
- local verified backup:
  `backups/stage1_k4_final_refit_e8c0383/`
- full checksum-manifest SHA256:
  `db17084f813abd19dd11297570a2befc48aa9c7d93f9755216780c3418f0aca0`
- candidate-manifest SHA256:
  `c941504037d885b74a1555d97109ff31ada9a60545b52e8c244fdccafe3ad9ee`
- router-report SHA256:
  `2f5600eabe7a9c48af0f55b86beeea9a0fe6a629e5863fe5aea2257b36e16a15`

Completion markers include `FINAL_REFIT_COMPLETE`, `ROUTER_FROZEN`,
`FINAL_CANDIDATE_FROZEN`, and `READY_FOR_VERIFIED_BACKUP`. The portable-candidate
validator and the full 184-file checksum manifest pass centrally and on the Mac.

## Active metadata-only external scout

Purpose: determine whether an untouched, multisource, post-v11 cohort can cover all
five organs before any expression access.

Production code commit:
`182207bbc85c30df80f17cd45784d5c87f8a52a7`.

Runtime:

- clean checkout: `/home/exouser/nasa-rna-moe-182207b`
- tmux: `stage1_k4_ext_scout_182207b`
- result root:
  `/media/volume/moe-reboot/results/stage1_k4_external_scout_182207b`
- protocol: `artifacts/stage1_k4_external_scout/protocol.json`
- protocol SHA256:
  `1ab183ba9d31851a2f605d51d29eb9a282b7581b63a56e6eacdd9693276dc1c4`

The scout reads only `meta/info` and `meta/samples` from the pinned current ARCHS4
human HDF5 object through HTTP byte ranges. The 62,257,385,524-byte object is bound by
its ETag and 2026-07-07 Last-Modified value. Its metadata describes 1,098,771 human
samples. `data/expression` is never indexed.

Before organ classification, the scout excludes:

- every accession present in ARCHS4 v11; and
- every sample sharing any GEO-series token with v11.

Historical firewall hashes:

- ordered v11 accession SHA256:
  `784035aa00284f2a8c0c500a391f88d9c6986621c22dd7f622a06284d731eba0`
- v11 accession/series mapping SHA256:
  `ffce20e908770672571d3e75755cb00643c330da8899424255b6a245e9936523`

The output is a candidate metadata pool plus 50 deterministic manual-review rows per
organ. It is explicitly **not** a frozen external lockbox and computes no model score.

Quick status commands:

```bash
ssh moe-reboot 'cat /media/volume/moe-reboot/results/stage1_k4_external_scout_182207b/SCOUT_STATUS'
ssh moe-reboot 'tail -5 /media/volume/moe-reboot/results/stage1_k4_external_scout_182207b/current_export.log'
ssh moe-reboot 'tmux list-sessions'
```

## Next decision tree

1. **Technical scout failure:** repair and rerun the identical metadata-only protocol.
   There is no external effect to interpret.
2. **Insufficient study coverage:** add a separately pinned metadata source such as
   recount3 or a curated resource. Do not lower the five-study minimum or inspect
   expression to select samples.
3. **Feasible coverage:** require at least five, preferably eight, temporally new
   connected studies per organ. Manually review labels and audit publication,
   BioProject, Biosample, donor, accession, connected-group, and near-duplicate links.
4. **Freeze before expression:** freeze exact ordered sample IDs, organ labels, group
   IDs, gene mapping, random-control assignments, mask, power analysis, checkpoint and
   router hashes, evaluator code, and mutually exclusive decision branches.
5. **One-time confirmation:** only then request expression, build the score cache once,
   and evaluate blind K4, true dispatch, pooled, pooled-residual, and all matched random
   controls. K5 and K4-total are not rescue candidates on that lockbox.

## Non-negotiable safeguards

- The previously inspected 1,018-row internal test is historical only and may never
  confirm or tune the final K4 model.
- Do not select a best seed, average weights, reopen K, or retune gates after seeing an
  external effect.
- Do not treat the metadata scout as evidence for or against organ specialization.
- Do not delete or relabel the failed organ-fixed averaging control.
- A favorable external result would support the Stage 1 architecture, not automatically
  establish Stage 2 biological mechanisms.

## Read order and source of truth

1. `docs/current-status.md` — current state, paths, hashes, next action.
2. `docs/stage1-k4-final-refit.md` — scientific reasoning, completed evidence, frozen
   external estimands and branches.
3. `artifacts/stage1_k4_final_refit/protocol.json` — final-refit machine contract.
4. `artifacts/stage1_k4_external_scout/protocol.json` — metadata-scout machine contract.
5. `progress.md` — append-only historical chronology and older experiment detail.

