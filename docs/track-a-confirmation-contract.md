# Track A pristine reconstruction confirmation contract

**Frozen:** 2026-08-11

**Status:** scientific design and pre-expression membership frozen; deliberately
unexecuted

The machine-readable contract is
`artifacts/final_evaluation/track_a_confirmation_v1/protocol.json`. It confirms one
candidate only: the final frozen three-seed K8 package. K4-EPE remains separate
adaptive development evidence and cannot enter this confirmation.

The complete metadata-only candidate membership contains all 23,975 mechanically
eligible ARCHS4 2.7 rows across the eight frozen organs. The exact parquet is versioned
beside the protocol at SHA256
`7e7ca561bbddf99235b7be5802eabd98d5f7bf6b241ecdb08f8dd23060f5cf14`.
It has zero original Stage-1 or explicit-GTEx overlap rows. No expression, nonzero-gene
QC, model score, or efficacy outcome was accessed while freezing it.

After future one-time expression access, the only allowed sample exclusion is the
already frozen threshold of fewer than 14,000 nonzero genes. There are no replacement
samples, replacement studies, manual relabels, or threshold changes. If any of the
eight fixed organs retains fewer than eight series values or 50 samples, the workflow
must stop automatically before model scoring and report cohort infeasibility. It may
not drop the organ and recompute the aggregate.

The single primary comparison is blind hard routing versus pooled reconstruction.
Confirmation requires a positive relative-MSE improvement in all three seeds, a
positive lower 95% bound from the paired series-within-organ bootstrap after averaging
the three seed effects, and no organ-by-seed harm greater than 2%. Soft routing and
true-organ routing are mandatory supportive results. The three already frozen random
K8 axes are negative controls and cannot define success.

Total-parameter-matched generic K8 is intentionally outside Track A. Capacity
attribution is a separate future experiment requiring both expression-cluster K8 and
organ-balanced random K8 controls. Until that experiment runs, the result cannot be
attributed uniquely to organ biology rather than stored capacity.

This protocol does not authorize expression access. Before execution, a second
manifest must bind runtime paths, artifact checks, final evaluator/launcher hashes,
and a mechanical smoke. That manifest may add execution hashes only; it cannot alter
membership, QC, conditions, estimands, gates, or interpretation. Per the August 17
schedule, no further Track A work occurs before the presentation.
