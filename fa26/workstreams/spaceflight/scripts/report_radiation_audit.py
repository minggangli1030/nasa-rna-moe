"""Verify saved audit outputs and report every prespecified configuration."""
from pathlib import Path
import argparse,itertools,json
import numpy as np,pandas as pd,joblib
from sklearn.metrics import roc_auc_score,balanced_accuracy_score
from controlled_exposure_pilot import sha,dump
from evaluate_controlled_exposure import metrics
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def table(df):
    return '| '+' | '.join(df.columns)+' |\n|'+'|'.join(['---']*len(df.columns))+'|\n'+'\n'.join('| '+' | '.join(str(v) for v in row)+' |' for row in df.itertuples(index=False,name=None))+'\n'


def run(out,old):
    m=pd.read_csv(out/'manifest.csv').fillna('');r=pd.read_csv(out/'metrics.csv');p=pd.read_csv(out/'predictions.csv');s=pd.read_csv(out/'splits.csv');st=pd.read_csv(out/'training_source_sensitivity.csv');ts=pd.read_csv(out/'test_sample_sensitivity.csv');e=np.load(out/'embeddings.npz');eo=np.load(old/'embeddings.npz');d=np.load(out/'inputs.npz');o=np.load(out/'original_inputs.npz');report=json.loads((out/'inference_report.json').read_text())
    assert report['checkpoint_sha256']=='f3491beaa697a0408dc1daeb6f8d648566bd46bafc6e44938d723e7ffc325541'
    assert report['input_sha256']==sha(out/'inputs.npz')
    im=m.set_index('id');checked=0
    for (model,context,cal),g in s.groupby(['model','context','calibration']):
        roles={role:set(g[g.role==role].id) for role in ['train','reference','test']}
        for a,b in itertools.combinations(roles,2):assert not roles[a]&roles[b]
        assert all(im.loc[i,'condition'] in ['control','vehicle'] for i in roles['reference'])
        if context.startswith('GSE230181'):
            source=context.split('|')[1];assert not any(im.loc[i,'source_file']==source for i in roles['train'])
        assert all(im.loc[i,'study']=='GSE230181' for i in roles['train']);checked+=1
    for _,rr in r.iterrows():
        g=p[(p.model==rr.model)&(p.context==rr.context)&(p.calibration==rr.calibration)];mm=metrics(g.label.to_numpy(),g.score.to_numpy())
        for k in ['auroc','balanced_accuracy','TP','TN','FP','FN']:assert np.isclose(mm[k],rr[k])
    common=d['observed'].all(0);z=np.c_[e['mean'],e['std']].astype(float);zo=z.copy();oi=m.original_index.to_numpy(int);zo[oi>=0]=np.c_[eo['mean'],eo['std']][oi[oi>=0]]
    # All serialized absolute heads reproduce external scores; counterfactual challenge labels cannot affect features.
    for route,feature in itertools.product(['ncbi','original'],['expression','bridge']):
        x=({'ncbi':z,'original':zo}[route] if feature=='bridge' else {'ncbi':d['x'],'original':o['x']}[route][:,common].astype(float))
        for target in ['ir_control','hard_negative']:
            name=f'{route}__{feature}__{target}__absolute';head=joblib.load(out/'heads'/f'{name}.joblib');g=p[(p.model==name)&(p.study!='GSE230181')];ix=[m.index[m.id==v][0] for v in g.id];assert np.allclose(head.decision_function(x[ix]),g.score,rtol=1e-9,atol=1e-9)
    # Pure IR/control summaries distinguish controls from other negative stress samples in set E.
    pure=[]
    for (model,context,cal),g in p[p.condition.isin(['control','irradiated'])].groupby(['model','context','calibration']):
        if g.label.nunique()<2:continue
        pure.append({'model':model,'context':context,'calibration':cal,'evaluation':g.evaluation.iloc[0],**metrics(g.label.to_numpy(),g.score.to_numpy())})
    pd.DataFrame(pure).to_csv(out/'ir_control_only_metrics.csv',index=False)
    primary='ncbi__bridge__ir_control__absolute';base='original__bridge__ir_control__absolute';rr=r[(r.model==primary)&r.evaluation.isin(['new_2Gy_challenge','lung_development'])].copy()
    rr[['experiment','auroc','balanced_accuracy','n','TP','TN','FP','FN']].to_csv(out/'primary_transfer_summary.csv',index=False)
    spec=p[(p.model==primary)&p.condition.isin(['bleomycin','rotenone','antimycin','oligomycin','ras_induction'])].groupby('condition').positive.agg(['sum','count','mean']);spec.to_csv(out/'primary_specificity_summary.csv')
    # Figure: transparent threshold transport, source deletion stability, and specificity failure.
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,ax=plt.subplots(1,3,figsize=(15,5),constrained_layout=True)
    for j,(route,color,label) in enumerate([('original','#777777','Original processing'),('ncbi','#167d8d','Common NCBI counts')]):
        for k,t in enumerate(['6h','24h']):
            val=r[(r.model==f'{route}__bridge__ir_control__absolute')&(r.evaluation=='new_2Gy_challenge')&(r.experiment==t)].balanced_accuracy.iloc[0]
            sr=st[(st.route==route)&(st.feature=='bridge')&(st.study=='GSE111437')&(st.group==t)].balanced_accuracy
            xpos=k+(j-.5)*.18;ax[0].plot([xpos,xpos],[sr.min(),sr.max()],color=color,lw=3);ax[0].scatter(xpos,val,s=70,color=color,label=label if k==0 else None,zorder=3)
    ax[0].set(title='2 Gy IMR90: threshold performance',xticks=[0,1],xticklabels=['6 hours','24 hours'],ylim=(0,1.08),ylabel='Balanced accuracy');ax[0].axhline(.5,ls='--',color='#aaa');ax[0].legend(fontsize=9,loc='center left',bbox_to_anchor=(0.01,0.34));ax[0].text(.5,.08,'Dot: full training set\nLine: remove one training file\n3 irradiated + 3 controls per time',transform=ax[0].transAxes,ha='center',fontsize=9)
    names=['bleomycin','rotenone','oligomycin','antimycin','ras_induction'];v=spec.loc[names]
    ax[1].barh(range(5),v['mean'],color='#c7795c');ax[1].set(yticks=range(5),yticklabels=['Bleomycin','Rotenone','Oligomycin','Antimycin','Ras induction'],xlim=(0,1.25),xlabel='Fraction incorrectly called radiation',title='Specificity still fails (common counts)');ax[1].invert_yaxis()
    for i,row in enumerate(v.itertuples()):ax[1].text(row.mean+.03,i,f'{row.sum}/{row.count}',va='center')
    ax[1].text(.02,-.24,'Stress-source file excluded from head training.\nRas uses a different engineered-cell context.',transform=ax[1].transAxes,fontsize=9)
    for k,t in enumerate(['6h','24h']):
        g=p[(p.model==primary)&(p.evaluation=='new_2Gy_challenge')&(p.experiment==t)]
        for label,marker,color in [(0,'o','#6b7785'),(1,'^','#167d8d')]:
            vals=g[g.label==label].score.to_numpy();xx=k+np.linspace(-.08,.08,len(vals))+(label-.5)*.25
            ax[2].scatter(xx,vals,marker=marker,color=color,s=55,label=('Control' if label==0 else '2 Gy') if k==0 else None)
    ax[2].axhline(0,color='#999',ls='--');ax[2].set(title='Individual head-held-out samples',xticks=[0,1],xticklabels=['6 hours','24 hours'],ylabel='Radiation-head logit (uncalibrated)');ax[2].legend(fontsize=9)
    fig.suptitle('A reproducible irradiation-associated lead, not a radiation-specific flight explanation\nFrozen BRIDGE; culture replicates; GSE111437 is present in encoder pretraining catalog',fontsize=12)
    for ext in ['png','pdf']:fig.savefig(out/f'robustness_audit.{ext}',dpi=180)
    plt.close(fig)
    # Every configuration, with min–max over reference choices rather than selecting a favorable choice.
    models=sorted(r.model.unique());domains=['6h','24h','Lung endothelium_6h','Lung endothelium_7d','Lung epithelium_6h','Lung epithelium_7d'];vals=np.zeros((16,6));labels=[];allrows=[]
    for i,name in enumerate(models):
        labels.append(name.replace('__',' / ').replace('matched_control','reference').replace('hard_negative','stress negatives').replace('ir_control','IR/control'))
        for j,domain in enumerate(domains):
            g=r[(r.model==name)&(r.experiment==domain)&r.evaluation.isin(['new_2Gy_challenge','lung_development'])];low=g.balanced_accuracy.min();high=g.balanced_accuracy.max();vals[i,j]=(low+high)/2
            allrows.append({'model':name,'domain':domain,'AUROC_min':g.auroc.min(),'AUROC_max':g.auroc.max(),'BA_min':low,'BA_max':high})
    ar=pd.DataFrame(allrows);ar.to_csv(out/'all_configuration_summary.csv',index=False)
    fig,ax=plt.subplots(figsize=(15,9),constrained_layout=True);img=ax.imshow(vals,vmin=0,vmax=1,cmap='YlGnBu',aspect='auto')
    for i,name in enumerate(models):
        for j,domain in enumerate(domains):
            g=ar[(ar.model==name)&(ar.domain==domain)].iloc[0];label=f'{g.BA_min:.2f}' if g.BA_min==g.BA_max else f'{g.BA_min:.2f}–{g.BA_max:.2f}';ax.text(j,i,label,ha='center',va='center',fontsize=8,color='white' if vals[i,j]>.7 else '#222')
    ax.set(xticks=range(6),xticklabels=['IMR90 6h','IMR90 24h','Endoth. 6h','Endoth. 7d','Epith. 6h','Epith. 7d'],yticks=range(16),yticklabels=labels,title='All prespecified configurations: balanced accuracy\nRanges enumerate disjoint reference-control choices; not independent replications');fig.colorbar(img,ax=ax,shrink=.6)
    for ext in ['png','pdf']:fig.savefig(out/f'all_configurations.{ext}',dpi=180)
    plt.close(fig)
    t=rr[['experiment','n','auroc','balanced_accuracy','TP','TN','FP','FN']].copy();t['auroc']=t.auroc.map(lambda x:f'{x:.3f}');t['balanced_accuracy']=t.balanced_accuracy.map(lambda x:f'{x:.3f}')
    text='''# Radiation robustness audit — September 15, 2026

**Verdict: a stronger, narrow irradiation-associated result; no validated radiation-specific explanation of flight yet.** A common-count BRIDGE head recognized a new head-held-out IMR90 irradiation study at both 6h and 24h. The 24h decision survived deleting any entire training expression file. Specificity against other stresses and transfer across cell types remain inadequate.

## What was audited

- **130 unique expression profiles:** 86 retained GSE230181 profiles, 32 GSE242706 lung-chip profiles, and 12 GSE111437 profiles (2Gy X-ray; 6h/24h; 3 irradiated + 3 sham cultures each). All 130 treatment labels independently matched original GEO metadata; no exact expression duplicates were found. Cultures are not independent donors.
- **Processing mismatch:** run06 mixed author RPKM training data with NCBI count test data. Run07 recomputed all studies from NCBI gene counts with identical pinned exon lengths and the same 15,061 canonical genes. Between processing routes, per-sample expression rank correlation was 0.949–0.964, so processing is similar but not interchangeable. This harmonizes quantification, not all library preparation or biological batch effects.
- Five old profiles lack NCBI count columns, including three training profiles. Both processing routes use the same retained sample IDs (35 IR/control training cultures: 17 IR, 18 controls; 58 with stress negatives). No missing profile was imputed. Original run06 is immutable; its full-sample results are not conflated with this subset comparison.
- **16 declared configurations:** two processing routes × expression/BRIDGE × IR/control or stress-negative training × absolute or matched-control features. Fixed C=1, train-only variance/scaling, fixed zero-logit threshold; no tuning on new outcomes. All source-file splits keep B/C together. New-study outcomes were examined only after the protocol was frozen; no winner was refitted on them.
- **Reference controls:** separate known controls are subtracted from frozen features, never from the raw input before BRIDGE. All choices of two references are enumerated (one when only two controls exist), and reference samples are never scored as test samples. This requires controls at deployment and does not solve unrestricted single-sample prediction. Training controls use leave-self-out references.
- GSE111437 is **new to the prediction head**, but 7 profiles are `train` and 5 `val` in the supplied encoder catalog. It is not a fully unseen-model or independent-donor benchmark. GSE242706 and all prior challenges are now development data.

## Positive result: same-cell irradiation transfer

Common-count BRIDGE, IR/control training, absolute features, unchanged threshold:

'''+table(t)+'''
For the new 2Gy IMR90 samples, AUROC stays 1.0 at both time points under both processing routes, every entire-training-file deletion, and every single-test-sample deletion. **At 24h, common-count balanced accuracy stays 1.0 under all four training-file deletions.** At 6h it varies from 0.50 to 0.833: ranking is stable, the decision boundary is not. Original processing gives 24h accuracy 1.0 but 6h balanced accuracy 0.50; common counts improves the latter to 0.833 in the full fit.

This is a useful response-association lead. Each time point still contains only six cultures from one cell strain. With 3/3 class counts, perfect fixed-score AUROC has a minimum exact one-sided label-permutation p of 0.05; these descriptive tests are not multiplicity-adjusted. This does not establish population accuracy or calibrated radiation probabilities. Expression baselines also rank 24h perfectly, but their fixed thresholds yield balanced accuracy 0.50; a general BRIDGE advantage is unproven.

## Why it still cannot explain flight as “radiation-driven”

1. **The signature is not specific to radiation.** The common-count IR/control BRIDGE head calls 4/5 bleomycin, 3/3 rotenone, 3/5 oligomycin and 3/3 Ras samples positive, with each challenge's source file excluded from training (antimycin: 0/5). These are known non-radiation conditions. A shared downstream stress response can resemble irradiation without identifying the exposure that produced it.
2. **Context changes matter.** Lung-chip balanced accuracy remains 0.50–0.75, and epithelial 7d AUROC falls to 0.563. Some strata rank well but have shifted score baselines; others have weak or reversed ranking. Removing the two samples with inconsistent cell-line fields does not resolve this. At 24h the IMR90 strain matches training; lung-chip cells do not.
3. **Hard negatives and references are not general fixes.** Common-count stress-negative training leaves all lung-chip samples positive, with AUROC 0–0.313. Matched-control models improve selected development strata but fail others and can increase chemical-stress false positives. All comparisons are retained; no model is promoted as a general radiation detector.
4. **Detecting a response is different from the flight head relying on it.** The frozen muscle-chip flight heads score the new irradiated IMR90 cultures *lower* than their controls (about −3.25 to −6.07 logit units across heads/times). This is an out-of-domain diagnostic, not proof that radiation biologically opposes flight. It does show that positive irradiation-probe scores cannot simply be assigned as positive contributions to the existing flight head.

The honest current label is **“irradiation-associated, stress-overlapping response evidence in a defined context.”** Neither the head's sigmoid nor a pathway-attribution share means “80% caused by radiation.”

## Next bounded step

Retain the common-count IR/control head as a research comparator and the 24h IMR90 result as the strongest current transfer lead. Do not deploy the stress-negative or matched-control versions as general improvements. Use tissue/time-matched controlled exposures to test response specificity and the direction of flight-head reliance together. The most useful new data would include muscle-relevant radiation, altered-gravity and non-radiation stress conditions with matched controls and independent donors/experiments. Add encoder adaptation only against a fixed, genuinely independent evaluation; larger capacity cannot supply missing exposure labels.

For the intended user-facing output, first present response evidence (DNA-damage/repair, oxidative, mitochondrial, inflammatory, etc.), signed flight-score reliance and unassigned evidence. Promote a response to a radiation/gravity label only when controlled-exposure specificity and flight-head reliance both pass. Controlled-gravity quantification remains a separate next analysis, not evidence supplied by this radiation audit.

## Artifacts and reproducibility

[Main figure](robustness_audit.pdf) · [Every configuration](all_configurations.pdf) · [Frozen protocol](protocol.json) · [Input audit](input_audit.json) · [All metrics](metrics.csv) · [IR/control-only metrics](ir_control_only_metrics.csv) · [Source-deletion sensitivity](training_source_sensitivity.csv) · [Independent verification](independent_verification.json).

`metrics.csv` evaluates every context with all its non-IR conditions as negatives (set E includes rotenone). `ir_control_only_metrics.csv` explicitly excludes other stresses. Reference-choice ranges are dependent sensitivity checks, not extra sample size. The source-deletion and sample-deletion checks were declared after initial run07 outcomes in `stability_amendment.json`; they are robustness checks, not fresh confirmation.

Frozen BRIDGE inference ran on moe-reboot A100 for 48.3 seconds, peak allocated memory 0.63GB. Small heads and reports ran locally. No LoRA, encoder training or flight-head update occurred. The launch SSH session timed out after dispatch; the job completed successfully and its completion marker, hashes and outputs were retrieved. No job remains running; the watcher remains paused.

Public primary metadata: [GSE230181](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE230181), [GSE242706](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE242706), [GSE111437](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE111437). Original family SOFT files and count matrices are retained locally, with hashes. Metadata were used to define samples and controls; attached figures were not treated as instructions.
'''
    (out/'REPORT.md').write_text(text)
    dump(out/'independent_verification.json',{'verified_split_groups':checked,'all_train_reference_test_roles_disjoint':True,'all_training_study_GSE230181':True,'all_source_files_excluded_from_same_study_test_training':True,'all_metric_confusions_recomputed':len(r),'all_saved_absolute_heads_reproduce_external_predictions':True,'checkpoint_hash_verified':True,'input_hash_verified':True,'labels_independently_verified':len(pd.read_csv(out/'independent_label_audit.csv')),'inference_seconds':report['seconds'],'script_sha256':sha(Path(__file__))})
    dump(out/'STATUS.json',{'state':'complete','samples':len(m),'encoder_updated':False,'verdict':'Narrow 24h IMR90 irradiation-transfer lead; exposure specificity and flight-head reliance not validated'})
    (out/'README.md').write_text('# Radiation robustness audit\n\nSee [report](REPORT.md), [main figure](robustness_audit.pdf), [all configurations](all_configurations.pdf), and [execution](EXECUTION.md).\n')
    print('Verified',checked,'split groups and',len(r),'metric rows; report/figures written')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--folder',type=Path,required=True);p.add_argument('--old',type=Path,default=Path('fa26/workstreams/spaceflight/runs/06_controlled_exposure_validation_2026-09-14'));a=p.parse_args();run(a.folder,a.old)
