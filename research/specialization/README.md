# Biological specialization

A focused path from a shared distributed trainer to species/organ specialists and controlled reconstruction evaluation. Archived cohort builders, abandoned branches, and one-off analysis variants are intentionally omitted from this portfolio.

| Read in this order | Purpose |
| --- | --- |
| [core/train_single.py](core/train_single.py) | Expression model, Parquet input pipeline, DDP, AMP, and checkpointing |
| [core/train_moe.py](core/train_moe.py) | Species specialist composition and routing |
| [core/train_manifest.py](core/train_manifest.py) | Deterministic sampling, masks, budgets, and data contracts |
| [core/train_fixed_partition_banks.py](core/train_fixed_partition_banks.py) | Frozen-trunk organ adapter banks |
| [evaluation/headroom_metrics.py](evaluation/headroom_metrics.py) | Routing/blending and reconstruction metrics |
| [evaluation/evaluate_gtex_k8_adapter_scale.py](evaluation/evaluate_gtex_k8_adapter_scale.py) | Frozen budget-by-seed comparison |
| [evaluation/evaluate_organ_moe.py](evaluation/evaluate_organ_moe.py) | Organ-specialization evaluation |
| [preprocessing/preprocessing.py](preprocessing/preprocessing.py) | Public-expression preprocessing |
| [tests/](tests/) | Synthetic training, routing, masking, and cache contracts |

The remaining core modules are direct dependencies of these entry points. Numerical Performer helpers stay beside their trainer to preserve the existing import contract. Run training from this directory; its relative data, checkpoints, and generated paths are local-only. No original runtime data or models are bundled.
