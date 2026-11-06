# NASA AI4LS · Distributed RNA Modeling & Mixture of Experts

**Minggang Li · NASA Ames AI4LS research · PyTorch, distributed training, MoE routing**

Cross-species and cross-organ RNA modeling, with distributed data loading, GPU training, specialist routing, and controlled evaluation of transfer to spaceflight-associated responses.

This source-focused portfolio companion presents Summer and Fall 2026 work without the original meeting records, infrastructure details, sample-level exports, checkpoints, or notebook outputs. It is an adaptation of a larger research repository, not a complete experiment archive.

## Systems implementation

- **Distributed PyTorch:** NCCL process-group setup, one GPU per local rank, DDP model wrapping, rank-aware input pipelines, and reduced validation statistics.
- **Accelerator execution:** mixed-precision training with autocast and gradient scaling, checkpoint recovery, and streaming-versus-preloaded Parquet inputs.
- **Specialist routing:** species and organ partitions, learned expert selection, and frozen-trunk adapter banks with matched-control evaluation.
- **Research compute experience:** Savio and Jetstream environments, as reported by the author. Private hostnames, addresses, accounts, and launch records are excluded.

Start with [the systems walkthrough](docs/SYSTEMS.md). The code demonstrates data parallel training and biological expert partitioning; this release includes no benchmark establishing a multi-node speedup, communication-overhead reduction, or production latency.

## Research story

**Summer: organ-specialized models.** Eight human-organ specialists reduced masked-gene reconstruction error relative to a shared model on an externally evaluated ARCHS4 cohort (821 samples, 63 connected studies, eight organs).

| Condition | Relative error reduction vs. shared model |
| --- | ---: |
| Correct organ supplied | 3.797% |
| Hard routing | 3.633% |
| Soft routing | 3.676% |

These figures are transcribed from the original closeout report, not recomputed here. The result is **externally evaluated, pending untouched confirmation**: six QC failures were removed after expression access and before efficacy scoring. Learned outputs did not outperform raw expression or fold-fit PCA on the tested OSDR spaceflight-versus-ground classification task.

**Controlled adapter study:** in a separate donor-disjoint GTEx development analysis, eight-organ adapter banks outperformed a pooled adapter in all **15 budget-by-seed trials**, with **4.565–12.455% lower MSE**. The controls match samples, updates, active adapter width, and compute—not total stored parameter count. This is a different cohort and comparison from the 821-sample ARCHS4 evaluation.

**Fall: transfer and specificity.** Frozen-embedding heads learned within-flight associations but failed unseen-flight transfer. Attribution and controlled-exposure analyses investigated what supported those scores. Muscle negative controls did not support describing the current flight head as radiation-driven. Attribution is descriptive, not causal.

## Explore the implementation

```text
research/specialization/  distributed trainer, specialist models, controlled evaluation
research/spaceflight/    inference contracts, flight heads, attribution, diagnostics
scripts/                 portable GPU-training launcher
docs/                    systems, results, provenance, validation
```

| Start here | What to inspect |
| --- | --- |
| [Specialization code guide](research/specialization/README.md) | DDP/AMP, input pipeline, MoE, adapters, metrics |
| [Spaceflight code guide](research/spaceflight/README.md) | Input contracts, frozen inference, heads, attribution |
| [Systems walkthrough](docs/SYSTEMS.md) | Code-supported distributed/GPU behaviors |
| [Full code map](docs/CODE-MAP.md) | Organization and curation boundaries |

This is a curated implementation portfolio rather than the full research archive. Superseded variants and one-off operational scripts are omitted; selected modules keep the direct dependencies needed to read and test them coherently.

## Local checks

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-test.txt
python -m pytest -q research/spaceflight/tests research/specialization/tests
```

The offline test dependencies are separate from the full research dependencies in `requirements.txt`; neither list is version locked. Full training and archived evaluations require external data, model files, and frozen manifests omitted from this copy. Full archived experiments require the original research archive. These commands are synthetic code checks, not reproduction of the reported biological results.

## Provenance and limitations

The original repository describes continuity from the `sp26_nasa` team repository and Walter Alvarado's `bridge-rna` work. This copy preserves that lineage; it does not claim sole authorship of every inherited model or utility. See [provenance](docs/PROVENANCE.md) and [results](docs/RESULTS.md). No employer endorsement or clinical utility is claimed. Publication rights and inherited licenses must be established before redistribution; no new project license is assigned here.
