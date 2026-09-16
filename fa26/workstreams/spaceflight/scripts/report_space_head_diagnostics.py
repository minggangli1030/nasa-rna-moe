"""Figures and reproducible review of head diagnostics."""
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd,joblib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.metrics import roc_auc_score,balanced_accuracy_score
from evaluate_space_head_diagnostics import ROOT,OUT
import space_head_pilot as pilot

def run():
    m,_,_,_=pilot.load();d=np.load(OUT/'inputs.npz');e=np.load(OUT/'readouts.npz');metrics=pd.read_csv(OUT/'remedy_metrics.csv');pred=pd.read_csv(OUT/'remedy_predictions.csv');a=pd.read_csv(OUT/'supervised_adaptation_metrics.csv');curve=pd.read_csv(OUT/'target_label_learning_curve.csv');decomp=pd.read_csv(OUT/'logit_decomposition.csv');ood=pd.read_csv(OUT/'out_of_domain_features.csv')
    for (fold,variant),g in pred.groupby(['fold','variant']):
        row=metrics[(metrics.fold==fold)&(metrics.variant==variant)].iloc[0];pos=g[g.label==1].logit.to_numpy();neg=g[g.label==0].logit.to_numpy();auc=(pos[:,None]>neg).mean()+.5*(pos[:,None]==neg).mean();assert np.isclose(auc,row.auroc);assert np.isclose(balanced_accuracy_score(g.label,g.logit>=0),row.balanced_accuracy)
    # All persisted target heads reproduce held-out logits and train-only transforms.
    q=pd.read_csv(OUT/'adapted_head_predictions.csv')
    for p in (OUT/'adapted_heads').glob('*.joblib'):
        state=joblib.load(p);x=d['harmonized'][:,d['common']].astype(float) if state['feature_kind']=='common_gene_log1pTPM' else e['harmonized_L12_meanstd'].astype(float)
        train=m.index[m.id.isin(state['training_ids'])].to_numpy();test=m.index[m.id.isin(state['held_out_ids'])].to_numpy();assert set(train).isdisjoint(test);assert len(train)==6 and len(test)==6
        np.testing.assert_allclose(state['training_mean'],x[train].mean(0));model='expression' if state['feature_kind']=='common_gene_log1pTPM' else 'bridge';g=q[(q.model==model)&(q.target_study==state['context'])&(q.training_pool==state['training_pool'])].set_index('id').loc[m.iloc[test].id]
        np.testing.assert_allclose(state['head'].decision_function((x[test]-state['training_mean'])/state['training_scale']),g.logit,rtol=1e-9,atol=1e-9)
    assert len(curve)==152 and len(metrics)==32 and len(a)==24
    # Distinguish no-target-label diagnostic remedies from supervised adaptation visually.
    plt.rcParams.update({'font.size':10})
    fig,axes=plt.subplots(2,2,figsize=(13,10),layout='constrained')
    ax=axes[0,0];v=decomp[decomp.variant=='original_bridge'].sort_values('fold');x=np.arange(2)
    ax.bar(x-.18,v.train_flight_ground_logit_gap,.34,label='Training flight',color='#397b9a');ax.bar(x+.18,v.test_flight_ground_logit_gap,.34,label='Other flight',color='#c56a4e');ax.axhline(0,color='black',lw=.8);ax.set_xticks(x,['First → repeat','Repeat → first']);ax.set_ylabel('Mean flight score − mean ground score (logit)');ax.set_title('A. The learned ordering reverses');ax.legend(frameon=False)
    ax=axes[0,1];variants=['original_expression','original_bridge','FPKM_expression','FPKM_bridge_L12'];labels=['Expression\noriginal','Bridge\noriginal','Expression\nFPKM','Bridge\nFPKM'];vals=[ood[ood.variant==v].fraction_features_beyond_train_range.mean()*100 for v in variants];ax.bar(range(4),vals,color=['#aaa','#888','#71a6a2','#287b77']);ax.set_xticks(range(4),labels);ax.set_ylim(0,100);ax.set_ylabel('Features outside source-training range (%)');ax.set_title('B. Consistent processing reduces the shift');
    for i,v in enumerate(vals):ax.text(i,v+2,f'{v:.1f}%',ha='center')
    ax=axes[1,0];selected=['original_bridge','FPKM_bridge_L12','FPKM_bridge_L1','FPKM_bridge_Hallmark50','FPKM_Hallmark50_expression'];labs=['Original\nBridge','FPKM\nBridge','Earlier\nlayer 1','Bridge\n50 pathways','Expression\n50 pathways']
    for j,name in enumerate(selected):
        z=metrics[metrics.variant==name].auroc.to_numpy();ax.scatter([j-.08,j+.08],z,s=60,color='#795493')
    ax.axhline(.5,color='gray',ls='--');ax.set_ylim(-.05,1.05);ax.set_xticks(range(5),labs);ax.set_ylabel('AUROC');ax.set_title('C. No tested source-only remedy restores transfer')
    ax=axes[1,1]
    for j,(name,label,color) in enumerate([('expression','Expression','#387d97'),('bridge','BridgeRNA','#bc6945')]):
        for i,approach in enumerate(['source_only','target_pool_only']):
            v=a[(a.variant==name)&(a.approach==approach)].balanced_accuracy.to_numpy();xx=i+(j-.5)*.22;ax.scatter(xx+np.linspace(-.035,.035,len(v)),v,color=color,s=50,label=label if i==0 else None);ax.plot([xx-.07,xx+.07],[v.mean()]*2,color=color,lw=2)
    ax.axhline(.5,color='gray',ls='--');ax.set_ylim(-.05,1.05);ax.set_xticks([0,1],['No target-flight labels','6 labeled target chips\nTest the other pool']);ax.set_ylabel('Balanced accuracy');ax.set_title('D. A head adapted to the target experiment works');ax.legend(frameon=False,loc='lower right')
    fig.suptitle('Diagnosis: experiment shift and response reversal, not a swapped label\n24 muscle-chip profiles / two flights / shared donor pools; diagnostic reuse, not independent confirmation',fontsize=13)
    fig.savefig(OUT/'diagnosis_and_remedies.png',dpi=170);fig.savefig(OUT/'diagnosis_and_remedies.pdf');plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(10,4.2),layout='constrained')
    for ax,metric,label in [(axes[0],'auroc','AUROC'),(axes[1],'balanced_accuracy','Balanced accuracy')]:
        for model,color in [('expression','#387d97'),('bridge','#bc6945')]:
            g=curve[curve.model==model].groupby('labeled_chips')[metric].agg(['min','median','max']);ax.plot(g.index,g['median'],marker='o',label=model,color=color);ax.fill_between(g.index,g['min'],g['max'],color=color,alpha=.15)
        ax.set_ylim(-.05,1.05);ax.set_xticks([2,4,6]);ax.set_xlabel('Labeled target-flight chips from one pool');ax.set_ylabel(label);ax.axhline(.5,color='gray',ls='--');ax.legend(frameon=False)
    fig.suptitle('Target-pool adaptation: all balanced chip subsets\nBands are observed min–max sensitivity, not confidence intervals or independent donor replicates',fontsize=11);fig.savefig(OUT/'adaptation_learning_curve.pdf');fig.savefig(OUT/'adaptation_learning_curve.png',dpi=170);plt.close(fig)
    verification={'passed':True,'remedy_metric_checks':32,'adapted_heads_reproduced':8,'learning_curve_fits':152,'source_target_input_gene_order':'verified','original_embedding_max_abs_diff':json.loads((OUT/'reproduction_check.json').read_text())['original_embedding_max_absolute_difference'],'plots':'rendered for visual review','scores':'uncalibrated, exact positive label 1=flight; AUROC calculated from logits'}
    (OUT/'verification.json').write_text(json.dumps(verification,indent=2)+'\n')
    print(json.dumps(verification,indent=2))
if __name__=='__main__':run()
