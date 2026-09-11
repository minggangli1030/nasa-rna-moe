# Tissue-site Tier-2 protected-adapter result

**Completed:** 2026-07-31 07:47 PDT / 2026-07-31 14:47 UTC

## Decision

The frozen Tier-2 gate failed in all three fixed seeds. Tissue site does not enter
the final architecture. The architecture is therefore closed as the validated K8
organ MoE with its pooled prediction retained as the fallback/reference; no
secondary biological axis is added.

This is a refusal to attribute generic residual capacity to tissue-site biology,
not evidence that anatomical site carries no signal.

## Result

The input-only soft site adapter improved score-gene MSE over the frozen protected
organ path by 70.70%, 70.56%, and 70.50% in seeds 17, 42, and 101. It also beat a
within-organ shuffled-site bank by 0.149%, 0.199%, and 0.128%, with positive
donor-bootstrap intervals. Known-site routing helped in every seed, routing did not
collapse, and the protected per-organ safety gate passed.

The decisive matched-capacity control was stronger. The parameter-matched generic
adapter beat the tissue-site adapter by 0.461%, 0.534%, and 0.544%; equivalently,
soft-site versus generic effects were negative in every seed, with 95% donor
bootstrap intervals of:

- seed 17: −0.496% to −0.428%;
- seed 42: −0.572% to −0.500%; and
- seed 101: −0.577% to −0.512%.

Consequently `soft_site_improves_generic` and the joint pairwise-bootstrap gate
failed in every seed. No seed, threshold, or condition was selected after access.

## Interpretation

Tier 1 correctly found reproducible residual structure associated with tissue site.
Tier 2 shows that the large neural correction is mostly an effect of adding residual
capacity: a generic head uses the same parameter budget slightly better. The small
advantage over shuffled site is reproducible, but it is not sufficient to justify a
more complex deployable site hierarchy under the frozen gate.

The clean conclusion is therefore:

> Organ specialization remains the validated domain structure. Tissue site is a
> useful explanatory attribute, but this implementation did not convert it into
> incremental predictive value beyond matched generic capacity.

This is donor-disjoint GTEx development evidence, not study-universal biological
evidence.

## Next execution

The immediate development step is to expose an explicit downstream-facing output
from the frozen organ model before any final refit. The output combines the pooled
trunk sample summary, the selected or router-weighted organ-adapter bottleneck, and
the frozen input-only router probabilities. It will be evaluated with the existing
study-grouped OSDR development harness against raw expression and fold-fit PCA.

That experiment does not reopen the architecture or add tissue site. It determines
whether the organ model already contains a useful general-purpose representation
that was hidden by the earlier score-panel-prediction output contract. A new
untouched grouped cohort remains necessary for a final downstream claim.

## Immutable evidence

- frozen protocol SHA256:
  `d922c1997389aacdc09c032415f0dc8a57ee579530f67f7f539477490eaac410`;
- exact scientific commit:
  `d47ac36f11647d3bcd6bd6d3aa3c2dffefc10378`;
- accepted seeds: 17, 42, and 101;
- local compact evidence:
  `artifacts/stage2_organ_expert_mechanism/tissue_site_tier2_d47ac36/`; and
- aggregate report SHA256:
  `130d8ab775777a5e4a3d0a31513d3fb6c330add9452fb30c1a6fa73999f0d921`.
