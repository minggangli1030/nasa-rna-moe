# PaperPlot prompt: overarching human-organ MoE plan

The active slide asset is `human-organ-moe-overarching-plan.png`. The generated
`paperplot-ef56e392823647e181e217dd5a8d4c23.png` replaced the earlier raster and
was renamed to this semantic path on 2026-07-16. The replacement aligns Panel A
with the 32.94% blind hard two-expert result, uses the new Stage 0/Stage 1
vocabulary, and makes the calibration-only use of species labels explicit.
The pre-renumbering raster remains recoverable from Git history.

Create a publication-quality scientific pipeline figure for an ICML paper or
high-impact computational biology journal. Use a clean, flat vector style on a
white background, with restrained muted teal, sage green, charcoal, and one
amber accent for uncertainty. No gradients, 3D effects, decorative imagery,
people, DNA helices, or stock-art aesthetics. Use consistent line weights,
generous whitespace, short readable labels, and a left-to-right visual flow.
The figure must remain legible on a presentation slide and when printed at
single-page journal width.

Title: **From interspecies specialization to organ-aware human RNA-seq
Mixture-of-Experts**

Build two connected panels:

## Panel A - Validated Stage 0 principle: interspecies routing

Show one human bulk RNA-seq sample and one mouse bulk RNA-seq sample as compact
horizontal gene-expression heatmap strips. In each strip, visibly mask a random
30% subset of genes using neutral gray blocks. Label this input **"Masked
expression: 70% observed, 30% hidden"**.

Send the masked expression into a small box labeled **"Expression-only blind
router"** with the note **"species-supervised calibration; no species metadata or
hidden targets at test"**.
The router outputs probabilities to two boxes labeled **"Human expert"** and
**"Mouse expert"**. Emphasize that top-1 routing activates one expert per sample.
The selected expert reconstructs the hidden genes, shown as the gray blocks
becoming colored expression values. Label the output **"Reconstructed masked
genes"**.

Add one concise validated finding beneath Panel A:
**"Stage 0 result: blind hard routing reduced strict-cohort MSE by 32.94% versus
a fixed ensemble while executing one species expert at test."**

Do not depict this as species classification being the final task. Make clear
that species prediction is only the routing mechanism and masked-gene
reconstruction is the trained/evaluated task.

Between panels, add a clear rightward arrow labeled:
**"Transfer the specialization principle from between-species biology to
within-human organ biology"**.

## Panel B - Stage 1 hypothesis: unknown-organ human RNA-seq

At the upper left of Panel B, show five study-disjoint human bulk RNA-seq organ
cohorts labeled **Brain**, **Liver**, **Lung**, **Skin**, and **Colon**. Depict
each cohort as several small grouped heatmap strips to communicate independent
GEO studies rather than one large homogeneous dataset.

Show two fair training branches from these exact samples:

1. **Organ-specialist branch:** each organ cohort trains its corresponding
   expert. Label the experts **Brain expert**, **Liver expert**, **Lung expert**,
   **Skin expert**, and **Colon expert**.
2. **General-model control branch:** the exact union of all specialist training
   samples trains one box labeled **"General human model"**.

Place a prominent equality annotation between the branches:
**"Fair-data constraint: pooled training set = exact union of all specialist
training samples (ΣN_k = N)"**.

At inference, show a new human bulk RNA-seq sample with the organ label hidden.
Mask 30% of its genes using gray blocks. Label it **"Unknown-organ human RNA-seq"**.
Send the same masked input down two parallel comparison paths:

- **Proposed MoE path:** the sample enters a **"Trained expression-derived organ
  router"** that produces a probability distribution across the five organs.
  Show a compact probability bar and activate only the top-1 organ expert. Add
  the note **"one expert executed"**. The selected expert reconstructs the
  masked genes.
- **Control path:** the same sample enters the **"General human model"**, which
  reconstructs the same masked genes.

Add an amber low-confidence branch from the router to the general human model,
labeled **"Low confidence / out-of-taxonomy → general-model fallback"**.

At the far right, place the two reconstructions side by side under a bracket
labeled **"Paired, study-disjoint evaluation"**. List the primary outcomes:
**Masked-gene MSE**, **residual Pearson correlation**, and **clustered 95% CI**.
Under this comparison, state the Stage 1 hypothesis without inventing results:
**"Hypothesis: blind top-1 organ routing is more accurate than the general human
model while using approximately one-model inference compute."**

Add a small footnote:
**"The router sees only observed expression. Reconstruction targets and true
organ labels are unavailable at test time. Extra expert-storage cost is reported
separately."**

## Visual hierarchy and constraints

- Make Panel A visibly smaller and label it **"Validated principle"**.
- Make Panel B the main focus and label it **"Prospective Stage 1 experiment"**.
- Use solid arrows for training/data flow, teal arrows for the selected inference
  route, thin gray arrows for inactive experts, and an amber dashed arrow for the
  fallback.
- Use heatmap-strip glyphs for RNA-seq expression and simple labeled rectangles
  for learned models. Avoid brain/liver organ clip-art; the figure should look
  computational and scientific rather than medical-marketing oriented.
- Do not add any Stage 1 performance numbers, significance stars, or claims of
  success. Stage 1 is explicitly a hypothesis to test.
- Ensure all scientific labels are spelled exactly as provided and that no text
  overlaps arrows, models, heatmaps, or panel boundaries.

Preferred aspect ratio: 16:9 for the presentation version, with composition
that can also crop cleanly to approximately 2:1 for a paper figure.
