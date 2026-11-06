"""Response-program reliance in fixed BRIDGE heads; prepare locally, run on CUDA.

Program expression, signed attribution, and replacement sensitivity are different measures.
No new model is fitted and no exposure-specific labels are inferred from flight status.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import shutil
import time
import numpy as np
import pandas as pd

PANEL = [
    ('mitochondrial_expression', 'Mitochondrial expression', 'Oxidative Phosphorylation'),
    ('dna_repair', 'DNA repair expression', 'DNA Repair'),
    ('oxidative_stress', 'Oxidative-stress-associated expression', 'Reactive Oxygen Species Pathway'),
    ('inflammatory_signaling', 'Inflammatory signaling', 'TNF-alpha Signaling via NF-kB'),
    ('proteostasis', 'Unfolded-protein-response expression', 'Unfolded Protein Response'),
    ('muscle_remodeling', 'Muscle differentiation/remodeling', 'Myogenesis'),
]

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def dump(p, obj):
    p.write_text(json.dumps(obj, indent=2) + '\n')

def prepare(root, out):
    out.mkdir(parents=True, exist_ok=True)
    assert not (out/'protocol.json').exists(), 'Preserve prior runs; choose a new directory.'
    src = root/'artifacts/space_head_attribution_2026-09-14'
    diag = root/'artifacts/space_head_diagnostics_2026-09-14'
    # Freeze the design before inspecting program-specific outcomes.
    protocol = {
        'question': 'Which predefined response programs contribute to the existing flight score?',
        'study': 'GSE298393', 'n_chips': 12, 'independent_donor_pools': 2,
        'status_of_data': 'Previously explored development data; not independent confirmation',
        'encoder_updated': False, 'heads_updated': False,
        'programs': [{'key':k, 'label':label, 'gene_set':gs} for k,label,gs in PANEL],
        'references': ['training_ground_mean_TPM','training_all_mean_TPM'],
        'random_panels_per_program_per_head': 20,
        'random_matching': 'Exact joint training log1p-expression mean/SD quintile-bin counts; without replacement; excludes target set',
        'seed': 20260914,
        'primary_perturbation': 'Replace program inputs with training-ground reference; no TPM renormalization',
        'sensitivities': ['Training-all reference', 'TPM renormalization of target and all matched controls'],
        'expression_score': 'Mean per-gene log1p TPM difference from reference; not a functional activity measurement',
        'allocation': 'Split each gene IG equally among selected program memberships; outside-panel bucket; supporting and opposing totals separate',
        'decision': 'Descriptive pilot; no causal fractions, no radiation/gravity detector, no independent significance claim',
        'validation': ['Reproduce fixed logits within 1e-5', 'Exact random-bin matching and disjoint panels', 'Finite scores', 'Expression replacement equals summed linear attribution', 'Complete balanced sample/reference/panel matrix', 'Allocation reconstructs total attribution'],
        'replication': 'Two reciprocal head/pool directions, two references, leave-one-evaluation-chip sensitivity; shared biological pools',
    }
    dump(out/'protocol.json', protocol)
    for name in ['attribution_inputs.npz','folds.json','cohort.csv','attribution_rows.csv','attributions.npz','integration_checks.csv','expression_attributions.npz','expression_scores.csv']:
        shutil.copy2(src/name, out/name)
    d = np.load(out/'attribution_inputs.npz')
    x = np.nan_to_num(d['x'], nan=-10).astype(np.float32)
    assert x.shape == (12,15165) and np.isfinite(x).all()
    common = d['common'].astype(bool)
    modules = {m['name']:m for m in json.loads((diag/'modules.json').read_text())}
    gmt = root/'artifacts/pathway_onboard_1g_2026-09-13/hallmark_2020.gmt'
    source_sets = {line.split('\t')[0]:set(line.split('\t')[2:]) for line in gmt.read_text().splitlines()}
    programs = []
    membership = np.zeros((len(PANEL),len(common)),dtype=bool)
    for j,(key,label,gs) in enumerate(PANEL):
        ix = np.asarray(modules[gs]['indices'],int)
        assert common[ix].all() and len(ix)==len(set(ix))
        expected = np.flatnonzero(common & np.isin(d['genes'],list(source_sets[gs])))
        assert np.array_equal(ix,expected), 'Program mapping must reproduce the source GMT.'
        membership[j,ix] = True
        programs.append({'key':key,'label':label,'gene_set':gs,'indices':ix.tolist(),'n_genes':len(ix),'source_size':len(source_sets[gs]),'coverage':len(ix)/len(source_sets[gs])})
    dump(out/'programs.json',programs)
    overlap=[]
    for j,a in enumerate(programs):
        for k,b in enumerate(programs):
            inter=int((membership[j]&membership[k]).sum());union=int((membership[j]|membership[k]).sum())
            overlap.append({'program_a':a['key'],'program_b':b['key'],'shared_genes':inter,'jaccard':inter/union})
    pd.DataFrame(overlap).to_csv(out/'program_overlap.csv',index=False)
    folds=json.loads((out/'folds.json').read_text());rng=np.random.default_rng(protocol['seed'])
    panels=[];geneix=np.flatnonzero(common);matching=[]
    for fold in folds:
        pool=fold['training_pool'];tr=np.asarray(fold['train_indices']);te=fold['test_indices']
        assert len(tr)==len(te)==6 and not set(tr)&set(te)
        assert np.bincount(d['labels'][tr],minlength=2).tolist()==[3,3]
        mu=x[tr][:,common].mean(0);sd=x[tr][:,common].std(0)
        bins=np.digitize(mu,np.quantile(mu,[.2,.4,.6,.8]))*5+np.digitize(sd,np.quantile(sd,[.2,.4,.6,.8]))
        fullbins=np.full(len(common),-1,int);fullbins[geneix]=bins
        for program in programs:
            ix=np.asarray(program['indices']);targetbins=fullbins[ix];used_target=set(ix)
            panels.append({'training_pool':pool,'program':program['key'],'kind':'program','replicate':-1,'indices':ix.tolist()})
            for rep in range(20):
                picked=[]
                for binid in np.unique(targetbins):
                    n=int((targetbins==binid).sum())
                    available=np.asarray([v for v in geneix[bins==binid] if v not in used_target])
                    assert len(available)>=n, 'Exact matching unavailable; do not silently relax.'
                    picked.extend(rng.choice(available,n,replace=False).tolist())
                chosen=np.asarray(sorted(picked));assert len(chosen)==len(ix) and len(set(chosen))==len(ix)
                assert not set(chosen)&used_target
                assert np.array_equal(np.bincount(fullbins[chosen],minlength=25),np.bincount(targetbins,minlength=25))
                panels.append({'training_pool':pool,'program':program['key'],'kind':'matched_random','replicate':rep,'indices':chosen.tolist()})
                matching.append({'training_pool':pool,'program':program['key'],'replicate':rep,'n_genes':len(ix),'exact_joint_bin_match':True})
    dump(out/'panels.json',panels);pd.DataFrame(matching).to_csv(out/'matching_checks.csv',index=False)
    dump(out/'input_provenance.json',{'public_source':'https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE298393','sources':{str(p.relative_to(root)):sha(p) for p in [src/'attribution_inputs.npz',src/'attributions.npz',diag/'modules.json',gmt]},'copied_input_sha256':sha(out/'attribution_inputs.npz'),'panel_sha256':sha(out/'panels.json'),'script_sha256':sha(Path(__file__))})
    dump(out/'STATUS.json',{'state':'prepared','programs':6,'samples':12,'references':2,'matched_panels':240,'expected_perturbation_rows':6048})
    print('Prepared 6 programs, 12 samples, 2 references, exact matched panels; 6048 replacement passes.',flush=True)


def run(folder,checkpoint,official,config):
    import torch
    torch.set_num_threads(4);torch.manual_seed(20260914);torch.backends.cuda.matmul.allow_tf32=False
    assert not (folder/'COMPLETE').exists(), 'Completed run is immutable.'
    cfg=json.loads(config.read_text())
    spec=importlib.util.spec_from_file_location('bridge_official',official)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    model=mod.ExpressionPerformer(num_genes=15165,hidden_dim=cfg['hidden_dim'],n_heads=cfg['num_heads'],n_layers=cfg['num_layers'],ffn_dim=cfg['ffn_dim'],ree_base=cfg['ree_base'],mask_token_id=cfg['mask_token'],feature_type=cfg['feature_type'],compute_type=cfg['compute_type'],include_species_embedding=cfg['include_species_embedding'],num_species=2)
    ck=torch.load(checkpoint,map_location='cpu',weights_only=True);model.load_state_dict(ck['model_state_dict'],strict=True);del ck
    model.eval().cuda().requires_grad_(False)
    d=np.load(folder/'attribution_inputs.npz');x=np.nan_to_num(d['x'],nan=-10).astype(np.float32);common=d['common'].astype(bool)
    panels=json.loads((folder/'panels.json').read_text());folds=json.loads((folder/'folds.json').read_text())
    checks=pd.read_csv(folder/'integration_checks.csv');start=time.time();score_rows=[]
    output=folder/'perturbations.csv';written=0
    # Resume only complete sample-reference blocks, keyed by persisted output rows.
    previous=pd.read_csv(output) if output.exists() else pd.DataFrame()
    finished=set()
    if len(previous):
        for key,g in previous.groupby(['training_pool','id','reference']):
            if len(g)==252:finished.add(key)
            else:raise RuntimeError('Partial block found; preserve and inspect before resuming')
        written=len(previous)
    def scores(z,w,b):
        # Small fixed batches bound GPU memory; no gradients are needed for replacements.
        vals=[]
        with torch.inference_mode():
            for startix in range(0,len(z),4):
                t=torch.tensor(np.asarray(z[startix:startix+4]),device='cuda',dtype=torch.float32)
                h=model._encode_hidden(t)
                emb=torch.cat([h.mean(1),h.std(1,unbiased=False)],1)
                vals.extend((emb.double()@w+b).cpu().numpy().tolist())
        return np.asarray(vals)
    for fold in folds:
        pool=fold['training_pool'];w=torch.tensor(d[f'{pool}_weight'],device='cuda',dtype=torch.float64);b=torch.tensor(d[f'{pool}_bias'],device='cuda',dtype=torch.float64)
        ew=d[f'{pool}_expression_weight'];eb=float(d[f'{pool}_expression_bias']);refs=d[f'{pool}_references'];panelset=[p for p in panels if p['training_pool']==pool]
        for i in fold['test_indices']:
            sample=x[i];ident=str(d['ids'][i]);fx=float(scores([sample],w,b)[0]);ex=float(sample[common].astype(float)@ew+eb)
            expected=checks[(checks.training_pool==pool)&(checks.id==ident)].iloc[0].logit
            assert abs(fx-expected)<1e-5,(ident,fx,expected)
            for ri,ref in enumerate(refs):
                refname=fold['reference_names'][ri];fr=float(scores([ref],w,b)[0]);er=float(ref[common].astype(float)@ew+eb)
                score_rows.append({'training_pool':pool,'id':ident,'sample_index':i,'label':int(d['labels'][i]),'reference':refname,'bridge_logit':fx,'reference_logit':fr,'expression_logit':ex,'expression_reference_logit':er,'prior_logit_error':abs(fx-expected)})
                if (pool,ident,refname) in finished:continue
                pert=[];tags=[]
                for panel in panelset:
                    ix=np.asarray(panel['indices']);z=sample.copy();z[ix]=ref[ix]
                    for renorm in [False,True]:
                        q=z.copy()
                        if renorm:
                            mass=np.expm1(q[common].astype(float));q[common]=np.log1p(mass/mass.sum()*1e6)
                        pert.append(q)
                        tags.append({'training_pool':pool,'id':ident,'sample_index':i,'label':int(d['labels'][i]),'reference':refname,'program':panel['program'],'kind':panel['kind'],'replicate':panel['replicate'],'n_genes':len(ix),'renormalized':renorm,'expression_logit_change':ex-float(q[common].astype(float)@ew+eb)})
                values=scores(pert,w,b);assert np.isfinite(values).all()
                for row,val in zip(tags,values):
                    row.update({'bridge_logit_change':fx-float(val),'perturbed_logit':float(val),'original_logit':fx,'reference_logit':fr})
                pd.DataFrame(tags).to_csv(output,index=False,mode='a' if output.exists() else 'w',header=not output.exists())
                written+=len(tags)
                pd.DataFrame(score_rows).to_csv(folder/'score_checks.csv',index=False)
                dump(folder/'STATUS.json',{'state':'running','completed_perturbations':written,'expected_perturbations':6048,'elapsed_seconds':time.time()-start,'last_sample':ident,'reference':refname})
                print('RESPONSE',pool,ident,refname,written,'/ 6048','elapsed',round(time.time()-start,1),flush=True)
    pd.DataFrame(score_rows).to_csv(folder/'score_checks.csv',index=False)
    assert written==6048
    dump(folder/'execution_report.json',{'elapsed_seconds_this_invocation':time.time()-start,'device':torch.cuda.get_device_name(),'peak_memory_GB':torch.cuda.max_memory_allocated()/1e9,'perturbation_passes':written,'checkpoint_sha256':sha(checkpoint),'official_source_sha256':sha(official),'input_sha256':sha(folder/'attribution_inputs.npz'),'panels_sha256':sha(folder/'panels.json'),'script_sha256':sha(Path(__file__)),'encoder_updated':False,'heads_updated':False})
    dump(folder/'STATUS.json',{'state':'gpu_complete','completed_perturbations':written,'expected_perturbations':6048})
    (folder/'COMPLETE').write_text('complete\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['prepare','run']);p.add_argument('--root',type=Path);p.add_argument('--folder',type=Path,required=True);p.add_argument('--checkpoint',type=Path);p.add_argument('--official',type=Path);p.add_argument('--config',type=Path);a=p.parse_args()
    if a.phase=='prepare':prepare(a.root,a.folder)
    else:run(a.folder,a.checkpoint,a.official,a.config)
