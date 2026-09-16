"""Integrated gradients for the fixed repeat-flight heads, with numerical and perturbation checks."""
from pathlib import Path
import json,hashlib,argparse,importlib.util,time
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'artifacts/space_head_attribution_2026-09-14';DIAG=ROOT/'artifacts/space_head_diagnostics_2026-09-14'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,indent=2)+'\n')

def prepare():
 import joblib
 m=pd.read_csv(DIAG/'cohort.csv');d=np.load(DIAG/'inputs.npz');assert m.id.tolist()==d['ids'].tolist();keep=np.flatnonzero(m.study.eq('GSE298393'));meta=m.iloc[keep].reset_index(drop=True);x=d['harmonized'][keep];common=d['common'];y=meta.label.to_numpy();arrays={'x':x,'ids':d['ids'][keep],'genes':d['genes'],'common':common,'labels':y};folds=[]
 for pool in ['YA','OS']:
  st=joblib.load(DIAG/'adapted_heads'/f'bridge_GSE298393_{pool}.joblib');ex=joblib.load(DIAG/'adapted_heads'/f'expression_GSE298393_{pool}.joblib');tr=np.flatnonzero(meta.id.isin(st['training_ids']));te=np.flatnonzero(meta.id.isin(st['held_out_ids']));assert len(tr)==len(te)==6 and not set(tr)&set(te)
  # Preserve the fitted double-precision sklearn transform/head.
  arrays[f'{pool}_weight']=st['head'].coef_[0]/st['training_scale'];arrays[f'{pool}_bias']=np.asarray(st['head'].intercept_[0]-(st['head'].coef_[0]*st['training_mean']/st['training_scale']).sum())
  arrays[f'{pool}_expression_weight']=ex['head'].coef_[0]/ex['training_scale'];arrays[f'{pool}_expression_bias']=np.asarray(ex['head'].intercept_[0]-(ex['head'].coef_[0]*ex['training_mean']/ex['training_scale']).sum())
  refs=[]
  for group in [tr[y[tr]==0],tr]:
   ref=np.full(x.shape[1],-10.,np.float32);ref[common]=np.log1p(np.expm1(x[group][:,common].astype(float)).mean(0));refs.append(ref)
  arrays[f'{pool}_references']=np.array(refs);folds.append({'training_pool':pool,'train_indices':tr.tolist(),'test_indices':te.tolist(),'reference_names':['training_ground_mean_TPM','training_all_mean_TPM'],'training_ids':meta.iloc[tr].id.tolist(),'test_ids':meta.iloc[te].id.tolist()})
 np.savez_compressed(OUT/'attribution_inputs.npz',**arrays);meta.to_csv(OUT/'cohort.csv',index=False);dump(OUT/'folds.json',folds)
 dump(OUT/'provenance_inputs.json',{'source_input_sha256':sha(DIAG/'inputs.npz'),'attribution_input_sha256':sha(OUT/'attribution_inputs.npz'),'source':'Public GEO GSE298393; same expression inputs already present on the user VM','heads':{p.name:sha(p) for p in (DIAG/'adapted_heads').glob('*GSE298393*.joblib')}})
 print('Prepared 12 repeat-flight chips, two reciprocal pool heads, two training-only references each.')

def run(folder,checkpoint,official,config):
 import torch
 torch.set_num_threads(4);torch.manual_seed(1701);torch.backends.cuda.matmul.allow_tf32=False
 cfg=json.loads(config.read_text());spec=importlib.util.spec_from_file_location('bridge_official',official);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 model=mod.ExpressionPerformer(num_genes=15165,hidden_dim=cfg['hidden_dim'],n_heads=cfg['num_heads'],n_layers=cfg['num_layers'],ffn_dim=cfg['ffn_dim'],ree_base=cfg['ree_base'],mask_token_id=cfg['mask_token'],feature_type=cfg['feature_type'],compute_type=cfg['compute_type'],include_species_embedding=cfg['include_species_embedding'],num_species=2)
 ck=torch.load(checkpoint,map_location='cpu',weights_only=True);model.load_state_dict(ck['model_state_dict'],strict=True);del ck;model.eval().cuda();model.requires_grad_(False)
 d=np.load(folder/'attribution_inputs.npz');x=np.nan_to_num(d['x'],nan=-10).astype(np.float32);common=d['common'];folds=json.loads((folder/'folds.json').read_text());rows=[];values=[];checks=[];perturb=[];finite=[];start=time.time();rng=np.random.default_rng(1701)
 def score(z,w,b):
  h=model._encode_hidden(z);emb=torch.cat([h.mean(1),h.std(1,unbiased=False)],1);return emb.double()@w+b
 def evalscore(z,w,b):
  with torch.no_grad():return float(score(torch.tensor(z[None],device='cuda',dtype=torch.float32),w,b).item())
 def ig(sample,ref,w,b,steps):
  nodes,weights=np.polynomial.legendre.leggauss(steps);delta=sample-ref;total=np.zeros(len(sample),np.float64)
  for alpha,weight in zip((nodes+1)/2,weights/2):
   point=torch.tensor((ref+alpha*delta)[None],device='cuda',dtype=torch.float32,requires_grad=True);s=score(point,w,b);g=torch.autograd.grad(s,point)[0].detach().cpu().numpy()[0];assert np.isfinite(g).all();total+=weight*g
  return delta*total
 for fold in folds:
  pool=fold['training_pool'];w=torch.tensor(d[f'{pool}_weight'],device='cuda',dtype=torch.float64);b=torch.tensor(d[f'{pool}_bias'],device='cuda',dtype=torch.float64);refnames=fold['reference_names'];refarray=d[f'{pool}_references'];tr=np.array(fold['train_indices'])
  # Random controls matched on training expression mean and SD quintile bins.
  means=x[tr][:,common].mean(0);sds=x[tr][:,common].std(0);geneix=np.flatnonzero(common);cuts0=np.quantile(means,[.2,.4,.6,.8]);cuts1=np.quantile(sds,[.2,.4,.6,.8]);bins=np.digitize(means,cuts0)*5+np.digitize(sds,cuts1);lookup={int(j):int(k) for j,k in zip(geneix,bins)}
  for i in fold['test_indices']:
   sample=x[i];fx=evalscore(sample,w,b)
   for ri,ref in enumerate(refarray):
    fref=evalscore(ref,w,b);prev=ig(sample,ref,w,b,8);chosen=None
    for steps in [16,32,64]:
     current=ig(sample,ref,w,b,steps);change=float(np.abs(current-prev).sum()/max(np.abs(current).sum(),1e-10));residual=float(current.sum()-(fx-fref));passed=abs(residual)<=max(.005,.02*abs(fx-fref)) and change<=.05
     if passed:chosen=current;break
     prev=current
    if chosen is None:chosen=current
    assert np.all(chosen[~common]==0)
    tag={'training_pool':pool,'id':str(d['ids'][i]),'sample_index':i,'label':int(d['labels'][i]),'reference':refnames[ri]};rows.append(tag);values.append(chosen)
    checks.append({**tag,'logit':fx,'reference_logit':fref,'logit_difference':fx-fref,'attribution_sum':float(chosen.sum()),'completeness_residual':residual,'relative_L1_change':change,'quadrature_steps':steps,'passed':passed})
    if ri==0:
     # Check input gradients against central finite differences for 3 influential genes.
     if i==fold['test_indices'][0]:
      point=torch.tensor(sample[None],device='cuda',requires_grad=True);grad=torch.autograd.grad(score(point,w,b),point)[0].detach().cpu().numpy()[0]
      for j in geneix[np.argsort(-np.abs(grad[common]))[:3]]:
       plus=sample.copy();minus=sample.copy();plus[j]+=.002;minus[j]-=.002;fd=(evalscore(plus,w,b)-evalscore(minus,w,b))/.004;finite.append({'training_pool':pool,'id':str(d['ids'][i]),'gene':str(d['genes'][j]),'autograd':float(grad[j]),'finite_difference':fd,'relative_error':abs(fd-grad[j])/max(abs(fd),abs(grad[j]),1e-8)})
     # Faithfulness check on top absolute contributions; compare signed gap movement.
     targetsign=1 if fx-fref>=0 else -1
     for k in [25,100]:
      top=geneix[np.argsort(-np.abs(chosen[common]))[:k]];panels=[('top',-1,top)]
      for rep in range(20):
       used=set(top.tolist());selected=[]
       for j in top:
        candidates=[v for v in geneix[bins==lookup[int(j)]] if int(v) not in used]
        if not candidates:candidates=[v for v in geneix if int(v) not in used]
        pick=int(rng.choice(candidates));used.add(pick);selected.append(pick)
       panels.append(('matched_random',rep,np.array(selected)))
      for kind,rep,ix in panels:
       pert=sample.copy();pert[ix]=ref[ix];s=evalscore(pert,w,b)
       perturb.append({**tag,'k':k,'panel':kind,'replicate':rep,'signed_score_movement_toward_reference':targetsign*(fx-s),'absolute_logit_change':abs(fx-s),'predicted_IG_change':float(chosen[ix].sum()),'observed_logit_change':fx-s,'renormalized':False})
       if kind=='top':
        mass=np.expm1(pert[common].astype(float));pert[common]=np.log1p(mass/mass.sum()*1e6);s=evalscore(pert,w,b);perturb.append({**tag,'k':k,'panel':kind,'replicate':rep,'signed_score_movement_toward_reference':targetsign*(fx-s),'absolute_logit_change':abs(fx-s),'predicted_IG_change':float(chosen[ix].sum()),'observed_logit_change':fx-s,'renormalized':True})
    # Save progress after each path, allowing inspection without a rerun.
    pd.DataFrame(checks).to_csv(folder/'integration_checks.csv',index=False);pd.DataFrame(perturb).to_csv(folder/'perturbation_checks.csv',index=False);pd.DataFrame(finite).to_csv(folder/'finite_difference_checks.csv',index=False);pd.DataFrame(rows).to_csv(folder/'attribution_rows.csv',index=False);np.savez_compressed(folder/'attributions.npz',attributions=np.array(values),genes=d['genes'])
    print('ATTR',pool,d['ids'][i],refnames[ri],'steps',steps,'passed',passed,'residual',round(residual,6),'elapsed',round(time.time()-start,1),flush=True)
 dump(folder/'execution_report.json',{'elapsed_seconds':time.time()-start,'device':torch.cuda.get_device_name(),'peak_memory_GB':torch.cuda.max_memory_allocated()/1e9,'checkpoint_sha256':sha(checkpoint),'official_source_sha256':sha(official),'input_sha256':sha(folder/'attribution_inputs.npz'),'script_sha256':sha(Path(__file__)),'paths':len(rows),'all_integration_checks_passed':all(v['passed'] for v in checks),'encoder_updated':False,'head_updated':False})
 (folder/'ATTRIBUTION_COMPLETE').write_text('complete\n')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['prepare','run']);p.add_argument('--folder',type=Path);p.add_argument('--checkpoint',type=Path);p.add_argument('--official',type=Path);p.add_argument('--config',type=Path);a=p.parse_args()
 if a.phase=='prepare':prepare()
 else:run(a.folder,a.checkpoint,a.official,a.config)
