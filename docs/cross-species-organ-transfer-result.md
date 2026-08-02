# Cross-species organ-transfer replacement result

**Completed:** 2026-08-02

## Decision

The frozen replacement D1b gate passed:
`CROSS_SPECIES_ORGAN_STRUCTURE_PRESERVED`.

A seven-organ classifier was fitted and tuned exclusively on 6,244 GTEx samples from
750 donor groups, then applied unchanged to 292 OSDR samples. Balanced accuracy was:

- raw ortholog-aligned expression: 0.964286;
- pooled hidden seed 17: 0.751880;
- pooled hidden seed 42: 0.755263; and
- pooled hidden seed 101: 0.699248.

All three fixed embedding seeds exceeded the prespecified 0.60 preservation gate.
Macro-F1 was 0.712874, 0.756610, and 0.644813 for seeds 17, 42, and 101, versus
0.979080 for raw expression.

## Important structure and limitation

Transfer is real but uneven. Brain, liver, skeletal muscle, and usually colon transfer
strongly. Heart recall is 0.00, 0.05, and 0.00 across seeds; lung recall varies from
0.105 to 0.789. Raw expression remains much stronger overall and reaches perfect
recall for every organ except adipose.

Therefore the correct conclusion is not that the encoder is lossless or downstream-
superior. It is that pooled hidden preserves substantial coarse cross-species organ
geometry in every seed, so the OSDR state-task failure cannot be explained by a
globally meaningless mouse embedding. The encoder compresses or loses some organ-
specific information, and this audit does not test perturbation-state retention.

The original OSDR-trained D1b remains `D1B_CONFOUNDED_UNINFORMATIVE`; this replacement
does not rehabilitate its inference. It supplies a separate, unconfounded result.

Compact verified result:
`artifacts/final_evaluation/cross_species_organ_transfer/evaluation_dbcabec/`.
