# NASA RNA mixture-of-experts

Research code and frozen evidence for asking when specialized RNA models outperform
one shared model—and whether reconstruction gains transfer to biological-response
classification.

The summer project is closed as of **2026-08-17**. Start with:

1. [`docs/project-closeout.md`](docs/project-closeout.md) — final scientific result,
   limitations, presentation decisions, and future plan.
2. [`docs/recovery-and-data.md`](docs/recovery-and-data.md) — verified backups and
   exact public-data reconstruction instructions.
3. [`docs/README.md`](docs/README.md) — index of final results and historical plans.

## Final result

Eight human-organ specialists reduced masked-gene reconstruction error relative to
one shared model on an externally evaluated ARCHS4 cohort:

| Condition | Reduction vs. shared model |
| --- | ---: |
| Correct organ supplied | 3.797% |
| Model chooses one organ expert | 3.633% |
| Model blends organ experts | 3.676% |

The evaluation covered 821 samples from 63 connected studies and eight organs. All
three fixed training seeds improved. Automatic routing retained about 96–97% of the
revealed-organ gain.

The learned outputs did **not** beat raw expression or fold-fit PCA for the tested
OSDR spaceflight-versus-ground classification task. The supported conclusion is that
specialization improved reconstruction, but reconstruction alone was not aligned
enough with the downstream biological question.

The ARCHS4 result is labeled **externally evaluated, pending untouched
confirmation**. It is not a clinical or operational spaceflight result.

## Repository layout

```text
core/            model definitions and deterministic training
preprocessing/   public-data and reference preprocessing
evaluation/      cohort construction, frozen scoring, controls, and evaluators
runs/            reproducibility and workflow launchers
tests/           fail-closed protocol and evaluator tests
artifacts/       tracked protocols, manifests, compact reports, and figures
docs/            closeout, results, plans, and recovery instructions
presentation/    final AI4LS deck, script, historical check-ins, and design guide
data/            small references plus ignored public/generated data
checkpoints/     ignored local weights
backups/         ignored checksum-bound recovery bundles
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

Large datasets and model weights are deliberately excluded from Git. Follow
[`docs/recovery-and-data.md`](docs/recovery-and-data.md) before running an experiment
or retiring a machine.

## Final presentation

- [HTML deck](presentation/2026-08-17-ai4ls-final.html)
- [PDF deck](presentation/2026-08-17-ai4ls-final.pdf)
- [speaking script](docs/2026-08-17-ai4ls-speaking-script.md)
- [presentation index](presentation/README.md)

## Provenance

This standalone repository continues work developed in the `sp26_nasa` team
repository, derived from Walter Alvarado's `bridge-rna` work. The former long-form
operational history is preserved in Git history and in the ignored pre-cleanup
snapshot under `backups/project-closeout-2026-08-17/`.
