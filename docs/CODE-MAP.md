# Code map

```text
research/
  specialization/
    core/          shared trainer, MoE/router, adapter bank, deterministic data utilities
    evaluation/    reconstruction, blending, organ and budget-controlled comparisons
    preprocessing/ public-expression preprocessing
    tests/         small synthetic training and evaluation contracts
  spaceflight/     encoder input contracts, inference, heads, attribution, diagnostics
    tests/         normalization/inference/statistical checks
scripts/           portable distributed-training launcher
docs/              systems walkthrough, results, provenance, and validation
```

Start at the phase READMEs: [specialization](../research/specialization/README.md) and [spaceflight](../research/spaceflight/README.md). Then use [the systems walkthrough](SYSTEMS.md) for distributed training and [results](RESULTS.md) for the scientific evidence.

The public portfolio retains selected entry points and their local import dependencies. One-off cohort builders, superseded pilot variants, report generators, and most historical tests are omitted. The complete original local research repository is unchanged, and the pre-reorganization public source remains in earlier commits. No experiment code was merged merely because filenames looked similar.
