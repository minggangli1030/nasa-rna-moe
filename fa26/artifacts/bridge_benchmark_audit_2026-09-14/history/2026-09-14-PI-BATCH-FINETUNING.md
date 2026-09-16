# PI discussion — first fine-tuning case, September 14, 2026

## Direction agreed in discussion

Make the first fine-tuning question **whether BridgeRNA can suppress technical preparation/batch information while retaining tissue and flight-associated biology**. Use the PI's poly(A)/ribodepleted example and RR1/RR3 as an initial audit target, then repeat the biological survey after a successful correction experiment. Determine data requirements empirically and compare a small number of adaptation methods. Fourier methods were mentioned as an optional technique; they are not a requirement.

This is a proposed experiment and a completed metadata inventory, **not a launched training run**. The screenshot's article and exact sample membership remain unverified; do not claim that the candidate accessions below reproduce that figure. The September 14 slides and earlier discovery outputs remain unchanged.

## Dataset handoff status

The user confirmed that the mentor will send the dataset later; no paper link or
exact dataset is available yet. The screenshot and locally identified OSD-168 records
are provisional context, not the designated training cohort. Do not substitute them
for the mentor's dataset or infer its preparation labels, sample size or pairing.

Before arrival, refine the layer-probe, biological-preservation and matched-method
comparison design. After arrival, audit the supplied sample/animal IDs, preparation
protocols, mission/strain/tissue/condition crossing and count-matrix compatibility;
then freeze splits and choose the pilot size. Dataset-specific training remains pending.

## What “batch” means here

A technical batch effect is a systematic measurement difference caused by sample handling or measurement, rather than the biological question under study. The screenshot specifically labels **polyA** and **ribodepleted** libraries: these are RNA-selection/preparation protocols, not two biological treatments. Preserve differences that reflect tissue, strain, donor and flight condition unless there is an explicit biological reason to remove them.

| Field | Proposed treatment |
|---|---|
| Verified poly(A) selection versus rRNA depletion | Candidate technical domain; compare shared measured genes, with sample/animal links |
| Preparation run, extraction protocol, sequencing platform, processing pipeline | Candidate nuisance labels; confirm whether each is separable from biology |
| RR1 / RR3 or study accession | Mixed technical and biological context; initially diagnose, not automatically erase |
| Tissue / cell type, strain, sex, donor, age, flight duration | Biological covariates to retain or match; donor/animal determines independence |
| Flight versus ground / onboard 1g | Biological condition, not the batch-removal target |
| Training minibatch | Computational grouping; unrelated to the experimental batch label |

A plot clustered by mission does not establish a technical artifact. Conversely, a mixed plot does not establish successful correction. Where batch and biology are completely confounded, the measurements alone cannot identify both effects without additional assumptions or overlap. The experimental-design principle is illustrated by [Song et al., 2020](https://www.nature.com/articles/s41467-020-16905-2); its specific method is for single-cell data, not a bulk-RNA benchmark recommendation.

## What the local inventory establishes

The [metadata audit](../artifacts/batch_metadata_audit_2026-09-14/summary.json) covers 585 selected biological sample records (86 human, 499 mouse). All seven human studies have one recorded instrument per study. First/repeat muscle-chip instruments are NovaSeq 6000/NovaSeq X; this difference is entangled with protocol and flight changes. The cached mouse metadata has assay and preservation context but no explicit sequencing-run or preparation-batch columns. `library_type=unknown` is not a valid preparation label. Missing fields in a cached table may still exist in original ISA assay/protocol files.

**OSD-168 is a candidate RR1/RR3 liver audit target.** The 52 cached library/sample records include:

| Mission | Flight | Ground | Other controls | Candidate animals across all conditions |
|---|---:|---:|---|---:|
| RR1 | 10 records / 5 animals | 10 records / 5 animals | 5 basal + 5 vivarium animals, each represented twice | 20 |
| RR3 | 4 records / 4 animals | 4 records / 4 animals | 4 basal animals | 12 |

RR1 uses C57BL/6J; RR3 uses BALB/c, with different durations. Mission removal could therefore remove strain or exposure-duration biology. The 28 flight/ground records represent **18 candidate independent animals**, not 28. These animal links are inferred from sample names and require original-record confirmation. RR1 records carry `wERCC` and `noERCC`; those labels concern spike-ins and **do not establish poly(A) versus ribodepletion**. Do not infer a preparation label from them.

The [NASA RR1 data description](https://catalog.data.gov/dataset/rodent-research-1-rr1-nasa-validation-flight-mouse-liver-transcriptomic-proteomic-and-epig) explicitly notes resequencing of RR1 liver RNA into GLDS-168. This makes verified same-RNA comparisons worth investigating before trying to erase mission labels. Resolve the original accession and library protocols at sample level; OSD-48 and OSD-168 are candidates, not yet a frozen paired cohort. A restricted liver case here would be a technical-control experiment, not a return to a liver-only scientific scope.

## Three separate questions: layers, training objective, and LoRA

1. **Where is the information?** Probe the frozen input/early, middle and final hidden layers using the same gene pooling, masks and preprocessing. Compare preparation/batch, tissue and flight predictability. Use layer-wise plots as illustrations and grouped out-of-sample probes as evidence. Select layers on development data only. A better earlier layer may remove the need for fine-tuning.
2. **What should training encourage?** Preserve useful biology while discouraging prediction of verified technical labels. This is the adversarial objective, regardless of which parameters are updated.
3. **Which weights can move?** Compare LoRA and limited last-block unfreezing under the same objective. LoRA is a parameter-update strategy, not a batch-correction objective. These choices are compatible with layer inspection.

[LoRA](https://arxiv.org/abs/2106.09685) learns low-rank weight updates while freezing the original weights. It can reduce trainable parameter count; it does not guarantee less overfitting, successful batch removal or a particular sample requirement. Local BridgeRNA has explicit `q_proj`, `k_proj`, `v_proj`, `out_proj` layers, so a bounded attention-projection LoRA experiment is structurally feasible. Its inference `encode()` is decorated with `no_grad`; training must use a gradient-enabled path and verify that adapter parameters actually receive gradients.

## What to borrow from scGPT

The [scGPT paper](https://www.nature.com/articles/s41592-024-02201-0) includes multi-batch integration. Its [official integration example](https://github.com/bowang-lab/scGPT/blob/main/examples/finetune_integration.py) uses expression-prediction objectives, an adversarial batch objective and domain-specific batch normalization. Its [model code](https://github.com/bowang-lab/scGPT/blob/main/scgpt/model/model.py) implements a batch discriminator with reversed gradients and supports batch-conditioned decoding. This is a relevant pattern to adapt, not evidence that LoRA is the best method for our bulk datasets.

Do not copy the single-cell cell counts, random cell splits, highly-variable-gene binning or batch-specific normalization into BridgeRNA automatically. Keep BridgeRNA's validated normalization, vocabulary and species contract. Unknown batches at deployment require an explicit policy if batch-specific normalization or decoding is introduced. Freeze the source revision before implementation.

## Proposed adversarial mechanism

Let `z = pool(encoder_theta(x))`. Attach a biological prediction head and a technical-batch head:

```text
expression → BridgeRNA → sample embedding z → tissue / biology head
                                     └────→ gradient reversal → batch head
```

For batch-head parameters, minimize `L_batch` normally. For the encoder/trainable adapters, use

`gradient = gradient(L_preserve + alpha * L_tissue) − lambda * gradient(L_batch)`.

Gradient reversal leaves the forward value unchanged and reverses/scales the batch gradient on its way into the encoder. It does not simply stop or delete a gradient. This follows [Ganin et al., 2016](https://www.jmlr.org/beta/papers/v17/15-239.html).

Start with pooled sample embeddings; individual neurons are not assumed to correspond to isolated batch factors. A tissue head is only informative when multiple tissues are represented. In a liver-only pilot, keep tissue fixed and use a separate multi-tissue preservation check. Stratify or condition the adversary on supported biological context, rather than requiring identical distributions across inherently different tissues or strains. With no overlap, mark the contrast non-identifiable for technical correction.

`L_preserve` needs an explicit choice before training: a masked-expression objective can help retain useful information, but reconstructing uncorrected values can also preserve batch. A batch-conditioned decoder can place nuisance information outside the biological embedding. A weak reconstruction/distillation anchor is another pilot option, with that tension reported rather than assumed solved. Train on broadly matched ground data if useful; keep final flight tests outside adaptation. Small flight data need not carry the entire adaptation objective.

## How much data is needed?

There is no defensible universal sample threshold or a direct conversion from scGPT's cell counts to our animal counts. **Independent animals, technical-batch overlap and independent studies matter more than repeated libraries.** More of a perfectly confounded design does not identify a technical effect.

The current 18-animal RR1/RR3 flight/ground candidate subset is sufficient to audit labels and inspect exploratory embeddings, but cannot support a confident ranking of many fine-tuning methods or reliable unseen-mission claims. Training on one mission and testing the other yields a useful but very small challenge; two missions alone do not provide a clean three-way train/validation/test split across missions.

After sample links and batch crossing are verified, construct nested training fractions (25%, 50%, 100% when each subset retains viable strata) with a fixed independent test set. Plot batch leakage and biological preservation versus **unique training animals**. Use three fixed seeds, donor/animal-grouped uncertainty and identical subsets across methods. Determine sufficiency from whether performance stabilizes and uncertainty is useful; report actual counts. If tiny groups prevent these splits, stop at feasibility and expand matched preparation data instead of running a large sweep.

## Small experiment sequence

1. **Cohort contract:** obtain the screenshot source if available; recover original ISA assay metadata, library selection, spike-ins, preparation/sequencing runs, animal links and pipeline versions. Audit the preparation × mission × strain × tissue × flight-condition table. Verify same-RNA pairs and count-file availability/coverage.
2. **Frozen diagnostics:** measure raw/PCA and early/middle/final BridgeRNA embeddings. Plot the same samples colored separately by preparation, mission, tissue/strain and flight condition. Do not tune the projection to make batches mix. Use fit-on-training PCA and fixed rendering settings.
3. **Bounded adaptation comparison:** frozen model/best development layer; a small LoRA configuration without adversarial loss; the same LoRA configuration with gradient reversal. Only then compare last one/two trainable blocks with matched preservation/adversarial objectives if data and the first result justify it. A low rank such as 8 is a proposed starting configuration, not an established optimum. Freeze learning rates, rank, early stopping and selection rules on development data.
4. **Simple correction reference:** use an appropriate ComBat/ComBat-seq comparison only with valid inputs, biological covariates and an identifiable design. Separate an all-data descriptive integration plot from an inductive held-out evaluation; many correction workflows require test-batch information. Do not feed adjusted values into BridgeRNA while also changing its normalization contract without a separate input audit.
5. **Repeat the survey:** rerun model direction, sample-removal and source-sensitivity diagnostics on the same saved cohorts, then test independent contexts. Keep the raw-expression pathway results fixed: changing model weights does not change input gene-set scores. Any new model-decoded gene-expression analysis is a separate endpoint.

## What would count as success?

Use fresh, separately trained linear and nonlinear probes on frozen before/after representations. A weak training adversary can fail even while batch information remains available to another probe. For the known-batch diagnostic, hold out animals while retaining identifiable batch classes in train/test; compare against a balanced or context-conditional baseline. Unseen mission evaluation is a separate biological generalization test, not a closed-set classifier asked to predict an unseen batch class.

Advance only if technical-label predictability decreases **and** held-out biological performance/preservation does not materially degrade, with no representation collapse. Define margins before training once the eligible cohort and baseline variance are known. Keep tissue/strain preservation, within-study flight contrasts, embedding variance/rank, and masked-expression performance visible. A more mixed PCA plot, a failed adversary, or artificially positive cross-flight response cosine is insufficient. Do not force contradictory flight biology to agree.

**Immediate deliverable:** an audited preparation/animal manifest and frozen layer diagnostic. **First fine-tuning case:** a small, controlled adversarial adaptation comparison if the metadata support separating batch from biology. **Next biological problem:** revisit the muscle-chip and MG63 leads only after the corrected representation passes those checks.

## Fourier suggestion

The PI mentioned Fourier methods informally; the user clarified that their necessity was uncertain. They are not part of the first pilot. An FFT across an arbitrary gene order lacks a specified biological frequency axis. BridgeRNA already uses sinusoidal expression features in its input encoder; that is not itself batch correction. Revisit a Fourier-based method only if a concrete nuisance model and applicable signal axis are identified.
