# nasa-rna-moe — Progress Log

## Workflow

- **Local (Mac)**: `/Users/minggangli/Projects/nasa-rna-moe` — edit code, commit, push. (Note: this directory was `~/Workspace/...` earlier the same day; the user renamed `Workspace` → `Projects`. Same repo, just a renamed parent folder.)
- **VM (Jetstream, `moe-reboot`)**: `~/nasa-rna-moe` — `git pull`, then run (data/checkpoints/results live here or on the attached volume, never committed).
- Both sides push/pull over SSH using the same GitHub account (`minggangli1030`); Mac already had a working deploy key, VM got a fresh one added at github.com/settings/keys.
- Round-trip verified 2026-07-08: `PROGRESS.md` was written locally, pushed from the Mac, and pulled on the VM in the same session.

## 2026-07-08 — VM bring-up + repo split-off

- Jetstream VM `moe-reboot` created: `g3.xl` (32 CPU, 117GB RAM, full A100-SXM4-40GB, driver 595.71.05 / CUDA 13.2), Ubuntu 22.04.5, 60GB root disk.
- Confirmed GPU visible via `nvidia-smi`; confirmed reachable from PyTorch (`torch 2.6.0+cu124`, `torch.cuda.is_available() == True`, `NVIDIA A100-SXM4-40GB`).
- Python env: `~/moe-env` (venv, python3.10) — deliberately one consolidated env, replacing the old repo's split `nasa` / `bridge-rna` conda envs (see migration survey — that split was missing real dependencies on both sides).
- Split this work out of the team `sp26_nasa` monorepo into a new standalone private repo: `github.com/minggangli1030/nasa-rna-moe` (clean single commit, no history carried over — full history still lives in `sp26_nasa/bridge-rna-moe` if ever needed).
- Copied OSDR reference files into the new repo's expected layout:
  - `data/osdr/human_mouse_orthologs.csv`
  - `data/osdr/metadata_new.csv` (converted from `sp26_nasa/osdr_data/selected_sample_metadata.tsv`, 2,896 samples)
  - This incidentally fixes the old sibling-directory path bug in `evaluate_osdr.py` (previously assumed `bridge-rna-moe` and `sp26_nasa` sat as sibling directories on Savio scratch; now finds everything locally under `data/osdr/`).
- Ran `fetch_reference_data.py` against Ensembl BioMart to build reference gene data. The exon-length queries (mouse + human) hung indefinitely on the public BioMart server — full-genome exon-coordinate queries with no filtering are known-slow there. Worked around by reusing the already-computed `mouse_exon_lengths_df.csv` / `human_exon_lengths_df.csv` tables from the old monorepo (`archs4_preprocessing/`, `archs4_preprocessing_demo/`) instead of re-deriving from BioMart. Only the ortholog query (fast, filtered) and the protein-coding copy actually hit BioMart/disk.
  - `data/ensembl/orthologs_one2one.txt` (BioMart, 17,065 one-to-one pairs)
  - `data/ensembl/protein_coding_ortholog_genes.txt` (copied from `sp26_nasa/archs4_preprocessing_demo/`, 15,734 genes)
  - `data/gencode/gencode_v49_gene_exon_lengths.csv`, `gencode_v49_mouse_gene_exon_lengths.csv` (converted from precomputed monorepo tables, not BioMart)
- **Bug caught and fixed**: the repo's original `.gitignore` blanket-excluded `data/`, which silently dropped the OSDR reference files from the very first commit even though `git push` reported success. Fixed `.gitignore` to keep `data/ensembl/`, `data/gencode/`, `data/osdr/` (small, hard-won reference files) while still excluding `data/osdr/raw/`, `*.parquet`, `*.h5` (large generated/downloaded data). Re-verified with `git status --short` before the next commit that exactly the 4 intended files were staged.

## Scope decisions

- Only `bridge-rna-moe/` migrated (as `nasa-rna-moe`) — not the rest of the `sp26_nasa` monorepo (`archs4_preprocessing/`, `binformer/`, `walts_code_savio/`, `outdated/` left behind; full rationale in the earlier migration-survey artifact). `sp26_nasa` was kept locally just long enough to source the handful of reference files above; nothing else in it is a live dependency of this repo (verified by grep before removing it locally).
- Rebuilding 5k-scale data fresh rather than pulling from Savio scratch (no reachable Savio access from this VM).

## 2026-07-08 — Persistent volume + hit a wall on S3 streaming, pivoted to local .h5

- Attached a 200GB Cinder volume (`moe-reboot`) to the instance, auto-formatted/mounted by Exosphere at `/media/volume/moe-reboot`. Symlinked the 3 directories that actually grow onto it: `data/archs4`, `checkpoints`, `checkpoints_moe`, `results` (small git-tracked reference data under `data/ensembl`, `data/gencode`, `data/osdr` stays on the 60GB root disk). Hit a `chown` snag first — `sudo mkdir -p` had left the volume's subdirectories owned by `root`, silently breaking `curl`'s write with "Permission denied" later; fixed with `chown -R exouser:exouser`.
- Ran `compute_shared_canonical.py` locally to build `data/ensembl/canonical_genes_shared.txt` — **15,448 genes**, not the 15,581 the original v1→v2 migration report cited. Expected drift, not a bug: it's the intersection of freshly-refetched `orthologs_one2one.txt` (BioMart data can shift between fetches) with the older committed exon-length/protein-coding tables. Internal consistency across the 3 new variants is what matters, not matching the old number exactly.
- Started `preprocessing.py --species human --max-samples 5000 ...` using its S3-streaming fallback (no local ARCHS4 `.h5` present) — **it stalled for 15+ minutes on the very first batch.** Diagnosed live rather than guessing:
  - `/proc/net/dev` RX-byte delta showed the process was moving bytes, just at ~1.5KB/s — not dead, just crawling.
  - A clean 10MB ranged `curl` straight against the S3 bucket got 16.7MB/s — so raw bandwidth was fine, the bottleneck was specific to the streaming code path.
  - Root cause: `preprocessing.py`'s `_rand_s3()` reads "contiguous windows" of *sorted* random sample indices. With 5,000 samples drawn from 245,658 total, consecutive order-statistics are tens of thousands of columns apart — so each "batch" read actually pulls a huge contiguous slice of the remote matrix to extract a handful of needed columns. Summed across all windows this approaches transferring close to the *entire* file, over the network, once per variant.
  - **Fix**: `human_matrix_v11.h5` / `mouse_matrix_v11.h5` are only ~18GB each (not "100GB+" as the earlier survey guessed — checked via `curl -sI`, real `Content-Length`). Downloading both once (`curl` into `data/archs4/`, on the volume) lets `preprocessing.py` use its local-file path (`archs4py.data.rand()`) instead, which is the same method the original Savio runs used and is dramatically faster for scattered random sampling. Added `archs4py` to `requirements.txt`.
  - Download in progress as of this entry (`tmux` session `download`, ~18-20 min/file expected at measured throughput).

## 2026-07-08 — Cleanup pass (while data downloads)

- Removed `archive/` (superseded scratch code/early experiments — recoverable via git history if ever needed) and the 17 Savio-specific `scripts/*.sh` + `diff_walt_configs.py` (100% SLURM/`sbatch`-dependent, non-functional off Savio).
- Replaced `scripts/` with 3 plain-bash equivalents of the actual Jetstream workflow, args double-checked against each target script's real `argparse` (not guessed): `preprocess_5k_v2.sh`, `train_5k_v2.sh`, `run_diagnostics.sh` (the latter runs `evaluate_osdr.py` first specifically because it's what builds/caches `data/osdr/osdr_expression.parquet`, which `check_alignment.py` and `analyze_moe_headroom.py` both require via `--osdr-parquet`).
- Removed `prep_osdr_from_kmeng.py` (dead — pointed at a collaborator's inaccessible Savio scratch path, not referenced anywhere else, and superseded by `evaluate_osdr.py`'s own NASA GeneLab download path).
- Simplified `evaluate_osdr.py`'s `_build_ensmusg_to_human_map()` and OSDR-metadata loading — both used to fall back to a sibling `sp26_nasa/` checkout that doesn't exist in this repo's layout; now they just use the local `data/osdr/` files directly (this was the dead-fallback bug flagged in the original migration survey).
- Updated `README.md` and `fetch_reference_data.py`'s docstring to match current reality (standalone repo, Jetstream VM, no more Savio/`sp26_nasa` framing).

## Next up

- [ ] Finish `.h5` download, run `scripts/preprocess_5k_v2.sh` (human / mouse / mixed)
- [ ] Run `scripts/train_5k_v2.sh` — 3 v2 experts fresh on the A100
- [ ] Run `scripts/run_diagnostics.sh` (zero-shot OSDR eval → alignment check → MoE headroom)
- [ ] Build `presentation/` slides for tomorrow's biweekly update, fill in real numbers once diagnostics finish
- [ ] Time permitting: MoE gate training if headroom justifies it
