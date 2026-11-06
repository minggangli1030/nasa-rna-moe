"""Evaluate diagnostic remedies under fixed source-to-target directions."""
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd,joblib
from scipy.stats import rankdata
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler,normalize
from sklearn.metrics import roc_auc_score,balanced_accuracy_score
import space_head_pilot as pilot
ROOT=next((p for p in Path(__file__).resolve().parents if (p/'bridge-rna-latest').is_dir()), Path(__file__).resolve().parent);OUT=ROOT/'artifacts/space_head_diagnostics_2026-09-14'

def fit_predict(x,y,tr,te,mode='standard',center=False):
    if mode=='unit':x=normalize(x);mode='none'
    if mode=='rank':x=rankdata(x,axis=1)/x.shape[1];mode='standard'
    mu=x[tr].mean(0);sd=x[tr].std(0)
    if mode=='standard':scale=np.where(sd>0,sd,1.)
    elif mode=='floor':scale=np.maximum(sd,np.median(sd[sd>0]))
    elif mode=='none':scale=np.ones(x.shape[1])
    z=(x-mu)/scale
    if center:z[te]-=z[te].mean(0)
    model=LogisticRegression(C=1,solver='liblinear',max_iter=2000,random_state=17).fit(z[tr],y[tr])
    assert model.n_iter_[0]<2000
    return model.decision_function(z[te]),(model,mu,scale)

def run():
    m,old,_,_=pilot.load();d=np.load(OUT/'inputs.npz');e=np.load(OUT/'readouts.npz');assert m.id.tolist()==d['ids'].tolist()==e['ids'].tolist();common=d['common'];genes=d['genes'];y=m.label.to_numpy()
    original=old['bridge_mean_std_linear'];recomputed=e['original_L12_meanstd'];maxdiff=float(np.max(np.abs(original-recomputed)));assert np.allclose(original,recomputed,atol=2e-5,rtol=2e-5),maxdiff
    mods=json.loads((OUT/'modules.json').read_text());harm=d['harmonized'].astype(float)
    pmeans=np.stack([harm[:,v['indices']].mean(1) for v in mods],axis=1)
    variants=[('original_expression',old['expression_linear'],'standard',False),('original_bridge',original,'standard',False),('original_bridge_target_center',original,'standard',True),('original_expression_target_center',old['expression_linear'],'standard',True),('FPKM_expression',harm[:,common],'standard',False),('FPKM_expression_no_scale',harm[:,common],'none',False),('FPKM_expression_SD_floor',harm[:,common],'floor',False),('FPKM_expression_sample_rank',harm[:,common],'rank',False),('FPKM_Hallmark50_expression',pmeans,'standard',False)]
    for layer in [1,6,11,12]:variants.append((f'FPKM_bridge_L{layer}',e[f'harmonized_L{layer}_meanstd'].astype(float),'standard',False))
    variants.extend([('FPKM_bridge_L12_SD_floor',e['harmonized_L12_meanstd'].astype(float),'floor',False),('FPKM_bridge_L12_unit',e['harmonized_L12_meanstd'].astype(float),'unit',False),('FPKM_bridge_Hallmark50',e['harmonized_modules_meanstd'].astype(float),'standard',False)])
    results=[];preds=[];decomp=[];ood=[];directions=[]
    for study in m.study.unique():
        tr=np.flatnonzero(m.study.eq(study));te=np.flatnonzero(~m.study.eq(study));fold=study+'__to__'+m.iloc[te[0]].study
        for name,x,mode,center in variants:
            score,state=fit_predict(x,y,tr,te,mode,center);model,mu,scale=state
            tag={'fold':fold,'variant':name,'evaluation':'unlabeled_target_center_diagnostic' if center else 'source_only_diagnostic','n_features':x.shape[1]}
            results.append({**tag,'auroc':roc_auc_score(y[te],score),'balanced_accuracy':balanced_accuracy_score(y[te],score>=0)})
            preds.extend({**tag,'id':m.iloc[i].id,'label':int(y[i]),'logit':float(s)} for i,s in zip(te,score))
            if name in ['original_expression','original_bridge','FPKM_expression','FPKM_bridge_L12']:
                z=(x-mu)/scale;w=model.coef_[0];delta=z[te].mean(0)-z[tr].mean(0);effect_train=z[tr[y[tr]==1]].mean(0)-z[tr[y[tr]==0]].mean(0);effect_test=z[te[y[te]==1]].mean(0)-z[te[y[te]==0]].mean(0)
                decomp.append({'fold':fold,'variant':name,'train_logit_mean':float(model.decision_function(z[tr]).mean()),'test_logit_mean':float(score.mean()),'logit_shift_from_study_offset':float(w@delta),'train_flight_ground_logit_gap':float(w@effect_train),'test_flight_ground_logit_gap':float(w@effect_test),'response_cosine_train_scaled':float(effect_train@effect_test/(np.linalg.norm(effect_train)*np.linalg.norm(effect_test)))})
                for i in te:ood.append({'fold':fold,'variant':name,'id':m.iloc[i].id,'fraction_features_beyond_train_range':float(np.mean((x[i]<x[tr].min(0))|(x[i]>x[tr].max(0)))),'median_abs_train_z':float(np.median(np.abs(z[i]))),'max_abs_train_z':float(np.max(np.abs(z[i])))})
        for pool in ['YA','OS']:
            a=tr[m.iloc[tr].stratum.to_numpy()==pool];b=te[m.iloc[te].stratum.to_numpy()==pool]
            for name,x in [('original_expression',old['expression_linear']),('FPKM_expression',harm[:,common]),('original_bridge',original),('FPKM_bridge_L12',e['harmonized_L12_meanstd'])]:
                da=x[a[y[a]==1]].mean(0)-x[a[y[a]==0]].mean(0);db=x[b[y[b]==1]].mean(0)-x[b[y[b]==0]].mean(0);directions.append({'fold':fold,'pool':pool,'variant':name,'response_cosine':float(da@db/(np.linalg.norm(da)*np.linalg.norm(db)))})
    pd.DataFrame(results).to_csv(OUT/'remedy_metrics.csv',index=False);pd.DataFrame(preds).to_csv(OUT/'remedy_predictions.csv',index=False);pd.DataFrame(decomp).to_csv(OUT/'logit_decomposition.csv',index=False);pd.DataFrame(ood).to_csv(OUT/'out_of_domain_features.csv',index=False);pd.DataFrame(directions).to_csv(OUT/'response_directions.csv',index=False)
    # Separately labeled supervised scenarios: source-only, target-pool-only,
    # or direct pooling of source and target training rows. Other target pool is held out.
    adaptation=[];adaptpred=[]
    for name,x in [('expression',harm[:,common]),('bridge',e['harmonized_L12_meanstd'].astype(float))]:
        for target in m.study.unique():
            source=np.flatnonzero(~m.study.eq(target));targetidx=np.flatnonzero(m.study.eq(target))
            for pool in ['YA','OS']:
                train=targetidx[m.iloc[targetidx].stratum.to_numpy()==pool];test=targetidx[m.iloc[targetidx].stratum.to_numpy()!=pool]
                for approach in ['source_only','target_pool_only','source_plus_target_pool']:
                    use=source if approach=='source_only' else train if approach=='target_pool_only' else np.r_[source,train]
                    # Study-centered training with separate intercept effects requires known
                    # target reference; use direct pooled fit here so the baseline is explicit.
                    score,_=fit_predict(x,y,use,test)
                    tag={'variant':name,'target_study':target,'training_target_pool':pool,'approach':approach,'n_target_labeled':0 if approach=='source_only' else len(train),'n_test':len(test),'auroc':roc_auc_score(y[test],score),'balanced_accuracy':balanced_accuracy_score(y[test],score>=0)}
                    adaptation.append(tag);adaptpred.extend({**tag,'id':m.iloc[i].id,'label':int(y[i]),'logit':float(s)} for i,s in zip(test,score))
    pd.DataFrame(adaptation).to_csv(OUT/'supervised_adaptation_metrics.csv',index=False);pd.DataFrame(adaptpred).to_csv(OUT/'supervised_adaptation_predictions.csv',index=False)
    # Decompose expression score-gap into gene contributions, all genes retained.
    geneout=[]
    for study in m.study.unique():
        tr=np.flatnonzero(m.study.eq(study));te=np.flatnonzero(~m.study.eq(study));x=harm[:,common];score,(fit,mu,scale)=fit_predict(x,y,tr,te)
        w=fit.coef_[0];a=(x[tr[y[tr]==1]].mean(0)-x[tr[y[tr]==0]].mean(0))/scale;b=(x[te[y[te]==1]].mean(0)-x[te[y[te]==0]].mean(0))/scale
        for j,g in enumerate(genes[common]):geneout.append({'training_study':study,'gene':g,'train_weight_times_effect':float(w[j]*a[j]),'test_weight_times_effect':float(w[j]*b[j]),'train_effect_log1pTPM':float(a[j]*scale[j]),'test_effect_log1pTPM':float(b[j]*scale[j])})
    pd.DataFrame(geneout).to_csv(OUT/'expression_reversal_gene_contributions.csv',index=False)
    (OUT/'reproduction_check.json').write_text(json.dumps({'original_embedding_max_absolute_difference':maxdiff,'original_embeddings_reproduced':True,'label_audit_all_match':bool(pd.read_csv(OUT/'label_source_audit.csv').matches.all())},indent=2)+'\n')
    print(pd.DataFrame(results).pivot(index='variant',columns='fold',values='auroc').to_string());print('\nADAPTATION');print(pd.DataFrame(adaptation).to_string(index=False))
if __name__=='__main__':run()
