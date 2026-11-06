"""Declared post-outcome training-source sensitivity; no model/threshold selection."""
from pathlib import Path
import json,itertools,argparse
import numpy as np,pandas as pd
from sklearn.metrics import roc_auc_score
from controlled_exposure_pilot import dump,sha
from evaluate_controlled_exposure import fit,metrics


def run(out,old,root):
    assert not (out/'training_source_sensitivity.csv').exists()
    dump(out/'stability_amendment.json',{'timing':'After inspecting prespecified run07 outcomes','reason':'Common-count BRIDGE IR/control head transferred to 2Gy IMR90; test sensitivity to each training source before interpreting this lead','scope':'Both processing routes and both features; remove each entire training file; fixed C1 and threshold0; evaluate all six outside-study strata; no selecting or tuning models','additional':'Single-test-sample deletion and exact fixed-score label permutation summaries are descriptive, unadjusted, tiny-N; examine unchanged flight heads on new irradiation profiles as out-of-domain diagnostics'})
    m=pd.read_csv(out/'manifest.csv').fillna('');d=np.load(out/'inputs.npz');o=np.load(out/'original_inputs.npz');e=np.load(out/'embeddings.npz');eo=np.load(old/'embeddings.npz');common=d['observed'].all(0);z=np.c_[e['mean'],e['std']].astype(float);zo=z.copy();oi=m.original_index.to_numpy(int);zo[oi>=0]=np.c_[eo['mean'],eo['std']][oi[oi>=0]]
    features={'ncbi':{'expression':d['x'][:,common].astype(float),'bridge':z},'original':{'expression':o['x'][:,common].astype(float),'bridge':zo}};train=np.flatnonzero(m.training_eligible);y=m.radiation_label.to_numpy(int);rows=[];pred=[]
    for route,ff in features.items():
      for feature,x in ff.items():
        for omitted in sorted(m.iloc[train].source_file.unique()):
            tr=train[m.iloc[train].source_file.to_numpy()!=omitted];model=fit(feature,x[tr],y[tr])
            for (study,group),g in m[m.study!='GSE230181'].groupby(['study','experiment_set']):
                te=g.index.to_numpy();assert not set(tr)&set(te);s=model.decision_function(x[te])
                rows.append({'route':route,'feature':feature,'omitted_source':omitted,'study':study,'group':group,'n_train':len(tr),**metrics(y[te],s)})
                pred.extend({'route':route,'feature':feature,'omitted_source':omitted,'id':m.iloc[i].id,'label':int(y[i]),'score':float(v)} for i,v in zip(te,s))
    pd.DataFrame(rows).to_csv(out/'training_source_sensitivity.csv',index=False);pd.DataFrame(pred).to_csv(out/'training_source_predictions.csv',index=False)
    original_preds=pd.read_csv(out/'predictions.csv');summary=[]
    for (model,context),g in original_preds[(original_preds['mode']=='absolute')&original_preds.evaluation.isin(['lung_development','new_2Gy_challenge'])].groupby(['model','context']):
        yy=g.label.to_numpy();s=g.score.to_numpy();obs=roc_auc_score(yy,s);aucs=[];bas=[]
        for k in range(len(g)):
            keep=np.arange(len(g))!=k;rr=metrics(yy[keep],s[keep]);aucs.append(rr['auroc']);bas.append(rr['balanced_accuracy'])
        null=[]
        for pos in itertools.combinations(range(len(g)),int(yy.sum())):
            py=np.zeros(len(g),int);py[list(pos)]=1;null.append(roc_auc_score(py,s))
        summary.append({'model':model,'context':context,'n':len(g),'auroc':obs,'leave_one_auroc_min':min(aucs),'leave_one_auroc_max':max(aucs),'leave_one_BA_min':min(bas),'leave_one_BA_max':max(bas),'exact_fixed_score_one_sided_permutation_p':float((np.array(null)>=obs-1e-12).mean()),'null_label_assignments':len(null),'multiplicity_adjusted':False})
    pd.DataFrame(summary).to_csv(out/'test_sample_sensitivity.csv',index=False)
    # This is the fixed original flight classifier, not the new irradiation head.
    a=np.load(root/'artifacts/space_head_attribution_2026-09-14/attribution_inputs.npz');flight=[]
    for pool in ['YA','OS']:
        s=z@a[f'{pool}_weight']+float(a[f'{pool}_bias'])
        for time,g in m[m.study=='GSE111437'].groupby('time'):
            ix=g.index.to_numpy();delta=s[ix][y[ix]==1].mean()-s[ix][y[ix]==0].mean()
            flight.append({'pool':pool,'time':time,'irradiated_minus_control_flight_logit':float(delta),'interpretation':'Out-of-domain diagnostic, not causal contribution or a validated flight test'})
    pd.DataFrame(flight).to_csv(out/'old_flight_head_new_irradiation.csv',index=False)
    print(pd.DataFrame(rows).groupby(['route','feature','study','group'])[['auroc','balanced_accuracy']].agg(['min','max']).to_string());print(pd.DataFrame(flight).to_string(index=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--folder',type=Path,required=True);p.add_argument('--old',type=Path,default=Path('fa26/workstreams/spaceflight/runs/06_controlled_exposure_validation_2026-09-14'));p.add_argument('--root',type=Path,default=Path('fa26'));a=p.parse_args();run(a.folder,a.old,a.root)
