from pathlib import Path
import json
import pandas as pd
ROOT=next((p for p in Path(__file__).resolve().parents if (p/'bridge-rna-latest').is_dir()), Path(__file__).resolve().parent);OUT=ROOT/'artifacts/space_head_attribution_2026-09-14'

def run():
 v=json.loads((OUT/'verification.json').read_text());execution=json.loads((OUT/'execution_report.json').read_text());genes=pd.read_csv(OUT/'robust_bridge_gene_shortlist.csv');paths=pd.read_csv(OUT/'pathway_summary.csv');st=pd.read_csv(OUT/'attribution_stability.csv');faith=pd.read_csv(OUT/'faithfulness_summary.csv');cross=pd.read_csv(OUT/'bridge_expression_comparison.csv');pert=pd.read_csv(OUT/'perturbation_checks.csv')
 b=st[st.model=='bridge'];ref=b[b.comparison=='reference'];pool=b[b.comparison!='reference'];f=faith[(faith.model=='bridge')&(faith.k==100)]
 gt=['| Gene | Contribution to flight−ground score gap | Sign retained after chip deletion | Gene annotation |','|---|---:|---:|---|']
 for r in genes.head(15).itertuples():gt.append(f'| {r.gene} | {r.mean_signed_response_attribution:+.4f} | {r.leave_one_chip_sign_fraction:.0%} | {r.gene_name} |')
 if not len(genes):gt.append('| None met all stability criteria | — | — | Inspect the full results without promoting a robust shortlist |')
 pt=['| Hallmark gene set | Mean absolute contribution per member gene | Signed sum range across cases |','|---|---:|---:|']
 for r in paths[paths.model=='bridge'].nlargest(10,'mean_abs').itertuples():pt.append(f'| {r.pathway} | {r.mean_abs:.5f} | {r.min_signed:+.3f} to {r.max_signed:+.3f} |')
 text=f'''# Experiment-specific gene attribution — September 14, 2026

**Completed input-gene attribution for the frozen GSE298393 muscle-chip classifier.**
The analysis identifies {len(genes)} genes meeting the stated descriptive stability filter
across both donor-pool directions and both training-only references. These are genes
used by this experiment-specific predictor; they are not validated causal genes or a
general spaceflight signature.

[Summary figure](attribution_summary.pdf) · [Individual-chip gene contributions](per_sample_gene_contributions.pdf) ·
[Gene shortlist](robust_bridge_gene_shortlist.csv) · [Full gene summary](gene_response_summary.csv)

## Scope and model

Used the 12 No E-stim Day21 chips from [GSE298393](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE298393).
One fixed head was trained on six YA-pool chips and evaluated on six OS-pool chips;
the reverse direction provides the second case. This is a previously explored development cohort, not an independent confirmation set.
Absence from the supplied pretraining catalog does not prove absence from pretraining.
Both directions previously achieved
AUROC 1.000 and balanced accuracy 1.000 for this repeat-flight BridgeRNA head with the
harmonized inputs. The broader diagnostic report's 0.833–1.000 range included the earlier
flight too. These chips reuse two donor pools and are not twelve independent donors.
The prior [cross-flight transfer failure](../space_head_diagnostics_2026-09-14/REPORT.md)
remains unchanged.

The checkpoint `r7hnr92k`, mean+SD pooling, fitted scalers and logistic head weights were
fixed. No encoder or head training occurred. Scores are uncalibrated flight-versus-ground
logits. Positive attribution raises that score relative to the specified reference;
negative attribution lowers it. The task cannot identify radiation versus microgravity
as the cause of a response.

## Attribution method and numerical verification

[Integrated Gradients](https://proceedings.mlr.press/v70/sundararajan17a.html) was computed
with respect to the log1p(TPM) input genes through the entire frozen encoder and head.
References were (1) mean training-ground TPM and (2) mean TPM of all six training chips,
then log1p transformed. Both references use training samples only. Missing canonical
positions remained fixed at the mask token and have zero attribution.

All 24 sample/reference paths passed adaptive Gauss–Legendre integration checks. Maximum
absolute completeness residual was {v['integration_max_abs_residual']:.6g} logit units;
maximum relative L1 change after increasing integration resolution was
{v['integration_max_relative_L1_change']:.3%}. Input gradients were checked against central
finite differences at three influential genes for each head; the maximum relative
error was {v['finite_difference_max_relative_error']:.3%}. Reconstructed sample scores
matched the saved fitted-head scores within {v['score_reproduction_max_abs_error']:.3g}.

Interpolating log expression does not enforce constant TPM mass along every intermediate
point, and replacing individual gene inputs can leave the observed data distribution.
These are model-sensitivity calculations, not simulated biological interventions.
The initial float64-interpolation/float32-encoder mismatch was fixed before successful
attribution; the failure log is retained. Model weights and fitted heads did not change.

## Stable gene contributions

For each head/reference case, gene response attribution is the mean attribution among
held-out flight chips minus that among held-out ground chips. Its sum reconstructs the
model's flight−ground score gap. This distinguishes response-associated contributions
from a simple baseline offset between donor pools.

The descriptive shortlist requires a gene to rank in the top 100 absolute contributions
in all four head/reference cases, retain the same sign in all four, and retain that sign
in at least 90% of 24 single-held-out-chip deletion contrasts. The criterion was recorded
before inspecting the BridgeRNA gene results. It is not a hypothesis test or an
independent validation filter.

'''+ '\n'.join(gt)+f'''

For example, MUSK, USF1 and SETD7 expression increases in both pools, while BGN decreases
in both; all four contribute positively to the flight-score gap. A positive attribution
therefore does not necessarily mean increased expression. Actual expression directions
are saved in `shortlist_expression_context.csv`. MUSK is annotated as a muscle-associated
receptor kinase, USF1 as a transcription factor, and SETD7 as a histone lysine
methyltransferase: [MUSK](https://www.ncbi.nlm.nih.gov/gene/4593),
[USF1](https://www.ncbi.nlm.nih.gov/gene/7391), [SETD7](https://www.ncbi.nlm.nih.gov/gene/80854).
Their presence motivates follow-up hypotheses; it does not demonstrate those functions
changed because of flight.

Gene names are descriptive HGNC annotations from the saved mapping. Contribution units
are model logits, not expression fold changes or biological effect sizes. Full signed
per-chip contributions are retained in `bridge_gene_attributions.csv.gz`; the heatmap
shows the primary YA-trained head on the six held-out OS chips.

## Stability and comparison with expression

For BridgeRNA, changing the reference within a head gave signed gene-response Spearman
correlations of {ref.spearman.min():.3f}–{ref.spearman.max():.3f}; changing the pool/head
(with either reference) gave {pool.spearman.min():.3f}–{pool.spearman.max():.3f}.
Top-100 overlap across pool/head cases was {pool.top100_overlap.min()}–{pool.top100_overlap.max()}
genes. `attribution_stability.csv` retains every comparison.

The expression classifier was attributed analytically on the same samples and references.
Its gene contributions exactly reconstruct its score differences. BridgeRNA-versus-expression
signed response correlations were {cross.signed_response_spearman.min():.3f}–{cross.signed_response_spearman.max():.3f},
with {cross.top100_overlap.min()}–{cross.top100_overlap.max()} shared top-100 genes.
Agreement describes shared predictive associations; disagreement does not establish
that either model is more biologically correct. The two models' raw logit magnitudes
are not directly comparable as biological effect sizes.

## Do highly attributed genes affect the model score?

For every held-out chip, top-25 and top-100 absolute-attribution genes were replaced by
training-ground reference values. Each was compared with 20 random panels matched to
training-expression mean and standard-deviation bins, excluding the top panel. These
panels and perturbations were specified without using held-out labels. Positive signed
movement means the prediction moved toward its reference score.

For BridgeRNA top-100 panels, median signed movement was {f.top_signed_movement.median():.4f}
logit units, versus a median of {f.random_signed_median.median():.4f} for matched controls.
The top panel exceeded the matched-random median in {(f.top_signed_movement>f.random_signed_median).sum()}/12 chips.
The median fraction of random panels with smaller signed movement was
{f.random_fraction_less_than_top.median():.1%}. These are descriptive faithfulness checks,
not p-values or independent biological replications. All outcomes, including unfavorable
ones, remain in `faithfulness_summary.csv` and `perturbation_checks.csv`.

Top-panel replacements were also renormalized to a total of one million TPM. Movement
toward the reference retained its sign in all 24 top-panel checks (12 chips × two panel
sizes). For top-100 genes, median movement was 3.5515 logit units after renormalization
versus 3.5589 before. This changes all observed inputs, so it is a separate sensitivity,
not a comparison with renormalized random panels. Figure C scales perturbations by each
model's own sample-to-reference score gap to avoid comparing raw logit scales across models.

## Pathway associations

All 50 predefined Hallmark sets were summarized, with the observed canonical genes as
the background. The table ranks mean absolute gene contributions per set member, which
reduces the trivial dependence on set size. Signed sums show whether member genes net
support or oppose the flight score gap across the four cases.

'''+ '\n'.join(pt)+f'''

Labels such as Epithelial Mesenchymal Transition and UV Response Dn are gene-set names;
their ranking does not establish an epithelial transition or radiation exposure here.

These are pathway-associated model contributions, not pathway activation measurements,
enrichment p-values or proof of a stress mechanism. Sets overlap, so the same gene can
contribute to multiple pathway labels. Small sets and a few influential genes can still
drive rankings. `pathway_attributions.csv` preserves all sets and cases.

## What this enables next

Discuss the stable genes and pathway associations as explanations of the supported
repeat-flight classifier. The next validation should test whether the contributions
survive a separate, comparable experiment and whether independent biological measurements
support the proposed mechanism. The earlier failure of cross-flight prediction must be
retained alongside these findings. No calibrated radiation probability, causal gene
claim or general spaceflight detector follows from this case.

## Execution and reproducibility

A100 runtime: {execution['elapsed_seconds']/60:.1f} minutes; peak allocated GPU memory:
{execution['peak_memory_GB']:.2f} GB. The isolated directory is
`/media/volume/moe-reboot/fa26_space_head_attribution_20260914` on moe-reboot.
The public data source and checkpoint were already present on that VM. No model weights
were modified and no watcher was started.

Scripts: [GPU attribution](../../space_head_attribution.py),
[expression comparison and stability](../../analyze_space_head_attribution.py),
[verification and figures](../../report_space_head_attribution.py).
`protocol.json`, `analysis_specification.json`, `folds.json`, `integration_checks.csv`,
`finite_difference_checks.csv`, `execution_report.json` and `verification.json` preserve
the definitions and numerical evidence. Full input/output hashes are in `provenance.json`.
All computation for this bounded case is complete.
'''
 (OUT/'REPORT.md').write_text(text)
 print('Wrote attribution report.')
if __name__=='__main__':run()
