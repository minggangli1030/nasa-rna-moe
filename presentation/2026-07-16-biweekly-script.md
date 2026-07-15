# Talking script - 2026-07-16 biweekly (~10 min, 10 slides)

The slides hold the numbers. Use the script to keep the methodological story
clear without reading every bullet. Structure: slides 2-5 recap the finished
Stage 1 interspecies work concisely, slides 6-8 lay out the Stage 2 organ
hypothesis and fair design, slide 9 is the one experiment still running plus the
decision tree, and slide 10 is the new Stage 3 direction I want to pursue.

## Timing

| Slide | Target | Running total |
|---|---:|---:|
| 01 - Title and training task | 0:50 | 0:50 |
| 02 - Stage 1: the evaluation was broken | 1:00 | 1:50 |
| 03 - Stage 1: large headroom, and scale | 1:10 | 3:00 |
| 04 - Stage 1: blind gate | 1:00 | 4:00 |
| 05 - Stage 1: what it proves and does not | 0:50 | 4:50 |
| 06 - Overarching goal: species to organs | 0:50 | 5:40 |
| 07 - The fair Stage 2 experiment | 0:55 | 6:35 |
| 08 - Stage 2 immediate plan | 0:50 | 7:25 |
| 09 - Running control and decision tree | 1:00 | 8:25 |
| 10 - New direction: interference matrix | 1:05 | 9:30 |

---

**01 - Title and training task**

Hi everyone, I'm Martin. To make the task concrete: this is self-supervised
RNA-seq pretraining. I hide 30 percent of a sample's genes and ask the model to
reconstruct their expression from the other 70 percent. That teaches which genes
and biological programs move together, without needing a disease or species label
for every sample. The strategy is to learn those representations from abundant
ground-based ARCHS4 data and transfer them to rare spaceflight studies. My MoE
question is whether a biological specialist reconstructs those hidden genes better
than one general model. Last sprint that looked negative; this sprint the
conclusion changes after I corrected the evaluation.

**02 - Stage 1: the evaluation was broken**

The July 9 result made fixed ensembling look slightly useful and adaptive routing
look useless. Before accepting that, I audited the evaluator end to end and found
it was invalid: it fed raw TPM to models trained on log-TPM, fitted blend weights
on the reporting set, used a test-derived gene mean, called a hard selector the
oracle, and let large GEO studies dominate the average. So the real work this
sprint was rebuilding a frozen, study-aware protocol: a 103-study strict cohort
disjoint from every training study, one log-one-plus transform, out-of-fold
weights, and clustered-bootstrap intervals. The key principle is on the slide:
beating one pooled model is only ensemble evidence; to claim adaptive MoE value
the router has to beat the fixed ensemble.

**03 - Stage 1: large headroom, and scale strengthens it**

Under the corrected protocol the result flips, including on the unchanged 5k
checkpoints. At 5k, true-species soft routing lowers MSE by 18.7 percent versus
the fixed blend; at 20k it grows to 34.7 percent, with the absolute gain interval
entirely above zero and residual correlation also improving. Hard routing already
delivers most of that; soft mixing is a smaller refinement; and the soft oracle at
35 percent shows species explains almost the entire measured ceiling. V3 here is
just scale - same four-layer Performer, same 15,448 genes, same objective, four
times the data - so I call it a controlled scale comparison, not a perfect
ablation, because draws and epoch budgets differ. The headline discovery is the
evaluation fix, since 5k moves too.

**04 - Stage 1: blind expression gate**

Next: is this useful when the species label is not handed to the system? I trained
a small balanced logistic gate on separate calibration studies. It sees exactly
the masked expression the expert sees; the targets are hidden. On the strict cohort
it identifies 102 of 103 samples, its soft route lowers MSE by 33.95 percent versus
the fixed blend, and it is only 1.11 percent behind routing with the true species.
So for human versus mouse, expression itself contains a route a blind gate can
recover without answer leakage.

**05 - Stage 1: what it proves and does not**

The Stage 1 conclusion is now positive but bounded. Supported: real
species-conditioned specialization - hard routing works, blind routing works, and
more data increases headroom. Not yet supported: that storing three full experts
is the best systems tradeoff, or that this improves a downstream spaceflight
endpoint, and organ specialization has to be tested on its own. There is also one
open control, which I will come back to on slide 9. The honest one-line summary is
that adaptive routing beats the fixed ensemble cleanly; the "beats a fair single
general model" claim is what the open control is there to settle.

**06 - Overarching goal: species to organs**

This is the arc of the project. Stage 1 is not just a human-versus-mouse
classifier - it is a proof that biological subdomains support different predictive
relationships, and that expression alone can identify which specialist to use.
Stage 2 transfers that lesson within human biology: organ-specific gene programs
may be distinct enough that a trained expression router plus the right organ expert
beats one general human model on an unknown-organ sample. The target system is more
accurate through specialization, efficient because top-one routing runs a single
expert, and interpretable because the route has an explicit organ meaning. Stored
size still grows, and I report that as a cost.

**07 - The fair Stage 2 experiment**

This figure states the primary experiment. With the same training data and roughly
the same inference compute, does blind organ-specialist routing reconstruct masked
genes better than one general model? The specialists collectively see N samples and
the pooled model sees the identical N-sample union, so no specialist gets extra
data. At inference the organ label is hidden: the router uses expression we already
measured, activates one expert, and sends low-confidence samples to the general
model. This is practical because real samples often arrive with missing or
unreliable organ metadata. Fixed, metadata, random-shard, and oracle controls
separate genuine organ specialization from generic ensembling.

**08 - Stage 2 immediate plan**

A conservative ARCHS4 audit supports a five-organ pipeline pilot - brain, skin,
liver, colon, lung - 2,856 samples across 317 connected studies, with K chosen from
data rather than fixed in advance and the pooled training-ID hash exactly equal to
the specialist union. I am not launching the full campaign yet: spot checks found
residual tumor and cell-source shorthand and some specialists are still small. Next
is label cleanup and a bounded end-to-end smoke test across all controls, including
the random-shard experts. I scale only if blind top-one beats the pooled and
inference-matched controls by at least five percent MSE with positive study-level
and residual-correlation intervals.

**09 - Running control and decision tree**

One experiment is still in flight. The original pooled mixed model trained with
species-contiguous batches - a known weakness - so I am retraining it with global
row shuffling. On a clean exit it automatically runs the full and strict evaluation
and the blind-gate rerun on the frozen masks. It will not finish before this talk,
so I am deliberately not showing a partial result; instead here is the decision
tree. If blind-soft still beats both the fixed ensemble and this fairer pooled model
by at least five percent, Stage 1 is practically convincing and I green-light Stage
2 training after label cleanup. If it beats the fixed ensemble but not the shuffled
pooled model, that is an adaptive-ensemble benefit, not a better general model, and
I reframe the claim. If the soft oracle drops below three percent, there is no real
routing ceiling and I revisit expert and data design before spending compute. And
if a full-cohort win disappears on the strict cohort, I treat it as study leakage,
not MoE evidence.

**10 - New direction: organ interference matrix**

Finally, where I want to take this next. Reviewing the multi-task and
transcriptomics literature, I realized "does MoE beat a dense model" is a mostly
expected pattern - the interesting, and as far as I found genuinely novel, question
is where and why organ specialization helps. So the proposed Stage 3 experiment is
an organ-by-organ interference matrix: for each pair, does adding organ B to joint
training help or hurt reconstruction on a held-out, study-disjoint organ A? I
control for the fact that adding B also adds data with size-matched fillers, so the
matrix isolates B's biological identity. It reuses essentially the whole Stage 2
pipeline - mainly a change of training-set composition - and it reframes the paper
from "MoE works" to the transfer structure of the human transcriptome, while also
explaining which organs the Stage 2 router should help most. I could not find prior
work building this matrix from a masked bulk-expression model, so I think it is both
novel and worth testing. A backup direction is asking whether the learned experts
even match the organ ontology or cut across it along a different biological axis.

## Optional current-run insert (slide 09)

Only if the shuffled pooled run and its automatic frozen evaluation finish before
the talk: replace the decision tree's framing with the realized branch and report
shuffled pooled strict MSE, blind-soft versus shuffled fixed-blend relative MSE
reduction and CI, and one sentence on whether the Stage 1 conclusion survives. Do
not report a partial epoch or validation loss as an evaluation result.

## Likely questions

**Why not use OSDR?**

The available OSDR evaluation is mouse-only. Useful for downstream spaceflight
transfer, but it cannot test whether a blind interspecies router distinguishes
human from mouse.

**Is the blind gate leaking species through the targets?**

No. All reconstruction targets are replaced with the mask token before the gate
sees the sample, and calibration and test connected studies are disjoint.

**Does this prove MoE beats one equally large general model?**

Not fully. It beats the current pooled model and the fixed ensemble, but expert
storage is larger. The shuffled pooled retrain addresses the batch-order weakness;
future work should also compare shared-backbone or adapter experts under a
parameter budget.

**Why five organs?**

K is selected by minimum capped sample count and number of independent connected
GEO study groups after conservative filtering. Five organs currently pass; K can
change as label coverage improves.

**Why reconstruction instead of classification?**

Masked reconstruction is the pretraining objective and gives a controlled zero-shot
specialization test. Downstream spaceflight classification improvement is a later,
separate claim.

**Is the Stage 3 interference matrix just multi-task task-grouping?**

The methodology descends from task-affinity and task-grouping work, which I cite.
The novelty is the measurement in genomics - a per-organ interference matrix from a
masked bulk-expression model, which I did not find in prior work - not a new
algorithm.
