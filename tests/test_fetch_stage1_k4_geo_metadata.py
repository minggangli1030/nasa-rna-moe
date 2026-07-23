import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))

from fetch_stage1_k4_geo_metadata import parse_series_soft, select_review_groups


def test_parse_series_soft_extracts_only_metadata():
    text = """^SERIES = GSE123
!Series_title = Healthy human brain RNA-seq
!Series_geo_accession = GSE123
!Series_status = Public on Jan 01 2024
!Series_pubmed_id = 12345678
!Series_summary = Bulk tissue from healthy controls
!Series_overall_design = Untreated brain samples
!Series_type = Expression profiling by high throughput sequencing
!Series_sample_id = GSM1
!Series_sample_id = GSM2
!Series_relation = BioProject: https://www.ncbi.nlm.nih.gov/bioproject/PRJNA123
!Series_supplementary_file = ftp://example.invalid/expression.tsv.gz
"""
    parsed = parse_series_soft(text, "GSE123")
    assert parsed["series_accession"] == "GSE123"
    assert parsed["pubmed_ids"] == "12345678"
    assert parsed["bioproject_ids"] == "PRJNA123"
    assert parsed["n_geo_samples"] == 2
    assert "supplementary" not in parsed


def test_select_review_groups_preserves_priority_order():
    rows = []
    for organ in ("adipose", "brain", "liver", "skeletal_muscle", "skin"):
        rows.extend([
            {"organ": organ, "series_tokens": f"GSE_{organ}_A",
             "automated_priority": "A"},
            {"organ": organ, "series_tokens": f"GSE_{organ}_B",
             "automated_priority": "B"},
            {"organ": organ, "series_tokens": f"GSE_{organ}_X",
             "automated_priority": "excluded_only"},
        ])
    selected = select_review_groups(pd.DataFrame(rows), per_organ=2)
    assert len(selected) == 10
    assert "excluded_only" not in set(selected["automated_priority"])
    assert selected.groupby("organ").size().eq(2).all()
