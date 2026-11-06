"""Exhaustive target-pool label-count sensitivity; no target-test model selection."""
from pathlib import Path
import itertools,json,hashlib
import numpy as np,pandas as pd,joblib
from sklearn.metrics import roc_auc_score,balanced_accuracy_score
from evaluate_space_head_diagnostics import fit_predict,OUT,ROOT
import space_head_pilot as pilot

def run():
    m,_,_,_=pilot.load();d=np.load(OUT/'inputs.npz');e=np.load(OUT/'readouts.npz');y=m.label.to_numpy();rows=[];preds=[];(OUT/'adapted_heads').mkdir(exist_ok=True)
    for name,x in [('expression',d['harmonized'][:,d['common']].astype(float)),('bridge',e['harmonized_L12_meanstd'].astype(float))]:
        for target in m.study.unique():
            for pool in ['YA','OS']:
                tr=np.flatnonzero(m.study.eq(target)&m.stratum.eq(pool));te=np.flatnonzero(m.study.eq(target)&~m.stratum.eq(pool))
                assert set(m.iloc[tr].stratum).isdisjoint(set(m.iloc[te].stratum))
                for n in [1,2,3]:
                    for a,b in itertools.product(itertools.combinations(tr[y[tr]==0],n),itertools.combinations(tr[y[tr]==1],n)):
                        use=np.array(a+b);score,state=fit_predict(x,y,use,te);tag={'model':name,'target_study':target,'training_pool':pool,'labeled_chips':2*n,'training_ids':'|'.join(m.iloc[use].id),'n_test':6}
                        rows.append({**tag,'auroc':roc_auc_score(y[te],score),'balanced_accuracy':balanced_accuracy_score(y[te],score>=0)})
                        if n==3:
                            model,mu,scale=state;artifact={'head':model,'training_mean':mu,'training_scale':scale,'training_ids':m.iloc[use].id.tolist(),'held_out_ids':m.iloc[te].id.tolist(),'species':'human','context':target,'training_pool':pool,'feature_kind':'common_gene_log1pTPM' if name=='expression' else 'harmonized_L12_meanstd','calibration':'none; return logits/scores, not calibrated exposure probabilities','scope':'exploratory within-experiment; unsupported outside this context','input_sha256':hashlib.sha256((OUT/'inputs.npz').read_bytes()).hexdigest()}
                            joblib.dump(artifact,OUT/'adapted_heads'/f'{name}_{target}_{pool}.joblib')
                            check=model.decision_function((x[te]-mu)/scale);np.testing.assert_allclose(check,score)
                            preds.extend({**tag,'id':m.iloc[i].id,'label':int(y[i]),'logit':float(s)} for i,s in zip(te,score))
    r=pd.DataFrame(rows);r.to_csv(OUT/'target_label_learning_curve.csv',index=False);pd.DataFrame(preds).to_csv(OUT/'adapted_head_predictions.csv',index=False)
    print(r.groupby(['model','labeled_chips'])[['auroc','balanced_accuracy']].agg(['min','median','max']).to_string())
if __name__=='__main__':run()
