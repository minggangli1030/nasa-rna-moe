#!/usr/bin/env python3
"""Render the complete frozen pathway panel and controlled model comparisons."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parent/'artifacts/pathway_onboard_1g_2026-09-13'
r=pd.read_csv(P/'pathway_contrasts.csv');s=pd.read_csv(P/'pathway_source_sensitivity.csv')
r['passes_primary_checks']=(r.leave_one_sign_retention==1)&(np.sign(r.zscore_shift)==np.sign(r.rank_shift))&(np.sign(r.zscore_shift)==np.sign(r.background_centered_shift))
cols=['GSE234465|YA','GSE234465|OS','GSE298393|YA','GSE298393|OS','GSE224805|microgravity_vs_onboard_1g|author','GSE157937|microgravity_vs_onboard_1g|NCBI','GSE157937|onboard_1g_vs_ground|NCBI','GSE157937|microgravity_vs_ground|NCBI']
labels=['Flight 1\nYA pool','Flight 1\nOS pool','Flight 2\nYA pool','Flight 2\nOS pool','MG63\nµg − onboard 1g','HMEC-1\nµg − onboard 1g','HMEC-1\nonboard 1g − Earth','HMEC-1\nµg − Earth']
names=['Oxidative Phosphorylation','TNF-alpha Signaling via NF-kB','Inflammatory Response','DNA Repair','Unfolded Protein Response','Reactive Oxygen Species Pathway','p53 Pathway','Circadian clock','Myogenesis','Muscle contraction']
selected=r[r.contrast.isin(cols)].copy();passed=[]
for row in selected.itertuples():
 if row.study in ['GSE234465','GSE298393']:
  ss=s[(s.comparison=='muscle_chip_source')&(s.pool==row.contrast.split('|')[1])&(s.pathway==row.pathway)]
  ss=ss[ss.source.str.startswith('first_' if row.study=='GSE234465' else 'repeat_')]
 elif row.study=='GSE224805':ss=s[(s.comparison=='MG63_source_matched5')&(s.pathway==row.pathway)]
 else:ss=s[(s.comparison=='endothelial_source')&(s.pool==row.setting)&(s.pathway==row.pathway)]
 passed.append(bool(len(ss)>0 and row.passes_primary_checks and ss.robust.all() and (np.sign(ss.zscore_shift)==np.sign(row.zscore_shift)).all()))
selected['passes_primary_and_source_checks']=passed;selected.to_csv(P/'presentation_pathway_checks.csv',index=False)
a=selected.pivot(index='pathway',columns='contrast',values='zscore_shift').loc[names,cols];p=selected.pivot(index='pathway',columns='contrast',values='passes_primary_and_source_checks').loc[names,cols]
fig,ax=plt.subplots(figsize=(15,8.7));fig.subplots_adjust(left=.25,right=.92,top=.79,bottom=.2);im=ax.imshow(a,cmap='RdBu_r',vmin=-1.2,vmax=1.2,aspect='auto');ax.set_yticks(range(10),names,fontsize=11);ax.set_xticks(range(8),labels,fontsize=9);ax.xaxis.tick_top();ax.tick_params(axis='both',length=0,pad=8)
for i in range(10):
 for j in range(8):ax.text(j,i,f'{a.iloc[i,j]:+.2f}'+(' •' if p.iloc[i,j] else ''),ha='center',va='center',fontsize=10,color='white' if abs(a.iloc[i,j])>.75 else '#202020')
ax.axvline(3.5,color='white',lw=5);ax.axvline(4.5,color='white',lw=2);cax=fig.add_axes([.94,.22,.014,.55]);fig.colorbar(im,cax=cax,label='Exposed − control mean gene z-score')
fig.text(.25,.945,'Narrow gene-set patterns survive a broader mixed response',fontsize=20,weight='bold');fig.text(.25,.906,'All 10 predefined gene sets • human flight comparisons • exploratory, no significance tests',fontsize=12)
fig.text(.25,.155,'• Direction survives every sample deletion, rank/background score checks, and source-processing checks.\nDots are robustness flags, not statistical significance. Scores are standardized within each contrast.\nMuscle chips: 3 + 3 per pool/flight; shared donor pools. MG63: 3 + 3; source sensitivity 3 + 2.\nHMEC-1: 3 µg, 2 onboard 1g, 3 Earth cultures; its three contrasts share samples.',fontsize=10,va='top',linespacing=1.6)
fig.savefig(P/'pathway_discovery.png',dpi=170);fig.savefig(P/'pathway_discovery.pdf');plt.close(fig)
# Compare model stability with expression, without claiming predictive performance.
m=pd.read_csv(P/'model_contrast_metrics.csv');m=m[m.role=='primary'];cc=[cols[4],cols[5],cols[6],cols[7]];fig,ax=plt.subplots(figsize=(11,5.5),layout='constrained')
for j,(rep,label,color) in enumerate([('raw','Expression','#3875a9'),('model_mean','BridgeRNA mean','#bc6238'),('model_std','BridgeRNA std','#60976a')]):
 g=m[m.representation==rep].set_index('contrast').loc[cc];ax.bar(np.arange(4)+(j-1)*.24,g.split_median_cosine,width=.22,label=label,color=color)
ax.axhline(0,color='black',lw=.7);ax.set_ylim(-1,1);ax.set_xticks(range(4),[labels[i] for i in [4,5,6,7]]);ax.set_ylabel('Median response-direction cosine between balanced splits');ax.set_title('MG63 separates consistently; endothelial responses are less stable\nFrozen BridgeRNA r7hnr92k versus expression baseline');ax.legend(loc='lower right',frameon=False);fig.savefig(P/'controlled_model_stability.png',dpi=170);fig.savefig(P/'controlled_model_stability.pdf');plt.close(fig)
print(selected[selected.passes_primary_and_source_checks][['contrast','pathway','zscore_shift']].to_string(index=False))
