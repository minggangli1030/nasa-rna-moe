# Stage 2 recipient-exposure-preserving additive transfer

**Status:** complete, checksum-verified development result
**Completed:** 2026-07-28 10:37 PDT / 2026-07-28 17:37 UTC

## Question and frozen design

Does adding donor-organ B training signal help recipient organ A when all original
recipient exposure is preserved?

The prospectively frozen primary estimand compares `A1500+B750` with `A1500` on
held-out recipient-A donors. Eight directed edges were frozen before any additive
outcome. Every edge retained seeds 17, 42, and 101; no seed, edge, or outcome was
selected after access. Controls were `A2250` and three `A1500+random750` arms.

- scientific implementation: `be1a6f9cb5a7473d6a33f20fc848ef728918f5be`
- arm definitions:
  `78edd164f8c5444299da7ab5bf45cd35eed3d513f772b6a7fab11b9aef60d3fb`
- schedule:
  `fe71a83a9eb60529aef8f1c66dff5072dbc2ba1c6f508284e3568a862f35a75c`
- pre-outcome edge freeze:
  `15d5cfe19506aa7fe267a422626417ceb794ef6707481d3a15d7fdbf5a89813d`
- local verified result:
  `artifacts/stage2_organ_expert_mechanism/additive_evaluation_be1a6f9`
- result checksum-manifest SHA256:
  `0c005678d312ac8924e498249f215f45d33153704fc5fc646248596b32e5bf7b`

This is donor-disjoint GTEx development evidence. It is not independent-study
universality.

## Result

Positive values mean B improved recipient-A MSE relative to `A1500`.

| Recipient A ← donor B | Mean effect | Positive seeds | Donor-bootstrap 95% CI | Effect vs A2250 | Beats all random controls |
| --- | ---: | ---: | ---: | ---: | ---: |
| brain ← skin | −0.742% | 1/3 | [−0.875%, −0.596%] | −3.962% | 2/3 seeds |
| colon ← skeletal muscle | +0.277% | 2/3 | [+0.229%, +0.327%] | −0.975% | 2/3 seeds |
| liver ← skin | **+1.956%** | **3/3** | **[+1.647%, +2.244%]** | −2.357% | **3/3 seeds** |
| adipose ← lung | +0.109% | 1/3 | [−0.011%, +0.225%] | −2.057% | 3/3 seeds |
| heart ← adipose | −0.186% | 2/3 | [−0.248%, −0.121%] | −3.218% | 2/3 seeds |
| lung ← skeletal muscle | −0.383% | 1/3 | [−0.491%, −0.290%] | −2.465% | 3/3 seeds |
| skeletal muscle ← lung | +0.811% | 2/3 | [+0.697%, +0.918%] | −5.011% | 3/3 seeds |
| skin ← adipose | +0.264% | 2/3 | [+0.194%, +0.338%] | −5.328% | 2/3 seeds |

Five of eight mean effects were positive, but only **liver ← skin** satisfied both
three-of-three positive seeds and an interval above zero. Four edges beat all three
random auxiliaries in all three seeds, showing donor identity matters, but none of
the eight named-donor additions beat `A2250` across all seeds.

## Takeaway

The substitution and additive results answer different questions:

1. Replacing half of A with B was harmful for every one of 56 directed pairs.
2. Preserving A and adding B can help selectively; the strongest frozen example is
   liver ← skin.
3. More recipient-A exposure remains the best tested use of the extra 750 draws.

The practical policy supported on development data is therefore:

> Protect recipient-organ exposure first. Add another organ only under a
> prospectively validated, directional transfer rule; otherwise prefer more
> recipient data or keep specialists isolated.

## Directionality

Transfer need not be symmetric. Training on B changes optimization for recipient A,
and sample size, heterogeneity, baseline error, and learnable programs differ by
recipient. The frozen subset illustrates this: skeletal muscle ← lung was +0.811%,
whereas lung ← skeletal muscle was −0.383%.

That contrast is suggestive, not a universal pairwise law: neither direction was
positive in all three seeds. The full substitution matrix already contains both
directions for all 28 unordered organ pairs. The additive subset contains both
directions only for lung and skeletal muscle.

## Next experiments

1. Freeze the six missing reciprocal additive directions as one post-discovery
   follow-up set; do not select only favorable pairs.
2. Compare frozen expert residual genes/pathways and router compatibility with the
   observed directed effects.
3. Test whether those predictors beat expression similarity, sample-count,
   platform/study, and random controls on held-out edges.
4. Freeze a genuinely new multisource cohort before claiming study universality.

The reciprocal expansion must be labeled post-discovery because the first additive
outcomes are now known. It is useful for estimating asymmetry, not for upgrading the
original eight-edge test to pristine prospective confirmation.
