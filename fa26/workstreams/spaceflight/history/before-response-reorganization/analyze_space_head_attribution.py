"""Analyze experiment-specific gene attributions; no causal or independent-validation claims."""
from pathlib import Path
import json,itertools
import numpy as np,pandas as pd
from scipy.stats import spearmanr
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'artifacts/space_head_attribution_2026-09-14';DIAG=ROOT/'artifacts/space_head_diagnostics_2026-09-14'

def expression():
 d=np.load(OUT/'attribution_inputs.npz');folds=json.loads((OUT/'folds.json').read_text());rows=[];attrs=[];scores=[];pert=[];rng=np.random.default_rng(1701);common=d['common'];geneix=np.flatnonzero(common);x=np.nan_to_num(d['x'],nan=-10)
 for fold in folds:
  pool=fold['training_pool'];w=d[f'{pool}_expression_weight'];b=d[f'{pool}_expression_bias'];refs=d[f'{pool}_references'];tr=np.array(fold['train_indices']);means=x[tr][:,common].mean(0);sds=x[tr][:,common].std(0);bins=np.digitize(means,np.quantile(means,[.2,.4,.6,.8]))*5+np.digitize(sds,np.quantile(sds,[.2,.4,.6,.8]));lookup={int(j):int(k) for j,k in zip(geneix,bins)}
  for i in fold['test_indices']:
   fx=float(x[i,common]@w+b)
   for ri,ref in enumerate(refs):
    a=np.zeros(len(common));a[common]=(x[i,common].astype(float)-ref[common])*w;fr=float(ref[common]@w+b);assert np.isclose(a.sum(),fx-fr,atol=1e-6)
    tag={'training_pool':pool,'id':str(d['ids'][i]),'sample_index':i,'label':int(d['labels'][i]),'reference':fold['reference_names'][ri]};rows.append(tag);attrs.append(a);scores.append({**tag,'logit':fx,'reference_logit':fr,'attribution_sum':float(a.sum())})
    if ri==0:
     sign=1 if fx-fr>=0 else -1
     for k in [25,100]:
      top=geneix[np.argsort(-np.abs(a[common]))[:k]]
      for rep in range(-1,20):
       if rep==-1:ix=top
       else:
        selected=[];used=set(top.tolist())
        for j in top:
         candidates=[v for v in geneix[bins==lookup[int(j)]] if int(v) not in used]
         if not candidates:candidates=[v for v in geneix if int(v) not in used]
         pick=int(rng.choice(candidates));selected.append(pick);used.add(pick)
        ix=np.array(selected)
       change=float(a[ix].sum());pert.append({**tag,'k':k,'panel':'top' if rep==-1 else 'matched_random','replicate':rep,'signed_score_movement_toward_reference':sign*change,'absolute_logit_change':abs(change),'observed_logit_change':change,'renormalized':False})
 np.savez_compressed(OUT/'expression_attributions.npz',attributions=np.array(attrs),genes=d['genes']);pd.DataFrame(rows).to_csv(OUT/'expression_attribution_rows.csv',index=False);pd.DataFrame(scores).to_csv(OUT/'expression_scores.csv',index=False);pd.DataFrame(pert).to_csv(OUT/'expression_perturbation_checks.csv',index=False)
 print('Expression analytic attributions and matched perturbations complete.')

def analyze():
 d=np.load(OUT/'attribution_inputs.npz');genes=d['genes'];common=d['common'];folds=json.loads((OUT/'folds.json').read_text());allresponses={};allloo={};gene_tables=[];stabilities=[];pathrows=[];modules=json.loads((DIAG/'modules.json').read_text());effectrows=[]
 for model,prefix in [('bridge',''),('expression','expression_')]:
  attrs=np.load(OUT/(prefix+'attributions.npz'))['attributions'];rows=pd.read_csv(OUT/(prefix+'attribution_rows.csv'));assert attrs.shape==(24,15165) and np.isfinite(attrs).all()
  responses=[];loo=[];tags=[]
  for (pool,ref),g in rows.groupby(['training_pool','reference'],sort=True):
   ix=g.index.to_numpy();a=attrs[ix];y=g.label.to_numpy();response=a[y==1].mean(0)-a[y==0].mean(0);responses.append(response);tags.append((pool,ref));dels=[]
   for j in range(6):
    keep=np.arange(6)!=j;dels.append(a[(y==1)&keep].mean(0)-a[(y==0)&keep].mean(0))
   loo.append(dels);effectrows.append({'model':model,'training_pool':pool,'reference':ref,'attributed_flight_ground_logit_gap':float(response.sum())})
   for mod in modules:
    mi=np.array(mod['indices']);pathrows.append({'model':model,'training_pool':pool,'reference':ref,'pathway':mod['name'],'n_genes':len(mi),'signed_sum':float(response[mi].sum()),'mean_absolute_contribution':float(np.abs(response[mi]).mean()),'absolute_mass_fraction':float(np.abs(response[mi]).sum()/np.abs(response[common]).sum()),'positive_fraction':float((response[mi]>0).mean())})
  responses=np.array(responses);loo=np.array(loo);allresponses[model]=responses;allloo[model]=loo
  for i,j in itertools.combinations(range(4),2):
   topi=set(np.flatnonzero(common)[np.argsort(-np.abs(responses[i,common]))[:100]]);topj=set(np.flatnonzero(common)[np.argsort(-np.abs(responses[j,common]))[:100]])
   stabilities.append({'model':model,'case1':'|'.join(tags[i]),'case2':'|'.join(tags[j]),'comparison':'reference' if tags[i][0]==tags[j][0] else 'pool_and_or_reference','spearman':float(spearmanr(responses[i,common],responses[j,common]).statistic),'top100_overlap':len(topi&topj),'top100_jaccard':len(topi&topj)/len(topi|topj)})
  avg=responses.mean(0);sign=np.sign(avg);same=(np.sign(responses)==sign).all(0);loostable=(np.sign(loo)==sign[None,None,:]).mean((0,1));ranks=np.stack([pd.Series(-np.abs(a)).rank(method='min').to_numpy() for a in responses]);topall=(ranks<=100).all(0)
  for j,gene in enumerate(genes):
   if common[j]:gene_tables.append({'model':model,'gene':gene,'mean_signed_response_attribution':float(avg[j]),'mean_abs_response_attribution':float(np.abs(responses[:,j]).mean()),'same_sign_all_pools_references':bool(same[j]),'leave_one_chip_sign_fraction':float(loostable[j]),'worst_abs_rank':float(ranks[:,j].max()),'top100_all_pools_references':bool(topall[j]),'robust_candidate':bool(same[j] and loostable[j]>=.9 and topall[j])})
  # Preserve full per-chip inputs and signed attributions, including ground samples.
  records=[]
  for k,row in rows.iterrows():
   for j in np.flatnonzero(common):records.append({'model':model,'id':row.id,'training_pool':row.training_pool,'reference':row.reference,'label':row.label,'gene':genes[j],'IG_logit_contribution':attrs[k,j]})
  pd.DataFrame(records).to_csv(OUT/f'{model}_gene_attributions.csv.gz',index=False)
 pd.DataFrame(gene_tables).to_csv(OUT/'gene_response_summary.csv',index=False);pd.DataFrame(stabilities).to_csv(OUT/'attribution_stability.csv',index=False);pd.DataFrame(pathrows).to_csv(OUT/'pathway_attributions.csv',index=False);pd.DataFrame(effectrows).to_csv(OUT/'response_completeness.csv',index=False)
 # Compare the two model families on the same four cases; coefficients live on input genes.
 cross=[]
 for k,(pool,ref) in enumerate(tags):
  a,b=allresponses['bridge'][k],allresponses['expression'][k];ia=set(np.flatnonzero(common)[np.argsort(-np.abs(a[common]))[:100]]);ib=set(np.flatnonzero(common)[np.argsort(-np.abs(b[common]))[:100]]);cross.append({'training_pool':pool,'reference':ref,'signed_response_spearman':float(spearmanr(a[common],b[common]).statistic),'top100_overlap':len(ia&ib)})
 pd.DataFrame(cross).to_csv(OUT/'bridge_expression_comparison.csv',index=False)
 faith=[]
 for model,prefix in [('bridge',''),('expression','expression_')]:
  p=pd.read_csv(OUT/(prefix+'perturbation_checks.csv'));p=p[~p.renormalized]
  for (pool,ident,k),g in p.groupby(['training_pool','id','k']):
   top=g[g.panel=='top'].iloc[0];rand=g[g.panel=='matched_random'];faith.append({'model':model,'training_pool':pool,'id':ident,'k':int(k),'top_signed_movement':top.signed_score_movement_toward_reference,'random_signed_median':rand.signed_score_movement_toward_reference.median(),'random_fraction_less_than_top':float((rand.signed_score_movement_toward_reference<top.signed_score_movement_toward_reference).mean()),'top_absolute_change':top.absolute_logit_change,'random_absolute_median':rand.absolute_logit_change.median()})
 pd.DataFrame(faith).to_csv(OUT/'faithfulness_summary.csv',index=False)
 print('ROBUST GENES');g=pd.DataFrame(gene_tables);print(g[(g.model=='bridge')&g.robust_candidate].sort_values('mean_abs_response_attribution',ascending=False).head(20).to_string(index=False));print('STABILITY');print(pd.DataFrame(stabilities).to_string(index=False));print('FAITHFULNESS');print(pd.DataFrame(faith).groupby(['model','k'])[['top_signed_movement','random_signed_median','random_fraction_less_than_top']].median().to_string())

if __name__=='__main__':
 import sys
 if sys.argv[1]=='expression':expression()
 else:analyze()
