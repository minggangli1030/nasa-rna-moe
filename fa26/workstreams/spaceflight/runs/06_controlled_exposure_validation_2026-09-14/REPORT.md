# Controlled-exposure validation — September 14, 2026

**Verdict: BRIDGE supports a useful irradiation-associated probe in one cell context, but the current probe is not specific or transferable enough to label a flight sample “radiation-driven.”** The six broad pathway averages are also insufficient as a reliable exposure bottleneck.

[Specificity/transfer figure](specificity_and_transfer.pdf) · [All-model AUROC figure](exposure_probe_validation.pdf) · [Dataset audit](dataset_audit.csv)

## What ran

Downloaded and audited **123 new public profiles**: 91 from GSE230181 and 32 from GSE242706. Prepared 15,061 common observed canonical genes with audited sample labels and columns. Frozen BRIDGE inference ran on moe-reboot’s A100 in **45.5 seconds**. Small local logistic heads were then fitted; no encoder update occurred.

The initial radiation-associated head used **38 normal IMR90 cultures** (19 irradiated, 19 controls) from five named experiment sets spanning four expression files. Entire files were held out; the B/C sets stayed together. Other cell types were secondary within-study tests; the lung-chip study supplied a separate external test. These are culture replicates, not 123 donors.

Four fixed comparisons used expression, PCA (5 components), BRIDGE mean+SD, and the same six predefined response-program averages. No layer/LoRA search, sign reversal, threshold tuning or calibration was performed.

## 1. Within-study recognition is strong, but not unique to BRIDGE

Across all four held-out files, BRIDGE, expression and PCA each achieved **AUROC 1.0 and balanced accuracy 1.0** for irradiated versus control IMR90 cultures. Thus this task provides no clear predictive advantage for BRIDGE. The six-program head varied substantially: AUROC **0.22–1.0**, balanced accuracy **0.25–0.83**. A small set of generic pathway averages does not reliably summarize the exposure decision.

## 2. Non-radiation stresses expose a specificity problem

The BRIDGE probe ranked irradiated cultures above bleomycin, antimycin, oligomycin and rotenone cultures in the matched held-out-file comparisons (AUROC 1.0). However, a high ranking score does not make its binary decisions specific:

| Non-radiation treatment | Positive calls, initial BRIDGE probe | Matched controls positive |
|---|---:|---:|
| bleomycin | 4/5 | 0/5 |
| antimycin | 0/5 | 0/5 |
| oligomycin | 0/5 | 0/5 |
| rotenone | 3/3 | 0/3 |
| ras_induction | 3/3 | 0/3 |

Ras is a separate hTERT/inducible-genotype context, and its file has no irradiated comparison. It is a secondary specificity challenge. Treatments, timing, and culture protocols differ; these tests do not isolate a single common mechanism.

## 3. Independent-study transfer depends on cell type and time

| External lung-chip stratum | BRIDGE AUROC | Balanced accuracy | TP / TN / FP / FN |
|---|---:|---:|---|
| Lung endothelium_6h | 0.812 | 0.625 | 1 / 4 / 0 / 3 |
| Lung endothelium_7d | 1.000 | 1.000 | 4 / 4 / 0 / 0 |
| Lung epithelium_6h | 1.000 | 0.500 | 0 / 4 / 0 / 4 |
| Lung epithelium_7d | 0.688 | 0.500 | 0 / 4 / 0 / 4 |

Each row has four irradiated and four sham profiles. Do not pool channels and time points as independent donors. Expression and PCA achieved AUROC 0.69–1.0 but balanced accuracy 0.5 in every stratum, illustrating strong score-offset/domain effects. The one perfect BRIDGE stratum is encouraging development evidence, not broad validation.

## 4. A bounded correction helps one challenge but hurts transfer

After seeing the false positives, one **explicitly adaptive** comparison added verified non-IR normal-IMR90 treatments and vehicle controls as training negatives. The full development set became 61 cultures; entire-file holdouts remained intact. Ras/hTERT samples were excluded. The same model settings and threshold were retained.

BRIDGE bleomycin false positives fell from **4/5 to 1/5**, with **5/5 irradiated** cultures still positive in that held-out file. Rotenone remained **3/3 false positives**, and **2/3 controls** in its file became positive. External lung-chip balanced accuracy became **0.5 in every stratum**, with all samples called positive; AUROC ranged **0.25–0.81**. This version is not promoted as a generally improved detector. The exposure label needs more varied, matched examples rather than an outcome-selected threshold.

The adaptive comparison used already inspected evaluation data; its apparent local improvement needs independent confirmation. See `hard_negative_amendment.json` and `hard_negative_metrics.csv`.

## 5. Connection to the existing flight classifier

As an explicitly out-of-domain diagnostic, the two unchanged muscle-chip flight heads were applied to the controlled-exposure embeddings. Radiation lowered the old flight score in **all five IMR90 experiment sets under both heads**. This does not prove radiation can never contribute in muscle; tissue, dose, timing and preparation differ. It does show that the current flight head cannot simply be relabeled as a radiation detector. No radiation percentage is assigned to a flight sample. The prior failed cross-flight result is unchanged.

## Gravity data audit and next step

GSE222998 is a relevant new candidate with eight human HEK293 ISS RNA-seq profiles comparing microgravity and centrifuged 1g at 24/48 hours, plus human ground analog experiments. The author files contain transcript/CDS counts across many isoforms, rather than gene-level counts compatible with the current preprocessing contract. The NCBI processed gene-count route was unavailable (404). It was audited but not fed into BRIDGE by summing potentially overlapping transcript counts. A dedicated mapping/quantification audit is the next technical prerequisite; some analog treatment cells have only one sample.

The previously analyzed MG63/HMEC-1 onboard-1g datasets remain useful context but are not new independent validation. Radiation and gravity remain separate targets; exposed and control groups must be matched within tissue/time/experiment.

**Recommended next decision:** retain the initial irradiation-associated probe as an exploratory comparator, not a deployed response detector. Prioritize a controlled gravity quantification audit and tissue-matched perturbation data, then test response concepts in the intended muscle/flight domain. An eventual concept-based flight head should expose uncertainty and unassigned evidence. Additional LoRA capacity is not the current demonstrated need.

## Numerical correction and provenance

A near-constant TAS1R2 training feature (SD approximately 1e-22) caused extreme expression/PCA logits in an initial pass. The corrected comparison applies a training-only variance filter (variance > 1e-12) before scaling for every fitted model. Earlier outputs were preserved under `history/before-near-zero-variance-fix/`. A regression check confirms perturbing that excluded feature cannot affect predictions. Primary BRIDGE conclusions were unchanged. No variance threshold was selected for better AUROC.

Checks cover input/embedding IDs and hashes, label/column mapping, finite values, whole-file separation, training-only preprocessing, convergence and the variance regression. Two GSE242706 control profiles have contradictory cell-line fields; agreeing titles/cell-type fields were used, and conflicts remain recorded. Pretraining-catalog labels are 122 “unseen” and one absent; this does not prove absence from every version of pretraining.

Key files: `protocol.json`, `input_audit.json`, `label_column_audit.csv`, `manifest.csv`, `metrics.csv`, `specificity.csv`, `predictions.csv`, `controlled_program_expression.csv`, `old_flight_head_stress_response.csv`, `hard_negative_metrics.csv`, `verification.json`, and saved `heads/`.

Sources: [GSE230181](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE230181), [GSE242706](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE242706), [GSE222998](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE222998). Downloaded SOFT records, expression files and hashes are retained under `sources/`.

All computation is complete. The VM is idle; no new background job or watcher is required.
