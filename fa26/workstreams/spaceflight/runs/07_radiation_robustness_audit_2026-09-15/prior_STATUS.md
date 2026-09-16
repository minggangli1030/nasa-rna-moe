# Spaceflight workstream — current status

**Controlled-exposure validation is complete.** The latest run added 123 public profiles,
computed frozen BRIDGE embeddings on moe-reboot's A100 (45.5 seconds), and fitted/tested
small local radiation-associated heads. No encoder update occurred; the VM is idle and
the watcher remains paused.

## Findings

- IR/control classification in normal IMR90 cultures reached AUROC and balanced accuracy
  1.0 on all four held-out expression files. Expression/PCA matched this performance.
- The BRIDGE probe called 4/5 bleomycin and 3/3 rotenone samples positive at the fixed
  threshold. Strong ranking does not imply a radiation-specific binary decision.
- In the independent lung-chip study, AUROC was 0.69–1.0 and balanced accuracy 0.5–1.0
  depending on cell type/time; only one stratum reached perfect classification.
- Adding other stresses as negatives reduced bleomycin false positives to 1/5 but worsened
  external transfer. This adaptive version is not promoted as generally improved.
- The six-program-average classifier was unstable. Generic pathway averages are not yet
  an adequate exposure bottleneck; radiation/microgravity percentages remain unsupported.
- A near-constant expression feature was corrected with a training-only variance filter;
  the original outputs and numerical regression check are retained.

## Outputs

[Latest report](runs/06_controlled_exposure_validation_2026-09-14/REPORT.md) ·
[Specificity/transfer figure](runs/06_controlled_exposure_validation_2026-09-14/specificity_and_transfer.pdf) ·
[Dataset audit](runs/06_controlled_exposure_validation_2026-09-14/dataset_audit.csv)

The [previous response-level pilot](runs/05_response_explanations_2026-09-14/REVIEW.md)
remains the evidence for the muscle-chip flight head: myogenesis-associated inputs are
the clearest of six tested contributors; most positive attribution is unassigned.
The prior cross-flight failure remains unresolved. None of these new tests independently
validates a radiation contribution to flight samples.

## Next decision

Retain the original radiation-associated probe as a development comparator. Prioritize
controlled-gravity input quantification and matched tissue/time perturbation examples
before connecting exposure concepts to the muscle-chip flight decision. GSE222998 has
human ISS/analog RNA-seq, but published transcript/CDS counts require a dedicated audit;
it was not silently treated as gene-level bulk expression. Some analog cells have n=1.

No new run is queued. See [plan](PLAN.md) and the latest [execution record](runs/06_controlled_exposure_validation_2026-09-14/EXECUTION.md).
