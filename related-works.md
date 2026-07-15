# Related Work — NASA RNA MoE

Prior-art record for the paper (arXiv-preprint target, ML-for-genomics venue).
Organized by the argument each block supports. Use this to (a) position the
contribution, (b) avoid redoing known experiments, and (c) pull citations.

**Last updated:** 2026-07-15.

**Provenance convention.** Entries marked **[verified]** were retrieved this
session via the alphaXiv / Hugging Face paper tools; their arXiv IDs and titles are
as returned by those tools. Entries marked **[from-memory — verify]** are canonical
works cited from background knowledge; confirm the exact ID, authors, and year
before putting them in a bibliography. Do not cite a **[from-memory]** entry in the
paper without checking it first.

---

## A. Core thesis: when does router + specialists beat one dense model?

The central Stage 2 claim — router + K organ experts beats one general human model
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

## C. Species-routing context (Stage 1)

- Stage 1 result (species MoE, corrected evaluation) is our own; the point for
  reviewers is that species is the maximally-separable, minimally-useful routing
  axis, so the ~34% headroom does not transfer to organ. No external citation is
  load-bearing here beyond the MoE theory in block A.

---

## D1. Organ-by-organ interference / transfer matrix  → Stage 3 default (highest novelty)

**Status:** novel *measurement in genomics*; the methodology (task affinity / task
grouping / negative transfer) is established and must be cited as ancestry. No
located work builds a per-organ interference matrix from a masked bulk-expression
reconstruction model.

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
- **[from-memory — verify]** Standley et al., *Which Tasks Should Be Learned Together
  in Multi-Task Learning?* (2020, arXiv 1905.07553). Canonical task-grouping.
- **[from-memory — verify]** Fifty et al., *Efficiently Identifying Task Groupings
  for Multi-Task Learning* (2021, arXiv 2109.04617). Task-affinity grouping; the
  method our matrix is most directly a genomics instance of.

## D2. Do learned experts match the organ ontology?  → backup / second result (novel angle, crowded field)

**Status:** the meta-question ("do MoE experts specialize by domain / label") is an
active LLM-interpretability topic — **scoop risk**. Our novelty is strictly the
biological alternative hypothesis (germ layer / cell composition vs organ) in the
genomics setting. Differentiate explicitly.

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

1. **D2 scoop risk** — re-run this search close to submission; the LLM
   expert-specialization literature is moving fast (multiple 2026 entries already).
2. **D3 pre-emption** — confirm no reconstruction-trained genomics model has already
   been shown to recover composition as a byproduct; if one has, D3 collapses to a
   replication.
3. **Verify all [from-memory] IDs** before the bibliography; several canonical
   biology methods live in biomedical journals outside the arXiv/alphaXiv index and
   must be pulled from the journals directly.
