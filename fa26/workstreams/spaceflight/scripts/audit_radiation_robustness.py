"""Prespecified source-harmonization and matched-control audit; no encoder fitting."""
from pathlib import Path
import argparse,json,hashlib,itertools,re,datetime
import numpy as np
import pandas as pd
import joblib
from scipy.spatial.distance import pdist,squareform
from scipy.stats import spearmanr
from controlled_exposure_pilot import samples,sha,dump
from evaluate_controlled_exposure import fit,metrics


def prepare(root,out,old):
    assert not (out/'inputs.npz').exists()
    m0=pd.read_csv(old/'manifest.csv').fillna('');d0=np.load(old/'inputs.npz');mapping=pd.read_csv(old/'gene_mapping.csv');genes=d0['genes'];common=d0['observed'].all(0)
    lengths=pd.read_csv(root/'bridge-rna-latest/data/gencode/gencode_v49_gene_exon_lengths.csv').set_index('gene_symbol').exon_length.reindex(genes).to_numpy(float)
    tables={s:pd.read_csv((old if s=='GSE242706' else out)/'sources'/f'{s}_raw_counts_GRCh38.p13_NCBI.tsv.gz',sep='\t').set_index('GeneID') for s in ['GSE230181','GSE242706','GSE111437']}
    ids=mapping.entrez_id.to_numpy(int)
    for t in tables.values():assert t.index.is_unique;assert np.isin(ids[common],t.index).all()
    assert np.isfinite(lengths[common]).all()
    keep=(m0.study!='GSE230181')|m0['sample'].isin(tables['GSE230181'].columns)
    m0[~keep].to_csv(out/'missing_ncbi_samples.csv',index=False)
    m=m0[keep].copy();m['original_index']=m.index;m=m.reset_index(drop=True)
    catalog=pd.read_parquet(root/'bridge-rna-latest/data/manifests/sample_manifest.parquet').set_index('gsm')['split'].to_dict()
    rows=[]
    for s in samples(out/'sources/GSE111437_family.soft.gz'):
        if s['gsm'] not in tables['GSE111437'].columns:continue
        assert s['library_strategy']==['RNA-Seq'] and s['organism_ch1']==['Homo sapiens']
        c=dict(v.split(': ',1) for v in s['characteristics_ch1']);dose=int(c['dose x-ray (gy)']);time=c['time point (h)'];title=s['title'][0]
        assert f'_{dose}Gy_{time}_' in title and c['cell line']=='IMR90'
        rows.append(dict(id='GSE111437:'+s['gsm'],sample=s['gsm'],study='GSE111437',species='human',cell_type='IMR90',condition='irradiated' if dose else 'control',radiation_label=int(dose>0),training_eligible=False,source_file='NCBI_gene_counts',source_column=s['gsm'],description_column=s['gsm'],experiment_set=time,replicate=int(title.split('_')[3]),time=time,dose_Gy=dose,title=title,agent=f'{dose}Gy X-ray',group='normal',source_units='NCBI gene counts',metadata_conflict='',pretraining_catalog=catalog.get(s['gsm'],'not_in_supplied_catalog'),original_index=-1))
    assert len(rows)==12
    m=pd.concat([m,pd.DataFrame(rows)],ignore_index=True)
    values=[]
    for _,r in m.iterrows():
        v=tables[r.study][r['sample']].reindex(ids[common]).to_numpy(float)/lengths[common]
        assert np.isfinite(v).all() and (v>=0).all() and v.sum()>0
        values.append(np.log1p(v/v.sum()*1e6))
    x=np.full((len(m),len(genes)),np.nan,dtype=np.float32);x[:,common]=values
    # Original route comparator differs only in GSE230181 processing; common samples/genes stay fixed.
    original=x.copy();old_ix=m.original_index.to_numpy(int);original[old_ix>=0]=d0['x'][old_ix[old_ix>=0]]
    assert np.array_equal(x[m.study=='GSE242706'],original[m.study=='GSE242706'],equal_nan=True)
    np.savez_compressed(out/'inputs.npz',x=x,observed=np.broadcast_to(common,x.shape),genes=genes,ids=m.id.to_numpy(str))
    np.savez_compressed(out/'original_inputs.npz',x=original,ids=m.id.to_numpy(str))
    m.to_csv(out/'manifest.csv',index=False);mapping.to_csv(out/'gene_mapping.csv',index=False)
    comparisons=[]
    for i in np.flatnonzero(m.study=='GSE230181'):
        comparisons.append({'id':m.iloc[i].id,'condition':m.iloc[i].condition,'spearman_expression':float(spearmanr(x[i,common],original[i,common]).statistic),'mean_abs_log1p_difference':float(np.abs(x[i,common]-original[i,common]).mean())})
    pd.DataFrame(comparisons).to_csv(out/'processing_comparison.csv',index=False)
    # Audit nearest profiles as well as exact duplicates (correlated cultures are not independent donors).
    dist=squareform(pdist(x[:,common],metric='euclidean'));np.fill_diagonal(dist,np.inf)
    near=dist.argmin(1);pd.DataFrame({'id':m.id,'nearest_id':m.id.iloc[near].to_numpy(),'euclidean_distance':dist[np.arange(len(m)),near],'different_study':m.study.to_numpy()!=m.study.iloc[near].to_numpy()}).to_csv(out/'nearest_samples.csv',index=False)
    assert not (dist==0).any(),'Exact duplicate profiles require resolution before fitting'
    sourcehash={p.name:sha(p) for p in (out/'sources').iterdir() if p.is_file()}
    sourcehash['GSE242706_counts']=sha(old/'sources/GSE242706_raw_counts_GRCh38.p13_NCBI.tsv.gz')
    dump(out/'input_audit.json',{'samples':len(m),'common_genes':int(common.sum()),'missing_old_samples':m0.loc[~keep,'sample'].tolist(),'original_route_comparator':'Identical retained sample IDs and 15061 genes; prior run06 profiles/embeddings reused where appropriate','training_n':int(m.training_eligible.sum()),'new_challenge_counts':m[m.study=='GSE111437'].groupby(['time','condition']).size().to_string(),'catalog_new':m[m.study=='GSE111437'].pretraining_catalog.value_counts().to_dict(),'no_exact_profile_duplicates':True,'labels':'GSE111437 titles and dose/time characteristics agree for all 12 RNA-seq samples; old source mappings retained from audited run06','source_sha256':sourcehash,'inputs_sha256':sha(out/'inputs.npz'),'protocol_sha256':sha(out/'protocol.json'),'prepare_script_sha256':sha(Path(__file__)),'public_sources':['https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc='+s for s in tables]})
    dump(out/'reference_implementation.json',{'timing':'Before model outcomes','reference_size':'min(2, n_control-1); necessary because one retained B control was unavailable in NCBI counts','contexts':'Study/source/cell/experiment; normal IMR90 BFX36 vehicle+drugs form a separate vehicle reference context from quiescent-control+IR set D; BFX02 rotenone shares control set E. Ras excluded from training and evaluated separately.','training_reference':'Only control/vehicle samples within training partition; leave focal control out of its reference','test_reference':'Every possible reference subset; references disjoint from scored samples; no external irradiated sample fitted','interpretation':'Repeated calibration choices are dependent sensitivity analyses, not additional independent sample size; reference subtraction happens on frozen expression/embedding features, not before encoder inference'})
    print(json.dumps(json.loads((out/'input_audit.json').read_text()),indent=2))


def context(r):
    group=r.experiment_set
    if r.study=='GSE230181' and r.cell_type=='IMR90':
        if r.source_file=='BFX36_expr.txt' and r.condition in ['vehicle','bleomycin','antimycin','oligomycin']:group='D_vehicle'
        elif r.source_file=='BFX02_expr.txt':group='E'
    return '|'.join([r.study,r.source_file,r.cell_type,group])


def evaluate(out,old):
    assert not (out/'metrics.csv').exists()
    m=pd.read_csv(out/'manifest.csv').fillna('');d=np.load(out/'inputs.npz');e=np.load(out/'embeddings.npz');original=np.load(out/'original_inputs.npz');eo=np.load(old/'embeddings.npz');report=json.loads((out/'inference_report.json').read_text())
    assert sha(out/'inputs.npz')==report['input_sha256'];assert m.id.tolist()==d['ids'].tolist()==e['ids'].tolist()
    common=d['observed'].all(0);z=np.c_[e['mean'],e['std']].astype(float);zo=z.copy();oi=m.original_index.to_numpy(int);zo[oi>=0]=np.c_[eo['mean'],eo['std']][oi[oi>=0]]
    inputs={'ncbi':{'expression':d['x'][:,common].astype(float),'bridge':z},'original':{'expression':original['x'][:,common].astype(float),'bridge':zo}}
    assert all(np.isfinite(v).all() for f in inputs.values() for v in f.values())
    y=m.radiation_label.to_numpy(int);ctx=np.array([context(r) for _,r in m.iterrows()]);isctrl=m.condition.isin(['control','vehicle']).to_numpy();basic=np.flatnonzero(m.training_eligible);hard=np.flatnonzero((m.study=='GSE230181')&(m.cell_type=='IMR90')&(m.group=='normal'))
    rows=[];preds=[];splitrows=[];fitcount=0
    (out/'heads').mkdir(exist_ok=True)
    def delta_train(x,tr):
        xx=[]
        for i in tr:
            cc=tr[(ctx[tr]==ctx[i])&isctrl[tr]&(tr!=i)];assert len(cc)>0
            xx.append(x[i]-x[cc].mean(0))
        return np.array(xx)
    for route,features in inputs.items():
      for feature,x in features.items():
       for target,train in [('ir_control',basic),('hard_negative',hard)]:
        for mode in ['absolute','matched_control']:
          model_id='__'.join([route,feature,target,mode]);fitted={}
          groups=[('all',train)]+[(src,train[m.iloc[train].source_file.to_numpy()!=src]) for src in sorted(m.iloc[train].source_file.unique())]
          for source,tr in groups:
            xx=x[tr] if mode=='absolute' else delta_train(x,tr)
            fitted[source]=fit(feature,xx,y[tr]);fitcount+=1
          joblib.dump(fitted['all'],out/'heads'/f'{model_id}.joblib')
          # Evaluate all contexts; original source file is held out for training-study tests.
          for group in sorted(set(ctx)):
            idx=np.flatnonzero(ctx==group);sg=m.iloc[idx];study=sg.study.iloc[0];source=sg.source_file.iloc[0]
            if study=='GSE230181':
                tr=train[m.iloc[train].source_file.to_numpy()!=source];model=fitted.get(source,fitted['all']);evaluation='held_file' if sg.cell_type.iloc[0]=='IMR90' else 'other_cell_held_file'
            else:tr=train;model=fitted['all'];evaluation='new_2Gy_challenge' if study=='GSE111437' else 'lung_development'
            assert not set(tr)&set(idx)
            controls=idx[isctrl[idx]];assert len(controls)>=2
            calibrations=[()] if mode=='absolute' else list(itertools.combinations(controls,min(2,len(controls)-1)))
            for calibration,refs in enumerate(calibrations):
                refs=np.array(refs,dtype=int);te=idx[~np.isin(idx,refs)];assert not set(refs)&set(te);assert not set(refs)&set(tr)
                xx=x[te] if mode=='absolute' else x[te]-x[refs].mean(0)
                scores=model.decision_function(xx);assert np.isfinite(scores).all()
                record={'model':model_id,'route':route,'feature':feature,'training':target,'mode':mode,'evaluation':evaluation,'context':group,'study':study,'cell_type':sg.cell_type.iloc[0],'experiment':sg.experiment_set.iloc[0],'calibration':calibration,'n_reference':len(refs),'n_train':len(tr)}
                if len(np.unique(y[te]))==2:rows.append({**record,**metrics(y[te],scores)})
                for i,score in zip(te,scores):preds.append({**record,'id':m.iloc[i].id,'condition':m.iloc[i].condition,'label':int(y[i]),'score':float(score),'positive':int(score>=0),'metadata_conflict':bool(m.iloc[i].metadata_conflict)})
                for role,ii in [('train',tr),('reference',refs),('test',te)]:splitrows.extend({'model':model_id,'context':group,'calibration':calibration,'role':role,'id':m.iloc[i].id} for i in ii)
          print('COMPLETE',model_id,flush=True)
    res=pd.DataFrame(rows);pr=pd.DataFrame(preds);res.to_csv(out/'metrics.csv',index=False);pr.to_csv(out/'predictions.csv',index=False);pd.DataFrame(splitrows).to_csv(out/'splits.csv',index=False)
    # Conflicting cell-line metadata: remove ambiguous profiles from scoring AND reject calibration using them.
    ss=pd.DataFrame(splitrows);ambig=set(m.loc[m.metadata_conflict.ne(''),'id']);sensitivity=[]
    for key,g in pr[pr.evaluation=='lung_development'].groupby(['model','context','calibration']):
        refs=ss[(ss.model==key[0])&(ss.context==key[1])&(ss.calibration==key[2])&(ss.role=='reference')]
        if set(refs.id)&ambig:continue
        gg=g[~g.id.isin(ambig)]
        if gg.label.nunique()==2:sensitivity.append({'model':key[0],'context':key[1],'calibration':int(key[2]),**metrics(gg.label.to_numpy(),gg.score.to_numpy())})
    pd.DataFrame(sensitivity).to_csv(out/'metadata_exclusion_sensitivity.csv',index=False)
    # A head is fixed before challenge outcomes. All configurations retained, no challenge-based refitting.
    dump(out/'verification.json',{'fit_count':fitcount,'model_configurations':16,'finite_features_predictions':True,'source_file_disjoint_training':True,'calibration_controls_disjoint_from_test_and_training':True,'scaler_and_variance_training_only':True,'no_target_positive_fitting':True,'fixed_threshold':0,'all_heads_converged':True,'encoder_updated':False,'metrics_rows':len(res),'prediction_rows':len(pr),'input_sha256':sha(out/'inputs.npz'),'embedding_sha256':sha(out/'embeddings.npz'),'script_sha256':sha(Path(__file__)),'protocol_sha256':sha(out/'protocol.json')})
    print(res[res.evaluation.isin(['lung_development','new_2Gy_challenge'])].groupby(['evaluation','model'])[['auroc','balanced_accuracy']].agg(['min','max']).to_string())

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['prepare','evaluate']);p.add_argument('--root',type=Path,default=Path('fa26'));p.add_argument('--folder',type=Path,required=True);p.add_argument('--old',type=Path,default=Path('fa26/workstreams/spaceflight/runs/06_controlled_exposure_validation_2026-09-14'));a=p.parse_args()
    if a.phase=='prepare':prepare(a.root,a.folder,a.old)
    else:evaluate(a.folder,a.old)
