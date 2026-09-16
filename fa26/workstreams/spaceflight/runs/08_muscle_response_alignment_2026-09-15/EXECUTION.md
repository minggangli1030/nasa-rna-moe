# Run08 execution record

Authorized by the user's “continue” after run07.

1. Inspect primary GEO family metadata for human muscle perturbation candidates.
   Include GSE200335 EPS/control (7 donor pairs); document excluded candidates in
   `candidate_audit.csv`. Sources downloaded with curl over HTTPS.
2. Freeze `protocol.json` before outcomes, with implementation detail in `analysis_detail.json`.
3. Run `muscle_response_alignment.py prepare --folder <run08>` from project root.
   Reuse run07 gene mapping and old harmonized/original flight inputs; prepare 76
   encodings, comprising 38 unique biological samples. See `input_audit.json`.
4. Upload only derived public GEO inputs and source audit to
   `/media/volume/moe-reboot/fa26_muscle_alignment_20260915`, moe-reboot (149.165.175.241).
   Run `controlled_exposure_pilot.py infer` with the pinned r7hnr92k model/config in
   `/media/volume/moe-reboot/fa26_bridge_inference/model/r7hnr92k/`, official inference
   source in `/media/volume/moe-reboot/fa26_pattern_pilot_20260911/bridge-rna-latest/upstream_embeddings/src/fm_embed/inference_model.py`,
   using `/home/exouser/moe-env/bin/python`. Retrieve embeddings, inference report and
   completion marker. 26.9 seconds; no encoder fitting.
5. Run `muscle_response_alignment.py evaluate --folder <run08>` locally. Saved probes
   and flight heads remain fixed; four source-deletion probes use prior radiation data only.
6. Run `report_muscle_alignment.py --folder <run08>`. Recheck source donor pairing,
   saved pipeline scores, paired differences, held-out pool separation, projection sums
   and robustness directions. Inspect the summary figure.

All scripts are under `fa26/workstreams/spaceflight/scripts/`. Prepare/evaluate refuse
completed-output overwrite; report regenerates derived summaries. Use a fresh folder
with copies of the frozen protocol/source files for reproduction. Heads and prior runs
are unchanged. No background job or watcher is needed after completion.

New RNA-seq count source:
https://www.ncbi.nlm.nih.gov/geo/download/?type=rnaseq_counts&acc=GSE200335&format=file&file=GSE200335_raw_counts_GRCh38.p13_NCBI.tsv.gz

Primary metadata:
https://ftp.ncbi.nlm.nih.gov/geo/series/GSE200nnn/GSE200335/soft/GSE200335_family.soft.gz
