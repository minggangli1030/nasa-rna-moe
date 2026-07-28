# Stage 2 seed-stability diagnosis

**Status:** protocol frozen before diagnostic outcomes

## Why this is now the direct next step

The first additive transfer map is adequate as a transparent preliminary result for
the July 30 presentation, but it is not adequate as the Stage 2 final product. Only
liver←skin was positive in every original seed, while several small mean-positive
effects changed sign. A few favorable means cannot support a general organ-transfer
rule.

The current result is preserved without reinterpretation. The strongest stable
findings remain:

- all 56 same-compute substitutions were harmful in all three seeds;
- all eight donor additions were worse than the A2250 additional-recipient-exposure
  control in all three seeds; and
- liver←skin was the only named addition positive in all three original seeds.

The diagnostic asks whether the mixed additive signs arise primarily from the
frozen pooled representation, from adapter/mask optimization, or from an
edge-specific interaction. It does not search for a best seed.

## Frozen factor design

Cross three frozen pooled trunks, seeds 17, 42, and 101, with three new independent
optimization replicates, seeds 211, 223, and 227. Each of the nine combinations
runs the same 24-arm schedule:

- eight A1500 recipient-only references;
- the unchanged eight A1500+B750 named-donor edges; and
- eight A2250 additional-recipient controls.

The sample-draw schedule is identical across combinations. Within each combination,
all paired arms share the trunk, initialization, training-mask seed, and loader
seed. Adapter training uses deterministic full precision rather than mixed
precision. This first diagnosis intentionally couples initialization, masks, and
loader order into one optimization-replicate factor. If that factor dominates,
the next diagnostic will separate those components.

Frozen hashes:

- implementation commit:
  `70f604f28d32a0319022c0140d76f9ad3a125c94`
- training schedule:
  `066144402245cac3114fee71a7dd8e0cfc4a6f4f74b9df405510e9b4e7b0c9a3`
- arm definitions:
  `e206e20ae46721d6d353f0179afd9f4acbc0a19cb81d9d89e8b7018d24063c9d`
- schedule report:
  `199582d518da149f237b0b1b4819e53e8c1cab0f1a8f3d8a5e474cd05874bf65`
- machine-readable protocol:
  `artifacts/stage2_organ_expert_mechanism/seed_stability_protocol.json`

## Prespecified edge classification

An edge is `stable_helpful` only if:

- at least eight of nine crossed combinations are positive versus A1500;
- all three trunk-averaged effects are positive;
- all three optimization-averaged effects are positive;
- the crossed trunk/optimization/donor bootstrap interval is above zero; and
- the mean effect is at least +0.5%.

`stable_harmful` uses the symmetric negative rule. Everything else is
`unstable_or_negligible`.

The A2250 comparison remains a separate compute-allocation control. A donor can be
reproducibly informative versus A1500 without being the best use of the extra 750
updates.

## Frozen decision branches

1. **Raw addition viable:** at least three of eight edges are stable helpful.
   Continue to a larger confirmation and directed mechanism/router predictor.
2. **Map reproducible but not helpfully transferable:** at least six of eight edges
   have stable signs, but fewer than three are helpful. Pivot raw addition toward
   negative-transfer avoidance or a recipient-protected selective-sharing
   architecture.
3. **Optimization instability confirmed:** fewer than six edges have stable signs.
   Test one recipient-protected sharing implementation with the same crossed design,
   then pivot if stability still fails.

These are development decisions, not external-confirmation claims. A new untouched
multisource cohort remains required for study universality.
