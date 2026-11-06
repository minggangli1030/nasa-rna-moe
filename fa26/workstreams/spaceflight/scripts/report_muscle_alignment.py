"""Summarize paired muscle controls and geometry-dependent fixed-head alignment."""
from pathlib import Path
import argparse,json,itertools
import numpy as np,pandas as pd,joblib
from controlled_exposure_pilot import sha,dump,samples
from muscle_response_alignment import effective
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def run(root,out,prior):
    m=pd.read_csv(out/'manifest.csv');sc=pd.read_csv(out/'sample_scores.csv');sh=pd.read_csv(out/'within_context_shifts.csv');pr=pd.read_csv(out/'projection_components.csv');ps=pd.read_csv(out/'projection_contrast_summary.csv');st=pd.read_csv(out/'probe_training_source_sensitivity.csv');pg=pd.read_csv(out/'program_expression_shifts.csv');d=np.load(out/'inputs.npz');e=np.load(out/'embeddings.npz');z=np.c_[e['mean'],e['std']].astype(float);ir=json.loads((out/'inference_report.json').read_text());assert sha(out/'inputs.npz')==ir['input_sha256'];assert ir['checkpoint_sha256']=='f3491beaa697a0408dc1daeb6f8d648566bd46bafc6e44938d723e7ffc325541'
    assert np.isfinite(z).all() and len(m)==76 and m.biological_id.nunique()==38
    # Independently check donor pairing and native metadata, then each stored group difference.
    sm={s['gsm']:s for s in samples(out/'sources/GSE200335_family.soft.gz')};eps=m[(m.study=='GSE200335')&(m.route=='harmonized')]
    for donor,g in eps.groupby('donor'):
        assert len(g)==2 and set(g.label)=={0,1}
        for _,r in g.iterrows():
            c=dict(v.split(': ',1) for v in sm[r['sample']]['characteristics_ch1']);assert (c['treatment']=='electrical pulse stimulation')==bool(r.label);assert sm[r['sample']]['title'][0].split('-')[0]==donor
    for _,r in sh.iterrows():
        g=sc[(sc.study==r.study)&(sc.group==r.group)&(sc.route==r.route)&(sc['head']==r['head'])];delta=g[g.label==1].score.mean()-g[g.label==0].score.mean();assert np.isclose(delta,r.treated_minus_control)
    assert np.allclose(pr.projected_component+pr.residual_component,pr.flight_score_delta)
    assert not ((pr.study=='GSE298393')&(pr.group==pr.flight_training_pool)).any()
    for source in ['ncbi','original']:
        head=joblib.load(prior/'heads'/f'{source}__bridge__ir_control__absolute.joblib');g=sc[sc['head']=='probe_'+source].set_index('id').loc[m.id];assert np.allclose(head.decision_function(z),g.score,rtol=1e-9,atol=1e-9)
    primary=sh[(sh.route=='harmonized')&(sh['head']=='probe_ncbi')];f=primary[primary.study!='GSE200335'];ep=primary[primary.study=='GSE200335'].sort_values('group')
    assert (ep.treated_minus_control>0).sum()==6
    donor=[]
    for (head,route),g in sh[sh.study=='GSE200335'].groupby(['head','route']):
        vals=g.treated_minus_control.to_numpy();loo=[np.delete(vals,i).mean() for i in range(len(vals))];donor.append({'head':head,'route':route,'n_donors':len(vals),'positive_shifts':int((vals>0).sum()),'mean_shift':float(vals.mean()),'median_shift':float(np.median(vals)),'leave_one_donor_mean_min':float(min(loo)),'leave_one_donor_mean_max':float(max(loo))})
    pd.DataFrame(donor).to_csv(out/'donor_summary.csv',index=False)
    program=[]
    for name,g in pg[(pg.study=='GSE200335')&(pg.route=='harmonized')].groupby('program'):
        vals=g.mean_log1p_shift.to_numpy();program.append({'program':name,'positive_donors':int((vals>0).sum()),'rank_positive_donors':int((g.rank_shift>0).sum()),'mean_log1p_shift':float(vals.mean()),'leave_one_donor_mean_min':float(min(np.delete(vals,i).mean() for i in range(7))),'leave_one_donor_mean_max':float(max(np.delete(vals,i).mean() for i in range(7)))})
    pd.DataFrame(program).to_csv(out/'program_donor_summary.csv',index=False)
    # Every source-deletion result retains primary direction; no favorable file chosen.
    merged=st.merge(primary[['study','group','treated_minus_control']],on=['study','group']);assert (np.sign(merged.probe_shift)==np.sign(merged.treated_minus_control)).all()
    wider=sh[(sh.study=='GSE200335')&(sh['head']=='probe_ncbi')].pivot(index='group',columns='route',values='treated_minus_control');assert (np.sign(wider.harmonized)==np.sign(wider.wider_gene_mask)).all()
    # Alternative probe routes and the original/harmonized flight expression routes keep each flight direction.
    flight=sh[(sh.study!='GSE200335')&sh['head'].str.startswith('probe_')]
    assert flight.groupby(['study','group']).treated_minus_control.apply(lambda x:len(set(np.sign(x)))==1).all()
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,ax=plt.subplots(1,3,figsize=(15,5),constrained_layout=True)
    colors=['#cc7859' if x<0 else '#167d8d' for x in ep.treated_minus_control]
    ax[0].barh(range(7),ep.treated_minus_control,color=colors);ax[0].axvline(0,color='#888');ax[0].set(yticks=range(7),yticklabels=ep.group.tolist(),xlabel='EPS − control: irradiation-probe logit',title='Non-radiation muscle stimulation')
    for i,row in enumerate(ep.itertuples()):
        ss=st[(st.study=='GSE200335')&(st.group==row.group)].probe_shift;ax[0].plot([ss.min(),ss.max()],[i,i],color='#222',lw=2)
    ax[0].text(.02,-.22,'6/7 donor shifts increase; black lines show\nremoving each radiation-training file.',transform=ax[0].transAxes,fontsize=9)
    labels=[]
    for i,row in enumerate(f.sort_values(['study','group']).itertuples()):
        ax[1].barh(i,row.treated_minus_control,color='#167d8d' if row.treated_minus_control>0 else '#cc7859');ss=st[(st.study==row.study)&(st.group==row.group)].probe_shift;ax[1].plot([ss.min(),ss.max()],[i,i],color='#222',lw=2);labels.append(row.study+' / '+row.group)
    ax[1].axvline(0,color='#888');ax[1].set(yticks=range(4),yticklabels=labels,xlabel='Flight − ground: irradiation-probe logit',title='Probe direction reverses across flights')
    ax[1].text(.02,-.22,'Both donor pools agree within each flight.\nPreviously explored data; not new replication.',transform=ax[1].transAxes,fontsize=9)
    vv=ps[(ps.study=='GSE298393')&(ps.route=='harmonized')]
    for i,pool in enumerate(['YA','OS']):
        g=vv[vv.group==pool];ax[2].scatter(g.projected_gap,np.full(len(g),i)+np.linspace(-.10,.10,len(g)),s=45,color='#167d8d');ax[2].scatter(g.score_gap.iloc[0],i,marker='D',s=60,color='#666',label='Full flight-score gap' if i==0 else None)
    ax[2].axvline(0,color='#aaa');ax[2].set(yticks=[0,1],yticklabels=['YA test / OS head','OS test / YA head'],xlabel='Flight − ground: flight-head logit',title='Lower probe component supports flight');ax[2].legend(loc='center right',fontsize=9)
    ax[2].text(.02,-.22,'Teal: projection across 2 probes × 2 metrics.\nAlgebraic component, not a causal percentage.',transform=ax[2].transAxes,fontsize=9)
    fig.suptitle('Human muscle follow-up: exposure recognition and flight-head reliance are different\n14 new samples / 7 paired donors; frozen encoder and flight heads',fontsize=12)
    for ext in ['png','pdf']:fig.savefig(out/f'muscle_alignment.{ext}',dpi=180)
    plt.close(fig)
    report='''# Human muscle response alignment — September 15, 2026

**Verdict: the irradiation-associated probe is not a radiation-specific explanation of the working flight classifier.** In human muscle, it responds to non-radiation electrical stimulation, and its flight/ground direction reverses between the two missions. In the working GSE298393 classifier, a *lower* irradiation-probe component supports the flight score. This is a useful model diagnostic, not evidence of less biological radiation damage.

## New tissue-matched negative control

[GSE200335](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE200335) provides primary human skeletal muscle cells from **seven donors**, with each donor's electrically stimulated culture compared with its unstimulated control (14 samples). The GEO protocol specifies 24h EPS. It is an exercise-like perturbation, not ionizing radiation or spaceflight. All seven donor pairs and treatment labels were checked against primary GEO metadata. All 14 samples occur in the supplied encoder catalog (13 train, 1 val), so this is a new challenge for the fixed heads, not fully unseen-encoder confirmation.

The fixed common-count irradiation probe:

- Scores **all 14 samples positive**, including all seven unstimulated controls. Its absolute threshold is therefore unsuitable in this muscle context.
- Increases after EPS in **6/7 donors**. Those donor-specific signs survive deleting every whole radiation-training source file, switching probe training preprocessing, and using a wider gene mask. The one decreasing donor remains decreasing.
- Thus exhibits both a muscle-context baseline shift and a reproducible non-radiation treatment response. The former must not be mistaken for an EPS-induced response; the paired comparison establishes the latter.

The two unchanged muscle flight heads decrease after EPS in the same six donors and increase in the remaining donor. Their absolute calls also vary strongly by donor/head, so EPS samples are not a validated flight-classification test. This negative-control result argues against interpreting either head's sigmoid as an exposure probability.

## Actual flight samples: response direction reverses

Primary common-count probe on matched-coverage, harmonized inputs; numbers are mean flight-minus-ground probe logits:

| Study | YA pool | OS pool |
|---|---:|---:|
| GSE234465, earlier flight | +1.613 | +2.309 |
| GSE298393, working-head flight | −2.315 | −3.391 |

Both processing routes, both probe-source versions and the original-versus-matched gene masks retain these signs. Removing any whole radiation-training expression file also retains all four signs. No study or pool was selected based on the preferred direction. These are the previously studied 24 chips from two pooled donor groups, not 24 independent donors or new confirmation of a general flight signature.

For the common-count probe, all 12 GSE298393 samples—including all six ground controls—are above its irradiation threshold. The original-processing probe calls all 12 negative. Both nevertheless agree that flight reduces the score relative to matched ground. **Absolute calls and within-context response directions answer different questions.**

## What the flight classifier actually does with this direction

We used a declared geometric diagnostic: remove the component along the fixed irradiation-probe normal relative to the flight head's training-pool ground reference, and measure the resulting change in the unchanged flight head. The test pool is always opposite the training pool for GSE298393. The projection is tested in both raw embedding coordinates and coordinates scaled using radiation training data; both original/common-count probes are retained.

Across all eight head/probe/metric combinations, increasing the irradiation-probe direction reduces the flight score. Because GSE298393 flight samples move in the opposite direction, this component **adds** to their flight-minus-ground separation:

| Held-out pool | Total flight-score gap | Projected component across probes/metrics |
|---|---:|---:|
| YA, OS-trained head | +10.085 | +0.485 to +1.557 |
| OS, YA-trained head | +12.160 | +0.591 to +1.226 |

The remaining score gap is kept as residual evidence. Each projected component plus residual exactly reconstructs the fixed score difference. The projected embedding's probe score returns to the reference score, and its flight-logit change matches the algebraic component.

This is **a property of the chosen latent-space operation**, not a validated biological intervention. The component's magnitude varies with metric and probe; it is not a unique explanation or a percentage caused by radiation. The removed coordinate can encode shared muscle/stress biology. We therefore report the signed result as “lower irradiation-associated probe component supports the score,” with its specificity failure visible, rather than calling the sample “radiation-driven.”

## Response-level lead from the new control study

Using the previously fixed six-program vocabulary, TNF/NF-kB-associated expression increases after EPS in **all seven donors**, agreeing under both mean log1p-expression and within-sample rank scoring. Myogenesis-associated expression decreases in **six of seven donors**, also agreeing under rank scoring. These are candidate transcriptional response patterns in an exercise-like intervention, not functional pathway-activity measurements or radiation-specific signatures.

Other programs are less consistent across scoring methods. All six are retained in `program_expression_shifts.csv` and `program_donor_summary.csv`. In particular, no new general flight inflammatory-response claim follows from this EPS result: the flight/pool response directions are mixed. The previous program-replacement evidence for the flight head remains the relevant model-reliance test (run05).

## Data search and scope

No clean human skeletal-muscle irradiation RNA-seq cohort was verified in this targeted search; that is not proof none exists. A public mouse 3D C2C12 candidate, **GSE318627**, includes irradiation, normal controls and unirradiated constructs co-cultured with senescent constructs. It could help distinguish direct exposure from shared downstream responses, but it has an n=2 versus n=3 metadata discrepancy, constructs sharing dishes, and unresolved timing/independence. It is documented, not silently substituted for human muscle or counted as independent validation. GSE171644 was excluded after primary GEO showed mouse rather than the human label in a secondary index. Full candidate decisions are in `candidate_audit.csv`.

## Decision and next step

Keep the 24h IMR90 irradiation-transfer finding from run07 as a narrow comparator. **Do not attach this probe as a named radiation contribution to the flight classifier.** The next usable explanation should expose transcriptional response evidence, its signed contribution to the flight model, consistency across controls and an explicit unexplained component. Exposure names require additional specificity evidence.

Prioritize a controlled human muscle radiation versus non-radiation stress dataset, with timing and controls comparable to the flight chips. The strongest immediate comparison now available is the seven-donor EPS negative control; it should be retained for every future response head. Controlled-gravity quantification remains separate. More encoder capacity is not the current remedy for unvalidated exposure meaning.

## Execution and artifacts

76 frozen-model encodings represent **38 biological samples**: 24 existing chips and 14 new EPS/control cultures; alternate preprocessing/masks are not extra samples. All primary inputs contain the same 15,061 observed genes as the radiation probe. The original flight mask had 15,137 genes; the EPS wider-mask sensitivity retained 15,132 verified mappings. Source/coverage changes preserve the main response directions.

Inference ran on moe-reboot's A100 in **26.9 seconds**. No encoder or flight-head update occurred. The four training-source-deletion probes were fitted only on prior irradiation data, never on muscle outcomes. All other scores use saved fixed heads. Projection and paired-donor analyses ran locally. The run is complete; no job remains queued.

[Summary figure](muscle_alignment.pdf) · [Protocol](protocol.json) · [Paired donor summary](donor_summary.csv) · [All sample scores](sample_scores.csv) · [Projection components](projection_components.csv) · [Coverage sensitivity](coverage_sensitivity.csv) · [Independent verification](independent_verification.json).
'''
    (out/'REPORT.md').write_text(report)
    dump(out/'independent_verification.json',{'sample_order_and_input_checkpoint_hashes_verified':True,'n_encodings':76,'n_biological_samples':38,'n_new_donor_pairs':7,'paired_labels_verified':True,'fixed_probe_predictions_reproduced':True,'group_shifts_recomputed':len(sh),'projection_sums_recomputed':len(pr),'opposite_pool_evaluation_verified':True,'all_primary_signs_retained_under_training_source_deletion':True,'EPS_primary_signs_retained_wider_mask':True,'all_flight_probe_signs_retained_processing_routes':True,'report_script_sha256':sha(Path(__file__))})
    dump(out/'STATUS.json',{'state':'complete','new_samples':14,'new_donors':7,'encoder_updated':False,'flight_heads_updated':False,'verdict':'Non-radiation muscle responses trigger probe; working flight classifier supported by lower probe component, not radiation-specific biology'})
    (out/'README.md').write_text('# Human muscle response alignment\n\n[Report](REPORT.md) · [Figure](muscle_alignment.pdf) · [Execution](EXECUTION.md).\n')
    print(pd.DataFrame(donor).to_string(index=False));print('Report and independent checks complete')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('fa26'));p.add_argument('--folder',type=Path,required=True);p.add_argument('--prior',type=Path,default=Path('fa26/workstreams/spaceflight/runs/07_radiation_robustness_audit_2026-09-15'));a=p.parse_args();run(a.root,a.folder,a.prior)
