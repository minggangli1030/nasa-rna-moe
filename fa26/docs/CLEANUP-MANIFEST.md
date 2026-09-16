# September 15 cleanup manifest

The complete pre-cleanup state is preserved in GitHub commit `6012dcb`.

Removed from the active branch:

- repeated `history/` snapshots copied into artifacts and runs;
- copied upstream benchmark source under the BridgeRNA benchmark audit;
- public GEO expression/SOFT downloads used by runs 06–08;
- reproducible input, embedding, attribution, readout, and fitted-head intermediates;
- Python/test caches and macOS metadata;
- the 58 GB local ARCHS4 matrix after exact remote-object verification.

Retained in the active branch:

- all canonical code and tests;
- protocols, manifests, provenance, checksums, and completion/status markers;
- reports, reviews, final figures, and compact result tables;
- meeting notes, chronological log, and future roadmap;
- small sample/source metadata required to interpret study membership.

Retained locally but ignored by Git:

- the active Fall BridgeRNA model/reference cache;
- Summer checkpoint and recovery bundles that do not yet have a separately verified durable
  artifact-store copy.

Use [`STORAGE-AND-RECOVERY.md`](STORAGE-AND-RECOVERY.md) for restoration commands and the
rules governing any additional deletion.

