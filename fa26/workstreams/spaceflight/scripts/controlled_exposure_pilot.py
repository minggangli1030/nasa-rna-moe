"""Controlled radiation specificity pilot. Frozen encoder; whole-file validation splits."""
from pathlib import Path
import argparse,gzip,json,re,hashlib,time,importlib.util
import numpy as np
import pandas as pd


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,o):p.write_text(json.dumps(o,indent=2)+'\n')
def samples(path):
    text=gzip.open(path,'rt').read();result=[]
    for block in text.split('^SAMPLE = ')[1:]:
        lines=block.splitlines();row={'gsm':lines[0]}
        for line in lines:
            if line.startswith('!Sample_') and ' = ' in line:
                k,v=line.split(' = ',1);row.setdefault(k[8:],[]).append(v)
        result.append(row)
    return result

def prepare(root,out):
    src=out/'sources';out.mkdir(parents=True,exist_ok=True)
    assert not (out/'protocol.json').exists()
    protocol={
        'question':'Does a radiation-response probe transfer and distinguish irradiation from other stress treatments?',
        'development_study':'GSE230181','external_study':'GSE242706',
        'development_target':'10 Gy irradiation-associated late response in normal IMR90 cultures versus matched non-senescent controls; not a validated radiation-specific mechanism',
        'external_target':'16 Gy irradiated versus sham lung-chip samples; report separately by cell type and time',
        'split':'Leave one entire source expression file out for IMR90 radiation/control tests; B and C sets remain together in BFX17',
        'specificity':'Other stress treatments tested using head trained without their entire expression file; report IR-vs-other AUROC and false positive rate at fixed zero logit',
        'models':['expression_linear','pca5_linear','bridge_meanstd_linear','six_programs_linear'],
        'head':'StandardScaler training only + L2 logistic regression C=1, liblinear, seed=17; PCA train only; no search/calibration',
        'encoder_update':False,'gene_universe':'Observed common canonical positions across the two new studies; structural coverage filter without label/outcome selection',
        'six_programs':'Reuse the fixed six programs from run05; no outcome-selected gene sets',
        'old_flight_head':'Evaluate model-reliance alignment only as an out-of-domain diagnostic; never count ground radiation cultures as real flight positives',
        'controlled_gravity':'Audit GSE222998; source CDS/transcript counts require a separate audited conversion, not silently treated as gene counts. Prior onboard-1g data remain previously explored context.',
        'limitations':['Cell-culture replicates, not independent donors','High dose and senescence/time confounding','Cross-study cell type/time/preparation shifts','No universal sample requirement or causal percentages','No claim of independent pretraining absence from a catalog check'],
    }
    dump(out/'protocol.json',protocol)
    genes=pd.read_csv(root/'bridge-rna-latest/data/ensembl/canonical_genes.csv').sort_values('token_id').gene_symbol.to_numpy(str)
    orth=pd.read_csv(root/'bridge-rna-latest/data/ensembl/orthologs_one2one.txt',sep='\t').set_index('Human gene name').loc[genes]
    stable=orth['Human gene stable ID'].to_numpy(str)
    h=pd.read_csv(root/'bridge-rna-latest/data/human_survey/hgnc_complete_set_2026-09-12.txt',sep='\t',low_memory=False)
    hh=h.dropna(subset=['ensembl_gene_id','entrez_id']).drop_duplicates('ensembl_gene_id',keep=False).set_index('ensembl_gene_id')
    entrez=hh.entrez_id.reindex(stable).fillna(-1).astype(int).to_numpy(str)
    lengths=pd.read_csv(root/'bridge-rna-latest/data/gencode/gencode_v49_gene_exon_lengths.csv').set_index('gene_symbol').exon_length.reindex(genes).to_numpy(float)
    meta=[];values=[];observed=[];audit=[];maps=[]
    tables={}
    for path in sorted(src.glob('GSE230181_BFX*_expr.txt.gz')):
        table=pd.read_csv(path,sep='\t');ids=table.gene_id.str.split('.').str[0]
        assert not ids.duplicated().any(),path
        lookup={v:i for i,v in enumerate(ids)};ix=np.array([lookup.get(v,-1) for v in stable]);found=ix>=0
        tables[path.name]=(table,ix,found)
    for sample in samples(src/'GSE230181_family.soft.gz'):
        gsm=sample['gsm'];title=sample['title'][0];desc=sample['description'];fname=next(v for v in desc if re.fullmatch(r'BFX\d+_expr.txt',v))
        table,ix,found=tables['GSE230181_'+fname+'.gz'];col=desc[-1]
        # Explicit, minimal reconciliation of GEO descriptions with provided headers.
        requested=col
        if fname=='BFX01_expr.txt':col=col.replace('MCA_set','MCA_Set')+'A'
        if fname=='BFX02_expr.txt':col=col.removesuffix('_sequence')
        assert col in table.columns,(gsm,col)
        v=np.full(len(genes),np.nan);v[found]=table[col].to_numpy(float)[ix[found]]
        assert np.isfinite(v[found]).all() and (v[found]>=0).all()
        chars=dict(v.split(': ',1) for v in sample.get('characteristics_ch1',[]) if ': ' in v)
        is_ir=' Sen IR ' in title;cell=title.split(' ')[0]
        if is_ir:condition='irradiated'
        elif ' Sen Bleo ' in title:condition='bleomycin'
        elif ' Sen Rot ' in title:condition='rotenone'
        elif ' Sen Ant ' in title:condition='antimycin'
        elif ' Sen Oligo ' in title:condition='oligomycin'
        elif ' Sen Ras ' in title:condition='ras_induction'
        elif ' NS DMSO ' in title:condition='vehicle'
        else:condition='control'
        normal=chars.get('group')=='normal'
        training=cell=='IMR90' and normal and (is_ir or ' NS Qui ' in title)
        setmatch=re.search(r'[Ss]et ([A-E])',title)
        group=setmatch.group(1) if setmatch else cell
        row={'id':'GSE230181:'+gsm,'sample':gsm,'study':'GSE230181','species':'human','cell_type':cell,'condition':condition,'radiation_label':int(is_ir),'training_eligible':training,'source_file':fname,'source_column':col,'description_column':requested,'experiment_set':group,'replicate':int(re.search(r'rep (\d+)',title).group(1)),'time':'14d' if is_ir else 'see GEO agent','dose_Gy':10 if is_ir else 0,'title':title,'agent':chars.get('agent',''),'group':chars.get('group',''),'source_units':'RPKM','metadata_conflict':''}
        meta.append(row);values.append(v);observed.append(found)
        maps.append({'gsm':gsm,'description':requested,'matrix_column':col,'source_file':fname,'label_source':title+' | '+chars.get('agent','')})
    table=pd.read_csv(src/'GSE242706_raw_counts_GRCh38.p13_NCBI.tsv.gz',sep='\t');ids=table.GeneID.astype(str);assert not ids.duplicated().any()
    lookup={v:i for i,v in enumerate(ids)};ix=np.array([lookup.get(v,-1) for v in entrez]);found=(ix>=0)&np.isfinite(lengths)&(lengths>0)
    for sample in samples(src/'GSE242706_family.soft.gz'):
        gsm=sample['gsm'];title=sample['title'][0];chars=dict(v.split(': ',1) for v in sample.get('characteristics_ch1',[]) if ': ' in v)
        assert gsm in table.columns;is_ir=chars['treatment']=='16 Gy radiation';assert ('16 Gy' in title)==is_ir
        cell=chars['cell type'];conflict='cell-line field contradicts title/cell-type; use agreeing title and cell-type, retain ambiguity' if cell=='Lung endothelium' and 'epithelial' in chars.get('cell line','') else ''
        t='6h' if '6h' in title else '7d';rep=int(re.search(r'rep\s*(\d+)',title).group(1))
        v=np.full(len(genes),np.nan);v[found]=table[gsm].to_numpy(float)[ix[found]]/lengths[found]
        assert np.isfinite(v[found]).all() and (v[found]>=0).all()
        meta.append({'id':'GSE242706:'+gsm,'sample':gsm,'study':'GSE242706','species':'human','cell_type':cell,'condition':'irradiated' if is_ir else 'control','radiation_label':int(is_ir),'training_eligible':False,'source_file':'NCBI_gene_counts','source_column':gsm,'description_column':gsm,'experiment_set':cell+'_'+t,'replicate':rep,'time':t,'dose_Gy':16 if is_ir else 0,'title':title,'agent':chars['treatment'],'group':'primary lung-chip culture','source_units':'NCBI gene counts divided by pinned exon length','metadata_conflict':conflict})
        values.append(v);observed.append(found);maps.append({'gsm':gsm,'description':gsm,'matrix_column':gsm,'source_file':'NCBI_gene_counts','label_source':title+' | '+chars['treatment']})
    m=pd.DataFrame(meta);v=np.array(values);obs=np.array(observed);common=obs.all(0)
    assert len(m)==123 and m.id.is_unique and common.mean()>=.95
    assert m.training_eligible.sum()==38 and m[m.training_eligible].radiation_label.value_counts().to_dict()=={1:19,0:19}
    assert m[m.training_eligible].groupby(['source_file','radiation_label']).size().groupby(level=0).nunique().eq(1).all()
    x=np.full_like(v,np.nan,dtype=np.float32);rates=v[:,common];assert np.all(rates.sum(1)>0)
    x[:,common]=np.log1p(rates/rates.sum(1)[:,None]*1e6)
    catalog=pd.read_parquet(root/'bridge-rna-latest/data/manifests/sample_manifest.parquet').set_index('gsm')
    m['pretraining_catalog']=m['sample'].map(catalog['split'].to_dict()).fillna('not_in_supplied_catalog')
    m.to_csv(out/'manifest.csv',index=False);pd.DataFrame(maps).to_csv(out/'label_column_audit.csv',index=False)
    pd.DataFrame({'gene':genes,'stable_id':stable,'entrez_id':entrez,'common_observed':common}).to_csv(out/'gene_mapping.csv',index=False)
    np.savez_compressed(out/'inputs.npz',x=x,observed=np.broadcast_to(common,x.shape),genes=genes,ids=m.id.to_numpy(str))
    programs=json.loads((root/'workstreams/spaceflight/runs/05_response_explanations_2026-09-14/programs.json').read_text())
    for p in programs:p['indices']=[i for i in p['indices'] if common[i]];assert len(p['indices'])>=10
    dump(out/'programs.json',programs)
    audit={'n_new_profiles':len(m),'n_training_profiles':38,'n_independent_donors':'Not established; IMR90 is one cell strain, culture replicates are not donors','common_genes':int(common.sum()),'canonical_total':len(genes),'input_sha256':sha(out/'inputs.npz'),'sample_counts':m.groupby(['study','cell_type','condition']).size().to_dict().__str__(),'catalog_counts':m.groupby(['study','pretraining_catalog']).size().to_dict().__str__(),'column_reconciliations':'BFX01: set capitalization + trailing A; BFX02: strip _sequence; all source pairs in label_column_audit.csv','metadata_conflicts':m[m.metadata_conflict!=''][['sample','metadata_conflict']].to_dict('records'),'sources':{p.name:sha(p) for p in src.iterdir() if p.is_file()},'normalization':'RPKM rescaled directly to common-canonical TPM; NCBI counts divided by pinned gene exon length then same TPM denominator; log1p once; missing positions masked','preparation_script_sha256':sha(Path(__file__))}
    dump(out/'input_audit.json',audit);dump(out/'STATUS.json',{'state':'prepared','samples':len(m),'common_genes':int(common.sum())})
    print('Prepared',len(m),'samples;',common.sum(),'common genes; training 38; catalog',m.groupby(['study','pretraining_catalog']).size().to_dict(),flush=True)


def infer(folder,checkpoint,official,config):
    import torch
    torch.set_num_threads(4);torch.manual_seed(17);torch.backends.cuda.matmul.allow_tf32=False
    cfg=json.loads(config.read_text());spec=importlib.util.spec_from_file_location('bridge_official',official);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    model=mod.ExpressionPerformer(num_genes=15165,hidden_dim=cfg['hidden_dim'],n_heads=cfg['num_heads'],n_layers=cfg['num_layers'],ffn_dim=cfg['ffn_dim'],ree_base=cfg['ree_base'],mask_token_id=cfg['mask_token'],feature_type=cfg['feature_type'],compute_type=cfg['compute_type'],include_species_embedding=cfg['include_species_embedding'],num_species=2)
    ck=torch.load(checkpoint,map_location='cpu',weights_only=True);model.load_state_dict(ck['model_state_dict'],strict=True);del ck;model.eval().cuda().requires_grad_(False)
    d=np.load(folder/'inputs.npz');means=[];stds=[];start=time.time()
    with torch.inference_mode():
        for i,row in enumerate(d['x']):
            h=model._encode_hidden(torch.tensor(np.nan_to_num(row,nan=-10)[None],device='cuda',dtype=torch.float32));means.append(h.mean(1).cpu().numpy()[0]);stds.append(h.std(1,unbiased=False).cpu().numpy()[0])
            if (i+1)%20==0 or i==len(d['x'])-1:print('EMBED',i+1,'/',len(d['x']),'seconds',round(time.time()-start,1),flush=True)
    np.savez_compressed(folder/'embeddings.npz',mean=np.array(means),std=np.array(stds),ids=d['ids'])
    dump(folder/'inference_report.json',{'samples':len(means),'seconds':time.time()-start,'device':torch.cuda.get_device_name(),'peak_memory_GB':torch.cuda.max_memory_allocated()/1e9,'input_sha256':sha(folder/'inputs.npz'),'checkpoint_sha256':sha(checkpoint),'official_source_sha256':sha(official),'script_sha256':sha(Path(__file__)),'encoder_updated':False})
    (folder/'INFERENCE_COMPLETE').write_text('complete\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['prepare','infer']);p.add_argument('--root',type=Path);p.add_argument('--folder',type=Path,required=True);p.add_argument('--checkpoint',type=Path);p.add_argument('--official',type=Path);p.add_argument('--config',type=Path);a=p.parse_args()
    if a.phase=='prepare':prepare(a.root,a.folder)
    else:infer(a.folder,a.checkpoint,a.official,a.config)
