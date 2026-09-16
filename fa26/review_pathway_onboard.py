#!/usr/bin/env python3
"""Source-processing checks and figures for the fixed-panel exploratory survey."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import rankdata
from pathway_onboard_survey import references,program_score,dataset_contrasts
from analyze_general_survey import cosine
from audit_bridge_contract import log1p_tpm
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/pathway_onboard_1g_2026-09-13'

def metrics(x,y,ob,panel,genes):
 lookup={s:i for i,s in enumerate(genes)};ranks=rankdata(x[:,ob],axis=1)/ob.sum();ranklookup={i:j for j,i in enumerate(np.where(ob)[0])};rows=[]
 for p in panel:
  ix=[lookup[g] for g in p['canonical_genes'] if ob[lookup[g]]]
  if len(ix)<10 or len(ix)/len(p['canonical_genes'])<.5:
   rows.append({'pathway':p['name'],'n_genes':len(ix),'source_set_fraction':len(ix)/len(p['genes']),'status':'insufficient_coverage','robust':False});continue
  z=x[:,ix];v=program_score(z);delta=float(v[y==1].mean()-v[y==0].mean());loo=[]
  for k in range(len(y)):
   keep=np.arange(len(y))!=k;yy=y[keep];s=program_score(z[keep]);loo.append(float(s[yy==1].mean()-s[yy==0].mean()))
  rs=ranks[:,[ranklookup[i] for i in ix]].mean(1);bg=z.mean(1)-x[:,ob].mean(1);rr=float(rs[y==1].mean()-rs[y==0].mean());bb=float(bg[y==1].mean()-bg[y==0].mean());ret=float(np.mean(np.sign(loo)==np.sign(delta)))
  rows.append({'pathway':p['name'],'n_genes':len(ix),'source_set_fraction':len(ix)/len(p['genes']),'status':'ok','zscore_shift':delta,'rank_shift':rr,'background_centered_shift':bb,'leave_one_sign_retention':ret,'robust':ret==1 and np.sign(delta)==np.sign(rr)==np.sign(bb)})
 return rows

def renormalize(x,ob):
 z=np.full_like(x,np.nan,dtype=float);v=np.expm1(x[:,ob]);z[:,ob]=np.log1p(v/v.sum(1,keepdims=True)*1e6);return z

def sensitivities():
 genes,stable,entrez,lengths,resolve=references();lookup={g:i for i,g in enumerate(genes)};panel=json.loads((OUT/'mapped_panel.json').read_text());b=ROOT/'artifacts/general_survey_2026-09-12';r=ROOT/'artifacts/muscle_repeat_flight_2026-09-12';bd=np.load(b/'inputs.npz');rd=np.load(r/'inputs.npz');bm=pd.read_csv(b/'manifest.csv');rm=pd.read_csv(r/'manifest.csv');nd=np.load(OUT/'inputs.npz');nm=pd.read_csv(OUT/'manifest.csv');rows=[];audits=[]
 assert bd['genes'].tolist()==rd['genes'].tolist()==nd['genes'].tolist()==genes.tolist()
 old=bm[bm.study=='GSE234465'];f=pd.read_csv(r/'GSE234465_FPKM.txt.gz',sep='\t');sid=f.GeneID.astype(str).str.split('.').str[0];assert not sid.duplicated().any();idx={s:i for i,s in enumerate(sid)};ix=np.array([idx.get(g,-1) for g in stable]);ob=(ix>=0)&rd['observed'].all(0)&bd['observed'][old.index].all(0);x=np.full((len(old),len(genes)),np.nan)
 for k,row in enumerate(old.itertuples()):
  col=row.title.replace('GC-OS-NOES-','GC-OS-NOS-').replace('GC-YA-NOES-','GC-YA-NOS-');v=f[col].to_numpy(float)[ix[ob]];x[k,ob]=np.log1p(v/v.sum()*1e6)
 for pool in ['YA','OS']:
  sel=old.stratum.to_numpy()==pool;g=old[sel];h=rm[rm.stratum==pool]
  for source,z,y in [('first_author_FPKM',x[sel],g.condition.to_numpy()),('first_primary_counts',renormalize(bd['x'][g.index],ob),g.condition.to_numpy()),('repeat_author_FPKM',renormalize(rd['x'][h.index],ob),h.condition.to_numpy())]:
   for v in metrics(z,y,ob,panel,genes):rows.append({'comparison':'muscle_chip_source','pool':pool,'source':source,**v})
 # Published endothelial CPM, matched gene universe; duplicate canonical mappings excluded.
 f=pd.read_csv(ROOT/'bridge-rna-latest/data/human_survey/GSE157937_CPM.txt.gz',sep='\t');f['canonical']=f.Symbol.map(resolve);f=f.dropna(subset=['canonical']);f=f[~f.canonical.duplicated(keep=False)].set_index('canonical');found=np.array([g in f.index for g in genes]);g=nm[nm.study=='GSE157937'];ob=found&nd['observed'][g.index].all(0);x=np.full((len(g),len(genes)),np.nan)
 cols=['space_microg_rep1','space_microg_rep2','space_microg_rep3','space_1g_rep1','space_1g_rep2','ground_rep1','ground_rep2','ground_rep3']
 for k,row in enumerate(g.itertuples()):
  col=cols[int(row.sample[3:])-4781322];v=f.loc[genes[ob],col].to_numpy(float);x[k,ob]=log1p_tpm(v[None],lengths[ob])[0]
 audits.append({'study':'GSE157937','author_CPM_common_genes':int(ob.sum()),'canonical_fraction':float(ob.mean()),'mapping':'Unique canonical symbols after HGNC stable-ID/previous-symbol resolution; ambiguous or duplicate mappings excluded. CPM treated as library-size scaled counts, then divided by exon length; observed common-gene denominator used for BOTH sources. Filtered author table is sensitivity only.'})
 for exposed,control in [('microgravity','onboard_1g'),('onboard_1g','ground'),('microgravity','ground')]:
  sel=g.condition_name.isin([exposed,control]).to_numpy();y=(g.loc[sel,'condition_name']==exposed).astype(int).to_numpy()
  for source,z in [('author_CPM',x[sel]),('NCBI_counts',renormalize(nd['x'][g.index],ob)[sel])]:
   for v in metrics(z,y,ob,panel,genes):rows.append({'comparison':'endothelial_source','pool':exposed+'_vs_'+control,'source':source,**v})
 # Exactly five same GSMs and same gene denominator, not six versus five.
 a=nm[(nm.study=='GSE224805')&(nm.source=='author')];n=nm[(nm.study=='GSE224805')&(nm.source=='NCBI')];ss=sorted(set(a['sample'])&set(n['sample']));aa=a.reset_index().set_index('sample').loc[ss]['index'].to_numpy();nn=n.reset_index().set_index('sample').loc[ss]['index'].to_numpy();ob=nd['observed'][np.r_[aa,nn]].all(0);y=(nm.loc[aa,'condition_name']=='microgravity').astype(int).to_numpy()
 for source,idx in [('author_counts',aa),('NCBI_counts',nn)]:
  for v in metrics(renormalize(nd['x'][idx],ob),y,ob,panel,genes):rows.append({'comparison':'MG63_source_matched5','pool':'microgravity_vs_onboard_1g','source':source,**v})
 pd.DataFrame(rows).to_csv(OUT/'pathway_source_sensitivity.csv',index=False);(OUT/'sensitivity_audit.json').write_text(json.dumps(audits,indent=2)+'\n')
 # Prespecified sets are evaluated in full; focused OxPhos coherence is post-outcome descriptive.
 contrasts,_=dataset_contrasts(OUT);cp=[c for c in contrasts if c['study'] in ['GSE234465','GSE298393']];p=next(p for p in panel if p['name']=='Oxidative Phosphorylation');ob=np.logical_and.reduce([c['observed'] for c in cp]);ix=[lookup[g] for g in p['canonical_genes'] if ob[lookup[g]]];gr=[];checks=[];deltas={}
 for c in cp:
  z=c['x'][:,ix];y=c['y'];d=z[y==1].mean(0)-z[y==0].mean(0);deltas[c['contrast']]=d;loo=[]
  for j in range(len(ix)):
   v=program_score(np.delete(z,j,axis=1));loo.append(float(v[y==1].mean()-v[y==0].mean()))
  checks.append({'contrast':c['contrast'],'n_genes':len(ix),'positive_gene_fraction':float((d>0).mean()),'leave_one_gene_min':min(loo),'leave_one_gene_max':max(loo),'leave_one_gene_positive_fraction':float((np.array(loo)>0).mean())})
  for gene,value in zip(genes[ix],d):gr.append({'contrast':c['contrast'],'gene':gene,'log1p_expression_shift':value})
 pd.DataFrame(gr).to_csv(OUT/'oxphos_gene_changes.csv',index=False);pd.DataFrame(checks).to_csv(OUT/'oxphos_gene_deletion.csv',index=False)
 cross=[]
 for pool in ['YA','OS']:
  keys=[c['contrast'] for c in cp if c['contrast'].endswith('|'+pool)];assert len(keys)==2,keys
  a,b=[deltas[k] for k in keys];cross.append({'pool':pool,'n_genes':len(a),'gene_response_cosine':float(cosine(a,b)),'same_sign_gene_fraction':float((np.sign(a)==np.sign(b)).mean()),'both_positive_gene_fraction':float(((a>0)&(b>0)).mean())})
 pd.DataFrame(cross).to_csv(OUT/'oxphos_cross_flight_coherence.csv',index=False)
 print(pd.DataFrame(rows)[pd.DataFrame(rows).pathway.isin(['Oxidative Phosphorylation','TNF-alpha Signaling via NF-kB','DNA Repair','Unfolded Protein Response'])].to_string(index=False));print(pd.DataFrame(cross).to_string(index=False))

if __name__=='__main__':sensitivities()
