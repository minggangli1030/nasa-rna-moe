# Mentor discussion — Monday, September 14

**Main message:** we found narrower spaceflight-associated patterns worth discussing, even though a universal response did not emerge. The new pathway survey and both onboard-1g studies are complete. Frozen BridgeRNA was used throughout; no training ran.

[New pathway figure](../pathway_onboard_1g_2026-09-13/pathway_discovery.pdf) · [Controlled-model figure](../pathway_onboard_1g_2026-09-13/controlled_model_stability.pdf) · [Full follow-up evidence](../pathway_onboard_1g_2026-09-13/REPORT.md)

## 1. Human muscle chips share an average oxidative-phosphorylation expression increase

Across two flights and both young/active and old/sedentary donor pools, the 173-gene set's average score increases. The direction survives every single-chip deletion, rank/background scoring, alternative first-flight FPKM processing, and every single-gene deletion.

**Limit:** individual gene responses agree weakly between flights (within-set response cosines +0.095 and −0.121), while the whole-transcriptome and whole-model directions oppose. This is a shared average expression pattern, not evidence that respiration increased or the same mechanism repeated. Some rank effects are small. Three chips per condition and shared donor pools do not provide independent human-population replication.

MYH1 still decreases in all four groups, but broad myogenesis and muscle-contraction programs do not repeat their directions. TNF/NF-kB and inflammatory-response gene-set decreases are a secondary lead confined to the young/active pool under all scoring checks; age and activity are confounded.

**Question for the mentor:** is the aggregate mitochondrial-expression pattern biologically coherent enough to justify a focused driver/metadata audit and an independent matched-condition comparison?

## 2. MG63 gives a stable response against onboard 1g controls

In GSE224805, three microgravity versus three onboard-1g cultures show higher TNF/NF-kB and inflammatory-response gene-set expression, and lower DNA-repair gene-set expression. These directions survive sample deletion, alternative scores, and author-versus-NCBI processing on five matched samples.

BridgeRNA preserves this response well: median balanced-split direction cosines are 0.953 for model mean and 0.835 for expression. Both are positive in every split. That is within-study robustness, not evidence of superior prediction. MG63 is an osteosarcoma-derived cell line; this does not establish normal bone biology or impaired repair function.

**Question for the mentor:** is an inflammation/repair-associated transcriptional response in this controlled context a better next target, ideally tested in another flight experiment with primary bone cells?

## 3. Endothelial cells show why control choice matters

GSE157937 has three microgravity, two onboard-1g and three Earth cultures. Oxidative-phosphorylation expression rises robustly against Earth controls, but fails the full robustness checks against onboard 1g. The gravity-specific model result is less stable than MG63; a lower unfolded-protein-response gene-set score is a narrower lead. Small groups and shared controls limit interpretation. Onboard-1g versus Earth cannot isolate radiation.

## Scope and guardrails

The initial survey covered 559 samples, 28 accessions and 11 tissue groups. Follow-ups added 12 repeat-flight muscle chips and 14 biological samples with onboard controls. Ten predefined gene sets were evaluated across 60 primary contrasts, plus one alternate-processing contrast. No program score has the same mission-averaged direction across all four mouse-muscle missions, despite earlier recurrent gene candidates. Analog experiments remain distinct from actual flight.

These are exploratory expression associations. Gene-set scores are not pathway activity measurements or model explanations. We have not established statistical significance, a universal signature, general model superiority, or novelty. Choose one focused biological question before deeper evaluation or fine-tuning.

**Suggested opening:** “The broad survey was mixed, but two targeted follow-ups were useful: a shared average mitochondrial gene-set shift in human muscle chips, and a stable inflammation/repair-associated response in a human cell model with onboard 1g controls. I want to discuss which gives us the clearest independent next test.”
