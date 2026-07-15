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
- **Always launch training inside a tmux session on the VM, never as a bare command over a direct SSH connection.** A bare launch dies on `SIGHUP` when the launching SSH session detaches (this killed the `mixed`/`human` V3 runs on 2026-07-13, costing ~1.5h). Use `tmux new -s train` (or `tmux attach -t train`), start the run redirected to a logfile, then detach with `Ctrl-b d`.

## Research resources (MCP)

Prior-art / literature / model-search guidance lives in the **global `~/.claude/CLAUDE.md`** now (alphaxiv, hf-mcp-server, github — applies to all projects). Repo-specific angles worth a prior-art check with those tools: MoE routing / gating headroom, frozen-backbone + lightweight-adapter designs (the CodonMoE-style refactor in "Next up"), linear-attention / Performer variants (the SLiMPerformer backbone), OOD generalization in genomic sequence models (the gene-mean-beats-experts gap), and ARCHS4-derived datasets / RNA foundation models on the Hub.

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

### 2026-07-09/10 — All 3 experts finished; diagnostics pipeline had 3 real bugs; built a second, harder eval set

- All three v2 5k experts finished training. Final val losses: `human_5k_v2` **0.429095** (epoch 30/30), `mouse_5k_v2` **0.5188** (20/20, capped), `mixed_5k_v2` **0.8047** (20/20, capped). Caught and killed **two separate leftover-script incidents** where a stale sequential launcher (from the pre-reorg flat layout, before the per-variant `runs/*.sh` split) auto-started a redundant duplicate run right after the real one finished — once on `moe-reboot2` (`mixed_5k_v2` restarting at the old 12-epoch cap) and once on `moe-reboot` (`mouse_5k_v2` restarting at the wrong 30-epoch cap). Both killed before wasting significant compute; neither had touched the real, already-saved `best_model.pt`.
- Ran `runs/run_diagnostics.sh` on `moe-reboot2` and hit **3 real, unrelated bugs in sequence**, each root-caused rather than retried blindly:
  1. **`evaluate_osdr.py`'s OSDR download failed 94/94 studies with 404s.** NASA had migrated GeneLab's file host from static `genelab-data.ndc.nasa.gov` paths (now just 301-redirects) to a JSON file-listing API + presigned-S3 download flow at `osdr.nasa.gov`. Rewrote `download_osdr_study()` to query `https://osdr.nasa.gov/osdr/data/osd/files/{num}` and follow the `remote_url` it returns; verified against a real study (`OSD-100`, 57,186 genes × 12 samples) before rerunning the full pipeline.
  2. **`CANONICAL_GENES_FILE` pointed at the wrong file** — `protein_coding_ortholog_genes.txt` (15,734 genes, a pre-canonicalization intermediate left over from before the v2 shared-vocab fix) instead of the actual `canonical_genes_shared.txt` (15,448 genes) the v2 experts train on. This caused an out-of-bounds `nn.Embedding` lookup (`CUDA error: device-side assert triggered`, `srcIndex < srcSelectDimSize`) once real OSDR data started flowing through. One-line fix; the mismatch had been silently latent since the reorg because nothing had exercised this code path with real data yet.
  3. **`analyze_moe_headroom.py` requires each expert's training-parquet gene order to align to a common space**, which fails when an expert trained on a different VM than the one running diagnostics (`human_5k_v2` trained on `moe-reboot`, diagnostics ran on `moe-reboot2`). Rather than assume this was safe to skip, verified empirically first: pulled `human_5k_v2`'s actual training-parquet schema via a remote schema-only read (no data transfer) and confirmed its gene order matches `canonical_genes_shared.txt` exactly — as it must, since all 3 v2 variants were built via the same `--canonical-genes-file` flag. Added a fallback in `load_checkpoint()` that uses the canonical file when the parquet isn't locally present, gated to `num_genes == 15448` (v2 only) with an explicit warning printed, not a silent assumption.
- **OSDR headroom result** (2,318 mouse spaceflight samples, common 15,448-gene space): best single expert `mouse_5k_v2` (0.7683), oracle per-sample routing only reaches 0.7701 — **headroom = +0.0018**, same tiny order of magnitude as v1's per-species gaps, confirming v1's inflated +0.0199 "global mixed" number was a vocab-alignment artifact, not real signal. A **fixed 30/70 human/mouse blend** beat the best single expert by +0.0084 — 4-5× the oracle gap — despite not being a smart per-sample choice, just averaging.
- User flagged the obvious confound: OSDR is **100% mouse data**, so of course the mouse-trained expert wins — this doesn't actually test cross-species routing. Built a second, genuinely balanced eval set from held-out ARCHS4 data to check:
  - Investigated a real human-spaceflight OSDR eval set first (Option A) — dead end. NASA OSDR does have human RNA-seq studies, but they're all ground-based simulated-microgravity cell-culture experiments (confirmed via the OSDR API: zero human RNA-seq samples have the `study.factor value.spaceflight` field populated), not real astronaut flight data with the same factor structure as the mouse studies.
  - Built Option B instead: added `--seed` and `--exclude-ids-file` flags to `preprocessing.py`. The exact training-sample manifests for `mouse_5k_v2`/`mixed_5k_v2` survived on disk (`samples.json`); `human_5k_v2`'s did not (cleaned up for space), so reproduced it exactly via `reproduce_human_exclusion.py` (same `archs4py.data.rand(seed=42, n=5000)` call the original preprocessing made — deterministic, confirmed by union-with-mixed's-human-IDs landing at exactly 5,000, meaning mixed's human draw was a strict prefix of the same seeded shuffle).
  - Re-downloaded both ~18GB ARCHS4 `.h5` matrices (deleted earlier for disk space) — sequentially, since no instance had 36GB free at once — to draw 331 held-out human + 336 held-out mouse samples (different seed, explicit exclusion of all known training IDs), merged into one 667-sample parquet with a `species` column.
  - **Result, and it's a different finding, not just a confirmation**: headroom is still tiny (+0.0031), but for a new reason — `mixed_5k_v2` (the jointly-trained expert) wins as best-single on **both** species, not just its own. It beats `mouse_5k_v2` even on native mouse samples (0.386 vs 0.304) and beats `human_5k_v2` even on native human samples (0.399 vs 0.147). Joint training produces a more broadly generalizing expert; oracle routing has little to add on top because one expert already dominates everywhere.
  - **Caveat surfaced, not hidden**: the trivial gene-mean baseline (0.686) beats every trained expert (0.14-0.39) on this harder, more heterogeneous ARCHS4 slice — a much larger gap than the ambiguous OSDR baseline comparison (n=68 there vs n=667 here). Reads as a real generalization gap between the narrow 5k-sample training distributions and broader ARCHS4 diversity (different tissues/cell-lines/conditions never seen in training), not a fluke — worth investigating before trusting the experts' zero-shot behavior outside their training distribution.
- **Backup pass**: local `checkpoints/` directory didn't exist — all 3 final checkpoints were only on `moe-reboot2`'s ephemeral root disk (`/dev/sda1` mounted at `/`, not a separate persistent volume, unlike `moe-reboot`'s attached Cinder volume). Pulled all 3 checkpoints + both headroom `report.json`s to the Mac (MD5-verified against the VM copies), and committed+pushed all code changes to GitHub (`f8f8e12`).

### 2026-07-13 — Steps 1 & 2 diagnostics closed the case for scale; launched V3 (20k)

**Reasoning trail (why we're here):**
1. The original OSDR headroom test is **100% mouse spaceflight data** — the mouse-trained expert wins by construction, so it can't actually test cross-species/expert routing. We built a genuinely **balanced held-out set** (331 human + 336 mouse from held-out ARCHS4) for an honest test.
2. On that balanced set MoE headroom stayed **minimal (+0.0031)**, and — the loud signal — the trivial **gene-mean baseline (0.686) beat every trained expert (0.14–0.39)**. That's an out-of-distribution generalization failure worth explaining before trusting the experts.
3. **Step 1 decomposition** (`scratchpad/steps12.py`, run on the cached `predictions.npz`): split each per-sample Pearson into "recovers the shared cross-gene profile" vs "captures sample-specific residual". Experts recover the shared profile only **0.17 / 0.36 / 0.51** (human/mouse/mixed) — i.e. worse than trivially copying the dataset-mean profile the baseline uses — and add only ~**0.15** of residual signal. Their outputs are also magnitude-collapsed (std ≈ 0.2–0.4% of truth). `mixed` recovers the profile best (0.51), which is exactly why it's best-single on both species. **Conclusion: the 5k experts are distribution-bound, not that the baseline is clever.**
4. **This aligns with the earlier scale finding**: `human_20k` v1 more than halved val_loss vs `human_5k` v1 (0.72→0.32, still descending at ep 28) and lifted OSDR Pearson 0.687→0.813, nearly closing the gene-mean gap. At 5k, data scale dominates architecture ~6–7×. So the fix is **scale, not more architecture tweaks**.
5. **Step 2** (K-fold CV blend validation): the OSDR **30/70 human/mouse blend is NOT overfit** — same-set advantage +0.0084 reproduces out-of-sample at +0.0084 (20/20 folds, stable weights). The balanced-set blend edge is real but negligible (+0.0007, all weight on `mixed`). Fixed blending gives a small real gain; per-sample routing (oracle +0.0018) still adds ~nothing **at 5k**.

**Decision → V3 = 20k scale-up.** Retrain all three experts at 20k on the *same* shared canonical vocab and v2 architecture, to test whether scale (a) closes the OOD gap and (b) makes the experts specialize enough that MoE routing finally has headroom — i.e. whether the "routing doesn't pay" conclusion is itself a 5k artifact. Evaluated on the same balanced held-out set (which V3 training explicitly excludes — see below).

**V1 → V2 → V3 at a glance:**
| | V1 (5k) | V2 (5k) | V3 (20k) — *this sprint* |
|---|---|---|---|
| samples/expert | ~5k drawn | ~5k drawn | ~20k drawn (4×) |
| gene vocab | per-variant (~14.8k, mismatched) | shared canonical 15,448 | shared canonical 15,448 |
| architecture | 2 layers, mask 0.15, wd 0 | 4 layers, mask 0.30, wd 0.01 | same as V2 |
| what it fixed | (baseline) | vocab mismatch → MoE headroom now *measurable* | tests whether *scale* closes the OOD gap + unlocks routing headroom |
| result | OSDR collapsed to gene-mean (0.687 vs 0.847) | val 0.43/0.52/0.80; headroom ~0; still distribution-bound on balanced set | *pending* |

**V3 mechanics (launched this session):**
- New variant configs `human_20k_v3` / `mouse_20k_v3` / `mixed_20k_v3` in `core/train_single.py`; launchers `runs/train_*_20k_v3.sh`, preprocessor `runs/preprocess_20k_v3.sh`.
- Preprocessing draws 24k/24k/12k-per-species (over-draw to net ≥19,200 after QC), `--seed 123`, and **`--exclude-ids-file data/holdout_eval/exclude_holdout_all.txt`** (the 667 balanced-holdout IDs) so that eval set stays a clean OOD test for V3.
- Allocation: `mixed`→`moe-reboot` (full A100), `human`→`moe-reboot2` (full A100), `mouse`→`moe-reboot-partial` (vGPU, gloo backend). 15 epochs each; `best_model.pt` rewritten every improving epoch so intermediate reads are safe.
- **batch_size 8 for all three** (not the 16 initially used on the full A100s). Measured throughput showed the runs are compute-bound at ~0.51 s/sample, so batch 16 gave *zero* wall-clock speedup over batch 8 (8.22 s/16-batch vs 4.13 s/8-batch) while halving optimizer steps/epoch at a fixed LR and diverging from the batch-8 config the 5k V2 experts used. Restarted human/mixed at batch 8 ~1h in (nothing checkpointed yet) so all three are directly comparable to each other and to V2. Wall-clock unchanged: **~33 h / 15 epochs** for all three (they finish together — no long-pole asymmetry; ~2000 batches/epoch × ~4.1 s).
- `human_matrix_v11.h5` re-downloaded to `moe-reboot` (was deleted for space); mouse matrix was still present. Current code rsync'd fresh to all 3 VMs (they were on stale/flat layouts).
- **NOTE the pre-existing `human_20k_v2` config is the OLD non-canonical v1-era A/B — not part of V3.** V3 uses the `_20k_v3` keys.

### 2026-07-13 (later) — V3 monitoring: mixed/human were SIGHUP-restarted, now ~1.5h behind mouse

- Checked all 3 VMs mid-training. `mouse_20k_v3` (`moe-reboot-partial`) has run uninterrupted since ~18:26 and is on epoch 1, batch ~1500/2000 (~4.13 s/batch, Run ETA ~32h40m).
- `mixed_20k_v3` (`moe-reboot`) and `human_20k_v3` (`moe-reboot2`) both got **SIGHUP (`SignalException: got signal: 1`) on their original launches** — the earlier PID (e.g. 145065 on `moe-reboot`) died when its launching SSH session detached (they were started outside tmux). Both were **relaunched at ~19:59 inside the tmux `train` session** (`bash -c ... bash runs/train_*_20k_v3.sh > ~/train_*_20k_v3.log 2>&1`), so they now survive disconnects. Verified the *current* runs are genuinely training (GPU compute-app PIDs holding ~15GB, worker state R, CPU time climbing, ~30 min alive) — they just hadn't hit the batch-500 print interval yet. Net effect: **mixed/human are ~1.5h behind mouse**, so the three no longer finish simultaneously; expect completion staggered by that much (~mid-day 2026-07-15).
- **Gotcha for reading these logs**: batch progress lines use `\r`, so plain `grep` reports the log as a "binary file" and finds nothing — decode with `tr '\r' '\n'` first. The stale SIGHUP traceback sits mid-file in `train_mixed_20k_v3.log`; it's from the dead PID 145065, not the live run.
- Local background watcher polling all 3 every 15 min (`scratchpad/vm_watch.sh` → `vm_watch.log`); exits and re-notifies on all-complete, a real crash (process gone without "Training complete!"), OOM/CUDA error, or a 40h ceiling.

### 2026-07-14/15 - Corrected interspecies evaluation audit (in progress)

**Decision:** finish and evaluate the human/mouse interspecies experiment at both
5k and 20k before starting organ experts. OSDR is no longer the primary MoE
headroom benchmark because its current cohort is mouse-only. The primary data
source is a frozen human+mouse ARCHS4 holdout; OSDR remains a secondary
spaceflight-domain check.

**The previously reported balanced-ARCHS4 headroom and gene-mean numbers are
invalid and must not be used.** The old evaluator fed raw TPM directly to models
trained on `log1p(TPM)`. It also tuned a fixed blend on the test samples, used a
test-derived gene mean, and called a hard expert selector the oracle even though
a soft convex gate can do better. Those faults are sufficient to invalidate the
old `+0.0031` headroom and `0.686` gene-mean comparison.

Corrected protocol now implemented locally:

- Frozen full holdout: 667 samples, 331 human / 336 mouse, ordered ID SHA256
  `84c607dd83f93964430877f572291836fddd7315dd4f7eae3bcbf12f70fc0d65`.
  This is sample-disjoint but has training-series overlap, so it is a
  **held-out-sample diagnostic**, not unseen-study OOD evidence.
- Strict sensitivity cohort: exact reconstruction of every V2/V3 train+val
  split, global exclusion of all whitespace-tokenized GEO series, leaving 103
  samples (50 human / 53 mouse), ordered ID SHA256
  `e52a695f5e518be24803dcb1fba266c7a67b7d4696520dba35466f5f38da2b18`.
- Exact `log1p(TPM)` input transform; one shared deterministic mask at the
  training-matched 30% mask rate; connected GEO-series grouping; grouped
  out-of-fold fitting for fixed blends and metadata-species routing.
- Separate hard Pearson oracle, hard MSE oracle, and exact per-sample soft
  convex MSE oracle. True-species routing is explicitly labeled a
  metadata-conditioned upper bound, not a learned unknown-species gate.
- Exact train-row-only global and species-specific gene means; no test-derived
  baseline. Primary estimates and paired bootstrap intervals give every study
  equal weight within species, then weight human and mouse equally.
- Paired 5k-versus-20k comparison requires identical sample order, folds,
  common gene space, and mask hashes. Raw Pearson/MSE are compared across scale;
  residual-Pearson scale deltas are intentionally omitted because the two scales
  use different train-derived centering profiles.

Current status at this checkpoint:

- Corrected evaluator, headroom math, scale comparison, launch guards, and OSDR
  preprocessing safeguards passed final local review. The expanded local suite
  passes 29/29 tests.
- Remote grouped/full and exact study-disjoint artifacts were regenerated with
  the final scripts. The strict result reproduced exactly: 103 samples (50
  human / 53 mouse), ordered ID SHA256 `e52a...2b18`. The launcher rejects stale
  artifacts by full/strict ID hashes and required `series_group_id` metadata.
- Exact train-only baseline artifacts are complete and split-hash verified.
  The 5k mean uses 4,000 rows (2,024 human / 1,976 mouse), artifact SHA256
  `2cef96f9...2b533fd77`; the 20k mean uses 16,000 rows (7,989 human / 8,011
  mouse), artifact SHA256 `35bfe19a...d56ad51f`.
- All three V3 runs are healthy in epoch 14/15. Latest best validation losses:
  mixed `0.594307`, human `0.288136`, mouse `0.232793`. Do not evaluate a V3
  checkpoint until its log says `Training complete!` and all corresponding
  `train_single.py` processes have exited.
- The current mixed V3 run inherited a species-contiguous row-group batch-order
  bug. Its result is still useful diagnostically, but a weak mixed checkpoint
  cannot by itself prove the MoE method fails; a corrected mixed retrain is a
  possible follow-up after this frozen evaluation.

### Overnight completion and backup automation (armed 2026-07-15 05:09 UTC)

All work required before unattended completion is now staged on `moe-reboot`:
the six training parquets, both ARCHS4 H5 files, frozen holdouts, exact baseline
means, selected 5k checkpoints, corrected evaluator modules, and launch scripts.
Local and remote evaluator SHA256 values match exactly. Real 5k and 20k
checkpoint snapshots also load successfully through the final evaluator on CPU:
15,448 model genes, 15,448 aligned gene labels, `log1p_tpm`, mask ratio `0.3`,
mask token `-10`. Only the full real-model forward pass awaits a free GPU.

Before waiting, each live 20k `best_model.pt` was frozen under a separate name
and copied to the Mac and `moe-reboot`'s persistent checkpoint volume with
checksum verification. These snapshots guarantee that the completed hours are
recoverable even if an instance fails before epoch 15:

- human epoch-13 snapshot: MD5 `079aac312215539be8e259363912bd61`
- mouse epoch-14 snapshot: MD5 `07d2714f85d2f2807bae3a82bc7b4227`
- mixed epoch-13 snapshot: MD5 `2f11bc192701b006437d6997281715cc`

Three standard detached macOS `screen` sessions are active, each wrapped in
`caffeinate -dims` so the Mac stays awake:

- `nasa_moe_backup_final`: polls all VMs. A final is accepted only after the
  training log contains `Training complete!` and no `train_single.py` PID
  remains. It downloads the final model atomically, verifies remote/local MD5,
  archives non-weight metadata and the training log, mirrors human/mouse finals
  into `moe-reboot` persistent checkpoint storage, then writes
  `<run>.SAFE_TO_SHELVE`. It writes `ALL_SAFE_TO_SHELVE` only after all three.
- `nasa_moe_eval`: waits for `ALL_SAFE_TO_SHELVE`, then launches the corrected
  5k+20k full/strict evaluation in remote tmux on the freed `moe-reboot` A100.
  It copies all result directories back to the Mac and runs
  `validate_corrected_eval_outputs.py`; success writes
  `EVALUATION_COMPLETE_AND_VALIDATED`.
- `nasa_moe_git`: waits for validated evaluation, stages an explicit allowlist
  of repository code/docs/scripts/tests (never checkpoints, data, backups, or
  results), validates the staged diff, commits, and retries the push to `origin`
  until it succeeds. Success writes `GIT_BACKUP_PUSHED` with the branch and full
  commit SHA.

Monitor without attaching:

```bash
screen -ls
tail -f backups/20k_v3_final/backup_watcher.log
tail -f backups/20k_v3_final/evaluation_watcher.log
```

**Where the watchers run:** both `screen` sessions and their `caffeinate`
processes run on the Mac, not inside a VM. Closing the Terminal app/window is
safe because `screen` is detached. Shutting down the Mac, disconnecting its
network, or closing a laptop lid is **not safe** for the automated handoff;
`caffeinate` prevents idle sleep while the lid remains open, but it is not a
guarantee against lid-close sleep. The remote training jobs themselves continue
inside VM tmux sessions, and the pre-completion snapshots are already safe, but
final download/central mirroring and automatic evaluation require the Mac
watchers to remain alive. Keep the Mac powered, lid open, and online until
`EVALUATION_COMPLETE_AND_VALIDATED` exists.

**Model-capacity downgrade checkpoint: safe now.** The high-capacity audit,
protocol correction, artifact freezing, tests, central staging, and unattended
handoff are complete. Scientific results are still pending overnight inference,
but the remaining path is scripted and integrity-gated. **VM shelving is a
different checkpoint:** only shelve an individual VM after its corresponding
`backups/20k_v3_final/<run>.SAFE_TO_SHELVE` marker exists.

## Next up

- [x] Investigate the gene-mean-beats-everyone gap on the ARCHS4 held-out set → **done** (distribution-bound; see step 1 above). Re-check on V3.
- [x] Validate the blend on a proper held-out split → **done** (CV; OSDR 30/70 not overfit, balanced-set edge negligible; see step 2 above).
- [ ] **V3 (in progress)**: when all 3 20k experts finish, rerun `analyze_moe_headroom.py` on `mixed_holdout.parquet` (the balanced set) and OSDR; compare headroom + gene-mean gap to V2. Back up the 3 new `best_model.pt` to the Mac (MD5-verified) as before.
- [ ] Then the organ-split test (see below).
- [ ] Frozen-backbone + lightweight-adapter architecture (CodonMoE-style) — the 3-independent-full-experts design is the likely reason routing has so little headroom; scoped as a later engineering task.
- [ ] `data/holdout_eval/` source data (raw batch parquets, `predictions.npz`) is only on `moe-reboot`/`moe-reboot2`, not backed up to the Mac (predictions.npz for both eval sets were pulled to `scratchpad/` this session for steps 1&2).

## V3 decision framework (what to do when the 20k runs finish)

The plan is: (1) wait for all three 20k experts to finish, (2) check whether MoE routing now has meaningful headroom, (3) branch on the result. Concretely, run `analyze_moe_headroom.py` on both eval sets (`mixed_holdout.parquet` balanced + OSDR) and read **two** numbers:

- **OOD gap** — do the 20k experts beat the gene-mean baseline (0.686)? At V2/5k they collapsed to 0.14–0.39. Tests whether *scale* fixed the generalization failure.
- **Routing headroom** — oracle per-sample routing minus best-single-expert. V2 reference: **+0.0031** (balanced) / **+0.0018** (OSDR oracle), i.e. noise.

**"Meaningful" bar:** oracle − best-single **≥ ~+0.02** (≈7–10× the V2 noise floor), *and* ideally a learnable gate (not just the oracle upper bound) captures a real fraction of it. Under ~+0.01 = same "routing doesn't pay" result at bigger scale.

**Branch:**
- **Headroom ≥ +0.02** → scale unlocked specialization → pursue the gating direction (train the MoE gate, then frozen-backbone + lightweight-adapter / CodonMoE-style design).
- **Headroom ~0 but OOD gap closed** (experts now beat gene-mean) → experts generalize, species axis just doesn't separate them → **pivot to the organ-split test below**.
- **Headroom ~0 AND OOD gap persists** (still lose to gene-mean at 20k) → bottleneck is backbone/data, not routing → reconsider frozen-backbone+adapter architecture or more data *before* spending compute on organ experts.

## Planned: MoE organ-split test

The species axis barely separates the experts (`mixed` dominates everywhere), so routing has nothing to arbitrate. **Organ is a finer, more biologically meaningful axis** — the hypothesis is that organ-specialized experts diverge enough that per-sample routing finally shows real headroom. Deferred behind V3 so we first know whether scale alone matters.

- **Data**: mouse `.h5` `source_name_ch1` has ample organ coverage (verified 2026-07-13: brain ~28k, lung ~26k, bone ~26k, liver ~19k, colon/spleen/skin ~6–7k). Reuses the mouse matrix already on `moe-reboot` — no new download. (Human organ labels would need the human matrix; start mouse-only.)
- **Design**: pick 3–5 organs by count; add organ-based sample selection to `preprocessing.py` (new `--organ`/`--source-filter` flag — filter `source_name_ch1` before sampling, mirroring `--exclude-ids-file`). Train one expert per organ on the shared canonical vocab / v2 arch.
- **Eval**: draw an organ-labeled held-out set (exclude training IDs), compute **oracle-by-organ routing vs best-single-organ-expert** headroom — the organ analogue of the current species headroom analysis. Key comparison: is organ headroom > the ~0 species headroom?
- **Open questions**: organ count vs samples-per-organ tradeoff; whether to route by true organ label (upper bound) or a learned gate; whether to fold in V3-scale per organ if 5k-per-organ underfits the same way.

## Provenance

Fork of Walter Alvarado's `bridge-rna` work (UChicago), itself part of a larger team project (`sp26_nasa` — Abraham Guan, Brian Zhou, Karen Meng, Ishanth Hombaiah, Minggang Li; mentor Dr. Walter Alvarado, NASA Ames; Berkeley CDSS Data Discovery program). This repo (`nasa-rna-moe`) is Minggang Li's individual continuation under a SPARC research proposal — the zero-shot OSDR evaluation pipeline, collapse/alignment diagnostics, MoE headroom analysis, and the v2 shared-vocabulary fix are this author's own work built on top of the team's shared pretraining pipeline; see `presentation/2026-07-09-biweekly.html` for the full attribution split.
