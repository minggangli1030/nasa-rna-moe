import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_bridge_contract import canonical_genes, aligned_lengths, log1p_tpm


def test_tpm_uses_lengths_and_is_invariant_to_library_size():
    counts = np.array([[10, 20], [100, 200]])
    actual = log1p_tpm(counts, [1000, 2000])
    np.testing.assert_allclose(actual, np.log1p(np.full((2, 2), 500000)), rtol=1e-6)
    np.testing.assert_allclose(np.expm1(actual.astype(float)).sum(1), 1e6, rtol=1e-6)


@pytest.mark.parametrize('counts,lengths', [([[0, 0]], [1, 1]), ([[-1, 1]], [1, 1]),
    ([[float('nan'), 1]], [1, 1]), ([[1, 1]], [0, 1]), ([[1, 1]], [1]),
    ([[1, 1]], [float('inf'), 1])])
def test_invalid_normalization_inputs_fail(counts, lengths):
    with pytest.raises(ValueError):
        log1p_tpm(counts, lengths)


def test_canonical_order_follows_token_ids(tmp_path):
    path = tmp_path / 'genes.csv'
    path.write_text('token_id,gene_symbol\n2,B\n1,A\n')
    assert canonical_genes(path, expected=2) == ['A', 'B']
    path.write_text('token_id,gene_symbol\n1,A\n3,B\n')
    with pytest.raises(ValueError):
        canonical_genes(path, expected=2)
    path.write_text('token_id,gene_symbol\n1,A\n2,A\n')
    with pytest.raises(ValueError):
        canonical_genes(path, expected=2)


def test_lengths_cannot_silently_drop_duplicates_or_missing_genes(tmp_path):
    path = tmp_path / 'lengths.csv'
    path.write_text('gene_symbol,exon_length\nA,1000\nA,2000\n')
    with pytest.raises(ValueError):
        aligned_lengths(path, ['A'])
    path.write_text('gene_symbol,exon_length\nA,1000\n')
    with pytest.raises(ValueError):
        aligned_lengths(path, ['A', 'B'])


def test_inference_exports_unmasked_embeddings_in_bounded_batches(tmp_path, monkeypatch):
    import h5py
    import torch
    import bridge_infer_gtex as inference

    genes = [f'G{i}' for i in range(100)]
    raw = np.arange(1, 301).reshape(3, 100)
    h5_path = tmp_path / 'data/gtex/gtex_matrix.h5'
    h5_path.parent.mkdir(parents=True)
    with h5py.File(h5_path, 'w') as f:
        f['meta/genes'] = np.asarray(genes, dtype='S')
        f['meta/tissue'] = np.asarray(['Liver', '', 'Brain'], dtype='S')
        f['meta/sampid'] = np.asarray(['A', 'B', 'C'], dtype='S')
        f['data/expression'] = raw
    calls = []

    class FakeModel(torch.nn.Module):
        def load_state_dict(self, state, strict):
            assert strict
        def encode(self, x):
            calls.append(x.clone())
            return torch.stack([x, x * 2], dim=-1)
        def forward(self, x):
            return x, self.encode(x)

    monkeypatch.setattr(inference, 'canonical_genes', lambda path: genes)
    monkeypatch.setattr(inference, 'aligned_lengths', lambda path, genes: np.ones(100) * 1000)
    monkeypatch.setattr(inference, 'BridgeRNA', FakeModel)
    monkeypatch.setattr(inference, 'sha256', lambda path: 'test-only')
    monkeypatch.setattr(torch, 'load', lambda path, map_location, weights_only: {'model_state_dict': {}})
    output = tmp_path / 'embeddings.npz'
    monkeypatch.setattr(sys, 'argv', ['infer', '--root', str(tmp_path), '--output', str(output), '--device', 'cpu', '--batch-size', '1'])
    inference.main()
    expected = log1p_tpm(raw[[0, 2]], np.ones(100) * 1000).mean(1)
    with np.load(output) as result:
        np.testing.assert_allclose(result['embeddings'], np.stack([expected, expected * 2], axis=1), rtol=1e-6)
        assert result['sample_ids'].tolist() == ['A', 'C']
    assert all(len(call) == 1 for call in calls)
    assert all((call >= 0).all() for call in calls[::2])
    assert any((call == -10).any() for call in calls[1::2])
