# Talking script - 2026-07-16 biweekly (~10 min, 10 slides)

The slides hold the numbers. Use the script to keep the methodological story
clear without reading every bullet.

## Timing

| Slide | Target | Running total |
|---|---:|---:|
| 01 - Title and training task | 0:50 | 0:50 |
| 02 - Why the conclusion changed | 1:05 | 1:55 |
| 03 - V3 scale experiment | 0:50 | 2:45 |
| 04 - Corrected protocol | 1:00 | 3:45 |
| 05 - Headroom result | 1:15 | 5:00 |
| 06 - Blind gate | 1:05 | 6:05 |
| 07 - Interpretation | 0:55 | 7:00 |
| 08 - Overarching research goal | 0:55 | 7:55 |
| 09 - Fair Stage 2 experiment | 1:00 | 8:55 |
| 10 - Immediate plan | 1:00 | 9:55 |

---

**01 - Title and training task**

Hi everyone, I'm Martin. First, to make the task concrete: this is self-supervised
RNA-seq pretraining. I hide 30 percent of a sample's genes and ask the model to
reconstruct their expression from the other 70 percent. That teaches the model
which genes and biological programs move together, without requiring a disease
or species label for every sample. The practical strategy is to learn those
representations from abundant ground-based ARCHS4 data and later transfer them
to rare spaceflight studies. My MoE question is whether a biological specialist
can reconstruct those hidden genes better than one general model. Last week that
appeared negative; this week the conclusion changes after correcting evaluation.

**02 - The earlier result was not a valid MoE test**

The July 9 result made fixed ensembling look slightly useful but adaptive routing
look useless. Before accepting that, I audited the evaluator end to end. It was
feeding raw TPM to models trained on log-transformed TPM. It also fitted blend
weights on the reporting set, used a test-derived gene mean, called a hard
selector the oracle, and let large GEO studies dominate the average. Any one of
those can distort the comparison; together they made the earlier headroom number
unusable. So the key work this sprint was to freeze a study-aware evaluation
where tuning and reporting are separated.

**03 - V3 scale experiment**

In parallel, I finished the 20k scale-up. V3 is deliberately not a new model:
the human, mouse, and pooled experts use the same four-layer Performer, the same
15,448 genes, and the same 30 percent masked reconstruction objective as V2.
The principal change is four times more training and validation rows. The three
validation losses are on screen. I describe this as a controlled scale
comparison, not a perfect ablation, because the data draws and epoch budgets are
not identical.

**04 - Corrected protocol**

This is the comparison ladder I now use. The full diagnostic has both human and
mouse, unlike OSDR, which is all mouse. The strict sensitivity cohort goes
further: 103 samples from 103 connected studies that do not overlap the
reconstructed training-study union. Every model sees the same deterministic
mask in the correct log-one-plus-TPM space. Blend and router weights are fitted
out of fold, and confidence intervals resample whole studies. Most importantly,
beating one pooled model is only ensemble evidence. To claim adaptive MoE value,
the router has to beat the fixed ensemble.

**05 - Correct evaluation reveals headroom**

The corrected result is qualitatively different, including on the unchanged 5k
checkpoints. At 5k, true-species soft routing lowers MSE by 18.7 percent relative
to the fixed blend. At 20k, that grows to 34.7 percent. The confidence interval
on the absolute 20k gain is entirely above zero, and residual correlation also
improves. Hard species routing already gives almost all of the benefit; soft
mixing is a smaller refinement. The soft oracle reaches 35 percent, almost the
same as the species router. That means species explains nearly all of the
measured routing ceiling for these experts. Scale strengthens the result, but
the major discovery came from fixing evaluation, because V2 changes too.

**06 - Blind expression-derived gate**

The next question is whether this is useful when the species label is not handed
to the system. I trained a small balanced logistic gate on separate calibration
studies. It receives exactly the masked expression available to the expert; the
reconstruction targets are hidden. On the strict cohort it identifies 102 of
103 samples correctly. Its soft route lowers MSE by 33.95 percent versus the
fixed blend and is only 1.11 percent worse than routing with the true species.
So, at least for this human-versus-mouse problem, expression contains a route
that a blind gate can recover without answer leakage.

**07 - What Stage 1 proves and does not prove**

My Stage 1 conclusion is now positive but bounded. It supports real
species-conditioned specialization: hard routing works, blind routing works,
and more data increases headroom. It does not yet prove that storing three full
experts is the best systems tradeoff, or that this directly improves a
spaceflight classification endpoint. There is also one pooled-model control in
progress. The original mixed run shuffled parquet row groups, but those groups
still produced single-species batches. I am retraining it with global row
shuffling, and it will run the same frozen evaluation automatically when done.
It is not expected to finish before this talk, so I am not presenting a partial
result.

**08 - Overarching research goal**

This is the overall arc of the project. Stage 1 is not just a human-versus-mouse
classifier. It is a proof that biological subdomains can support different
predictive relationships, and that expression itself can identify which
specialist to use. Stage 2 transfers that lesson within human biology. The
hypothesis is that organ-specific gene programs are distinct enough that a
trained expression router plus the appropriate organ expert will beat one
general human model on an unknown-organ sample. The desired system is more
accurate through specialization, efficient at inference because top-one routing
runs only one expert, and interpretable because the route has an explicit organ
meaning. Stored model size still increases, and I will report that cost.

**09 - Fair Stage 2 experiment**

The biologically more interesting extension is within human data. Given a human
bulk RNA-seq sample without an organ label, can expression identify the relevant
organ expert, and can that routed specialist reconstruct masked genes better
than one general human model? The fairness constraint is important: if the
specialists collectively see N samples, the pooled model sees the identical
N-sample union. Top-one routing then executes only one expert plus a small gate,
so inference compute is roughly comparable; the extra model-storage cost is
reported separately. Fixed, metadata, random-shard, and oracle controls tell us
whether any gain is biological specialization or generic ensembling.

**10 - Immediate plan**

The first conservative ARCHS4 audit supports a five-organ pipeline pilot: brain,
skin, liver, colon, and lung, with 2,856 samples across 317 connected studies.
That K is data-driven rather than fixed in advance, and the pooled training-ID
hash exactly matches the specialist union. I am not launching the full training
campaign yet because manual spot checks found residual tumor and cell-source
shorthand, and some specialists are still small. The next step is label cleanup
and a bounded end-to-end smoke test. I scale it only if the blind top-one system
beats the pooled and inference-matched controls by at least five percent MSE,
with positive study-level uncertainty and residual-correlation improvements.
So the summary is: Stage 1 now justifies moving into Stage 2 data work, while the
remaining controls prevent us from overclaiming.

## Optional current-run insert

Only use this if the shuffled pooled run and its automatic frozen evaluation
finish before the presentation. Replace the current-run panel on slide 10 with:

- shuffled pooled strict MSE;
- blind-soft versus shuffled fixed blend relative MSE reduction and CI;
- one sentence: whether the Stage 1 conclusion survives the fairer pooled run.

Do not report a partial epoch or validation loss as an evaluation result.

## Likely questions

**Why not use OSDR?**

The available OSDR evaluation is mouse-only. It is useful for downstream
spaceflight transfer, but it cannot test whether a blind interspecies router
distinguishes human from mouse.

**Is the blind gate leaking species through the targets?**

No. All reconstruction targets are replaced with the mask token before the gate
receives the sample, and calibration/test connected studies are disjoint.

**Does this prove MoE beats one equally large general model?**

Not fully. It beats the current pooled model and the fixed ensemble, but expert
storage and parameter count are larger. The shuffled pooled retrain addresses
the known batch-order weakness; future work should also compare shared-backbone
or adapter experts under a parameter budget.

**Why five organs?**

K is selected by minimum capped sample count and number of independent connected
GEO study groups after conservative filtering. Five organs currently pass. K
can change when label coverage improves.

**Why reconstruction instead of classification?**

Masked reconstruction is the pretraining objective and gives a controlled
zero-shot specialization test. Demonstrating downstream spaceflight
classification improvement is a later, separate claim.
