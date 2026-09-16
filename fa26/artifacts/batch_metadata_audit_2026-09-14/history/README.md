# Fall 2026 (FA26) — BridgeRNA space-biology direction

## Goal

Use the latest BridgeRNA foundation model and compatible public datasets to identify
interpretable space-biology patterns before committing to fine-tuning or a new MoE
experiment.

## Immediate work

Prepare a lightweight, general discovery survey for the September 14 mentor discussion:
identify spaceflight-associated patterns, check basic robustness, and choose a concrete
biological follow-up. Include human flight models, human analogs, and multiple mouse
tissues where compatible data are available. No mouse-only or liver-only commitment.

## Decision rule

Do not fine-tune or add MoE capacity until the embedding exploration identifies a
specific task, dataset, and success metric. Raw expression and PCA remain required
baselines for any predictive claim.

## Local inputs

`bridge-rna-latest/` contains the downloaded BridgeRNA checkpoint, manifests, and
public reference inputs. Large files in this directory are intentionally ignored by
Git.

## Current result — reviewed September 13, 2026

The **general survey, repeat-flight check, pathway survey and both onboard-1g human
comparisons are complete**. Use the [Monday discussion brief](artifacts/general_survey_2026-09-12/MONDAY-DISCUSSION.md),
[new pathway figure](artifacts/pathway_onboard_1g_2026-09-13/pathway_discovery.pdf), and
[current full report](artifacts/pathway_onboard_1g_2026-09-13/REPORT.md).

Two discussion leads survive basic robustness checks: an average oxidative-phosphorylation
gene-set increase in both human muscle-chip flights/pools, and higher inflammatory-associated
plus lower DNA-repair-associated expression in MG63 microgravity versus onboard-1g cultures.
The muscle set's individual gene responses agree weakly across flights; the MG63 result is
from an osteosarcoma-derived cell line. Neither establishes a common mechanism or biomarker.
Endothelial results are weaker and depend on the control comparison.

Frozen checkpoint `r7hnr92k`, the latest available in the inspected author embedding source,
completed all inference on moe-reboot's A100. No training ran. Expression remains the
baseline, and no general model advantage is established. See [next steps](NEXT-STEPS.md)
for two focused biological questions to discuss before committing to deeper evaluation.

## Completed survey history

The [general survey](artifacts/general_survey_2026-09-12/REPORT.md) covered 559 samples,
28 accessions, 54 contrasts and 11 broad tissue groups. The [repeat-flight follow-up](artifacts/muscle_repeat_flight_2026-09-12/REPORT.md)
added 12 human muscle chips: broad expression/model directions oppose across flights,
while MYH1 decrease survives. The current follow-up adds 14 human biological samples
and scores ten predefined gene sets across 60 primary contrasts plus one source sensitivity.
Five alternate-processing model inputs are not extra biological samples.

Hardware/protocol differences, donor pooling, related animals, collection timing and
source processing remain limits. Mouse muscle has recurring gene candidates across four
missions, but none of the ten program scores keeps one mission-average direction across
all four. Failed comparisons are retained in the reports. No pending run remains; the
previous completed-run watcher stays paused.

## Earlier work

The [34-sample mouse-liver pilot](artifacts/osdr_liver_pilot_2026-09-11/REPORT.md)
was a pipeline-development convenience cohort, not a search for the most significant
tissue. It is superseded in scope by the general survey. The
[contract audit](CONTRACT-AUDIT.md) records source/config/vocabulary checks and correction
of the draft model's normalization order. GTEx's unmatched-symbol issue remains a
separate limitation; the general survey uses different human count sources with
explicit mapping, missingness, and sensitivity checks.
