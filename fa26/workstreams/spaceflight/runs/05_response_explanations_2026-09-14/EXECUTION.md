# Response-level pilot — execution and completion

Authorized by Minggang on September 14, 2026: update the Markdown, reorganize the folder,
and execute the next response-level explanation step. No encoder or head training occurs.

Local preparation and local response/attribution summaries completed. The replacement
job runs on moe-reboot's A100. Public GEO expression inputs were reused from existing VM
files; only code and gene-set/panel definitions were uploaded.

Remote directory: `/media/volume/moe-reboot/fa26_response_programs_20260914`.
SSH alias needs explicit `-o HostName=149.165.175.241` (the saved alias IP is stale).
Watch `STATUS.json`, `response.log`, and the `COMPLETE` marker. A full run has 6,048
replacement rows, 24 score-reference rows and an `execution_report.json`.

After completion, copy `perturbations.csv`, `score_checks.csv`, `execution_report.json`,
`STATUS.json`, `response.log`, and `COMPLETE` into this local run directory. Then run:

```sh
python3 fa26/workstreams/spaceflight/scripts/report_response_programs.py final --folder fa26/workstreams/spaceflight/runs/05_response_explanations_2026-09-14
```

The finalizer checks design completeness, exact matching, finite values, reproduction of
original model logits, and analytic expression-model perturbations. It writes REPORT.md,
EXAMPLE.md, response_program_summary.pdf/png, per-sample reliance, response contrasts,
stability and verification tables. Inspect the figure and report before claiming completion.
Update the workstream STATUS.md and top-level README.md/NEXT-STEPS.md with verified findings.
Preserve failed cross-flight transfer and the exploratory nature of the data.

For interrupted runs, inspect process state and preserve errors before any restart. The
GPU script resumes only complete 252-row sample-reference blocks; partial blocks require
inspection, not blind overwrite. Checkpoint SHA-256 and source hashes are recorded.
