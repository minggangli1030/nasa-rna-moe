# Spaceflight workstream — current status

**Human muscle response-alignment follow-up complete — September 15, 2026.**
76 encodings represent 38 biological samples: 24 existing flight chips plus 14 new
human muscle cultures from seven EPS/control donor pairs. Inference took 26.9 seconds
on moe-reboot A100. No encoder or flight-head update; no job remains running.

## Findings

- Non-radiation electrical stimulation increases the irradiation probe in 6/7 donors;
  the absolute threshold also calls all seven unstimulated controls positive.
- The probe rises with flight in GSE234465 but falls in GSE298393, in both donor pools.
  All four directions survive preprocessing, gene coverage and radiation-training-file
  deletion checks. There is no consistent irradiation-like flight response across missions.
- The working flight classifier is supported by a *lower* irradiation-probe component.
  Its geometric contribution is positive but metric-dependent (about 0.5–1.6 logit units
  of a 10–12-unit flight/ground gap). This is not a validated biological intervention or
  an exposure percentage. Residual evidence remains explicit.
- EPS raises TNF/NF-kB-associated expression in all seven donors under mean-expression
  and rank scoring. It is a useful non-radiation response control, not a general flight
  inflammatory signature. Myogenesis-associated expression falls in six of seven donors.

The seven-donor study was not used to train these heads, but all 14 profiles appear in
BRIDGE's encoder catalog. No clean human muscle irradiation dataset was verified in the
targeted search. A mouse 3D muscle candidate is documented separately because of species,
shared-dish dependence and contradictory replicate counts.

## Outputs and next step

[Report](runs/08_muscle_response_alignment_2026-09-15/REPORT.md) ·
[Figure](runs/08_muscle_response_alignment_2026-09-15/muscle_alignment.pdf) ·
[Donor summary](runs/08_muscle_response_alignment_2026-09-15/donor_summary.csv) ·
[Dataset candidates](runs/08_muscle_response_alignment_2026-09-15/candidate_audit.csv).

Keep the narrow run07 24h IMR90 result as a comparator, but do not label the current
flight prediction radiation-driven. Future response heads should retain the paired EPS
control and test tissue/time-matched radiation, altered gravity and other stresses.
Report response evidence, signed flight-score reliance and unexplained evidence first;
exposure names and percentages require further validation. Controlled-gravity quantification
is still separate. No next run is queued; watcher remains paused. See [plan](PLAN.md).
