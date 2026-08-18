# Condensed project chronology

This file is the readable milestone history after the 2026-08-17 closeout. Detailed
operational notes remain recoverable from Git history and the ignored pre-cleanup
snapshot described in [`docs/recovery-and-data.md`](docs/recovery-and-data.md).

## 2026-07-17 — Stage 0 species specialists

- Corrected study-aware human/mouse evaluation completed.
- An expression-only router reliably selected species specialists.
- The positive two-expert result motivated the eight-organ summer extension.

Canonical result: [`docs/stage0-final-result.md`](docs/stage0-final-result.md).

## 2026-07-22 to 2026-07-27 — Stage 1 organ specialists

- Organ-supervised adapters and target-hidden routing were developed under frozen
  donor/study-aware protocols.
- The reverse GTEx-to-ARCHS4 evaluation retained 821 QC-passing samples from 63
  connected studies across eight organs.
- Relative to the shared model, true-organ K8 improved balanced reconstruction by
  3.797%, hard automatic routing by 3.633%, and soft routing by 3.676%.
- All three fixed seeds improved; pooled-adapter and random-K controls were neutral.
- The evaluation is post-access QC-amended, not pristine confirmation.

Canonical result: [`docs/stage-1-end-result.md`](docs/stage-1-end-result.md).

## 2026-07-28 to 2026-07-30 — Stage 2 sharing tests

- All 56 same-budget directed substitution edges were harmful across the frozen
  seeds.
- Recipient-preserving addition produced isolated positive edges but none reliably
  beat adding more target-organ data.
- Tissue site briefly passed a screen but failed a matched generic-capacity control.
- No reproducible cross-organ sharing rule was adopted.

Canonical results:
[`docs/stage2-directed-transfer-preliminary-result.md`](docs/stage2-directed-transfer-preliminary-result.md)
and [`docs/stage2-additive-transfer-result.md`](docs/stage2-additive-transfer-result.md).

## 2026-07-30 to 2026-08-02 — Downstream evaluation

- The frozen OSDR cohort contained 292 samples from 18 studies after exact structured
  label and QC rules.
- Raw expression AUROC was 0.726 and fold-fit PCA AUROC was 0.733.
- Learned pooled and specialist conditions were weaker; no specialist mode passed the
  all-seed direction gate.
- Hallmark features, residual analyses, and low-label extensions did not create a
  robust specialist advantage.
- The downstream branch closed without seed, organ, layer, or cohort selection.

Canonical result:
[`docs/stage1-osdr-downstream-result.md`](docs/stage1-osdr-downstream-result.md).

## 2026-08-03 to 2026-08-04 — Closeout diagnostics

- The frozen-trunk K8 donor-budget curve was positive in all 15 budget-by-seed runs
  from 25 to 200 donors per organ.
- The effect did not grow monotonically across seeds, so no scaling-law claim was
  made.
- The organ-label compatibility audit was saturated by simple PCA and failed its
  deployable-advantage gate.
- The final K8 package was frozen and checksum-bound.

Canonical results:
[`docs/gtex-k8-adapter-scale-result.md`](docs/gtex-k8-adapter-scale-result.md) and
[`docs/gtex-k8-mislabel-result.md`](docs/gtex-k8-mislabel-result.md).

## 2026-08-04 to 2026-08-11 — Future contracts frozen

- A metadata-only ARCHS4 catalog identified 23,975 eligible rows across 931 study
  values without reading candidate expression.
- The untouched Track A contract fixed eight organs, deterministic QC, no
  replacements, blind hard routing versus pooled, all-seed direction, paired-study
  uncertainty, and a per-organ safety bound.
- The contract was deliberately left unexecuted for future work.

Canonical contract:
[`artifacts/final_evaluation/track_a_confirmation_v1/`](artifacts/final_evaluation/track_a_confirmation_v1/).

## 2026-08-17 — Training-objective diagnosis

- On unstandardized GTEx `log1p(TPM)`, 71.557% of scored variance was between genes,
  19.192% between tissues within gene, and 9.251% within tissue.
- Train-only per-gene standardization removed the between-gene term by construction
  and increased the within-tissue share to 46.638%.
- This measures loss allocation, not the amount or location of spaceflight-response
  signal. No standardized model was trained.

Canonical result:
[`docs/training-variance-decomposition-result.md`](docs/training-variance-decomposition-result.md).

## 2026-08-17 — Final presentation and project closeout

- The final six-slide AI4LS deck separated the positive reconstruction result from
  the downstream limitation.
- The story begins with the previous two-species pilot and this summer's eight-organ
  extension.
- The limitation uses a missing-word versus missing-gene-value analogy to explain why
  reconstruction can rely on typical values and fail to transfer.
- The final PDF and recording were checksum-recorded.
- The reachable Jetstream VM, six Git bundles, final model package, and all compact
  result files were backed up; public raw data were intentionally excluded.
- README, status, progress, presentation, recovery, and future-work documentation were
  consolidated.

Canonical handoff: [`docs/project-closeout.md`](docs/project-closeout.md).
