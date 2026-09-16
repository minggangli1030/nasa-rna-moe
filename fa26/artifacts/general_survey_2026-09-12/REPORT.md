# General space-biology discovery survey

> **September 13 follow-up complete:** the [pathway and onboard-1g report](../pathway_onboard_1g_2026-09-13/REPORT.md) adds shared average muscle-chip and controlled MG63 leads, with source and sample checks. Use the [updated Monday brief](MONDAY-DISCUSSION.md) for the current conclusion. This report retains the original general-survey evidence.


Completed September 12, 2026, for the September 14 mentor discussion. Frozen BridgeRNA `r7hnr92k`; no training or classifier tuning. The broad screen supports several **context-specific leads**, not a universal spaceflight signature or a demonstrated model advantage.

**September 13 follow-up:** GSE298393 has now been tested. The broad human muscle-chip directions do not repeat across flights, while MYH1 decrease survives in both pools. Read the [completed repeat-flight report](../muscle_repeat_flight_2026-09-12/REPORT.md). The September 12 results below retain the original discovery-stage context.

Start with [Monday discussion notes](MONDAY-DISCUSSION.md) and the [three-panel figure](monday_findings.pdf). The [full survey map](survey_pattern_map.pdf) includes all 54 contrasts, including weak results.

## What was surveyed

Screened all **940,455 supplied ARCHS4 metadata rows** (human and mouse) and the **2,896-row, 94-study supplied OSDR catalog**. A keyword screen identified 422 ARCHS4 rows across 29 series strings; controls were recovered from the corresponding study metadata. This is an inventory of the supplied catalogs, not an exhaustive search of all public spaceflight biology.

Expression analysis covers **559 samples, 28 study accessions, 54 within-study contrasts, and 11 broad tissue groups**. Cohorts were selected from accessible count files and explicit experimental designs before inspecting their expression/model results. OSDR contrasts required at least three samples per condition, matched recorded covariates, and were capped at six per condition by a fixed sample-ID hash. Unavailable files and exclusions are recorded in `osdr_selection_decisions.csv`.

| System | Samples | Design |
|---|---:|---|
| Mouse, 24 OSDR accessions | 499 | 250 flight, 249 ground; multiple tissues |
| Human cardiac cells, GSE137081 | 18 | 3 cell lines × flight/ground/post-flight × 2 replicates |
| Human muscle chips, GSE234465 | 12 | 2 donor-source pools × flight/ground × 3 chips |
| Human muscle biopsies, GSE113165 and GSE126865 | 30 | 15 paired pre/post bed-rest donors; analog, not flight |

The 529 samples in actual-flight **study designs include their ground controls and six post-flight samples**. Study accessions, tissues, chips, and RNA samples are not interchangeable with independent missions or donors. The OSDR catalog supplied here is entirely mouse; this explains its numerical dominance, not an MoE requirement or a biological preference.

## Discussion leads

### 1. A consistent human muscle-chip shift, with substantial experimental confounding

In GSE234465, both young/active and old/sedentary pools retain agreeing flight-minus-ground directions in **all 9 balanced chip splits**, for raw expression and both BridgeRNA summaries. Cross-pool direction cosine is **0.914 for model mean, 0.724 for model std, and 0.758 for expression**. Removing one chip retains the model-mean direction (minimum cosine 0.961 young/active; 0.995 old/sedentary). Mask-versus-zero sensitivity changes the model shift by only 0.27–0.51%.

These are three chips per condition using each five-male-donor pool, not independent donor replication. Age and activity vary together. The original experiment reported flight temperature/fluid-flow difficulties and asynchronous ground controls in an incubator rather than the flight hardware. Thus this is a reproducible **flight-experiment association**, not isolated microgravity causation. The original paper already reports biological effects; recovering a pattern does not establish novelty. [Original study](https://www.nature.com/articles/s41526-023-00322-y).

**Next:** compare the non-stimulated arms of the later flight, **GSE298393**, before exploring age-related mechanisms. That follow-up study reports a ground run in the same CubeLab hardware; it still is not independent donor validation. It was identified after this screen and has since been analyzed in the linked September 13 follow-up. [Follow-up study and data accession](https://pmc.ncbi.nlm.nih.gov/articles/PMC12277833/).

### 2. Recurrent mouse-muscle expression leads span four missions

Across 12 muscle accessions (13 contrasts), study-average **Cdkn1a and Mmp14 increase, Dbp decreases**, and the mouse **Mt2** row increases. Related accessions collapse to RR-1, RR-4, RR-5, and RR-23; every mission-average direction agrees. These are raw-expression leads accompanying the model survey, not genes attributed as drivers of model embeddings.

| Canonical model label (mouse gene) | RR-1 | RR-4 | RR-5 | RR-23 |
|---|---:|---:|---:|---:|
| CDKN1A (Cdkn1a) | +0.568 | +0.950 | +0.298 | +1.606 |
| DBP (Dbp) | −1.383 | −0.275 | −0.150 | −1.219 |
| MMP14 (Mmp14) | +0.346 | +0.247 | +0.149 | +0.454 |
| MT1X (mapped mouse Mt2) | +0.991 | +0.501 | +0.510 | +0.554 |

Values are mean differences in **log1p(TPM)**, with equal study weighting within mission; they are not log2 fold changes. The MT1X→Mt2 label is from the supplied checkpoint mapping and needs biological mapping review before cross-species interpretation.

Dbp and Mmp14 retain their signs after every single-sample deletion in all 13 contrasts. Cdkn1a flips in one deletion in OSD-419; the mapped Mt2 result flips in two deletions in the six-sample OSD-401 gastrocnemius contrast. These four genes were selected after the broad screen; there are no adjusted significance or biomarker claims.

Cdkn1a provides a stress/cell-cycle question, and Dbp a circadian-output question. Collection time, unloading, handling, and cell composition could explain these patterns. [CDKN1A annotation](https://www.ncbi.nlm.nih.gov/gene/1026), [primary Dbp circadian study](https://pubmed.ncbi.nlm.nih.gov/10733528/).

**Next:** audit collection time and experimental units, then inspect a small set of related genes. Human muscle chips do **not** consistently share these directions: for example, CDKN1A decreases and DBP increases in both chip pools. That limits claims of a shared human–mouse signature.

### 3. Tissue context is informative within one multi-tissue experiment

In OSD-457/MHU-3, thymus and brown adipose show agreeing split directions in **all 400 balanced partitions**, in both wild-type and Nrf2-knockout groups, for expression and both model summaries. Their WT/KO direction cosines are 0.993/0.995 for model mean and 0.778/0.852 for expression, respectively. Cerebrum and temporal bone are less consistent; mandible has a stable expression shift that mean pooling largely loses.

This supports exploring tissue-dependent responses and how the model represents them. It does not establish a genotype interaction, rank tissue vulnerability, or provide independent replication: tissues reuse animals from the same mission. [NASA MHU-3 design](https://osdr.nasa.gov/bio/repo/data/payloads/MHU-3).

**Next:** identify a separate thymus/adipose flight cohort and inspect cell-composition markers before interpreting a mechanism.

## Results that constrain the story

- Human cardiac flight responses agree in only **1 of 3 cell-line splits**, in expression and both model summaries. Post-flight samples are not consistently closer to ground; different collection times prevent a recovery conclusion.
- Bed-rest shifts are reasonably consistent in GSE113165, but the three-pair GSE126865 model result agrees in only **1 of 3 splits**. Analog observations cannot be labeled flight replication.
- RR-1 and RR-23 quadriceps directions align in model mean (cosine 0.857), less so in raw expression (0.190). RR-4 does not align with either in model mean (−0.225, −0.070). A favorable pair is not a universal muscle result.
- Across 54 contrasts, median split agreement is 0.990 for expression, 0.739 for model mean, and 0.830 for model std. This descriptive screen provides **no general model advantage**. Cosines and distances in different representations are not predictive-performance measures.

## Robustness and provenance

Used the author's pinned inference source, canonical 15,165-gene vocabulary, species-specific exon lengths, and observed-canonical-universe log1p(TPM). Human coverage was 99.65% in the older available ARCHS4 matrix and 99.89% in the chip count file. One mouse source lacked 10 genes. Missing genes remain structurally missing and receive the training mask token; they are not primary measured-zero inputs. This is an exploratory extension of the complete-input contract. Expression comparisons use the 15,100 genes observed in every sample. Human shift directions are insensitive to mask versus zero filling (all cosines >0.9998; relative changes <1.9%). This check does not validate every mapping or normalization choice.

The model produced finite 559×512 mean and std summaries on the recovered A100 at **149.165.175.241** in **204.7 seconds**. All sample IDs align and the input hash matches the inference report. Checkpoint SHA256: `f3491beaa697a0408dc1daeb6f8d648566bd46bafc6e44938d723e7ffc325541`; input SHA256: `7a0545741784b7af00e96c28f47001ff61bf03977f67ba881ba8c0bfdaafd8f6`. More provenance is in `inference_report.json`, `preprocessing_audit.json`, and `artifact_provenance.json`.

Balanced splits respect paired donors/cell lines where applicable; other cohorts use within-condition sample splits. We replaced the initial 200 random draws with enumeration of all 3–400 balanced partitions to remove Monte Carlo noise and compare representations on identical partitions. The cohort/readout rules did not change. Split agreement is not a p-value, and leave-one-out cosine relative to the full shift is a sensitivity check rather than independent validation. PCA is an unsupervised descriptive fit within each contrast, not a held-out evaluation. No claim survives merely because a plot separates conditions.

The supplied pretraining catalog labels the 12 chip samples unseen; the other 48 human samples include 39 training and 9 validation samples. Mouse overlap is unknown. This is exploratory reuse, not a held-out generalization benchmark.

## Reuse

Reproduce local analysis from the saved inputs and embeddings:

```sh
OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 python3 fa26/analyze_general_survey.py --output fa26/artifacts/general_survey_2026-09-12
OPENBLAS_NUM_THREADS=2 python3 fa26/summarize_survey_leads.py --output fa26/artifacts/general_survey_2026-09-12
```

See `contrast_pattern_metrics.csv`, `muscle_gene_leave_one_out.csv`, and `human_candidate_expression_shifts.csv` for the observations behind the brief. The four supplied human cohorts are documented at [GSE137081](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE137081), [GSE234465](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE234465), [GSE113165](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE113165), and [GSE126865](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE126865).
