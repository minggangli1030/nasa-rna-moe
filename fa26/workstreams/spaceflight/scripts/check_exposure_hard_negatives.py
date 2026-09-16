"""One explicitly adaptive comparison: add known non-radiation stresses as negatives."""
from pathlib import Path
import argparse,json
import numpy as np,pandas as pd,joblib
from evaluate_controlled_exposure import fit,metrics,dump


def run(out):
    assert not (out/'hard_negative_metrics.csv').exists()
    dump(out/'hard_negative_amendment.json',{'timing':'Written after inspecting the original pilot; exploratory adaptation, not pristine validation','reason':'IR-vs-control probe ranks IR above other stresses but makes positive calls on bleomycin/rotenone/Ras at its original threshold','change':'Add normal-IMR90 known non-IR treatments and vehicle as negative training labels; exclude hTERT/Ras; retain entire-file holdouts and external study','fixed':'Same C=1, no threshold tuning or hyperparameter search','models':['expression_linear','bridge_meanstd_linear'],'limitations':'The same evaluation datasets informed this adaptation; independent confirmation is still required'})
    m=pd.read_csv(out/'manifest.csv').fillna('');d=np.load(out/'inputs.npz');e=np.load(out/'embeddings.npz');common=d['observed'].all(0);features={'expression_linear':d['x'][:,common].astype(float),'bridge_meanstd_linear':np.concatenate([e['mean'],e['std']],axis=1).astype(float)}
    # Only verified normal IMR90 samples; all non-IR groups here have known non-IR treatments.
    train=np.flatnonzero((m.study=='GSE230181')&(m.cell_type=='IMR90')&(m.group=='normal'));assert len(train)==61
    y=m.radiation_label.to_numpy(int);rows=[];preds=[];specific=[];split=[]
    for name,x in features.items():
        allfit=fit(name,x[train],y[train]);joblib.dump(allfit,out/'heads'/f'{name}__hard_negatives.joblib')
        for source in sorted(m.iloc[train].source_file.unique()):
            tr=train[m.iloc[train].source_file.to_numpy()!=source];te=train[m.iloc[train].source_file.to_numpy()==source];model=fit(name,x[tr],y[tr]);s=model.decision_function(x[te]);assert not set(m.iloc[tr].source_file)&set(m.iloc[te].source_file)
            rows.append({'model':name,'evaluation':'held_out_file_with_other_stresses','fold':source,'n_train':len(tr),**metrics(y[te],s)})
            for i,score in zip(te,s):preds.append({'model':name,'evaluation':'held_out_file_with_other_stresses','fold':source,'id':m.iloc[i].id,'condition':m.iloc[i].condition,'label':int(y[i]),'score_logit':float(score),'positive':bool(score>=0)})
            for role,idx in [('train',tr),('test',te)]:split.extend({'model':name,'fold':source,'role':role,'id':m.iloc[i].id} for i in idx)
            for condition,g in m.iloc[te].groupby('condition'):
                ss=model.decision_function(x[g.index]);specific.append({'model':name,'source':source,'condition':condition,'n':len(g),'positive_fraction':float((ss>=0).mean())})
        for group,g in m[m.study=='GSE242706'].groupby('experiment_set'):
            te=g.index.to_numpy();s=allfit.decision_function(x[te]);rows.append({'model':name,'evaluation':'external_lung_chip','fold':group,'n_train':len(train),**metrics(y[te],s)})
            for i,score in zip(te,s):preds.append({'model':name,'evaluation':'external_lung_chip','fold':group,'id':m.iloc[i].id,'condition':m.iloc[i].condition,'label':int(y[i]),'score_logit':float(score),'positive':bool(score>=0)})
    for file,data in [('hard_negative_metrics.csv',rows),('hard_negative_predictions.csv',preds),('hard_negative_specificity.csv',specific),('hard_negative_splits.csv',split)]:pd.DataFrame(data).to_csv(out/file,index=False)
    print(pd.DataFrame(rows).to_string(index=False));print(pd.DataFrame(specific).to_string(index=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--folder',type=Path,required=True);a=p.parse_args();run(a.folder)
