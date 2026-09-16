# Linked BridgeRNA benchmarks — source review, September 14

Source: [sample_embeddings/benchmarks](https://github.com/alwalt/bridge-rna/tree/sample_embeddings/benchmarks), pinned to **ddf5e4bd1e48692dbc41caead413d6ca56154fca**. This is the same author revision referenced by our frozen inference audit. We had previously retained only a subset of the author source; the benchmark folders provide additional methods, manifests and results.

This review downloaded selected code, metadata/result tables and overviews, not all source expression matrices or ignored work caches. No upstream script or training job was executed. The reported numerical results below are **author-supplied results, not an independent reproduction**. The root index is less complete than the folder contents; use the relevant saved tables and pipeline code.

## Data identification is substantially resolved

`library_prep_disentanglement/results/task4a_data_audit/controlled_dataset_audit.csv` identifies:

- **Chen 2020:** 40 independent donors, each with the same naïve CD4 T-cell RNA prepared using poly(A) selection and Ribo-Zero. The [primary paper](https://www.nature.com/articles/s41597-020-00719-4) confirms the paired design. The preparation script asserts 80 profiles, one per protocol per donor. DOI 10.1038/s41597-020-00719-4; source downloads are recorded in `prepare_controlled_data.py`.
- **Zhao 2018, SRP127360:** two biological source RNAs (pooled blood and colon), four technical libraries per protocol per source, totaling 16 profiles. This is a small external challenge, not 16 independent biological replicates. [Primary paper](https://www.nature.com/articles/s41598-018-23226-4).
- **GSE150097:** candidate only; authoritative pairing is not established. Do not promote it to paired validation.

The link therefore supplies a concrete controlled preparation benchmark. It does not demonstrate that any later mentor-provided dataset is identical, nor that all needed data are already cached locally.

## The RR1/RR3 mapping is more specific than our provisional inventory

The author's `rr1_rr3_robust_response_comparison/results/manifest/exact_matched_animals.csv` defines 34 profiles from **17 matched animals**:

| Comparison | Original → remeasurement | Matched biological units | Preparation labels |
|---|---|---:|---|
| RR1 | OSD-48 → OSD-168 | 4 flight + 5 ground | poly(A) → ribodepleted |
| RR3, 39-day | OSD-137 → OSD-168 | 2 flight + 2 ground | ribodepleted → ribodepleted |
| RR3, 40-day | OSD-137 → OSD-168 | 2 flight + 2 ground | ribodepleted → ribodepleted |

Our earlier 18-animal figure described flight/ground candidates within OSD-168 alone. It was not an exact cross-accession matched cohort. The author's RR1 matched subset excludes M29. Reuse this explicit mapping for reproduction, then confirm original metadata and exclusions before new training.

RR1 changes read layout/length/depth and recorded preservation context along with preparation; its outcome is protocol-associated, not a pure causal poly(A) effect. RR3 is a valuable same-preparation remeasurement control. The goal is to preserve its reproducibility, not to erase RR1/RR3 mission or strain identity.

## Existing correction is not encoder fine-tuning

`run_task4.py` loads cached 512-D arrays and trains `task4_model.Disentangler`: two small MLPs produce a 64-D candidate invariant representation (FE) and a 64-D library-associated representation (RE). It uses reconstruction, pair similarity, an RE preparation classifier and an FE gradient-reversal classifier. BridgeRNA itself is not part of this optimization.

The author reports unsuccessful general correction. The initial external test has two biological sources and several AUROCs near zero; systematic prediction inversion is not loss of label information. The later correction table reports orientation-free AUROC explicitly. In `correction_tradeoff_summary.csv`, removing two controlled components changes RR1 response cosine −0.804 → +0.221 but reduces RR3-39 from 0.790 → 0.480 and response-matrix preservation to 0.619. The existing FE representation also retains strongly predictable preparation labels in its within-cohort probe; its encoder was fit on that cohort, so this is not a fully held-out correction estimate.

A favorable RR1 sign or mixed embedding plot is therefore not the success criterion. The next distinct test is controlled **encoder adaptation** with matched ablations, not another unqualified claim that a residual is pure biology.

## Existing layer/readout benchmarks should be reused

`frozen_sample_embedding_readout` already compares layers 11/12, mean/SD, attention pooling and program-level summaries using a 3,272-sample, 14-tissue cohort with five study-disjoint folds. Its fixed-readout results give layer-11 mean+SD macro-F1 0.8355 versus layer-12 0.8332; the difference is small and layer-11 worsens a response-similarity check. Program-level pooling has additional promising results but is much larger and is not an updated checkpoint.

Do not repeat these comparisons as though untested, or claim LoRA has been demonstrated superior. Reproduce the needed fixed baselines, use development-only layer selection, and compare adapter/last-block updates under the same losses and data splits. A broad early-to-final diagnostic remains distinct from the existing layer-11/12 comparison.

## Integration notes before reuse

- Retain the audited `r7hnr92k` checkpoint, canonical order, species labels and natural log1p(TPM) contract.
- Upstream controlled-data preparation zero-fills absent vocabulary genes. Our survey distinguishes missing genes with an explicit mask. Audit coverage and harmonize this difference before combining outputs; do not silently change the original replication baseline.
- Keep all protocols/technical replicates from an animal or donor in the same split.
- The upstream external data and RR1/RR3 outcomes have already been examined publicly and in this review. They are development/challenge evidence; a new untouched confirmation set would be needed for pristine confirmation.
- The original correction study had no verified independent validation dataset and used fixed epochs. Our new method comparison may use nested donor-held-out development within Chen, explicitly without claiming study-independent validation, while preserving external challenges.

Current action plan: [two-stage fine-tuning pipeline](../../docs/2026-09-14-FINETUNING-PIPELINE.md).
