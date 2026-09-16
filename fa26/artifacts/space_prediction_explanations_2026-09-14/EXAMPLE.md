# Prediction plus evidence shares — worked example

The classification head already exists. This report adds an explanation layer using
its saved, numerically checked input-gene attributions. It does not train another model.
All percentages below describe attribution relative to a reference profile, not causal
stress fractions or independently measured biological contributions.

## Example: GSE298393:GSM9013410

- Model prediction: **flight**, within the supported GSE298393 experiment.
- Uncalibrated sigmoid score: **0.9964**. This is not a validated
  probability or a claim of this percentage confidence in a new flight.
- Training: six YA-pool chips; this OS-pool chip was held out from head fitting.
- Reference: mean training-ground expression. Interpretation is conditional on this reference.

### Why did the score favor flight?

The reference logit was -5.825. Positive gene contributions totaled
+45.213; opposing contributions totaled
−33.760. Their net change was
+11.453, yielding the sample logit 5.628
(up to numerical integration error). The baseline score is shown separately; it is
not itself assigned to genes by this attribution calculation.

Of the absolute gene-attribution magnitude, 57.3%
raises the score and 42.7% lowers it.
The following table divides only the **supporting** contributions into shares summing to 100%:

| Gene | Share of supporting gene attribution | Same head, alternate-reference range |
|---|---:|---:|
| MUSK | 1.35% | 1.35–1.51% |
| BGN | 1.20% | 1.20–1.64% |
| SETD7 | 1.04% | 0.79–1.04% |
| ITGA7 | 0.88% | 0.84–0.88% |
| USF1 | 0.75% | 0.28–0.75% |
| All other supporting genes | 94.79% | — |

For gene j, supporting share = max(IG_j, 0) / sum(max(IG, 0)). Opposing shares are
computed separately from negative contributions. These are accounting definitions,
not probabilities. Signed net percentages were avoided because cancellation can make
them exceed 100% or become unstable. Relative shares change with the reference, head
and input; the second-reference ranges illustrate one sensitivity, not confidence intervals.

### Optional pathway view

Pathways overlap. To prevent double counting, each gene's contribution is split equally
among the represented Hallmark sets containing it. Genes in none of these sets retain
an explicit outside-category allocation. This is a transparent display convention,
not a learned or causal division between biological mechanisms.

| Gene-set allocation | Share of supporting attribution |
|---|---:|
| Outside these 50 Hallmark sets | 65.38% |
| Epithelial Mesenchymal Transition | 3.23% |
| Myogenesis | 2.54% |
| Adipogenesis | 1.65% |
| UV Response Dn | 1.56% |
| Remaining gene sets | 25.64% |

The gene-set labels are annotations. A UV-response share does not estimate radiation
exposure, and a myogenesis share does not quantify damage to muscle. For a claim such as
“80% radiation,” separate radiation/control supervision and independent calibration
would be required; even then the result would predict an exposure label, not the fraction
of stress caused by radiation. Current data do not identify causal shares of gravity,
radiation or other stresses.

## Next step

The prediction/explanation pipeline is now: normalized expression → frozen BridgeRNA →
fixed classification head → class score → signed gene attributions → explicitly defined
gene/pathway evidence shares. Validate the classifier and its calibration in additional
comparable data before presenting confidence percentages. Preserve the failed cross-flight
transfer case; this demonstration remains an experiment-specific research output.

Files include all 12 chips, both references, supporting and opposing gene shares, and
all pathway allocations. The example is the first held-out flight chip from the primary
head, selected by the existing manifest order. It was not selected for the best score.
