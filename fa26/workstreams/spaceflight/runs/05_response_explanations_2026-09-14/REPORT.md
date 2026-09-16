# Response-level explanation pilot

**Scope:** explain the biological-response programs associated with the existing GSE298393 flight classifier. Frozen BRIDGE and both fitted heads are unchanged. This is development evidence from 12 chips and two donor pools, not independent validation or exposure-cause identification.

[Figure](response_program_summary.pdf) · [Per-sample example](EXAMPLE.md) · [Protocol](protocol.json)

## Findings

**Reviewed verdict:** myogenesis-associated muscle differentiation/remodeling is the
clearest of the six tested contributors. Other tested stress responses are weak or
sensitive to the head/normalization. The six-program vocabulary leaves 91.2–92.9% of
positive attribution unassigned in the flight samples. This is a partial response-level
explanation, not a radiation/microgravity detector. Read the [interpretation and next decision](REVIEW.md).

| Program | Flight–ground expression difference, range across pools | Flight–ground logit gap removed, four cases | Same sign including renormalization? | Chip-deletion sign retention | Matched random absolute percentile range |
|---|---:|---:|---|---:|---:|
| Mitochondrial expression | +0.158 to +0.178 | -0.108 to -0.010 | True | 92% | 0–30% |
| DNA repair expression | +0.102 to +0.173 | -0.136 to +0.078 | False | 100% | 15–45% |
| Oxidative-stress-associated expression | +0.008 to +0.103 | +0.028 to +0.052 | True | 96% | 15–25% |
| Inflammatory signaling | -0.146 to +0.116 | +0.066 to +0.176 | True | 92% | 20–25% |
| Unfolded-protein-response expression | +0.032 to +0.178 | +0.015 to +0.072 | False | 81% | 0–40% |
| Muscle differentiation/remodeling | -0.005 to +0.142 | +0.562 to +0.821 | True | 98% | 90–95% |

Positive removed gap means the program inputs support the flight/ground separation; negative means they suppress it. A program can increase in mean expression while suppressing the score, because the classifier weights individual genes differently. These gene-set scores do not measure functional pathway activation. All six programs are retained, including weak or opposing ones.

## What was tested

Six Hallmark programs were fixed before this run (earlier pathway rankings had already been explored). Each complete measured program was replaced with each training-only reference in all 12 held-out chips. Twenty random panels matched each target’s exact joint training-expression mean/SD quintile counts, without replacement or target overlap. The same panels were reused across evaluation chips. Every target and random panel was tested both with and without TPM renormalization. No hyperparameters, genes or exposure labels were learned from this pilot.

Reference replacement is an input sensitivity experiment, not a biological intervention. It can leave the expression manifold; TPM renormalization perturbs other genes too. Matched panels control size and coarse expression mean/SD, not gene correlation structure. This run does not establish statistical significance or causal effects.

## Interpretation and next step

Use the stable response associations as model-reliance hypotheses, with genes as supporting evidence. A radiation or microgravity label requires controlled exposure comparisons and specificity against alternative stressors. Existing onboard-1g cohorts may help in their own cell contexts; they do not automatically validate this muscle-chip classifier. Unseen-flight transfer remains failed, and scores remain uncalibrated.

Response expression, attributed evidence, and observed replacement effects are reported separately. Overlapping replacement effects must not be added as independent percentages. The allocation table splits shared genes equally and retains all evidence outside the six programs; this is a reporting convention. A future concept-based head is a separately evaluated model, not retrospective proof of what this one learned.

## Files and checks

- `program_evidence.csv`: per-chip response expression and signed attribution for BRIDGE and expression baseline.
- `per_sample_reliance.csv`: target replacement effects and matched-control percentiles.
- `program_reliance_contrasts.csv`: change in the flight–ground score gap by program, head, reference and normalization.
- `response_summary.csv`, `leave_one_chip.csv`, `reliance_leave_one_chip.csv`: stability, without treating chips as independent donors.
- `supporting_genes.csv`: genes beneath each response explanation.
- `program_overlap.csv`, `evidence_allocation.csv`: overlap and unassigned evidence.
- `verification.json`, `matching_checks.csv`, `execution_report.json`: numerical and run records.

GPU: NVIDIA A100-SXM4-40GB; 6,048 replacement passes; 32.8 minutes this invocation; peak allocated memory 1.93 GB. Preparation and reporting ran locally. No encoder/head training occurred.

Sources: [public GEO study](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE298393); gene-set definitions reused from the previously archived `hallmark_2020.gmt`, whose hash is recorded in `input_provenance.json`.
