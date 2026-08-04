# Post-D2 Phase 1 final result: E1–E4

**Completed:** 2026-08-02 17:35 PDT
**Status:** checksum-verified secondary analysis on an already accessed OSDR
development cohort; not confirmation
**Joint protocol SHA256:**
`082d7f4edfb314ddf7a97e5c53072977062af89ac4c01203d37df3dc98e86913`

## Decision

E1, E2, E3, and E4 all fail their frozen downstream-specialization gates. The result is
now more precise than the earlier aggregate negative:

- the skeletal-muscle task is real but close to saturated for raw expression;
- the learned embeddings retain part of that signal but do not approach raw/PCA;
- specialization does not improve downstream performance over its matched pooled
  representation consistently across seeds; and
- organ-conditional residuals are highly predictive, but their useful signal is
  already present in the pooled residual and simple observed-expression controls.

No seed, representation, organ, interval, or condition is selected. The current frozen
downstream-output-contract branch is closed on this accessed development task.

## E4: specialization versus pooling on frozen OOF predictions

E4 gives Q-B its direct matched estimand and paired study-bootstrap interval. It does
not support a seed-invariant specialization advantage.

On the full embedding cohort, true-organ minus pooled-hidden AUROC was +0.0456
(95% study-bootstrap CI +0.0161 to +0.0939) in seed 17, -0.0108 (-0.0815 to
+0.0663) in seed 42, and -0.0609 (-0.1102 to -0.0054) in seed 101. Seed 101 is a
significant reversal, not merely a noisy null. Hard and soft routing show the same
pattern: seed 101 is negative with intervals below zero (-0.0741 and -0.0998), while
the other seeds are small or uncertain.

Within skeletal muscle, no true-organ, hard, or soft embedding comparison is positive
with an interval above zero in every seed. Seed-101 hard routing is negative by
-0.1180 with CI -0.2525 to -0.0107. The score-panel family is also inconsistent:
seed-17 true-organ is negative on the full cohort (-0.0511, CI -0.0881 to -0.0047),
and its muscle hard/soft comparisons are negative with intervals below zero.

**E4 verdict:** Q-B is not downstream-positive under either frozen output contract.
This is accessed development evidence and does not negate the independently validated
masked-gene reconstruction gain.

## E1: explicit skeletal-muscle-only nested evaluation

E1 refits only the downstream elastic-net heads on the exact 139 skeletal-muscle
samples from 10 studies. Encoder weights and representations remain frozen.

| representation | seed 17 | seed 42 | seed 101 |
|---|---:|---:|---:|
| pooled hidden | 0.6522 | 0.5578 | 0.7362 |
| true-organ embedding | 0.6468 | 0.5801 | 0.7563 |
| blind hard embedding | 0.6269 | 0.5930 | 0.7172 |
| blind soft embedding | 0.6805 | 0.5872 | 0.6710 |

Raw-expression AUROC is 0.9675 and fold-fit PCA-64 is 0.9623. The small difference
from the earlier post-hoc raw value of 0.989 is expected because E1 retunes and refits
the grouped downstream head inside the muscle-only cohort rather than merely slicing
predictions from a head trained across organs.

No Q-B comparison has a study-bootstrap interval above zero in every seed. Every blind
embedding loses to raw and PCA by 0.245 to 0.380 AUROC, with all corresponding
bootstrap intervals below zero.

**E1 verdict:** the benchmark has a strong, nearly saturated muscle signal, but the
frozen learned embeddings retain substantially less of it and organ specialization
does not rescue that gap.

## E2: organ-conditional residuals

Residuals are observed score-panel expression minus each frozen predicted score
panel. They therefore retain a direct observed-expression component. Subtraction can
still remove, distort, or amplify state signal, and the score panel is not the full raw
vector, so high residual AUROC was not guaranteed. It is nevertheless not evidence of
an MoE benefit by itself; the informative comparison is specialized residual versus
pooled and fold-fit centered controls. The muscle-only AUROCs are:

| representation | seed 17 | seed 42 | seed 101 |
|---|---:|---:|---:|
| pooled residual | 0.9698 | 0.9772 | 0.9783 |
| true-organ residual | 0.9658 | 0.9772 | 0.9694 |
| blind hard residual | 0.9731 | 0.9567 | 0.9747 |
| blind soft residual | 0.9729 | 0.9702 | 0.9820 |

Controls score 0.9675 for raw/full-raw fold-fit centered expression, 0.9623 for PCA,
and 0.9373 for the dimension-matched centered score panel. Residuals therefore retain
the strong muscle state signal, but the frozen scientific gate asks whether the same
specialized residual beats both pooled residual and centered score-panel raw in every
seed with lower bounds above zero. None does.

The most favorable isolated comparison is seed-101 blind-soft versus centered score
panel (+0.0447, CI +0.0048 to +0.0898), but it does not beat pooled residual robustly
(+0.0037, CI -0.0027 to +0.0155) and it is not reproduced in the other seeds. Every
blind-residual comparison against raw/PCA/full-raw centered either crosses zero or is
negative. Selecting this isolated seed would violate the protocol.

The prespecified full-cohort secondary centering analysis is not estimable: at least
one grouped inner/test fold contains an organ absent from its training partition.
The evaluator correctly stopped that scope instead of inventing a pooled-mean fallback
or changing membership.

**E2 verdict:** organ specialization contributes no reproducible residual advantage
beyond the pooled residual or simple fold-fit expression controls on this task.

## E3: low-label learning curves

E3 tested the last prespecified rescue hypothesis: compact embeddings might beat raw
expression when labeled training data are scarce. The corrected, checksum-verified
lineage uses four paired studies/eight labels at the nominal 5% floor, approximately
the smallest setting compatible with two grouped inner folds and fold-fit PCA. It
retains all ten frozen subsample seeds and scores complete untouched outer-test
studies.

The frozen gate fails for pooled hidden, true-organ, blind hard, and blind soft. No
representation beats raw at both 5% and 10% with a positive across-subsample interval
in all three model seeds. Every mean learned-minus-raw delta is negative.

| seed | representation | 5% mean delta (95% interval) | 10% mean delta (95% interval) |
|---:|---|---:|---:|
| 17 | pooled hidden | -0.104 (-0.246, +0.074) | -0.197 (-0.305, -0.096) |
| 17 | true-organ | -0.114 (-0.230, +0.004) | -0.201 (-0.301, -0.071) |
| 17 | blind hard | -0.118 (-0.248, +0.002) | -0.201 (-0.297, -0.073) |
| 17 | blind soft | -0.118 (-0.224, +0.002) | -0.215 (-0.297, -0.161) |
| 42 | pooled hidden | -0.134 (-0.245, +0.001) | -0.220 (-0.347, -0.090) |
| 42 | true-organ | -0.136 (-0.260, -0.013) | -0.217 (-0.303, -0.144) |
| 42 | blind hard | -0.140 (-0.238, -0.005) | -0.224 (-0.310, -0.111) |
| 42 | blind soft | -0.123 (-0.251, +0.005) | -0.211 (-0.276, -0.104) |
| 101 | pooled hidden | -0.119 (-0.227, +0.020) | -0.209 (-0.355, -0.072) |
| 101 | true-organ | -0.119 (-0.220, -0.000) | -0.212 (-0.289, -0.078) |
| 101 | blind hard | -0.109 (-0.207, -0.008) | -0.212 (-0.286, -0.085) |
| 101 | blind soft | -0.122 (-0.246, +0.008) | -0.208 (-0.285, -0.085) |

Mean absolute AUROC is 0.6289 for raw and 0.6329 for PCA at 5%, versus
0.4890-0.5250 for learned representations. At 10%, raw is 0.7313 and PCA is 0.7203,
versus 0.5074-0.5339 learned. At 100%, learned AUROCs remain 0.5568-0.7491, while
raw/PCA are 0.9424/0.9700 under E3's common two-inner-fold tuning scheme.

The first E3 lineage is preserved as an implementation failure: three paired studies
left one PCA inner-training split with only a single available component. It emitted
no baseline report. Although its three seed shards completed, none was reused. The
corrected lineage reran all four shards with the smallest feasible four paired studies;
all shard and aggregate checksums verify.

**E3 verdict:** under the same elastic-net probe family, label budget, and grouped
splits, compact learned representations make the state signal less linearly accessible
than raw expression at the 5% and 10% floors in every model seed. Scarce labels amplify
rather than close the raw-expression gap. This is strong evidence that the frozen
reconstruction outputs do not preserve state information in a practically useful form;
it does not establish information-theoretic absence.

## Interpretation and next step

The combined result separates three facts that were previously conflated:

1. Stage 1 establishes an external masked-gene reconstruction advantage for organ
   experts.
2. OSDR skeletal muscle contains a strong state signal that raw expression captures
   nearly perfectly.
3. The frozen specialization contracts do not convert that reconstruction advantage
   into seed-robust downstream discrimination, whether represented as hidden states,
   predicted score panels, or organ-conditional residuals.

The current frozen representation family is therefore supported for external
masked-gene reconstruction and coarse cross-species organ geometry, not for
perturbation-state classification. The next work should not tune another output on
OSDR. It should first consolidate the August 17 package, run the metadata-only D3-0
readiness audit for a genuinely informative human controlled-stress task, and write a
pristine reconstruction-confirmation cohort contract. Any supervised downstream
extension must be a separately versioned model family evaluated on a task selected
before model training.
