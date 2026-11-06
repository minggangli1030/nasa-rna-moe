import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from analyze_general_survey import diagnostics


def test_paired_checks_do_not_confuse_subject_offsets_with_response():
    y=np.tile([0,1],4);units=np.repeat(['a','b','c','d'],2)
    z=np.array([[0.,0.],[1.,2.]]*4)
    offsets=np.repeat(np.array([[100,5],[-40,30],[2,-100],[80,200]]),2,axis=0)
    shift,a=diagnostics(z,y,units,True,np.random.default_rng(1),40)
    other,b=diagnostics(z+offsets,y,units,True,np.random.default_rng(1),40)
    np.testing.assert_allclose(shift,[1,2]);np.testing.assert_allclose(other,shift)
    assert a['split_positive_fraction']==b['split_positive_fraction']==1
    assert b['n_effective_units']==4
    assert a['n_balanced_splits']==b['n_balanced_splits']==6


def test_reversing_labels_reverses_response_not_stability():
    y=np.array([0,0,0,1,1,1]);z=np.array([[0,0],[.1,0],[0,.1],[4,5],[4.1,5],[4,5.1]])
    shift,a=diagnostics(z,y,np.arange(6),False,np.random.default_rng(3),40)
    reverse,b=diagnostics(z,1-y,np.arange(6),False,np.random.default_rng(3),40)
    np.testing.assert_allclose(reverse,-shift)
    assert a['split_positive_fraction']==b['split_positive_fraction']==1


def test_three_pairs_have_three_partitions_not_two_hundred_independent_resamples():
    y=np.tile([0,1],3);units=np.repeat(['a','b','c'],2)
    z=np.array([[0.,0.],[1.,0.],[0.,0.],[1.,0.],[0.,0.],[-3.,0.]])
    _,a=diagnostics(z,y,units,True,np.random.default_rng(3),200)
    _,b=diagnostics(z,y,units,True,np.random.default_rng(500),200)
    assert a['n_balanced_splits']==3
    assert a==b
    assert a['split_positive_fraction']==0
