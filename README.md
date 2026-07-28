# NASA RNA mixture-of-experts

Masked gene-expression modeling that asks when specialized RNA models outperform one
general model, how a model can choose a specialist from expression alone, and when
biological domains should share or isolate training information.

Start with [`docs/current-status.md`](docs/current-status.md). It contains the active
run, frozen hashes, evidence boundaries, and next decision.

## Current state

- **Stage 0 — species specialists:** complete. An expression-only router reliably
  chooses between human and mouse specialists and beats a fixed mixture under a
  corrected study-aware evaluation.
- **Stage 1 — organ specialists:** complete. Organ-specialized models improve
  reconstruction versus one general model with known-organ, automatic hard, and
  automatic soft routing. The reverse-direction ARCHS4 evaluation is explicitly
  post-access QC-amended.
- **Stage 2 — sharing versus interference:** active. Same-budget substitution is
  uniformly harmful; recipient-preserving addition is mixed. A frozen crossed
  trunk/optimization diagnosis is testing whether any helpful pattern is
  reproducible enough to guide selective sharing.

The project is representation-first. Organ is the strongest independently validated
specialization axis and current benchmark, not a permanent restriction on the MoE.

## Key results

| Result | Bounded takeaway |
| --- | --- |
| Stage 0 blind species router | 99.0% balanced species accuracy; adaptive routing remains useful after strengthening the pooled control |
| Stage 1 GTEx → ARCHS4 | 3.797% lower MSE with the correct organ specialist; 3.633% hard automatic; 3.676% soft automatic |
| Stage 2 substitution | all 56 directed organ pairs harmful in all three seeds when another organ replaces half the target-organ budget |
| Stage 2 addition | one of eight pairs robustly helpful; none consistently beats adding more target-organ data |

See:

- [`docs/stage0-final-result.md`](docs/stage0-final-result.md)
- [`docs/stage-1-end-result.md`](docs/stage-1-end-result.md)
- [`docs/stage2-directed-transfer-preliminary-result.md`](docs/stage2-directed-transfer-preliminary-result.md)
- [`docs/stage2-additive-transfer-result.md`](docs/stage2-additive-transfer-result.md)
- [`docs/stage2-seed-stability-diagnosis.md`](docs/stage2-seed-stability-diagnosis.md)

## Repository layout

```text
core/            model definitions and deterministic training
preprocessing/   reference and expression preprocessing
evaluation/      cohort construction, frozen scoring, controls, and evaluators
runs/            active and reproducibility launchers
tests/           fail-closed protocol and evaluator tests
artifacts/       small tracked protocols, manifests, reports, and figures
docs/            canonical status and scientific result documents
presentation/    rendered historical/current decks, content brief, and theme
data/            reference files plus large ignored local datasets
checkpoints/     ignored local model weights
backups/         ignored checksum-bound recovery bundles
```

Generated datasets, checkpoints, runtime results, and backups are intentionally
excluded from Git. Small scientific protocols and result summaries are tracked.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the focused test suites associated with a workflow before launching it. Exact
commands, commits, schedules, and host paths belong in the relevant document under
`docs/`, not in this overview.

## Presentation workflow

All presentations beginning with the July 30, 2026 deck use
[`presentation/design.md`](presentation/design.md), the canonical
Anthropic-inspired scientific field-journal specification.
The workflow is audience-first, visual-first, and script-free. Historical rendered
decks remain unchanged.

## Provenance

This standalone repository continues work originally developed in the `sp26_nasa`
team repository, itself derived from Walter Alvarado’s `bridge-rna` work. The detailed
pre-cleanup chronology remains recoverable from Git commit `2bc1bef`.
