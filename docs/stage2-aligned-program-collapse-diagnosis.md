# Stage 2 aligned-program collapse diagnosis

**Status:** read-only diagnosis complete

**Evaluated scientific training commit:** `93e5a9b5b95652e37b563c8bc649bb058524b20b`

**Evaluated result lineage:** evaluator commit
`ba07442d193d00a11c39546c26eb29954699260c`

## Question

The shared-plus-private model passed every utility control, and its learned
coefficients correlated strongly across the three fixed seeds. However, coefficient
effective rank was only 1.22–1.31 rather than the frozen minimum of 8.

This diagnosis asks whether that collapse reflects:

1. an inherently low-rank decoder or residual target;
2. a random optimization failure;
3. a stable but scientifically unhelpful shortcut; or
4. a learnable high-rank target that the present head and objective fail to recover.

All analyses are post-result, read-only development diagnostics. They do not change
the frozen models or qualify as independent confirmation.

## Findings

### The decoder is not collapsed

The fixed 32-component decoder has effective rank 29.00. Its leading direction
accounts for only 6.36% of decoder variance, and its largest row norm is 2.07 times
its smallest. Decoder scaling is a secondary imbalance, not an explanation for a
learned representation whose first direction accounts for 94–96% of donor-level
coefficient variance.

### The learned collapse is reproducible

Across seeds 17, 42, and 101:

- donor-level coefficient effective rank is 1.22–1.31;
- sample-level coefficient effective rank is 1.42–1.66;
- the final coefficient-output weight matrix has effective rank 2.26–3.30;
- leading coefficient directions have absolute cross-seed cosine 0.926–0.985; and
- leading decoded directions have absolute cross-seed cosine 0.944–0.990.

This rules out a one-seed numerical accident. All three optimizations found nearly
the same shortcut.

### The shortcut is primarily tissue identity and difficulty

The leading coefficient score is strongly explained by organ (eta-squared
0.868–0.871) and tissue site (0.886–0.895). Brain lies at one extreme and liver,
adipose, lung, muscle, heart, skin, and colon largely occupy the other. Its decoded
genes are enriched for conspicuous brain/CNS markers including `GFAP`, `MBP`,
`SLC1A2`, `OLIG1`, `SNCB`, `PCSK1N`, and `BCAS1`.

The score also correlates with pooled reconstruction difficulty (0.671–0.717) and
shared-path improvement (0.673–0.700). Component 1 alone accounts for approximately
75–78% of the estimated decoded output energy.

Therefore the shared head mostly acts as a soft tissue-identity/difficulty router:
it detects the easiest, highest-value global distinction and scales one correction
direction. High cross-seed coefficient correlation is real, but it means the same
one-dimensional shortcut was reproduced; it does not establish 32 stable programs.

### The aggregate utility is heterogeneous

The incremental shared-path gain over the private-only model is largest for brain
in every seed (+42.8% to +45.8%) and for liver in seeds 42 and 101. Several
organ/seed cells are negative, including skin in seeds 17 and 101, colon in seeds
17 and 101, and heart in seed 101.

The model's 30–37% aggregate improvement is therefore genuine under the frozen
balanced metric, but it should not be described as a uniform benefit for every
organ.

### A high-rank target exists in the same decoder span

For each calibration sample, the diagnosis projected the actual reconstruction
residual onto the exact frozen decoder by least squares. This is an oracle
diagnostic, not a deployable prediction.

| Quantity | Seed 17 | Seed 42 | Seed 101 |
|---|---:|---:|---:|
| learned sample coefficient rank | 1.42 | 1.47 | 1.66 |
| post-private oracle sample rank | 12.89 | 13.73 | 14.34 |
| post-private oracle donor rank | 7.00 | 7.68 | 8.05 |
| post-private oracle within-organ rank | 16.48 | 17.04 | 16.85 |
| trained reduction versus private | 33.6% | 37.0% | 31.8% |
| oracle reduction versus private | 75.1% | 76.0% | 73.4% |

The current basis and residual target can therefore support substantially richer
structure. Forcing artificial variance into an intrinsically rank-one target is not
the issue.

## Most likely mechanism

Three design choices interact:

1. **Joint path competition.** The shared and organ-private branches learn
   simultaneously from the same reconstruction loss. The shared branch can capture
   the largest cross-organ correction while the flexible gene-level private branch
   absorbs the remaining structure. Nothing assigns a stable residual target to the
   shared coefficients.
2. **An output-MSE-only objective.** The loss rewards immediate decoded error
   reduction, not recovery of multiple fixed coordinates. A dominant
   tissue-identity/error direction receives the strongest and most consistent
   gradient. The zero-initialized final coefficient layer and 1,500-update schedule
   reinforce this early winner.
3. **A potentially lossy global summary.** The coefficient head mean-pools all
   observed per-gene hidden states into one vector before predicting 32
   coefficients. A separate donor-grouped probe below tests this possibility
   directly.

The decoder's modest non-orthogonality can amplify unequal gradients, but the
decoder's rank and oracle results show that it is not the primary cause.

### The existing input summary is sufficient

An exploratory five-fold donor-grouped probe was run for seed 17. It used the
unchanged 768-dimensional global hidden summary to predict the post-private oracle
coefficients with a linear ridge model. Every donor appeared in exactly one test
fold.

At alpha 0.01, the held-out predictions had:

- effective rank 12.40;
- median component correlation 0.963;
- minimum component correlation 0.849; and
- 69.8% donor-balanced error reduction versus the private path.

The nonlinear trained head achieved only 33.6% reduction for the same seed, while
the unattainable per-sample oracle ceiling was 75.1%. The simple grouped probe
recovers most of that ceiling without changing the summary or adding capacity.

This localizes the primary failure to the training target and simultaneous path
competition. The current global summary is not the bottleneck, although a richer
pooling architecture may remain a later extension. The probe is post hoc,
single-seed development evidence and is used only to choose the next engineering
intervention.

## Recommended bounded repair

Do not add a generic “make rank high” penalty to the current joint model. That could
manufacture unused coefficient variance without improving prediction.

The next implementation should preserve the data, donor split, three seeds, exact
fixed decoder, controls, and no-best-seed rule, while changing coefficient
identifiability:

1. train the organ-private path first and freeze it;
2. compute training-only least-squares coefficient targets for the residual left
   after pooled plus private prediction;
3. train the existing shared head against per-component standardized coefficient
   targets, with decoded reconstruction MSE retained as an auxiliary objective; and
4. use donor-balanced batches and evaluate coefficient rank both overall and after
   removing organ/site means.

The donor-grouped probe already clears the rationale for keeping the current
architecture. Decoder row orthonormalization should be retained only as a
prespecified secondary ablation, not bundled into the first repair, because the
probe predicts high-rank coefficients in the existing coordinates. Likewise, no
generic variance-maximization penalty is currently justified.

## Required gates for a repaired run

- repeat all three fixed seeds; no seed or component selection;
- retain superiority to pooled, private-only, matched generic, and random-basis
  controls;
- add an extended-private-update control to show that the shared gain is not merely
  extra optimization;
- require donor-level and within-organ coefficient effective rank, not only global
  rank;
- report per-organ benefit and harm rather than only the aggregate;
- require cross-seed coordinate correlation after the fixed orthonormal transform;
  and
- treat all results as donor-disjoint GTEx development evidence until confirmed on
  a new study-disjoint cohort.

## Artifacts

Read-only numeric outputs are stored in
`artifacts/stage2_organ_expert_mechanism/aligned_program_diagnosis_ba07442/`.
