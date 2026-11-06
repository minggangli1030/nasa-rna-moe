#!/usr/bin/env python3
"""Bounded repeat-flight check; FPKM interpretation follows the source annotation."""
import argparse,json,re,itertools
from pathlib import Path
import numpy as np
import pandas as pd
from audit_bridge_contract import sha256

def dump(p,x):p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')

def prepare(out,reference):
 matrix=out/'GSE298393_genes.rawmatrix.tsv.gz';df=pd.read_csv(matrix,sep='\t');cg=pd.read_csv(reference/'ensembl/canonical_genes.csv').sort_values('token_id');genes=cg.gene_symbol.to_numpy(str)
 ortho=pd.read_csv(reference/'ensembl/orthologs_one2one.txt',sep='\t').set_index('Human gene name').loc[genes];sid=df.iloc[:,0].astype(str).str.split('.').str[0]
 assert not sid.duplicated().any();lookup={g:i for i,g in enumerate(sid)};ix=np.array([lookup.get(g,-1) for g in ortho['Human gene stable ID']]);found=ix>=0
 assert found.mean()>=.99
 pd.DataFrame({'canonical_gene':genes,'source_row':ix,'source_symbol':[df.Gene.iloc[i] if i>=0 else '' for i in ix]}).to_csv(out/'gene_mapping.csv',index=False)
 samples=[];arrays=[];qc=[];catalog=pd.read_parquet(reference/'manifests/sample_manifest.parquet').set_index('gsm')
 for block in (out/'GSE298393_samples.soft').read_text().split('^SAMPLE = ')[1:]:
  lines=block.splitlines();gsm=lines[0];fields={}
  for line in lines[1:]:
   if ' = ' in line:
    k,v=line.split(' = ',1);fields.setdefault(k,[]).append(v)
  title=fields['!Sample_title'][0]
  if not title.startswith('No E-stim ') or 'Day 21' not in title:continue
  desc=fields['!Sample_description'][0];mat=re.search(r'muscle_(YA|OS)_NoEstim_(TOCO2GC_|SpX25)_+Chip_(\d+)',desc);assert mat,desc
  group,env,chip=mat.groups();col=f'{group}-NoEstim-'+('TOCO2GC--' if env.startswith('TOCO') else 'SpX25-')+f'Chip-{chip}';assert col in df
  condition=int(env=='SpX25');assert condition==int('microgravity' in title)
  vals=df[col].to_numpy(float)[ix[found]];assert np.isfinite(vals).all() and (vals>=0).all() and vals.sum()>0
  x=np.full(len(genes),np.nan,np.float32);x[found]=np.log1p(vals/vals.sum()*1e6)
  ident='GSE298393:'+gsm;split=str(catalog.loc[gsm,'split']) if gsm in catalog.index else 'not_in_supplied_catalog'
  samples.append({'id':ident,'sample':gsm,'study':'GSE298393','contrast':'GSE298393|'+group,'stratum':group,'species':'human','setting':'actual_flight','tissue':'skeletal muscle','material':'human muscle chip','condition':condition,'unit':col,'title':title,'source_column':col,'split':split,'source_kind':'source_annotated_FPKM'})
  arrays.append(x);qc.append({'id':ident,'source_nonzero':int((vals>0).sum()),'source_total':float(vals.sum()),'source_total_units':'sum of source FPKM, not read depth','coverage':float(found.mean())})
 m=pd.DataFrame(samples);assert len(m)==12 and m.source_column.nunique()==12;assert (m.groupby(['stratum','condition']).size()==3).all()
 m.to_csv(out/'manifest.csv',index=False);pd.DataFrame(qc).to_csv(out/'sample_qc.csv',index=False)
 np.savez_compressed(out/'inputs.npz',x=np.array(arrays),observed=np.repeat(found[None],len(m),axis=0),genes=genes,ids=m.id.to_numpy(str))
 dump(out/'preprocessing_audit.json',{'source_units':'FPKM per GEO Sample_data_processing; rawmatrix filename does not establish counts','conversion':'log1p(1e6 * FPKM / sum(FPKM over observed canonical genes)); no second division by gene length','limitation':'Source effective gene lengths and ambiguous phrase non-normalized FPKM are not independently verified. Cross-flight conclusions remain conditional on this annotation; first flight used counts/exon lengths.','coverage':float(found.mean()),'missing_genes':genes[~found].tolist(),'source_sha256':sha256(matrix),'input_sha256':sha256(out/'inputs.npz'),'gene_order_sha256':sha256(reference/'ensembl/canonical_genes.csv'),'training_exposure':m.split.value_counts().to_dict(),'sample_mapping':'GSM library description to cohort, setting, exact chip number; no rank/order matching'})
 print('READY',len(m),'samples; coverage',found.mean(),flush=True)

def analyze(out,baseline):
 from analyze_general_survey import diagnostics,cosine
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 bm=pd.read_csv(baseline/'manifest.csv');bd=np.load(baseline/'inputs.npz');be=np.load(baseline/'embeddings.npz');m=pd.read_csv(out/'manifest.csv');d=np.load(out/'inputs.npz');e=np.load(out/'embeddings.npz')
 assert m.id.tolist()==d['ids'].tolist()==e['ids'].tolist();assert np.array_equal(d['genes'],bd['genes'])
 assert sha256(out/'inputs.npz')==json.loads((out/'inference_report.json').read_text())['input_sha256']
 keep=bm.study=='GSE234465';oi=np.flatnonzero(keep);common=d['observed'].all(0)&bd['observed'][oi].all(0)
 for k in ['mean','std','zero_fill_sensitivity']:assert np.isfinite(e[k]).all()
 meta=pd.concat([bm[keep],m],ignore_index=True);rep={'raw':np.concatenate([bd['x'][oi][:,common],d['x'][:,common]]),'model_mean':np.concatenate([be['mean'][oi],e['mean']]),'model_std':np.concatenate([be['std'][oi],e['std']])}
 metrics=[];shifts={};leave={}
 for con,g in meta.groupby('contrast'):
  shifts[con]={};leave[con]={};y=g.condition.to_numpy()
  for name,z in rep.items():
   zz=z[g.index].astype(float);shift,diag=diagnostics(zz,y,g.unit.to_numpy(),False);shifts[con][name]=shift;metrics.append({'contrast':con,'representation':name,**diag})
   leave[con][name]=[zz[(y==1)&(np.arange(len(g))!=i)].mean(0)-zz[(y==0)&(np.arange(len(g))!=i)].mean(0) for i in range(len(g))]
 pd.DataFrame(metrics).to_csv(out/'within_flight_robustness.csv',index=False)
 zero=np.concatenate([be['zero_fill_sensitivity'][oi],e['zero_fill_sensitivity']]);sensitivity=[]
 for con,g in meta.groupby('contrast'):
  y=g.condition.to_numpy();z=zero[g.index];a=shifts[con]['model_mean'];b=z[y==1].mean(0)-z[y==0].mean(0)
  sensitivity.append({'contrast':con,'masked_vs_zero_shift_cosine':float(cosine(a,b)),'relative_shift_change':float(np.linalg.norm(a-b)/max(np.linalg.norm(a),1e-15))})
 pd.DataFrame(sensitivity).to_csv(out/'missingness_sensitivity.csv',index=False)

 cross=[]
 for pool in ['YA','OS']:
  a='GSE234465|'+pool;b='GSE298393|'+pool
  for name in rep:
   v=[float(cosine(x,y)) for x,y in itertools.product(leave[a][name],leave[b][name])]
   cross.append({'pool':pool,'representation':name,'cross_flight_cosine':float(cosine(shifts[a][name],shifts[b][name])),'leave_one_chip_each_min_cosine':min(v),'leave_one_chip_each_max_cosine':max(v),'leave_one_chip_each_positive_fraction':float(np.mean(np.array(v)>0))})
 cross=pd.DataFrame(cross);cross.to_csv(out/'cross_flight_direction.csv',index=False)
 # Primary gene follow-up fixed in protocol before later-flight outcomes.
 genes=d['genes'][common].tolist();rows=[]
 for gene in ['PDK4','ACTN3','MYH1','ANKRD2','NMRK2','CDKN1A','DBP','MMP14','MT1X']:
  for con in shifts:rows.append({'gene':gene,'contrast':con,'expression_shift':float(shifts[con]['raw'][genes.index(gene)]) if gene in genes else None})
 pd.DataFrame(rows).to_csv(out/'prespecified_gene_shifts.csv',index=False)
 fig,ax=plt.subplots(figsize=(7,4),layout='constrained');colors=['#3875a9','#bc6238','#60976a']
 for j,name in enumerate(rep):
  g=cross[cross.representation==name];ax.bar(np.arange(2)+(j-1)*.23,g.cross_flight_cosine,width=.21,label=name,color=colors[j])
 ax.axhline(0,color='black',lw=.7);ax.set_xticks([0,1],['Young / active pool','Old / sedentary pool']);ax.set_ylim(-1,1);ax.set_ylabel('Flight-response direction cosine');ax.set_title('Does the human muscle-chip response repeat across flights?');ax.legend(loc='lower right');fig.savefig(out/'cross_flight_pattern.png',dpi=160);fig.savefig(out/'cross_flight_pattern.pdf');plt.close(fig)
 dump(out/'analysis_summary.json',{'samples_first_flight':12,'samples_repeat_flight':12,'common_genes':int(common.sum()),'cross_flight':cross.to_dict('records'),'cautions':['Exploratory association; shared donor pools, different durations/hardware, source preprocessing difference.','Primary input assumes GEO-annotated FPKM units.','Source absent from provided pretraining catalog, not independently established unseen by checkpoint.','No causal, significance, classifier, or generalization claim.']})
 (out/'ANALYSIS_COMPLETE').write_text('ready for scientific review and brief update\n');print(cross.to_string(index=False),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['prepare','analyze']);p.add_argument('--output',type=Path,required=True);p.add_argument('--reference',type=Path);p.add_argument('--baseline',type=Path);a=p.parse_args()
 if a.phase=='prepare':prepare(a.output,a.reference)
 else:analyze(a.output,a.baseline)
