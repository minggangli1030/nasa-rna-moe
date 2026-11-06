#!/usr/bin/env python3
"""Audit bundled references and checkpoint structure; never infer training provenance."""
import argparse
import hashlib
import json
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import torch


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def canonical_genes(path, expected=15165):
    frame = pd.read_csv(path).sort_values('token_id')
    if len(frame) != expected or not np.array_equal(frame.token_id, np.arange(1, expected + 1)):
        raise ValueError('Canonical token IDs must be contiguous 1-based IDs of the expected size')
    if frame.gene_symbol.isna().any() or frame.gene_symbol.duplicated().any():
        raise ValueError('Canonical symbols must be nonmissing and unique')
    return frame.gene_symbol.tolist()


def aligned_lengths(path, genes):
    frame = pd.read_csv(path)
    if frame.gene_symbol.duplicated().any():
        raise ValueError(f'Duplicate exon-length symbols: {path}')
    lengths = frame.set_index('gene_symbol').exon_length.reindex(genes).to_numpy(dtype=np.float64)
    if not np.isfinite(lengths).all() or (lengths <= 0).any():
        raise ValueError(f'Missing, nonfinite, or nonpositive exon lengths: {path}')
    return lengths


def log1p_tpm(counts, lengths):
    counts = np.asarray(counts, dtype=np.float64)
    lengths = np.asarray(lengths, dtype=np.float64)
    if counts.ndim != 2 or lengths.ndim != 1 or counts.shape[1] != len(lengths):
        raise ValueError('Expected sample-by-gene counts and one length per gene')
    if not np.isfinite(counts).all() or (counts < 0).any():
        raise ValueError('Counts must be finite and nonnegative')
    if not np.isfinite(lengths).all() or (lengths <= 0).any():
        raise ValueError('Lengths must be finite and positive')
    rate = counts / (lengths[None, :] / 1000.0)
    denominator = rate.sum(axis=1, keepdims=True)
    if not np.isfinite(denominator).all() or (denominator <= 0).any():
        raise ValueError('Each sample must have a positive finite canonical TPM denominator')
    return np.log1p(rate / denominator * 1e6).astype(np.float32)


def audit(root):
    paths = {
        'canonical': root / 'data/ensembl/canonical_genes.csv',
        'orthologs': root / 'data/ensembl/orthologs_one2one.txt',
        'human_lengths': root / 'data/gencode/gencode_v49_gene_exon_lengths.csv',
        'mouse_lengths': root / 'data/gencode/gencode_v49_mouse_gene_exon_lengths.csv',
        'config': root / 'model/r7hnr92k/config.json',
        'checkpoint': root / 'model/r7hnr92k/best_model.pt',
        'gtex': root / 'data/gtex/gtex_matrix.h5',
    }
    genes = canonical_genes(paths['canonical'])
    orthologs = pd.read_csv(paths['orthologs'], sep='\t')
    orthologs = orthologs[orthologs['Human gene name'].isin(genes)]
    pairs = orthologs[['Human gene name', 'Gene name']]
    if (len(pairs) != len(genes) or pairs.isna().any().any()
            or pairs['Human gene name'].duplicated().any() or pairs['Gene name'].duplicated().any()
            or set(pairs['Human gene name']) != set(genes)):
        raise ValueError('Canonical human/mouse mapping is incomplete or ambiguous')
    if not (orthologs['Human homology type'] == 'ortholog_one2one').all():
        raise ValueError('Expected one-to-one orthologs')
    human_lengths = aligned_lengths(paths['human_lengths'], genes)
    mouse_genes = pairs.set_index('Human gene name').loc[genes, 'Gene name'].tolist()
    aligned_lengths(paths['mouse_lengths'], mouse_genes)
    checkpoint = torch.load(paths['checkpoint'], map_location='cpu', weights_only=True)
    config = json.loads(paths['config'].read_text())
    state = checkpoint['model_state_dict']
    mismatches = [k for k, v in checkpoint['config'].items() if k not in config or config[k] != v]
    if mismatches:
        raise ValueError(f'Checkpoint/config mismatch: {mismatches}')
    if config['normalization'] != 'log1p_tpm':
        raise ValueError('Unsupported normalization')
    if tuple(state['gene_embedding.weight'].shape) != (len(genes), config['hidden_dim']):
        raise ValueError('Embedding dimensions disagree with canonical references/config')
    # State loading checks tensor layout, not equivalence to the original forward pass.
    from bridge_infer_gtex import BridgeRNA
    model = BridgeRNA()
    model.load_state_dict(state, strict=True)
    n_params = sum(p.numel() for p in model.parameters())
    if n_params != config['total_params'] or n_params != checkpoint['total_params']:
        raise ValueError('Parameter counts disagree')
    with h5py.File(paths['gtex'], 'r') as handle:
        source_genes = [s.decode() if isinstance(s, bytes) else str(s) for s in handle['meta/genes'][:]]
        missing = [g for g in genes if g not in set(source_genes)]
        shape = list(handle['data/expression'].shape)
        if shape != [len(handle['meta/sampid']), len(source_genes)]:
            raise ValueError('GTEx matrix does not match sample/gene metadata')
        duplicates = len(source_genes) - len(set(source_genes))
    # Check normalization arithmetic on synthetic counts only; not biological data.
    probe = log1p_tpm(np.ones((1, len(genes))), human_lengths)
    return {
        'status': 'blocked_before_inference',
        'checkpoint_run_id': config['run_id'],
        'checkpoint_epoch': checkpoint['epoch'],
        'canonical_gene_count': len(genes),
        'canonical_token_ids': '1..15165; file order sorted by token_id; tensor positions 0..15164',
        'canonical_symbols_alphabetical': genes == sorted(genes),
        'ortholog_pairs': len(pairs),
        'ortholog_confidence_counts': {str(k): int(v) for k, v in orthologs['Human orthology confidence [0 low, 1 high]'].value_counts().items()},
        'human_positive_length_coverage': len(genes),
        'mouse_positive_length_coverage': len(genes),
        'strict_state_dict_load': True,
        'parameter_count': n_params,
        'normalization': config['normalization'],
        'candidate_tpm_denominator': 'sum of count/(species-specific exon length in kb) over final canonical genes',
        'normalization_evidence': 'Matches su26/preprocessing/preprocessing.py _apply_final_normalization_once; latest training source not bundled',
        'synthetic_tpm_sum': float(np.expm1(probe.astype(np.float64)).sum()),
        'gtex_shape': shape,
        'gtex_exact_symbol_coverage': len(genes) - len(missing),
        'gtex_duplicate_symbols': duplicates,
        'gtex_missing_symbols': missing,
        'blockers': [
            f'GTEx lacks {len(missing)} exact canonical symbols; resolve via a versioned, unambiguous alias/stable-ID mapping and audit remaining absence before inference.',
            'Checkpoint does not embed the canonical gene list or its hash; bundled order is structurally consistent but its training provenance is unverified.',
            'Obtain checkpoint-matched model/preprocessing source to verify forward semantics, species lengths, and TPM denominator; tensor shapes and normalization label alone are insufficient.',
        ],
        'inputs': {key: {'path': str(path.relative_to(root)), 'sha256': sha256(path), 'bytes': path.stat().st_size} for key, path in paths.items()},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('gtex_missing_symbols', 'inputs')}, indent=2))


if __name__ == '__main__':
    main()
