# Stage 2 seed-stability diagnosis

**Status:** complete; instability branch selected by the frozen evaluator

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

## Execution

Exact input-bound commit
`3a27ffabdcb6d2a4209006452958b30cf0fff520` launched at 2026-07-28
19:52 UTC:

- primary 40 GB A100: trunk/optimization combinations 17:211, 17:223, 42:211,
  42:223, and 101:211;
- parallel 20 GB A100: combinations 17:227, 42:227, 101:223, and 101:227.

Both detached sessions passed their input hashes. All nine combinations completed
24/24 arms in deterministic FP32:

- primary completed at 2026-07-29 09:21 UTC; 379/379 immutable entries verified;
- parallel completed at 2026-07-29 06:40 UTC; 304/304 immutable entries verified;
- its score caches and metadata were copied to a distinct compact lineage with
  207/207 entries verified and no adapter checkpoints transferred.

The evaluator was run over the exact 3×3 roots with the frozen protocol, schedule,
definitions, and decision gates. The first direct-file invocation stopped before
result access because Python could not resolve the repository package; rerunning the
identical evaluator as a module repaired only that invocation path. No input,
estimand, gate, or scientific code changed.

## Result

The frozen evaluator selected:
`optimization_instability_confirmed_test_robust_sharing_then_pivot`.

| Recipient ← donor | Mean vs A1500 | 95% factor-bootstrap CI | Positive combinations | Classification |
| --- | ---: | ---: | ---: | --- |
| brain ← skin | −0.883% | [−1.621%, −0.298%] | 1/9 | stable harmful |
| colon ← skeletal muscle | −0.104% | [−0.787%, +0.368%] | 5/9 | unstable/negligible |
| liver ← skin | +3.011% | [−0.632%, +7.862%] | 6/9 | unstable/negligible |
| adipose ← lung | +0.102% | [−0.491%, +0.807%] | 6/9 | unstable/negligible |
| heart ← adipose | −0.740% | [−2.031%, +0.157%] | 2/9 | unstable/negligible |
| lung ← skeletal muscle | −0.990% | [−2.115%, +0.539%] | 2/9 | unstable/negligible |
| skeletal muscle ← lung | −1.682% | [−4.548%, +0.706%] | 2/9 | unstable/negligible |
| skin ← adipose | −3.369% | [−6.654%, −0.682%] | 1/9 | stable harmful |

Summary:

- stable helpful: 0/8;
- stable harmful: 2/8;
- unstable or negligible: 6/8; and
- 9/72 crossed cells beat A2250, while every edge's mean comparison with A2250 was
  negative (mean across cells −3.664%).

The earlier liver←skin result was not a fabricated fluke: its crossed mean remained
positive. But it was not reliable enough to use as a rule. Its effect ranged from
−2.402% to +11.316% across the nine combinations, its cross-combination standard
deviation was 4.362%, and its interval included zero.

The instability is not attributable to one universal factor. Edge-level variance
decomposition differs: some relationships are trunk-sensitive, some are
optimization-sensitive, and some are dominated by interaction/unresolved variance.
This argues against fixing the result by selecting a seed or rerunning the same raw
addition design.

Immutable local result:
`artifacts/stage2_organ_expert_mechanism/seed_stability_evaluation_3a27ffa/`.
Its checksum-manifest SHA256 is
`66dc24a0d8541f37dfea99be9553677509cb3523da843609835d36febf7c6801`.

## Prespecified next experiment

Run one recipient-protected sharing implementation, then stop or pivot.

The design target is a separate, zero-initialized donor-residual branch:

- recipient A1500 updates train the recipient adapter;
- donor B750 updates cannot modify that recipient path;
- donor information enters only through a bounded residual gate trained on
  development donors;
- the gate begins at zero, so disabling sharing exactly recovers the recipient-only
  model; and
- once the recipient organ expert is selected, the residual gate uses expression
  only; this is a protected organ-expert test, not a return to de novo label-free
  routing.

Controls remain:

- A1500 recipient-only;
- the existing raw A1500+B750 addition;
- protected A1500+B750;
- A2250 recipient-only; and
- protected random-auxiliary additions with matched exposure.

Freeze the exact architecture, capacity match, eight edges, 3×3 factors, masks,
seeds, gates, and stopping rule before opening outcomes. Keep the current bar:
at least three of eight edges must be stable helpful under the same classification,
and recipient protection must not introduce a stable-harmful edge. Otherwise stop
raw organ-transfer work and pivot to organ-conditioned pathway/state or continuous
expert-residual structure.

## Post-diagnosis scope

This diagnosis shows that raw organ-to-organ addition is not reproducible enough to
remain the primary Stage 2 mechanism. It does not invalidate the independently
replicated Stage 1 organ experts or bind the broader MoE project to organ labels
alone.

Organ remains the independently validated benchmark and control. If the diagnosis
and the one permitted recipient-protected sharing test are disappointing, the
project may pivot to hierarchical attributes, cross-cutting biological programs, or
continuous expert-residual representations under the same donor/study-disjoint,
seed-stability, anti-collapse, and confound-control gates. That decision will be
made from the completed diagnosis; it must not retroactively change the running
protocol or turn an unstable edge into a selected result.
