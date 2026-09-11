# Fall 2026 (FA26) — BridgeRNA space-biology direction

## Goal

Use the latest BridgeRNA foundation model and compatible public datasets to identify
interpretable space-biology patterns before committing to fine-tuning or a new MoE
experiment.

## Immediate work

1. Verify the canonical 15,165-gene order, ortholog mapping, and `log1p(TPM)`
   preprocessing contract against the BridgeRNA checkpoint.
2. Generate embeddings for selected OSDR flight and matched ground-control samples.
3. Look for useful patterns: within-tissue flight/control shifts, cross-species
   tissue alignment, and retrieved human samples with plausible stress or disease
   contexts.
4. Turn the strongest reproducible observation into one concrete downstream task.

## Decision rule

Do not fine-tune or add MoE capacity until the embedding exploration identifies a
specific task, dataset, and success metric. Raw expression and PCA remain required
baselines for any predictive claim.

## Local inputs

`bridge-rna-latest/` contains the downloaded BridgeRNA checkpoint, manifests, and
public reference inputs. Large files in this directory are intentionally ignored by
Git.
