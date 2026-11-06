# Distributed training and model systems

## Code to inspect

| Concern | Implementation |
| --- | --- |
| DDP bootstrap and full training loop | [train_single.py](../research/specialization/core/train_single.py): `_init_ddp`, `main` |
| Input throughput and rank sharding | Same file: streaming Parquet dataset, row-group batch sampler, preload path, `DistributedSampler` |
| GPU numerics | Same file: `torch.amp.autocast` and `GradScaler` |
| Expert routing | [train_moe.py](../research/specialization/core/train_moe.py) |
| Organ adapter training | [train_fixed_partition_banks.py](../research/specialization/core/train_fixed_partition_banks.py) |
| Budget-controlled evaluation | [evaluate_gtex_k8_adapter_scale.py](../research/specialization/evaluation/evaluate_gtex_k8_adapter_scale.py) |

## Execution model

`torchrun` supplies rank and rendezvous variables. The trainer selects a local CUDA device, initializes a process group (NCCL by default), broadcasts run configuration and split definitions, partitions inputs, wraps the shared model in DDP, and reduces validation statistics across ranks. Mixed precision reduces activation and arithmetic costs; no throughput gain is quantified in this release.

Species/organ expert partitions describe biological specialization. They should not be confused with expert-parallel model sharding across machines. The retained MoE training path uses a CUDA device; the presence of a DDP shared-model trainer does not establish that every MoE experiment ran across multiple nodes.

## Reproduction boundary

The author reports hands-on work in Savio and Jetstream environments. Exact node counts, accelerator utilization, samples/second, gradient communication timings, and latency distributions are not established by the retained evidence. Do not infer a measured systems improvement from a biological MSE result. Original cluster launchers are excluded because they contain environment-specific paths and operational details.

The source uses research-relative data paths. Execute Summer tools from `research/specialization/` after provisioning authorized data and references. Multi-GPU training requires CUDA GPUs and correctly configured distributed rendezvous; it is not covered by the CPU tests.

## Portable launch template

After provisioning the expected data and runtime, run from the repository root:

```bash
DATASET_VARIANT=human_20k_v3 NPROC_PER_NODE=2 bash scripts/train_distributed.sh
```

For multiple nodes, use the same `NNODES`, `MASTER_ADDR`, and `MASTER_PORT` on each node, with a distinct `NODE_RANK`. The launcher is a new portable wrapper around the existing trainer, not a recovered cluster execution record. It has been syntax-checked; no GPU training was started during portfolio preparation.
