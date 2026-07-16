# Related Work — NASA RNA MoE

Living prior-art record for the project. A late-2026 submission is only a horizon;
record relevant work now without forcing a paper claim before Stage 1/2 results.
Organized by the argument each block supports. Use this to (a) position a future
contribution, (b) avoid redoing known experiments, and (c) pull citations.

**Last updated:** 2026-07-15.

**Provenance convention.** Entries marked **[verified]** were checked against an
official paper page (publisher/proceedings/OpenReview/arXiv) on 2026-07-15. Entries
marked **[from-memory — verify]** are canonical works cited from background knowledge;
confirm the exact title, authors, venue, and year before putting them in a bibliography.
Do not cite a **[from-memory]** entry in a paper without checking it first.

---

## A. Core thesis: when does router + specialists beat one dense model?

The central Stage 1 claim — router + K organ experts beats one general human model
on the same data at matched inference compute — is a *confirmatory* instance of an
established ML pattern. These ground the mechanism and force honesty about what is
and isn't novel.

- **[verified]** *Mixture-of-Experts Can Surpass Dense LLMs Under Strictly Equal
  Resource* — arXiv 2506.12119 (Fudan / Megvii / StepFun, 2025). The compute-matched
  MoE-vs-dense question. Use to justify the "matched inference compute" framing —
  but note their win comes with more parameters; our honest framing is
  *iso-inference-compute, K× storage*.
- **[verified]** *Robustness of Mixtures of Experts to Feature Noise* — arXiv
  2601.14792 (2026). Iso-parameter regime; why MoE beats dense beyond parameter
  scaling. Supports the fair, parameter-aware comparison.
- **[verified]** *Mixture of Experts Provably Detect and Learn the Latent Cluster
  Structure in Gradient-Based Learning* — arXiv 2506.01656 (U. Tokyo / RIKEN AIP,
  2025). Theory: MoE wins **iff** the data has genuine latent cluster structure the
  router can exploit. This is our load-bearing "why it might work" citation and the
  reason organ (strong tissue variance axis) is a favorable but non-trivial test.
- **[verified]** *TAG-MoE: Task-Aware Gating for Unified Generative Mixture-of-
  Experts* — arXiv 2601.08881 (CAS / Tencent Hunyuan, 2026). Names the mechanism:
  "severe task interference in dense... a shared parameter space must compromise
  between conflicting objectives." Our negative-transfer hypothesis, stated as an ML
  failure mode.
- **[from-memory — verify]** Shazeer et al., *Outrageously Large Neural Networks:
  The Sparsely-Gated Mixture-of-Experts Layer* (2017, arXiv 1701.06538). Canonical
  sparse-gated MoE.
- **[from-memory — verify]** Fedus, Zoph, Shazeer, *Switch Transformers* (2021,
  arXiv 2101.03961). Canonical compute-matched sparse MoE at scale.
- **[from-memory — verify]** Jacobs, Jordan, Nowlan, Hinton, *Adaptive Mixtures of
  Local Experts* (1991). Original MoE; cite for lineage.
- **[verified]** *Learning Factored Representations in a Deep Mixture of Experts* —
  arXiv 1312.4314 (Eigen, Ranzato, Sutskever, 2013). Early deep MoE with
  class/location-specialized experts.

## B. Genomics / transcriptomic foundation models (domain baselines)

Where our pooled "general model" and masked-gene task sit relative to the field.

- **[verified]** *BMFM-RNA: An Open Framework for Building and Evaluating
  Transcriptomic Foundation Models* — arXiv 2506.14861 (IBM, 2025). Unifies TFM
  objectives incl. masked LM and multitask; whole-cell expression decoder. Represents
  the *generalist/pooled* status quo we compare against.
- **[verified]** *What Topological and Geometric Structure Do Biological Foundation
  Models Learn? Evidence from 141 Hypotheses* — arXiv 2602.22289 (2026). Probes
  scGPT/Geneformer internal structure. Ancestor for D2's interpretability angle in
  the biology setting (as opposed to LLM interpretability).
- **[from-memory — verify]** scGPT (Cui et al., 2024, Nat. Methods) and Geneformer
  (Theodoris et al., 2023, Nature) are the canonical single-cell TFMs — biomedical
  journals, so **not** in the alphaXiv/arXiv index; cite from the journals directly.
- **[verified]** [*xTrimoGene: An Efficient and Scalable Representation Learner for
  Single-Cell RNA-Seq Data*](https://proceedings.neurips.cc/paper_files/paper/2023/hash/db68f1c25678f72561ab7c97ce15d912-Abstract-Conference.html)
  — Gong et al., NeurIPS 2023. Closest major masked-continuous-expression ancestor:
  an asymmetric Transformer trained for scalable RNA-seq representation learning.
  Masked reconstruction is therefore not the novelty; specialization and validated
  biological structure must carry the contribution.
- **[verified]** [*scBERT as a large-scale pretrained deep language model for cell
  type annotation of single-cell RNA-seq data*](https://www.nature.com/articles/s42256-022-00534-z)
  — Yang et al., Nature Machine Intelligence 2022. Performer-based masked expression
  pretraining and interpretability lineage; single-cell/discretized rather than this
  project's continuous bulk-expression setting.
- **[verified]** [*Effective Biological Representation Learning by Masking Gene
  Expression*](https://openreview.net/forum?id=NqZqClqtTK) — Kenyon-Dean et al.,
  ICLR 2026 FM4Science workshop (TxFM). Trains on 1.4M bulk and single-cell profiles
  and evaluates downstream biological representation. Important scale/data-quality
  comparator; do not imply that low reconstruction loss alone proves a useful
  representation.
- **[verified]** [*A large-scale foundation model for bulk
  transcriptomes*](https://www.biorxiv.org/content/10.1101/2025.06.11.659222v1)
  — Kang et al., bioRxiv 2025 (BulkFormer). A 150M-parameter graph/Performer model
  pretrained on more than 500,000 human bulk profiles from GEO/ARCHS4 and evaluated
  on imputation and five downstream tasks. This is a direct scale, modality, data,
  and architecture comparator; generic claims about bulk representation learning or
  recovering latent mechanisms are already occupied.
- **[verified]** [*TifBERT: a self-supervised foundation model for
  normalization-robust bulk RNA-seq representation
  learning*](https://www.biorxiv.org/content/10.64898/2026.06.08.728683v1) —
  Hosseini and Sharma, bioRxiv 2026. Uses TF-IDF gene ordering and masked-gene
  modeling on TCGA. A direct recent bulk Transformer comparator, especially for
  cross-normalization robustness.
- **[verified]** [*An atlas-scale generative model for unified representation
  learning of bulk RNA-seq data*](https://doi.org/10.64898/2026.06.18.733198) —
  Pande, Uyar, and Akalin, bioRxiv 2026. A supervised VAE trained on 118,263
  TCGA/GTEx/ARCHS4 samples across 42 tissues; tissue is the dominant latent axis and
  is externally evaluated. This is the simplest direct challenge to treating organ
  recovery as a new discovery.
- **[verified]** [*Transformer-based representation learning for robust gene
  expression modeling and cancer prognosis*](https://www.nature.com/articles/s41598-025-14949-2)
  — GexBERT, Scientific Reports 2025. Bulk RNA-seq masking/restoration with downstream
  cancer, survival, and imputation tasks; a direct warning against positioning masked
  bulk reconstruction itself as new.
- **[verified]** [*Robust evaluation of deep learning-based representation methods
  for survival and gene essentiality prediction on bulk RNA-seq data*](https://www.nature.com/articles/s41598-024-67023-8)
  — Scientific Reports 2024. Benchmarks identity/PCA, autoencoders, masked
  autoencoders, and other learned representations. Motivates simple representation
  baselines and downstream checks rather than relying only on reconstruction.
- **[verified]** [*Parameter-free representations outperform single-cell foundation
  models on downstream benchmarks*](https://arxiv.org/abs/2602.16696) — Souza and
  Mehta, arXiv 2026. Careful normalization plus linear representations match or beat
  deep foundation models on several benchmarks. Require raw-expression, PCA, and NMF
  baselines before attributing any biological structure to MoE machinery.

### B2. Biological representation versus study/batch structure

Label-free routes are not biological merely because they are stable or interpretable.
ARCHS4 organ, disease, laboratory, platform, processing, and study are partially
confounded, so Stage 2 must score biological conservation and technical association
separately.

- **[verified]** [*Cross-study validation for the assessment of prediction
  algorithms*](https://academic.oup.com/bioinformatics/article/30/12/i105/388164)
  — Bernau et al., Bioinformatics 2014. Genomic prediction can look substantially
  better under ordinary cross-validation than across independent studies; supports
  connected-study splits and study-level uncertainty.
- **[verified]** [*Deep generative modeling for single-cell
  transcriptomics*](https://www.nature.com/articles/s41592-018-0229-2) — Lopez et al.,
  Nature Methods 2018 (scVI). Canonical example of learning expression
  representations while modeling batch effects; methodological context, not a direct
  bulk baseline.
- **[verified]** [*Benchmarking atlas-level data integration in single-cell
  genomics*](https://www.nature.com/articles/s41592-021-01336-8) — Luecken et al.,
  Nature Methods 2022. Key evaluation principle: measure biological conservation and
  batch removal separately. Adapt that principle to route-vs-organ and route-vs-study/
  platform diagnostics.
- **[verified]** [*Methods that remove batch effects while retaining group differences
  may lead to exaggerated confidence in downstream analyses*](https://academic.oup.com/biostatistics/article/17/1/29/1744261)
  — Nygaard, Rodland, and Hovig, Biostatistics 2016. When biology and batch are
  unbalanced, correction can create false confidence; batch correction alone cannot
  validate a biological expert partition.

## C. Species-routing context (Stage 0)

- Stage 0 result (species MoE, corrected evaluation) is our own; the point for
  reviewers is that species is the maximally-separable, minimally-useful routing
  axis, so the ~34% headroom does not transfer to organ. No external citation is
  load-bearing here beyond the MoE theory in block A.
- **[verified]** [*GLARE: discovering hidden patterns in spaceflight transcriptome
  using representation learning*](https://www.nature.com/articles/s41526-025-00525-5)
  — Seo et al., npj Microgravity 2025. Uses sparse-autoencoder representation
  learning, ensemble clustering, and pathway analysis on NASA GeneLab plant data to
  recover known and additional expression programs. It does not test bulk-human MoE
  routing or transfer, but it directly pre-empts a broad "representation learning
  discovers hidden spaceflight transcriptomic patterns" framing.

---

## D1. Directed organ transfer / interference graph  → Stage 2 supervised anchor

**Status:** potentially new *measurement in bulk transcriptomics*; the methodology
(directed transfer, task/domain affinity, grouping, and negative transfer) is well
established. D1 alone is moderate novelty. The stronger use is a cheap affinity screen,
selected matched-block confirmation, and held-out prediction of label-free routing.
No work located as of 2026-07-15 reports that full combination, but this is not yet a
submission-grade exhaustive novelty claim.

- **[verified]** *SMART: A Spectral Transfer Approach to Multi-Task Learning* —
  arXiv 2604.20161 (2026). Multi-task transfer when target sample size is small;
  borrowing strength across related studies. Methodological ancestor.
- **[verified]** *Co-Adaptive Multi-Task LoRA: Transfer-Aware, Label-Free Control of
  Domain Participation* — arXiv 2607.03522 (2026). Decides how domains share an
  adapter based on whether they help/hurt one another — closest general-ML analogue
  of "which organs should train together."
- **[verified]** *LoRI: Reducing Cross-Task Interference in Multi-Task Low-Rank
  Adaptation* — arXiv 2504.07448 (Tsinghua / UMD, 2025). Cross-task interference in
  PEFT.
- **[verified]** *Understanding Task Transfer in Vision-Language Models* — arXiv
  2511.18787 (2025). Pairwise task transfer measurement (different domain, same
  spirit as the matrix).
- **[verified]** *Parameter-Efficient Subspace Decoupling ViT for Mitigating
  Multi-Task Negative Transfer in Histological Scoring* — arXiv 2605.29852 (2026).
  Negative transfer in a *biomedical imaging* multi-task setting; nearest biomedical
  neighbor to our interference framing.
- **[verified]** *Systematic evaluation of the isolated effect of tissue environment
  on the transcriptome using a single-cell RNA-seq atlas* — arXiv 2406.06969 (Kyoto,
  2024). Measures tissue-environment effect on the transcriptome — closest *biology*
  work, but via a scRNA atlas, not a jointly-trained model. Key differentiator: we
  measure interference *induced by joint training*, not the raw biological effect.
- **[verified]** [*Taskonomy: Disentangling Task Transfer
  Learning*](https://openaccess.thecvf.com/content_cvpr_2018/html/Zamir_Taskonomy_Disentangling_Task_CVPR_2018_paper.html)
  — Zamir et al., CVPR 2018. Canonical directed transfer graph and explicit evidence
  that transfer can be asymmetric.
- **[verified]** [*Which Tasks Should Be Learned Together in Multi-task
  Learning?*](https://proceedings.mlr.press/v119/standley20a.html) — Standley et al.,
  ICML 2020. Canonical task-grouping baseline; establishes that pairwise training
  effects and grouping are not themselves new.
- **[verified]** [*Efficiently Identifying Task Groupings for Multi-Task
  Learning*](https://proceedings.neurips.cc/paper_files/paper/2021/hash/e77910ebb93b511588557806310f78f1-Abstract.html)
  — Fifty et al., NeurIPS 2021. Measures how one domain/task update changes another's
  loss in one training run. This is the practical template for the proposed cheap
  development-only organ-affinity screen.
- **[verified]** [*Gradient Surgery for Multi-Task
  Learning*](https://proceedings.neurips.cc/paper_files/paper/2020/hash/3fe78a8acf5fda99de95303940a2420c-Abstract.html)
  — Yu et al., NeurIPS 2020. Gradient conflict is a mechanistic negative-transfer
  diagnostic; compare it with held-out loss transfer rather than assuming equivalence.
- **[verified]** [*Asymmetric Multi-task Learning Based on Task Relatedness and
  Loss*](https://proceedings.mlr.press/v48/leeb16.html) — Lee, Yang, and Hwang,
  ICML 2016. Learns a sparse directed relation graph to limit negative transfer;
  important prior art for donor/recipient asymmetry.
- **[verified]** [*DMTG: One-Shot Differentiable Multi-Task
  Grouping*](https://proceedings.mlr.press/v235/gao24h.html) — Gao et al., ICML 2024.
  Learns higher-order task groupings jointly rather than relying only on sequential
  pairwise heuristics; relevant if a transfer graph is used to design expert groups.

## D2. Label-free expert structure versus biological organization  → linked Stage 2 core

**Status:** the meta-question ("do MoE experts specialize by domain / label") is an
active interpretability topic — **scoop risk**. RNA-seq clustering and latent-factor
discovery are also mature. Novelty requires the joint result: label-free routes are
cross-study stable, beat fair predictive controls, align with independently validated
biological programs rather than technical variables, and predict measured transfer.

- **[verified]** [*CellOS: Learning a World Model of Cellular State through Joint
  Embedding Prediction*](https://www.biorxiv.org/content/10.64898/2026.06.18.733163v2.full)
  — bioRxiv 2026. A 12B sparse-MoE single-cell foundation model trained at roughly
  390M-cell scale. Its purpose and representation differ, but it makes both "MoE for
  transcriptomics" and sparse expert scaling non-novel; our differentiator must be a
  controlled biological measurement, not architecture transfer.
- **[verified]** [*scMoE: single-cell mixture of experts for learning hierarchical,
  cell-type-specific, and interpretable representations from heterogeneous scRNA-seq
  data*](https://doi.org/10.1101/2024.10.24.620111) — Huang and Li, bioRxiv/ACM-BCB
  2024. Each expert is trained on a known cell type and a gate combines the frozen
  experts. This is close precedent for supervised biological specialists, but it does
  not establish label-free emergence or bulk cross-study transfer.
- **[verified]** [*scMoE: single-cell Multi-Modal Multi-Task Learning via Sparse
  Mixture-of-Experts*](https://doi.org/10.1101/2024.11.12.623336) — bioRxiv 2024;
  subsequently circulated as an ICLR submission. Uses sparse experts to address
  optimization conflict and interpretability across single-cell modalities/tasks.
  Distinguish the proposed single-modality bulk reconstruction setting and its
  independently tested route-to-transfer link.
- **[verified]** [*Transcriptomic age prediction using mixture-of-experts models
  reveals tissue-specific aging signatures in large-scale human RNA-sequencing
  data*](https://www.medrxiv.org/content/10.1101/2025.06.28.25330474v1.full) —
  medRxiv 2025. Applies learned gating and age-range experts to ARCHS4 bulk data and
  reports tissue-specific interpretation. Audit its split design and evidentiary
  quality before citing claims, but it already blocks a blanket "first MoE on bulk
  ARCHS4 with tissue-specific insight" statement.

- **[verified]** *The Illusion of Specialization: Unveiling the Domain-Invariant
  "Standing Committee" in Mixture-of-Experts Models* — arXiv 2601.03425 (2026).
  Directly questions whether MoE experts specialize by domain. **Read closely and
  differentiate** — this is the nearest framing competitor.
- **[verified]** *What Gets Activated: Uncovering Domain and Driver Experts in MoE
  Language Models* — arXiv 2601.10159 (2026). Expert-level functional specialization.
- **[verified]** *Probing Semantic Routing in Large Mixture-of-Expert Models* —
  arXiv 2502.10928 (Intel Labs, 2025). Whether routing is semantic vs efficiency-
  driven.
- **[verified]** *Exploring Expert Specialization through Unsupervised Training in
  Sparse Mixture of Experts* — arXiv 2509.10025 (2025). Emergent specialization
  without supervision — directly relevant to letting experts self-organize vs organ
  labels.
- **[verified]** *MoDE: CLIP Data Experts via Clustering* — arXiv 2404.16030 (2024).
  Clusters data into experts and discusses ontology vs cluster granularity; template
  for "learned partition vs annotated categories."
- **[verified]** *Heterogeneous Multi-task Learning with Expert Diversity (MMoEEx)* —
  arXiv 2106.10595 (2021). Inducing expert diversity in MTL; uses MIMIC-III / PubChem.
- **[verified]** [*The Myth of Expert Specialization in MoEs: Why Routing Reflects
  Geometry, Not Necessarily Domain Expertise*](https://arxiv.org/abs/2604.09780) —
  Wang, Hayou, and Nalisnick, arXiv 2604.09780 (2026). Direct warning for D2: routing
  similarity may follow hidden-state geometry without semantic expert functions.
  Compare route partitions with simple input/PCA/trunk-geometry clusters and measure
  counterfactual expert advantage before using the word specialization.
- **[verified]** [*Improving Expert Specialization in Mixture of
  Experts*](https://arxiv.org/abs/2302.14703) — Krishnamurthy, Watkins, and Gaertner,
  arXiv 2302.14703 (2023). Vanilla MoE does not guarantee intuitive decompositions or
  healthy expert utilization; motivates collapse, utilization, diversity, and
  seed-stability diagnostics.
- **[verified]** [*Learning to Specialize: Joint Gating-Expert Training for Adaptive
  MoEs in Decentralized Settings*](https://openreview.net/forum?id=3FBByWp6GL) —
  Farhat et al., NeurIPS 2025. Studies emergent domain specialization under
  distribution shift without clear task partitions; close general-ML precedent for
  the label-free joint router/expert experiment.
- **[verified]** [*Challenging Common Assumptions in the Unsupervised Learning of
  Disentangled Representations*](https://proceedings.mlr.press/v97/locatello19a.html)
  — Locatello et al., ICML 2019. Unsupervised factors are not guaranteed to recover
  semantic generative factors without inductive biases; biological alignment is a
  falsifiable result, not an automatic interpretation.

## D3. Router weights as deconvolution  → ARCHIVED (mostly established; interpretability check only if revisited)

**Status:** bulk RNA-seq deconvolution is a mature field. Only the "emergent,
unsupervised byproduct of reconstruction routing" framing is defensible, and it
still competes with unsupervised deconvolution. Use as a validation check, benchmark
against an established method, do not claim a new deconvolution method.

- **[verified]** *GC-MoE: Genomics-Guided Cell-Type-Specific Mixture of Experts for
  Histology-Based Single-Cell Spatial Transcriptomics* — arXiv 2606.02424 (2026).
  MoE + cell-type in transcriptomics — the closest existing MoE-for-composition work;
  must be cited and distinguished (they use histology + supervision).
- **[verified]** *Sweetwater: An interpretable and adaptive autoencoder for efficient
  tissue deconvolution* — arXiv 2311.11991 (NYU / Mayo / Navarra, 2023). Neural
  deconvolution baseline.
- **[verified]** *Masked adversarial neural network for cell type deconvolution in
  spatial transcriptomics* — arXiv 2408.05065 (Yunnan U., 2024).
- **[verified]** *Hierarchical Bayesian Model for Gene Deconvolution ... Human
  Endometrium* — arXiv 2510.27097 (Columbia, 2025). Probabilistic deconvolution.
- **[verified]** *Statistical Inference of Cell-type Proportions Estimated from Bulk
  Expression Data* — arXiv 2209.04038 (2022). Inference on deconvolved proportions.
- **[from-memory — verify]** Newman et al., *CIBERSORT* (2015, Nat. Methods) and
  Menden et al., *Scaden* (2020, Sci. Adv.) — canonical bulk deconvolution methods,
  biomedical journals (not in arXiv index). Benchmark D3 against one of these.

---

## Open novelty risks to re-check before submission

1. **D2 scoop risk** — re-run this search before scaling Stage 2 and again near any
   submission; expert-specialization work is moving fast (multiple 2026 entries).
2. **Masked reconstruction is established** — xTrimoGene, scBERT, TxFM, GexBERT, and
   bulk representation benchmarks mean neither the objective nor a Transformer on
   expression is the novelty. Require fair simple baselines and biological validation.
3. **Geometry/batch masquerading as biology** — compare routes with input/PCA/shared-
   trunk geometry; test study, platform, library-size, disease, and other nuisance
   associations; require cross-study and preferably external replication.
4. **D1 is established methodology** — a heatmap alone may be useful but is unlikely
   to be the exciting contribution. Test whether affinity predicts confirmed transfer,
   learned routing, or a better held-out expert grouping.
5. **Transcriptomic MoE is already occupied** — CellOS and both scMoE lines mean the
   novelty cannot be merely applying experts to expression data, sparse scaling, or
   showing interpretable routes. Re-check these fast-moving direct competitors before
   implementing or submitting D2.
6. **Broad hidden-pattern claims are occupied** — GLARE already makes this argument
   in NASA spaceflight transcriptomics. Require preregistered, cross-study, external
   evidence for a specific program and distinguish sample routing from gene clustering.
7. **D3 pre-emption** — confirm no reconstruction-trained genomics model has already
   been shown to recover composition as a byproduct; if one has, D3 collapses to a
   replication.
8. **Verify all [from-memory] IDs** before the bibliography; several canonical
   biology methods live in biomedical journals outside the arXiv/alphaXiv index and
   must be pulled from the journals directly.
