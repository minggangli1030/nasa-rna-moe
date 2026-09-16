# Run07 execution record

User authorized an audit and attempts to improve the radiation-associated prediction head.

1. Freeze `protocol.json` before new-model outcomes. Download public GEO counts for
   GSE230181 and GSE111437 and family SOFT metadata for GSE111437. Reuse run06's public
   GSE242706 counts, metadata and mapping. Exact file hashes: `input_audit.json`.
2. Run `audit_radiation_robustness.py prepare --folder <run07>` from project root.
   This creates 130 input profiles and a sample-matched original-processing comparator.
3. Copy `inputs.npz`, public-source audit, protocol and `controlled_exposure_pilot.py`
   to `/media/volume/moe-reboot/fa26_radiation_audit_20260915` on moe-reboot
   (SSH alias with HostName override 149.165.175.241). Run its `infer` phase with the
   pinned checkpoint/config in `/media/volume/moe-reboot/fa26_bridge_inference/model/r7hnr92k/`
   and official source in `/media/volume/moe-reboot/fa26_pattern_pilot_20260911/bridge-rna-latest/upstream_embeddings/src/fm_embed/inference_model.py`.
   Python: `/home/exouser/moe-env/bin/python`. The dispatch SSH session timed out;
   completion was verified without relaunching. Retain `inference.log` and completion marker.
4. Retrieve `embeddings.npz`, `inference_report.json`, `inference.log`, `INFERENCE_COMPLETE`.
   Input/model hashes and sample order are checked before evaluation.
5. Run `audit_radiation_robustness.py evaluate --folder <run07>` locally. All 16 configurations
   and all reference choices are retained. Scripts live in `workstreams/spaceflight/scripts/`.
6. After initial outcomes, freeze `stability_amendment.json` via
   `check_radiation_training_stability.py --folder <run07>`: delete each whole training file,
   inspect sample-deletion sensitivity, and score the fixed flight heads out of domain.
   This is an explicitly adaptive robustness check, not untouched confirmation.
7. Run `report_radiation_audit.py --folder <run07>`. Independently recompute metric counts,
   verify 792 train/reference/test split groups and saved-head external scores. Inspect both figures.

Prepare/evaluate/stability refuse to overwrite their completed outputs; reproduce in a
new folder with the protocol and source files. The report command regenerates derived
summaries and figures. No encoder update. Inference took 48.3 seconds, 0.63GB peak GPU
allocated memory. All head fits were local. The VM is idle and the watcher remains paused.
