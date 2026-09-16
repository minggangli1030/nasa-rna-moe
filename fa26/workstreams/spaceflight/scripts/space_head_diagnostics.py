"""Post-pilot diagnostic inputs and bounded remedies; no independent-confirmation claim."""
from pathlib import Path
import json,re,hashlib,argparse,importlib.util,time
import numpy as np
import pandas as pd
ROOT=next((p for p in Path(__file__).resolve().parents if (p/'bridge-rna-latest').is_dir()), Path(__file__).resolve().parent)
OUT=ROOT/'artifacts/space_head_diagnostics_2026-09-14'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def fields(path):
    out={}
    for block in path.read_text().split('^SAMPLE = ')[1:]:
        lines=block.splitlines();d={}
        for line in lines[1:]:
            if ' = ' in line:
                k,v=line.split(' = ',1);d.setdefault(k,[]).append(v)
        out[lines[0].strip()]=d
    return out

def prepare():
    import space_head_pilot as pilot
    m,_,_,_=pilot.load();m.to_csv(OUT/'cohort.csv',index=False)
    sources=[ROOT/'artifacts/general_survey_2026-09-12',ROOT/'artifacts/muscle_repeat_flight_2026-09-12']
    annotations=[fields(OUT/'GSE234465_samples.soft'),fields(sources[1]/'GSE298393_samples.soft')]
    labelaudit=[];raw=[];obs=[]
    for k,(folder,study) in enumerate(zip(sources,m.study.unique())):
        meta=pd.read_csv(folder/'manifest.csv');d=np.load(folder/'inputs.npz');ix=np.flatnonzero(meta.study.eq(study));raw.append(d['x'][ix]);obs.append(d['observed'][ix])
        for row in m[m.study==study].itertuples():
            f=annotations[k][row.sample];title=f['!Sample_title'][0]
            if k==0:
                treatment=next(v for v in f['!Sample_characteristics_ch1'] if v.startswith('treatment:'))
                expected=0 if 'Earth control' in treatment else 1 if 'Space' in treatment or 'space' in treatment or 'microgravity' in treatment else None
                sourcecol=title.replace('GC-OS-NOES-','GC-OS-NOS-').replace('GC-YA-NOES-','GC-YA-NOS-')
            else:
                treatment=title;expected=1 if 'microgravity' in title else 0 if 'ground control' in title else None
                mat=re.search(r'muscle_(YA|OS)_NoEstim_(TOCO2GC_|SpX25)_+Chip_(\d+)',f['!Sample_description'][0]);assert mat
                pool,env,chip=mat.groups();sourcecol=f'{pool}-NoEstim-'+('TOCO2GC--' if env.startswith('TOCO') else 'SpX25-')+f'Chip-{chip}'
                assert sourcecol==row.source_column
            assert expected==int(row.label),(row.sample,treatment,expected)
            assert title==row.title
            labelaudit.append({'id':row.id,'label':int(row.label),'GEO_treatment':treatment,'source_column':sourcecol,'matches':True,'instrument':f.get('!Sample_instrument_model',['unknown'])[0],'library_selection':f.get('!Sample_library_selection',['unknown'])[0]})
    pd.DataFrame(labelaudit).to_csv(OUT/'label_source_audit.csv',index=False)
    genes=np.load(sources[1]/'inputs.npz')['genes'];original=np.concatenate(raw).astype(np.float32)
    orth=pd.read_csv(ROOT/'bridge-rna-latest/data/ensembl/orthologs_one2one.txt',sep='\t').set_index('Human gene name').loc[genes]
    fp=[];found=[];sourcefiles=[]
    for k,name in enumerate(['GSE234465_FPKM.txt.gz','GSE298393_genes.rawmatrix.tsv.gz']):
        p=sources[1]/name;f=pd.read_csv(p,sep='\t');ids=f.iloc[:,0].astype(str).str.split('.').str[0];assert not ids.duplicated().any();lookup={s:i for i,s in enumerate(ids)};ix=np.array([lookup.get(s,-1) for s in orth['Human gene stable ID']]);present=ix>=0;found.append(present);a=[]
        for r in labelaudit[k*12:(k+1)*12]:
            z=np.full(len(genes),np.nan);z[present]=f[r['source_column']].to_numpy(float)[ix[present]];assert np.isfinite(z[present]).all() and (z[present]>=0).all();a.append(z)
        fp.extend(a);sourcefiles.append(p)
    common=np.concatenate(obs).all(0)&found[0]&found[1];fp=np.array(fp);harm=np.full_like(fp,np.nan,dtype=np.float32);harm[:,common]=np.log1p(fp[:,common]/fp[:,common].sum(1)[:,None]*1e6)
    panel=json.loads((ROOT/'artifacts/pathway_onboard_1g_2026-09-13/mapped_panel.json').read_text())
    # Full Hallmark collection, fixed independently of this diagnosis; exact canonical symbols.
    modules=[]
    for line in (ROOT/'artifacts/pathway_onboard_1g_2026-09-13/hallmark_2020.gmt').read_text().splitlines():
        parts=line.split('\t');members=set(parts[2:]);ix=np.array([i for i,g in enumerate(genes) if common[i] and g in members]);
        if len(ix)>=10:modules.append({'name':parts[0],'indices':ix.tolist(),'n_genes':len(ix)})
    assert len(modules)==50
    (OUT/'modules.json').write_text(json.dumps(modules,indent=2)+'\n')
    np.savez_compressed(OUT/'inputs.npz',original=original,harmonized=harm,genes=genes,ids=m.id.to_numpy(str),common=common)
    (OUT/'input_audit.json').write_text(json.dumps({'label_checks':24,'common_genes':int(common.sum()),'normalization':'Both author-annotated FPKM, same 15137-gene denominator, log1p once, full canonical positions retained with NaN for missing; no gene-length division','limitation':'Units follow GEO annotations. Both FPKM does not mean identical upstream read processing.','sha256':{str(p.relative_to(ROOT)):sha(p) for p in sourcefiles}},indent=2)+'\n')
    print('Prepared',harm.shape,'common',common.sum(), 'modules',len(modules))

def infer(folder,checkpoint,official,config):
    import torch
    torch.set_num_threads(4);torch.manual_seed(1701);torch.backends.cuda.matmul.allow_tf32=False
    cfg=json.loads(config.read_text());spec=importlib.util.spec_from_file_location('bridge_official',official);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    model=mod.ExpressionPerformer(num_genes=15165,hidden_dim=cfg['hidden_dim'],n_heads=cfg['num_heads'],n_layers=cfg['num_layers'],ffn_dim=cfg['ffn_dim'],ree_base=cfg['ree_base'],mask_token_id=cfg['mask_token'],feature_type=cfg['feature_type'],compute_type=cfg['compute_type'],include_species_embedding=cfg['include_species_embedding'],num_species=2)
    ck=torch.load(checkpoint,map_location='cpu',weights_only=True);model.load_state_dict(ck['model_state_dict'],strict=True);del ck;model.eval().cuda()
    d=np.load(folder/'inputs.npz');modules=json.loads((folder/'modules.json').read_text());inds=[torch.tensor(v['indices'],device='cuda') for v in modules];result={};started=time.time()
    with torch.inference_mode():
        for variant in ['original','harmonized']:
            for n,row in enumerate(d[variant]):
                x=torch.from_numpy(np.nan_to_num(row,nan=-10)[None]).cuda();ids=torch.arange(15165,device='cuda');h=model.gene_embedding(ids).unsqueeze(0)+model.ree(x)
                if model.include_species_embedding:h=h+model.species_embedding(torch.zeros(1,dtype=torch.long,device='cuda')).unsqueeze(1)
                for j,layer in enumerate(model.layers,1):
                    h=layer(h)
                    if j in ([12] if variant=='original' else [1,6,11,12]):
                        v=torch.cat([h.mean(1),h.std(1,unbiased=False)],1).cpu().numpy()[0];result.setdefault(f'{variant}_L{j}_meanstd',[]).append(v)
                if variant=='harmonized':
                    v=torch.cat([torch.cat([h[:,ix].mean(1),h[:,ix].std(1,unbiased=False)],1) for ix in inds],1).cpu().numpy()[0];result.setdefault('harmonized_modules_meanstd',[]).append(v)
                if (n+1)%6==0:print(variant,n+1,'/24 seconds',round(time.time()-started,1),flush=True)
    np.savez_compressed(folder/'readouts.npz',**{k:np.asarray(v) for k,v in result.items()},ids=d['ids'])
    (folder/'inference_report.json').write_text(json.dumps({'samples':48,'seconds':time.time()-started,'device':torch.cuda.get_device_name(),'checkpoint_sha256':sha(checkpoint),'official_source_sha256':sha(official),'input_sha256':sha(folder/'inputs.npz'),'script_sha256':sha(Path(__file__)),'encoder_updated':False},indent=2)+'\n')
    (folder/'INFERENCE_COMPLETE').write_text('complete\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['prepare','infer']);p.add_argument('--folder',type=Path);p.add_argument('--checkpoint',type=Path);p.add_argument('--official',type=Path);p.add_argument('--config',type=Path);a=p.parse_args()
    if a.phase=='prepare':prepare()
    else:infer(a.folder,a.checkpoint,a.official,a.config)
