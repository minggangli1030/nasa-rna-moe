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

## Current result — general survey completed 2026-09-12

Completed **559 samples, 28 study accessions, 54 contrasts, and 11 broad tissue groups**
with frozen checkpoint `r7hnr92k`, the latest checkpoint available in the inspected
author embedding source. The A100 on moe-reboot completed inference; no training ran.

Start with the [Monday discussion brief](artifacts/general_survey_2026-09-12/MONDAY-DISCUSSION.md),
[discussion figure](artifacts/general_survey_2026-09-12/monday_findings.pdf), and
[full survey report](artifacts/general_survey_2026-09-12/REPORT.md).

The leads are a consistent human muscle-chip flight-experiment shift, recurrent
mouse-muscle expression candidates across four missions, and tissue-dependent
patterns in a multi-tissue mouse experiment. Hardware/protocol differences, donor
pooling, related animals, and collection timing limit interpretation. Human cardiac
responses and several cross-study model patterns are unstable. Raw expression is
often more stable than the model summaries; no general model advantage is established.

## Repeat-flight follow-up — reviewed 2026-09-13

The additional 12-sample GSE298393 check is complete. Its overall human muscle-chip
response opposes the first flight's direction in expression and both model summaries;
model-mean disagreement survives every chip-deletion pair. Expression-only source-FPKM
sensitivity retains disagreement. A narrower **MYH1 decrease** persists in both pools
in both flights and survives single-chip removal. This is a candidate, not a validated
biomarker, and protocol/source-unit differences remain relevant.

Use the [repeat-flight report](artifacts/muscle_repeat_flight_2026-09-12/REPORT.md),
[reviewed figure](artifacts/muscle_repeat_flight_2026-09-12/cross_flight_pattern_reviewed.pdf),
and updated Monday brief. Discuss a focused shared-gene question or a cleaner control
design before adding model complexity. See [next steps](NEXT-STEPS.md).

## Earlier work

The [34-sample mouse-liver pilot](artifacts/osdr_liver_pilot_2026-09-11/REPORT.md)
was a pipeline-development convenience cohort, not a search for the most significant
tissue. It is superseded in scope by the general survey. The
[contract audit](CONTRACT-AUDIT.md) records source/config/vocabulary checks and correction
of the draft model's normalization order. GTEx's unmatched-symbol issue remains a
separate limitation; the general survey uses different human count sources with
explicit mapping, missingness, and sensitivity checks.
