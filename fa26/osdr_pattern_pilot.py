#!/usr/bin/env python3
"""Bounded descriptive liver survey; no model training or final validation claim."""
import argparse
import importlib.util
import itertools
import json
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd

from audit_bridge_contract import canonical_genes, aligned_lengths, log1p_tpm, sha256

STUDIES = {'OSD-48': ('RR1', '_C_', 5), 'OSD-379': ('RR8', '_ISS-T_YNG_', 6), 'OSD-463': ('RR23', None, 6)}
SOURCE_REVISION = 'ddf5e4bd1e48692dbc41caead413d6ca56154fca'


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')


def prepare(root, metadata_path, output):
    output.mkdir(parents=True, exist_ok=False)
    genes = canonical_genes(root / 'data/ensembl/canonical_genes.csv')
    official = root / 'upstream_embeddings'
    for name in ['data/ensembl/canonical_genes.csv', 'model/r7hnr92k/config.json']:
        if (root / name).read_bytes() != (official / name).read_bytes():
            raise ValueError(f'Official reference mismatch: {name}')
    metadata = pd.read_csv(metadata_path, low_memory=False)
    metadata['sample_id'] = metadata['id.sample name'].str.strip()
    if metadata[['id.accession', 'sample_id']].duplicated().any():
        raise ValueError('Duplicate normalized study/sample keys')
    candidates = metadata[metadata['id.accession'].isin(STUDIES)].copy()
    candidates['decision'] = 'outside_selected_subgroup_or_control'
    selected = []
    for study, (mission, subgroup, n) in STUDIES.items():
        d = candidates[candidates['id.accession'] == study].copy()
        d = d[d['study.factor value.spaceflight'].isin(['Space Flight', 'Ground Control'])]
        d = d[d['study.characteristics.material type'].str.contains('liver', case=False, na=False)]
        if subgroup:
            d = d[d.sample_id.str.contains(subgroup, regex=False)]
        # One measurement per animal; choose techrep1 when explicit technical replicates exist.
        d['animal_id'] = d.sample_id.str.replace(r'_techrep\d+$', '', regex=True)
        d = d.sort_values('sample_id').drop_duplicates('animal_id', keep='first')
        candidates.loc[d.index, 'decision'] = 'eligible_not_selected_by_fixed_cap'
        for label in ['Ground Control', 'Space Flight']:
            rows = d[d['study.factor value.spaceflight'] == label].sort_values('sample_id').head(n).copy()
            if len(rows) != n:
                raise ValueError(f'{study}: insufficient samples in {label}')
            rows['study'] = study
            rows['mission'] = mission
            rows['flight'] = int(label == 'Space Flight')
            selected.append(rows)
            candidates.loc[rows.index, 'decision'] = 'selected'
    manifest = pd.concat(selected).reset_index(drop=True)
    manifest['input_id'] = manifest.study + ':' + manifest.sample_id
    if manifest[['study', 'animal_id']].duplicated().any():
        raise ValueError('Repeated animal in selected manifest')
    manifest.to_csv(output / 'manifest.csv', index=False)
    candidates.to_csv(output / 'candidate_decisions.csv', index=False)
    protocol = {
        'purpose': 'exploratory within-liver pattern survey, development only',
        'source_revision': SOURCE_REVISION,
        'checkpoint': 'r7hnr92k; only checkpoint listed on inspected author embedding branch',
        'studies': STUDIES,
        'selection': 'Exact flight/ground labels, specified subgroup, lexicographic sample cap per condition, first explicit technical replicate only; fixed before expression comparison',
        'qc': 'Complete canonical gene measurement coverage; finite nonnegative counts; positive canonical TPM denominator; report nonzero genes and library size without adaptive sample removal',
        'normalization': 'mouse exon lengths; canonical 15165-gene TPM denominator; log1p once; no standardization before model',
        'embedding': 'official final layer, mean over genes, unmasked input, float32, frozen checkpoint',
        'analyses': 'study/condition variance fractions; within-study flight-ground centroid shifts and cross-study cosine; descriptive LOSO fixed logistic probe with raw, train-fit PCA8, and BridgeRNA; consistent gene differences',
        'probe': 'StandardScaler fitted per training split; LogisticRegression(C=1,class_weight=balanced,max_iter=2000,solver=liblinear); no hyperparameter selection',
        'limitations': ['Small study count', 'Sex, strain, preservation and library preparation differ across studies', 'Subject IDs inferred from sample names where explicit IDs absent', 'Cage structure unavailable; animal-level independence not fully verified', 'OSD-379 numeric age/duration unavailable in local catalog', 'Pretraining sample overlap not established', 'Old summer development datasets reused; no untouched confirmation'],
        'metadata_sha256': sha256(metadata_path),
        'manifest_sha256': sha256(output / 'manifest.csv'),
    }
    write_json(output / 'protocol.json', protocol)
    orthologs = pd.read_csv(root / 'data/ensembl/orthologs_one2one.txt', sep='\t')
    orthologs = orthologs[orthologs['Human gene name'].isin(genes)].set_index('Human gene name').loc[genes]
    if not orthologs['Gene stable ID'].is_unique:
        raise ValueError('Ambiguous canonical ortholog stable IDs')
    mouse_ids = orthologs['Gene stable ID'].tolist()
    lengths = aligned_lengths(root / 'data/gencode/gencode_v49_mouse_gene_exon_lengths.csv', orthologs['Gene name'])
    arrays = []
    reports = []
    qc_rows = []
    for study, rows in manifest.groupby('study', sort=False):
        filename = rows.counts_file.unique()
        if len(filename) != 1:
            raise ValueError('Multiple count files per study')
        path = root / 'data/osdr/raw' / filename[0]
        d = pd.read_csv(path, index_col=0)
        d.columns = d.columns.str.strip()
        d.index = d.index.astype(str).str.split('.').str[0]
        if not d.columns.is_unique:
            raise ValueError('Duplicate normalized count columns')
        d = d.groupby(level=0, sort=False).sum()
        missing = [g for g in mouse_ids if g not in d.index]
        if missing:
            raise ValueError(f'{study}: {len(missing)} structurally absent canonical genes')
        raw = d.loc[mouse_ids, rows.sample_id].T.to_numpy(dtype=np.float64)
        x = log1p_tpm(raw, lengths)
        arrays.append(x)
        for j, row in enumerate(rows.itertuples()):
            qc_rows.append({'input_id': row.input_id, 'study': study, 'flight': row.flight,
                            'canonical_nonzero': int((raw[j] > 0).sum()), 'canonical_counts': float(raw[j].sum()),
                            'all_counts': float(d[row.sample_id].sum()), 'input_min': float(x[j].min()), 'input_max': float(x[j].max())})
        reports.append({'study': study, 'count_file': filename[0], 'sha256': sha256(path), 'canonical_coverage': len(genes), 'samples': len(rows)})
    x = np.concatenate(arrays)
    # The groupby order follows the contiguous study blocks of the manifest.
    np.savez_compressed(output / 'inputs.npz', x=x, genes=np.asarray(genes), sample_ids=manifest.input_id.to_numpy(dtype=str), flight=manifest.flight.to_numpy(), study=manifest.study.to_numpy(dtype=str))
    pd.DataFrame(qc_rows).to_csv(output / 'sample_qc.csv', index=False)
    write_json(output / 'input_audit.json', {'studies': reports, 'reference_hashes': {str(p.relative_to(root)): sha256(p) for p in [root/'data/ensembl/canonical_genes.csv', root/'data/ensembl/orthologs_one2one.txt', root/'data/gencode/gencode_v49_mouse_gene_exon_lengths.csv']}, 'input_sha256': sha256(output/'inputs.npz')})
    print('Prepared', x.shape, flush=True)


def infer(root, output, checkpoint_path=None):
    import torch
    from bridge_infer_gtex import BridgeRNA
    torch.set_num_threads(4)
    torch.manual_seed(1701)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA unavailable')
    official_path = root / 'upstream_embeddings/src/fm_embed/inference_model.py'
    spec = importlib.util.spec_from_file_location('official_bridge', official_path)
    official = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(official)
    config = json.loads((root/'model/r7hnr92k/config.json').read_text())
    checkpoint_path = checkpoint_path or root/'model/r7hnr92k/best_model.pt'
    c = torch.load(checkpoint_path, map_location='cpu', weights_only=True)
    for k, v in c['config'].items():
        if config[k] != v:
            raise ValueError(f'Checkpoint configuration mismatch: {k}')
    model = official.ExpressionPerformer(num_genes=15165, hidden_dim=config['hidden_dim'], n_heads=config['num_heads'], n_layers=config['num_layers'], ffn_dim=config['ffn_dim'], ree_base=config['ree_base'], mask_token_id=config['mask_token'], feature_type=config['feature_type'], compute_type=config['compute_type'], include_species_embedding=config['include_species_embedding'], num_species=2)
    model.load_state_dict(c['model_state_dict'], strict=True)
    model.eval().to('cuda')
    candidate = BridgeRNA()
    candidate.load_state_dict(c['model_state_dict'], strict=True)
    candidate.eval().to('cuda')
    data = np.load(output/'inputs.npz')
    x = data['x']
    parity = []
    with torch.inference_mode():
        for masked in [False, True]:
            probe = torch.from_numpy(x[:1].copy()).to('cuda')
            if masked:
                probe[:, ::7] = -10
            expected = model(probe)
            actual, h = candidate(probe)
            torch.testing.assert_close(actual, expected, rtol=1e-5, atol=1e-5)
            torch.testing.assert_close(h.mean(1), model.encode(probe), rtol=1e-5, atol=1e-5)
            parity.append({'masked': masked, 'max_abs_error': float((actual-expected).abs().max())})
    del candidate, c, h, actual, expected, probe
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    embeddings = []
    times = []
    started = time.time()
    with torch.inference_mode():
        for i, row in enumerate(x):
            tick = time.time()
            t = torch.from_numpy(row[None]).to('cuda')
            emb = model.encode(t).float().cpu().numpy()
            if not np.isfinite(emb).all():
                raise ValueError('Nonfinite embedding')
            embeddings.append(emb[0])
            torch.cuda.synchronize()
            times.append(time.time()-tick)
            print(json.dumps({'completed': i+1, 'total': len(x), 'sample': str(data['sample_ids'][i]), 'seconds': times[-1]}), flush=True)
        repeated = model.encode(torch.from_numpy(x[:1]).to('cuda')).float().cpu().numpy()[0]
        np.testing.assert_allclose(repeated, embeddings[0], rtol=1e-5, atol=1e-5)
    embeddings = np.asarray(embeddings)
    if np.linalg.norm(embeddings.std(axis=0)) == 0:
        raise ValueError('Collapsed embeddings')
    np.savez_compressed(output/'embeddings.npz', embeddings=embeddings, sample_ids=data['sample_ids'])
    write_json(output/'inference_report.json', {'checkpoint_sha256':sha256(checkpoint_path), 'source_revision': SOURCE_REVISION, 'source_sha256':sha256(official_path), 'input_sha256':sha256(output/'inputs.npz'), 'candidate_parity':parity, 'repeat_max_abs_error':float(np.max(np.abs(repeated-embeddings[0]))), 'samples':len(x), 'shape':list(embeddings.shape), 'device':torch.cuda.get_device_name(), 'torch':torch.__version__, 'dtype':'float32', 'seconds':time.time()-started, 'median_seconds_per_sample':float(np.median(times)), 'peak_cuda_allocated_gib':torch.cuda.max_memory_allocated()/2**30})
    (output/'INFERENCE_COMPLETE').write_text('complete\n')


def analyze(output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from scipy.spatial.distance import pdist
    from scipy.stats import spearmanr
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score, balanced_accuracy_score
    data=np.load(output/'inputs.npz')
    em=np.load(output/'embeddings.npz')
    if not np.array_equal(data['sample_ids'], em['sample_ids']):
        raise ValueError('Embedding/sample misalignment')
    x=data['x'].astype(float); e=em['embeddings'].astype(float); y=data['flight']; groups=data['study']; studies=list(dict.fromkeys(groups))
    qc=pd.read_csv(output/'sample_qc.csv')
    if qc.input_id.tolist()!=data['sample_ids'].tolist():
        raise ValueError('QC/sample misalignment')
    reps={'Raw log1p(TPM)':x, 'PCA8 (descriptive fit)':PCA(n_components=8,svd_solver='full').fit_transform(x), 'BridgeRNA mean':e}
    geometry=[]; contrasts={}; cosine_rows=[]
    fig,axes=plt.subplots(2,3,figsize=(15,9),layout='constrained')
    for k,(name,z) in enumerate(reps.items()):
        centered=z-z.mean(0); total=float(np.square(centered).sum())
        within=z.copy(); study_ss=0.; cond_ss=0.; shifts=[]
        for study in studies:
            ix=groups==study; mean=z[ix].mean(0); within[ix]-=mean
            study_ss+=ix.sum()*np.square(mean-z.mean(0)).sum()
            shift=z[ix & (y==1)].mean(0)-z[ix & (y==0)].mean(0);shifts.append(shift)
            for label in [0,1]:
                idx=ix & (y==label);cond_ss+=idx.sum()*np.square(z[idx].mean(0)-mean).sum()
        contrasts[name]=np.asarray(shifts)
        coords=PCA(n_components=2).fit_transform(z)
        geom={'representation':name,'study_variance_fraction':study_ss/total,'within_study_condition_variance_fraction':cond_ss/total,'median_pair_distance':float(np.median(pdist(z))), 'pc1_log_count_spearman':float(spearmanr(coords[:,0],np.log1p(qc.all_counts)).statistic),'pc1_nonzero_spearman':float(spearmanr(coords[:,0],qc.canonical_nonzero).statistic)}
        geometry.append(geom)
        for a,b in itertools.combinations(range(len(studies)),2):
            v,w=shifts[a],shifts[b];cosine_rows.append({'representation':name,'study_a':studies[a],'study_b':studies[b],'flight_shift_cosine':float(v@w/(np.linalg.norm(v)*np.linalg.norm(w)))})
        for row,points in enumerate([coords,PCA(n_components=2).fit_transform(within)]):
            ax=axes[row,k]
            for si,study in enumerate(studies):
                for label,marker in [(0,'o'),(1,'^')]:
                    ix=(groups==study)&(y==label); ax.scatter(points[ix,0],points[ix,1],c=[f'C{si}'],marker=marker,s=55,alpha=.8,label=f'{study}: {"flight" if label else "ground"}')
            ax.set_title(name+('\nWithin-study centered' if row else '\nUncentered'));ax.set_xlabel('PC1');ax.set_ylabel('PC2');ax.spines[['top','right']].set_visible(False)
    axes[0,0].legend(fontsize=7)
    fig.suptitle('Exploratory liver survey — 34 animals, 3 studies\nColors = studies; triangles = flight. Plots are descriptive, not validation.',fontsize=14)
    fig.savefig(output/'pattern_overview.png',dpi=160);fig.savefig(output/'pattern_overview.pdf');plt.close(fig)
    pd.DataFrame(geometry).to_csv(output/'geometry.csv',index=False)
    pd.DataFrame(cosine_rows).to_csv(output/'response_cosines.csv',index=False)
    # Fold-fit transforms and a fixed probe; no tuning or selected seed.
    fold_rows=[]; predictions=[]
    for study in studies:
        train=groups!=study;test=~train
        pca=PCA(n_components=min(8,int(train.sum())-1),svd_solver='full').fit(x[train])
        sources={'Raw log1p(TPM)':(x[train],x[test]),'PCA8':(pca.transform(x[train]),pca.transform(x[test])),'BridgeRNA mean':(e[train],e[test])}
        for name,(tr,te) in sources.items():
            scaler=StandardScaler().fit(tr);model=LogisticRegression(C=1,class_weight='balanced',max_iter=2000,solver='liblinear',random_state=1701).fit(scaler.transform(tr),y[train]);prob=model.predict_proba(scaler.transform(te))[:,1]
            fold_rows.append({'held_out_study':study,'representation':name,'n_test':int(test.sum()),'auroc':roc_auc_score(y[test],prob),'balanced_accuracy':balanced_accuracy_score(y[test],prob>=.5)})
            for sid,label,p in zip(data['sample_ids'][test],y[test],prob):predictions.append({'sample_id':sid,'representation':name,'flight':int(label),'probability':float(p)})
    pd.DataFrame(fold_rows).to_csv(output/'study_held_out_probe.csv',index=False)
    pd.DataFrame(predictions).to_csv(output/'probe_predictions.csv',index=False)
    shifts=contrasts['Raw log1p(TPM)']; sign_agreement=np.all(shifts>0,axis=0)|np.all(shifts<0,axis=0)
    gene_table=pd.DataFrame({'gene':data['genes'],'direction_consistent_all_studies':sign_agreement,'min_abs_shift':np.min(np.abs(shifts),axis=0),'mean_shift':shifts.mean(0)})
    for i,study in enumerate(studies):gene_table[study+'_flight_minus_ground']=shifts[i]
    gene_table.sort_values(['direction_consistent_all_studies','min_abs_shift'],ascending=False).to_csv(output/'gene_shifts.csv',index=False)
    # Same-direction count alone is exploratory: the sign-null expectation is 25% for three independent symmetric contrasts.
    write_json(output/'analysis_summary.json', {'n_samples':len(x),'n_studies':len(studies),'geometry':geometry,'cosines':cosine_rows,'held_out_probe':fold_rows,'same_direction_genes':int(sign_agreement.sum()),'same_direction_fraction':float(sign_agreement.mean()),'status':'descriptive_development_survey_complete','caution':'No pathway significance, causal inference, new model advantage, or untouched generalization claim. Study, sex, strain, protocol, and pretraining overlap remain limitations.'})
    (output/'COMPLETE').write_text('complete\n')
    print(json.dumps({'geometry':geometry,'cosines':cosine_rows,'held_out_probe':fold_rows},indent=2))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=['prepare','infer','analyze']);p.add_argument('--root',type=Path,default=Path(__file__).parent/'bridge-rna-latest');p.add_argument('--metadata',type=Path,default=Path(__file__).parents[1]/'su26/data/osdr/metadata_new.csv');p.add_argument('--output',type=Path,required=True);p.add_argument('--checkpoint',type=Path);a=p.parse_args()
    if a.phase=='prepare':prepare(a.root,a.metadata,a.output)
    elif a.phase=='infer':infer(a.root,a.output,a.checkpoint)
    else:analyze(a.output)

if __name__=='__main__':main()
