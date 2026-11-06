#!/usr/bin/env python3
"""Post-screen descriptive checks and figures for mentor discussion, not validation."""
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);out=p.parse_args().output
m=pd.read_csv(out/'manifest.csv');d=np.load(out/'inputs.npz');metrics=pd.read_csv(out/'contrast_pattern_metrics.csv');genes=list(d['genes'])
mission={**{f'OSD-{i}':'RR-1' for i in [99,101,103,104,105,419]},**{f'OSD-{i}':'RR-23' for i in [576,665,666,770]},'OSD-326':'RR-4','OSD-401':'RR-5'}
rows=[]
for (study,con),g in m[(m.species=='mouse')&(m.tissue=='skeletal muscle')].groupby(['study','contrast']):
 z=d['x'][g.index];y=g.condition.to_numpy();delta=z[y==1].mean(0)-z[y==0].mean(0)
 for gene in ['MT1X','CDKN1A','DBP','MMP14']:
  j=genes.index(gene);changes=[]
  for i in range(len(g)):
   keep=np.arange(len(g))!=i;changes.append(z[keep&(y==1),j].mean()-z[keep&(y==0),j].mean())
  rows.append({'study':study,'mission':mission[study],'contrast':con,'gene':gene,'shift':float(delta[j]),'leave_one_sample_out_same_sign_fraction':float(np.mean(np.sign(changes)==np.sign(delta[j]))),'minimum_abs_leave_one_sample_out_shift':float(np.min(np.abs(changes)))})
genesurvey=pd.DataFrame(rows);genesurvey.to_csv(out/'muscle_gene_leave_one_out.csv',index=False)
studygenes=genesurvey.groupby(['mission','study','gene'])['shift'].mean().reset_index();missiongenes=studygenes.groupby(['mission','gene'])['shift'].mean().reset_index();missiongenes.to_csv(out/'muscle_gene_mission_summary.csv',index=False)
# All human contrasts for selected recurrent candidates and published chip comparator genes.
hr=[]
for con,g in m[m.species=='human'].groupby('contrast'):
 z=d['x'][g.index];y=g.condition.to_numpy();delta=z[y==1].mean(0)-z[y==0].mean(0)
 for gene in ['MT1X','CDKN1A','DBP','MMP14','PFKFB3','MYH1','ANKRD2','NMRK2','PDK4','ACTN3']:
  j=genes.index(gene);hr.append({'contrast':con,'setting':g.setting.iloc[0],'gene':gene,'shift':float(delta[j])})
pd.DataFrame(hr).to_csv(out/'human_candidate_expression_shifts.csv',index=False)
# Genotype agreement within the same MHU-3 experiment; no independent mission claim.
e=np.load(out/'embeddings.npz');common=d['observed'].all(0);reps={'Expression':d['x'][:,common],'BridgeRNA mean':e['mean'],'BridgeRNA std':e['std']};gr=[]
for mat,g in m[m.study=='OSD-457'].groupby('material'):
 for rep,z in reps.items():
  shifts=[]
  for _,sg in g.groupby('stratum'):
   a=z[sg.index];y=sg.condition.to_numpy();shifts.append(a[y==1].mean(0)-a[y==0].mean(0))
  if len(shifts)==2:gr.append({'material':mat,'representation':rep,'genotype_response_cosine':float(np.dot(*shifts)/np.prod([np.linalg.norm(a) for a in shifts]))})
pd.DataFrame(gr).to_csv(out/'mhu3_genotype_direction_agreement.csv',index=False)
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
fig,axs=plt.subplots(1,3,figsize=(17,6.5),layout='constrained',gridspec_kw={'width_ratios':[1.15,1.2,1]})
labels={'GSE234465|YA':'Muscle chips: young/active (3+3 chips)','GSE234465|OS':'Muscle chips: old/sedentary (3+3 chips)','GSE137081|all_lines':'Cardiac cells (3 paired cell lines)','GSE113165|old':'Bed rest: older (6 paired donors)','GSE113165|young':'Bed rest: younger (6 paired donors)','GSE126865|all_subjects':'Bed rest: second study (3 pairs)'}
piv=metrics.pivot(index='contrast',columns='representation',values='split_positive_fraction').loc[list(labels),['raw','model_mean','model_std']]
ax=axs[0];im=ax.imshow(piv,aspect='auto',vmin=0,vmax=1,cmap='viridis');ax.set_yticks(range(6),list(labels.values()),fontsize=9);ax.set_xticks(range(3),['Expression','Model\nmean','Model\nstd']);ax.set_title('A  Human pattern consistency',loc='left',weight='bold',pad=15)
for i in range(6):
 for j in range(3):ax.text(j,i,f'{piv.iloc[i,j]:.2f}',ha='center',va='center',color='black' if piv.iloc[i,j]>.65 else 'white')
ax.axhline(2.5,color='white',lw=3);ax.set_xlabel('Fraction of balanced splits agreeing\nDescriptive stability; not significance',labelpad=12)
a=metrics[(metrics.study=='OSD-457')&(metrics.representation.isin(['raw','model_mean']))].copy();a['group']=a.stratum.map(lambda s:'KO' if 'nrf2ko' in s else 'WT')+' / '+a.representation.map({'raw':'expression','model_mean':'model'})
piv=a.pivot(index='material',columns='group',values='split_positive_fraction')[['WT / expression','WT / model','KO / expression','KO / model']]
ax=axs[1];ax.imshow(piv,aspect='auto',vmin=0,vmax=1,cmap='viridis');ax.set_yticks(range(len(piv)),piv.index,fontsize=9);ax.set_xticks(range(4),['WT\nexpr.','WT\nmodel','Nrf2KO\nexpr.','Nrf2KO\nmodel']);ax.set_title('B  Tissue context within one flight',loc='left',weight='bold',pad=15)
for i in range(len(piv)):
 for j in range(4):ax.text(j,i,f'{piv.iloc[i,j]:.2f}',ha='center',va='center',fontsize=9,color='black' if piv.iloc[i,j]>.65 else 'white')
ax.set_xlabel('MHU-3: 3–6 flight + 3–6 ground per tissue/genotype\nTissues reuse animals; not independent replications',labelpad=12)
ax=axs[2];palette={'RR-1':'#3579b1','RR-4':'#dc7838','RR-5':'#7f59ac','RR-23':'#309381'}
for k,(mis,gg) in enumerate(missiongenes.groupby('mission')):
 for j,gene in enumerate(['MT1X','CDKN1A','DBP','MMP14']):
  v=gg[gg.gene==gene]['shift'].iloc[0];ax.scatter(v,j+(k-1.5)*.1,color=palette[mis],s=65,label=mis if j==0 else None)
ax.axvline(0,color='#777',ls='--',lw=1);ax.set_yticks(range(4),['MT1X (mapped mouse Mt2)','CDKN1A (Cdkn1a)','DBP (Dbp)','MMP14 (Mmp14)']);ax.invert_yaxis();ax.set_ylim(3.6,-.6);ax.set_title('C  Recurrent mouse-muscle leads',loc='left',weight='bold',pad=15);ax.set_xlabel('Mean flight − ground log1p(TPM)\nEqual weight per study within mission',labelpad=12);ax.legend(ncol=2,loc='lower left',fontsize=9,frameon=False);ax.grid(axis='x',alpha=.15)
fig.suptitle('Space-biology discovery survey • discussion leads, September 14, 2026\n559 samples · 28 study accessions · 11 tissue groups · frozen BridgeRNA',fontsize=15,weight='bold')
fig.savefig(out/'monday_findings.png',dpi=160);fig.savefig(out/'monday_findings.pdf');plt.close(fig)
print('Mission gene summaries');print(missiongenes.to_string(index=False));print('Gene leave-one-out minimum by gene');print(genesurvey.groupby('gene').leave_one_sample_out_same_sign_fraction.min().to_string());print('Genotype response cosines');print(pd.DataFrame(gr).to_string(index=False))
