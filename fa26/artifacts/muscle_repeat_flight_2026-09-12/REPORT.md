# Human muscle-chip repeat-flight check — reviewed September 13, 2026

**The broad flight-response direction does not repeat across the two flights. A narrower gene-level lead, MYH1 decrease, does persist in both donor pools.** This supports a focused mentor discussion about common genes versus experiment-specific global responses, rather than promotion of a universal model signature.

[Reviewed figure](cross_flight_pattern_reviewed.pdf) · [Updated Monday brief](../general_survey_2026-09-12/MONDAY-DISCUSSION.md)

## Design and execution

Compared the 12 non-stimulated muscle-chip samples from GSE234465 with all 12 No E-stim Day21 samples from GSE298393: three flight and three ground chips in each young/active (YA) or old/sedentary (OS) pool per study. Replicate chips reuse donor pools; age and activity vary together. Day2 and electrically stimulated samples were excluded before inference. The protocol, sample IDs and gene panel were frozen in `protocol.json` before later-flight outcomes.

The same frozen BridgeRNA `r7hnr92k`, pinned author source and final hidden mean/std summaries were used. The A100 on moe-reboot completed the new 12-sample inference in 8.1 seconds. No training ran. Ordered IDs, finite outputs, local/VM hashes, input/source hashes and identical checkpoint/source provenance passed verification. The VM shows no active GPU compute process.

## Overall response: consistent within experiments, different across flights

A direction is the flight-minus-ground group-mean vector. Cosine +1 means agreement and −1 means opposition. These are descriptive geometry measures, not p-values or classification scores.

| Readout | YA cross-flight cosine | OS cross-flight cosine |
|---|---:|---:|
| Expression, 15,137 common observed genes | −0.185 | −0.402 |
| BridgeRNA mean | −0.686 | −0.963 |
| BridgeRNA std | −0.306 | −0.722 |

Both flights show strong within-experiment split consistency. All 9 balanced splits agree for expression in every pool/flight and for both model summaries in the original flight. In the later flight, OS agrees in 9/9 splits for both summaries; YA agrees in 7/9 for model mean and 9/9 for model std.

The cross-flight disagreement is not driven by one chip: deleting one chip from each flight in all 36 combinations leaves model-mean cosines negative throughout, ranging −0.856 to −0.359 in YA and −0.974 to −0.946 in OS. OS expression/std also remain negative in every deletion pair. YA expression is slightly positive in one pair and YA model std in six pairs, so their negative directions are less stable. See `cross_flight_direction.csv` and `within_flight_robustness.csv`.

## Normalization and missingness checks

The later matrix is named `rawmatrix` but GEO describes its units as FPKM. We followed that annotation: rescaled observed canonical FPKM to sum to one million, then applied log1p, without dividing by gene length again. Stable-ID coverage is 99.815% (28 missing positions). Missing positions receive the model's training mask token. Switching missing genes to zero as a sensitivity changes shift magnitude/direction by less than 0.52%, with direction cosines above 0.99998.

Because the original flight used counts divided by the supplied exon lengths, review added a **post-run, expression-only sensitivity** using the authors' FPKM table for the original flight as well. With source FPKM on both sides, cross-flight cosines remain negative: **YA −0.192, OS −0.376**, and all 36 chip-deletion combinations are negative in both pools. This reduces concern that the expression disagreement arose solely from the different first-flight normalization route. It does not independently establish the later file's true units, harmonize all processing, or test new model embeddings under the alternate route. See `source_FPKM_sensitivity.csv`.

## A narrower positive lead: MYH1

Among the nine genes prespecified for this check, MYH1 decreases in both pools in both flights, and its sign survives every single-chip deletion in all four contrasts.

| Pool | First flight shift | Later flight shift |
|---|---:|---:|
| YA | −0.431 | −0.752 |
| OS | −1.760 | −0.489 |

Values are differences in log1p(TPM), not log2 fold changes. The first flight's alternate source-FPKM calculation also retains the decrease (YA −0.445; OS −1.624). Other selected genes differ: ACTN3 and ANKRD2 switch from decreasing to increasing in both pools; NMRK2 switches from increasing to decreasing. All nine candidates and their deletion checks are saved, including failures, in `prespecified_gene_shifts.csv`, `gene_panel_leave_one_out.csv`, and `first_flight_FPKM_gene_panel.csv`.

MYH1 is a candidate for a small follow-up, not a novel validated biomarker or attribution of the model's response. The original paper already discusses MYH1 changes. [Original muscle-chip study](https://www.nature.com/articles/s41526-023-00322-y).

## What to discuss Monday

1. Should we focus on a small common gene pattern, starting with MYH1, rather than a whole-embedding flight signature?
2. Can duration, hardware, maturation, handling, or processing differences explain the opposing global responses? The first flight reported hardware difficulties and incubator ground controls; the later study used the same CubeLab hardware for its ground run. Shared donor pools remain a limitation. [Later study](https://pmc.ncbi.nlm.nih.gov/articles/PMC12277833/).
3. Would a cleaner human experiment with onboard 1g controls, or the mouse-muscle collection-time audit, be a more informative next test?

These data establish neither causal microgravity effects nor a biological reversal between missions. Later GSMs are absent from the supplied training catalog, but actual checkpoint exposure is not independently proven. No model superiority claim or full powered evaluation is warranted.

## Reproduction and completion

From the project root, `muscle_repeat_flight.py analyze` with this output directory and the general-survey baseline reproduces the original calculations. `python3 fa26/review_repeat_flight.py` reproduces the post-run FPKM/gene checks and reviewed figure using the saved source FPKM table. The source table is [GSE234465 FPKM](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE234465); the later sample annotations are saved in `GSE298393_samples.soft` from [GSE298393](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE298393).

Scientific review and the Monday/Fall handoff updates are complete. No further computation is queued for this bounded comparison. The watcher is paused.
