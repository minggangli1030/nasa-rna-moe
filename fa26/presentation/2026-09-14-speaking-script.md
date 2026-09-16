# Space-biology discovery — short speaking script

Three slides; approximately 3 minutes at a conversational pace.

## Slide 1 — Muscle-chip finding

I broadened the survey beyond mouse liver, using frozen BridgeRNA and expression comparisons. We screened ten biological gene sets across sixty primary comparisons. One useful lead came from the human muscle chips: the average expression score for 173 oxidative-phosphorylation genes rises in both flights and both donor pools. These genes are associated with mitochondrial energy production. The direction survives removing individual chips or genes, and changing the expression-processing method. But the individual genes agree only weakly between flights, and the overall profiles still differ. So I would present this as a shared average expression pattern, not proof of increased respiration or one common mechanism.

## Slide 2 — Controlled MG63 finding

The second lead comes from MG63, a bone-like cancer cell line. This experiment compares microgravity with a one-g centrifuge control, both aboard the ISS. In three cultures per group, inflammation-associated gene sets rise and the DNA-repair gene set falls. These directions survive sample removal and comparison with independently processed counts. BridgeRNA also preserves the overall response consistently, as does the expression baseline. The numbers on the right measure agreement between data splits; they are not prediction accuracy. This gives us a cleaner experimental contrast, but it does not yet establish inflammation or impaired repair in healthy bone.

## Slide 3 — Choose the next test

For the next step, I would choose one of these questions with you. For muscle, we could first inspect the genes driving the shared average and the differences in collection and culture conditions, then ask whether the pattern repeats in a matched independent experiment. For bone, we could look for the inflammation-and-repair expression pattern in another study with onboard one-g controls, ideally using primary cells. The endothelial comparison reminds us why controls matter: its mitochondrial gene-set result is stable against Earth controls but fragile against onboard one-g controls. Which biological question and independent comparison would be most useful to pursue?

## If asked about the numbers

- A gene-set score averages standardized gene expression within each comparison; it is not a fold change or a functional measurement.
- Split-direction agreement is cosine similarity between response vectors from balanced subsets; +1 means alignment. The overlapping splits are robustness checks, not independent experiments.
- All ten gene sets, including failed checks, are in the [full report](../artifacts/pathway_onboard_1g_2026-09-13/REPORT.md).
- Model checkpoint: frozen BridgeRNA r7hnr92k, latest available in the inspected author source. These pathway labels come from expression analysis, not model attribution.
