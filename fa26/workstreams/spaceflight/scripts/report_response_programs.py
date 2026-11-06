"""Response-level evidence reports for the fixed experiment-specific classifier."""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def dump(p,x):
    p.write_text(json.dumps(x,indent=2)+'\n')


def load(folder):
    d=np.load(folder/'attribution_inputs.npz');rows=pd.read_csv(folder/'attribution_rows.csv')
    assert len(rows)==24 and np.array_equal(d['ids'],pd.read_csv(folder/'cohort.csv').id)
    a=np.load(folder/'attributions.npz')['attributions']
    ex=np.load(folder/'expression_attributions.npz')['attributions']
    assert a.shape==ex.shape==(24,15165)
    programs=json.loads((folder/'programs.json').read_text())
    return d,rows,a,ex,programs


def local(folder):
    d,rows,a,ex,programs=load(folder);folds=json.loads((folder/'folds.json').read_text())
    common=d['common'].astype(bool);x=np.nan_to_num(d['x'],nan=-10);n=len(common)
    members=np.zeros((6,n),bool)
    for j,p in enumerate(programs):members[j,p['indices']]=True
    count=members.sum(0);weights=members/np.maximum(count,1)[None,:]
    weights=np.vstack([weights,((count==0)&common)[None,:]])
    assert np.all(weights[:,common].sum(0)==1)
    evidence=[];alloc=[];summary=[];loo=[];genes=[]
    for model,attrs in [('bridge',a),('expression',ex)]:
        for k,row in rows.iterrows():
            fold=next(f for f in folds if f['training_pool']==row.training_pool)
            ri=fold['reference_names'].index(row.reference);ref=d[f'{row.training_pool}_references'][ri]
            delta=x[int(row.sample_index)].astype(float)-ref
            pos=np.maximum(attrs[k],0);neg=np.maximum(-attrs[k],0)
            for j,p in enumerate(programs):
                ix=np.asarray(p['indices']);con=attrs[k,ix]
                evidence.append({'model':model,**row.to_dict(),'program':p['key'],'label_display':p['label'],'n_genes':len(ix),'mean_log1p_TPM_difference':float(delta[ix].mean()),'fraction_genes_above_reference':float((delta[ix]>0).mean()),'signed_IG_logit':float(con.sum()),'positive_IG_logit':float(np.maximum(con,0).sum()),'opposing_IG_logit':float(np.maximum(-con,0).sum())})
                top=ix[np.argsort(-np.abs(con))[:5]]
                for rank,gi in enumerate(top,1):
                    genes.append({'model':model,**row.to_dict(),'program':p['key'],'rank':rank,'gene':str(d['genes'][gi]),'IG_logit':float(attrs[k,gi]),'log1p_TPM_difference':float(delta[gi])})
            for j,key in enumerate([p['key'] for p in programs]+['outside_six_programs']):
                ap=float(weights[j]@pos);an=float(weights[j]@neg)
                alloc.append({'model':model,**row.to_dict(),'program':key,'positive_allocated_logit':ap,'opposing_allocated_logit':an,'supporting_share_percent':100*ap/pos.sum() if pos.sum() else 0,'opposing_share_percent':100*an/neg.sum() if neg.sum() else 0})
            assert np.isclose(sum(weights[j]@attrs[k] for j in range(7)),attrs[k].sum())
        for (pool,refname),g in rows.groupby(['training_pool','reference']):
            idx=g.index.to_numpy();y=g.label.to_numpy();z=attrs[idx]
            for p in programs:
                ix=np.asarray(p['indices']);per_sample=z[:,ix].sum(1)
                expr=x[g.sample_index.to_numpy()][:,ix].mean(1)
                gap=float(per_sample[y==1].mean()-per_sample[y==0].mean())
                summary.append({'model':model,'training_pool':pool,'reference':refname,'program':p['key'],'response_attribution_gap':gap,'flight_ground_mean_log1p_TPM_difference':float(expr[y==1].mean()-expr[y==0].mean())})
                for omitted in range(6):
                    keep=np.arange(6)!=omitted
                    val=float(per_sample[(y==1)&keep].mean()-per_sample[(y==0)&keep].mean())
                    loo.append({'model':model,'training_pool':pool,'reference':refname,'program':p['key'],'omitted_id':g.iloc[omitted].id,'response_attribution_gap':val,'retains_full_sign':bool(np.sign(val)==np.sign(gap))})
    for name,data in [('program_evidence.csv',evidence),('evidence_allocation.csv',alloc),('program_response_contrasts.csv',summary),('leave_one_chip.csv',loo),('supporting_genes.csv',genes)]:
        pd.DataFrame(data).to_csv(folder/name,index=False)
    alloc=pd.DataFrame(alloc)
    shares=alloc.groupby(['model','training_pool','id','reference'])[['supporting_share_percent','opposing_share_percent']].sum()
    assert np.allclose(shares,100)
    dump(folder/'local_verification.json',{'aligned_sample_ids':True,'allocation_sums_to_100_percent_separately':True,'allocation_reconstructs_signed_IG':True,'program_count':6,'gene_sets_are_associations_not_exposure_detectors':True,'new_model_training':False})
    print('Local response expression, attribution, overlap allocation and deletion checks complete.')


def final(folder):
    d,rows,a,ex,programs=load(folder)
    p=pd.read_csv(folder/'perturbations.csv');scores=pd.read_csv(folder/'score_checks.csv')
    assert len(p)==6048 and len(scores)==24
    keys=['training_pool','id','reference','program','kind','replicate','renormalized']
    assert not p.duplicated(keys).any()
    assert p.groupby(['training_pool','id','reference']).size().eq(252).all()
    assert p.groupby(['training_pool','id','reference','program','renormalized']).size().eq(21).all()
    assert np.isfinite(p[['bridge_logit_change','expression_logit_change','perturbed_logit']]).all().all()
    assert scores.prior_logit_error.max()<1e-5
    assert p.groupby('id').label.nunique().eq(1).all()
    ev=pd.read_csv(folder/'program_evidence.csv');contrast=pd.read_csv(folder/'program_response_contrasts.csv');loo=pd.read_csv(folder/'leave_one_chip.csv')
    for row in p[(p.kind=='program')&~p.renormalized].itertuples():
        ee=ev[(ev.model=='expression')&(ev.training_pool==row.training_pool)&(ev.id==row.id)&(ev.reference==row.reference)&(ev.program==row.program)].iloc[0]
        assert abs(row.expression_logit_change-ee.signed_IG_logit)<1e-5
    per=[];case=[];stability=[]
    for model,col in [('bridge','bridge_logit_change'),('expression','expression_logit_change')]:
        for key,g in p.groupby(['training_pool','id','reference','program','renormalized'],sort=False):
            pool,ident,ref,prog,ren=key;t=g[g.kind=='program'].iloc[0];r=g[g.kind=='matched_random'][col]
            val=float(t[col])
            per.append({'model':model,'training_pool':pool,'id':ident,'label':int(t.label),'reference':ref,'program':prog,'renormalized':bool(ren),'logit_change':val,'matched_random_median':float(r.median()),'matched_random_abs_percentile':float((abs(r)<abs(val)).mean()),'matched_random_signed_percentile':float((r<val).mean())})
        # Panels are fixed within each training head and reused across chips.
        for key,g in p.groupby(['training_pool','reference','program','renormalized'],sort=False):
            pool,ref,prog,ren=key;gaps=[]
            for (kind,rep),v in g.groupby(['kind','replicate']):
                assert len(v)==6
                gap=float(v[v.label==1][col].mean()-v[v.label==0][col].mean())
                gaps.append((kind,rep,gap))
            value=next(v for kind,rep,v in gaps if kind=='program');rand=np.array([v for kind,rep,v in gaps if kind=='matched_random'])
            case.append({'model':model,'training_pool':pool,'reference':ref,'program':prog,'renormalized':bool(ren),'flight_ground_score_gap_removed':value,'random_gap_median':float(np.median(rand)),'matched_random_abs_percentile':float((abs(rand)<abs(value)).mean())})
            target=g[g.kind=='program']
            for omitted in target.id:
                z=target[target.id!=omitted];gap=float(z[z.label==1][col].mean()-z[z.label==0][col].mean())
                stability.append({'model':model,'training_pool':pool,'reference':ref,'program':prog,'renormalized':bool(ren),'omitted_id':omitted,'gap_removed':gap,'retains_full_sign':bool(np.sign(gap)==np.sign(value))})
    per=pd.DataFrame(per);case=pd.DataFrame(case);stability=pd.DataFrame(stability)
    per.to_csv(folder/'per_sample_reliance.csv',index=False);case.to_csv(folder/'program_reliance_contrasts.csv',index=False);stability.to_csv(folder/'reliance_leave_one_chip.csv',index=False)
    synopsis=[]
    for program in programs:
        key=program['key'];c=case[(case.model=='bridge')&(case.program==key)];raw=c[~c.renormalized]
        st=stability[(stability.model=='bridge')&(stability.program==key)];ig=contrast[(contrast.model=='bridge')&(contrast.program==key)]
        expr=ig.groupby('training_pool').flight_ground_mean_log1p_TPM_difference.first()
        signed=np.sign(c.flight_ground_score_gap_removed.to_numpy())
        rawsign=np.sign(raw.flight_ground_score_gap_removed.to_numpy())
        synopsis.append({'program':key,'response_label':program['label'],'gene_set':program['gene_set'],'n_genes':program['n_genes'],'expression_difference_min':float(expr.min()),'expression_difference_max':float(expr.max()),'attribution_gap_min':float(ig.response_attribution_gap.min()),'attribution_gap_max':float(ig.response_attribution_gap.max()),'replacement_gap_min':float(raw.flight_ground_score_gap_removed.min()),'replacement_gap_max':float(raw.flight_ground_score_gap_removed.max()),'same_sign_all_4_primary_cases':bool((rawsign==rawsign[0]).all() and rawsign[0]!=0),'same_sign_all_8_including_renormalization':bool((signed==signed[0]).all() and signed[0]!=0),'leave_one_chip_sign_retention':float(st.retains_full_sign.mean()),'min_matched_random_abs_percentile':float(raw.matched_random_abs_percentile.min()),'max_matched_random_abs_percentile':float(raw.matched_random_abs_percentile.max()),'exposure_specificity':'Not established'})
    syn=pd.DataFrame(synopsis);syn.to_csv(folder/'response_summary.csv',index=False)
    # Independent direct expression model is displayed in its own score scale.
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axs=plt.subplots(1,3,figsize=(16,5.2),constrained_layout=True)
    display=['Mitochondrial\nexpression','DNA repair','Oxidative-stress\nassociation','Inflammatory\nsignaling','Unfolded-protein\nresponse','Muscle\nremodeling']
    palette={'YA':'#167d8d','OS':'#bc6638'}
    for j,prog in enumerate(programs):
        for pool,offset in [('YA',-.10),('OS',.10)]:
            g=contrast[(contrast.model=='bridge')&(contrast.program==prog['key'])&(contrast.training_pool==pool)]
            axs[0].scatter(g.flight_ground_mean_log1p_TPM_difference.iloc[0],j+offset,color=palette[pool],label=f'{pool}-trained head' if j==0 else None)
            for ax,model in [(axs[1],'bridge'),(axs[2],'expression')]:
                c=case[(case.model==model)&(case.program==prog['key'])&(case.training_pool==pool)&~case.renormalized]
                ax.plot([c.flight_ground_score_gap_removed.min(),c.flight_ground_score_gap_removed.max()],[j+offset]*2,color=palette[pool],lw=3)
                main=c[c.reference=='training_ground_mean_TPM'].iloc[0]
                ax.scatter(main.flight_ground_score_gap_removed,j+offset,color=palette[pool],s=30)
    for ax in axs:
        ax.axvline(0,color='#777',lw=1);ax.grid(axis='x',alpha=.15);ax.set_yticks(range(6));ax.invert_yaxis()
    axs[0].set_yticklabels(display);axs[1].set_yticklabels([]);axs[2].set_yticklabels([])
    axs[0].set_title('Observed expression difference');axs[0].set_xlabel('Flight − ground, mean log1p TPM');axs[0].legend(fontsize=8,loc='best')
    axs[1].set_title('BRIDGE: contribution to separation');axs[2].set_title('Expression baseline: contribution')
    for ax in axs[1:]:ax.set_xlabel('Flight–ground logit gap removed\nDots: ground reference; lines: two references')
    fig.suptitle('Six predefined response programs — one experiment, two donor pools\nPositive removal means the program supports flight/ground separation; panels use each classifier’s own score scale.',fontsize=11)
    fig.savefig(folder/'response_program_summary.png',dpi=180);fig.savefig(folder/'response_program_summary.pdf');plt.close(fig)
    # Fixed example: first held-out flight sample for the primary YA-trained head.
    sample=rows[(rows.training_pool=='YA')&(rows.label==1)&(rows.reference=='training_ground_mean_TPM')].iloc[0]
    ident=sample.id;sc=scores[(scores.id==ident)&(scores.reference==sample.reference)].iloc[0]
    exrows=per[(per.model=='bridge')&(per.id==ident)&(per.reference==sample.reference)&~per.renormalized]
    evidence=ev[(ev.model=='bridge')&(ev.id==ident)&(ev.reference==sample.reference)]
    allocations=pd.read_csv(folder/'evidence_allocation.csv');al=allocations[(allocations.model=='bridge')&(allocations.id==ident)&(allocations.reference==sample.reference)]
    extext=['# Example: flight prediction explained by response programs','',f'Sample `{ident}`; YA-trained fixed head, held-out OS chip. This example was fixed by order, not selected for its results.', '',f'Flight logit: **{sc.bridge_logit:.3f}** (uncalibrated). The response programs below are expression associations, not validated radiation or gravity detectors.','', '| Response program | Expression difference from training-ground reference | Change in flight logit when replaced | Matched-control absolute percentile |','|---|---:|---:|---:|']
    for pr in programs:
        ee=evidence[evidence.program==pr['key']].iloc[0];rr=exrows[exrows.program==pr['key']].iloc[0]
        extext.append(f"| {pr['label']} | {ee.mean_log1p_TPM_difference:+.3f} | {rr.logit_change:+.3f} | {100*rr.matched_random_abs_percentile:.0f}% |")
    outside=al[al.program=='outside_six_programs'].iloc[0]
    extext+=['','Positive logit change means replacing the program lowers the flight score: the observed program inputs support the prediction. Negative means they oppose it. Expression direction and model reliance are separate. Matched percentiles use only 20 controls; they are descriptive, not independent significance tests.','',f"**Unassigned evidence:** {outside.supporting_share_percent:.1f}% of positive attribution lies outside these six programs. Genes shared by programs are split equally for this accounting; the percentage is not a causal fraction.",'','Replacement effects overlap and do not sum to a complete decomposition. Radiation-versus-gravity specificity is **not established**. See the [full report](REPORT.md) for stability and limitations.']
    (folder/'EXAMPLE.md').write_text('\n'.join(extext)+'\n')
    verification={'perturbation_rows':len(p),'score_rows':len(scores),'max_prior_logit_error':float(scores.prior_logit_error.max()),'balanced_unique_design':True,'finite_scores':True,'expression_analytic_check_passed':True,'exact_matching_passed':bool(pd.read_csv(folder/'matching_checks.csv').exact_joint_bin_match.all()),'encoder_updated':False,'heads_updated':False}
    dump(folder/'verification.json',verification)
    run=json.loads((folder/'execution_report.json').read_text())
    report=['# Response-level explanation pilot','', '**Scope:** explain the biological-response programs associated with the existing GSE298393 flight classifier. Frozen BRIDGE and both fitted heads are unchanged. This is development evidence from 12 chips and two donor pools, not independent validation or exposure-cause identification.','', '[Figure](response_program_summary.pdf) · [Per-sample example](EXAMPLE.md) · [Protocol](protocol.json)','', '## Findings','', '| Program | Flight–ground expression difference, range across pools | Flight–ground logit gap removed, four cases | Same sign including renormalization? | Chip-deletion sign retention | Matched random absolute percentile range |','|---|---:|---:|---|---:|---:|']
    for r in syn.itertuples():
        report.append(f'| {r.response_label} | {r.expression_difference_min:+.3f} to {r.expression_difference_max:+.3f} | {r.replacement_gap_min:+.3f} to {r.replacement_gap_max:+.3f} | {r.same_sign_all_8_including_renormalization} | {100*r.leave_one_chip_sign_retention:.0f}% | {100*r.min_matched_random_abs_percentile:.0f}–{100*r.max_matched_random_abs_percentile:.0f}% |')
    report+=['','Positive removed gap means the program inputs support the flight/ground separation; negative means they suppress it. A program can increase in mean expression while suppressing the score, because the classifier weights individual genes differently. These gene-set scores do not measure functional pathway activation. All six programs are retained, including weak or opposing ones.','', '## What was tested','', 'Six Hallmark programs were fixed before this run (earlier pathway rankings had already been explored). Each complete measured program was replaced with each training-only reference in all 12 held-out chips. Twenty random panels matched each target’s exact joint training-expression mean/SD quintile counts, without replacement or target overlap. The same panels were reused across evaluation chips. Every target and random panel was tested both with and without TPM renormalization. No hyperparameters, genes or exposure labels were learned from this pilot.','', 'Reference replacement is an input sensitivity experiment, not a biological intervention. It can leave the expression manifold; TPM renormalization perturbs other genes too. Matched panels control size and coarse expression mean/SD, not gene correlation structure. This run does not establish statistical significance or causal effects.','', '## Interpretation and next step','', 'Use the stable response associations as model-reliance hypotheses, with genes as supporting evidence. A radiation or microgravity label requires controlled exposure comparisons and specificity against alternative stressors. Existing onboard-1g cohorts may help in their own cell contexts; they do not automatically validate this muscle-chip classifier. Unseen-flight transfer remains failed, and scores remain uncalibrated.','', 'Response expression, attributed evidence, and observed replacement effects are reported separately. Overlapping replacement effects must not be added as independent percentages. The allocation table splits shared genes equally and retains all evidence outside the six programs; this is a reporting convention. A future concept-based head is a separately evaluated model, not retrospective proof of what this one learned.','', '## Files and checks','', '- `program_evidence.csv`: per-chip response expression and signed attribution for BRIDGE and expression baseline.','- `per_sample_reliance.csv`: target replacement effects and matched-control percentiles.','- `program_reliance_contrasts.csv`: change in the flight–ground score gap by program, head, reference and normalization.','- `response_summary.csv`, `leave_one_chip.csv`, `reliance_leave_one_chip.csv`: stability, without treating chips as independent donors.','- `supporting_genes.csv`: genes beneath each response explanation.','- `program_overlap.csv`, `evidence_allocation.csv`: overlap and unassigned evidence.','- `verification.json`, `matching_checks.csv`, `execution_report.json`: numerical and run records.','', f"GPU: {run['device']}; {run['perturbation_passes']:,} replacement passes; {run['elapsed_seconds_this_invocation']/60:.1f} minutes this invocation; peak allocated memory {run['peak_memory_GB']:.2f} GB. Preparation and reporting ran locally. No encoder/head training occurred.",'', 'Sources: [public GEO study](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE298393); gene-set definitions reused from the previously archived `hallmark_2020.gmt`, whose hash is recorded in `input_provenance.json`.']
    (folder/'REPORT.md').write_text('\n'.join(report)+'\n')
    dump(folder/'STATUS.json',{'state':'complete','perturbations':6048,'verification_passed':True,'encoder_updated':False,'heads_updated':False})
    dump(folder/'report_provenance.json',{'report_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'outputs':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file() and p.name not in ['report_provenance.json']}})
    print(syn.to_string(index=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['local','final']);p.add_argument('--folder',type=Path,required=True);a=p.parse_args()
    if a.phase=='local':local(a.folder)
    else:final(a.folder)
