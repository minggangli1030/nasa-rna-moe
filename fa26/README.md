# Fall 2026 — BridgeRNA space-biology research

## Current status

Eight numbered spaceflight runs are complete. No local or remote job is running, and no
new run is queued.

The latest tissue-matched check shows that the irradiation-associated probe also responds
to non-radiation electrical stimulation in human muscle and reverses direction between
the two flight studies. In the working flight head, a lower probe component supports the
flight score. This is a model-geometry diagnostic, not a causal radiation fraction.

Use these canonical documents:

- [Project log](docs/PROJECT-LOG.md) — every completed research and maintenance step.
- [Meeting index](docs/MEETINGS.md) — decisions, owners, and open questions.
- [Roadmap](docs/ROADMAP.md) — the next decision and future validation gates.
- [Storage and recovery](docs/STORAGE-AND-RECOVERY.md) — what belongs in GitHub, what is
  reproducible, and what remains local.
- [Spaceflight status](workstreams/spaceflight/STATUS.md) — detailed latest result.
- [Spaceflight plan](workstreams/spaceflight/PLAN.md) — technical plan and interpretation rules.

## Workstreams

| Workstream | Owner | State | Entry point |
| --- | --- | --- | --- |
| Spaceflight prediction and explanation | Minggang | Active; eight runs complete, next hypothesis not selected | [`workstreams/spaceflight/`](workstreams/spaceflight/) |
| Batch/preparation effects | Brain | Separately owned; objective still requires owner confirmation | [`workstreams/batch/`](workstreams/batch/) |
| Human–mouse question | Unassigned | Target and success metric unresolved | [`workstreams/cross_species/`](workstreams/cross_species/) |

## Repository map

```text
fa26/
├── docs/                         canonical log, meetings, roadmap, and recovery
├── workstreams/                  workstream-specific plans, code, and numbered runs
│   └── spaceflight/
│       ├── scripts/              canonical current analysis scripts
│       └── runs/                 run reports, protocols, summaries, and figures
├── artifacts/                    early survey evidence and compatibility targets for runs 01–04
├── tests/                        lightweight contract and robustness tests
├── presentation/                 current discussion deck and speaking notes
└── bridge-rna-latest/            ignored local cache; not a GitHub source directory
```

The root-level links for the first four head scripts and runs are compatibility symlinks.
Their canonical locations are under `workstreams/spaceflight/`; they consume negligible
space and keep historical commands valid.

## Scientific result to carry forward

- Frozen-embedding heads learn within-flight associations but fail unseen-flight transfer.
- Experiment-specific gene attribution is numerically verified, but it is not causal biology.
- A six-program explanation captures only part of the flight-head evidence.
- A narrow IMR90 irradiation transfer result survives strong checks, but specificity across
  other stresses and tissues is inadequate.
- Human-muscle negative controls rule out describing the current flight head as
  radiation-driven.

The next step is a scientific choice, not another automatic run. Follow the gates in the
[roadmap](docs/ROADMAP.md).

## Validation

From the repository root:

```bash
python3 -m pytest -q fa26/tests
```

Large inputs and model files are intentionally excluded. Follow
[`docs/STORAGE-AND-RECOVERY.md`](docs/STORAGE-AND-RECOVERY.md) before restoring or deleting
any of them.
