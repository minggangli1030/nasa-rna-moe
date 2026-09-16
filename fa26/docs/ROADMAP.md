# Fall 2026 roadmap

**Updated:** September 15, 2026  
**Execution state:** paused at a scientific decision gate; no job is queued.

## Immediate decision

Select one biological question before adding data, training a model, or expanding the
response vocabulary. The current evidence supports two bounded candidates:

1. **Cross-flight human-muscle remodeling.** Determine why average mitochondrial and
   muscle-remodeling programs can agree while individual gene responses and classifier
   geometry differ across flights.
2. **Controlled-gravity inflammatory/repair response.** Replicate the MG63 onboard-1g
   comparison in an independent, preferably primary-cell context before generalizing.

A mentor-selected alternative is acceptable if it supplies a cleaner independent contrast.

## Gate 1 — define the claim before execution

Write a short protocol that fixes:

- the biological unit and label;
- primary and negative-control contrasts;
- study/donor grouping and leakage prevention;
- the primary metric and a minimum useful effect;
- expression/PCA comparators;
- allowed preprocessing and gene mapping;
- the interpretation that would be supported by positive, null, or reversed results.

Do not proceed if exposure identity, response detection, and causal contribution are being
treated as the same endpoint.

## Gate 2 — verify independent data

Confirm accession, sample membership, treatment, tissue/cell type, time, dose, pairing,
replicate independence, and raw-source availability. Record exclusions before viewing model
performance. Prefer a held-out study or donor group over random sample splits.

## Gate 3 — run the simplest baseline

1. Raw-expression program scores and a regularized expression head.
2. Fold-fit PCA or another low-dimensional expression baseline.
3. Frozen BridgeRNA embeddings with the same split and metrics.
4. Calibration only when sample size and design support it.

Do not fine-tune merely because an embedding plot separates groups.

## Gate 4 — explanation and specificity

For a useful predictor, report signed score reliance, supporting genes, residual unexplained
evidence, negative controls, and sensitivity to preprocessing and training sources. A pathway
score is not pathway activity; attribution is not causality; a probability is not a causal
percentage.

## Gate 5 — consider adaptation only if warranted

Only after a valid baseline and independent endpoint exist, compare a small last-block or
LoRA update against the frozen model under the same held-out protocol. Stop if gains do not
survive study/donor grouping or do not beat expression/PCA baselines.

## Parallel workstreams

- **Batch effects:** Brain owns objective design and validation. Minggang's spaceflight work
  does not silently absorb this task.
- **Human–mouse:** remains blocked on target definition and ownership, not on computation.

## Required outputs for every future run

Each numbered run must contain a README, frozen protocol, execution record, report, source
manifest, compact machine-readable summaries, and a status marker. Update
[`PROJECT-LOG.md`](PROJECT-LOG.md), the workstream status, and this roadmap after review.

