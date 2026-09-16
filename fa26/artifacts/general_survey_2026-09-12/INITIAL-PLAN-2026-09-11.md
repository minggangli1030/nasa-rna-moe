# Fall next-step plan — 2026-09-11

**Status update:** The [initial pilot is complete](artifacts/osdr_liver_pilot_2026-09-11/REPORT.md).
Source matching, the primary VM restart, and 34-sample inference were executed after
this plan was agreed. Follow the report for findings and the next experiment.

The planned milestone was a reproducible, frozen-BridgeRNA OSDR pilot that tests whether
within-tissue flight/control differences recur across independent studies. Use
those observations to define a downstream task before fine-tuning or adding MoE.
This document is a plan; no VM reboot, inference job, or training run was launched.

## Current position

The structural input audit passes for the bundled 15,165 genes, one-to-one
human/mouse mappings, and species-specific exon lengths. Ten focused tests pass.
Checkpoint-matched forward semantics, training gene-order provenance, and exact
normalization remain unverified. GTEx has 509 missing exact canonical symbols;
that is a blocker for GTEx inference, not evidence that OSDR has the same gap.
OSDR coverage must be audited independently.

Both VMs were reachable on September 11 at the updated addresses:

- `moe-reboot`: `149.165.175.241`
- `moe-reboot2`: `149.165.147.148`

Neither showed a training/inference process. Both have an installed-versus-loaded
NVIDIA driver mismatch and report a required restart. GPU availability must be
rechecked after recovery. The saved SSH aliases still contain older addresses.

The local OSDR catalog contains 2,896 unique study/sample keys, all mouse. Labels
include Space Flight, Ground Control, capitalization variants, and several other
control types. Most library-type entries are unknown. Catalog row counts do not
yet establish an eligible, compatible cohort.

## 1. Recover source provenance and prepare the compute environment

Search the existing VM project checkouts, including `sp26_nasa` on moe-reboot,
for the checkpoint-matched upstream repository, revision, training manifest, and
preprocessing source. Inspect repository remotes and config references before
requesting another copy from the model author. Availability on these VMs is not
yet confirmed. Also verify whether `r7hnr92k` is the intended Fall release; the
folder name `bridge-rna-latest` alone is not release evidence.

Verify the exact gene order, expression embedding, attention, residual/normalization
order, mask handling, and species handling against the source. Verify the count
universe and species-specific lengths used for the TPM denominator. Keep fixed
probe inputs and compare source versus candidate outputs, first in float32;
record tolerances before inspecting differences. Save source revision and hashes.
If source cannot be located, record the specific missing provenance and obtain it
before interpreting model outputs.

Recover the VM driver state through a planned restart, then verify `nvidia-smi`
and a small PyTorch CUDA operation. Record hardware and environment versions.
Update the SSH aliases to the user-confirmed addresses during execution. Keep
CPU metadata/preprocessing work moving independently of GPU recovery.

**Deliverable:** source/config/checkpoint contract and usable GPU environment.
**Gate:** authenticated input order and preprocessing, equivalent forward outputs,
and a successful CUDA check. Strict state-dictionary loading alone is insufficient.

## 2. Freeze a small OSDR development cohort

Use the local catalog and summer cohort code as starting material. Do not reuse
summer preprocessed tensors without verifying their gene and normalization contract.
The prior 292-sample/18-study cohort is development evidence, not a new untouched
confirmation set; its historical scores are not directly comparable to a new cohort.

Start with one tissue represented in multiple independent flight/ground studies.
Liver is a provisional first candidate based on catalog representation, not an
expression result. Confirm exact tissue/subregion, organism, strain, sex, age,
mission duration, preservation, assay, and count-file compatibility. Prefer a
pilot with at least three independent studies and biological replication in both
conditions; use fewer only as a clearly labeled technical/descriptive pilot.
Choose a second tissue only after the first pipeline is reproducible.

Map exact structured flight/control labels explicitly. Do not silently pool basal,
vivarium, rerun, or cohort controls with matched ground controls. Define how
technical replicates, repeated animals, and related missions are grouped; samples
from the same animal or related experimental unit must not become independent
validation observations. Missing matching metadata must be reported.

Freeze metadata eligibility and proposed count-QC rules before reading embedding
results. Audit source gene identifiers, ortholog mapping, alias ambiguity, missing
versus measured-zero genes, and count units against the verified training contract.
Apply sample QC consistently and record every exclusion. Retain only eligible
study/tissue contrasts containing flight and matched ground samples. Do not
silently change canonical genes, fill structural absence with biological zeros,
or import the summer 14,000-nonzero threshold without checking its applicability.

**Deliverables:** candidate and retained manifests, mapping/coverage reports,
exclusion ledger, and checksum-bound normalized input matrices.
**Gate:** interpretable matched contrasts and checkpoint-compatible inputs. If
coverage or replication is inadequate, document it and revise the data plan before
looking at embedding effects.

## 3. Run a bounded inference pilot

After gates 1–2, run one flight/ground pair to measure runtime and peak memory,
then a small pilot spanning the selected studies. Use the frozen checkpoint and
unmasked inputs. Fix the extraction layer and pooling rule before inspecting
condition separation; final-layer mean pooling is the current candidate, subject
to source verification. Keep masked reconstruction as a separate technical check.

Use moe-reboot for the initial inference pilot. Use moe-reboot2 for independent
preprocessing/baseline work or a reproducibility check once useful; two VMs do
not need to run duplicate full jobs. Assign work only after checking their resources.
Save sample IDs, study/animal metadata, model/input/source hashes, seed, pooling,
runtime, and peak GPU memory. Confirm finite, noncollapsed embeddings and repeat
selected samples to check deterministic inference within a recorded tolerance.
Scale only after this check and measured resource estimates.

**Deliverable:** reproducible embeddings plus QC and run report, without training.

## 4. Test the Fall hypotheses in priority order

1. **Within-tissue flight/control shifts:** inspect study-specific contrasts and
   whether their directions/effects recur across studies. Report uncertainty with
   the independent biological/study unit respected; use restricted label
   permutations only where the design makes labels exchangeable. With few studies,
   report limited precision and emphasize study-wise results. Global clustering
   or a flight-versus-ground plot alone does not establish reproducible biology.
2. **Cross-species tissue alignment:** add compatible human references after their
   mapping passes. Resolve the 509 GTEx symbol mismatches with a versioned alias or
   stable-ID source; alternatively use a compatible human reference with documented
   provenance. Separate tissue identity from study/species confounding. Compare
   the same samples and common gene space with raw expression and PCA.
3. **Human reference retrieval:** use tissue-matched, metadata-annotated human
   references and compare neighborhoods across representations. Inspect supported
   stress/disease annotations as hypotheses. Similarity alone is not evidence of
   shared mechanism, disease, or causal spaceflight effects. Audit reference overlap
   with pretraining where manifests permit; record unknown overlap explicitly.

For every predictive comparison, rerun raw expression and PCA on the same retained
samples and splits. Fit scaling, PCA, hyperparameters, and any supervised choices
only within training folds; hold out studies and connected experimental units.
The summer AUROC values (raw 0.726, PCA 0.733) are historical motivation, not target
scores to compare against different samples. Label development exploration as such.

**Deliverable:** a compact comparison report with per-study effects, baseline
comparisons, confounding checks, and uncertainty; descriptive plots support it.

## 5. Decide the downstream task

Promote the strongest replicated observation into a written task contract specifying
inputs, outcome, cohort, independent validation unit, primary metric, baselines,
and a minimum useful improvement before training. Reserve new studies for future
confirmation; do not relabel the explored summer cohort as untouched evidence.

If a flight/ground predictor is justified, study-held-out AUROC with a paired
comparison against the stronger raw/PCA baseline is a candidate primary measure.
If alignment or retrieval is the stronger result, define independent reference
labels and a suitable retrieval/alignment metric instead. Set the acceptance rule
for that task before fine-tuning. No stable observation or no representation
advantage means revisit data/task suitability; it does not automatically justify
MoE capacity.

## First execution session

1. Locate checkpoint-matched source on the reachable VMs and inventory reusable
   raw OSDR files/manifests without modifying summer results.
2. Prepare a metadata-only liver candidate table with explicit control matching
   and independent study/animal counts.
3. Recover and verify GPU access, then complete the model/preprocessing contract.
4. Freeze a compatible pilot manifest and run the smallest verified inference job.

GTEx alias repair supports the human-comparison branch and can proceed separately;
it should not delay an independently compatible mouse OSDR pilot.
