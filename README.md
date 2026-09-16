# NASA RNA research repository

This repository contains two sequential research phases:

- [`su26/`](su26/) — closed Summer 2026 mixture-of-experts project.
- [`fa26/`](fa26/) — active Fall 2026 BridgeRNA space-biology work.

## Start here

For current work, read the Fall documentation in this order:

1. [`fa26/README.md`](fa26/README.md) — current scientific status and repository map.
2. [`fa26/docs/PROJECT-LOG.md`](fa26/docs/PROJECT-LOG.md) — chronological record of completed steps.
3. [`fa26/docs/MEETINGS.md`](fa26/docs/MEETINGS.md) — meeting decisions, ownership, and unresolved questions.
4. [`fa26/docs/ROADMAP.md`](fa26/docs/ROADMAP.md) — future plan and decision gates.
5. [`fa26/docs/STORAGE-AND-RECOVERY.md`](fa26/docs/STORAGE-AND-RECOVERY.md) — GitHub backup and large-file recovery policy.

The Summer project is complete. Its scientific conclusion and recovery instructions are
in [`su26/docs/project-closeout.md`](su26/docs/project-closeout.md) and
[`su26/docs/recovery-and-data.md`](su26/docs/recovery-and-data.md).

## Current state

As of September 15, 2026, the Fall work has completed eight numbered spaceflight runs.
The latest result is a negative specificity finding: the current irradiation-associated
probe is useful diagnostically but does not support labeling the flight classifier as
radiation-driven. No training, inference, or watcher job is currently running.

## Repository policy

GitHub is the source of truth for code, tests, reports, protocols, compact evidence,
meeting notes, and plans. Public datasets, downloaded upstream repositories, model
weights, caches, and reproducible intermediate arrays stay out of Git and are kept
locally only when needed for active work. Every excluded asset must have a documented
remote source or reconstruction path.

The complete Fall snapshot before the September 15 cleanup is Git commit `6012dcb`.
