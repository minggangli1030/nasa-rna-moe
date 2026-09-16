"""Evaluate radiation-response probes with source-file holdouts and non-radiation challenges."""
from pathlib import Path
import argparse,json,hashlib
import numpy as np
import pandas as pd
import joblib
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score,balanced_accuracy_score,confusion_matrix
from scipy.stats import rankdata
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,indent=2)+'\n')

def fit(name,x,y):
    parts=[('scale',StandardScaler())]
    if name=='pca5_linear':parts.append(('pca',PCA(n_components=5,svd_solver='full')))
    parts.append(('head',LogisticRegression(C=1,solver='liblinear',max_iter=3000,random_state=17)))
    model=Pipeline(parts).fit(x,y)
    assert model.named_steps['head'].n_iter_[0]<3000
    assert np.allclose(model.named_steps['scale'].mean_,x.mean(0))
    return model

def metrics(y,s):
    pred=(s>=0).astype(int);tn,fp,fn,tp=confusion_matrix(y,pred,labels=[0,1]).ravel()
    return {'auroc':float(roc_auc_score(y,s)),'balanced_accuracy':float(balanced_accuracy_score(y,pred)),'n':len(y),'TP':int(tp),'TN':int(tn),'FP':int(fp),'FN':int(fn),'mean_positive_logit':float(s[y==1].mean()),'mean_negative_logit':float(s[y==0].mean())}

def run(root,out):
    assert not (out/'metrics.csv').exists(),'Preserve completed runs'
    m=pd.read_csv(out/'manifest.csv').fillna('');d=np.load(out/'inputs.npz');e=np.load(out/'embeddings.npz');report=json.loads((out/'inference_report.json').read_text())
    assert sha(out/'inputs.npz')==report['input_sha256'];assert m.id.tolist()==d['ids'].tolist()==e['ids'].tolist()
    assert np.isfinite(e['mean']).all() and np.isfinite(e['std']).all()
    common=d['observed'].all(0);x=d['x'][:,common].astype(float);z=np.concatenate([e['mean'],e['std']],axis=1).astype(float)
    programs=json.loads((out/'programs.json').read_text());six=np.column_stack([d['x'][:,p['indices']].mean(1) for p in programs]).astype(float)
    features={'expression_linear':x,'pca5_linear':x,'bridge_meanstd_linear':z,'six_programs_linear':six}
    assert all(np.isfinite(v).all() for v in features.values())
    y=m.radiation_label.to_numpy(int);train=np.flatnonzero(m.training_eligible.to_numpy(bool));assert len(train)==38
    fits={};full={};results=[];preds=[];splits=[];specificity=[]
    (out/'heads').mkdir(exist_ok=True)
    def evaluate(name,model,tr,te,kind,fold,target_y=None):
        yy=y[te] if target_y is None else target_y;s=model.decision_function(features[name][te]);assert np.isfinite(s).all()
        assert not set(tr)&set(te)
        results.append({'model':name,'evaluation':kind,'fold':fold,'n_train':len(tr),**metrics(yy,s)})
        for i,l,score in zip(te,yy,s):preds.append({'model':name,'evaluation':kind,'fold':fold,'id':m.iloc[i].id,'label':int(l),'score_logit':float(score),'predicted_positive':bool(score>=0),'condition':m.iloc[i].condition,'cell_type':m.iloc[i].cell_type})
        splits.extend({'model':name,'evaluation':kind,'fold':fold,'role':role,'id':m.iloc[i].id} for role,idx in [('train',tr),('test',te)] for i in idx)
        return s
    for name,xx in features.items():
        full[name]=fit(name,xx[train],y[train]);joblib.dump(full[name],out/'heads'/f'{name}__IMR90_all.joblib')
        for source in sorted(m.iloc[train].source_file.unique()):
            tr=train[m.iloc[train].source_file.to_numpy()!=source];te=train[m.iloc[train].source_file.to_numpy()==source]
            assert len(set(m.iloc[tr].source_file)&set(m.iloc[te].source_file))==0
            fitted=fit(name,xx[tr],y[tr]);fits[name,source]=fitted
            evaluate(name,fitted,tr,te,'held_out_expression_file',source)
        # External study: no fitting, threshold changes, or target normalization from labels.
        for group,g in m[m.study=='GSE242706'].groupby('experiment_set'):
            evaluate(name,full[name],train,g.index.to_numpy(),'external_lung_chip',group)
        # Other cells in development study share a study/file: explicitly weaker validation.
        for cell,g in m[(m.study=='GSE230181')&(m.cell_type!='IMR90')].groupby('cell_type'):
            evaluate(name,full[name],train,g.index.to_numpy(),'other_cell_same_study',cell)
        # Challenge heads have not seen the source file containing that non-radiation stress.
        for stress in ['bleomycin','antimycin','oligomycin','rotenone','ras_induction']:
            sg=m[m.condition==stress];source=sg.source_file.iloc[0];tr=train[m.iloc[train].source_file.to_numpy()!=source]
            model=fits.get((name,source),full[name]);stressix=sg.index.to_numpy();stressscores=model.decision_function(xx[stressix])
            ctrlcondition='control' if stress in ['rotenone','ras_induction'] else 'vehicle'
            cg=m[(m.source_file==source)&(m.cell_type=='IMR90')&(m.condition==ctrlcondition)]
            cs=model.decision_function(xx[cg.index]);ir=m[(m.source_file==source)&m.training_eligible&(m.radiation_label==1)]
            rr={'model':name,'stress':stress,'held_out_source':source,'n_stress':len(sg),'n_control':len(cg),'stress_false_positive_fraction':float((stressscores>=0).mean()),'control_false_positive_fraction':float((cs>=0).mean()),'mean_stress_logit':float(stressscores.mean()),'mean_control_logit':float(cs.mean()),'stress_minus_control_logit':float(stressscores.mean()-cs.mean()),'radiation_vs_other_auroc':np.nan}
            if len(ir):
                te=np.r_[ir.index.to_numpy(),stressix];yy=np.r_[np.ones(len(ir),int),np.zeros(len(stressix),int)]
                s=evaluate(name,model,tr,te,'radiation_vs_other_stress',stress,yy);rr['radiation_vs_other_auroc']=roc_auc_score(yy,s)
            else:
                # Ras has no irradiated group in this file; don't manufacture that comparison.
                for i,score in zip(stressix,stressscores):preds.append({'model':name,'evaluation':'other_stress_only','fold':stress,'id':m.iloc[i].id,'label':0,'score_logit':float(score),'predicted_positive':bool(score>=0),'condition':stress,'cell_type':'IMR90'})
            specificity.append(rr)
    res=pd.DataFrame(results);res.to_csv(out/'metrics.csv',index=False);pd.DataFrame(preds).to_csv(out/'predictions.csv',index=False);pd.DataFrame(splits).to_csv(out/'splits.csv',index=False);sp=pd.DataFrame(specificity);sp.to_csv(out/'specificity.csv',index=False)
    # Independent six-program expression checks; every contrast is within its source/context.
    contrasts=[]
    for source,g in m[m.training_eligible].groupby('source_file'):
        for exp,sg in g.groupby('experiment_set'):contrasts.append(('IMR90_IR_'+exp,sg.index.to_numpy(),sg.radiation_label.to_numpy(int)))
    for group,g in m[m.study=='GSE242706'].groupby('experiment_set'):contrasts.append(('lung_chip_'+group,g.index.to_numpy(),g.radiation_label.to_numpy(int)))
    for cell,g in m[(m.study=='GSE230181')&(m.cell_type!='IMR90')].groupby('cell_type'):contrasts.append(('other_cell_'+cell,g.index.to_numpy(),g.radiation_label.to_numpy(int)))
    for stress in ['bleomycin','antimycin','oligomycin','rotenone','ras_induction']:
        sg=m[m.condition==stress];src=sg.source_file.iloc[0];cc='control' if stress in ['rotenone','ras_induction'] else 'vehicle';g=m[(m.source_file==src)&m.condition.isin([cc,stress])&(m.cell_type=='IMR90')];contrasts.append((stress,g.index.to_numpy(),g.condition.eq(stress).to_numpy(int)))
    rank=rankdata(x,axis=1)/common.sum();mapping={g:i for i,g in enumerate(np.flatnonzero(common))};pr=[];headrows=[]
    old=np.load(root/'artifacts/space_head_attribution_2026-09-14/attribution_inputs.npz')
    oldscores={pool:z@old[f'{pool}_weight']+float(old[f'{pool}_bias']) for pool in ['YA','OS']}
    for label,idx,yy in contrasts:
        for j,p in enumerate(programs):
            expr=six[idx,j];delta=float(expr[yy==1].mean()-expr[yy==0].mean());ri=[mapping[v] for v in p['indices']];rs=rank[idx][:,ri].mean(1);rd=float(rs[yy==1].mean()-rs[yy==0].mean());loo=[]
            for omit in range(len(idx)):
                keep=np.arange(len(idx))!=omit;loo.append(float(expr[(yy==1)&keep].mean()-expr[(yy==0)&keep].mean()))
            pr.append({'contrast':label,'program':p['key'],'n_exposed':int((yy==1).sum()),'n_control':int((yy==0).sum()),'mean_log1p_TPM_shift':delta,'rank_shift':rd,'rank_agrees':bool(np.sign(delta)==np.sign(rd)),'leave_one_sign_retention':float((np.sign(loo)==np.sign(delta)).mean())})
        for pool,s in oldscores.items():
            headrows.append({'contrast':label,'old_flight_head_training_pool':pool,'out_of_domain_diagnostic_only':True,'treated_minus_control_flight_logit':float(s[idx][yy==1].mean()-s[idx][yy==0].mean()),'limitation':'Different tissues/preparation; not a validated exposure contribution or flight test'})
    pd.DataFrame(pr).to_csv(out/'controlled_program_expression.csv',index=False);pd.DataFrame(headrows).to_csv(out/'old_flight_head_stress_response.csv',index=False)
    # Charts show every split; no best-fold selection.
    labels=['Expression','PCA (5)','BRIDGE mean+SD','Six programs'];names=list(features);colors=['#626b77','#d08636','#167d8d','#9563a4']
    fig,axs=plt.subplots(1,3,figsize=(15,4.8),constrained_layout=True)
    for ax,kind,title in [(axs[0],'held_out_expression_file','Held-out experiment file'),(axs[1],'external_lung_chip','Independent lung-chip study'),(axs[2],'radiation_vs_other_stress','Radiation versus other stresses')]:
        for j,name in enumerate(names):
            vv=res[(res.model==name)&(res.evaluation==kind)].auroc.to_numpy();offset=np.linspace(-.15,.15,len(vv));ax.scatter(j+offset,vv,color=colors[j],s=45)
        ax.axhline(.5,color='#999',ls='--');ax.set_ylim(-.05,1.05);ax.set_xticks(range(4),labels,rotation=20,ha='right');ax.set_title(title);ax.set_ylabel('AUROC (radiation = positive)');ax.grid(axis='y',alpha=.15)
    fig.suptitle('Radiation-response probe: transfer and specificity\nEach dot is a file, cell/time stratum or stress comparison; dots are not independent donors.',fontsize=11)
    fig.savefig(out/'exposure_probe_validation.pdf');fig.savefig(out/'exposure_probe_validation.png',dpi=180);plt.close(fig)
    dump(out/'verification.json',{'n_new_profiles':len(m),'n_train_IMR90':38,'input_hash_and_ID_alignment':True,'finite_inputs_embeddings_predictions':True,'whole_file_holdout_without_overlap':True,'scalers_and_PCA_training_only':True,'all_heads_converged':True,'fixed_zero_logit_threshold':True,'new_encoder_training':False,'metrics_rows':len(res),'specificity_rows':len(sp)})
    dump(out/'analysis_provenance.json',{'script_sha256':sha(Path(__file__)),'input_sha256':sha(out/'inputs.npz'),'embedding_sha256':sha(out/'embeddings.npz'),'protocol_sha256':sha(out/'protocol.json'),'sources':['https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE230181','https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE242706']})
    print(res.groupby(['evaluation','model'])[['auroc','balanced_accuracy']].agg(['min','max']).to_string());print('\nSPECIFICITY');print(sp.to_string(index=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--folder',type=Path,required=True);a=p.parse_args();run(a.root,a.folder)
