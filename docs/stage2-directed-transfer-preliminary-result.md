# Stage 2 preliminary result: directed same-compute organ transfer

**Result time:** 2026-07-28 00:10 PDT / 2026-07-28 07:10 UTC  
**Scientific training commit:** `229dfa6dc18302a798734880dc8e3eb60e506e61`  
**Evaluator correction commit:** `46a64b2497cd9ffafd1f6ec3812752fc845d5810`  
**Evidence stage:** GTEx donor-disjoint development analysis

## Primary result

The frozen substitution estimand compares recipient-only A1500 training with
same-compute A750+B750 training, then evaluates on held-out recipient-A GTEx donors.
Positive effects would indicate helpful transfer; negative effects indicate
interference.

All **56/56** directed off-diagonal organ pairs were negative:

- every edge was negative in seeds 17, 42, and 101;
- every paired donor-bootstrap 95% interval excluded zero;
- mean effect: **−3.273%**;
- median effect: **−3.382%**;
- range: **−7.086% to −0.450%**; and
- no seed was selected.

The most negative directed edges were skeletal-muscle←liver (−7.086%),
skeletal-muscle←brain (−6.497%), and skin←brain (−6.209%). The least negative
edges were colon←heart (−0.450%), colon←skeletal-muscle (−0.752%), and
colon←adipose (−0.889%). These examples describe the frozen matrix; they are not
post-hoc selected claims of universality.

## Interpretation

Under a fixed 1,500-draw training budget, replacing half of recipient-organ
training exposure with any other tested organ is worse than using the full budget
on the recipient organ.

This supports three bounded conclusions:

1. recipient-organ data is especially valuable for recipient generalization;
2. indiscriminate cross-organ pooling can cause negative transfer when it displaces
   recipient exposure; and
3. organ-specific adapters or protected specialist updates are justified under
   limited compute/data budgets.

This result complements Stage 1. Stage 1 showed that organ-aligned experts improve
over pooled models and that target-hidden routing preserves most of the gain. Stage
2 now shows a functional training consequence: substituting away from the recipient
organ consistently harms held-out recipient performance.

## Random controls

Twenty of 56 organ-donor edges beat all three random-auxiliary controls in all three
seeds; 13 beat none of them, 16 beat them in one seed, and seven beat them in two
seeds. Donor identity therefore modulates the magnitude of interference, but no
tested organ donor becomes helpful under substitution.

Random controls do not change the primary conclusion that recipient exposure is the
best use of the fixed budget. They motivate the next correspondence analysis: test
whether expert signatures or router compatibility predict *how harmful* a donor is,
not whether substitution becomes positive.

## What this does not show

The matrix does not establish that every form of cross-organ sharing is harmful.
The substitution design deliberately trades away 750 recipient draws. A donor may
still add useful information when all recipient exposure is preserved.

The prospectively frozen additive subset therefore remains essential:

- A1500+B750 versus A1500;
- A1500+B750 versus A1500+random750; and
- A1500+B750 versus A2250.

Those comparisons distinguish donor information from generic heterogeneity and
additional optimization.

The result also does not establish independent-study universality. It is
donor-disjoint and seed-stable within GTEx development data. A genuinely new,
untouched multisource cohort is required for a study-universality claim.

## Evaluator correction audit

Training completed without alteration under commit `229dfa6`. The first evaluator
attempt failed before producing any matrix because the frozen producer stored plain
string identifiers in NumPy object arrays while the evaluator prohibited
pickle-compatible loading.

A code-only correction at `98dcb65`:

- retained every score-cache hash;
- loaded object-backed identifiers only after their producer-recorded SHA256 passed;
- required every object value to be a plain string; and
- changed no score, arm, seed, schedule, checkpoint, cohort, or estimand.

The next attempt failed before producing a matrix because it required bit-exact
pooled scores across arms. An exhaustive audit of all 38,346 frozen comparisons
showed only float32 batch-composition variation:

- maximum absolute difference: `2.384185791015625e-07`;
- maximum relative difference: `2.403279996539277e-07`.

The final code-only correction at `46a64b2` bounded acceptance at
`rtol=5e-7`, `atol=3e-7` and fails closed on material divergence. The combined
Stage 2 focused suite passes 15 tests. No result existed before these corrections.

## Artifact lineage

The final early result uses:

- primary seed 17;
- primary seed 42; and
- checksum-verified parallel `seed101_partial`.

The result directory is
`artifacts/stage2_directed_transfer_229dfa6/evaluation_partial_seed101_fix_46a64b2`.
Its eight-file checksum-manifest SHA256 is
`270fdeb0fcb76c4a08713b92157d6e3ca3f70ab9f38a74df3c2a2fdb8f1db41d`.

The main figure is `directed_transfer_heatmap.png`. The original primary launcher is
continuing its independent duplicate seed-101 lineage as an operational
replication; it must not overwrite or replace this result.

