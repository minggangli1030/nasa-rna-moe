#!/usr/bin/env python3
"""Broad, bounded discovery survey. No fitted classifier or causal claims."""
import argparse,hashlib,importlib.util,json,re,time
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd
from audit_bridge_contract import log1p_tpm,sha256


def dump(p,x):p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def text(x):return '' if pd.isna(x) else str(x).strip()
def rank(x):return hashlib.sha256(('survey1701|'+str(x)).encode()).hexdigest()
def tissue(x):
 x=x.lower()
 for k,v in [('liver','liver'),('kidney','kidney'),('lung','lung'),('spleen','spleen'),('thym','thymus'),('adipose','adipose'),('bone','bone'),('mandible','bone'),('hippocamp','brain'),('cerebr','brain'),('cerebell','brain'),('brain','brain'),('heart','heart'),('colon','colon'),('retina','retina'),('eye','eye'),('soleus','skeletal muscle'),('gastrocnem','skeletal muscle'),('quadriceps','skeletal muscle'),('tibialis','skeletal muscle'),('digitorum','skeletal muscle')]:
  if k in x:return v
 return x


def select(base,out,raw):
 out.mkdir(parents=True,exist_ok=True);m=pd.read_csv(base/'metadata_new.csv',low_memory=False)
 rows=[];decisions=[]
 controls={'Ground Control':0,'Ground control':0,'Space Flight':1}
 for (study,material,file),g in m.groupby(['id.accession','study.characteristics.material type','counts_file']):
  g=g[g['study.factor value.spaceflight'].isin(controls)].copy()
  if len(g)==0:continue
  if not (raw/file).exists():
   decisions.append({'study':study,'material':material,'reason':'count_file_not_in_supplied_VM_cache','samples':len(g)});continue
  g['sample']=g['id.sample name'].str.strip();g['condition']=g['study.factor value.spaceflight'].map(controls)
  def subgroup(row):
   sid=row['sample'];tokens=[]
   for pattern in [r'(ISS-T|LAR)',r'(?:_|-)(OLD|YNG)(?:_|-)',r'_(?:FLT|GC)_(C|I)_']:
    found=re.search(pattern,sid);tokens.append(found.group(1) if found else '')
   for c in ['study.characteristics.strain','study.characteristics.sex','study.characteristics.age at launch','study.factor value.genotype','study.parameter value.duration','study.parameter value.carcass preservation method','study.parameter value.sample preservation method']:
    tokens.append(text(row[c]).lower())
   return '|'.join(tokens)
  g['stratum']=g.apply(subgroup,axis=1);g['unit']=g['sample'].str.replace(r'_techrep\d+$','',regex=True)
  for stratum,sg in g.groupby('stratum'):
   sg=sg.sort_values('sample').drop_duplicates('unit');counts=sg.condition.value_counts()
   if min(counts.get(0,0),counts.get(1,0))<3:
    decisions.append({'study':study,'material':material,'stratum':stratum,'reason':'fewer_than_3_each_after_matching','samples':len(sg)});continue
   con=study+'|'+material+'|'+hashlib.sha256(stratum.encode()).hexdigest()[:8]
   for cond,cg in sg.groupby('condition'):
    cg=cg.assign(selection_rank=cg['sample'].map(rank)).sort_values('selection_rank').head(6)
    for _,r in cg.iterrows():
     rows.append({'id':study+':'+r['sample'],'study':study,'contrast':con,'tissue':tissue(material),'material':material,'species':'mouse','setting':'actual_flight','condition':int(cond),'condition_name':'flight' if cond else 'ground','unit':r['unit'],'stratum':stratum,'sample':r['sample'],'source_file':file,'source_kind':'osdr_counts','split':'unknown','study_exposure':'unknown'})
   decisions.append({'study':study,'material':material,'stratum':stratum,'reason':'selected_up_to_6_per_condition','samples':min(counts[0],6)+min(counts[1],6)})
 # Human cohorts identified from the supplied metadata, with explicit designs.
 for study in ['GSE137081','GSE234465','GSE113165','GSE126865']:
  d=pd.read_csv(base/(study+'_metadata.csv')).fillna('')
  for _,r in d.iterrows():
   title=r['title'];ch=r['characteristics_ch1'];c=None
   if study=='GSE137081':
    unit=re.search(r'Line (\d+)',title).group(1);c=2 if 'Post-flight' in title else (1 if 'Flight' in title else 0);stratum='all_lines';mat='hiPSC-derived cardiomyocytes';setting='actual_flight';kind='human_h5'
   elif study=='GSE234465':
    c=0 if title.startswith('GC-') else 1;stratum='YA' if 'YA-' in title else 'OS';unit=title;mat='human muscle chip';setting='actual_flight';kind='human_muscle_counts'
   elif study=='GSE113165':
    unit=re.search(r'subject: ([^,]+)',ch).group(1);c=1 if 'post bed rest' in ch else 0;stratum=re.search(r'age: ([^,]+)',ch).group(1);mat='human skeletal muscle biopsy';setting='bed_rest_analog';kind='human_h5'
   else:
    unit=re.search(r'Subject (\d+)',title).group(1);c=1 if 'Post' in title else 0;stratum='all_subjects';mat='human skeletal muscle biopsy';setting='bed_rest_analog';kind='human_h5'
   rows.append({'id':study+':'+r.gsm,'study':study,'contrast':study+'|'+stratum,'tissue':'heart' if study=='GSE137081' else 'skeletal muscle','material':mat,'species':'human','setting':setting,'condition':c,'condition_name':('post-flight' if c==2 else ('exposed' if c else 'control')),'unit':unit,'stratum':stratum,'sample':r.gsm,'title':title,'source_file':'GSE234465_estimated-counts.txt.gz' if kind=='human_muscle_counts' else 'human_matrix_v11.h5','source_kind':kind,'split':r['split'],'study_exposure':r['study_exposure']})
 selected=pd.DataFrame(rows)
 # Keep a bounded six donor pairs per bed-rest subgroup; all three cardiac lines and chip replicates.
 keep=np.ones(len(selected),dtype=bool)
 for con,g in selected[selected.setting=='bed_rest_analog'].groupby('contrast'):
  units=[u for u,h in g.groupby('unit') if set(h.condition)=={0,1}];units=sorted(units,key=rank)[:6];keep[g.index]=g.unit.isin(units)
 selected=selected[keep].reset_index(drop=True)
 if selected.id.duplicated().any():raise ValueError('Sample reused across contrasts')
 selected.to_csv(out/'selected_manifest.csv',index=False);pd.DataFrame(decisions).to_csv(out/'osdr_selection_decisions.csv',index=False)
 dump(out/'survey_protocol.json',{'status':'exploratory_discovery','scope':'all 940455 supplied ARCHS4 metadata rows; all 2896 supplied OSDR metadata rows; bounded expression subset based on available files and explicit designs, not outcomes','selection':'OSDR all cached study/exact-tissue/covariate strata with >=3 per condition; cap6 per condition by hash; explicit human cardiac, muscle-chip and paired bedrest cohorts','model':'r7hnr92k frozen official pre-norm; final hidden mean and gene-wise std as two descriptive readouts','minimum_canonical_coverage':.99,'missing_gene_policy':'Never interpreted as measured zero. Missing canonical positions masked with training token -10 for model; normalization uses observed canonical genes; missingness documented and sensitivity to zero fill checked for incomplete HUMAN inputs only','analysis':'within-stratum effect distances, group/donor resampling and leave-one-unit-out directional consistency; no classifier tuning; raw expression and PCA comparators','pretraining':'Recorded from supplied manifest for human GSMs; OSDR overlap unknown. No generalization claims','manifest_sha256':sha256(out/'selected_manifest.csv')})
 print('Selected',len(selected),'samples',selected.contrast.nunique(),'contrasts',selected.groupby('species').size().to_dict(),flush=True)


def prepare(base,out,raw,h5path):
 import h5py
 m=pd.read_csv(out/'selected_manifest.csv').fillna('');genes=pd.read_csv(base/'canonical_genes.csv').sort_values('token_id').gene_symbol.tolist()
 ortho=pd.read_csv(base/'orthologs_one2one.txt',sep='\t').set_index('Human gene name').loc[genes]
 mouse_ids=ortho['Gene stable ID'].tolist();human_ids=ortho['Human gene stable ID'].tolist()
 ml=pd.read_csv(base/'gencode_v49_mouse_gene_exon_lengths.csv').set_index('gene_symbol').exon_length.reindex(ortho['Gene name']).to_numpy(float)
 hl=pd.read_csv(base/'gencode_v49_gene_exon_lengths.csv').set_index('gene_symbol').exon_length.reindex(genes).to_numpy(float)
 hgnc=pd.read_csv(base/'hgnc_complete_set_2026-09-12.txt',sep='\t',low_memory=False)
 prev=defaultdict(set)
 for r in hgnc.itertuples():
  for old in str(r.prev_symbol).split('|'):
   if old!='nan':prev[old].add(r.symbol)
 def human_mapping(symbols,ids):
  direct=defaultdict(list);stable=defaultdict(list);oldmap=defaultdict(list)
  for i,sym in enumerate(symbols):
   direct[sym].append(i)
   for target in prev.get(sym,[]):
    if len(prev[sym])==1:oldmap[target].append(i)
  for i,eid in enumerate(ids):stable[str(eid).split('.')[0]].append(i)
  index=[];methods=[]
  for gene,eid in zip(genes,human_ids):
   choices=[('exact_symbol',direct.get(gene,[])),('stable_id',stable.get(eid,[])),('hgnc_previous_symbol',oldmap.get(gene,[]))]
   found=next(((name,vals[0]) for name,vals in choices if len(vals)==1),('missing',-1));methods.append(found[0]);index.append(found[1])
  # Multiple canonical genes resolving to one input row are ambiguous and stay masked.
  counts=pd.Series([i for i in index if i>=0]).value_counts()
  for j,i in enumerate(index):
   if i>=0 and counts[i]>1:index[j]=-1;methods[j]='ambiguous_shared_row'
  return np.array(index),methods
 arrays=[];masks=[];kept=[];audit=[];qc=[]
 fh=None;hlookup=None;hindex=None
 for (kind,file),g in m.groupby(['source_kind','source_file'],sort=False):
  if kind=='osdr_counts':
   path=raw/file;d=pd.read_csv(path,index_col=0);d.columns=d.columns.str.strip();d.index=d.index.astype(str).str.split('.').str[0];d=d.groupby(level=0,sort=False).sum();lookup={v:i for i,v in enumerate(d.index)};index=np.array([lookup.get(v,-1) for v in mouse_ids]);lengths=ml;methods=['stable_id' if i>=0 else 'missing' for i in index]
  elif kind=='human_muscle_counts':
   path=base/file;df=pd.read_csv(path,sep='\t');index,methods=human_mapping(df.Gene.fillna('').tolist(),df['#GeneID'].tolist());d=df.drop(columns=['#GeneID','Gene','Biotype']);lengths=hl
  else:
   path=h5path
   if fh is None:
    fh=h5py.File(path,'r');symbols=[s.decode() for s in fh['meta/genes/gene_symbol'][:]];ids=[s.decode() for s in fh['meta/genes/ensembl_gene_id'][:]];hindex,hmethods=human_mapping(symbols,ids);hlookup={s.decode():i for i,s in enumerate(fh['meta/samples/geo_accession'][:])}
   index=hindex;methods=hmethods;lengths=hl
  found=index>=0;coverage=float(found.mean())
  audit.append({'source_file':file,'source_kind':kind,'coverage':coverage,'missing_genes':[genes[i] for i in np.flatnonzero(~found)],'mapping_methods':dict(pd.Series(methods).value_counts().astype(int).items()),'source_sha256':sha256(path) if kind!='human_h5' else 'large existing v11 matrix; selected count values hashed separately'})
  if coverage<.99:
   audit[-1]['decision']='excluded_below_99_percent';print('Excluded',file,'coverage',coverage,flush=True);continue
  pd.DataFrame({'gene':genes,'source_row':index,'method':methods}).to_csv(out/(file.replace('.gz','').replace('.csv','').replace('.h5','')+'_mapping.csv'),index=False)
  for ri,row in g.iterrows():
   sample=row['sample']
   if kind=='human_h5':
    if sample not in hlookup:audit.append({'sample':sample,'decision':'not_present_in_v11'});continue
    full=fh['data/expression'][:,hlookup[sample]].astype(float)
   else:
    col=row['title'].replace('GC-OS-NOES-','GC-OS-NOS-').replace('GC-YA-NOES-','GC-YA-NOS-') if kind=='human_muscle_counts' else sample
    if col not in d:raise ValueError(f'Missing count column: {col}')
    full=d[col].to_numpy(float)
   vals=full[index[found]];norm=log1p_tpm(vals[None,:],lengths[found])[0];x=np.full(len(genes),np.nan,dtype=np.float32);x[found]=norm
   arrays.append(x);masks.append(found);kept.append(ri);qc.append({'id':row.id,'source_nonzero':int((vals>0).sum()),'source_total':float(vals.sum()),'coverage':coverage})
  print('Prepared',file,'coverage',coverage,'samples',len(g),flush=True)
 if fh:fh.close()
 meta=m.loc[kept].reset_index(drop=True);x=np.asarray(arrays);observed=np.asarray(masks)
 # Remove a whole contrast if missing sample access breaks its minimum support.
 valid=[]
 for con,g in meta.groupby('contrast'):
  c=g.condition.value_counts()
  if c.get(0,0)>=3 and c.get(1,0)>=3:valid.extend(g.index)
 valid=sorted(valid);meta=meta.loc[valid].reset_index(drop=True);x=x[valid];observed=observed[valid]
 meta.to_csv(out/'manifest.csv',index=False);pd.DataFrame(qc).iloc[valid].to_csv(out/'sample_qc.csv',index=False)
 np.savez_compressed(out/'inputs.npz',x=x,observed=observed,genes=np.array(genes),ids=meta.id.to_numpy(str))
 dump(out/'preprocessing_audit.json',audit)
 print('READY',x.shape,'human',int((meta.species=='human').sum()),'contrasts',meta.contrast.nunique(),flush=True)


def infer(base,out,checkpoint,official):
 import torch
 torch.set_num_threads(4);torch.manual_seed(1701);torch.backends.cuda.matmul.allow_tf32=False
 spec=importlib.util.spec_from_file_location('official',official);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 cfg=json.loads((base/'config.json').read_text());ck=torch.load(checkpoint,map_location='cpu',weights_only=True)
 model=mod.ExpressionPerformer(num_genes=15165,hidden_dim=cfg['hidden_dim'],n_heads=cfg['num_heads'],n_layers=cfg['num_layers'],ffn_dim=cfg['ffn_dim'],ree_base=cfg['ree_base'],mask_token_id=cfg['mask_token'],feature_type=cfg['feature_type'],compute_type=cfg['compute_type'],include_species_embedding=cfg['include_species_embedding'],num_species=2);model.load_state_dict(ck['model_state_dict'],strict=True);del ck
 model.eval().cuda();data=np.load(out/'inputs.npz');m=pd.read_csv(out/'manifest.csv');means=[];stds=[];zero=[];started=time.time()
 with torch.inference_mode():
  for i,row in enumerate(data['x']):
   x=torch.from_numpy(np.nan_to_num(row,nan=-10)[None]).cuda();h=model._encode_hidden(x);means.append(h.mean(1).cpu().numpy()[0]);stds.append(h.std(1,unbiased=False).cpu().numpy()[0]);del h
   if m.iloc[i].species=='human' and np.isnan(row).any():zero.append(model.encode(torch.from_numpy(np.nan_to_num(row,nan=0)[None]).cuda()).cpu().numpy()[0])
   else:zero.append(means[-1])
   if i%20==0 or i+1==len(m):print('EMBED',i+1,'/',len(m),'seconds',round(time.time()-started,1),flush=True)
 np.savez_compressed(out/'embeddings.npz',mean=np.array(means),std=np.array(stds),zero_fill_sensitivity=np.array(zero),ids=data['ids'])
 dump(out/'inference_report.json',{'samples':len(m),'seconds':time.time()-started,'device':torch.cuda.get_device_name(),'checkpoint_sha256':sha256(checkpoint),'official_source_sha256':sha256(official),'input_sha256':sha256(out/'inputs.npz'),'readouts':['final_gene_mean','final_gene_std'],'missing_human_sensitivity':'unknown token versus zero fill; zero fill is sensitivity only, not biological observed zero'})
 (out/'INFERENCE_COMPLETE').write_text('complete\n')


def main():
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['select','prepare','infer']);p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--raw',type=Path);p.add_argument('--human-h5',type=Path);p.add_argument('--checkpoint',type=Path);p.add_argument('--official',type=Path);a=p.parse_args()
 if a.phase=='select':select(a.base,a.output,a.raw)
 elif a.phase=='prepare':prepare(a.base,a.output,a.raw,a.human_h5)
 else:infer(a.base,a.output,a.checkpoint,a.official)
if __name__=='__main__':main()
