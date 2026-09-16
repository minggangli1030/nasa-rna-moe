# Exploratory spaceflight prediction-head pilot — September 14, 2026

**Completed: frozen-embedding heads learn within-flight associations, but fail to transfer
between the two human muscle-chip flights. Expression/PCA baselines fail cross-flight too.
This pilot establishes no BridgeRNA advantage or transferable flight classifier.**

[Results figure](pilot_results.pdf) · [Per-fold metrics](metrics.csv) ·
[Predictions](predictions.csv) · [Protocol fixed before fitting](protocol.json)

## What ran

Local CPU training of regularized logistic heads on cached inputs/embeddings from frozen
BridgeRNA `r7hnr92k`. No new inference, VM job, encoder fine-tuning, LoRA, batch correction
or watcher was needed. Training was explicitly authorized for this bounded pilot after
the earlier planning-only meeting notes.

Cohort: 12 non-stimulated GSE234465 chips and 12 No E-stim Day21 GSE298393 chips.
Each flight has three flight and three ground chips in each YA and OS donor-source pool.
The 24 profiles are not 24 independent donors; pool reuse across flights also prevents
an independent-donor interpretation. Labels mean flight experiment versus its matched
ground control, not isolated microgravity/radiation exposure. This deliberately narrow
human case does not change the broader space-biology scope.

Primary evaluation: train all 12 chips from one flight, test all 12 from the other,
in both directions. Secondary evaluation: within each flight train six chips from one
pool and test six from the other (four folds). No random chip train/test split was used.
Existing catalog `split` fields describe pretraining exposure and were not used as
prediction-head partitions.

Expression uses 15,137 structurally observed genes shared by this predefined cohort.
That feature-availability restriction uses masks, not test expression values or labels.
Scalers and PCA are fitted to training rows only. PCA uses five components. BridgeRNA
uses final-layer mean (512 features) or concatenated mean/SD (1,024). All heads use fixed
L2 logistic regression C=1 and threshold 0.5; no hyperparameter winner or threshold was
selected using test outcomes. YA/OS-only metadata is a limited negative control; it does
not rule out preparation, hardware or other confounding.

## Results

| Model | First → repeat: balanced accuracy / AUROC | Repeat → first: balanced accuracy / AUROC | Within-flight held-out-pool balanced accuracy |
|---|---:|---:|---:|
| Expression + linear head | 0.500 / 0.000 | 0.500 / 0.000 | 0.667–1.000 |
| PCA (5) + linear head | 0.500 / 0.000 | 0.417 / 0.000 | 0.667–1.000 |
| BridgeRNA mean + linear head | 0.500 / 0.000 | 0.500 / 0.000 | 0.667–1.000 |
| BridgeRNA mean+SD + linear head | 0.500 / 0.000 | 0.500 / 0.000 | 0.833–1.000 |
| Pool-only metadata control | 0.500 / 0.500 | 0.500 / 0.500 | 0.500–0.500 |

AUROC 0.000 means every held-out flight sample ranks below every held-out ground sample:
a complete reversal of the trained label ordering, not absence of all structure. Do not
flip labels or negate scores using the held-out result and call that successful transfer.
At threshold 0.5, both BridgeRNA readouts and direct expression predict all test samples
as flight in both directions; reverse-direction PCA predicts 11/12 as flight. Thus both
a between-experiment score shift and a reversed within-test ordering are present.
A threshold adjustment or monotonic calibration alone cannot repair the reversed ordering.

Within-flight accuracy is substantially higher. These are small six-chip tests between
two pools within a single experiment, not independent mission replication, and do not
establish a causal flight mechanism or dependable deployment performance. No confidence
interval treating the four folds or individual chips as independent donors is reported.

## Robustness and numerical checks

- Fixed sensitivity values C=0.01 and C=100 do not rescue cross-flight classification.
  Across all three C values, neither BridgeRNA readout exceeds 0.500 balanced accuracy.
  Bridge mean AUROC remains 0.000–0.139; mean+SD remains 0.000–0.028. Expression/PCA
  cross-flight AUROC remains 0.000 throughout.
- All 120 planned leave-one-training-chip refits retain balanced accuracy at or below
  0.500. Both BridgeRNA readouts remain exactly 0.500, predicting all test chips as flight.
  These deletions test sensitivity to training chips, not independent-donor uncertainty.
- AUROC/AP use decision logits to avoid ties from sigmoid saturation on shifted inputs.
  Sigmoid-only first-pass metrics are archived with the numerical revision explained in
  `implementation_notes.json`; the model specification and evaluation protocol did not change.
- Input hashes, ordered IDs, shared gene order, finite features, appropriate study/pool
  separation, training-only scaler statistics and head convergence passed checks.
  All 30 saved primary/secondary heads reproduce their predictions. Independent pairwise
  AUROC and classwise accuracy calculations match the reported metrics.

## Interpretation and limits

This agrees with the earlier descriptive finding that broad response directions differ
across these flights. It does not determine whether preparation, hardware, duration,
handling, donor context or biology explains the failure. Original-flight expression
was derived from counts and gene lengths; repeat-flight expression follows the source
FPKM annotation. Earlier expression-only FPKM sensitivity retained opposing directions,
but an equivalent-source classifier sensitivity has not been run here.

The cohort was previously explored; this is a development challenge, not a pristine
confirmation set. Supplied catalog entries mark original chips unseen and omit repeat
chips, but that does not independently establish absence from checkpoint pretraining.
Two flights and shared donor pools do not support broad cross-study reliability or
calibrated probabilities. Scores close to one here can still correspond to incorrect
predictions; the saved sigmoid outputs are explicitly uncalibrated.

## Gene attribution and next decision

No BridgeRNA input-gene attribution was run because the prespecified transfer gate failed.
The saved expression coefficients are exploratory training associations, not BridgeRNA
attributions or evidence for genes responsible for a transferable flight classifier.
No radiation/microgravity probability or causal stress explanation is supported.

A useful next bounded question is why a within-experiment classifier reverses across
these two flights. Before deeper tuning, specify an equivalent-source/input sensitivity
and a more compatible independent flight/control case. Brain's batch work can later be
compared with the original encoder using this same fixed evaluation, retaining the
expression/PCA baselines and failed contrasts. Batch correction must not be assumed to
solve a biological or hardware difference. Further work requires a separate execution
request; this pilot is complete.

## Reproduction and artifacts

Implementation: [space_head_pilot.py](../../space_head_pilot.py). Source inputs and code
hashes plus runtime versions are in [provenance.json](provenance.json). The script refuses
to overwrite a completed metrics file; a deliberate rerun should use an isolated output
location or preserve the completed artifact first.

- `cohort.csv`, `expression_gene_panel.csv`, `splits.csv`: exact membership/features/folds.
- `heads/`: 30 fitted C=1 heads including training-fitted transforms.
- `metrics.csv`, `predictions.csv`: 50 evaluations and 480 prediction rows, including C sensitivities.
- `training_chip_deletion.csv`: 120 sensitivity refits, not additional biological samples.
- `verification.json`: independent reproduction and metric checks.
- `pilot_results.png` / `.pdf`: three-panel comparison, visually reviewed.

No computation remains running for this pilot. The previous watcher remains paused.
