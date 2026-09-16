# Spaceflight workstream — current status

**Radiation robustness audit complete — September 15, 2026.** All 130 profiles were
embedded on moe-reboot's A100 in 48.3 seconds; 16 declared small-head configurations
were evaluated locally. No encoder, LoRA or flight-head update occurred. No job remains
running, and the watcher remains paused.

## Result worth discussing

The common-count BRIDGE IR/control head achieved AUROC 1.0 on both new 2Gy IMR90 time
points: 6/6 correct at 24h and 5/6 at 6h. Removing any entire training source file preserved
24h classification and both time-point rankings; 6h balanced accuracy ranged 0.50–0.833.
This is a narrow, reproducible irradiation-associated lead in the same cell strain.
Each time point has only three irradiated and three control cultures. GSE111437 was new
to the head but appears in the encoder catalog (7 train, 5 val).

## What remains unresolved

The same head labels 4/5 bleomycin, 3/3 rotenone and 3/5 oligomycin samples as radiation.
Lung-chip transfer is inconsistent; stress-negative and matched-control variants do not
provide a general remedy. Treatment-label and duplicate audits passed, and removing two
ambiguous cell-line records did not resolve failures. An exposure-associated response
probe does not establish that the muscle flight classifier uses that response positively.
The old flight heads decrease on these out-of-domain irradiated cultures; this is a
diagnostic, not a causal conclusion.

## Outputs and next step

[Audit report](runs/07_radiation_robustness_audit_2026-09-15/REPORT.md) ·
[Main figure](runs/07_radiation_robustness_audit_2026-09-15/robustness_audit.pdf) ·
[All configurations](runs/07_radiation_robustness_audit_2026-09-15/all_configurations.pdf) ·
[Verification](runs/07_radiation_robustness_audit_2026-09-15/independent_verification.json).

Retain the 24h result as a research lead and obtain tissue/time-matched radiation,
non-radiation stress and gravity controls with independent donors/experiments. Test
response specificity and flight-head reliance together before assigning exposure labels
or percentages. Controlled-gravity quantification is still a separate next analysis.
No next run is queued. See [plan](PLAN.md).
