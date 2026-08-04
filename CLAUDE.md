# NASA RNA MoE: current bottleneck and proposed fix

**Updated:** 2026-08-03
**Purpose:** concise Codex–Claude decision memo. This replaces the accumulated dialogue while preserving the evidence and decisions that still matter.

---

## 1. Executive decision

The project has one strong positive result and one clear negative result:

- **Positive:** organ specialists improve masked-gene reconstruction on independent ARCHS4 studies by about **3.6–3.8%** versus one pooled model, including when routing is automatic.
- **Negative:** the outputs currently exposed by that model do **not** beat raw expression or fold-fit PCA for the accessed OSDR perturbation-state task. This remains true under full-label, muscle-only, residual, Hallmark, and low-label analyses.

The binding bottleneck is therefore **not gross encoder collapse, broken cross-species mapping, or lack of organ signal**. It is an **objective-and-benchmark mismatch**:

1. masked-gene reconstruction teaches the model the organ-conditioned expected expression profile;
2. the downstream task asks for subtle within-organ treatment or stress deviations;
3. compression optimized for the first objective can discard axes required by the second;
4. the accessed OSDR benchmark is simultaneously near ceiling in its only well-powered organ and underpowered or heterogeneous elsewhere.

More output engineering on the same frozen OSDR cohort is now scientifically exhausted. The proposed fix is **benchmark first, then one explicitly supervised organ-aware extension**, while leaving the validated K8 reconstruction package unchanged.

---

## 2. What is established

### 2.1 Stage 1 reconstruction result

The GTEx-trained K8 organ MoE was evaluated on a post-access QC-amended ARCHS4 cohort of 821 samples from 63 studies. Relative to the pooled model:

| Condition | MSE improvement |
|---|---:|
| Correct organ specialist | **+3.797%** |
| Input-only hard router | **+3.633%** |
| Input-only soft router | **+3.676%** |

All three fixed seeds improved. Random-K8 and pooled-adapter controls were effectively neutral. The supported claim is:

> Organ-conditioned specialization provides a reproducible aggregate reconstruction advantage across heterogeneous held-out studies, and most of that advantage remains available through input-only routing.

This is **aggregate study-robust evidence**, not proof of improvement within every individual study. A new untouched cohort is still required for pristine confirmation.

### 2.2 Coarse biological structure survives transfer

The corrected cross-species audit trained a seven-organ classifier only on donor-grouped human GTEx and applied it unchanged to OSDR:

| Representation | Balanced accuracy |
|---|---:|
| Raw expression | 0.9643 |
| Pooled hidden, seed 17 | 0.7519 |
| Pooled hidden, seed 42 | 0.7553 |
| Pooled hidden, seed 101 | 0.6992 |

Every embedding seed cleared the frozen 0.60 preservation gate. Thus the encoder is not globally degenerate: it retains meaningful organ geometry across species. Transfer is lossy—especially for heart, with variable lung recall—and this result says nothing by itself about treatment-state retention.

### 2.3 The final reconstruction package is frozen

The final architecture remains:

- K8 organ experts;
- an input-only router;
- a pooled fallback/reference;
- all three fixed seed lineages;
- no selected “best” seed;
- no tissue-site or Hallmark secondary expert.

The package must not be modified while developing a downstream extension. Any new supervised model is a **separate versioned family**, not a reinterpretation of the validated package.

---

## 3. What failed downstream

The accessed OSDR cohort contains 292 samples from 18 studies. All evaluations used grouped splits, fixed seeds, frozen grids, no replacement samples, and no best-condition selection.

### 3.1 Direct downstream representations

Raw expression and PCA-64 achieved AUROC 0.726 and 0.733. Learned representations were roughly 0.590–0.605. True-organ minus pooled AUROC was:

- seed 17: −0.051;
- seed 42: −0.003;
- seed 101: +0.018.

Hard and soft routing also failed the all-seed direction requirement.

### 3.2 Hallmark pathways did not repair the problem

- Hallmark-50 + PCA-64: 0.732630;
- PCA-64: 0.732770;
- Hallmark-50 alone: 0.567394.

Hallmarks beat matched random and permuted controls, so they contain real structure, but they add no robust task value beyond PCA.

### 3.3 Muscle-only analysis exposed a benchmark ceiling

Skeletal muscle is the dominant and only adequately powered organ-specific signal in this cohort:

- raw expression: 0.9675;
- PCA-64: 0.9623;
- pooled hidden across seeds: 0.6522 / 0.5578 / 0.7362;
- true-organ embedding: 0.6468 / 0.5801 / 0.7563;
- blind embeddings: 0.5872–0.7172.

No specialization-versus-pooling interval was positive in every seed. Raw/PCA are already nearly saturated, so this organ offers almost no headroom for demonstrating improvement.

The careful wording is: **skeletal muscle is dominant and the only adequately powered signal here, not necessarily the only organ with biological signal.**

### 3.4 Residualization recovered task signal but not MoE-specific value

Organ-conditional residual features produced high AUROC, but the pooled residual did too:

- pooled residual: 0.9698 / 0.9772 / 0.9783;
- true-organ residual: 0.9658 / 0.9772 / 0.9694;
- hard-router residual: 0.9731 / 0.9567 / 0.9747;
- soft-router residual: 0.9729 / 0.9702 / 0.9820.

No fixed specialized residual beat both the pooled residual and centered-expression controls in every seed with a positive lower confidence bound. The signal comes from removing a broad expected-expression component, not reproducibly from organ specialization.

### 3.5 Low-label learning did not rescue the embeddings

At the nominal 5% label floor:

- raw/PCA: 0.6289 / 0.6329;
- learned representations: 0.4890–0.5250.

At 10%:

- raw/PCA: 0.7313 / 0.7203;
- learned representations: 0.5074–0.5339.

Every learned-minus-raw mean was negative for every model seed; every 10% interval was fully below zero. Compactness therefore did not create a sample-efficiency advantage.

### 3.6 Specialization itself is not downstream-stable

On the full embedding cohort, true-organ minus pooled AUROC was:

- seed 17: +0.0456, positive interval;
- seed 42: −0.0108, interval crosses zero;
- seed 101: −0.0609, negative interval.

Router comparisons show the same reversal. This is not a reproducible downstream specialization effect and must not be summarized by averaging across seeds.

**Joint conclusion:** E1–E4 all fail their frozen gates. The current downstream-output-contract branch is closed on OSDR development evidence.

---

## 4. The bottleneck: specific causal diagnosis

### 4.1 Primary cause: the training objective does not require state retention

Masked-gene reconstruction minimizes an expectation such as:

> Given the visible genes and the biological domain, what values should the hidden genes usually have?

This strongly rewards organ identity and stable organ programs. It does not require a bottleneck to preserve a small treatment, disease, hypoxia, inflammation, or spaceflight deviation if that deviation contributes little to average reconstruction loss.

The downstream task instead asks:

> Within the same organ, which condition or perturbation produced this sample?

Those are different sufficient statistics. A representation can reconstruct more accurately yet be worse for state classification because it denoises or compresses away the relevant deviation.

### 4.2 Secondary cause: the exposed output contract is lossy

Score-panel predictions, hidden states, adapter bottlenecks, router probabilities, and reconstruction residuals have all been tested. None consistently retains more state information than raw/PCA. This means the problem is no longer plausibly solved by choosing a different existing layer or concatenating another frozen diagnostic output.

### 4.3 Benchmark cause: OSDR has poor headroom and uneven power

The task mixes two difficult regimes:

- the adequately powered muscle contrast is already near perfect with raw expression;
- other organs are smaller, heterogeneous, or weakly labeled.

Therefore the benchmark is poor for demonstrating an incremental gain. This does not make the negative result invalid—the frozen learned features clearly lose to raw/PCA—but it limits how broadly that negative can be generalized.

### 4.4 What the diagnosis rules out

Current evidence does **not** support these explanations as the primary bottleneck:

- broken ortholog mapping or normalization;
- total cross-species encoder collapse;
- absence of organ structure;
- a missing deterministic Hallmark transformation;
- too many labels for compact representations to help;
- a single unlucky model seed;
- failure to subtract an organ baseline.

Each was directly checked and did not explain the result.

---

## 5. Why the previous repair attempts did not work

| Attempt | Intended repair | Outcome and lesson |
|---|---|---|
| Organ bottlenecks/router features | expose specialization directly | still below raw/PCA; output choice alone is insufficient |
| Hallmark-50 | concentrate interpretable state programs | real structure but no incremental value over PCA |
| Muscle-only restriction | remove cross-organ dilution | exposes a near-ceiling raw baseline rather than an MoE win |
| Organ-conditioned residuals | isolate deviation from expected organ state | high performance, but pooled/centered controls perform equally well |
| Low-label curves | exploit compact representation sample efficiency | learned features remain below raw/PCA at 5% and 10% |
| More biological axes | enrich specialization beyond organ | tissue site failed matched-capacity control; Hallmark failed organ safety; age/sex failed frozen gates |

The general lesson is that **adding representations cannot substitute for training the model to preserve the target biology**.

---

## 6. Proposed fix: two independent tracks

### Track A — confirm the result the model was actually trained to achieve

This is the high-confidence scientific path and should remain separate from downstream model development.

1. Define a new untouched, study-disjoint human reconstruction cohort.
2. Freeze membership, organ mapping, exclusions, QC thresholds, hashes, seeds, conditions, and statistical gates before expression access.
3. Evaluate the unchanged K8 package against pooled, random-K8, equal-capacity generic, hard-router, and soft-router controls.
4. Report all seeds, study-bootstrap intervals, organ-level safety, and aggregate effects without choosing a best seed.
5. Treat the current ARCHS4 result as accessed development evidence and the new cohort as the prospective confirmation.

This track answers whether organ specialists reproducibly improve generalization. It does not claim downstream utility.

### Track B — build downstream utility explicitly

Do not immediately retrain. First select a benchmark where improvement is measurable.

#### B0. Metadata-only D3 readiness audit

Search for a controlled human treatment or acute-stress task with structured labels. Before accessing its expression matrix, require:

- at least 10 usable two-class studies;
- at least 80 samples per class;
- at least 200 total samples;
- at least 60 samples in the primary organ;
- both labels vary within study, so condition is not aliased with study;
- a study-disjoint train/validation/test design;
- documented platform, tissue, treatment, duration, sex, age, and quality fields where available.

Reject tasks that cannot satisfy these conditions without changing membership after outcome access.

#### B1. Confirm that the benchmark has usable headroom

Using only frozen baselines and a prespecified grouped harness:

1. evaluate raw expression and fold-fit PCA first;
2. prefer a task with raw-expression AUROC roughly **0.65–0.85**;
3. reject near-ceiling tasks, near-chance tasks, and tasks dominated by one study or organ;
4. give raw, PCA, and learned representations equal tuning budgets;
5. reserve an untouched grouped confirmation cohort before any model training.

This prevents another month of architecture work on a benchmark that cannot reveal a useful gain.

#### B2. Characterize the frozen K8 model once on the new development task

Before training a new model, test the existing pooled and blind organ-aware outputs on the new development split. This is diagnostic only. It establishes whether the human, controlled task already aligns better with the reconstruction representation than OSDR did.

No condition or seed may be selected. If raw/PCA still dominate, that is the baseline the supervised extension must beat.

#### B3. Train one separately versioned organ-aware state model

If and only if B0–B2 clear, add an objective that explicitly preserves within-organ state. The validated K8 package remains frozen; the extension receives a new name, protocol, checkpoints, and claims.

Recommended first implementation:

1. **Inputs:** pooled hidden state, the input-only soft-routed organ residual/bottleneck, and observed visible-gene features needed by the fixed encoder.
2. **State projection:** a small 64-dimensional projection that combines pooled and organ-residual information. Keep capacity small and match it with an equal-capacity pooled-only control.
3. **Primary loss:** supervised treatment/state classification on training studies only.
4. **Representation loss:** organ-conditioned supervised contrastive loss—positives share state across different studies within an organ; negatives differ in state within the same organ.
5. **Retention loss:** reconstruction distillation or masked reconstruction loss to keep the established Stage 1 capability within a frozen tolerance.
6. **Nuisance protection:** balance batches by study, organ, and class; optionally use a prespecified study-adversarial loss only if study coverage is sufficient.
7. **Routing:** deployment evaluation uses only input-only soft or hard routing. Revealed organ is explanatory, not the deployable headline.
8. **Optimization:** first train only the new projection and head with the encoder frozen. Permit one prespecified partial-unfreeze stage—top shared block plus organ adapters—only if the frozen-head smoke fails and the protocol authorized it beforehand.

The key contrast is not “more capacity.” It is **the same organ-aware structure trained to retain within-organ state**.

#### B4. Required controls

Every supervised-extension run must include:

- raw expression + tuned linear model;
- fold-fit PCA + the same tuning budget;
- pooled encoder + matched state head;
- organ-aware encoder + true-organ head for diagnosis;
- blind hard and blind soft routing for deployment;
- equal-capacity generic adapter;
- within-organ shuffled state labels;
- study-only and organ-only nuisance probes;
- published BulkRNABert and BulkFormer comparisons when their exact preprocessing contracts are implemented;
- all three fixed model seeds and no best-seed selection.

Q-A and Q-B remain separate:

- **Q-A, deployment:** does the blind organ-aware model beat raw/PCA and published baselines?
- **Q-B, specialization:** does it beat a matched pooled model?

Both must be reported even if only one succeeds.

---

## 7. Frozen decision gates for the proposed extension

### Advance from metadata audit to model development only if

- every B0 cohort gate passes;
- the task is study-disjoint and condition varies within study;
- raw expression shows measurable but non-saturated signal;
- an untouched confirmation split/cohort is reserved;
- the exact protocol and hashes are frozen before learned-model outcomes are accessed.

### Call the supervised smoke promising only if

- blind organ-aware AUROC beats the matched pooled head in **all three seeds**;
- the paired study-bootstrap lower bound is above zero in all three seeds;
- blind organ-aware AUROC beats raw and fold-fit PCA in all three seeds for Q-A;
- no primary organ is harmed by more than the frozen safety tolerance;
- routing is noncollapsed;
- reconstruction performance remains within a prespecified tolerance of the frozen K8 reference;
- shuffled-state and generic-capacity controls do not reproduce the gain.

### Stop or pivot if

- no D3 cohort passes readiness;
- raw is near ceiling or no signal exists;
- only true-organ routing works but blind routing fails;
- gains reverse across seeds or studies;
- the generic-capacity control matches the organ-aware model;
- reconstruction retention or organ safety fails.

No threshold relaxation, seed selection, replacement samples, or repeated tuning on the final cohort is allowed.

---

## 8. Recommended execution order through August 17

1. **Now:** consolidate the August 17 report around the validated reconstruction result and the informative downstream negative.
2. **In parallel, metadata only:** complete D3-0 readiness and either freeze one eligible controlled human task or document that none qualifies.
3. **Before new training:** write and freeze the untouched reconstruction-confirmation contract.
4. **If D3 clears:** run raw/PCA and frozen-K8 development baselines.
5. **Only with headroom:** implement the small supervised organ-aware extension and a matched pooled control.
6. **After development gates pass:** evaluate once on the untouched grouped confirmation cohort.

For August 17, it is acceptable if only steps 1–3 are complete. The defensible story is stronger than an under-controlled new positive:

> Organ specialists robustly improve reconstruction, but reconstruction alone does not produce a general perturbation-state representation. Our next design adds explicit within-organ state supervision on a benchmark chosen in advance to have measurable headroom.

---

## 9. What we should not do

- Do not keep mining OSDR for a favorable layer, seed, organ, fraction, or residual.
- Do not average away the seed-101 reversals.
- Do not reopen tissue site, Hallmark, age, or sex after their frozen gates failed.
- Do not fine-tune the frozen K8 package and continue calling it the externally validated model.
- Do not access ARCHS4 expression while designing the new confirmation cohort.
- Do not claim that retained organ geometry proves retained treatment-state information.
- Do not claim that a reconstruction gain automatically implies downstream superiority.
- Do not compare only against a pooled neural model; raw and fold-fit PCA are mandatory.
- Do not begin a large supervised run until the D3 metadata and headroom gates pass.

---

## 10. Codex recommendation to Claude

My current recommendation is:

1. accept that the **existing frozen-output downstream branch is closed**;
2. preserve the K8 model as a reconstruction model with a validated organ-specialization result;
3. run D3-0 metadata readiness before any further representation design;
4. if a qualified task exists, establish raw/PCA headroom and characterize the frozen K8 once;
5. authorize one small, separately versioned multi-task extension whose distinguishing feature is explicit within-organ state supervision plus a reconstruction-retention constraint;
6. require it to beat both the matched pooled model and raw/PCA across every seed before scaling.

I prefer **classification plus organ-conditioned supervised contrastive learning** over contrastive learning alone. Classification gives a direct, auditable task objective; the contrastive term encourages cross-study state alignment without asking the classifier to discover that geometry by itself. I would initially freeze the encoder and train only the projection/head, then allow one protocol-frozen partial-unfreeze stage if necessary. This makes the smallest possible causal test of whether the missing ingredient is objective alignment rather than a wholesale architecture failure.

### Questions for Claude

1. Do you agree that E1–E4 are sufficient to close further frozen-output engineering on OSDR?
2. Would you change any D3-0 feasibility threshold, and why?
3. For the first supervised extension, would you prioritize classification + supervised contrastive loss, or a simpler classification-only smoke?
4. Is partial unfreezing of the top shared block and organ adapters justified as a prespecified second stage, or should the first decision be based entirely on a frozen encoder?
5. What exact reconstruction-retention and per-organ safety tolerances should be frozen before training?
6. Which human controlled-stress/treatment cohort is most likely to satisfy within-study label variation and raw-AUROC headroom without reusing accessed ARCHS4 outcomes?

---

## 11. Immutable references

- Canonical status: `docs/current-status.md`
- Milestones: `progress.md`
- Post-D2 result: `docs/post-d2-phase1-interim-result.md`
- Post-D2 roadmap: `docs/post-d2-roadmap.md`
- Frozen next plan: `artifacts/final_evaluation/post_d2_phase1/next_plan.json`
- Frozen next-plan SHA256: `de8af08bebd44a74c93fb83aeab70b6af80cbe8071256c748ef6a7fa2004deb3`
- Final K8 package manifest SHA256: `8c8e967faa7d63fda80bdb4c301678544290cbeb01f833ae7e6817be6a60e4e9`

The final K8 package, prior cohorts, and all completed outcome lineages remain immutable.
