# Storage, GitHub backup, and recovery policy

## Source of truth

GitHub repository `minggangli1030/nasa-rna-moe` is the source of truth for code, tests,
protocols, reports, meeting notes, plans, manifests, checksums, compact tables, and final
figures.

Recovery points created during the September 15 reorganization:

| Commit | Purpose |
| --- | --- |
| `c4d348f` | Summer/Fall repository split |
| `6012dcb` | Complete Fall work through run 08 before cleanup |

The active branch intentionally omits bulky raw downloads, copied upstream repositories,
model caches, and reproducible intermediate arrays. The full pre-cleanup files can be
recovered from GitHub without keeping them in the current working tree:

```bash
git restore --source 6012dcb -- path/to/file-or-directory
```

## Keep in the active Git tree

- source code and tests;
- meeting notes, project log, roadmap, and decisions;
- protocols, manifests, provenance, checksums, and completion markers;
- final reports, review notes, compact summary tables, and figures;
- small metadata needed to audit sample membership or reproduce selection.

## Keep locally only while actively needed

- the ignored `fa26/bridge-rna-latest/` checkpoint and reference cache;
- an active run's temporary arrays, embeddings, fitted heads, and downloaded matrices;
- the Summer final recovery bundle until it has an independently verified artifact-store copy.

These files are not ordinary GitHub content. Do not commit model weights or large public
expression matrices to Git merely to use GitHub as object storage.

## Safe to remove after verification

- public GEO/OSDR/ARCHS4/GTEx downloads with a pinned accession or object contract;
- copied upstream source trees whose commit is recorded;
- `__pycache__`, `.pytest_cache`, `.DS_Store`, logs that duplicate a reviewed execution
  record, and superseded document copies already in Git history;
- reproducible `inputs.npz`, `embeddings.npz`, fitted-head caches, and similar intermediates
  after their protocol, manifest, summaries, and snapshot commit are available remotely.

## ARCHS4 cleanup record

The removed local file was:

```text
su26/data/archs4/current/human_gene_v2.latest.h5
```

The remote object was verified immediately before deletion:

```text
URL: https://s3.k8s.maayanlab.cloud/archs4/files/human_gene_v2.latest.h5
Content-Length: 62,257,385,524 bytes
ETag: "86ec41d970158f18d065bb9f89248ce5-928"
Last-Modified: Tue, 07 Jul 2026 08:43:19 GMT
```

These values match [`../../su26/docs/recovery-and-data.md`](../../su26/docs/recovery-and-data.md).

## Summer assets that remain local

The `su26/checkpoints/` and `su26/backups/` directories are ignored by Git. They are retained
only because they include model/recovery material not yet verified in a durable remote
artifact store. They are not represented by ordinary GitHub commits. Before deleting them,
upload the required final package and checksum ledger to an appropriate remote artifact
store, download or remotely hash-verify it, and update the Summer recovery document.

## End-of-run checklist

1. Freeze protocol and source manifest before execution.
2. Write report and compact summaries after review.
3. Update project log, status, and roadmap.
4. Run tests and link checks.
5. Commit and push to GitHub.
6. Verify the remote commit exists.
7. Remove only inputs/intermediates covered by a public source contract or remote snapshot.

