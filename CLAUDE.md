# nasa-rna-moe

Mixture-of-Experts exploration for spaceflight transcriptomic classification — SLiMPerformer-based experts (human / mouse / mixed ARCHS4 pretraining), evaluated zero-shot on NASA OSDR. Personal continuation of work from the `sp26_nasa` team monorepo; see the Provenance note near the bottom.

This file is both **instructions for working in this repo** and a **running log** of what's been done, in chronological order (newest at the bottom). Read the orientation section below first if you're starting cold; the log below that has the reasoning behind non-obvious decisions.

## Repository structure

```text
.
├── preprocessing/              # Stage 1: raw ARCHS4/OSDR -> canonical-vocab parquet
│   ├── preprocessing.py         #   ARCHS4 sampling + QC + TPM + ortholog alignment
│   ├── merge.py                 #   batch parquet -> single expression.parquet
│   ├── compute_shared_canonical.py  # builds data/ensembl/canonical_genes_shared.txt
│   └── fetch_reference_data.py  #   Ensembl BioMart -> data/ensembl, data/gencode
│
├── core/                        # Stage 2: model + training (everything else imports from here)
│   ├── slim_performer_model.py  #   SLiMPerformer layer (Google Research, vendored)
│   ├── numerator_and_denominator.py  # prefix-sum attention internals
│   ├── train_single.py          #   single-expert DDP training, VARIANT_CONFIGS
│   └── train_moe.py             #   frozen-expert gate training
│
├── evaluation/                  # Stage 3: diagnostics and zero-shot eval
│   ├── evaluate_osdr.py         #   zero-shot OSDR eval; also builds the OSDR parquet cache
│   ├── evaluate_osdr_moe.py     #   same, for a trained MoE gate
│   ├── check_alignment.py       #   gene-mean-collapse / baseline-comparison diagnostic
│   ├── check_moe_gene_counts.py #   expert-vocabulary mismatch diagnostic
│   ├── analyze_moe_headroom.py  #   training-free oracle-vs-best-expert headroom check
│   ├── build_mixed_eval.py      #   mixed OSDR+TCGA eval set
│   └── prep_tcga.py             #   TCGA TPM -> canonical-space parquet
│
├── runs/                        # Stage 4: launcher scripts, one per variant (see below)
│   ├── preprocess_5k_v2.sh
│   ├── train_human_5k_v2.sh
│   ├── train_mouse_5k_v2.sh
│   ├── train_mixed_5k_v2.sh
│   └── run_diagnostics.sh
│
├── data/
│   ├── ensembl/, gencode/, osdr/   # small reference files, git-tracked
│   └── archs4/                     # generated parquet + raw .h5 (gitignored)
├── checkpoints/, checkpoints_moe/, results/   # gitignored, symlinked to a volume on the VM
├── checkpoints_performer/       # lightweight v1 sweep run metadata (tracked, no weights)
├── configs/, examples/, presentation/
```

**Import note**: `evaluation/evaluate_osdr.py` and `evaluation/evaluate_osdr_moe.py` are the only files that import across stage folders (they need `core/`); both do it via an explicit `sys.path.insert(0, ... / "core")` right before the import. Every other cross-file import is same-directory and needs no path tricks. If you add a new file that needs something from `core/`, copy that same pattern rather than restructuring into a formal package — it's been verified working and keeping it minimal avoids re-breaking the diagnostics scripts this repo depends on.

All launcher scripts `cd` to repo root first, so run them from anywhere: `runs/train_mouse_5k_v2.sh` works the same as `cd runs && ./train_mouse_5k_v2.sh`.

## Workflow

- **Local (Mac)**: `/Users/minggangli/Projects/nasa-rna-moe` — edit code, commit, push.
- **VM(s) (Jetstream)**: `~/nasa-rna-moe` on each instance — `git pull` (or direct file copy, see below), then run.
- Both sides push/pull over SSH using the same GitHub account (`minggangli1030`).
- **This sprint runs 3 GPU instances in parallel**, one variant each (see the 2026-07-09 log entry for why). SSH aliases are set up on the Mac (`~/.ssh/config`): `ssh moe-reboot`, `ssh moe-reboot2`, `ssh moe-reboot-partial`. Only `moe-reboot` was ever `git clone`d — the other two got their code via `rsync`/`scp` from the Mac (no `.git` history there), so **use `scp`/`rsync` to push updates to them, not `git pull`**.
- Data/checkpoints/results live under a volume mount or the VM's own disk, never committed — `data/archs4`, `checkpoints/`, `checkpoints_moe/`, `results/` are all gitignored.

## Progress Log

### 2026-07-08 — VM bring-up + repo split-off

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

### Scope decisions

- Only `bridge-rna-moe/` migrated (as `nasa-rna-moe`) — not the rest of the `sp26_nasa` monorepo (`archs4_preprocessing/`, `binformer/`, `walts_code_savio/`, `outdated/` left behind; full rationale in the earlier migration-survey artifact). `sp26_nasa` was kept locally just long enough to source the handful of reference files above; nothing else in it is a live dependency of this repo (verified by grep before removing it locally).
- Rebuilding 5k-scale data fresh rather than pulling from Savio scratch (no reachable Savio access from this VM).

### 2026-07-08 — Persistent volume + hit a wall on S3 streaming, pivoted to local .h5

- Attached a 200GB Cinder volume (`moe-reboot`) to the instance, auto-formatted/mounted by Exosphere at `/media/volume/moe-reboot`. Symlinked the 3 directories that actually grow onto it: `data/archs4`, `checkpoints`, `checkpoints_moe`, `results` (small git-tracked reference data under `data/ensembl`, `data/gencode`, `data/osdr` stays on the 60GB root disk). Hit a `chown` snag first — `sudo mkdir -p` had left the volume's subdirectories owned by `root`, silently breaking `curl`'s write with "Permission denied" later; fixed with `chown -R exouser:exouser`.
- Ran `compute_shared_canonical.py` locally to build `data/ensembl/canonical_genes_shared.txt` — **15,448 genes**, not the 15,581 the original v1→v2 migration report cited. Expected drift, not a bug: it's the intersection of freshly-refetched `orthologs_one2one.txt` (BioMart data can shift between fetches) with the older committed exon-length/protein-coding tables. Internal consistency across the 3 new variants is what matters, not matching the old number exactly.
- Started `preprocessing.py --species human --max-samples 5000 ...` using its S3-streaming fallback (no local ARCHS4 `.h5` present) — **it stalled for 15+ minutes on the very first batch.** Diagnosed live rather than guessing:
  - `/proc/net/dev` RX-byte delta showed the process was moving bytes, just at ~1.5KB/s — not dead, just crawling.
  - A clean 10MB ranged `curl` straight against the S3 bucket got 16.7MB/s — so raw bandwidth was fine, the bottleneck was specific to the streaming code path.
  - Root cause: `preprocessing.py`'s `_rand_s3()` reads "contiguous windows" of *sorted* random sample indices. With 5,000 samples drawn from 245,658 total, consecutive order-statistics are tens of thousands of columns apart — so each "batch" read actually pulls a huge contiguous slice of the remote matrix to extract a handful of needed columns. Summed across all windows this approaches transferring close to the *entire* file, over the network, once per variant.
  - **Fix**: `human_matrix_v11.h5` / `mouse_matrix_v11.h5` are only ~18GB each (not "100GB+" as the earlier survey guessed — checked via `curl -sI`, real `Content-Length`). Downloading both once (`curl` into `data/archs4/`, on the volume) lets `preprocessing.py` use its local-file path (`archs4py.data.rand()`) instead, which is the same method the original Savio runs used and is dramatically faster for scattered random sampling. Added `archs4py` to `requirements.txt`.
  - Download in progress as of this entry (`tmux` session `download`, ~18-20 min/file expected at measured throughput).

### 2026-07-08 — Cleanup pass (while data downloads)

- Removed `archive/` (superseded scratch code/early experiments — recoverable via git history if ever needed) and the 17 Savio-specific `scripts/*.sh` + `diff_walt_configs.py` (100% SLURM/`sbatch`-dependent, non-functional off Savio).
- Replaced `scripts/` with 3 plain-bash equivalents of the actual Jetstream workflow, args double-checked against each target script's real `argparse` (not guessed): `preprocess_5k_v2.sh`, `train_5k_v2.sh`, `run_diagnostics.sh` (the latter runs `evaluate_osdr.py` first specifically because it's what builds/caches `data/osdr/osdr_expression.parquet`, which `check_alignment.py` and `analyze_moe_headroom.py` both require via `--osdr-parquet`). **Note**: `scripts/` was later replaced again by `runs/` on 2026-07-09 (see below) — this entry is kept for historical accuracy.
- Removed `prep_osdr_from_kmeng.py` (dead — pointed at a collaborator's inaccessible Savio scratch path, not referenced anywhere else, and superseded by `evaluate_osdr.py`'s own NASA GeneLab download path).
- Simplified `evaluate_osdr.py`'s `_build_ensmusg_to_human_map()` and OSDR-metadata loading — both used to fall back to a sibling `sp26_nasa/` checkout that doesn't exist in this repo's layout; now they just use the local `data/osdr/` files directly (this was the dead-fallback bug flagged in the original migration survey).
- Updated `README.md` and `fetch_reference_data.py`'s docstring to match current reality (standalone repo, Jetstream VM, no more Savio/`sp26_nasa` framing).
- Confirmed (grep across all file types, not just code) that nothing in `nasa-rna-moe` still depends on the local `sp26_nasa` checkout, then deleted it from the Mac (`/Users/minggangli/Projects/sp26_nasa`). It's untouched on GitHub if ever needed again. **Not yet done**: the VM still has its own `~/sp26_nasa` sparse checkout (used to source `archs4_preprocessing_demo/protein_coding_ortholog_genes.txt` and the original OSDR files, both already committed into `nasa-rna-moe` now) — safe to `rm -rf ~/sp26_nasa` there too whenever convenient, not urgent.
- Added `presentation/2026-07-09-biweekly.html` — a self-contained (no external assets) scroll-snap slide deck for tomorrow's biweekly update. Slides 1-5 are ready (recap, v1 findings, the vocab-fix rationale, infra migration story). Slides 6-7 have real v1 numbers for context but the v2 results are explicit `PENDING` placeholders — **must be filled in with real numbers from diagnostics before presenting**.

### 2026-07-09 — .h5 download confirmed, preprocessing done in under 2 minutes

- `data/archs4/human_matrix_v11.h5` (17G) and `mouse_matrix_v11.h5` (18G) both landed intact (`ls -lh` matches the `Content-Length` check from the day before, just GiB- vs byte-rounding).
- Ran `scripts/preprocess_5k_v2.sh`: all three v2 5k variants (human/mouse/mixed) built successfully. The local-`.h5` fix fully paid off — this took **under 2 minutes total** for all three, versus 15+ minutes stalled on a single batch of one variant via S3 streaming the day before.
  - `mixed_5k_v2`: 2,146 human + 2,107 mouse = 4,253 samples × 15,448 canonical genes.
  - Confirms the earlier diagnosis was right: the S3-streaming path wasn't a fluke slowdown, it was structurally reading close to the entire remote file every time.
- Also revised `presentation/2026-07-09-biweekly.html` per feedback: added 5 SVG figures (results bar chart, collapse-vs-baseline chart, MoE architecture diagram, headroom dumbbell chart, ARCHS4-vs-OSDR stat pair), switched to horizontal scroll-snap navigation with keyboard/wheel support, and bumped body text to 16pt. Background section restructured so slides 5-8 center my own diagnostic work (OSDR eval, collapse check, MoE gate, headroom analysis) rather than reiterating the team poster — teammates get a brief, explicit credit instead of being the focus.

### 2026-07-09 — Training was ~42h ETA, root-caused and fixed to a fraction of that

- First real training ticker (`human_5k_v2`, epoch 1) reported a steady **5.12s/batch**, which the script's own ETA math projected to **~42 hours** for all three variants at 30 epochs each — completely unworkable for tomorrow.
- Root-caused rather than guessed: `CONFIG["compute_type"] = "iter"` computes the model's prefix-sum linear attention via a **Python-level loop over 64-position chunks** (`numerator_and_denominator.py`, `_ITER_CHUNK_SIZE`). For a 15,448-gene sequence that's ~242 sequential chunk iterations per layer per forward+backward pass — dominated by Python/kernel-launch overhead, not actual GPU FLOPs. `batch_size=4` showed the same fingerprint: both values trace back to a comment elsewhere in the codebase noting SLiMPerformer OOMs on an **11GB 1080 Ti** at this gene count — a constraint that doesn't apply to a 40GB A100 at all.
- Fix (mathematically identical output — same prefix-sum math, computed in fewer/larger chunks, not an approximation):
  - `_ITER_CHUNK_SIZE`: 64 → 1024 (16× fewer loop iterations; ~1.2GB per chunk even at the larger batch size below, well within 40GB)
  - `batch_size`: 4 → 16 (4× fewer batches/epoch: 1000 → 250)
  - Deliberately did **not** switch `compute_type` to `"ps"` (a different single-shot implementation) — that materializes a much larger tensor at once with a less predictable memory footprint; the chunk-size bump gets most of the same win with bounded, safer memory.
- **Caveat, noted honestly**: bumping batch size without also scaling the learning rate is a known simplification (linear-scaling-rule purists would bump LR too). Not doing that now — priority is a valid v2 result by tomorrow, not a fully hyperparameter-tuned one. Worth revisiting if training continues past this sprint.
- **First restart OOM'd**: `chunk_size=1024` and `batch_size=16` together (16×4=64× the original transient tensor size, not a modest bump) exceeded 40GB during backward — `torch.OutOfMemoryError` trying to allocate 4.50GiB with only 873MB free, ~32GB already held by activations/optimizer state/allocator fragmentation. The mistake: scaling chunk size and batch size simultaneously without doing the multiplicative memory arithmetic first.
- **Corrected**: `_ITER_CHUNK_SIZE` → 512 (was 1024), `batch_size` → 8 (was 16) — a 4× smaller transient tensor than the OOM'd config, while still 8× fewer loop iterations and 2× fewer batches/epoch than the original tiny config. Also added `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`, PyTorch's own suggested fix for the allocator-fragmentation part of the error (this later turned out to be incompatible with vGPU instances — see below).
- Switched off `WANDB_MODE=offline` on `moe-reboot` — logged into W&B properly for live run tracking instead.

### 2026-07-09 — Went from 1 GPU to 3, parallelizing the remaining two variants

- Quota reality check: allocation is 2 A100s total (not unlimited) — `moe-reboot` already counted as 1, so only **one** more full A100 (`moe-reboot2`) was available, plus a separate partial-GPU quota bucket (**1** more, a vGPU slice).
- Reassigned the plan: `human_5k_v2` stays on `moe-reboot` (uncapped, already progressing, not worth interrupting). `mouse_5k_v2` → `moe-reboot2` (full A100). `mixed_5k_v2` → new instance `moe-reboot-partial` (vGPU partition, 20GB).
- **Set up direct SSH from the Mac to all instances** (bypassing the Exosphere web shell) — added the Mac's existing key to each instance's `authorized_keys`, configured `~/.ssh/config` aliases (`moe-reboot`, `moe-reboot2`, `moe-reboot-partial`). From here on, driving setup and training launches directly via SSH rather than relaying commands for manual execution — user explicitly opted into this given the time pressure and round-trip friction of copy-pasting terminal output all night.
- Transferred already-preprocessed data (merged parquet, ~280-290MB per variant) directly instance-to-instance via piped `tar` through the SSH relay, instead of re-downloading raw `.h5` files (18-36GB) on each new instance — avoided ~35-40 min of redundant download per instance.
- **Epoch-budget asymmetry caught and fixed**: the original 12-epoch cap on mouse/mixed was a conservative estimate that turned out to leave real slack (12 epochs only needed 6h45m of the 16h budget once actual throughput was measured) — but it meant mouse/mixed would train for meaningfully fewer epochs than `human_5k_v2`'s uncapped 30, confounding the three-way comparison the whole point of this sprint is to make. Raised the cap to **20 epochs** for both (~11.4h at measured throughput, still real margin under 16h).
- **New bug found and fixed**: `moe-reboot-partial`'s vGPU (`GRID A100X-20C`, an NVIDIA virtualized/partitioned A100, 20GB) failed with `CUDA driver error: operation not supported` on `dist.init_process_group(backend="nccl")` — even in single-process mode. Root-caused by bisection rather than guessing:
  1. Tried `NCCL_P2P_DISABLE=1`/`NCCL_SHM_DISABLE=1`/`NCCL_IB_DISABLE=1` — still failed, now inside NCCL's object-broadcast tensor serialization.
  2. Switched `backend="nccl"` → `"gloo"` (made configurable via a new `DDP_BACKEND` env var, defaults to `nccl` — zero behavior change for `moe-reboot`/`moe-reboot2`) — got further, but then failed on a plain `model.to(device)` call. This proved the issue wasn't NCCL-specific at all.
  3. Isolated with a 2-line Python repro: `torch.randn(10,10).to('cuda')` failed with `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` set, succeeded without it. **Root cause: `expandable_segments` uses CUDA's virtual-memory-management driver APIs, which this vGPU partition doesn't expose** — unrelated to the NCCL error's surface symptom, which was a red herring from testing both changes near-simultaneously.
  - Final working config for `moe-reboot-partial`: `DDP_BACKEND=gloo`, no `PYTORCH_CUDA_ALLOC_CONF`. Training stable at 15GB/20GB VRAM, 98% GPU utilization. **If this happens again on another virtualized/vGPU instance, try this combination first.**
- All three instances confirmed training in parallel at consistent throughput (~4.1s/batch across all three, including the vGPU):
  - `moe-reboot`: `human_5k_v2`, uncapped, val loss dropping steadily (0.937→0.919→0.905 through epoch 3)
  - `moe-reboot2`: `mouse_5k_v2`, 20-epoch cap, Run ETA ~11h 24m
  - `moe-reboot-partial`: `mixed_5k_v2`, 20-epoch cap, Run ETA ~11h 24m
- Set up a local background watcher (polls all 3 instances every 10 min via SSH, checks for error patterns and whether both capped runs have finished; 15h safety ceiling regardless) instead of trying to use cloud-scheduled agents — those run in Anthropic's cloud with no access to local SSH keys or these private VM IPs, so they're the wrong tool for monitoring infrastructure only reachable from this Mac. Caught and fixed a bug in the watcher itself before it could false-trigger: `grep -c` returns exit code 1 on zero matches (despite correctly printing "0"), which tripped a local `|| echo 0` fallback and duplicated output, breaking the string comparison used to detect real errors.

### 2026-07-09 — Repo reorganized into stages; PROGRESS.md became this file

- Flat 15-file `.py` layout replaced with stage folders: `preprocessing/`, `core/`, `evaluation/`, `runs/` (see Repository structure above). Used `git mv` throughout to preserve file history.
- Fixed the resulting breakage before committing anything, verified locally (not assumed):
  - 3 files used `Path(__file__).parent / "data"` assuming they lived at repo root (`compute_shared_canonical.py`, `fetch_reference_data.py`, `evaluate_osdr.py` ×4 occurrences) — all bumped to `.parent.parent` now that they're one level deeper.
  - 2 files (`evaluate_osdr.py`, `evaluate_osdr_moe.py`) import across the new folder boundary into `core/` — fixed with an explicit `sys.path.insert(0, ... / "core")` right before the import, rather than a full package restructure (lower risk, smaller diff, and this repo's diagnostics scripts are the one thing that absolutely cannot break before tomorrow).
  - Verified every one of the 15 moved files actually imports cleanly from its new location, including a live check that `evaluate_osdr.BRIDGE_RNA_DATA` resolves to the real `data/` directory and not a phantom `evaluation/data/`.
- Old generic `scripts/train_5k_v2.sh` (looped all 3 variants) and `scripts/train_5k_v2_remaining.sh` (looped 2) replaced with 3 explicit single-variant scripts in `runs/` (`train_human_5k_v2.sh`, `train_mouse_5k_v2.sh`, `train_mixed_5k_v2.sh`) — matches how the 3 variants actually ended up running, one per dedicated instance, and each script documents in a comment which instance it ran on and any instance-specific quirks (e.g. `train_mixed_5k_v2.sh` documents the `DDP_BACKEND=gloo` / no-`expandable_segments` vGPU requirements inline, so a future run on similar hardware doesn't have to rediscover that bisection).
- Also fixed a leftover Savio-era hardcoded path in `configs/sweep_train_single.sh` (pointed at `/global/scratch/users/minggangli/bridge-rna/train_single.py`) — updated to the current repo layout, though flagged as unverified/unused since no W&B sweep has been run this sprint.
- **This reorganization is local-only as of this entry** — none of the 3 running VMs have been touched or resynced, since they're all mid-training from their already-loaded code and don't need anything new until the diagnostics stage. When that time comes, sync the new structure fresh (via `scp`/`rsync` for `moe-reboot2`/`moe-reboot-partial`, `git pull` for `moe-reboot`) rather than trying to patch the old flat layout in place.
- `PROGRESS.md` renamed to this file (`CLAUDE.md`) with an orientation section added on top — same historical log, now also auto-loaded as context for any future Claude Code session in this repo.

## Next up

- [ ] Sync the new repo structure to all 3 VMs before running diagnostics (not before — they're mid-training)
- [ ] Watcher-triggered review: once it fires, check all 3 instances' final results, fill in the presentation's `PENDING` sections with real numbers if they look meaningful, or diagnose+fix if something looks broken
- [ ] Run `runs/run_diagnostics.sh` once all 3 checkpoints are in one place
- [ ] Time permitting: MoE gate training if headroom justifies it

## Provenance

Fork of Walter Alvarado's `bridge-rna` work (UChicago), itself part of a larger team project (`sp26_nasa` — Abraham Guan, Brian Zhou, Karen Meng, Ishanth Hombaiah, Minggang Li; mentor Dr. Walter Alvarado, NASA Ames; Berkeley CDSS Data Discovery program). This repo (`nasa-rna-moe`) is Minggang Li's individual continuation under a SPARC research proposal — the zero-shot OSDR evaluation pipeline, collapse/alignment diagnostics, MoE headroom analysis, and the v2 shared-vocabulary fix are this author's own work built on top of the team's shared pretraining pipeline; see `presentation/2026-07-09-biweekly.html` for the full attribution split.
