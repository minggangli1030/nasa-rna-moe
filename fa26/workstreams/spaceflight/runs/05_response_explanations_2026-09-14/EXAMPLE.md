# Example: flight prediction explained by response programs

Sample `GSE298393:GSM9013410`; YA-trained fixed head, held-out OS chip. This example was fixed by order, not selected for its results.

Flight logit: **5.628** (uncalibrated). The response programs below are expression associations, not validated radiation or gravity detectors.

| Response program | Expression difference from training-ground reference | Change in flight logit when replaced | Matched-control absolute percentile |
|---|---:|---:|---:|
| Mitochondrial expression | +0.121 | -0.028 | 0% |
| DNA repair expression | +0.039 | -0.216 | 70% |
| Oxidative-stress-associated expression | -0.057 | +0.068 | 45% |
| Inflammatory signaling | -0.155 | +0.533 | 75% |
| Unfolded-protein-response expression | -0.032 | +0.119 | 40% |
| Muscle differentiation/remodeling | +0.026 | +0.866 | 100% |

Positive logit change means replacing the program lowers the flight score: the observed program inputs support the prediction. Negative means they oppose it. Expression direction and model reliance are separate. Matched percentiles use only 20 controls; they are descriptive, not independent significance tests.

**Unassigned evidence:** 91.2% of positive attribution lies outside these six programs. Genes shared by programs are split equally for this accounting; the percentage is not a causal fraction.

Replacement effects overlap and do not sum to a complete decomposition. Radiation-versus-gravity specificity is **not established**. See the [full report](REPORT.md) for stability and limitations.
