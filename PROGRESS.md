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
- Confirmed (grep across all file types, not just code) that nothing in `nasa-rna-moe` still depends on the local `sp26_nasa` checkout, then deleted it from the Mac (`/Users/minggangli/Projects/sp26_nasa`). It's untouched on GitHub if ever needed again. **Not yet done**: the VM still has its own `~/sp26_nasa` sparse checkout (used to source `archs4_preprocessing_demo/protein_coding_ortholog_genes.txt` and the original OSDR files, both already committed into `nasa-rna-moe` now) — safe to `rm -rf ~/sp26_nasa` there too whenever convenient, not urgent.
- Added `presentation/2026-07-09-biweekly.html` — a self-contained (no external assets) scroll-snap slide deck for tomorrow's biweekly update. Slides 1-5 are ready (recap, v1 findings, the vocab-fix rationale, infra migration story). Slides 6-7 have real v1 numbers for context but the v2 results are explicit `PENDING` placeholders — **must be filled in with real numbers from `scripts/run_diagnostics.sh` before presenting**.

## 2026-07-09 — .h5 download confirmed, preprocessing done in under 2 minutes

- `data/archs4/human_matrix_v11.h5` (17G) and `mouse_matrix_v11.h5` (18G) both landed intact (`ls -lh` matches the `Content-Length` check from the day before, just GiB- vs byte-rounding).
- Ran `scripts/preprocess_5k_v2.sh`: all three v2 5k variants (human/mouse/mixed) built successfully. The local-`.h5` fix fully paid off — this took **under 2 minutes total** for all three, versus 15+ minutes stalled on a single batch of one variant via S3 streaming the day before.
  - `mixed_5k_v2`: 2,146 human + 2,107 mouse = 4,253 samples × 15,448 canonical genes.
  - Confirms the earlier diagnosis was right: the S3-streaming path wasn't a fluke slowdown, it was structurally reading close to the entire remote file every time.
- Also revised `presentation/2026-07-09-biweekly.html` per feedback: added 5 SVG figures (results bar chart, collapse-vs-baseline chart, MoE architecture diagram, headroom dumbbell chart, ARCHS4-vs-OSDR stat pair), switched to horizontal scroll-snap navigation with keyboard/wheel support, and bumped body text to 16pt. Background section restructured so slides 5-8 center my own diagnostic work (OSDR eval, collapse check, MoE gate, headroom analysis) rather than reiterating the team poster — teammates get a brief, explicit credit instead of being the focus.

## 2026-07-09 — Training was ~42h ETA, root-caused and fixed to a fraction of that

- First real training ticker (`human_5k_v2`, epoch 1) reported a steady **5.12s/batch**, which the script's own ETA math projected to **~42 hours** for all three variants at 30 epochs each — completely unworkable for tomorrow.
- Root-caused rather than guessed: `CONFIG["compute_type"] = "iter"` computes the model's prefix-sum linear attention via a **Python-level loop over 64-position chunks** (`numerator_and_denominator.py`, `_ITER_CHUNK_SIZE`). For a 15,448-gene sequence that's ~242 sequential chunk iterations per layer per forward+backward pass — dominated by Python/kernel-launch overhead, not actual GPU FLOPs. `batch_size=4` showed the same fingerprint: both values trace back to a comment elsewhere in the codebase noting SLiMPerformer OOMs on an **11GB 1080 Ti** at this gene count — a constraint that doesn't apply to a 40GB A100 at all.
- Fix (mathematically identical output — same prefix-sum math, computed in fewer/larger chunks, not an approximation):
  - `_ITER_CHUNK_SIZE`: 64 → 1024 (16× fewer loop iterations; ~1.2GB per chunk even at the larger batch size below, well within 40GB)
  - `batch_size`: 4 → 16 (4× fewer batches/epoch: 1000 → 250)
  - Deliberately did **not** switch `compute_type` to `"ps"` (a different single-shot implementation) — that materializes a much larger tensor at once with a less predictable memory footprint; the chunk-size bump gets most of the same win with bounded, safer memory.
- **Caveat, noted honestly**: bumping batch size without also scaling the learning rate is a known simplification (linear-scaling-rule purists would bump LR too). Not doing that now — priority is a valid v2 result by tomorrow, not a fully hyperparameter-tuned one. Worth revisiting if training continues past this sprint.
- **First restart OOM'd**: `chunk_size=1024` and `batch_size=16` together (16×4=64× the original transient tensor size, not a modest bump) exceeded 40GB during backward — `torch.OutOfMemoryError` trying to allocate 4.50GiB with only 873MB free, ~32GB already held by activations/optimizer state/allocator fragmentation. The mistake: scaling chunk size and batch size simultaneously without doing the multiplicative memory arithmetic first.
- **Corrected**: `_ITER_CHUNK_SIZE` → 512 (was 1024), `batch_size` → 8 (was 16) — a 4× smaller transient tensor than the OOM'd config, while still 8× fewer loop iterations and 2× fewer batches/epoch than the original tiny config. Also added `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`, PyTorch's own suggested fix for the allocator-fragmentation part of the error.
- Switched off `WANDB_MODE=offline` — logged into W&B properly for live run tracking instead.

## Next up

- [ ] Confirm the corrected chunk/batch combo doesn't OOM and note the real speedup from the first post-restart ticker line
- [ ] Run `scripts/train_5k_v2.sh` — 3 v2 experts fresh on the A100 (in progress)
- [ ] Run `scripts/run_diagnostics.sh` (zero-shot OSDR eval → alignment check → MoE headroom)
- [ ] Fill in the `PENDING` results table + alignment-check summary in `presentation/2026-07-09-biweekly.html`
- [ ] Optional: `rm -rf ~/sp26_nasa` on the VM (already fully superseded there too)
- [ ] Time permitting: MoE gate training if headroom justifies it

## 2026-07-09 — Went from 1 GPU to 3, parallelizing the remaining two variants

- Quota reality check: allocation is 2 A100s total (not unlimited) — `moe-reboot` already counted as 1, so only **one** more full A100 (`moe-reboot2`) was available, plus a separate partial-GPU quota bucket (**1** more, a vGPU slice).
- Reassigned the plan: `human_5k_v2` stays on `moe-reboot` (uncapped, already progressing, not worth interrupting). `mouse_5k_v2` → `moe-reboot2` (full A100). `mixed_5k_v2` → new instance `moe-reboot-partial` (vGPU partition, 20GB).
- **Set up direct SSH from the Mac to all instances** (bypassing the Exosphere web shell) — added the Mac's existing key to each instance's `authorized_keys`, configured `~/.ssh/config` aliases (`moe-reboot`, `moe-reboot2`, `moe-reboot-partial`). From here on, driving setup and training launches directly via SSH rather than relaying commands for manual execution — user explicitly opted into this given the time pressure and round-trip friction of copy-pasting terminal output all night.
- Transferred already-preprocessed data (merged parquet, ~280-290MB per variant) directly instance-to-instance via piped `tar` through the SSH relay, instead of re-downloading raw `.h5` files (18-36GB) on each new instance — avoided ~35-40 min of redundant download per instance.
- **Epoch-budget asymmetry caught and fixed**: the original 12-epoch cap on mouse/mixed was a conservative estimate that turned out to leave real slack (12 epochs only needed 6h45m of the 16h budget once actual throughput was measured) — but it meant mouse/mixed would train for meaningfully fewer epochs than `human_5k_v2`'s uncapped 30, confounding the three-way comparison the whole point of this sprint is to make. Raised the cap to **20 epochs** for both (~11.4h at measured throughput, still real margin under 16h).
- **New bug found and fixed**: `moe-reboot-partial`'s vGPU (`GRID A100X-20C`, an NVIDIA virtualized/partitioned A100, 20GB) failed with `CUDA driver error: operation not supported` on `dist.init_process_group(backend="nccl")` — even in single-process mode. Root-caused by bisection rather than guessing:
  1. Tried `NCCL_P2P_DISABLE=1`/`NCCL_SHM_DISABLE=1`/`NCCL_IB_DISABLE=1` — still failed, now inside NCCL's object-broadcast tensor serialization.
  2. Switched `backend="nccl"` → `"gloo"` (made configurable via a new `DDP_BACKEND` env var, defaults to `nccl` — zero behavior change for `moe-reboot`/`moe-reboot2`) — got further, but then failed on a plain `model.to(device)` call. This proved the issue wasn't NCCL-specific at all.
  3. Isolated with a 2-line Python repro: `torch.randn(10,10).to('cuda')` failed with `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` set, succeeded without it. **Root cause: `expandable_segments` uses CUDA's virtual-memory-management driver APIs, which this vGPU partition doesn't expose** — unrelated to the NCCL error's surface symptom, which was a red herring from testing both changes near-simultaneously.
  - Final working config for `moe-reboot-partial`: `DDP_BACKEND=gloo`, no `PYTORCH_CUDA_ALLOC_CONF`. Training now stable at 15GB/20GB VRAM, 98% GPU utilization.
- All three instances training in parallel as of this entry:
  - `moe-reboot`: `human_5k_v2`, uncapped, epoch 3+, val loss 0.937→0.919→0.905
  - `moe-reboot2`: `mouse_5k_v2`, 20-epoch cap, restarted clean, ~4.1s/batch (matches `moe-reboot`'s rate)
  - `moe-reboot-partial`: `mixed_5k_v2`, 20-epoch cap, just started, throughput reading pending

## Next up

- [ ] Set up a scheduled check (timer) that fires once mouse/mixed are expected to finish: review all three instances' results, and if they look meaningful, fill in the presentation's `PENDING` sections and summarize findings; if something looks broken, diagnose before presenting
- [ ] Fill in the `PENDING` results table + alignment-check summary in `presentation/2026-07-09-biweekly.html`
- [ ] Time permitting: MoE gate training if headroom justifies it
