#!/usr/bin/env python3
"""Fixed-panel pathway survey and explicitly controlled human flight comparisons."""
import argparse,json,re,hashlib,itertools
from pathlib import Path
from collections import defaultdict
import numpy as np
import pandas as pd
from scipy.stats import rankdata
from audit_bridge_contract import log1p_tpm,sha256
from analyze_general_survey import diagnostics,cosine
ROOT=Path(__file__).resolve().parent

def dump(p,x):p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')

def references():
 r=ROOT/'bridge-rna-latest/data';g=pd.read_csv(r/'ensembl/canonical_genes.csv').sort_values('token_id').gene_symbol.to_numpy(str);o=pd.read_csv(r/'ensembl/orthologs_one2one.txt',sep='\t').set_index('Human gene name').loc[g]
 h=pd.read_csv(r/'human_survey/hgnc_complete_set_2026-09-12.txt',sep='\t',low_memory=False);hh=h.dropna(subset=['ensembl_gene_id','entrez_id']).drop_duplicates('ensembl_gene_id',keep=False).set_index('ensembl_gene_id');entrez=hh.entrez_id.reindex(o['Human gene stable ID']).fillna(-1).astype(int).to_numpy();stable=o['Human gene stable ID'].to_numpy();byid=dict(zip(stable,g));aliases=defaultdict(set)
 for row in h.itertuples():
  if row.ensembl_gene_id in byid:
   for sym in [row.symbol]+str(row.prev_symbol).split('|'):aliases[sym].add(byid[row.ensembl_gene_id])
 canonical=set(g)
 def resolve(s):return s if s in canonical else next(iter(aliases[s])) if len(aliases[s])==1 else None
 lengths=pd.read_csv(r/'gencode_v49_gene_exon_lengths.csv') if (r/'gencode_v49_gene_exon_lengths.csv').exists() else pd.read_csv(next(r.rglob('gencode_v49_gene_exon_lengths.csv')))
 lengths=lengths.set_index('gene_symbol').exon_length.reindex(g).to_numpy(float)
 return g,stable,entrez,lengths,resolve

def prepare(out):
 genes,stable,entrez,lengths,resolve=references();meta=[];xs=[];obs=[];audits=[];sourcearrays={};sourceobs={};training=pd.read_parquet(ROOT/'bridge-rna-latest/data/manifests/sample_manifest.parquet').set_index('gsm')
 for study,source in [('GSE224805','author'),('GSE157937','NCBI'),('GSE224805','NCBI')]:
  filename=study+('_source_matrix.tsv.gz' if source=='author' else '_NCBI_counts.tsv.gz');d=pd.read_csv(out/filename,sep='\t');key='ID' if source=='author' else 'GeneID';ids=d[key].astype(str).str.split('.').str[0];assert not ids.duplicated().any();lookup={x:i for i,x in enumerate(ids)};targets=stable if source=='author' else entrez.astype(str);ix=np.array([lookup.get(s,-1) for s in targets]);found=ix>=0;assert found.mean()>=.99
  maps=pd.DataFrame({'gene':genes,'source_row':ix,'source_identifier':targets});maps.to_csv(out/f'{study}_{source}_mapping.csv',index=False)
  cols={}
  if study=='GSE224805':
   for k in range(6):
    gsm=f'GSM{7032597+k}';col=f'X0{7 if k<3 else 8}.0{k%3+1}_R1' if source=='author' else gsm
    if col in d:cols[gsm]=col
  else:cols={f'GSM{i}':f'GSM{i}' for i in range(4781322,4781330)}
  for gsm,col in cols.items():
   vals=d[col].to_numpy(float)[ix[found]];assert np.isfinite(vals).all() and (vals>=0).all();x=np.full(len(genes),np.nan,np.float32);x[found]=log1p_tpm(vals[None],lengths[found])[0];condition=('onboard_1g' if int(gsm[3:])<7032600 else 'microgravity') if study=='GSE224805' else ('microgravity' if int(gsm[3:])<=4781324 else 'onboard_1g' if int(gsm[3:])<=4781326 else 'ground')
   meta.append({'id':study+':'+gsm+':'+source,'sample':gsm,'study':study,'source':source,'role':'sensitivity' if study=='GSE224805' and source=='NCBI' else 'primary','species':'human','tissue':'osteoblast-like MG63 cancer cells' if study=='GSE224805' else 'microvascular endothelial HMEC-1 cells','condition_name':condition,'source_column':col,'split':training.loc[gsm,'split'] if gsm in training.index else 'not_in_supplied_catalog','unit':gsm});xs.append(x);obs.append(found)
  audits.append({'study':study,'source':source,'samples':len(cols),'coverage':float(found.mean()),'source_sha256':sha256(out/filename),'missing_genes':genes[~found].tolist(),'units':'author sample counts after DESeq2 normalization; sample-wide scale cancels in canonical TPM; gene/sample offsets are not independently excluded' if source=='author' else 'NCBI independently processed raw integer counts; Entrez mapped via pinned HGNC stable IDs'})
 m=pd.DataFrame(meta);m.to_csv(out/'manifest.csv',index=False);np.savez_compressed(out/'inputs.npz',x=np.array(xs),observed=np.array(obs),genes=genes,ids=m.id.to_numpy(str));dump(out/'input_audit.json',audits)
 panel=json.loads((out/'pathway_panel.json').read_text());mapped=[]
 for row in panel:
  match={s:resolve(s) for s in row['genes']};mapped.append({**row,'canonical_genes':sorted(set(v for v in match.values() if v)),'symbol_mapping':match})
 dump(out/'mapped_panel.json',mapped);print('Prepared',len(m),'inputs;',int((m.role=='primary').sum()),'primary biological samples',flush=True)

def dataset_contrasts(out):
 base=ROOT/'artifacts/general_survey_2026-09-12';repeat=ROOT/'artifacts/muscle_repeat_flight_2026-09-12';bm=pd.read_csv(base/'manifest.csv').fillna('');bd=np.load(base/'inputs.npz');rm=pd.read_csv(repeat/'manifest.csv').fillna('');rd=np.load(repeat/'inputs.npz');common_chip=bd['observed'][bm.study=='GSE234465'].all(0)&rd['observed'].all(0)
 outrows=[]
 for m,d in [(bm,bd),(rm,rd)]:
  for con,g in m.groupby('contrast'):
   g=g[g.condition<2];idx=g.index.to_numpy();ob=d['observed'][idx].all(0)
   if g.study.iloc[0] in ['GSE234465','GSE298393']:ob=common_chip
   outrows.append({'contrast':con,'study':g.study.iloc[0],'species':g.species.iloc[0],'tissue':g.tissue.iloc[0],'setting':g.setting.iloc[0],'source':'existing','role':'primary','paired':g.study.iloc[0] in ['GSE137081','GSE113165','GSE126865'],'units':g.unit.astype(str).to_numpy(),'y':g.condition.to_numpy(),'x':d['x'][idx].astype(float),'observed':ob})
 nm=pd.read_csv(out/'manifest.csv');nd=np.load(out/'inputs.npz');assert bd['genes'].tolist()==rd['genes'].tolist()==nd['genes'].tolist()
 for (study,source),g in nm.groupby(['study','source']):
  pairs=[('microgravity','onboard_1g')]
  if study=='GSE157937':pairs += [('onboard_1g','ground'),('microgravity','ground')]
  for exposed,control in pairs:
   gg=g[g.condition_name.isin([exposed,control])];ix=gg.index.to_numpy();outrows.append({'contrast':f'{study}|{exposed}_vs_{control}|{source}','study':study,'species':'human','tissue':g.tissue.iloc[0],'setting':exposed+'_vs_'+control,'source':source,'role':g.role.iloc[0],'paired':False,'units':gg.unit.to_numpy(),'y':(gg.condition_name==exposed).astype(int).to_numpy(),'x':nd['x'][ix].astype(float),'observed':nd['observed'][ix].all(0),'new_indices':ix})
 return outrows,bd['genes']

def difference(v,y,units,paired):
 if paired:return float(np.mean([v[(units==u)&(y==1)].mean()-v[(units==u)&(y==0)].mean() for u in np.unique(units)]))
 return float(v[y==1].mean()-v[y==0].mean())

def program_score(z):
 sd=z.std(0,ddof=1);return ((z-z.mean(0))/np.where(sd>1e-10,sd,np.inf)).mean(1)

def pathways(out):
 contrasts,genes=dataset_contrasts(out);lookup={s:i for i,s in enumerate(genes)};panel=json.loads((out/'mapped_panel.json').read_text());results=[];all_con=[]
 for c in contrasts:
  x=c['x'];y=c['y'];units=c['units'];paired=c['paired'];ob=c['observed'];desc={k:c[k] for k in ['contrast','study','species','tissue','setting','source','role']};all_con.append({**desc,'n_control':int((y==0).sum()),'n_exposed':int((y==1).sum()),'paired':paired})
  ranks=np.full_like(x,np.nan);ranks[:,ob]=rankdata(x[:,ob],axis=1)/ob.sum();globalshift=difference(x[:,ob].mean(1),y,units,paired)
  for p in panel:
   ix=np.array([lookup[g] for g in p['canonical_genes'] if ob[lookup[g]]]);cov=len(ix)/len(p['canonical_genes']);base={**desc,'pathway':p['name'],'n_genes':len(ix),'n_source_genes':len(p['genes']),'n_canonical_genes':len(p['canonical_genes']),'observed_canonical_fraction':cov,'source_set_fraction':len(ix)/len(p['genes'])}
   if len(ix)<10 or cov<.5:results.append({**base,'status':'insufficient_coverage'});continue
   z=x[:,ix];score=program_score(z);effect=difference(score,y,units,paired);raw=difference(z.mean(1),y,units,paired);rank=difference(ranks[:,ix].mean(1),y,units,paired);loo=[]
   groups=[units==u for u in np.unique(units)] if paired else [np.arange(len(y))==i for i in range(len(y))]
   for drop in groups:
    keep=~drop;ss=program_score(z[keep]);loo.append(difference(ss,y[keep],units[keep],paired))
   gdelta=z[y==1].mean(0)-z[y==0].mean(0);no_myh=[i for i in ix if genes[i]!='MYH1'];exclude=difference(program_score(x[:,no_myh]),y,units,paired)
   results.append({**base,'status':'ok','zscore_shift':effect,'mean_log_expression_shift':raw,'background_centered_shift':raw-globalshift,'rank_shift':rank,'leave_one_min':min(loo),'leave_one_max':max(loo),'leave_one_sign_retention':float(np.mean(np.sign(loo)==np.sign(effect))),'genes_agreeing_fraction':float(np.mean(np.sign(gdelta)==np.sign(effect))),'excluding_MYH1_zscore_shift':exclude})
 r=pd.DataFrame(results);r.to_csv(out/'pathway_contrasts.csv',index=False);pd.DataFrame(all_con).to_csv(out/'contrast_inventory.csv',index=False)
 muscle=r[(r.species=='mouse')&(r.tissue=='skeletal muscle')].copy();mission={**{f'OSD-{i}':'RR-1' for i in [99,101,103,104,105,419]},**{f'OSD-{i}':'RR-23' for i in [576,665,666,770]},'OSD-326':'RR-4','OSD-401':'RR-5'};muscle['mission']=muscle.study.map(mission);muscle.groupby(['mission','study','pathway'])[['zscore_shift','rank_shift','background_centered_shift']].mean().groupby(['mission','pathway']).mean().reset_index().to_csv(out/'mouse_muscle_mission_programs.csv',index=False)
 chip=r[r.study.isin(['GSE234465','GSE298393'])];chip.to_csv(out/'human_chip_programs.csv',index=False)
 new=r[r.study.isin(['GSE157937','GSE224805'])];new.to_csv(out/'onboard_control_programs.csv',index=False)
 print('Computed',len(r),'program/contrast rows',flush=True);print(chip.pivot(index='pathway',columns='contrast',values='zscore_shift').round(3).to_string(),flush=True)


def model_analysis(out):
 e=np.load(out/'embeddings.npz');m=pd.read_csv(out/'manifest.csv');d=np.load(out/'inputs.npz');assert e['ids'].tolist()==m.id.tolist()==d['ids'].tolist();assert np.isfinite(e['mean']).all() and np.isfinite(e['std']).all();assert sha256(out/'inputs.npz')==json.loads((out/'inference_report.json').read_text())['input_sha256'];contrasts,genes=dataset_contrasts(out);rows=[];shifts={};ss=[]
 for c in contrasts:
  if 'new_indices' not in c:continue
  ix=c['new_indices'];y=c['y'];shifts[c['contrast']]={}
  for name,z in [('raw',c['x'][:,c['observed']]),('model_mean',e['mean'][ix]),('model_std',e['std'][ix])]:
   a,diag=diagnostics(z,y,c['units'],False);rows.append({'contrast':c['contrast'],'role':c['role'],'representation':name,**diag});shifts[c['contrast']][name]=a
  a=shifts[c['contrast']]['model_mean'];z=e['zero_fill_sensitivity'][ix];b=z[y==1].mean(0)-z[y==0].mean(0);ss.append({'contrast':c['contrast'],'masked_vs_zero_cosine':float(cosine(a,b)),'relative_shift_change':float(np.linalg.norm(a-b)/np.linalg.norm(a))})
 pd.DataFrame(rows).to_csv(out/'model_contrast_metrics.csv',index=False);pd.DataFrame(ss).to_csv(out/'model_missingness.csv',index=False)
 # Endothelial decomposition is descriptive, shares samples, and does not isolate radiation.
 a='GSE157937|microgravity_vs_onboard_1g|NCBI';b='GSE157937|onboard_1g_vs_ground|NCBI';pd.DataFrame([{'representation':n,'gravity_vs_onboard_ground_direction_cosine':float(cosine(shifts[a][n],shifts[b][n]))} for n in ['raw','model_mean','model_std']]).to_csv(out/'endothelial_direction_comparison.csv',index=False)
 # Compare author and NCBI MG63 on exactly the same five biological samples.
 ag=m[(m.study=='GSE224805')&(m.source=='author')].set_index('sample');ng=m[(m.study=='GSE224805')&(m.source=='NCBI')].set_index('sample');shared=sorted(set(ag.index)&set(ng.index));aa=[m.index[m.id==ag.loc[s,'id']][0] for s in shared];bb=[m.index[m.id==ng.loc[s,'id']][0] for s in shared];y=(m.loc[aa,'condition_name']=='microgravity').to_numpy();common=d['observed'][aa+bb].all(0);same=[]
 for n,za,zb in [('raw',d['x'][aa][:,common],d['x'][bb][:,common]),('model_mean',e['mean'][aa],e['mean'][bb]),('model_std',e['std'][aa],e['std'][bb])]:
  da=za[y].mean(0)-za[~y].mean(0);db=zb[y].mean(0)-zb[~y].mean(0);same.append({'representation':n,'n_shared_samples':len(shared),'author_vs_NCBI_shift_cosine':float(cosine(da,db))})
 pd.DataFrame(same).to_csv(out/'MG63_processing_sensitivity.csv',index=False);print(pd.DataFrame(rows).to_string(index=False),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['prepare','pathways','models']);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 {'prepare':prepare,'pathways':pathways,'models':model_analysis}[a.phase](a.output)
