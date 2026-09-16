# Fall 2026 project log

This is the chronological source of truth for completed steps. Individual reports retain
methods, exact results, caveats, and file-level provenance.

## September 11 — contract verification and first pilot

1. Audited the BridgeRNA canonical gene order, length alignment, preprocessing, checkpoint,
   and source contracts. Corrected the draft normalization order. See
   [`../CONTRACT-AUDIT.md`](../CONTRACT-AUDIT.md).
2. Ran a 34-sample mouse-liver OSDR pilot as a pipeline-development cohort. It was later
   superseded by the general survey. See
   [`../artifacts/osdr_liver_pilot_2026-09-11/REPORT.md`](../artifacts/osdr_liver_pilot_2026-09-11/REPORT.md).

## September 12–13 — discovery survey and focused follow-ups

3. Surveyed 559 samples, 28 accessions, 54 contrasts, and 11 broad tissue groups. The
   survey produced discussion leads, not a universal biomarker. See
   [`../artifacts/general_survey_2026-09-12/REPORT.md`](../artifacts/general_survey_2026-09-12/REPORT.md).
4. Tested a second human muscle-chip flight. Broad response directions did not repeat;
   MYH1 decrease persisted across both donor pools and flights. See
   [`../artifacts/muscle_repeat_flight_2026-09-12/REPORT.md`](../artifacts/muscle_repeat_flight_2026-09-12/REPORT.md).
5. Tested ten predefined programs across human muscle, MG63, endothelial, and mouse
   contexts. Average oxidative-phosphorylation expression in both muscle flights and a
   controlled MG63 inflammatory/repair pattern remained preliminary leads. See
   [`../artifacts/pathway_onboard_1g_2026-09-13/REPORT.md`](../artifacts/pathway_onboard_1g_2026-09-13/REPORT.md).

## September 14 — ownership, head evaluation, and response explanation

6. Recorded the PI discussion and separated three workstreams: batch effects (Brain),
   spaceflight prediction/explanation (Minggang), and an unassigned human–mouse question.
   See [`2026-09-14-MEETING-NOTES.md`](2026-09-14-MEETING-NOTES.md).
7. Audited linked BridgeRNA benchmark resources and the provisional local batch metadata.
   See [`../artifacts/bridge_benchmark_audit_2026-09-14/REVIEW.md`](../artifacts/bridge_benchmark_audit_2026-09-14/REVIEW.md).
8. Run 01: trained simple frozen-embedding and expression heads. Within-flight association
   was learnable, but unseen-flight transfer failed. See
   [`../workstreams/spaceflight/runs/01_frozen_head/REPORT.md`](../workstreams/spaceflight/runs/01_frozen_head/REPORT.md).
9. Run 02: reproduced the failure, verified labels and GPU scores, and tested bounded
   remedies. The failure reflected cross-flight geometry rather than an implementation
   error. See [`../workstreams/spaceflight/runs/02_diagnostics/REPORT.md`](../workstreams/spaceflight/runs/02_diagnostics/REPORT.md).
10. Run 03: computed and numerically checked experiment-specific input-gene attribution
    for the frozen GSE298393 classifier. See
    [`../workstreams/spaceflight/runs/03_gene_attribution/REPORT.md`](../workstreams/spaceflight/runs/03_gene_attribution/REPORT.md).
11. Run 04: converted signed gene evidence into a worked per-sample accounting example.
    These shares are attribution accounting, not calibrated confidence or causal fractions.
    See [`../workstreams/spaceflight/runs/04_gene_evidence_shares/EXAMPLE.md`](../workstreams/spaceflight/runs/04_gene_evidence_shares/EXAMPLE.md).
12. Run 05: completed 6,048 response-program checks. Muscle remodeling was the clearest
    tested contributor, but most positive evidence remained outside the six-program
    vocabulary. See
    [`../workstreams/spaceflight/runs/05_response_explanations_2026-09-14/REVIEW.md`](../workstreams/spaceflight/runs/05_response_explanations_2026-09-14/REVIEW.md).
13. Run 06: evaluated controlled exposures. One irradiation-associated probe was useful
    within a narrow context, but stress specificity and cross-context transfer were
    inadequate. See
    [`../workstreams/spaceflight/runs/06_controlled_exposure_validation_2026-09-14/REPORT.md`](../workstreams/spaceflight/runs/06_controlled_exposure_validation_2026-09-14/REPORT.md).

## September 15 — robustness, tissue-matched control, and repository maintenance

14. Run 07: strengthened the narrow irradiation result. A common-count BridgeRNA head
    recognized a head-held-out IMR90 study at 6h and 24h; the 24h result survived deleting
    each entire training file. Specificity remained inadequate. See
    [`../workstreams/spaceflight/runs/07_radiation_robustness_audit_2026-09-15/REPORT.md`](../workstreams/spaceflight/runs/07_radiation_robustness_audit_2026-09-15/REPORT.md).
15. Run 08: added seven paired human-muscle EPS/control donors. The irradiation probe
    responded to non-radiation stimulation and reversed flight direction across missions,
    ruling out a radiation-specific interpretation of the working flight head. See
    [`../workstreams/spaceflight/runs/08_muscle_response_alignment_2026-09-15/REPORT.md`](../workstreams/spaceflight/runs/08_muscle_response_alignment_2026-09-15/REPORT.md).
16. Verified that no job remained running. Removed the 58 GB local ARCHS4 matrix only
    after its public S3 object matched the frozen size, ETag, and modification-time
    contract in the Summer recovery document.
17. Pushed the Summer/Fall layout to GitHub (`c4d348f`) and then pushed a complete Fall
    pre-cleanup snapshot (`6012dcb`). Consolidated documentation and removed redundant,
    public, or reproducible local intermediates from the active branch.

## Current stopping point

No next experiment has been authorized or queued. The next action is to select one bounded
biological question and confirm its independent controls using [`ROADMAP.md`](ROADMAP.md).

