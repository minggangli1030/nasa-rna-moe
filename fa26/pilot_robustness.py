#!/usr/bin/env python3
"""Post-survey sensitivity checks; intervals are conditional animal resampling."""
import argparse,itertools,json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output
    d=np.load(out/'inputs.npz');e=np.load(out/'embeddings.npz')['embeddings'];x=d['x'];y=d['flight'];groups=d['study'];studies=list(dict.fromkeys(groups))
    rng=np.random.default_rng(20260911);nboot=500
    weights=[]
    for study in studies:
        w=np.zeros((nboot,len(y)))
        for label,sign in [(0,-1),(1,1)]:
            ix=np.flatnonzero((groups==study)&(y==label));draws=rng.multinomial(len(ix),np.ones(len(ix))/len(ix),size=nboot)
            w[:,ix]=sign*draws/len(ix)
        weights.append(w)
    rows=[]
    point=pd.read_csv(out/'response_cosines.csv')
    for name,z in [('Raw log1p(TPM)',x),('BridgeRNA mean',e)]:
        bs=[w@z for w in weights]
        for i,j in itertools.combinations(range(len(studies)),2):
            cos=np.einsum('ij,ij->i',bs[i],bs[j])/(np.linalg.norm(bs[i],axis=1)*np.linalg.norm(bs[j],axis=1))
            observed=point[(point.representation==name)&(point.study_a==studies[i])&(point.study_b==studies[j])].flight_shift_cosine.iloc[0]
            rows.append({'representation':name,'study_a':studies[i],'study_b':studies[j],'observed_cosine':observed,'resample_q025':np.quantile(cos,.025),'resample_q975':np.quantile(cos,.975)})
    pd.DataFrame(rows).to_csv(out/'response_bootstrap.csv',index=False)
    candidates=pd.read_csv(out/'gene_shifts.csv').head(8)
    gene_ix=[list(d['genes']).index(g) for g in candidates.gene]
    gene_rows=[]
    for i,study in enumerate(studies):
        b=weights[i]@x[:,gene_ix]
        for j,gene in enumerate(candidates.gene):
            gene_rows.append({'gene':gene,'study':study,'observed_shift':candidates.iloc[j][study+'_flight_minus_ground'],'resample_q025':np.quantile(b[:,j],.025),'resample_q975':np.quantile(b[:,j],.975)})
    pd.DataFrame(gene_rows).to_csv(out/'candidate_gene_bootstrap.csv',index=False)
    fig,axes=plt.subplots(1,2,figsize=(12,5),layout='constrained')
    for k,name in enumerate(['Raw log1p(TPM)','BridgeRNA mean']):
        r=pd.DataFrame(rows);r=r[r.representation==name];pos=np.arange(3)+(k-.5)*.16
        # Quantile intervals need not contain the observed statistic.
        axes[0].vlines(pos,r.resample_q025,r.resample_q975,color=f'C{k}',alpha=.8)
        axes[0].scatter(pos,r.observed_cosine,color=f'C{k}',label=name,zorder=3)
    axes[0].axhline(0,color='grey',lw=1);axes[0].set_xticks(range(3),['RR1 / RR8','RR1 / RR23','RR8 / RR23']);axes[0].set_ylim(-1,1);axes[0].set_ylabel('Cosine of flight − ground centroid shifts');axes[0].set_title('Apparent RR1/RR8 alignment is unstable\nBars: 95% within-group resampling ranges');axes[0].legend(fontsize=9)
    vals=candidates[[s+'_flight_minus_ground' for s in studies]].to_numpy();im=axes[1].imshow(vals,cmap='RdBu_r',vmin=-2.1,vmax=2.1,aspect='auto')
    axes[1].set_yticks(range(len(vals)),candidates.gene);axes[1].set_xticks(range(3),['RR1','RR8','RR23']);axes[1].set_title('Top consistent raw-expression candidates\nRanked by smallest absolute study shift')
    for i in range(len(vals)):
        for j in range(3): axes[1].text(j,i,f'{vals[i,j]:+.2f}',ha='center',va='center',fontsize=9,color='white' if abs(vals[i,j])>1.3 else 'black')
    fig.colorbar(im,ax=axes[1],label='Mean log1p(TPM): flight − ground')
    fig.suptitle('Exploratory patterns — 34 mouse liver samples, 3 missions',fontsize=14)
    fig.savefig(out/'candidate_patterns.png',dpi=160);fig.savefig(out/'candidate_patterns.pdf');plt.close(fig)
    (out/'robustness_notes.json').write_text(json.dumps({'bootstrap_replicates':nboot,'seed':20260911,'scope':'Added after descriptive survey; resample animals within study/condition. Conditional sensitivity ranges, not study-level confidence or multiplicity-adjusted discovery. Cage dependence unknown. Top genes selected using these same data.'},indent=2)+'\n')
    print(pd.DataFrame(rows).to_string(index=False))

if __name__=='__main__':main()
