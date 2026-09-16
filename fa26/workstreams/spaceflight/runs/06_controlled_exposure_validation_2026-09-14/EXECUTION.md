# Controlled exposure pilot — execution record

Authorized by the user's “continue” after the response-level pilot. The bounded objective
was to acquire independent controlled exposure data and test response-probe specificity.

1. Download public GEO family metadata and processed expression from GSE230181/GSE242706;
   audit GSE222998 gravity data separately. Sources and hashes are in `sources/` and `input_audit.json`.
2. Run `controlled_exposure_pilot.py prepare --root fa26 --folder <this folder>`.
3. Run its `infer` phase on moe-reboot's A100 using the pinned checkpoint and official
   inference source. Remote directory: `/media/volume/moe-reboot/fa26_controlled_exposure_20260914`.
4. Retrieve `embeddings.npz`, `inference_report.json`, `inference.log`, `INFERENCE_COMPLETE`.
5. Run `evaluate_controlled_exposure.py --root fa26 --folder <this folder>` locally.
6. After observing specificity failures, run the explicitly adaptive
   `check_exposure_hard_negatives.py --folder <this folder>` comparison.
7. Run `report_controlled_exposure.py --root fa26 --folder <this folder>`; inspect plots and report.

All scripts live in `fa26/workstreams/spaceflight/scripts/`. Prepare/evaluation phases
refuse to overwrite a completed run. Use a new folder for reproduction; preserve the
frozen protocol and amendments. Initial baseline outputs with a near-constant-feature
numerical problem were archived under `history/before-near-zero-variance-fix/`.

123 new profiles; 15,061 common canonical genes; 45.5 seconds of GPU inference. All head
fitting and reporting ran locally. No encoder update, LoRA or flight-head retraining.
The VM is idle and the watcher remains paused because no background job remains.
