# GTEx-to-ARCHS4 organ-specialization program

**Drafted:** 2026-07-24

## Purpose and relation to the completed result

This program extends Stage 1; it does not replace or reinterpret the completed
ARCHS4-to-GTEx result. The existing frozen K4 candidate remains an independently
evaluated model with a `full_external_pass` on GTEx V11. Once GTEx is used to fit a
new candidate, GTEx becomes development data for that candidate and cannot provide
its external confirmation.

The new primary question is:

> Can clean, donor-controlled organ supervision learned from GTEx improve masked
> reconstruction on heterogeneous, study-disjoint ARCHS4 human bulk RNA-seq?

A larger organ-versus-random gap is a possible outcome, not a training objective or
selection criterion.

## Prospective organ inventory

Organ selection uses metadata availability only. No ARCHS4 expression value or model
effect may contribute. The provisional inclusion rule is:

1. the organ is represented in the existing audited UBERON mapping;
2. the exact GTEx V11 RNASeQC header contains at least 250 eligible donors after
   removing cell/culture compartments and the four historical EN-TEx donors; and
3. after the historical ARCHS4-v11 accession and connected-series firewall, the
   current human ARCHS4 metadata contains at least 500 high-confidence samples from
   at least 30 connected studies submitted after the 2021-11-13 cutoff.

The preliminary metadata audit selects eight organs:

| Organ | GTEx samples | GTEx donors | Post-firewall ARCHS4 samples | ARCHS4 groups |
| --- | ---: | ---: | ---: | ---: |
| adipose | 1,293 | 817 | 626 | 34 |
| brain | 3,030 | 385 | 1,393 | 57 |
| colon | 890 | 619 | 774 | 48 |
| heart | 909 | 571 | 601 | 46 |
| liver | 261 | 261 | 1,072 | 44 |
| lung | 601 | 601 | 1,007 | 50 |
| skeletal muscle | 814 | 814 | 2,277 | 48 |
| skin | 1,397 | 842 | 2,291 | 77 |

GTEx counts use exact header membership, `RNA:Total RNA`, `TruSeq.v1`, and intact
tissue sites. Brain excludes spinal cord and skin excludes cultured fibroblasts.
ARCHS4 counts are metadata-only automated high-confidence candidates and still
require manual study/sample review before a lockbox is frozen.

The K=8 set is provisional until a reproducible inventory report, source hashes, and
review requirements are committed. It may change only because a metadata gate fails,
never because of expression or efficacy.

## Model families

All candidates use the same 15,448 ordered canonical genes, one TPM-to-`log1p`
transform, 30% masking during training, the frozen 4,634-gene target-hidden router
panel where structurally available, and seeds 17, 42, and 101.

### Strict reversal

The strict primary family has no ARCHS4-derived weights:

1. train a pooled `ExpressionPerformer` trunk from random initialization on GTEx;
2. freeze the selected pooled trunk;
3. train eight residual organ adapters;
4. train three matched eight-adapter random-control banks; and
5. fit a target-hidden blind organ router using GTEx development rows only.

This family answers the clean GTEx-to-messy ARCHS4 question.

### Practical transfer sensitivity

A secondary family may freeze the existing ARCHS4-trained trunk and refit only
adapters/router on GTEx. It is labeled `archs4_pretrained_gtex_adapted`, not
GTEx-only. It tests whether clean GTEx supervision improves a broadly pretrained
model, but it cannot support a strict train/test reversal claim.

### Required controls

- GTEx-only pooled model;
- true-organ K8 adapter bank;
- three donor-atomic, organ-balanced random K8 banks;
- pooled residual adapter with the same adapter dimension;
- target-hidden blind router;
- true dispatch, blind dispatch, pooled, pooled-adapter, assigned-random, and
  mapped-random evaluations; and
- the already frozen ARCHS4-trained K4 candidate as a prespecified reference, not a
  rescue candidate.

Pooled and specialist training must use the same GTEx row union. Update budgets,
sample streams, masks, and parameter accounting must be frozen before full fitting.

## GTEx development partitions

All rows from a donor remain in one split across every organ and tissue site. The
initial contract uses an outcome-free SHA-256 donor ranking with 80% development
training and 20% calibration. Calibration selects pooled checkpoints, training
duration, and at most one preregistered capacity setting. After selection, the final
candidate may be refit on train plus calibration under a predetermined update count,
without an internal GTEx efficacy claim.

Random partitions are donor-atomic and approximately balance the eight-organ sample
vector across shards. Every sample from a donor receives the same random label
within a partition seed.

## Staged ARCHS4 evaluation

ARCHS4 expression remains sealed until the cohort, candidates, evaluator, and
decision tree are frozen. Evaluation is human-first:

1. **Core tissue transfer:** intact human bulk tissue with defensible organ labels.
2. **Non-diseased versus disease:** report the core non-diseased/control stratum and
   a separately frozen disease stratum.
3. **Tumor stress:** analyze tumor and matched/non-tumor tissue separately; do not
   let tumor prevalence define the primary organ result.
4. **Spaceflight or space-analog stress:** separate flown, ground-control, and
   terrestrial studies when metadata and study counts support a defensible stratum.
5. **Noise-exposure curve:** optionally fine-tune on frozen ARCHS4 development
   studies at 0%, low, medium, and full prespecified exposure. Each exposure uses the
   same sample-order prefix and may never include a lockbox study.
6. **Mouse sensitivity:** optional and separate after ortholog remapping. Mouse may
   not be pooled into the primary human estimand.

The primary ARCHS4 estimator gives equal mass to connected studies within organ and
then equal mass to organs. Disease, tumor, spaceflight, species, platform, and
library variables are prespecified strata or moderators, not opportunistic cohort
rescue variables.

## Fine-tuning experiment

Fine-tuning is a dose-response experiment, not iterative exposure to the lockbox.
Before any lockbox expression access, freeze:

- the ARCHS4 development-study IDs available for fine-tuning;
- nested exposure levels and exact ordered sample prefixes;
- whether trunk, adapters, or both are trainable;
- update counts and learning rates;
- one checkpoint rule using development studies only; and
- all candidate hashes.

The main comparison is GTEx-only K8 at 0% exposure versus the same starting
checkpoint after each frozen exposure dose. A separately initialized ARCHS4-only
baseline is required to determine whether fine-tuning adds value beyond simply
training on ARCHS4.

## Mechanical smoke gate

Before full GTEx training, a synthetic/small-data smoke must verify:

- donor-disjoint GTEx train/calibration partitions;
- every organ and random shard appears in both partitions;
- no random partition splits a donor;
- pooled, organ, random, pooled-adapter, router, and scoring paths load and finish;
- pooled and every expert see their frozen exposure budgets;
- target genes are hidden identically from models and router;
- checkpoint round trips preserve finite tensors and hashes; and
- no ARCHS4 expression or efficacy result is accessed.

Smoke metrics establish software integrity only. They cannot select K, architecture,
training duration, or a candidate.

## Decision logic

- A GTEx-trained organ model is supported only if blind K8 beats its GTEx-trained
  pooled model, pooled adapter, and every mapped random control with positive
  study-clustered intervals and stable seeds.
- True K8 must beat every assigned random control, showing that biological
  partitioning—not added capacity—creates the gain.
- A successful core-tissue result with failure under disease/tumor/space stress
  supports organ as a baseline axis and motivates controlled within-organ experts.
- Failure on all ARCHS4 stages suggests GTEx-specific specialization or insufficient
  GTEx-only representation learning.
- No result may retroactively change organs, exposure doses, strata, masks, or
  thresholds on the same lockbox.

Stage 2 begins only after this program produces a frozen candidate and its
prespecified ARCHS4 evaluation. Within-organ latent states, transfer, pathways, and
gene-level interpretation remain downstream analyses.
