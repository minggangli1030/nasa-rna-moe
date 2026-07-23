# Stage 1 external dataset intake and one-time validation plan

Status: **awaiting a PI-recommended dataset; K4 candidate frozen; no external
expression access authorized.**

This is the operational handoff for the interval between receiving a candidate
external dataset and running the one-time Stage 1 confirmation. It preserves the
scientific choices already made and prevents a convenient new dataset from silently
changing the estimand.

## Short answer: do not jump directly to scoring

When a dataset becomes available, first request and inspect its metadata, data
dictionary, sample manifest, publications, provenance, and file checksums. Expression
must remain unopened until the dataset role, independence, eligibility, exact cohort,
and evaluator have been frozen.

The shortest valid path is:

1. metadata-only intake and overlap audit;
2. assign the dataset a permitted evidence role;
3. freeze the exact cohort and evaluator;
4. pass a synthetic or historical-data smoke test;
5. extract and score the external expression exactly once; and
6. execute the preregistered decision branch without rescue tuning.

## Frozen project state

The development candidate may not change in response to a new dataset:

- model: K4-EPE;
- active specialists: brain, liver, skeletal muscle, and skin;
- adipose: pooled fallback;
- training seeds: 17, 42, and 101, all retained;
- deployment: frozen target-hidden observed-input router;
- controls: pooled trunk, pooled-residual adapter, three connected-study-preserving
  random K4 banks, and their calibration-frozen deployment mappings;
- K5 and higher-exposure K4: development sensitivities only, not external rescue
  candidates; and
- old internal test: permanently excluded from confirmation.

Canonical candidate bindings:

| Artifact | SHA256 |
|---|---|
| Candidate manifest | `c941504037d885b74a1555d97109ff31ada9a60545b52e8c244fdccafe3ad9ee` |
| Pooled checkpoint | `080a8a36d2090c3a823cd3995d758d1205b0ad02c1c38c06e6763c5a7ebfd789` |
| Router artifact | `10ecef514ee2a7ec3e875d584227230949edf16b192495e4c2bb3e82bd3c4906` |
| Router report | `2f5600eabe7a9c48af0f55b86beeea9a0fe6a629e5863fe5aea2257b36e16a15` |
| Random deployment mappings | `454bad6b2da16232ce5c8e02f6cd4224f2bc57b7ef699f1c17aa76ab910d458e` |
| Ordered 15,448-gene universe | `3332cb312000e426a866d669b3ba9b6206da50d70094fb5f9d30ef168e860dff` |

The candidate is preserved on persistent `moe-reboot` storage and in
`backups/stage1_k4_final_refit_e8c0383/`.

## Gate 1: metadata-only dataset intake

Request these items before expression:

- dataset name, version, owner, license, and stable source;
- sample manifest with sample, donor, assay, tissue, compartment, condition, and
  replicate identifiers;
- study, publication, BioProject, BioSample, and repository accessions;
- species and assay documentation;
- processing description and gene identifier convention;
- available raw counts, normalized values, and relevant file checksums; and
- confirmation of whether the data have been published through GEO, SRA, ARCHS4, or
  another aggregate used during development.

Fail or hold the intake if the metadata cannot distinguish:

- human from nonhuman material;
- intact tissue from cell lines, organoids, primary cultures, or sorted cell
  fractions;
- bulk RNA-seq from single-cell, single-nucleus, spatial, Ribo-seq, or other assays;
- normal/healthy/untreated/baseline from tumor, disease, adjacent-normal,
  intervention, or stimulated tissue;
- biological donors from technical replicates; or
- relevant compartments such as epidermis versus dermis.

Before scores exist, explicitly decide policy for genuine edge cases such as
postmortem tissue, obesity, non-organ comorbidities, adjacent normal, and pretreatment
baseline. Apply that policy consistently and preserve every rejection reason.

## Gate 2: independence and evidence role

Compare sample, donor, study, publication, BioProject, BioSample, repository, and
connected-series identifiers against all historical development data, including the
old internal test. Near-duplicate checks must be planned before expression and
executed once expression is legitimately available.

Assign exactly one role before scoring:

### `primary_multistudy_confirmation`

Permitted only if the accepted cohort:

- covers all five target organs;
- has at least five and preferably eight independent connected studies per organ;
- is disjoint from development by sample and connected study;
- has defensible donor/replicate handling; and
- supports the frozen study-balanced, organ-balanced estimator.

### `secondary_donor_controlled_validation`

Appropriate for a clean single consortium or laboratory cohort with explicit donors
and all five organs. It can provide strong donor-level and domain-shift evidence, but
one source alone cannot establish broad cross-study generalization.

### `supplemental_partial_organ_validation`

Appropriate when only some target organs are available. It may test those organs but
cannot produce the full Stage 1 decision.

### `reject_or_development_only`

Required when the candidate overlaps development, lacks essential provenance, mixes
incompatible biological objects without separable labels, or cannot support the
frozen expression contract.

If a PI-recommended dataset is donor-controlled but single-source, preserve the
current 40-study GEO design as the planned multisource confirmation or robustness
cohort. Do not merge the two opportunistically after viewing effects.

## Gate 3: exact cohort and expression contract

Before opening values, freeze and hash:

- exact accepted sample IDs and order;
- organ, donor, biological-replicate, technical-replicate, study, and connected-group
  assignments;
- inclusion/exclusion ledger and evidence links;
- external source version and input file hashes;
- gene identifier translation and repeated-symbol aggregation;
- exact ordered 15,448-gene output and missing-gene policy;
- expression-space declaration and normalization order;
- QC rules and all permitted sample drops;
- deterministic external scoring mask;
- extraction code and expected report schema; and
- a firewall report proving that rejected and overlapping rows cannot enter scoring.

No external sample may be used for software debugging. Smoke tests must use synthetic
data, development-only historical data, or a staging set permanently excluded before
the lockbox is frozen.

## Gate 4: freeze the evaluator

The evaluator must be implemented, tested, code-hashed, and bound to the candidate
before external expression is loaded.

Primary aggregation:

1. compute each seed-level masked reconstruction loss;
2. average seeds 17, 42, and 101 within each sample;
3. average samples within each connected study;
4. give equal study mass within each organ; and
5. give equal mass to all five organs.

Primary and supporting comparisons:

- blind K4 versus pooled trunk;
- true-organ K4 with adipose fallback versus pooled;
- true-organ K4 versus each assigned-random K4 control;
- blind K4 versus each calibration-frozen mapped-random control; and
- blind K4 versus the pooled-residual adapter.

Uncertainty and multiplicity:

- at least 10,000 paired connected-study bootstrap draws;
- confidence intervals clustered by connected study;
- Holm control across the three random-control family comparisons;
- prespecified seed-stability and per-organ safety checks; and
- the exact one-sided 40-study sign diagnostic reported as supporting design
  evidence, not as a replacement for the relative-MSE estimator.

Frozen practical gates:

- at least 3% blind K4 relative-MSE gain versus pooled;
- at least 3% true-organ gain versus pooled;
- at least 3% true-organ gain versus every assigned-random partition;
- positive clustered evidence versus every mapped-random control;
- positive clustered evidence versus pooled residual;
- positive residual-Pearson evidence for pooled comparisons;
- blind router recovers at least 80% of true-dispatch gain;
- same positive direction at seeds 17, 42, and 101;
- seed SD no greater than half the mean effect;
- nonnegative true-dispatch effect for every active organ; and
- all provenance, overlap, target-hiding, cache, and alignment checks pass.

Natural-frequency estimates, fixed averaging, oracle headroom, per-organ effects, and
router confusion are diagnostics only. They cannot rescue a failed primary gate.

## Gate 5: one-time execution

After Gates 1–4 pass:

1. create a read-only, checksum-bound external input root;
2. validate the candidate bundle and evaluator hashes;
3. extract the accepted rows once using the frozen expression contract;
4. create one immutable prediction/loss cache for every frozen arm;
5. verify sample order, gene order, mask identity, checkpoint identity, and cache
   completeness before aggregation;
6. execute the frozen estimator and decision tree once;
7. write terminal markers only after checksum validation; and
8. preserve the full result on persistent VM storage, a verified local backup, and a
   pushed documentation commit.

No best seed, new expert count, alternate organ subset, threshold change, control
remapping, or checkpoint selection is permitted after an external effect is visible.

## Frozen decision precedence

1. `technical_fail`: provenance, independence, alignment, masking, cache, or execution
   failure; repair without interpreting effects.
2. `no_external_gain`: K4 does not establish the prespecified pooled improvement.
3. `generic_capacity_or_partition_fail`: the effect does not survive pooled-residual
   or matched-random controls.
4. `router_bottleneck`: true dispatch passes, but blind routing or recovery fails.
5. `full_external_pass`: blind routing, true dispatch, pooled, random, pooled-residual,
   stability, per-organ safety, and technical gates all pass.
6. `inconclusive`: a frozen residual pattern not covered above.

A failed K4 result may not be rescued by testing K5 or a different K4 arm on the same
external cohort.

## Dataset-arrival checklist

When the PI responds:

1. record the dataset name and do not download/open expression yet;
2. obtain its metadata manifest, data dictionary, source/version, and publications;
3. run the metadata and historical-overlap audit;
4. issue a short intake report assigning one permitted evidence role;
5. resolve only the remaining policy questions with the PI;
6. freeze the exact cohort and evaluator artifacts;
7. run the nonexternal smoke test; and
8. only then authorize the one-time validation.
