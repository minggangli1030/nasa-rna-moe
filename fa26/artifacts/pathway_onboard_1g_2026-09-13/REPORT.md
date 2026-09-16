# Pathway and onboard-1g follow-up — September 13, 2026

**Verdict: there are useful preliminary leads.** The strongest next discussion is a shared **average oxidative-phosphorylation gene-set increase in human muscle chips**, alongside a **stable, controlled microgravity response in MG63 cells**. These results narrow the biological questions; they do not establish a universal flight signature or a common mechanism.

Both authorized steps are complete. We scored ten predefined gene sets across the existing 56 contrasts and four new primary human contrasts: **600 primary pathway/contrast results**, plus ten results for a processing sensitivity. We added **14 biological samples** from two studies with onboard 1g controls. Frozen BridgeRNA inference on moe-reboot's A100 completed all **19 inputs** in 12.7 seconds; five inputs are alternate processing of the same MG63 samples, not additional biological replication. No training ran.

[Monday brief](../general_survey_2026-09-12/MONDAY-DISCUSSION.md) · [Pathway figure PDF](pathway_discovery.pdf) · [Model figure PDF](controlled_model_stability.pdf) · [All pathway results](pathway_contrasts.csv)

## 1. Muscle chips: a shared average program shift survives basic checks

The 173 observed canonical genes from the 200-gene Hallmark oxidative-phosphorylation set give a positive average score in both flights and both pooled donor contexts:

| Flight / pool | Mean gene-z-score shift | Genes increasing | Every chip-deletion sign retained? |
|---|---:|---:|---|
| GSE234465 / young-active | +0.335 | 64.2% | Yes |
| GSE234465 / old-sedentary | +0.207 | 57.2% | Yes |
| GSE298393 / young-active | +0.924 | 85.5% | Yes |
| GSE298393 / old-sedentary | +1.109 | 86.7% | Yes |

The direction also survives within-sample rank scoring, background-centered mean-expression scoring, a common observed gene universe, and replacing the first flight's count source with its published FPKM table. No single gene drives the positive average: all 173 single-gene deletions remain positive in every group. The source-FPKM rank shift in first-flight young/active chips is only +0.00072 (percentile ranks on a 0–1 scale), so this is not a large shift under every scoring method.

**The shared average does not imply the same gene-level response.** Within this set, cross-flight expression-change cosines are only +0.095 for young/active and −0.121 for old/sedentary. About 59% and 57% of member genes retain their signs between flights, respectively; 68/173 increase in all four groups. Gene-deletion/coherence checks were descriptive follow-ups after seeing the pathway result. These are not enrichment p-values or evidence for increased mitochondrial respiration. Scores are standardized separately within each contrast; their magnitudes cannot be read as comparable functional effect sizes across studies.

A secondary lead is lower **TNF-alpha/NF-kB and inflammatory-response gene-set expression in the young/active pool** in both flights, surviving the same source and sample checks. The old/sedentary pool does not consistently replicate this under all scoring methods. Shared donor pools and the joint age/activity grouping prevent an age-specific causal interpretation.

The negative evidence remains: whole-transcriptome and whole-embedding responses oppose across flights. **MYH1 decreases in all four groups**, but the broader myogenesis and muscle-contraction scores change direction between flights. Removing MYH1 leaves the myogenesis direction reversal intact; MYH1 is not a member of the downloaded Reactome muscle-contraction set. We therefore should not call this a reproduced global muscle-atrophy program. Three chips per condition, shared donors, flight hardware/duration differences, ground-control hardware differences and source processing remain limitations. [Earlier repeat-flight evidence](../muscle_repeat_flight_2026-09-12/REPORT.md).

## 2. MG63: a clear response with onboard 1g controls

[GSE224805](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE224805) provides three microgravity and three onboard-1g cultures. MG63 is an **osteosarcoma-derived, osteoblast-like cell line**, not healthy primary bone. Both groups were on the ISS; the [sample protocol](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSM7032597) records approximately 34 hours of treatment after recovery. This comparison controls much of the shared flight environment, while retaining centrifuge/hardware and protocol caveats.

| Gene set | Primary score shift | Source and sample checks |
|---|---:|---|
| TNF-alpha signaling via NF-kB | +0.874 | Pass |
| Inflammatory response | +0.375 | Pass |
| DNA repair | −0.571 | Pass |

These directions survive every single-sample deletion and alternative rank/background scores. They also hold in author and independently processed NCBI data on the **same five samples and same genes**. This supports a discussion of inflammation-associated and DNA-repair-associated transcription in this experimental context, not proof of inflammatory activation or defective repair capacity.

BridgeRNA preserves the controlled response particularly consistently: all nine balanced partitions have agreeing response directions for raw expression and both model summaries. Median between-partition cosines are **0.835 expression, 0.953 model mean, 0.954 model std**. On five samples shared by both source pipelines, author-versus-NCBI effect cosines are **0.930 expression, 0.992 model mean, 0.974 model std**. These overlapping splits are robustness diagnostics, not nine independent experiments or predictive accuracy estimates. The model does not yet demonstrate added predictive or biological value over expression.

The primary oxidative-phosphorylation score decreases, but its rank/background agreement fails in matched-five processing sensitivity. It is therefore **not** a highlighted MG63 finding. p53, ROS and clock scores also do not pass all checks. The data do not justify asserting a senescence or oxidative-stress mechanism from these program scores.

## 3. Endothelial cells: useful control design, weaker gravity-specific evidence

[GSE157937](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE157937) contributes three microgravity, two onboard-1g and three Earth HMEC-1 cultures. The same samples contribute to three dependent contrasts.

For microgravity versus onboard 1g, BridgeRNA-mean balanced-split agreement is **4/6**, versus **3/6** for expression. The unfolded-protein-response gene-set score decreases (−0.232) and passes source and sample checks. Several other plausible scores fail a deletion check. A myogenesis-labeled set also decreases, but its members have functions beyond muscle; the label does not establish muscle biology in endothelial cells.

Oxidative-phosphorylation expression increases robustly for **microgravity versus Earth**, but does **not** pass the full robustness checks for **microgravity versus onboard 1g**. This makes control choice a substantive issue. It is not evidence that gravity has no effect; there are only two onboard controls. Onboard-1g versus Earth includes environmental and protocol differences and cannot isolate radiation. Shared onboard controls also enter the two component contrasts with opposite signs, so an anticorrelation between those effects is not independent evidence for opposing mechanisms.

The filtered author CPM table is only a processing sensitivity: 11,010 canonical genes (72.6%) remain after unique HGNC mapping and common-gene restriction. The primary NCBI count inputs cover 99.90%. The muscle-contraction set fails the sensitivity coverage gate and is explicitly unpassed. All eight samples appear in the supplied pretraining catalog (seven train, one validation); these results cannot establish unseen-data generalization. MG63 samples are labeled unseen in that supplied catalog, which is an audit of the available manifest rather than a guarantee about all model exposure.

## Broader survey: retain the negative and context-specific results

All existing human flight, analog and mouse comparisons were scored with the same panel. Human analogs remain labeled separately from actual flight. In mouse skeletal muscle, **none of the ten mission-averaged program scores has the same sign across all four missions**. For example, oxidative phosphorylation is positive in RR-1 and negative in RR-23, RR-4 and RR-5. The earlier recurrent Cdkn1a, Dbp, Mmp14 and mapped Mt2 gene candidates do not establish uniform p53, circadian or oxidative programs. Mouse gene names and the human-canonical mapping must remain explicit. Related tissue accessions and shared animals are not independent mission replication.

## Methods and audit

The ten-set panel and directional robustness rule were recorded **before these pathway outcomes**, after the earlier global/gene findings were already known. This is an exploratory follow-up, not independent preregistration. Eight sets come from the [MSigDB Hallmark 2020 distribution](https://maayanlab.cloud/Enrichr/geneSetLibrary?mode=text&libraryName=MSigDB_Hallmark_2020); two are from the downloaded [Reactome GMT archive](https://reactome.org/download/current/ReactomePathways.gmt.zip): Circadian clock R-HSA-9909396 and Muscle contraction. The exact downloaded membership, canonical mapping, hashes and panel are saved. The snapshot is not described as the latest Hallmark release. [Hallmark collection documentation](https://www.gsea-msigdb.org/gsea/msigdb/human/collections.jsp).

Within a contrast, standardize each gene across samples, average within the set, and subtract control from exposure. Paired human contrasts use within-donor/cell-line differences, and their deletion unit is the pair; others delete one sample. Gene standardization is recomputed after deletion. At least ten observed genes and 50% of canonical-mapped set members are required; the fraction of the original published set is separately reported. Primary sets retain at least 86.5% of their published membership. Human cross-flight comparisons use common observed genes. No per-program p-values, multiple-testing significance or causal claims are made. Gene-set overlap means the ten results are not independent.

A highlighted direction must survive every leave-one-unit-out recomputation and agree under within-sample rank and background-centered mean-log-expression scores. For the presentation's human contrasts, it must also survive the source-processing checks, on matched samples and common genes where available. These flags do not measure statistical significance. The source-check table explicitly retains insufficient-coverage failures.

MG63 primary input uses all six author sample-count columns (99.954% canonical coverage); the workbook's differential-expression statistics are not used. Sample-wide scaling cancels during canonical TPM conversion; gene/sample-specific offsets in the published normalization are not independently excluded. The independently processed NCBI matrix provides five samples (99.901% coverage); **GSM7032598 is absent**, and no replacement was fabricated. Endothelial primary inputs use all eight NCBI raw-count samples. Both count inputs use the audited exon-length/observed-canonical TPM contract. FPKM inputs are rescaled directly, with no second length division.

Official frozen checkpoint **r7hnr92k**, latest available in the inspected author embedding source, was reused with unchanged inference code, human species IDs and float32. Missing genes use the unknown-token mask; zero fill is sensitivity only. Mask-versus-zero effect cosines exceed 0.99997 for every new contrast. Model input IDs/order, finite outputs and input hash were verified. **16 analysis/contract tests passed**, including outlier-only score rejection and common-gene denominator invariance. Both scientific figures were visually checked. Inference is complete; no new training or pending cohort run remains.

## Suggested mentor decision

Prioritize one of two bounded questions: **does the shared muscle-chip gene-set average reflect reproducible mitochondrial remodeling under matched conditions**, or **does the MG63 inflammatory/repair-associated pattern recur in an independent, preferably primary bone-cell experiment with onboard 1g controls**? A small metadata/driver audit and an independent comparison would be more informative than adding model complexity now. Keep the weaker endothelial result as a demonstration of why matched controls and enough replicates matter.

## Reproduction and files

Scripts: `fa26/pathway_onboard_survey.py` (`prepare`, `pathways`, `models`), `fa26/review_pathway_onboard.py`, `fa26/plot_pathway_onboard.py`. Run scripts from the repository with their saved inputs; preparation writes the exact model NPZ, and official `general_space_survey.py infer` produces its embeddings. The report's checks do not require retraining.

- `protocol.json`, `pathway_panel.json`, `mapped_panel.json`: frozen choices and membership.
- `manifest.csv`, `input_audit.json`, `inference_report.json`, `provenance.json`: sample/source/model audit.
- `pathway_contrasts.csv`, `contrast_inventory.csv`: all 61 comparisons, including the five-sample sensitivity.
- `pathway_source_sensitivity.csv`, `presentation_pathway_checks.csv`: source checks and figure flags.
- `oxphos_gene_changes.csv`, `oxphos_gene_deletion.csv`, `oxphos_cross_flight_coherence.csv`: descriptive driver checks.
- `model_contrast_metrics.csv`, `MG63_processing_sensitivity.csv`, `model_missingness.csv`: model diagnostics.
- `mouse_muscle_mission_programs.csv`: accession-averaged, then mission-averaged descriptive scores.

VM: `moe-reboot` (149.165.175.241), isolated directory `/media/volume/moe-reboot/fa26_pathway_onboard_20260913`. The second VM was unnecessary for this small run. The previous completed-run watcher remains paused.
