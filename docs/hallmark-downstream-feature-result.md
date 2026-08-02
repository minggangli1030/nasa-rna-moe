# Hallmark-50 downstream-feature development result

**Completed:** 2026-08-02

## Decision

The frozen D2 gate failed: `HALLMARK_FEATURES_FAIL`.

The prespecified primary, Hallmark-50 concatenated with fold-fit PCA64, achieved AUROC
0.732630 versus 0.732770 for PCA64 and 0.725921 for raw expression. Its study-bootstrap
95% interval versus PCA64 was −0.000666 to +0.000216 and versus raw expression was
−0.068670 to +0.086369. Neither interval was strictly above zero.

Hallmark+PCA did beat all four negative controls by point AUROC: permuted Hallmark
0.614356 and three size-matched random-set draws at 0.569364, 0.583533, and 0.634436.
That control result does not rescue the primary gate. Hallmark-50 alone scored 0.567394
and was worse than both PCA and raw, with both bootstrap intervals entirely below zero.

## Interpretation

Deterministic Hallmark features do not add study-robust spaceflight-state information
beyond fold-fit PCA64 on this accessed 292-sample, 18-study OSDR cohort. The previous
Hallmark signal against an organ-only base does not translate into a competitive
standalone downstream feature representation. No condition or threshold is selected
post hoc, and Hallmark remains excluded from the final architecture.

This is development evidence, not untouched confirmation. It says nothing negative
about Hallmark biology generally; it only rejects this frozen aggregation and task.

Compact verified result:
`artifacts/final_evaluation/hallmark_downstream/evaluation_f38b125/`.
