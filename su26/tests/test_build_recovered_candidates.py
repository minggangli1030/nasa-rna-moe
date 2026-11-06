"""Tests for the recovered-labels -> organ-candidates bridge."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evaluation"))

import build_recovered_candidates as brc  # noqa: E402


def _recovered(tmp_path):
    rows = [
        # high_confidence, two organs, distinct series
        ("GSM1", "GSE1", "liver", "high_confidence", "source_name", False),
        ("GSM2", "GSE1", "liver", "high_confidence", "source_name", False),
        ("GSM3", "GSE2", "brain", "high_confidence", "characteristics_tissue", False),
        # ambiguous -> excluded
        ("GSM4", "GSE3", "liver", "ambiguous", "title_only", False),
        # organ not requested -> excluded
        ("GSM5", "GSE4", "skin", "high_confidence", "source_name", False),
    ]
    meta = pd.DataFrame(rows, columns=[
        "geo_accession", "series_id", "organ", "tier", "evidence", "flag_tumor",
    ])
    meta["source_name_ch1"] = "src"
    meta["title"] = "t"
    meta["characteristics_ch1"] = "tissue: x"
    meta["singlecellprobability"] = 0.01
    path = tmp_path / "recovered.parquet"
    meta.to_parquet(path, index=False)
    return path


def test_selects_tier_and_organs(tmp_path):
    recovered = _recovered(tmp_path)
    args = brc.argparse.Namespace(
        recovered=str(recovered), tier="high_confidence",
        organs="liver,brain", output=str(tmp_path / "cand.parquet"),
    )
    report = brc.build(args)
    assert report["n_candidates"] == 3  # GSM1, GSM2, GSM3
    cand = pd.read_parquet(args.output)
    assert set(cand["organ"]) == {"liver", "brain"}
    # required candidate-schema columns present
    for col in ("sample_id", "organ", "series_group_id", "tumor_like"):
        assert col in cand.columns
    assert cand["tumor_like"].dtype == bool


def test_missing_organ_raises(tmp_path):
    recovered = _recovered(tmp_path)
    args = brc.argparse.Namespace(
        recovered=str(recovered), tier="high_confidence",
        organs="liver,pancreas", output=str(tmp_path / "cand.parquet"),
    )
    try:
        brc.build(args)
    except ValueError as exc:
        assert "pancreas" in str(exc)
    else:
        raise AssertionError("expected ValueError for absent organ")
