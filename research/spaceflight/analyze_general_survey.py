#!/usr/bin/env python3
"""Descriptive screening and sensitivity checks; rankings are hypothesis-generating."""
import argparse,itertools,json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.decomposition import PCA
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def cosine(a,b):
 a=np.asarray(a);b=np.asarray(b);return np.sum(a*b,axis=-1)/np.maximum(np.linalg.norm(a,axis=-1)*np.linalg.norm(b,axis=-1),1e-15)

def diagnostics(z,conditions,units,paired,rng=None,b=None):
 # rng/b retained for old callers; enumerate every balanced split to avoid Monte Carlo noise.
 labels=np.asarray(conditions);n=len(z)
 if paired:
  d=[]
  for u in sorted(set(units)):
   j=np.asarray(units)==u
   if np.any(j&(labels==0)) and np.any(j&(labels==1)):d.append(z[j&(labels==1)].mean(0)-z[j&(labels==0)].mean(0))
  d=np.asarray(d);shift=d.mean(0);N=len(d);k=max(1,N//2)
  combos=list(itertools.combinations(range(N),k));splits=np.zeros((len(combos),N))
  for t,idx in enumerate(combos):splits[t,list(idx)]=1/k
  other=(1-splits*k)/(N-k);a=splits@d;c=other@d
  loo=np.array([(d.sum(0)-v)/(N-1) for v in d]);noise=np.mean(np.sum((d-shift)**2,axis=1));effective=N
 else:
  pos=np.flatnonzero(labels==1);neg=np.flatnonzero(labels==0);shift=z[pos].mean(0)-z[neg].mean(0)
  kp=max(1,len(pos)//2);kn=max(1,len(neg)//2)
  combos=list(itertools.product(itertools.combinations(pos,kp),itertools.combinations(neg,kn)))
  w1=np.zeros((len(combos),n));w2=np.zeros_like(w1)
  for t,(ip,ineg) in enumerate(combos):
   w1[t,list(ip)]=1/kp;w1[t,list(ineg)]=-1/kn
   w2[t,np.setdiff1d(pos,ip)]=1/(len(pos)-kp);w2[t,np.setdiff1d(neg,ineg)]=-1/(len(neg)-kn)
  a=w1@z;c=w2@z;loo=[]
  for i in range(n):
   p=pos[pos!=i];q=neg[neg!=i];loo.append(z[p].mean(0)-z[q].mean(0))
  loo=np.asarray(loo);noise=(np.square(z[pos]-z[pos].mean(0)).sum()+np.square(z[neg]-z[neg].mean(0)).sum())/max(1,n-2);effective=n
 split=cosine(a,c)
 return shift,{'effect_over_within_rms':float(np.linalg.norm(shift)/max(np.sqrt(noise),1e-15)),'split_positive_fraction':float(np.mean(split>0)),'split_median_cosine':float(np.median(split)),'loo_min_direction_cosine':float(np.min(cosine(loo,shift))),'resampling_unit':'donor/cell-line paired differences' if paired else 'within-condition sample splits','n_effective_units':effective,'n_balanced_splits':len(split)}


def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args();out=args.output
 m=pd.read_csv(out/'manifest.csv').fillna('');d=np.load(out/'inputs.npz');e=np.load(out/'embeddings.npz');qc=pd.read_csv(out/'sample_qc.csv')
 assert m.id.tolist()==d['ids'].tolist()==e['ids'].tolist()==qc.id.tolist()
 common=d['observed'].all(0);raw=d['x'][:,common].astype(float);genes=d['genes'][common]
 rows=[];shiftrows=[];shifts={};info=[];rng=np.random.default_rng(120926);gene_rows=[]
 for con,g in m.groupby('contrast',sort=False):
  idx=g.index.to_numpy();idx=idx[m.loc[idx,'condition'].to_numpy()<2];gg=m.loc[idx];labels=gg.condition.to_numpy();units=gg.unit.to_numpy();paired=gg.study.iloc[0] in ['GSE137081','GSE113165','GSE126865']
  n0=int((labels==0).sum());n1=int((labels==1).sum())
  desc={k:gg.iloc[0][k] for k in ['study','species','setting','tissue','material','stratum']};desc.update({'contrast':con,'n_control':n0,'n_exposed':n1,'n_training_samples':int((gg.split=='train').sum()),'n_validation_samples':int((gg.split=='val').sum())});info.append(desc)
  rep={'raw':raw[idx],'PCA8_descriptive':PCA(n_components=min(8,len(idx)-1),svd_solver='full').fit_transform(raw[idx]),'model_mean':e['mean'][idx].astype(float),'model_std':e['std'][idx].astype(float)}
  shifts[con]={}
  for name,z in rep.items():
   shift,diag=diagnostics(z,labels,units,paired,rng);shifts[con][name]=shift
   proj=z@shift;rho=spearmanr(proj,np.log1p(qc.iloc[idx].source_total)).statistic
   rows.append({**desc,'representation':name,**diag,'projection_log_count_spearman':float(rho) if np.isfinite(rho) else 0.})
  # Unknown-mask versus zero-fill sensitivity for human inference.
  if gg.species.iloc[0]=='human':
   a=e['mean'][idx][labels==1].mean(0)-e['mean'][idx][labels==0].mean(0);z=e['zero_fill_sensitivity'][idx];b=z[labels==1].mean(0)-z[labels==0].mean(0)
   shiftrows.append({**desc,'masked_vs_zero_shift_cosine':float(cosine(a,b)),'relative_shift_change':float(np.linalg.norm(a-b)/max(np.linalg.norm(a),1e-15))})
 metrics=pd.DataFrame(rows);metrics.to_csv(out/'contrast_pattern_metrics.csv',index=False);pd.DataFrame(info).to_csv(out/'contrast_inventory.csv',index=False);pd.DataFrame(shiftrows).to_csv(out/'human_missingness_sensitivity.csv',index=False)
 # Cross-study comparisons only within the same species, setting, and broad tissue.
 pairs=[]
 for left,right in itertools.combinations(info,2):
  if left['study']==right['study']:continue
  if any(left[k]!=right[k] for k in ['species','setting','tissue']):continue
  for name in ['raw','model_mean','model_std']:
   pairs.append({'contrast_a':left['contrast'],'contrast_b':right['contrast'],'study_a':left['study'],'study_b':right['study'],'species':left['species'],'setting':left['setting'],'tissue':left['tissue'],'representation':name,'response_cosine':float(cosine(shifts[left['contrast']][name],shifts[right['contrast']][name]))})
 pd.DataFrame(pairs).to_csv(out/'within_tissue_cross_study_patterns.csv',index=False)
 # Average strata within study first, so many strata do not count as independent studies.
 for (species,setting,tis),ii in pd.DataFrame(info).groupby(['species','setting','tissue']):
  bystudy=[];study_names=[]
  for study,si in ii.groupby('study'):
   bystudy.append(np.mean([shifts[c]['raw'] for c in si.contrast],axis=0));study_names.append(study)
  if len(bystudy)<2:continue
  v=np.asarray(bystudy);agree=np.maximum((v>0).sum(0),(v<0).sum(0))/len(v)
  table=pd.DataFrame({'species':species,'setting':setting,'tissue':tis,'gene':genes,'n_studies':len(v),'same_direction_fraction':agree,'median_shift':np.median(v,0),'minimum_abs_study_shift':np.min(np.abs(v),0)})
  for j,study in enumerate(study_names):table[study]=v[j]
  table=table.sort_values(['same_direction_fraction','minimum_abs_study_shift'],ascending=False).head(30);gene_rows.append(table)
 if gene_rows:pd.concat(gene_rows).to_csv(out/'recurrent_gene_candidates.csv',index=False)
 # Human cardiac line-specific flight/post-flight distance to matched ground.
 recovery=[];card=m[m.study=='GSE137081'];human_dir=[]
 for unit,g in card.groupby('unit'):
  ix=g.index.to_numpy();c=g.condition.to_numpy()
  if set(c)!={0,1,2}:continue
  for name,z in [('raw',raw),('model_mean',e['mean']),('model_std',e['std'])]:
   means={k:z[ix[c==k]].mean(0) for k in [0,1,2]};a=means[1]-means[0];b=means[2]-means[0]
   recovery.append({'line':unit,'representation':name,'post_vs_flight_distance_ratio':float(np.linalg.norm(b)/np.linalg.norm(a)),'flight_post_direction_cosine':float(cosine(a,b))})
 pd.DataFrame(recovery).to_csv(out/'human_cardiac_postflight_pattern.csv',index=False)
 # A human muscle-chip subgroup comparison (age/activity jointly vary).
 chip=[i for i in info if i['study']=='GSE234465'];chip_comp=[]
 if len(chip)==2:
  for rep in ['raw','model_mean','model_std']:chip_comp.append({'representation':rep,'YA_OS_response_cosine':float(cosine(shifts[chip[0]['contrast']][rep],shifts[chip[1]['contrast']][rep]))})
 pd.DataFrame(chip_comp).to_csv(out/'human_muscle_subgroup_pattern.csv',index=False)
 # Human-to-mouse muscle comparisons are descriptive across systems, not pooled inference.
 cross=[]
 for human in [i for i in info if i['species']=='human' and i['tissue']=='skeletal muscle']:
  for mouse in [i for i in info if i['species']=='mouse' and i['tissue']=='skeletal muscle']:
   for rep in ['raw','model_mean','model_std']:cross.append({'human':human['contrast'],'human_setting':human['setting'],'mouse':mouse['contrast'],'representation':rep,'response_cosine':float(cosine(shifts[human['contrast']][rep],shifts[mouse['contrast']][rep]))})
 pd.DataFrame(cross).to_csv(out/'cross_species_muscle_patterns.csv',index=False)
 # Readable survey map: all contrasts, ordered by tissue and study; no visual selection of favorable results.
 order=pd.DataFrame(info).sort_values(['species','setting','tissue','study','contrast']).contrast.tolist();pivot=metrics.pivot(index='contrast',columns='representation',values='split_positive_fraction').loc[order,['raw','PCA8_descriptive','model_mean','model_std']]
 fig,ax=plt.subplots(figsize=(10,max(9,len(order)*.24)),layout='constrained');im=ax.imshow(pivot.to_numpy(),vmin=0,vmax=1,cmap='viridis',aspect='auto');ax.set_xticks(range(4),['Expression','PCA8\n(descriptive)','BridgeRNA\nmean','BridgeRNA\nstd'])
 lookup={i['contrast']:i for i in info};labels=[f"{lookup[c]['species']} · {lookup[c]['study']} · {lookup[c]['material']} · {lookup[c]['stratum'].split('|')[6] if lookup[c]['study']=='OSD-457' else lookup[c]['stratum'] if lookup[c]['species']=='human' else c.split('|')[-1]} [{lookup[c]['n_control']}+{lookup[c]['n_exposed']}]" for c in order]
 ax.set_yticks(range(len(order)),labels,fontsize=6);ax.set_title('General space-biology survey: directional split-sample stability\nFraction of all balanced splits with agreeing response directions (3–400 splits)');fig.colorbar(im,ax=ax,label='Fraction positive; descriptive, not a p-value');fig.savefig(out/'survey_pattern_map.png',dpi=160);fig.savefig(out/'survey_pattern_map.pdf');plt.close(fig)
 summary={'samples':len(m),'species_counts':m.species.value_counts().to_dict(),'studies':m.study.nunique(),'contrasts':len(info),'broad_tissues':sorted(m.tissue.unique()),'common_measured_genes':int(common.sum()),'settings':m.setting.value_counts().to_dict(),'human_training_exposure':m[m.species=='human'].split.value_counts().to_dict(),'caution':'Discovery screen; split stability is not significance. 54 comparisons, no multiple-testing claims. Tissue/sex/strain/protocol and cage structure can confound. Human cardiac pre/post has timing differences; human muscle YA/OS jointly differ in age/activity. Analog results are not flight results.'}
 dump=lambda p,x:p.write_text(json.dumps(x,indent=2)+'\n');dump(out/'survey_summary.json',summary)
 print(json.dumps(summary,indent=2));print(metrics[metrics.representation=='model_mean'].sort_values('split_positive_fraction',ascending=False)[['contrast','n_control','n_exposed','split_positive_fraction','loo_min_direction_cosine','effect_over_within_rms']].head(18).to_string(index=False));print(pd.DataFrame(recovery).to_string(index=False));print(pd.DataFrame(chip_comp).to_string(index=False))
 (out/'ANALYSIS_COMPLETE').write_text('complete\n')

if __name__=='__main__':main()
