"""Render experiment-specific attribution summaries with explicit robustness limits."""
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from analyze_space_head_attribution import ROOT,OUT,DIAG

def run():
 gene=pd.read_csv(OUT/'gene_response_summary.csv');stability=pd.read_csv(OUT/'attribution_stability.csv');faith=pd.read_csv(OUT/'faithfulness_summary.csv');paths=pd.read_csv(OUT/'pathway_attributions.csv');checks=pd.read_csv(OUT/'integration_checks.csv');fd=pd.read_csv(OUT/'finite_difference_checks.csv');score=pd.read_csv(DIAG/'adapted_head_predictions.csv');expected=score[(score.model=='bridge')&(score.target_study=='GSE298393')].set_index(['training_pool','id']).logit
 errors=[abs(row.logit-expected.loc[(row.training_pool,row.id)]) for row in checks.itertuples()];assert max(errors)<.001, max(errors)
 assert checks.passed.all(), 'Integration failed; do not promote attributions.'
 assert fd.relative_error.max()<.1,fd.to_dict('records')
 response=pd.read_csv(OUT/'response_completeness.csv')
 for row in response.itertuples():
  subset=checks[(checks.training_pool==row.training_pool)&(checks.reference==row.reference)] if row.model=='bridge' else pd.read_csv(OUT/'expression_scores.csv').query('training_pool == @row.training_pool and reference == @row.reference')
  gap=subset[subset.label==1].logit.mean()-subset[subset.label==0].logit.mean();assert abs(gap-row.attributed_flight_ground_logit_gap)<.03*max(abs(gap),1)
 # Normalize perturbation movements within each model's own reference-score gap.
 for model,filename in [('bridge','integration_checks.csv'),('expression','expression_scores.csv')]:
  sc=pd.read_csv(OUT/filename);sc=sc[sc.reference=='training_ground_mean_TPM'].set_index(['training_pool','id'])
  for i,row in faith[faith.model==model].iterrows():
   refrow=sc.loc[(row.training_pool,row.id)];denom=max(abs(refrow.logit-refrow.reference_logit),1e-10)
   faith.loc[i,'top_fraction_of_reference_gap']=row.top_signed_movement/denom
   faith.loc[i,'random_fraction_of_reference_gap']=row.random_signed_median/denom
 faith.to_csv(OUT/'faithfulness_summary.csv',index=False)
 # All genes are retained. Shortlist uses a declared descriptive robustness filter.
 namesfile=ROOT/'bridge-rna-latest/data/human_survey/hgnc_complete_set_2026-09-12.txt';h=pd.read_csv(namesfile,sep='\t',low_memory=False);names=h.drop_duplicates('symbol').set_index('symbol')['name'].to_dict()
 short=gene[(gene.model=='bridge')&gene.robust_candidate].sort_values('mean_abs_response_attribution',ascending=False).copy();short['gene_name']=short.gene.map(names).fillna('');short.to_csv(OUT/'robust_bridge_gene_shortlist.csv',index=False)
 # Save expression direction separately from contribution direction.
 inp=np.load(OUT/'attribution_inputs.npz');meta=pd.read_csv(OUT/'cohort.csv');lookup={g:i for i,g in enumerate(inp['genes'])};context=[]
 for row in short.itertuples():
  item={'gene':row.gene,'model_response_contribution':row.mean_signed_response_attribution,'gene_name':row.gene_name}
  for pool,g in meta.groupby('stratum'):
   xx=inp['x'][g.index,lookup[row.gene]];yy=g.label.to_numpy();item[pool+'_flight_minus_ground_log1pTPM']=float(xx[yy==1].mean()-xx[yy==0].mean())
  context.append(item)
 pd.DataFrame(context).to_csv(OUT/'shortlist_expression_context.csv',index=False)
 top=pd.read_csv(OUT/'perturbation_checks.csv');top=top[top.panel=='top'];wide=top.pivot(index=['training_pool','id','k'],columns='renormalized',values='signed_score_movement_toward_reference');wide.columns=['original','TPM_renormalized'];wide['same_sign']=np.sign(wide.original)==np.sign(wide.TPM_renormalized);wide.to_csv(OUT/'renormalization_sensitivity.csv')
 selected=short.head(15) if len(short) else gene[gene.model=='bridge'].sort_values('mean_abs_response_attribution',ascending=False).head(15)
 psummary=paths.groupby(['model','pathway']).agg(mean_abs=('mean_absolute_contribution','mean'),mean_signed=('signed_sum','mean'),min_signed=('signed_sum','min'),max_signed=('signed_sum','max'),n_genes=('n_genes','first')).reset_index();psummary['same_sign']=psummary.min_signed*psummary.max_signed>0;psummary.to_csv(OUT/'pathway_summary.csv',index=False)
 fig,axes=plt.subplots(2,2,figsize=(14,11),layout='constrained');ax=axes[0,0];z=selected.iloc[::-1];ax.barh(z.gene,z.mean_signed_response_attribution,color=np.where(z.mean_signed_response_attribution>0,'#ad643d','#317f9c'));ax.axvline(0,color='gray',lw=.8);ax.set_xlabel('Mean contribution to flight − ground logit gap');ax.set_title('A. Genes stable across pools and references' if len(short) else 'A. Largest genes (none meet stability filter)')
 ax=axes[0,1];p=psummary[psummary.model=='bridge'].nlargest(10,'mean_abs').iloc[::-1];ax.barh(p.pathway.str.replace('_',' '),p.mean_abs,color='#408a7c');ax.set_xlabel('Mean absolute gene contribution within set');ax.set_title('B. Pathway-associated attribution (size-normalized)');ax.tick_params(axis='y',labelsize=8)
 ax=axes[1,0]
 for j,(model,color) in enumerate([('bridge','#b36d45'),('expression','#397e98')]):
  a=faith[(faith.model==model)&(faith.k==100)];positions=np.arange(2)+(j-.5)*.25;ax.bar(positions,[a.top_fraction_of_reference_gap.median(),a.random_fraction_of_reference_gap.median()],width=.23,color=color,label=model)
 ax.axhline(0,color='gray',lw=.8);ax.set_xticks([0,1],['Top 100 attributed genes','Matched random 100']);ax.set_ylabel('Median fraction of own reference-score gap removed');ax.set_title('C. Replacing important genes tests score sensitivity');ax.legend(frameon=False)
 ax=axes[1,1]
 for j,(model,color) in enumerate([('bridge','#b36d45'),('expression','#397e98')]):
  for k,comp in enumerate(['reference','pool_and_or_reference']):
   s=stability[(stability.model==model)&(stability.comparison==comp)];ax.scatter(np.full(len(s),k+(j-.5)*.15)+np.linspace(-.03,.03,len(s)),s.spearman,color=color,s=45,label=model if k==0 else None)
 ax.set_ylim(-1.05,1.05);ax.axhline(0,color='gray',lw=.8);ax.set_xticks([0,1],['Change reference','Change pool / reference']);ax.set_ylabel('Signed gene-attribution Spearman correlation');ax.set_title('D. Attribution stability');ax.legend(frameon=False)
 fig.suptitle('Which genes support the repeat-flight classifier?\nGSE298393 · 12 chips · reciprocal held-out pools · fixed heads · exploratory model evidence',fontsize=14)
 fig.savefig(OUT/'attribution_summary.png',dpi=170);fig.savefig(OUT/'attribution_summary.pdf');plt.close(fig)
 # Per-sample raw contribution views for the primary (YA-trained) head and ground reference.
 a=np.load(OUT/'attributions.npz');rows=pd.read_csv(OUT/'attribution_rows.csv');sel=rows[(rows.training_pool=='YA')&rows.reference.eq('training_ground_mean_TPM')];lookup={g:i for i,g in enumerate(a['genes'])};glist=selected.head(15).gene.tolist();mat=a['attributions'][sel.index][:,[lookup[g] for g in glist]].T
 fig,ax=plt.subplots(figsize=(9,6.5),layout='constrained');limit=np.max(np.abs(mat));im=ax.imshow(mat,cmap='RdBu_r',vmin=-limit,vmax=limit,aspect='auto');ax.set_yticks(range(len(glist)),glist);ax.set_xticks(range(len(sel)),[i.split(':')[1]+'\n'+('Flight' if y else 'Ground') for i,y in zip(sel.id,sel.label)],rotation=30,ha='right');fig.colorbar(im,ax=ax,label='Contribution to flight logit relative to training ground mean');ax.set_title('Primary head: genes supporting individual held-out OS chips\nPositive contribution raises the flight score; negative lowers it');fig.savefig(OUT/'per_sample_gene_contributions.pdf');fig.savefig(OUT/'per_sample_gene_contributions.png',dpi=170);plt.close(fig)
 result={'passed':True,'paths':len(checks),'score_reproduction_max_abs_error':max(errors),'integration_max_abs_residual':checks.completeness_residual.abs().max(),'integration_max_relative_L1_change':checks.relative_L1_change.max(),'finite_difference_max_relative_error':fd.relative_error.max(),'stable_bridge_gene_count':len(short),'encoder_updated':False,'head_updated':False}
 (OUT/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));print('TOP PATHWAYS');print(psummary[psummary.model=='bridge'].nlargest(10,'mean_abs').to_string(index=False))
if __name__=='__main__':run()
