# Mentor discussion — Monday, September 14

**Aim:** decide which space-biology patterns deserve another small experiment. We used frozen BridgeRNA to survey 559 samples across 28 study accessions and 11 tissue groups, including human flight cell models and human bed-rest analogs. No training or full predictive benchmark was needed.

[Discussion figure, PDF](monday_findings.pdf) · [Full evidence and limitations](REPORT.md) · [All 54 comparisons](survey_pattern_map.pdf)

## Three points to bring

1. **Human muscle-chip responses are consistent within experiments, but their broad directions fail to repeat across flights.** We tested 12 additional non-stimulated chips from GSE298393. Cross-flight BridgeRNA-mean cosines are −0.686 (young/active) and −0.963 (old/sedentary); all chip-deletion checks remain negative. Expression also disagrees, including a check using source FPKM for both flights. **MYH1 decreases in both pools in both flights**, surviving every single-chip deletion: a narrower gene-level lead. Shared donors and differences in hardware, duration and processing limit interpretation. [Repeat-flight report](../muscle_repeat_flight_2026-09-12/REPORT.md) · [New figure](../muscle_repeat_flight_2026-09-12/cross_flight_pattern_reviewed.pdf).

2. **Mouse muscle has recurrent gene candidates across four missions.** Cdkn1a and Mmp14 increase, Dbp decreases; the supplied model's MT1X position maps to mouse Mt2 and also increases. Dbp and Mmp14 keep their signs in every single-sample deletion; Cdkn1a and mapped Mt2 have exceptions. Discuss whether stress/cell-cycle and circadian-output patterns are worth examining after auditing collection times, handling, and cell composition. These expression candidates are not explanations extracted from the model. Human chips do not reproduce all their directions.

3. **The response depends strongly on tissue and experimental context.** In one multi-tissue mouse flight, thymus and brown fat show consistent shifts in both genotypes, whereas several other tissues are less consistent in the model. The same animals contribute multiple tissues. Discuss checking another mission before interpreting a tissue-specific mechanism.

## What we should not overstate

The human cardiac response varies across its three cell lines. One small bed-rest model result is unstable. A model-aligned pair of quadriceps studies fails to extend to a third study. Overall, raw expression is often more stable than the model summaries. We have not identified a universal spaceflight signature, established model superiority, or isolated microgravity causation.

## Proposed decision

Discuss a **small shared-gene follow-up around MYH1**, while auditing why the overall human flight responses differ. Alternatively, the mouse-muscle collection-time audit or a human onboard-1g comparison may provide a cleaner question. The repeat-flight check is complete; do not present it as pending. Deeper evaluation or fine-tuning should wait until a specific biological question and credible comparison are chosen.

**Suggested opening:** “I broadened the survey beyond mouse liver. We found consistent within-experiment patterns, but a human repeat-flight check did not reproduce the overall response. A narrower gene-level lead survived. I want to discuss which one has the best biological question and the clearest next test.”
