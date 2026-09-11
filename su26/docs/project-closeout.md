# NASA RNA mixture-of-experts: project closeout

**Closeout date:** 2026-08-17
**Project state:** summer research complete; no active training or evaluation
**Primary handoff:** this document, [`recovery-and-data.md`](recovery-and-data.md),
and the final presentation package

## Executive summary

The project tested whether RNA models benefit from biological specialists instead of
one shared model. A two-expert human-versus-mouse pilot was positive, so the summer
work expanded the idea to eight human-organ specialists with automatic routing.

The central result is bounded but reproducible: organ specialists reduced masked-gene
reconstruction error by about 3.6–3.8% on the externally evaluated ARCHS4 cohort, and
automatic routing retained about 96–97% of the revealed-organ benefit. The result was
positive in all three fixed training seeds over 821 samples, 63 connected studies,
and eight organs.

The improvement did not transfer to the tested downstream task. Frozen learned
outputs did not beat raw expression or fold-fit PCA for OSDR spaceflight-versus-ground
classification. The reconstruction objective can reduce error by learning stable gene
and tissue averages; it does not necessarily require the subtle within-tissue changes
needed for biological-response classification.

The honest conclusion is:

> Biological specialization improved the task the model was trained to perform, but
> reconstruction alone did not produce a better biological-response representation.

## Final evidence

| Question | Final answer | Evidence boundary |
| --- | --- | --- |
| Do species specialists help? | Yes. The expression-only human/mouse router was reliable and improved corrected reconstruction evaluation. | Stage 0 development and study-aware holdout. |
| Do organ specialists help reconstruction? | Yes. True-organ, hard-routed, and soft-routed K8 models improved balanced ARCHS4 reconstruction by 3.797%, 3.633%, and 3.676%. | Post-access QC-amended external evaluation, not pristine confirmation. |
| Is automatic routing useful? | Yes. Hard and soft routing retained about 95.7% and 96.8% of the revealed-organ gain. | Same 821-sample external evaluation. |
| Is the gain only extra generic capacity? | The tested pooled-adapter and random-K controls were neutral. | Does not exhaust every possible equal-parameter generic K8 control. |
| Does simple cross-organ sharing help? | No reliable rule was found. All 56 same-budget substitution edges were harmful; additive sharing did not consistently beat more target-organ data. | GTEx donor-disjoint development analysis. |
| Do the frozen outputs improve the tested spaceflight-state classifier? | No. Raw expression and PCA were stronger than every learned condition. | Accessed OSDR development benchmark; not a universal impossibility result. |
| Why might transfer fail? | The reconstruction loss mostly rewards stable gene/tissue structure and permits typical-value shortcuts. | Descriptive diagnosis, not a state-information bound. |

Canonical result documents:

- [`stage0-final-result.md`](stage0-final-result.md)
- [`stage-1-end-result.md`](stage-1-end-result.md)
- [`stage1-osdr-downstream-result.md`](stage1-osdr-downstream-result.md)
- [`stage2-directed-transfer-preliminary-result.md`](stage2-directed-transfer-preliminary-result.md)
- [`stage2-additive-transfer-result.md`](stage2-additive-transfer-result.md)
- [`gtex-k8-adapter-scale-result.md`](gtex-k8-adapter-scale-result.md)
- [`training-variance-decomposition-result.md`](training-variance-decomposition-result.md)

## Important limitations

1. The 821-sample ARCHS4 result was externally evaluated but is not a pristine
   preregistered confirmation. Six unchanged-QC failures were removed after expression
   access, before efficacy scoring, with no replacement or model change.
2. The primary effect is a modest 3–4% reconstruction improvement. It is not evidence
   of clinical utility or improved spaceflight decisions.
3. The OSDR downstream benchmark is heterogeneous and unevenly powered. Only skeletal
   muscle supported a strong organ-specific analysis, and simple features were already
   near the ceiling there.
4. The variance diagnostic measures allocation of squared-error loss, not where
   spaceflight-response information resides. GTEx has no perturbation labels.
5. Per-gene standardization moved the measured within-tissue loss share from 9.251%
   to 46.638%, but no standardized model was trained. This is a candidate intervention,
   not a classification result.
6. Several historical experiments were intentionally stopped by frozen gates. Their
   negative outcomes should not be reopened by selecting favorable seeds, organs,
   layers, or cohorts after access.

## Final model and preserved evidence

The frozen K8 package is `final_k8_package_dc562cc`. The tracked package manifest and
output contract are under
[`artifacts/final_model/final_k8_package_dc562cc/`](../artifacts/final_model/final_k8_package_dc562cc/).
The complete model-bearing package is preserved locally at:

```text
backups/jetstream-final/2026-08-17/
  moe-reboot-results/final_k8_package_dc562cc/
```

Its `FULL_SHA256SUMS` ledger passed complete verification at closeout. Earlier
checksum-bound final-refit, three-seed training, and confirmation bundles also passed:

```text
backups/stage1_k4_final_refit_e8c0383/
backups/stage1_gtex_to_archs4_training_98e2cba/
backups/stage1_organ_k_confirmation_53ec6c4/
```

These paths are intentionally ignored by Git. See
[`recovery-and-data.md`](recovery-and-data.md) before deleting or moving the laptop
copy.

## Final presentation package

The delivered AI4LS package is:

- HTML deck: [`../presentation/2026-08-17-ai4ls-final.html`](../presentation/2026-08-17-ai4ls-final.html)
- PDF deck: [`../presentation/2026-08-17-ai4ls-final.pdf`](../presentation/2026-08-17-ai4ls-final.pdf)
- speaking script: [`2026-08-17-ai4ls-speaking-script.md`](2026-08-17-ai4ls-speaking-script.md)
- recording: `presentation/2026-08-17-ai4ls-final-recording.mp4` when present locally

The recording SHA-256 at closeout is
`84ec1af45a6ae34aa45e230befbc93df2f80b0bb63c560fe78f8bd6c79183fea`.
The PDF SHA-256 is
`23be460905fcb71c8afd1c0aa08b74369ed544c81c1607c9e13a2f7aa67ee328`.

## What this final session changed

The final presentation work intentionally simplified the research story for a
nontechnical NASA audience:

1. Slide 2 now explains the progression from two species experts to eight organ
   experts and preserves the hospital/front-desk analogy.
2. Slide 3 contains only the positive specialist-versus-shared reconstruction result.
3. Slide 4 contains the downstream limitation and the missing-word versus
   missing-gene-value analogy. It explains the typical-value shortcut without
   presenting the technical variance decomposition.
4. The narration distinguishes the training task—fill in hidden gene values—from the
   downstream task—classify whether an RNA sample reflects a spaceflight-related or
   control response.
5. The final script was shortened to about 523 spoken words for direct recording.
6. The HTML deck was exported and visually checked as a six-page 16:9 PDF.

## Repository cleanup

- Public expression matrices and reproducible preprocessing outputs were deliberately
  left out of the closeout backup; their sources, hashes, and rebuild commands are in
  [`recovery-and-data.md`](recovery-and-data.md).
- The final recording was moved under `presentation/` and excluded from normal Git
  because it exceeds GitHub's regular per-file limit.
- A duplicate root-level PDF was removed after confirming it was byte-identical to
  the canonical PDF under `presentation/`.
- Two unrelated project directories were moved intact, not deleted, to
  `/Users/minggangli/Projects/_recovered-from-nasa-rna-moe-2026-08-17/`.
- Redundant status and presentation drafts were removed only after the original
  documents and working-tree patch were preserved under
  `backups/project-closeout-2026-08-17/`.

## If the project resumes

Resume in this order; do not restart with open-ended architecture search.

### 1. Reproduce and verify the closeout state

- restore the final package and verify `FULL_SHA256SUMS`;
- rebuild public expression data using [`recovery-and-data.md`](recovery-and-data.md);
- run focused tests for the workflow being resumed; and
- reproduce the existing compact reports before opening a new outcome.

### 2. Run the untouched reconstruction confirmation

The expression-blind contract is frozen under
[`artifacts/final_evaluation/track_a_confirmation_v1/`](../artifacts/final_evaluation/track_a_confirmation_v1/).
It fixes all 23,975 metadata-eligible rows, eight organs, the 14,000-nonzero-gene QC
rule with no replacements, and blind hard routing versus pooled as the single primary
comparison. Stop before efficacy scoring if any organ has fewer than eight connected
series or 50 samples after QC.

This is the cleanest way to confirm the result the model was actually trained to
achieve. Do not alter the cohort or gate after expression access.

### 3. Test one inexpensive objective-alignment pilot

Train one separately versioned pilot with train-only per-gene standardization or a
robust variance-scaled reconstruction loss. Freeze in advance:

- the training and inference transforms;
- zero-variance and low-variance gene handling;
- mask-token behavior;
- de-standardized reconstruction reporting; and
- raw-expression, PCA, and equally capable shared-model controls.

The pilot matters only if its frozen representation improves a downstream task; a
better standardized reconstruction score alone is insufficient.

### 4. Build a stronger downstream benchmark

Use a larger, carefully labeled, multi-organ cohort with study- or mission-grouped
splits and measurable headroom. Require raw expression and fold-fit PCA as primary
baselines. Separate development and untouched confirmation studies before fitting.

If a reconstruction-aligned pilot still fails, move to a supervised or multi-task
objective that directly rewards biological-response distinctions. Preserve the
organ-specialist versus equally capable shared-model comparison.

## Claims to preserve

Use:

- “lower reconstruction error,” not unrestricted “better model”;
- “externally evaluated, pending untouched confirmation,” not “validated”;
- “did not improve classification under this test,” not “contains no state
  information”; and
- “objective mismatch is plausible,” not “the objective is proven wrong.”

Do not claim that simple sharing is universally harmful, that the variance fractions
are fractions of spaceflight signal, or that specialization has practical biological
impact before it beats raw data and standard controls on a suitable downstream task.
