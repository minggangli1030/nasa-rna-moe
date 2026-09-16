# Prediction-head diagnosis and attempted remedies — September 14, 2026

**The AUROC 0.00 result is reproducible. Verified labels and exactly reproduced GPU
embeddings rule out the suspected label swap, row mismatch and inference discrepancy.
The immediate failure has two parts: a large study-level score offset and a reversal
of the flight-versus-ground response along the learned classifier direction.**

Consistent preprocessing reduces the offset but does not restore transfer. None of the
bounded source-only remedies tested here establishes a transferable classifier. A
separately evaluated, experiment-specific head trained on six labeled chips from one
target-flight donor pool achieves **AUROC 1.00 and balanced accuracy 0.833–1.000** on the
other pool. This supports a narrower practical pilot; it does not solve prediction in
an unseen flight or establish a universal six-sample requirement.

[Diagnostic figure](diagnosis_and_remedies.pdf) · [Label-count sensitivity](adaptation_learning_curve.pdf) ·
[All remedy results](remedy_metrics.csv) · [Adaptation results](supervised_adaptation_metrics.csv)

## 1. Checks for implementation or label errors

All 24 samples were checked against GEO treatment descriptions and exact matrix-column
mapping. Original-flight records explicitly distinguish Earth control from microgravity;
repeat-flight records agree between their titles and library descriptions. Labels remain
0=ground and 1=flight. Source rows, sample IDs, canonical gene order and input hashes align.
The public sources are [GSE234465](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE234465)
and [GSE298393](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE298393).

The A100 on moe-reboot recomputed the original 24 embeddings and 24 alternate-input
representations with the same checkpoint/source. **Maximum absolute difference between
recomputed and cached original embeddings: 0.0.** Checkpoint SHA256 remains
`f3491beaa697a0408dc1daeb6f8d648566bd46bafc6e44938d723e7ffc325541`.
Scalers and heads are fitted on training samples. AUROC uses continuous decision logits;
independent pairwise ordering calculations reproduce all 32 remedy metrics. No test-label
inversion, test-selected threshold or score-sign flip was used.

## 2. What produces the failure

For a linear head, the score is `w · ((x − training_mean) / training_scale) + intercept`.
The study shift changes the overall score location; a response reversal changes which
class receives the larger score. These are distinct problems.

For the original BridgeRNA mean+SD head:

| Training → test flight | Study offset added to mean logit | Training flight−ground score gap | Test flight−ground score gap |
|---|---:|---:|---:|
| First → repeat | +20.57 | +12.72 | −4.33 |
| Repeat → first | +31.25 | +13.52 | −9.61 |

The large positive offset explains saturated, confidently wrong sigmoid scores and
all-flight predictions at threshold 0.5. The negative test gap explains the reversed
ordering. Removing the unlabeled target mean does not change AUROC and can expose even
worse thresholded accuracy. A monotonic probability calibration cannot fix this ordering.

On average, 66.4% of BridgeRNA feature values in the held-out samples lie outside their
source-training feature range. This is a descriptive comparison with only 12 training
chips, not a calibrated out-of-distribution detector. Equivalent FPKM-based processing
reduces that fraction to 47.0%; expression drops from 50.8% to 33.3%. Thus preprocessing
accounts for part of the distribution difference, but response reversal remains.

Gene-level decomposition of the expression classifier also shows opposing contributions,
so the problem is not restricted to BridgeRNA. All gene contributions are saved in
`expression_reversal_gene_contributions.csv`; these describe this expression head's
failure, not causal genes or BridgeRNA input attributions.

## 3. Physical explanation: plausible contributors, not an isolated cause

The two studies do not implement an identical flight/ground contrast. The first report
describes a 10-day flight experiment, temperature variation, flow concerns and incubator
ground controls. The later work used a modified CubeLab and a different flight experiment.
These facts make a single study-invariant response assumption questionable. Sources:
[first study](https://www.nature.com/articles/s41526-023-00322-y),
[later study](https://pmc.ncbi.nlm.nih.gov/articles/PMC12277833/).

Sequencing platforms also differ (NovaSeq 6000 versus NovaSeq X). Source preprocessing
and experimental context covary with study, so these data cannot isolate which factor
caused the reversal. Library selection is recorded as cDNA in these records; it does
not establish poly(A) versus ribodepletion. Do not assign this failure specifically to
Brain's preparation-batch question without further evidence. The result does not imply
that all spaceflight biology reverses or that no shared pathway exists.

## 4. Remedies tested without target-flight labels

The original count-derived/FPKM mixture was replaced with both author-annotated FPKM
sources, normalized over the same 15,137 observed genes, log1p transformed once, with
missing canonical positions still masked for BridgeRNA. This is equivalent input handling,
not uniform reprocessing of raw reads. The later source's FPKM units remain conditional
on its GEO annotation.

The fixed diagnostic configurations include alternate scaling, per-sample ranks, layers
1/6/11/12, unit-normalized embeddings and all 50 predefined Hallmark modules. Module
representations pool contextual gene hidden states; pathway-expression comparators use
mean log expression. All heads use C=1; no best-looking test result is promoted as a
validated model. Unlabeled-target centering is separately marked transductive.

| Configuration | First → repeat AUROC | Repeat → first AUROC |
|---|---:|---:|
| `original_expression` | 0.000 | 0.000 |
| `original_bridge` | 0.000 | 0.000 |
| `original_bridge_target_center` | 0.000 | 0.000 |
| `original_expression_target_center` | 0.000 | 0.000 |
| `FPKM_expression` | 0.000 | 0.000 |
| `FPKM_expression_no_scale` | 0.000 | 0.000 |
| `FPKM_expression_SD_floor` | 0.000 | 0.000 |
| `FPKM_expression_sample_rank` | 0.000 | 0.000 |
| `FPKM_Hallmark50_expression` | 0.444 | 0.444 |
| `FPKM_bridge_L1` | 0.194 | 0.056 |
| `FPKM_bridge_L6` | 0.000 | 0.000 |
| `FPKM_bridge_L11` | 0.000 | 0.000 |
| `FPKM_bridge_L12` | 0.000 | 0.000 |
| `FPKM_bridge_L12_SD_floor` | 0.028 | 0.000 |
| `FPKM_bridge_L12_unit` | 0.139 | 0.028 |
| `FPKM_bridge_Hallmark50` | 0.222 | 0.083 |

All source-only configurations remain at or below 0.500 balanced accuracy in both
directions. These tests weaken specific explanations such as a source-unit mismatch,
small-standard-deviation amplification, or final-layer global pooling being the sole
cause. They do not prove that every possible correction or model would fail.

## 5. A practical remedy with an explicit data requirement

Train the prediction head for a supported experimental context using **three labeled
flight chips and three labeled ground chips from one donor pool**, then test all six
chips from the other pool in that same flight. Keep the encoder frozen. Repeat both
pool directions in both flights. The entire test pool stays out of fitting.

| Approach | BridgeRNA AUROC, four tests | BridgeRNA balanced accuracy | Expression balanced accuracy |
|---|---:|---:|---:|
| Other-flight training only | 0.000 in all four | 0.500 | 0.500 |
| Target-flight pool only | 1.000 in all four | 0.833–1.000 | 0.667–1.000 |
| Directly pool source flight + target training pool | 0.778–1.000 | 0.667–0.833 | 0.833–1.000 |

The target-specific head is the useful next working baseline. Naively adding the old
flight is not consistently beneficial. This adaptation changes the information available
at training time; it must not be reported as rescued zero-target-label transfer. Expression
also performs well, so there is no established BridgeRNA advantage. These are development
results on shared pools and previously explored flights, not a clean external validation.

Eight head artifacts (expression and BridgeRNA, two flights × two training pools) are
saved in `adapted_heads/`. Each includes training-only transforms, training/test IDs,
feature type, supported experimental context and uncalibrated status. They are research
artifacts, not a deployed universal flight detector.

## 6. How many target labels appear sufficient in this pilot?

All balanced subsets of one, two or three chips per condition were tested within the
training pool, keeping the other pool fixed as test data. Across two models and four
study/pool directions, this produces 152 fits; these are not 152 independent experiments.

| Labeled target chips | BridgeRNA AUROC range | BridgeRNA balanced-accuracy range |
|---|---:|---:|
| 2 (1 per condition) | 0.000–1.000 | 0.167–1.000 |
| 4 (2 per condition) | 1.000 throughout | 0.500–1.000 |
| 6 (3 per condition) | 1.000 throughout | 0.833–1.000 |

Two chips are unstable; four still permit threshold failures. The full six-chip training
pool is the most stable tested setup, but the tiny number of donor pools cannot establish
a general sample-size requirement or reliable calibration. Leave all scores explicitly
uncalibrated pending an adequate independent validation/calibration design.

## 7. Recommended next work for Minggang

Use the target-specific frozen head as the first supported prediction/attribution case,
with expression as comparator. An input-gene attribution analysis can then ask what that
**particular experimental-context classifier** relies on. Do not describe its features
as genes that identify spaceflight in general. No BridgeRNA input attribution or encoder
fine-tuning was performed in this diagnosis.

To pursue unseen-flight transfer, obtain additional comparable experiments with explicit
handling/preparation/control metadata and evaluate whole-study holdouts. Compare Brain's
correction against both source-only and target-adapted baselines, retaining biological
preservation checks. A larger GPU or more training epochs cannot supply missing independent
experimental contexts; this turn therefore prioritized data/representation diagnostics.

## Execution, verification and files

The A100 completed 48 sample/processing passes in 16.3 seconds. Local CPU runs fitted the
heads and sensitivities. No encoder weights changed. The isolated VM directory is
`/media/volume/moe-reboot/fa26_space_head_diagnostics_20260914`; original data and prior
pilot outputs remain intact. No watcher was started.

The initial upload was blocked by automatic review; public GEO provenance and matching
existing VM copies were verified, and the reviewed retry succeeded. No data transfer
remains blocked.

- [Input preparation and GPU extraction](../../space_head_diagnostics.py).
- [Diagnostic comparisons](../../evaluate_space_head_diagnostics.py).
- [Label-count sensitivity and saved heads](../../check_space_head_adaptation.py).
- [Figure generation and independent checks](../../report_space_head_diagnostics.py).
- `label_source_audit.csv`, `input_audit.json`, `inference_report.json`, `verification.json`:
  annotation, input, inference and reproducibility checks.
- `logit_decomposition.csv`, `out_of_domain_features.csv`, `response_directions.csv`:
  the numerical failure analysis.
- `remedy_predictions.csv`, `supervised_adaptation_predictions.csv`,
  `target_label_learning_curve.csv`, `adapted_head_predictions.csv`: full outcomes.

The protocol was recorded after the original failure but before these remedy outcomes.
All results are explicitly diagnostic/development findings. Original benchmark results
are retained, including failures. No experiment remains running for this diagnosis.
