import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from review_pathway_onboard import metrics,renormalize


def test_single_outlying_sample_cannot_pass_pathway_robustness():
    genes=np.array([f'g{i}' for i in range(12)])
    panel=[{'name':'program','canonical_genes':genes[:10].tolist(),'genes':genes[:10].tolist()}]
    x=np.ones((6,12));x[-1,:10]=10;y=np.array([0,0,0,1,1,1])
    row=metrics(x,y,np.ones(12,bool),panel,genes)[0]
    assert row['zscore_shift']>0
    assert row['leave_one_sign_retention']<1 and not row['robust']


def test_source_sensitivity_uses_common_gene_denominator():
    counts=np.arange(1,79,dtype=float).reshape(6,13)
    other=counts.copy();other[:,-1]*=np.arange(1,7)*1000
    a=np.log1p(counts/counts.sum(1,keepdims=True)*1e6)
    b=np.log1p(other/other.sum(1,keepdims=True)*1e6)
    observed=np.array([True]*12+[False])
    np.testing.assert_allclose(renormalize(a,observed)[:,:12],renormalize(b,observed)[:,:12],atol=1e-12)


def test_too_little_pathway_coverage_is_explicitly_unpassed():
    genes=np.array([f'g{i}' for i in range(30)])
    panel=[{'name':'program','canonical_genes':genes.tolist(),'genes':genes.tolist()}]
    row=metrics(np.ones((6,30)),np.array([0,0,0,1,1,1]),np.array([True]*12+[False]*18),panel,genes)[0]
    assert row['status']=='insufficient_coverage' and not row['robust']
