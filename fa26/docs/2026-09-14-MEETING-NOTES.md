# Meeting notes — September 14, 2026

> Post-meeting status (September 15): the authorized spaceflight sequence is complete
> through the human-muscle response-alignment control. No job is running or queued. The
> current irradiation-associated probe is not specific enough to support a
> radiation-driven flight interpretation. See [`PROJECT-LOG.md`](PROJECT-LOG.md),
> [`MEETINGS.md`](MEETINGS.md), and [`ROADMAP.md`](ROADMAP.md).

Status: documentation and planning only. Do not execute data preparation, inference,
training, evaluation jobs or watchers from these notes. Execution will be requested separately.

These notes summarize the user's PI discussion and subsequent ownership clarification.
The proposed implementation details in the linked plan are recommendations, not decisions
already made by the meeting participants.

## Research direction and ownership

Three fine-tuning tasks were identified:

| Task | Owner | Scope |
|---|---|---|
| 1. Batch effects | Brain (name as supplied) | Investigate technical preparation effects and contrastive learning while preserving biological differences |
| 2. Spaceflight | Minggang (my part) | Build a prediction head to identify spaceflight-related responses and investigate the genes/pathways the prediction relies on |
| 3. Human versus mouse | Not yet assigned | Investigate the human–mouse question; precise target, ownership and evaluation remain to be defined |

These are separate workstreams. Minggang's initial frozen-model prediction-head baseline
can proceed independently when execution is requested; it does not require waiting for
Brain's batch-correction model. A corrected model can be compared later under the same
prediction protocol. This ownership clarification supersedes treating the earlier
combined pipeline as one person's sequential assignment.

## Task 1 — batch effects / Brain

Discussion points:

- Benchmark preparation effects using poly(A) versus ribodepleted RNA and PCA/embeddings.
- Consider contrastive learning, including **different tissues within the same batch**
  and **poly(A) versus ribodepleted preparations**.
- Investigate whether technical information can be suppressed without erasing tissue
  or other biological differences. Batch classification with reversed gradients was
  another technique discussed earlier.
- RR1/RR3 and the linked BridgeRNA benchmark are relevant resources to examine.
- Fourier methods were mentioned casually; they are not a required part of the plan.

The exact contrastive positive/negative pairs and loss have **not** been agreed. Do not
interpret “same batch” as an instruction to pull different tissues together. A candidate
design would align verified same-RNA samples across preparations while retaining tissue
and donor distinctions; Brain will define and validate the objective.

## Task 2 — spaceflight / Minggang

Main question: **Can a prediction head recognize a defined spaceflight-related response,
and which genes/pathways does it use to make that prediction?**

- Start with a supported flight/control classification task and frozen BridgeRNA embeddings.
- Investigate gene contributions and pathway associations, including mitochondrial,
  inflammatory, DNA-repair and other stress-response programs where supported.
- Inspect layers/readouts as candidates; compare a simple head before choosing last-block
  tuning or LoRA. No best fine-tuning method has been established.
- Radiation and microgravity are possible later targets, requiring suitable experimental
  labels and controls. A flight classifier alone does not distinguish their contributions.
- Probabilities are desirable, but require calibration. “80% radiation” must not be
  presented as “80% of stress was caused by radiation.”
- Gene attribution describes evidence used by the model, not proof of causal genes.

The detailed proposed sequence is in [Minggang's plan](2026-09-14-SPACE-PREDICTION-HEAD-PLAN.md).

## Task 3 — human versus mouse

Recorded as a third fine-tuning task. The discussion did not establish whether the target
is species classification, cross-species transfer of a biological prediction, or alignment
of conserved responses. Do not equate these objectives or automatically remove species
information. Owner, matched tissues/conditions, gene mapping and success metrics remain open.
This task is not assigned to Minggang by these notes.

## Resources and unresolved decisions

- [Author benchmarks](https://github.com/alwalt/bridge-rna/tree/sample_embeddings/benchmarks)
  and the [local source review](../artifacts/bridge_benchmark_audit_2026-09-14/REVIEW.md).
- Additional mentor-provided data are pending. The screenshot's exact source/membership
  is still unverified; do not silently substitute candidate datasets.
- Minggang's first cohort, label definition, number of independent units and feasible
  study-held-out evaluation need to be specified before training.
- Sample-size requirements and the choice between a head, last-block updates and LoRA
  remain empirical questions.

No new experiment or fine-tuning task was executed when recording these notes.

## Subsequent clarification and execution authorization

Minggang accepted the target **flight prediction → contributing biological responses →
supporting genes**. On September 14, Minggang requested Markdown updates, folder
organization and execution of the next step. The six-program response-level reliance
pilot is now running with the existing frozen encoder and heads; this supersedes the
original documentation-only restriction for that pilot. Brain’s batch task and the
unassigned cross-species task remain separate. See the [active spaceflight plan](../workstreams/spaceflight/PLAN.md)
and [run status](../workstreams/spaceflight/STATUS.md).
