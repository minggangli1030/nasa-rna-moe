#!/usr/bin/env python3
"""Post-run normalization sensitivity and visual QA; no new model inference."""
from pathlib import Path
import json,hashlib
import numpy as np
import pandas as pd
from analyze_general_survey import cosine
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent
p=ROOT/'artifacts/muscle_repeat_flight_2026-09-12';b=ROOT/'artifacts/general_survey_2026-09-12'
d=np.load(p/'inputs.npz');bd=np.load(b/'inputs.npz');m=pd.read_csv(p/'manifest.csv');bm=pd.read_csv(b/'manifest.csv');old=bm[bm.study=='GSE234465']
f=pd.read_csv(p/'GSE234465_FPKM.txt.gz',sep='\t');o=pd.read_csv(ROOT/'bridge-rna-latest/data/ensembl/orthologs_one2one.txt',sep='\t').set_index('Human gene name').loc[d['genes']]
sid=f.GeneID.astype(str).str.split('.').str[0];assert not sid.duplicated().any();lookup={s:i for i,s in enumerate(sid)};index=np.array([lookup.get(g,-1) for g in o['Human gene stable ID']]);found=index>=0;assert found.mean()>=.99
x=[]
for row in old.itertuples():
 col=row.title.replace('GC-OS-NOES-','GC-OS-NOS-').replace('GC-YA-NOES-','GC-YA-NOS-');v=f[col].to_numpy(float)[index[found]];assert np.isfinite(v).all() and (v>=0).all();a=np.full(len(found),np.nan);a[found]=np.log1p(v/v.sum()*1e6);x.append(a)
x=np.array(x);common=found&d['observed'].all(0)&bd['observed'][old.index].all(0);rows=[]
for pool in ['YA','OS']:
 g=old[old.stratum==pool];h=m[m.stratum==pool];oldsel=old.stratum.to_numpy()==pool
 a=x[oldsel][:,common];ay=g.condition.to_numpy();new=d['x'][h.index][:,common];y=h.condition.to_numpy();a_shift=a[ay==1].mean(0)-a[ay==0].mean(0);new_shift=new[y==1].mean(0)-new[y==0].mean(0)
 original=bd['x'][g.index][:,common];original_shift=original[ay==1].mean(0)-original[ay==0].mean(0)
 loo=[]
 for i in range(6):
  aa=a[(ay==1)&(np.arange(6)!=i)].mean(0)-a[(ay==0)&(np.arange(6)!=i)].mean(0)
  for j in range(6):
   bb=new[(y==1)&(np.arange(6)!=j)].mean(0)-new[(y==0)&(np.arange(6)!=j)].mean(0);loo.append(float(cosine(aa,bb)))
 rows.append({'pool':pool,'common_genes':int(common.sum()),'both_source_FPKM_cross_flight_cosine':float(cosine(a_shift,new_shift)),'original_counts_vs_FPKM_first_flight_cosine':float(cosine(original_shift,a_shift)),'leave_one_each_min':min(loo),'leave_one_each_max':max(loo),'leave_one_each_positive_fraction':float(np.mean(np.array(loo)>0))})
pd.DataFrame(rows).to_csv(p/'source_FPKM_sensitivity.csv',index=False)
fg=[]
for pool in ['YA','OS']:
 sel=old.stratum.to_numpy()==pool;yy=old.loc[sel,'condition'].to_numpy();zz=x[sel]
 for gene in json.loads((p/'protocol.json').read_text())['gene_panel']:
  j=list(d['genes']).index(gene);fg.append({'pool':pool,'gene':gene,'first_flight_FPKM_shift':float(zz[yy==1,j].mean()-zz[yy==0,j].mean())})
pd.DataFrame(fg).to_csv(p/'first_flight_FPKM_gene_panel.csv',index=False)

# Check every gene from the predeclared panel, not just a favorable one.
meta=pd.concat([old,m],ignore_index=True);xx=np.concatenate([bd['x'][old.index],d['x']]);genepanel=json.loads((p/'protocol.json').read_text())['gene_panel'];gr=[]
for con,g in meta.groupby('contrast'):
 y=g.condition.to_numpy();z=xx[g.index]
 for gene in genepanel:
  j=list(d['genes']).index(gene);v=z[:,j]
  if not np.isfinite(v).all():continue
  delta=v[y==1].mean()-v[y==0].mean();loo=[float(v[(y==1)&(np.arange(len(y))!=i)].mean()-v[(y==0)&(np.arange(len(y))!=i)].mean()) for i in range(len(y))]
  gr.append({'gene':gene,'contrast':con,'shift':float(delta),'leave_one_min':min(loo),'leave_one_max':max(loo),'leave_one_sign_retention':float(np.mean(np.sign(loo)==np.sign(delta)))})
pd.DataFrame(gr).to_csv(p/'gene_panel_leave_one_out.csv',index=False)
c=pd.read_csv(p/'cross_flight_direction.csv');fig,ax=plt.subplots(figsize=(8,4.8),layout='constrained');names={'raw':'Expression','model_mean':'BridgeRNA mean','model_std':'BridgeRNA std'}
for j,(rep,label) in enumerate(names.items()):
 g=c[c.representation==rep].set_index('pool').loc[['YA','OS']];ax.bar(np.arange(2)+(j-1)*.23,g.cross_flight_cosine,width=.21,label=label,color=['#3875a9','#bc6238','#60976a'][j])
ax.axhline(0,color='black',lw=.7);ax.set_xticks([0,1],['Young / active pool','Old / sedentary pool']);ax.set_ylim(-1,1);ax.set_ylabel('Direction cosine: +1 agrees, −1 opposes');ax.set_title('Muscle-chip response directions do not repeat across flights\nGSE234465 → GSE298393; non-stimulated arms');ax.legend(loc='upper right',frameon=False);ax.text(.02,.97,'3 chips per condition / pool / flight\nExploratory; shared donors and protocol differences',transform=ax.transAxes,va='top',fontsize=9);fig.savefig(p/'cross_flight_pattern_reviewed.png',dpi=160);fig.savefig(p/'cross_flight_pattern_reviewed.pdf');plt.close(fig)
print(pd.DataFrame(rows).to_string(index=False));print(pd.DataFrame(gr)[pd.DataFrame(gr).gene=='MYH1'].to_string(index=False))
