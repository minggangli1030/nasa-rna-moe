# Human muscle response alignment — September 15, 2026

**Verdict: the irradiation-associated probe is not a radiation-specific explanation of the working flight classifier.** In human muscle, it responds to non-radiation electrical stimulation, and its flight/ground direction reverses between the two missions. In the working GSE298393 classifier, a *lower* irradiation-probe component supports the flight score. This is a useful model diagnostic, not evidence of less biological radiation damage.

## New tissue-matched negative control

[GSE200335](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE200335) provides primary human skeletal muscle cells from **seven donors**, with each donor's electrically stimulated culture compared with its unstimulated control (14 samples). The GEO protocol specifies 24h EPS. It is an exercise-like perturbation, not ionizing radiation or spaceflight. All seven donor pairs and treatment labels were checked against primary GEO metadata. All 14 samples occur in the supplied encoder catalog (13 train, 1 val), so this is a new challenge for the fixed heads, not fully unseen-encoder confirmation.

The fixed common-count irradiation probe:

- Scores **all 14 samples positive**, including all seven unstimulated controls. Its absolute threshold is therefore unsuitable in this muscle context.
- Increases after EPS in **6/7 donors**. Those donor-specific signs survive deleting every whole radiation-training source file, switching probe training preprocessing, and using a wider gene mask. The one decreasing donor remains decreasing.
- Thus exhibits both a muscle-context baseline shift and a reproducible non-radiation treatment response. The former must not be mistaken for an EPS-induced response; the paired comparison establishes the latter.

The two unchanged muscle flight heads decrease after EPS in the same six donors and increase in the remaining donor. Their absolute calls also vary strongly by donor/head, so EPS samples are not a validated flight-classification test. This negative-control result argues against interpreting either head's sigmoid as an exposure probability.

## Actual flight samples: response direction reverses

Primary common-count probe on matched-coverage, harmonized inputs; numbers are mean flight-minus-ground probe logits:

| Study | YA pool | OS pool |
|---|---:|---:|
| GSE234465, earlier flight | +1.613 | +2.309 |
| GSE298393, working-head flight | −2.315 | −3.391 |

Both processing routes, both probe-source versions and the original-versus-matched gene masks retain these signs. Removing any whole radiation-training expression file also retains all four signs. No study or pool was selected based on the preferred direction. These are the previously studied 24 chips from two pooled donor groups, not 24 independent donors or new confirmation of a general flight signature.

For the common-count probe, all 12 GSE298393 samples—including all six ground controls—are above its irradiation threshold. The original-processing probe calls all 12 negative. Both nevertheless agree that flight reduces the score relative to matched ground. **Absolute calls and within-context response directions answer different questions.**

## What the flight classifier actually does with this direction

We used a declared geometric diagnostic: remove the component along the fixed irradiation-probe normal relative to the flight head's training-pool ground reference, and measure the resulting change in the unchanged flight head. The test pool is always opposite the training pool for GSE298393. The projection is tested in both raw embedding coordinates and coordinates scaled using radiation training data; both original/common-count probes are retained.

Across all eight head/probe/metric combinations, increasing the irradiation-probe direction reduces the flight score. Because GSE298393 flight samples move in the opposite direction, this component **adds** to their flight-minus-ground separation:

| Held-out pool | Total flight-score gap | Projected component across probes/metrics |
|---|---:|---:|
| YA, OS-trained head | +10.085 | +0.485 to +1.557 |
| OS, YA-trained head | +12.160 | +0.591 to +1.226 |

The remaining score gap is kept as residual evidence. Each projected component plus residual exactly reconstructs the fixed score difference. The projected embedding's probe score returns to the reference score, and its flight-logit change matches the algebraic component.

This is **a property of the chosen latent-space operation**, not a validated biological intervention. The component's magnitude varies with metric and probe; it is not a unique explanation or a percentage caused by radiation. The removed coordinate can encode shared muscle/stress biology. We therefore report the signed result as “lower irradiation-associated probe component supports the score,” with its specificity failure visible, rather than calling the sample “radiation-driven.”

## Response-level lead from the new control study

Using the previously fixed six-program vocabulary, TNF/NF-kB-associated expression increases after EPS in **all seven donors**, agreeing under both mean log1p-expression and within-sample rank scoring. Myogenesis-associated expression decreases in **six of seven donors**, also agreeing under rank scoring. These are candidate transcriptional response patterns in an exercise-like intervention, not functional pathway-activity measurements or radiation-specific signatures.

Other programs are less consistent across scoring methods. All six are retained in `program_expression_shifts.csv` and `program_donor_summary.csv`. In particular, no new general flight inflammatory-response claim follows from this EPS result: the flight/pool response directions are mixed. The previous program-replacement evidence for the flight head remains the relevant model-reliance test (run05).

## Data search and scope

No clean human skeletal-muscle irradiation RNA-seq cohort was verified in this targeted search; that is not proof none exists. A public mouse 3D C2C12 candidate, **GSE318627**, includes irradiation, normal controls and unirradiated constructs co-cultured with senescent constructs. It could help distinguish direct exposure from shared downstream responses, but it has an n=2 versus n=3 metadata discrepancy, constructs sharing dishes, and unresolved timing/independence. It is documented, not silently substituted for human muscle or counted as independent validation. GSE171644 was excluded after primary GEO showed mouse rather than the human label in a secondary index. Full candidate decisions are in `candidate_audit.csv`.

## Decision and next step

Keep the 24h IMR90 irradiation-transfer finding from run07 as a narrow comparator. **Do not attach this probe as a named radiation contribution to the flight classifier.** The next usable explanation should expose transcriptional response evidence, its signed contribution to the flight model, consistency across controls and an explicit unexplained component. Exposure names require additional specificity evidence.

Prioritize a controlled human muscle radiation versus non-radiation stress dataset, with timing and controls comparable to the flight chips. The strongest immediate comparison now available is the seven-donor EPS negative control; it should be retained for every future response head. Controlled-gravity quantification remains separate. More encoder capacity is not the current remedy for unvalidated exposure meaning.

## Execution and artifacts

76 frozen-model encodings represent **38 biological samples**: 24 existing chips and 14 new EPS/control cultures; alternate preprocessing/masks are not extra samples. All primary inputs contain the same 15,061 observed genes as the radiation probe. The original flight mask had 15,137 genes; the EPS wider-mask sensitivity retained 15,132 verified mappings. Source/coverage changes preserve the main response directions.

Inference ran on moe-reboot's A100 in **26.9 seconds**. No encoder or flight-head update occurred. The four training-source-deletion probes were fitted only on prior irradiation data, never on muscle outcomes. All other scores use saved fixed heads. Projection and paired-donor analyses ran locally. The run is complete; no job remains queued.

[Summary figure](muscle_alignment.pdf) · [Protocol](protocol.json) · [Paired donor summary](donor_summary.csv) · [All sample scores](sample_scores.csv) · [Projection components](projection_components.csv) · [Coverage sensitivity](coverage_sensitivity.csv) · [Independent verification](independent_verification.json).
