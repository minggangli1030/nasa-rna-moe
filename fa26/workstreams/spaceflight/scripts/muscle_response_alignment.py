"""Fixed-probe/fixed-flight-head alignment, with paired human muscle EPS controls."""
from pathlib import Path
import argparse,json,itertools
import numpy as np,pandas as pd,joblib
from scipy.stats import rankdata
from controlled_exposure_pilot import samples,sha,dump
from evaluate_controlled_exposure import fit


def prepare(root,out,prior):
    assert not (out/'inputs.npz').exists()
    diag=root/'artifacts/space_head_diagnostics_2026-09-14';d=np.load(diag/'inputs.npz');m=pd.read_csv(diag/'cohort.csv').fillna('');r=np.load(prior/'inputs.npz');common=r['observed'].all(0);full=d['common'];genes=d['genes'];mapping=pd.read_csv(prior/'gene_mapping.csv');assert np.array_equal(genes,r['genes']) and (full|~common).all()
    counts=pd.read_csv(out/'sources/GSE200335_raw_counts_GRCh38.p13_NCBI.tsv.gz',sep='\t').set_index('GeneID');assert counts.index.is_unique;entrez=mapping.entrez_id.to_numpy(int)
    lengths=pd.read_csv(root/'bridge-rna-latest/data/gencode/gencode_v49_gene_exon_lengths.csv').set_index('gene_symbol').exon_length.reindex(genes).to_numpy(float)
    # Full flight mask includes some genes not mapped to unique Entrez. Keep primary radiation mask exact.
    available=np.isin(entrez,counts.index)&np.isfinite(lengths)&(lengths>0);assert available[common].all()
    epsfull=full&available
    catalog=pd.read_parquet(root/'bridge-rna-latest/data/manifests/sample_manifest.parquet').set_index('gsm')['split'].to_dict()
    rows=[];values=[]
    for route in ['original','harmonized']:
      for i,row in m.iterrows():
        x=np.full(len(genes),np.nan,np.float32);mass=np.expm1(d[route][i,common].astype(float));x[common]=np.log1p(mass/mass.sum()*1e6)
        values.append(x);rows.append({'id':row.id+'|'+route,'biological_id':row.id,'sample':row['sample'],'study':row.study,'group':row.stratum,'condition':'flight' if row.label else 'control','label':int(row.label),'route':route,'donor':row.stratum,'source':'prior_audited_flight_inputs','original_index':i,'catalog':catalog.get(row['sample'],'absent')})
    for s in samples(out/'sources/GSE200335_family.soft.gz'):
        chars=dict(v.split(': ',1) for v in s['characteristics_ch1']);assert s['organism_ch1']==['Homo sapiens'] and s['library_strategy']==['RNA-Seq'];title=s['title'][0];donor,suffix=title.split('-');label=int(chars['treatment']=='electrical pulse stimulation');assert label==int(suffix=='EPS')
        for route,mask in [('harmonized',common),('wider_gene_mask',epsfull)]:
            rates=counts[s['gsm']].reindex(entrez[mask]).to_numpy(float)/lengths[mask];assert np.isfinite(rates).all() and (rates>=0).all();x=np.full(len(genes),np.nan,np.float32);x[mask]=np.log1p(rates/rates.sum()*1e6)
            values.append(x);rows.append({'id':'GSE200335:'+s['gsm']+'|'+route,'biological_id':'GSE200335:'+s['gsm'],'sample':s['gsm'],'study':'GSE200335','group':donor,'condition':'EPS' if label else 'control','label':label,'route':route,'donor':donor,'source':'NCBI_counts','original_index':-1,'catalog':catalog.get(s['gsm'],'absent')})
    mm=pd.DataFrame(rows);xx=np.array(values);assert len(mm)==76 and mm.id.is_unique
    primary=mm[(mm.study=='GSE200335')&(mm.route=='harmonized')];assert primary.groupby('donor').label.agg(['count','sum']).eq([2,1]).all().all()
    np.savez_compressed(out/'inputs.npz',x=xx,observed=np.isfinite(xx),genes=genes,ids=mm.id.to_numpy(str));mm.to_csv(out/'manifest.csv',index=False)
    dump(out/'input_audit.json',{'n_encoded_profiles':len(mm),'biological_samples':int(mm.biological_id.nunique()),'new_biological_samples':14,'new_donors':7,'common_genes':int(common.sum()),'flight_original_mask':int(full.sum()),'EPS_wider_mask':int(epsfull.sum()),'missing_EPS_Entrez_from_full_flight_mask':genes[full&~available].tolist(),'all_radiation_training_genes_present':True,'all_primary_EPS_title_treatment_pairs_agree':True,'new_catalog':primary.catalog.value_counts().to_dict(),'input_sha256':sha(out/'inputs.npz'),'source_sha256':{p.name:sha(p) for p in (out/'sources').glob('*')},'public_sources':['https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE200335','https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE234465','https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE298393']})
    print('Prepared',len(mm),'encodings /',mm.biological_id.nunique(),'samples. EPS catalog:',primary.catalog.value_counts().to_dict(),flush=True)


def effective(head):
    support=head.named_steps['variance'].get_support();sc=head.named_steps['scale'];beta=head.named_steps['head'].coef_[0];w=np.zeros(len(support));w[support]=beta/sc.scale_;b=float(head.named_steps['head'].intercept_[0]-np.dot(beta,sc.mean_/sc.scale_));scale=np.ones(len(support));scale[support]=sc.scale_;return w,b,scale


def evaluate(root,out,prior):
    assert not (out/'sample_scores.csv').exists()
    m=pd.read_csv(out/'manifest.csv').fillna('');e=np.load(out/'embeddings.npz');d=np.load(out/'inputs.npz');z=np.c_[e['mean'],e['std']].astype(float);assert m.id.tolist()==e['ids'].tolist()==d['ids'].tolist();assert sha(out/'inputs.npz')==json.loads((out/'inference_report.json').read_text())['input_sha256']
    a=np.load(root/'artifacts/space_head_attribution_2026-09-14/attribution_inputs.npz');dm=pd.read_csv(root/'artifacts/space_head_diagnostics_2026-09-14/cohort.csv');dz=np.load(root/'artifacts/space_head_diagnostics_2026-09-14/readouts.npz')['harmonized_L12_meanstd'].astype(float)
    head_scores={};probeinfo={};sample=[]
    for source in ['ncbi','original']:
        head=joblib.load(prior/'heads'/f'{source}__bridge__ir_control__absolute.joblib');w,b,scale=effective(head);scores=z@w+b;assert np.allclose(scores,head.decision_function(z),rtol=1e-9,atol=1e-9);head_scores['probe_'+source]=scores;probeinfo[source]=(w,b,scale)
    for pool in ['YA','OS']:head_scores['flight_'+pool]=z@a[pool+'_weight']+float(a[pool+'_bias'])
    for name,scores in head_scores.items():
      for i,score in enumerate(scores):sample.append({**m.iloc[i].to_dict(),'head':name,'score':float(score),'positive':bool(score>=0),'interpretation':'uncalibrated score; EPS is neither flight nor radiation; flight probe score is not an exposure measurement'})
    ss=pd.DataFrame(sample);ss.to_csv(out/'sample_scores.csv',index=False)
    # Group/donor shifts use only within-context controls, without target fitting.
    shifts=[]
    for (study,group,route),g in m.groupby(['study','group','route']):
        i=g.index.to_numpy();pos=i[g.label.to_numpy()==1];neg=i[g.label.to_numpy()==0];assert len(pos)>0 and len(neg)>0
        for name,scores in head_scores.items():shifts.append({'study':study,'group':group,'route':route,'head':name,'n_treated':len(pos),'n_control':len(neg),'treated_minus_control':float(scores[pos].mean()-scores[neg].mean()),'control_mean':float(scores[neg].mean()),'treated_mean':float(scores[pos].mean()),'treated_positive_fraction':float((scores[pos]>=0).mean()),'control_positive_fraction':float((scores[neg]>=0).mean())})
    sh=pd.DataFrame(shifts);sh.to_csv(out/'within_context_shifts.csv',index=False)
    # Prior unmodified flight representation is a coverage/source sensitivity, not extra samples.
    coverage=[]
    for source,(w,b,scale) in probeinfo.items():
      for route in ['original','harmonized']:
        priorz=np.load(root/'artifacts/space_head_diagnostics_2026-09-14/readouts.npz')[route+'_L12_meanstd'].astype(float)
        for name,weights,bias in [('probe_'+source,w,b)]+[(f'flight_{pool}',a[f'{pool}_weight'],float(a[f'{pool}_bias'])) for pool in ['YA','OS']]:
            oldscore=priorz@weights+bias
            for i,row in dm.iterrows():
                newix=m.index[(m.biological_id==row.id)&(m.route==route)][0];coverage.append({'id':row.id,'study':row.study,'pool':row.stratum,'label':row.label,'route':route,'head':name,'prior_mask_score':float(oldscore[i]),'matched_mask_score':float(head_scores[name][newix]),'score_change':float(head_scores[name][newix]-oldscore[i])})
    pd.DataFrame(coverage).drop_duplicates().to_csv(out/'coverage_sensitivity.csv',index=False)
    projections=[];align=[]
    for source,(wp,bp,scale) in probeinfo.items():
      for metric,s in [('raw',np.ones(1024)),('probe_training_scaled',scale)]:
        n=wp*s;n=n/np.linalg.norm(n)
        for pool in ['YA','OS']:
            wf=a[pool+'_weight'];wb=float(a[pool+'_bias']);coupling=float(np.dot(wf*s,n));align.append({'probe_source':source,'metric':metric,'flight_training_pool':pool,'directional_flight_slope':coupling,'cosine':float(coupling/np.linalg.norm(wf*s))})
            for route in ['original','harmonized']:
                trainref=m.index[(m.study=='GSE298393')&(m.group==pool)&(m.label==0)&(m.route==route)].to_numpy();assert len(trainref)==3;ref=z[trainref].mean(0)
                for i,row in m[m.route==route].iterrows():
                    if row.study=='GSE298393' and row.group==pool:continue
                    q=(z[i]-ref)/s;c=float(q@n);part=c*coupling;delta=float((z[i]-ref)@wf);removed=z[i]-s*n*c
                    assert abs((removed-ref)@wp)<1e-7
                    assert abs((z[i]@wf+wb)-(removed@wf+wb)-part)<1e-7
                    projections.append({'id':row.id,'study':row.study,'group':row.group,'label':row.label,'route':route,'probe_source':source,'metric':metric,'flight_training_pool':pool,'concept_displacement':c,'flight_score_delta':delta,'projected_component':part,'residual_component':delta-part,'projection_is_not_biological_intervention':True})
    pp=pd.DataFrame(projections);pp.to_csv(out/'projection_components.csv',index=False);pd.DataFrame(align).to_csv(out/'head_direction_alignment.csv',index=False)
    projshifts=[]
    for keys,g in pp.groupby(['study','group','route','probe_source','metric','flight_training_pool']):
        pos=g[g.label==1];neg=g[g.label==0]
        projshifts.append(dict(zip(['study','group','route','probe_source','metric','flight_training_pool'],keys),score_gap=float(pos.flight_score_delta.mean()-neg.flight_score_delta.mean()),projected_gap=float(pos.projected_component.mean()-neg.projected_component.mean()),residual_gap=float(pos.residual_component.mean()-neg.residual_component.mean())))
    pd.DataFrame(projshifts).to_csv(out/'projection_contrast_summary.csv',index=False)
    # Training-source deletion stability: fixed original C1 protocol, no muscle outcome tuning.
    rm=pd.read_csv(prior/'manifest.csv');rz=np.load(prior/'embeddings.npz');rz=np.c_[rz['mean'],rz['std']].astype(float);tr=np.flatnonzero(rm.training_eligible);yy=rm.radiation_label.to_numpy(int);stab=[]
    for omitted in sorted(rm.iloc[tr].source_file.unique()):
        keep=tr[rm.iloc[tr].source_file.to_numpy()!=omitted];head=fit('bridge',rz[keep],yy[keep]);scores=head.decision_function(z)
        for (study,group),g in m[m.route=='harmonized'].groupby(['study','group']):
            i=g.index.to_numpy();delta=scores[i][g.label==1].mean()-scores[i][g.label==0].mean();stab.append({'omitted_source':omitted,'study':study,'group':group,'probe_shift':float(delta)})
    pd.DataFrame(stab).to_csv(out/'probe_training_source_sensitivity.csv',index=False)
    # Fixed six-program vocabulary: expression only, not new inferred labels.
    programs=json.loads((root/'workstreams/spaceflight/runs/06_controlled_exposure_validation_2026-09-14/programs.json').read_text());programrows=[]
    for (study,group,route),g in m[m.route!='wider_gene_mask'].groupby(['study','group','route']):
        i=g.index.to_numpy();labels=g.label.to_numpy();common=d['observed'][i].all(0);geneix=np.flatnonzero(common);rank=rankdata(d['x'][i][:,common],axis=1)/common.sum()
        for program in programs:
            ix=np.array(program['indices']);assert common[ix].all();score=d['x'][i][:,ix].mean(1);rscore=rank[:,np.searchsorted(geneix,ix)].mean(1);programrows.append({'study':study,'group':group,'route':route,'program':program['key'],'mean_log1p_shift':float(score[labels==1].mean()-score[labels==0].mean()),'rank_shift':float(rscore[labels==1].mean()-rscore[labels==0].mean())})
    pd.DataFrame(programrows).to_csv(out/'program_expression_shifts.csv',index=False)
    dump(out/'verification.json',{'ids_and_input_hash_match':True,'all_76_encodings_finite':bool(np.isfinite(z).all()),'effective_probe_weights_reproduce_pipeline':True,'projected_probe_change_removed_to_reference':True,'projected_plus_residual_reproduces_flight_delta':True,'no_flight_training_pool_scored_as_heldout':True,'no_head_or_encoder_training_on_muscle_outcomes':True,'script_sha256':sha(Path(__file__))})
    print(sh[(sh.route=='harmonized')].to_string(index=False));print('\nHEAD DIRECTIONS');print(pd.DataFrame(align).to_string(index=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['prepare','evaluate']);p.add_argument('--root',type=Path,default=Path('fa26'));p.add_argument('--folder',type=Path,required=True);p.add_argument('--prior',type=Path,default=Path('fa26/workstreams/spaceflight/runs/07_radiation_robustness_audit_2026-09-15'));a=p.parse_args()
    if a.phase=='prepare':prepare(a.root,a.folder,a.prior)
    else:evaluate(a.root,a.folder,a.prior)
