# nasa-rna-moe — Progress Log

## Workflow

- **Local (Mac)**: `/Users/minggangli/Workspace/nasa-rna-moe` — edit code, commit, push.
- **VM (Jetstream, `moe-reboot`)**: `~/nasa-rna-moe` — `git pull`, then run (data/checkpoints/results live here or on the attached volume, never committed).
- Both sides push/pull over SSH using the same GitHub account (`minggangli1030`); Mac already had a working deploy key, VM got a fresh one added at github.com/settings/keys.
- Round-trip verified 2026-07-08: this file was written locally, pushed from the Mac, and pulled on the VM in the same session.

## 2026-07-08 — VM bring-up + repo split-off

- Jetstream VM `moe-reboot` created: `g3.xl` (32 CPU, 117GB RAM, full A100-SXM4-40GB, driver 595.71.05 / CUDA 13.2), Ubuntu 22.04.5, 60GB root disk.
- Confirmed GPU visible via `nvidia-smi`; confirmed reachable from PyTorch (`torch 2.6.0+cu124`, `torch.cuda.is_available() == True`, `NVIDIA A100-SXM4-40GB`).
- Python env: `~/moe-env` (venv, python3.10) — deliberately one consolidated env, replacing the old repo's split `nasa` / `bridge-rna` conda envs (see migration survey — that split was missing real dependencies on both sides).
- Split this work out of the team `sp26_nasa` monorepo into a new standalone private repo: `github.com/minggangli1030/nasa-rna-moe` (clean single commit, no history carried over — full history still lives in `sp26_nasa/bridge-rna-moe` if ever needed).
- Copied OSDR reference files into the new repo's expected layout:
  - `data/osdr/human_mouse_orthologs.csv`
  - `data/osdr/metadata_new.csv` (converted from `sp26_nasa/osdr_data/selected_sample_metadata.tsv`, 2,896 samples)
  - This incidentally fixes the old sibling-directory path bug in `evaluate_osdr.py` (previously assumed `bridge-rna-moe` and `sp26_nasa` sat as sibling directories on Savio scratch; now finds everything locally under `data/osdr/`).
- Ran `fetch_reference_data.py` against Ensembl BioMart to build:
  - `data/ensembl/orthologs_one2one.txt`
  - `data/ensembl/protein_coding_ortholog_genes.txt` (copied from `sp26_nasa/archs4_preprocessing_demo/`)
  - `data/gencode/gencode_v49_gene_exon_lengths.csv`
  - `data/gencode/gencode_v49_mouse_gene_exon_lengths.csv`

## Scope decisions

- Only `bridge-rna-moe/` migrated (as `nasa-rna-moe`) — not the rest of the `sp26_nasa` monorepo (`archs4_preprocessing/`, `binformer/`, `walts_code_savio/`, `outdated/` left behind; full rationale in the earlier migration-survey artifact).
- Rebuilding 5k-scale data fresh via S3 streaming rather than pulling from Savio scratch (no reachable Savio access from this VM).

## Next up

- [ ] Persistent Cinder volume for growing data (ARCHS4 parquet, checkpoints, results), decoupled from instance lifecycle
- [ ] Build 5k-scale ARCHS4 parquet (human / mouse / mixed) via S3 streaming, shared canonical vocab
- [ ] Train `human_5k_v2` / `mouse_5k_v2` / `mixed_5k_v2` experts fresh on the A100
- [ ] Run `check_alignment.py` + `analyze_moe_headroom.py` on the v2 experts
- [ ] Time permitting: zero-shot OSDR eval, and/or MoE gate training if headroom justifies it
