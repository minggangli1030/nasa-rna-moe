# Follow-up: VM computation complete; scientific review pending

Authorized by the user: start execution and periodic watcher. The 15-minute heartbeat
is `nasa-repeat-flight-watcher`. Stop it after final review, updated brief, and delivery.

## Scope and frozen protocol

Read `protocol.json` and `preprocessing_audit.json`. Twelve No E-stim Day21 samples
from GSE298393 passed 99.815% canonical stable-ID coverage and exact library/chip matching.
The supplied training catalog contains none of their GSM IDs; actual checkpoint
exposure is not independently proven. GEO describes the matrix as FPKM despite a
rawmatrix filename. Inputs use canonical-universe FPKM rescaling to TPM, log1p once;
no second division by gene length. This is conditional on the source units, and
normalization differs from first-flight count/exon-length inputs. Retain that caveat.
The source shares donor pools with earlier experiments; no independent-donor claim.

## VM execution

SSH: `ssh -o HostName=149.165.175.241 -o BatchMode=yes -o StrictHostKeyChecking=yes moe-reboot`.
Run directory: `/media/volume/moe-reboot/fa26_muscle_repeat_flight_20260912`.
Read `phase.txt`, `run.log`, and output markers. `run.sh` holds a flock to
avoid duplicate jobs. `COMPLETE` means inference and computed analysis finished;
`FAILED` means inspect the log. If `ANALYSIS_COMPLETE` exists, the scientific review
and Monday brief update are still required; do not launch the job again.

Local files: `/Users/minggangli/Projects/nasa-rna/fa26/artifacts/muscle_repeat_flight_2026-09-12`.
Source: `/Users/minggangli/Projects/nasa-rna/fa26/muscle_repeat_flight.py`.
Baseline: `fa26/artifacts/general_survey_2026-09-12/`.
Existing VM Python: `/home/exouser/moe-env/bin/python`.

## Completion work

1. Retrieve the VM output into this local artifact directory with rsync and the same SSH override.
2. Verify finite embeddings, ordered IDs, input/source/checkpoint hashes and matching source code.
3. Inspect `within_flight_robustness.csv`, `cross_flight_direction.csv`, `missingness_sensitivity.csv`,
   `prespecified_gene_shifts.csv`, and `cross_flight_pattern.pdf`. The last plot needs visual QA.
   If the VM analysis failed for missing CPU libraries, run locally:
   `OPENBLAS_NUM_THREADS=2 python3 fa26/muscle_repeat_flight.py analyze --output fa26/artifacts/muscle_repeat_flight_2026-09-12 --baseline fa26/artifacts/general_survey_2026-09-12`.
4. Write a concise REPORT.md here, update the general survey's MONDAY-DISCUSSION.md
   with whether the selected pools' directions agree across flights and survive chip deletion,
   then update fa26/README.md and fa26/NEXT-STEPS.md. Preserve negative outcomes.
5. Report the main finding and uncertainty to the user, pause this watcher, and mark
   scientific review complete in this handoff. Do not expand to training or other cohorts.

Notify only on meaningful progress, failure, required input, or final completion.
No routine unchanged-status notices. Do not send external messages to anyone.
The workspace sandbox has a symlink-root initialization issue; prior shell commands
used auto-reviewed require_escalated for this authorized repository/VM work.

## Latest status — scientific review complete

VM computation and scientific review are complete. REPORT.md, the reviewed figure,
normalization sensitivity, gene-panel deletion checks, verification.json, and the
Monday/Fall handoff updates are finished. Both positive and negative findings are
reported: broad directions do not repeat; MYH1 decrease survives in both pools and
flights. Source-FPKM sensitivity retains the expression disagreement. No more jobs
should be launched. The watcher is paused; final results have been delivered.
