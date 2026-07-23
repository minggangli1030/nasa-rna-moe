# NASA RNA MoE: current canonical status

**Updated:** 2026-07-22 23:12 PDT / 2026-07-23 06:12 UTC

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
- The metadata-only external-cohort feasibility scout completed successfully and
  found ample candidate study coverage for every target organ.
- The first 250-row metadata review **failed the automated eligibility gate**:
  nominal high-confidence labels still included cell models, non-bulk assays,
  diseased/tumor tissue, nonhuman samples, and active interventions. No cohort has
  been frozen.
- The expanded GEO review and provisional exact-sample resolver are complete. They
  provide 40 pending study decisions and 599 pending sample decisions; they are not
  an accepted cohort and have not opened expression.

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

## Completed metadata-only external scout

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

The scout completed at 2026-07-23 03:53:11 UTC. All checksum entries pass on the VM
and in the local verified backup at
`backups/stage1_k4_external_scout_182207b/`.

It found 13,845 candidate samples across 457 connected series groups:

| Organ | Candidate samples | Series groups | Post-cutoff samples | Post-cutoff series |
| --- | ---: | ---: | ---: | ---: |
| adipose | 1,577 | 55 | 1,047 | 44 |
| brain | 2,537 | 102 | 2,225 | 82 |
| liver | 2,631 | 100 | 2,154 | 78 |
| skeletal muscle | 2,981 | 65 | 2,488 | 50 |
| skin | 4,119 | 144 | 3,296 | 115 |

Every organ clears both the minimum five-series and preferred eight-series feasibility
thresholds after the v11 sample-and-series firewall. The largest connected group is
only 6.98%–13.19% of each organ pool, so no organ is provisionally dominated by one
study. The output includes exactly 50 deterministic manual-review rows per organ
(250 total). It is explicitly **not** a frozen external lockbox and computes no model
score.

Scout report SHA256:
`68ea1bdabb57c63ecea5d8636873e628db606c59b76bd75a94462b216a737786`.

### Round-1 review outcome and repair

Manual inspection showed that the generic organ-label classifier is not precise enough
to select an external cohort. Representative failures included adipose-derived stem
cells, HepG2/stellate/immune cells, Ribo-seq and single-nucleus/spatial assays, mouse
liver, tumor-adjacent tissue, and disease or treatment cohorts whose abbreviations
escaped the original vocabulary. After expanding the parser and exclusion vocabulary,
110 of the 250 nominally eligible round-1 rows are now conservatively downgraded:
adipose 20/50, brain 24/50, liver 30/50, skeletal muscle 9/50, and skin 27/50.
These are triage counts, not an efficacy result or a final precision estimate.

The repair therefore does not try to prove that another regex list is a curator.
`evaluation/build_stage1_k4_external_curation.py` builds a connected-study workbook
with positive healthy/control markers, conservative exclusion/context flags, GEO
links, and explicit blank review fields. Automated A/B/excluded values only prioritize
manual work and can never accept a study or freeze a sample.

Full-pool preflight produced 466 organ-by-connected-study rows (457 unique connected
groups). Strict all-sample priority-A counts are adipose 2, brain 8, liver 12,
skeletal muscle 4, and skin 10; the remaining viable groups are priority B and require
manual review. This confirms that broad feasibility remains, while also showing why
study-level curation—not automatic label recovery—is the current bottleneck.

The production workbook completed from isolated code commit
`f307108a5d3e9325b014d9171aa6522ebc6751bc` at 2026-07-23 05:24:34 UTC:

- VM result:
  `/media/volume/moe-reboot/results/stage1_k4_external_curation_f307108`
- local verified backup:
  `backups/stage1_k4_external_curation_f307108/`
- workbook SHA256:
  `965b4a2f40f28d94a1de7317fbaa4c97ae4014426195b287c125e92dc5c7b5e0`
- sample-triage SHA256:
  `b2645444af6ceb65df5d4b927057934ee9c4c37c3ab6912a978cf1a0568d7085`

Every checksum passes remotely and locally.

### Expanded GEO and exact-sample review

The GEO series-level review was expanded to the first 40 non-excluded connected
groups per organ: 200 organ/group rows and 226 pinned GEO series records. It reads
only public series title, summary, design, PubMed, BioProject, and sample count; it
does not request supplementary files, SRA objects, or expression.

- implementation commit:
  `a89e2e988e8e8e5467a56d16a85a5f173dd3dff6`
- VM result:
  `/media/volume/moe-reboot/results/stage1_k4_geo_review_a89e2e9`
- local verified backup:
  `backups/stage1_k4_geo_review_a89e2e9/`
- selected-study review SHA256:
  `19373eafa0e5d1fdf1127033a669c79232616adbe1d28fd26b6bd01c274cfc3b`
- GEO-series metadata SHA256:
  `9abf44b3a5f0d4511fd9636d2707a300f1206f7efa579a75a49f2c8ffa824edb`

Manual reading of the pinned designs produced a provisional eight-group shortlist
per organ. The review caught a likely cross-series donor reuse between adipose
`GSE306796` and `GSE287627`; the latter was removed and replaced before sample
resolution. This is evidence that GEO connected components alone do not establish
donor independence.

The exact metadata-only resolver completed at 2026-07-23 05:59:48 UTC. It binds the
source hashes, requires post-v11 samples, rejects classifier-ineligible matches, and
leaves all study, sample, donor, and near-duplicate decisions pending. It resolved:

| Organ | Provisional studies | Provisional selector matches |
| --- | ---: | ---: |
| adipose | 8 | 61 |
| brain | 8 | 126 |
| liver | 8 | 47 |
| skeletal muscle | 8 | 263 |
| skin | 8 | 102 |

These 599 rows are a review workload, not the final analysis size. Ambiguous cases
such as technical/biological replicates, tissue regions, graft donors, and skin
compartments are explicitly marked unresolved.

The initial 601-row v1 result remains preserved for audit at the paths below, but it
is no longer the current review sheet:

- implementation commit:
  `8e6d95b66d4ee26e2b226ee6ddab839e712b9e24`
- shortlist SHA256:
  `e7569661edbccc7d0ad075a184851b969c019b12067c19a1458012d7aa1de3f8`
- VM result:
  `/media/volume/moe-reboot/results/stage1_k4_external_sample_review_8e6d95b`
- local verified backup:
  `backups/stage1_k4_external_sample_review_8e6d95b/`
- full checksum-manifest SHA256:
  `da0ff1b8e5ae5e4d49e3699e176d88037467bfde41627d2fedfd549960feaca3`
- provisional sample-review SHA256:
  `4b5dead31111c8ae80c3d079d6ee73db4da45e6a61d7cc1a4233ae9fb4dcd3e8`
- provisional study-review SHA256:
  `9c6712ccc9772de39388dd846f446db2391eb809695924854739ccc5f5605fb5`

All checksum entries pass on the VM and Mac. The report states
`expression_values_read=false`, `efficacy_scoring_performed=false`, and
`external_lockbox_frozen=false`.

### Liver reserve amendment

Publication/series review rejected provisional liver group `GSE304242`: its official
design centers on hepatic cell-model comparisons, while the three liver-RNA samples
do not provide defensible donor or health semantics for this strict cohort. The
rejection is preserved rather than silently relabeling those samples.

A targeted metadata-only reserve fetch pinned `GSE284901`, an ENCODE4 unreplicated
bulk total-RNA sample from the right lobe of one adult liver. ARCHS4 metadata gives
BioSample `SAMN45079858` and donor `ENCDO757VPQ`; hypertension is explicitly retained
as a non-hepatic comorbidity rather than calling this a nominally healthy donor.

- reserve-fetch implementation commit:
  `119ed2d0f12f391d28c20a0dd9ed54a5f1c4b573`
- reserve VM result:
  `/media/volume/moe-reboot/results/stage1_k4_geo_reserve_review_119ed2d`
- reserve local verified backup:
  `backups/stage1_k4_geo_reserve_review_119ed2d/`
- reserve selected-study SHA256:
  `9afb4067935f5602241f0d4355c8a052f72475d655607c981fbbb4ec6702cf84`

The amended v2 resolver replaces the three ambiguous `GSE304242` rows with exact
sample `GSM8693930`, reducing liver from 49 to 47 pending rows and the total from
601 to 599 without changing the eight-groups-per-organ review target.

- v2 implementation commit:
  `8734e5e1486713850ab71cb386b51cc785fbfef7`
- amendment SHA256:
  `6cd1451da17e2d5877de6617e22e31ff3e1c6e97877cb8890407038a828c75a8`
- v2 VM result:
  `/media/volume/moe-reboot/results/stage1_k4_external_sample_review_v2_8734e5e`
- v2 local verified backup:
  `backups/stage1_k4_external_sample_review_v2_8734e5e/`
- v2 full checksum-manifest SHA256:
  `a3f5a58122fd58acc5f0c9ba2a56898de8e1bad53f44d8b7b9669ee15765ddcc`
- v2 provisional sample-review SHA256:
  `54d58c415568d73a8d962bb1b0e47eb75bd02393ad7a5f9ea1da839fff8594fd`
- v2 provisional study-review SHA256:
  `b4b133386a3b487a87739829932df4ea76d534fca5c41865c5f9a79897dd2bae`

Every v2 checksum passes centrally and locally. All 224 repository tests pass. The
v2 report still states `manual_decisions_complete=false`; this is a better review
sheet, not a cohort freeze.

Quick verification commands:

```bash
ssh moe-reboot 'cat /media/volume/moe-reboot/results/stage1_k4_external_scout_182207b/SCOUT_STATUS'
ssh moe-reboot 'cd /media/volume/moe-reboot/results/stage1_k4_external_scout_182207b && sha256sum -c FULL_SHA256SUMS'
```

## Next decision tree

1. **Feasibility passed:** every organ has 44–115 temporally new connected series,
   far above the preferred eight-series bar.
2. **Automated eligibility failed:** preserve round 1 as the rule-development audit;
   do not treat its broad candidate pool as confirmation data.
3. **Current gate — exact sample/donor review:** verify every provisional study and
   selected sample against GEO/publication/BioProject/Biosample evidence. Resolve
   donor IDs, biological versus technical replicates, regions/compartments, and
   cross-study near duplicates. Replace failures from the unused reviewed reserves;
   do not inspect expression.
4. **Preregister before freezing:** compute cluster-aware effective sample size and
   power from the accepted metadata, then freeze exact ordered sample IDs, organ
   labels, group IDs, gene mapping, random-control assignments, mask, power analysis,
   checkpoint and router hashes, evaluator code, and mutually exclusive decision
   branches.
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
5. `artifacts/stage1_k4_external_scout/sample_review_shortlist.json` — provisional,
   metadata-only sample selectors; not a frozen cohort.
6. `artifacts/stage1_k4_external_scout/sample_review_amendment_v2.json` — explicit
   rejection and one-for-one liver reserve amendment.
7. `progress.md` — append-only historical chronology and older experiment detail.
