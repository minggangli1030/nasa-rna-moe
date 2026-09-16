"""Convert saved input attributions into descriptive per-sample evidence shares."""
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'artifacts/space_head_attribution_2026-09-14'
OUT=ROOT/'artifacts/space_prediction_explanations_2026-09-14'

def run():
 OUT.mkdir(exist_ok=True);a=np.load(SOURCE/'attributions.npz');rows=pd.read_csv(SOURCE/'attribution_rows.csv');checks=pd.read_csv(SOURCE/'integration_checks.csv');inp=np.load(SOURCE/'attribution_inputs.npz');modules=json.loads((ROOT/'artifacts/space_head_diagnostics_2026-09-14/modules.json').read_text());genes=a['genes'];members=[[] for _ in genes]
 for k,m in enumerate(modules):
  for j in m['indices']:members[j].append(k)
 names=[m['name'] for m in modules]+['Outside these 50 Hallmark sets'];geneout=[];pathout=[];pred=[]
 for i,row in rows.iterrows():
  v=a['attributions'][i];positive=np.maximum(v,0);negative=np.maximum(-v,0);total=positive.sum()+negative.sum();support=positive.sum();opposition=negative.sum();assert total>0 and support>0 and opposition>0
  tag={'id':row.id,'training_pool':row.training_pool,'reference':row.reference};c=checks[(checks.id==row.id)&(checks.training_pool==row.training_pool)&(checks.reference==row.reference)].iloc[0]
  pospath=np.zeros(len(names));negpath=np.zeros(len(names))
  for j in np.flatnonzero(inp['common']):
   geneout.append({**tag,'gene':genes[j],'signed_logit_contribution':float(v[j]),'percent_of_supporting_attribution':float(100*positive[j]/support),'percent_of_opposing_attribution':float(100*negative[j]/opposition),'percent_of_absolute_attribution':float(100*abs(v[j])/total)})
   slots=members[j] or [len(names)-1]
   for k in slots:pospath[k]+=positive[j]/len(slots);negpath[k]+=negative[j]/len(slots)
  assert np.isclose(pospath.sum(),support) and np.isclose(negpath.sum(),opposition)
  for k,name in enumerate(names):pathout.append({**tag,'pathway':name,'percent_of_supporting_attribution':float(100*pospath[k]/support),'percent_of_opposing_attribution':float(100*negpath[k]/opposition),'positive_logit_contribution':pospath[k],'negative_logit_contribution':negpath[k]})
  pred.append({**tag,'known_label':int(row.label),'predicted_label':'flight' if c.logit>=0 else 'ground','logit':c.logit,'uncalibrated_sigmoid_score':float(1/(1+np.exp(-c.logit))),'reference_logit':c.reference_logit,'supporting_logit_contributions':support,'opposing_logit_contribution_magnitude':opposition,'net_attributed_logit_change':float(v.sum()),'percent_positive_of_absolute_attribution':float(100*support/total),'percent_negative_of_absolute_attribution':float(100*opposition/total),'reconstruction_residual':float(c.logit-(c.reference_logit+v.sum()))})
 gene=pd.DataFrame(geneout);path=pd.DataFrame(pathout);prediction=pd.DataFrame(pred)
 for data in [gene,path]:
  sums=data.groupby(['id','training_pool','reference'])[['percent_of_supporting_attribution','percent_of_opposing_attribution']].sum();assert np.allclose(sums,100)
 gene.to_csv(OUT/'gene_evidence_shares.csv.gz',index=False);path.to_csv(OUT/'pathway_evidence_shares.csv',index=False);prediction.to_csv(OUT/'prediction_explanations.csv',index=False)
 # First held-out flight chip of the predefined primary head, not the highest score.
 ident=rows[(rows.training_pool=='YA')&(rows.label==1)].id.iloc[0];ref='training_ground_mean_TPM';r=prediction[(prediction.id==ident)&(prediction.training_pool=='YA')&(prediction.reference==ref)].iloc[0];g=gene[(gene.id==ident)&(gene.training_pool=='YA')&(gene.reference==ref)];p=path[(path.id==ident)&(path.training_pool=='YA')&(path.reference==ref)]
 gt=['| Gene | Share of supporting gene attribution | Same head, alternate-reference range |','|---|---:|---:|']
 for item in g.nlargest(5,'percent_of_supporting_attribution').itertuples():
  vals=gene[(gene.id==ident)&(gene.training_pool=='YA')&(gene.gene==item.gene)].percent_of_supporting_attribution
  gt.append(f'| {item.gene} | {item.percent_of_supporting_attribution:.2f}% | {vals.min():.2f}–{vals.max():.2f}% |')
 remainder=100-g.nlargest(5,'percent_of_supporting_attribution').percent_of_supporting_attribution.sum();gt.append(f'| All other supporting genes | {remainder:.2f}% | — |')
 pt=['| Gene-set allocation | Share of supporting attribution |','|---|---:|']
 pp=p.nlargest(5,'percent_of_supporting_attribution')
 for item in pp.itertuples():pt.append(f'| {item.pathway} | {item.percent_of_supporting_attribution:.2f}% |')
 pt.append(f'| Remaining gene sets | {100-pp.percent_of_supporting_attribution.sum():.2f}% |')
 text=f'''# Prediction plus evidence shares — worked example

The classification head already exists. This report adds an explanation layer using
its saved, numerically checked input-gene attributions. It does not train another model.
All percentages below describe attribution relative to a reference profile, not causal
stress fractions or independently measured biological contributions.

## Example: {ident}

- Model prediction: **{r.predicted_label}**, within the supported GSE298393 experiment.
- Uncalibrated sigmoid score: **{r.uncalibrated_sigmoid_score:.4f}**. This is not a validated
  probability or a claim of this percentage confidence in a new flight.
- Training: six YA-pool chips; this OS-pool chip was held out from head fitting.
- Reference: mean training-ground expression. Interpretation is conditional on this reference.

### Why did the score favor flight?

The reference logit was {r.reference_logit:.3f}. Positive gene contributions totaled
+{r.supporting_logit_contributions:.3f}; opposing contributions totaled
−{r.opposing_logit_contribution_magnitude:.3f}. Their net change was
+{r.net_attributed_logit_change:.3f}, yielding the sample logit {r.logit:.3f}
(up to numerical integration error). The baseline score is shown separately; it is
not itself assigned to genes by this attribution calculation.

Of the absolute gene-attribution magnitude, {r.percent_positive_of_absolute_attribution:.1f}%
raises the score and {r.percent_negative_of_absolute_attribution:.1f}% lowers it.
The following table divides only the **supporting** contributions into shares summing to 100%:

'''+ '\n'.join(gt)+'''

For gene j, supporting share = max(IG_j, 0) / sum(max(IG, 0)). Opposing shares are
computed separately from negative contributions. These are accounting definitions,
not probabilities. Signed net percentages were avoided because cancellation can make
them exceed 100% or become unstable. Relative shares change with the reference, head
and input; the second-reference ranges illustrate one sensitivity, not confidence intervals.

### Optional pathway view

Pathways overlap. To prevent double counting, each gene's contribution is split equally
among the represented Hallmark sets containing it. Genes in none of these sets retain
an explicit outside-category allocation. This is a transparent display convention,
not a learned or causal division between biological mechanisms.

'''+ '\n'.join(pt)+'''

The gene-set labels are annotations. A UV-response share does not estimate radiation
exposure, and a myogenesis share does not quantify damage to muscle. For a claim such as
“80% radiation,” separate radiation/control supervision and independent calibration
would be required; even then the result would predict an exposure label, not the fraction
of stress caused by radiation. Current data do not identify causal shares of gravity,
radiation or other stresses.

## Next step

The prediction/explanation pipeline is now: normalized expression → frozen BridgeRNA →
fixed classification head → class score → signed gene attributions → explicitly defined
gene/pathway evidence shares. Validate the classifier and its calibration in additional
comparable data before presenting confidence percentages. Preserve the failed cross-flight
transfer case; this demonstration remains an experiment-specific research output.

Files include all 12 chips, both references, supporting and opposing gene shares, and
all pathway allocations. The example is the first held-out flight chip from the primary
head, selected by the existing manifest order. It was not selected for the best score.
'''
 (OUT/'EXAMPLE.md').write_text(text)
 provenance={'method':'Positive and negative input-IG shares separately normalized; overlapping Hallmark memberships split equally; reference logit separate','trained_new_model':False,'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [SOURCE/'attributions.npz',SOURCE/'attribution_rows.csv',SOURCE/'integration_checks.csv']},'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()};(OUT/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
 print(text[:4200])
if __name__=='__main__':run()
