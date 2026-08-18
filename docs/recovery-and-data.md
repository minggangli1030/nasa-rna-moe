# Recovery and public-data reconstruction

**Closeout date:** 2026-08-17
**Purpose:** restore the project after the Jetstream VMs or local generated data are
gone

## Recovery tiers

The project is intentionally split into three tiers:

1. **Git-tracked source and evidence:** code, tests, protocols, small reports,
   manifests, checksums, documentation, and presentation files.
2. **Ignored recovery bundles:** final model weights, compact VM outputs, Git bundles,
   and pre-cleanup snapshots under `backups/`.
3. **Publicly rebuildable data:** ARCHS4, GTEx, OSDR, Ensembl, and GENCODE expression
   or reference files. These are not duplicated in the final backup.

## Closeout backup inventory

The verified primary VM was `moe-reboot` at `149.165.155.21`. The local closeout copy
is:

```text
backups/jetstream-final/2026-08-17/
  moe-reboot-home/            complete 382 MB VM home repository, including .git
  moe-reboot-volume/          six verified Git bundles plus frozen small inputs
  moe-reboot-results-small/   all 4,384 result files smaller than 100 MB
  moe-reboot-results/         complete final_k8_package_dc562cc
```

The compact-results copy is about 1.3 GB; the final package is about 462 MB. The six
Git bundles all pass `git bundle verify`, the copied VM repository passes `git fsck`,
and the final package passes its full SHA-256 ledger.

The historical checksum-bound local bundles below also passed complete verification:

```text
backups/stage1_gtex_to_archs4_training_98e2cba/
backups/stage1_organ_k_confirmation_53ec6c4/
backups/stage1_k4_final_refit_e8c0383/
```

Two older aliases were not accessed because their SSH host keys changed:

| Alias | Last configured IP | Closeout state |
| --- | --- | --- |
| `moe-reboot2` | `149.165.169.55` | Host key changed; connection refused without bypass. |
| `moe-reboot-partial` | `149.165.159.5` | Host key changed; connection refused without bypass. |

Do not remove the old known-host entries or accept the new fingerprints unless
Jetstream independently confirms that these IPs still belong to this project.

## Restore source or a historical VM worktree

Normal source restoration:

```bash
git clone git@github.com:minggangli1030/nasa-rna-moe.git
cd nasa-rna-moe
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Restore a historical Git bundle when an exact VM lineage is needed:

```bash
git clone backups/jetstream-final/2026-08-17/moe-reboot-volume/git-bundles/nasa-rna-moe-gtex-b9a15f2.bundle restored-b9a15f2
```

Restore and verify the final model package:

```bash
cd backups/jetstream-final/2026-08-17/moe-reboot-results/final_k8_package_dc562cc
shasum -a 256 --status -c FULL_SHA256SUMS
```

## Rebuild public reference files

The repository retains the small canonical gene, ortholog, ontology, and exon-length
files required by the frozen workflows. To rebuild Ensembl-derived references:

```bash
python preprocessing/fetch_reference_data.py
python preprocessing/compute_shared_canonical.py
```

`fetch_reference_data.py` queries the Ensembl BioMart service and can also accept
precomputed human exon-length and protein-coding files. Frozen reference hashes remain
in the relevant protocols and checksum ledgers.

## Rebuild ARCHS4 data

### Current human ARCHS4 release

The future untouched-confirmation contract points to:

```text
https://s3.k8s.maayanlab.cloud/archs4/files/human_gene_v2.latest.h5
```

At the metadata-scout freeze, the expected content length was 62,257,385,524 bytes,
ETag `"86ec41d970158f18d065bb9f89248ce5-928"`, and last-modified time
`Tue, 07 Jul 2026 08:43:19 GMT`. Verify current metadata against the frozen contract
before using a later object.

Metadata can be exported without downloading the full matrix:

```bash
python preprocessing/export_archs4_remote_sample_metadata.py \
  --human-h5-url https://s3.k8s.maayanlab.cloud/archs4/files/human_gene_v2.latest.h5 \
  --output data/archs4/current_metadata.parquet \
  --report data/archs4/current_metadata_report.json
```

The exact untouched Track A membership and QC contract live under
`artifacts/final_evaluation/track_a_confirmation_v1/`. Use that contract rather than
reselecting studies from current metadata.

### Historical ARCHS4 v11 matrices

The Stage 0 preprocessing code expects:

```text
data/archs4/human_matrix_v11.h5
data/archs4/mouse_matrix_v11.h5
```

The public S3 object keys are:

```text
mssm-seq-matrix/human_matrix_v11.h5
mssm-seq-matrix/mouse_matrix_v11.h5
```

The preprocessing module can stream them through `s3fs`, but random sampling is much
faster after downloading the H5 files locally. Once present:

```bash
bash runs/preprocess_5k_v2.sh
bash runs/preprocess_20k_v3.sh
```

These scripts apply the shared 15,448-gene vocabulary, TPM normalization, `log1p`
model space, the 14,000-nonzero-gene QC rule, fixed seeds, and the frozen holdout
exclusions. They then merge each variant into
`data/archs4/<variant>_merged/expression.parquet`.

## Rebuild GTEx V11 data

The exact public source contract is
`artifacts/stage1_k4_gtex_intake/protocol.json`. Important URLs include:

```text
Sample attributes:
https://storage.googleapis.com/adult-gtex/annotations/v11/metadata-files/GTEx_Analysis_v11_Annotations_SampleAttributesDS.txt

Gene counts:
https://storage.googleapis.com/adult-gtex/bulk-gex/v11/rna-seq/GTEx_Analysis_2026-05-19_v11_RNASeQCv2.4.3_gene_reads.gct.gz

GENCODE 47:
https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_47/gencode.v47.annotation.gtf.gz

GENCODE 49:
https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_49/gencode.v49.annotation.gtf.gz
```

The frozen counts SHA-256 is
`8b254fc3f58f2e749986887b42c1d65523986728e6eadd95924d907692351242`.
The sample-attributes SHA-256 is
`98c246b3855edf62cb050982a7ca50f3069d010624baea47ef84a9465900ca4b`.

Do not substitute portal TPM for the frozen counts workflow. The project aggregates
counts to canonical symbols, computes TPM using the frozen exon-length table, and
applies `log1p` exactly once. The authoritative cohort, mapping, overlap, and
normalization rules are in:

- `artifacts/stage1_k4_gtex_intake/protocol.json`
- `artifacts/stage1_k4_gtex_evaluation/protocol.json`
- `docs/gtex-to-archs4-training-plan.md`
- `runs/run_gtex_to_archs4_training.sh`

## Rebuild OSDR data

OSDR counts are public and are downloaded through the NASA file-listing API by
`evaluation/evaluate_osdr.py`. The repository keeps the structured metadata and
human/mouse ortholog map required to reconstruct the frozen cohort.

The downloader resolves each `OSD-<number>` through:

```text
https://osdr.nasa.gov/osdr/data/osd/files/<number>
```

A typical rebuild starts with:

```bash
python evaluation/evaluate_osdr.py \
  --checkpoints checkpoints/human_5k_v2/best_model.pt \
  --metadata-csv data/osdr/metadata_new.csv \
  --output-dir results/osdr-rebuild
```

For the final downstream claim, use the frozen cohort and evaluator contract under
`artifacts/final_evaluation/stage1_osdr_downstream/` and the exact report under
`artifacts/final_evaluation/stage1_osdr_downstream_evaluation_61766ee/` rather than
creating a new favorable subset.

## What was intentionally not backed up

The 169 GB persistent volume was not copied byte for byte. Excluded categories are:

- public ARCHS4 and GTEx expression matrices;
- generated preprocessing outputs that can be recreated from public sources;
- repeated prediction caches and scratch arrays;
- obsolete smoke-run weights;
- duplicate worktrees; and
- superseded intermediate checkpoints already represented by final packages or Git
  bundles.

The final scientific reports, protocols, logs, manifests, compact outputs, model
package, and code histories were preserved. This is sufficient to audit the claims
and restart the declared future work without retaining publicly downloadable data.

## Remaining backup risk

`backups/` and the presentation recording are local and intentionally excluded from
normal Git history because of size. Before the laptop is retired, copy both to one
independent storage location and verify their SHA-256 ledgers. A Git remote alone is
not a complete backup of this project.
