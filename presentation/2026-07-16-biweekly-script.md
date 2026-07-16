# Talking script - 2026-07-16 biweekly (~10 min, 10 slides)

The slides hold the numbers. Use the script to keep the methodological story
clear without reading every bullet. Structure: slides 1-2 recap last semester and
last week's apparent dead end for anyone who missed that meeting; slides 3-5 give
the corrected Stage 0 result; slides 6-8 define Stage 1; slide 9 narrows the novelty
through related work; and slide 10 gives the selected gated Stage 2 experiment.
Here `Stage` is the research phase; V1/V2/V3 remain the inherited model/debugging
generations inside Stage 0.

## Timing

| Slide | Target | Running total |
|---|---:|---:|
| 01 - Recap: last semester to summer question | 0:55 | 0:55 |
| 02 - Recap: last week's apparent dead end | 1:00 | 1:55 |
| 03 - Stage 0: large headroom in larger V3 | 1:05 | 3:00 |
| 04 - Stage 0: blind gate | 1:00 | 4:00 |
| 05 - Stage 0: what it proves and does not | 0:50 | 4:50 |
| 06 - Overarching goal: species to organs | 0:50 | 5:40 |
| 07 - The fair Stage 1 experiment | 0:55 | 6:35 |
| 08 - Stage 1 immediate plan | 1:00 | 7:35 |
| 09 - Related work and experiment choice | 1:05 | 8:40 |
| 10 - Selected Stage 2: two maps, one test | 1:20 | 10:00 |

---

**01 - Recap: last semester to the summer question**

Since not everyone could join last week, I will start with the thread from last
semester. The inherited project trained human, mouse, and mixed models to reconstruct
30 percent masked genes from the rest of each RNA-seq profile. V1 through V3 repaired
data and vocabulary problems and scaled the models. My summer contribution shifts
from completing those checkpoints to a scientific question: do specialists learn
complementary biology that routing can exploit? The roadmap is Stage 0 species as a
positive control, Stage 1 organ specialization, and Stage 2 label-free discovery.

**02 - Recap: last week's apparent dead end**

Last week's first read looked like a dead end: a fixed blend helped, while the
reported selector had almost no headroom, suggesting “blend, don't route.” Before
ending the MoE path, I audited the test and found the conclusion was unsupported:
wrong input scale, reporting-set fitting, a test-derived baseline, the wrong oracle,
and large-study dominance. I therefore rebuilt a frozen protocol around 103
disjoint connected groups, deterministic masks, out-of-fold fitting, equal group
weight, and clustered intervals. Slide 3 is what happened when that honest test ran.

**03 - Stage 0: large headroom in the larger V3 cohort**

The corrected result flips even for the unchanged 5k checkpoints: soft routing
beats fixed by 18.7 percent at 5k and 34.7 percent at 20k, with positive MSE and
residual-correlation intervals. Hard routing delivers most of the gain, while the
35 percent oracle is the ceiling among these three frozen models on this cohort.
V3 keeps architecture, objective, and 15,448 genes fixed while adding four times
the data. Because draws and epoch budgets differ, I call this a controlled scale
comparison, not a perfect ablation. The main finding is still the evaluation fix,
because 5k changes too.

**04 - Stage 0: species-supervised blind-gate feasibility**

Can the route be recovered with species hidden at test? A species-supervised gate
is fitted only on separate calibration groups; at test it sees masked expression,
not species or targets. Its probability interpolates calibrated weights over the
human, mouse, and pooled predictions. It gets 102 of 103 species calls right,
lowers MSE by 33.95 percent versus fixed, and trails true-species soft routing by
only 1.11 percent. This establishes expression-derived routability without answer
leakage. Because the soft condition executes all three models, it is not yet a
sparse-inference result.

**05 - Stage 0: what it proves and does not**

Stage 0 is positive but bounded. Species-conditioned hard and blind routing work,
and the larger V3 cohort shows more headroom. It does not establish the best
parameter/storage tradeoff, a downstream spaceflight benefit, or organ
specialization. Adaptive routing cleanly beats fixed. The shuffled pooled control
still running will update the stronger single-general-model claim, but it does not
waive any Stage 1 gate.

**06 - Overarching goal: species to organs**

Species is a maximally separable positive control, not the novelty. Stage 0 shows
that the pipeline can detect specialist headroom and recover a label-hidden route;
it does not prove subtler domains will specialize. Stage 1 asks whether organ
programs differ enough that an expression gate plus one organ expert beats a
general human model. The target is more accurate, top-one at inference, and
interpretable through an explicit organ route, while reporting extra stored models
as a cost.

**07 - The fair Stage 1 experiment**

Panel A shows the exact hard Stage 0 bridge: 32.94 percent lower MSE than fixed
while executing one species expert. Panel B is the fair organ experiment. All
specialists collectively see exactly the same N training samples as the pooled
model. At test, organ is hidden as a scientific stress test; the expression gate
activates one expert and sends low-confidence cases to the general model. Fixed,
true-organ, random-shard, blind, and oracle controls separate organ biology from
generic sharding, ensembling, and routing error. The primary comparison is blind
top-one versus the general model at approximately matched active compute.

**08 - Stage 1 immediate plan**

The provisional five-organ manifest has 2,856 rows across 317 connected studies,
and the pooled manifest hash equals the specialist union. It is pipeline data, not
a definitive cohort: no organ reaches 1,000 clean training rows. Before a long
run, each organ needs audited labels and 30/10/15 train/calibration/test groups,
plus a deterministic manifest-aware trainer and evaluator. Testing then climbs
three rungs: micro-overfit, the K=5 mechanical path, and brain/skin three-seed
feasibility. A green result must clear all five visible comparisons with positive
paired MSE intervals, a positive top-one residual interval, and 80 percent recovery
of known-organ gain. Today definitive Stage 1 is NO-GO; smoke testing only.

**09 - Related work and experiment choice**

Related work moves the novelty boundary. Compute-matched MoE gains, task grouping,
and negative transfer are established. xTrimoGene, BulkFormer, and TxFM already
cover masked transcriptomic representation learning. CellOS and scMoE mean this is
not the first transcriptomic MoE, while GLARE already claims hidden-pattern
discovery. So Stage 1 is necessary validation, not the final contribution. Three
directions remain: D1 measures directed transfer, D2 learns label-free routes, and
D3 searches within-organ latent states. I select D1 plus D2 because the held-out
route-to-transfer link is both falsifiable and practical; D3 waits for replicated
within-organ evidence.

**10 - New direction: two maps, one held-out test**

The full Stage 2 experiment requires Stage 1 green; amber outcomes authorize only
the bounded component shown in the entry rule. Controlled transfer asks whether an
equal budget from donor B helps or interferes with untouched recipient-A studies.
Separately, a shared-trunk MoE must first pass supervised-vs-random, anti-collapse,
stability, and compute controls; only then is its router trained without organ,
study, disease, or platform labels. On the untouched lockbox, co-routed domains
should also transfer compatibly. Transfer is directed while co-assignment is
symmetric, so initial selected-pair tests use preregistered sign/rank concordance,
not a graph-wide correlation. Finally, route-derived groups are retrained and
compared with organ, random, and pooled groups at matched compute. Recovering organ
is only a positive control; a biological claim also needs pathway coherence,
confound rejection, and independent-study replication.

## Optional current-run insert (slide 05)

Only if the shuffled pooled run and its automatic frozen evaluation finish before
the talk: replace slide 5's in-flight sentence with the realized branch and report
shuffled pooled strict MSE, blind-soft versus shuffled fixed-blend relative MSE
reduction and CI, and one sentence on whether the Stage 0 conclusion survives. Do
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

K is selected by provisional sample count and number of independent connected GEO
groups. Five organs pass the pipeline-pilot threshold; zero currently pass the
definitive training gate. K can change after label cleanup and coverage expansion.

**Why reconstruction instead of classification?**

Masked reconstruction is the pretraining objective and gives a controlled zero-shot
specialization test. Downstream spaceflight classification improvement is a later,
separate claim.

**What exactly is novel in Stage 2?**

Neither masked RNA-seq reconstruction, MoE, clustering, nor task affinity is new by
itself. The proposed contribution is the held-out link between two independently
measured structures: label-free route compatibility and controlled training
transfer. The route must predict transfer and produce a better grouping when
retrained, rather than merely yielding an interpretable-looking cluster plot.

**Does Stage 2 require a complete Stage 1 win?**

The full coupled experiment requires a green Stage 1. If specialists and oracle pass
but the blind gate fails, selected controlled transfer can still diagnose domains,
but label-free interpretation waits. If oracle complementarity exists but organ
fails, a bounded label-free feasibility pilot can ask whether organ was the wrong
axis. If the oracle itself has no meaningful headroom, Stage 2 stops.

**Isn't human-versus-mouse routing nearly trivial?**

Yes, and that is why Stage 0 is a positive control rather than the novelty. Its value
is validating the specialist/evaluation machinery before the subtler organ test.

**Is the blind gate unsupervised?**

No. Stage 0 and planned Stage 1 gates use labels on disjoint calibration groups, then
hide labels and reconstruction targets at test. Only the Stage 2 router is label-free.

**Why learn an organ router when tissue is usually known?**

Blinding organ is primarily a scientific test of whether expression supports the
specialization. Imperfect metadata, low-confidence fallback, and out-of-taxonomy
detection are secondary practical motivations.

**Could the routes just recover GEO study, platform, disease, or cell composition?**

Yes; that is the main alternative explanation. A biological claim requires strict
study lockboxes, adversarial confound checks, pathway coherence, and replication.

**Does this beat an equal-total-parameter dense model?**

Not yet. The primary top-1 comparison matches active inference compute and reports
stored parameters; a shared-backbone or parameter-matched dense control remains a
separate systems comparison.

**Are three selected transfer pairs enough to prove map agreement?**

No. They support preregistered sign/rank confirmation. A formal graph-level
correlation requires more powered edges.
