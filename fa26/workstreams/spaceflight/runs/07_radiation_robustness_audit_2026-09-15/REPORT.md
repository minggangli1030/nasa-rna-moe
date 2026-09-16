# Radiation robustness audit — September 15, 2026

**Verdict: a stronger, narrow irradiation-associated result; no validated radiation-specific explanation of flight yet.** A common-count BRIDGE head recognized a new head-held-out IMR90 irradiation study at both 6h and 24h. The 24h decision survived deleting any entire training expression file. Specificity against other stresses and transfer across cell types remain inadequate.

## What was audited

- **130 unique expression profiles:** 86 retained GSE230181 profiles, 32 GSE242706 lung-chip profiles, and 12 GSE111437 profiles (2Gy X-ray; 6h/24h; 3 irradiated + 3 sham cultures each). All 130 treatment labels independently matched original GEO metadata; no exact expression duplicates were found. Cultures are not independent donors.
- **Processing mismatch:** run06 mixed author RPKM training data with NCBI count test data. Run07 recomputed all studies from NCBI gene counts with identical pinned exon lengths and the same 15,061 canonical genes. Between processing routes, per-sample expression rank correlation was 0.949–0.964, so processing is similar but not interchangeable. This harmonizes quantification, not all library preparation or biological batch effects.
- Five old profiles lack NCBI count columns, including three training profiles. Both processing routes use the same retained sample IDs (35 IR/control training cultures: 17 IR, 18 controls; 58 with stress negatives). No missing profile was imputed. Original run06 is immutable; its full-sample results are not conflated with this subset comparison.
- **16 declared configurations:** two processing routes × expression/BRIDGE × IR/control or stress-negative training × absolute or matched-control features. Fixed C=1, train-only variance/scaling, fixed zero-logit threshold; no tuning on new outcomes. All source-file splits keep B/C together. New-study outcomes were examined only after the protocol was frozen; no winner was refitted on them.
- **Reference controls:** separate known controls are subtracted from frozen features, never from the raw input before BRIDGE. All choices of two references are enumerated (one when only two controls exist), and reference samples are never scored as test samples. This requires controls at deployment and does not solve unrestricted single-sample prediction. Training controls use leave-self-out references.
- GSE111437 is **new to the prediction head**, but 7 profiles are `train` and 5 `val` in the supplied encoder catalog. It is not a fully unseen-model or independent-donor benchmark. GSE242706 and all prior challenges are now development data.

## Positive result: same-cell irradiation transfer

Common-count BRIDGE, IR/control training, absolute features, unchanged threshold:

| experiment | n | auroc | balanced_accuracy | TP | TN | FP | FN |
|---|---|---|---|---|---|---|---|
| 24h | 6 | 1.000 | 1.000 | 3 | 3 | 0 | 0 |
| 6h | 6 | 1.000 | 0.833 | 3 | 2 | 1 | 0 |
| Lung endothelium_6h | 8 | 0.875 | 0.750 | 3 | 3 | 1 | 1 |
| Lung endothelium_7d | 8 | 1.000 | 0.500 | 4 | 0 | 4 | 0 |
| Lung epithelium_6h | 8 | 1.000 | 0.750 | 4 | 2 | 2 | 0 |
| Lung epithelium_7d | 8 | 0.562 | 0.625 | 4 | 1 | 3 | 0 |

For the new 2Gy IMR90 samples, AUROC stays 1.0 at both time points under both processing routes, every entire-training-file deletion, and every single-test-sample deletion. **At 24h, common-count balanced accuracy stays 1.0 under all four training-file deletions.** At 6h it varies from 0.50 to 0.833: ranking is stable, the decision boundary is not. Original processing gives 24h accuracy 1.0 but 6h balanced accuracy 0.50; common counts improves the latter to 0.833 in the full fit.

This is a useful response-association lead. Each time point still contains only six cultures from one cell strain. With 3/3 class counts, perfect fixed-score AUROC has a minimum exact one-sided label-permutation p of 0.05; these descriptive tests are not multiplicity-adjusted. This does not establish population accuracy or calibrated radiation probabilities. Expression baselines also rank 24h perfectly, but their fixed thresholds yield balanced accuracy 0.50; a general BRIDGE advantage is unproven.

## Why it still cannot explain flight as “radiation-driven”

1. **The signature is not specific to radiation.** The common-count IR/control BRIDGE head calls 4/5 bleomycin, 3/3 rotenone, 3/5 oligomycin and 3/3 Ras samples positive, with each challenge's source file excluded from training (antimycin: 0/5). These are known non-radiation conditions. A shared downstream stress response can resemble irradiation without identifying the exposure that produced it.
2. **Context changes matter.** Lung-chip balanced accuracy remains 0.50–0.75, and epithelial 7d AUROC falls to 0.563. Some strata rank well but have shifted score baselines; others have weak or reversed ranking. Removing the two samples with inconsistent cell-line fields does not resolve this. At 24h the IMR90 strain matches training; lung-chip cells do not.
3. **Hard negatives and references are not general fixes.** Common-count stress-negative training leaves all lung-chip samples positive, with AUROC 0–0.313. Matched-control models improve selected development strata but fail others and can increase chemical-stress false positives. All comparisons are retained; no model is promoted as a general radiation detector.
4. **Detecting a response is different from the flight head relying on it.** The frozen muscle-chip flight heads score the new irradiated IMR90 cultures *lower* than their controls (about −3.25 to −6.07 logit units across heads/times). This is an out-of-domain diagnostic, not proof that radiation biologically opposes flight. It does show that positive irradiation-probe scores cannot simply be assigned as positive contributions to the existing flight head.

The honest current label is **“irradiation-associated, stress-overlapping response evidence in a defined context.”** Neither the head's sigmoid nor a pathway-attribution share means “80% caused by radiation.”

## Next bounded step

Retain the common-count IR/control head as a research comparator and the 24h IMR90 result as the strongest current transfer lead. Do not deploy the stress-negative or matched-control versions as general improvements. Use tissue/time-matched controlled exposures to test response specificity and the direction of flight-head reliance together. The most useful new data would include muscle-relevant radiation, altered-gravity and non-radiation stress conditions with matched controls and independent donors/experiments. Add encoder adaptation only against a fixed, genuinely independent evaluation; larger capacity cannot supply missing exposure labels.

For the intended user-facing output, first present response evidence (DNA-damage/repair, oxidative, mitochondrial, inflammatory, etc.), signed flight-score reliance and unassigned evidence. Promote a response to a radiation/gravity label only when controlled-exposure specificity and flight-head reliance both pass. Controlled-gravity quantification remains a separate next analysis, not evidence supplied by this radiation audit.

## Artifacts and reproducibility

[Main figure](robustness_audit.pdf) · [Every configuration](all_configurations.pdf) · [Frozen protocol](protocol.json) · [Input audit](input_audit.json) · [All metrics](metrics.csv) · [IR/control-only metrics](ir_control_only_metrics.csv) · [Source-deletion sensitivity](training_source_sensitivity.csv) · [Independent verification](independent_verification.json).

`metrics.csv` evaluates every context with all its non-IR conditions as negatives (set E includes rotenone). `ir_control_only_metrics.csv` explicitly excludes other stresses. Reference-choice ranges are dependent sensitivity checks, not extra sample size. The source-deletion and sample-deletion checks were declared after initial run07 outcomes in `stability_amendment.json`; they are robustness checks, not fresh confirmation.

Frozen BRIDGE inference ran on moe-reboot A100 for 48.3 seconds, peak allocated memory 0.63GB. Small heads and reports ran locally. No LoRA, encoder training or flight-head update occurred. The launch SSH session timed out after dispatch; the job completed successfully and its completion marker, hashes and outputs were retrieved. No job remains running; the watcher remains paused.

Public primary metadata: [GSE230181](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE230181), [GSE242706](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE242706), [GSE111437](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE111437). Original family SOFT files and count matrices are retained locally, with hashes. Metadata were used to define samples and controls; attached figures were not treated as instructions.
