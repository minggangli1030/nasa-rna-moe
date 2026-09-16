"""Bounded frozen-encoder head pilot. Protocol must exist before execution."""
from pathlib import Path
import json, hashlib, platform
import numpy as np
import pandas as pd
import sklearn
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, roc_auc_score, average_precision_score, confusion_matrix, brier_score_loss
import joblib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/space_head_pilot_2026-09-14'
MODEL_NAMES = ['expression_linear','pca5_linear','bridge_mean_linear','bridge_mean_std_linear','pool_metadata_linear']

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def load():
    frames, expressions, observed, means, stds, files = [], [], [], [], [], []
    genes = None
    for folder, study in [('general_survey_2026-09-12','GSE234465'), ('muscle_repeat_flight_2026-09-12','GSE298393')]:
        p = ROOT/'artifacts'/folder
        m = pd.read_csv(p/'manifest.csv').fillna('')
        x, e = np.load(p/'inputs.npz'), np.load(p/'embeddings.npz')
        assert m.id.tolist() == x['ids'].tolist() == e['ids'].tolist()
        assert sha(p/'inputs.npz') == json.loads((p/'inference_report.json').read_text())['input_sha256']
        if genes is None: genes = x['genes']
        else: assert np.array_equal(genes, x['genes'])
        ix = np.flatnonzero(m.study.eq(study))
        frames.append(m.iloc[ix].copy());expressions.append(x['x'][ix]);observed.append(x['observed'][ix]);means.append(e['mean'][ix]);stds.append(e['std'][ix])
        files.extend(p/name for name in ['manifest.csv','inputs.npz','embeddings.npz','inference_report.json'])
    m = pd.concat(frames, ignore_index=True).fillna('')
    m['label'] = m.condition.astype(int)
    assert len(m)==24 and m.id.is_unique and set(m.label)=={0,1}
    counts = m.groupby(['study','stratum','label']).size()
    assert len(counts)==8 and counts.eq(3).all()
    common = np.concatenate(observed).astype(bool).all(0)
    X = np.concatenate(expressions)[:,common].astype(float)
    mean,std = np.concatenate(means).astype(float),np.concatenate(stds).astype(float)
    features = {'expression_linear':X,'pca5_linear':X,'bridge_mean_linear':mean,'bridge_mean_std_linear':np.concatenate([mean,std],axis=1),'pool_metadata_linear':m.stratum.eq('OS').to_numpy(float)[:,None]}
    assert all(np.isfinite(a).all() for a in features.values())
    return m, features, genes[common], files

def estimator(name, c):
    steps=[('scale',StandardScaler())]
    if name=='pca5_linear': steps.append(('pca',PCA(n_components=5,svd_solver='full')))
    steps.append(('head',LogisticRegression(C=c,solver='liblinear',max_iter=2000,random_state=17)))
    return Pipeline(steps)

def metrics(y,p):
    pred=(p>=.5).astype(int);tn,fp,fn,tp=confusion_matrix(y,pred,labels=[0,1]).ravel()
    return {'balanced_accuracy':balanced_accuracy_score(y,pred),'auroc':roc_auc_score(y,p),'average_precision':average_precision_score(y,p),'uncalibrated_brier':brier_score_loss(y,p),'TP':int(tp),'TN':int(tn),'FP':int(fp),'FN':int(fn)}

def run():
    assert (OUT/'protocol.json').exists()
    assert not (OUT/'metrics.csv').exists(), 'Use a new output directory or explicitly review before replacing a completed run.'
    m,features,genes,files=load();y=m.label.to_numpy()
    m.to_csv(OUT/'cohort.csv',index=False)
    pd.DataFrame({'gene':genes}).to_csv(OUT/'expression_gene_panel.csv',index=False)
    folds=[]
    for study in m.study.unique():
        folds.append(('cross_flight',study+'__to__'+next(s for s in m.study.unique() if s!=study),np.flatnonzero(m.study.eq(study)),np.flatnonzero(~m.study.eq(study))))
        for pool in ['YA','OS']:
            folds.append(('within_flight_pool',study+'__'+pool+'__to__'+('OS' if pool=='YA' else 'YA'),np.flatnonzero(m.study.eq(study)&m.stratum.eq(pool)),np.flatnonzero(m.study.eq(study)&~m.stratum.eq(pool))))
    splitrows=[];results=[];predictions=[];sensitivity=[];coeffs=[]
    (OUT/'heads').mkdir(exist_ok=True)
    for kind,fold,tr,te in folds:
        assert not set(tr)&set(te)
        if kind=='cross_flight': assert set(m.iloc[tr].study).isdisjoint(set(m.iloc[te].study))
        else: assert set(m.iloc[tr].stratum).isdisjoint(set(m.iloc[te].stratum))
        for role,idx in [('train',tr),('test',te)]:
            splitrows.extend({'evaluation':kind,'fold':fold,'role':role,'id':m.iloc[i].id} for i in idx)
        for name,X in features.items():
            for c in ([1,.01,100] if kind=='cross_flight' else [1]):
                model=estimator(name,c).fit(X[tr],y[tr]);p=model.predict_proba(X[te])[:,1]
                assert int(model.named_steps['head'].n_iter_[0])<2000
                # Independently verify preprocessing was fit only to training rows.
                assert np.allclose(model.named_steps['scale'].mean_,X[tr].mean(0))
                tag={'evaluation':kind,'fold':fold,'model':name,'C':c,'n_train':len(tr),'n_test':len(te)}
                results.append({**tag,**metrics(y[te],p)})
                predictions.extend({**tag,'id':m.iloc[i].id,'true_label':int(y[i]),'score':float(v),'predicted_label':int(v>=.5)} for i,v in zip(te,p))
                if c==1:
                    joblib.dump(model,OUT/'heads'/f'{fold}__{name}.joblib')
                    if kind=='cross_flight' and name=='expression_linear':
                        b=model.named_steps['head'].coef_[0]
                        for j in np.argsort(-np.abs(b))[:50]:coeffs.append({'fold':fold,'gene':genes[j],'standardized_coefficient':float(b[j]),'interpretation':'training association; not BridgeRNA attribution or causal effect'})
                    if kind=='cross_flight':
                        for omit in tr:
                            reduced=tr[tr!=omit];fit=estimator(name,1).fit(X[reduced],y[reduced]);q=fit.predict_proba(X[te])[:,1]
                            sensitivity.append({**tag,'omitted_train_id':m.iloc[omit].id,**metrics(y[te],q),'prediction_agreement_with_full':float(np.mean((q>=.5)==(p>=.5)))})
            print(kind,fold,name,flush=True)
    pd.DataFrame(splitrows).to_csv(OUT/'splits.csv',index=False)
    r=pd.DataFrame(results);r.to_csv(OUT/'metrics.csv',index=False)
    pd.DataFrame(predictions).to_csv(OUT/'predictions.csv',index=False)
    pd.DataFrame(sensitivity).to_csv(OUT/'training_chip_deletion.csv',index=False)
    pd.DataFrame(coeffs).to_csv(OUT/'expression_coefficients_exploratory.csv',index=False)
    primary=r[(r.evaluation=='cross_flight')&(r.C==1)]
    secondary=r[(r.evaluation=='within_flight_pool')&(r.C==1)]
    fig,axes=plt.subplots(1,2,figsize=(13,5),constrained_layout=True)
    labels={'expression_linear':'Expression','pca5_linear':'PCA (5)','bridge_mean_linear':'Bridge mean','bridge_mean_std_linear':'Bridge mean + SD','pool_metadata_linear':'Pool metadata'}
    colors=['#147d92','#db8b47','#7051a0','#d16971','#888888']
    for ax,data,title in [(axes[0],primary,'Train one flight → test the other'),(axes[1],secondary,'Within a flight: train one pool → test the other')]:
        for j,name in enumerate(MODEL_NAMES):
            values=data[data.model==name].balanced_accuracy.to_numpy();offset=np.linspace(-.12,.12,len(values));ax.scatter(j+offset,values,color=colors[j],s=70,zorder=3);ax.plot([j-.2,j+.2],[values.mean()]*2,color=colors[j],lw=2)
        ax.axhline(.5,color='#555',linestyle='--',lw=1);ax.set_ylim(-.05,1.05);ax.set_xticks(range(5),[labels[x] for x in MODEL_NAMES],rotation=25,ha='right');ax.set_ylabel('Balanced accuracy, threshold 0.5');ax.set_title(title,fontsize=11);ax.grid(axis='y',alpha=.2)
    fig.suptitle('Human muscle-chip prediction pilot — 24 profiles, two flights, shared donor pools\nDots are evaluation folds; bars are their descriptive mean, not independent-replicate confidence intervals',fontsize=11)
    fig.savefig(OUT/'pilot_results.png',dpi=180);fig.savefig(OUT/'pilot_results.pdf');plt.close(fig)
    provenance={'python':platform.python_version(),'numpy':np.__version__,'sklearn':sklearn.__version__,'execution':'Local CPU; cached frozen embeddings; no GPU or encoder update','sha256':{str(p.relative_to(ROOT)):sha(p) for p in files+[Path(__file__),OUT/'protocol.json']},'checks':['24 unique IDs and balanced study/pool/label cells','Aligned input/embedding/manifest IDs and input hashes','Gene order, observed mask and finite features','Study/pool separation appropriate to evaluation','Training-only scaler means','All heads converged']}
    (OUT/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    print(primary[['fold','model','balanced_accuracy','auroc','TP','TN','FP','FN']].to_string(index=False))

if __name__=='__main__':run()
