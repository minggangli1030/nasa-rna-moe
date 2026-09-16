# Mentor discussion — Monday, September 14

**Aim:** decide which space-biology patterns deserve another small experiment. We used frozen BridgeRNA to survey 559 samples across 28 study accessions and 11 tissue groups, including human flight cell models and human bed-rest analogs. No training or full predictive benchmark was needed.

[Discussion figure, PDF](monday_findings.pdf) · [Full evidence and limitations](REPORT.md) · [All 54 comparisons](survey_pattern_map.pdf)

## Three points to bring

1. **Human muscle chips show a consistent flight-experiment response in both donor pools.** Every balanced chip split agrees in BridgeRNA and expression; the two pools' model response directions are similar (cosine 0.91). But the chips reuse pooled donor cells, age/activity vary together, and hardware/ground-protocol differences could explain part of the signal. Discuss testing the later flight, GSE298393, using matched non-stimulated arms. This would test repeatability across flights, not across new donors.

2. **Mouse muscle has recurrent gene candidates across four missions.** Cdkn1a and Mmp14 increase, Dbp decreases; the supplied model's MT1X position maps to mouse Mt2 and also increases. Dbp and Mmp14 keep their signs in every single-sample deletion; Cdkn1a and mapped Mt2 have exceptions. Discuss whether stress/cell-cycle and circadian-output patterns are worth examining after auditing collection times, handling, and cell composition. These expression candidates are not explanations extracted from the model. Human chips do not reproduce all their directions.

3. **The response depends strongly on tissue and experimental context.** In one multi-tissue mouse flight, thymus and brown fat show consistent shifts in both genotypes, whereas several other tissues are less consistent in the model. The same animals contribute multiple tissues. Discuss checking another mission before interpreting a tissue-specific mechanism.

## What we should not overstate

The human cardiac response varies across its three cell lines. One small bed-rest model result is unstable. A model-aligned pair of quadriceps studies fails to extend to a third study. Overall, raw expression is often more stable than the model summaries. We have not identified a universal spaceflight signature, established model superiority, or isolated microgravity causation.

## Proposed decision

Start with the **human muscle-chip repeat-flight comparison**, because it gives the clearest human lead and a concrete way to challenge it. In parallel as a small data audit, check collection-time and mission metadata for the mouse muscle candidates. Keep the tissue lead as an alternative. Choose one specific follow-up after discussing these results; deeper evaluation or fine-tuning should follow only if the pattern survives.

**Suggested opening:** “I broadened the survey beyond mouse liver. We found a few reproducible within-experiment patterns, but their consistency depends on tissue and context. I want to discuss which one has the best biological question and the clearest next test.”
