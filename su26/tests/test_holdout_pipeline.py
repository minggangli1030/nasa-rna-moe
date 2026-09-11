from __future__ import annotations

import ast
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evaluation"))

from attach_archs4_series import connected_series_groups  # noqa: E402
import audit_holdout_overlap  # noqa: E402
from audit_holdout_overlap import (  # noqa: E402
    main as audit_main,
    parquet_sample_ids,
    reproduce_split,
)
import compute_gene_mean as compute_gene_mean_module  # noqa: E402
from compute_gene_mean import compute_gene_mean  # noqa: E402


def _training_split_function():
    """Load only the three split helpers from train_single, avoiding training imports."""
    tree = ast.parse((ROOT / "core/train_single.py").read_text())
    wanted = {"_load_sample_species", "_read_parquet_index_ids", "build_single_parquet_split"}
    functions = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in wanted
    ]
    namespace = {"json": json, "np": np, "Path": Path, "pq": pq}
    exec(compile(ast.Module(body=functions, type_ignores=[]), "train_single_split", "exec"), namespace)
    return namespace["build_single_parquet_split"]


def test_reproduce_split_matches_training_implementation_and_index_priority():
    build_single_parquet_split = _training_split_function()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        path = root / "expression.parquet"
        sample_ids = [f"GSM{i:03d}" for i in range(14)]
        pq.write_table(pa.table({
            "sample_id": [f"WRONG{i:03d}" for i in range(14)],
            "__index_level_0__": sample_ids,
            "g1": np.arange(14, dtype=np.float32),
        }), path)
        species = {
            sample_id: ("human" if index % 2 == 0 else "mouse")
            for index, sample_id in enumerate(sample_ids)
        }
        samples_json = root / "samples.json"
        samples_json.write_text(json.dumps([
            {"id": sample_id, "species": species[sample_id]}
            for sample_id in sample_ids
        ]))

        assert parquet_sample_ids(path) == sample_ids
        for train_subset, val_subset, balanced in (
            (6, 4, True),
            (6, 4, False),
            (None, None, True),
        ):
            expected_train, expected_val = build_single_parquet_split(
                path,
                samples_json,
                train_subset=train_subset,
                val_subset=val_subset,
                balanced_sampling=balanced,
                seed=42,
                verbose=False,
            )
            actual_train, actual_val = reproduce_split(
                sample_ids,
                species,
                train_subset,
                val_subset,
                balanced,
                seed=42,
            )
            assert actual_train == [sample_ids[index] for index in expected_train]
            assert actual_val == [sample_ids[index] for index in expected_val]


def test_series_groups_are_transitive_and_empty_ids_fail():
    assert connected_series_groups(["GSE1 GSE2", "GSE3", "GSE2 GSE3", "GSE4"]) == [
        "GSE1|GSE2|GSE3",
        "GSE1|GSE2|GSE3",
        "GSE1|GSE2|GSE3",
        "GSE4",
    ]
    with unittest.TestCase().assertRaisesRegex(ValueError, "empty ARCHS4 series"):
        connected_series_groups(["GSE1", ""])


def test_gene_means_use_exact_training_rows_and_log1p_space():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        sample_ids = [f"GSM{i:03d}" for i in range(10)]
        values = np.column_stack([
            np.arange(10, dtype=np.float32),
            np.arange(10, dtype=np.float32) ** 2,
        ])
        parquet_path = root / "expression.parquet"
        table = pa.table({
            "geo_accession": sample_ids,
            "g1": values[:, 0],
            "g2": values[:, 1],
        })
        pq.write_table(table, parquet_path, row_group_size=3)

        human_ids, mouse_ids = sample_ids[::2], sample_ids[1::2]
        human_h5, mouse_h5 = root / "human.h5", root / "mouse.h5"
        species = {sample_id: "human" for sample_id in human_ids}
        species.update({sample_id: "mouse" for sample_id in mouse_ids})
        train_ids, val_ids = reproduce_split(sample_ids, species, 4, 2, True, seed=42)

        h5_maps = {
            human_h5: {sample_id: f"GSEH{i}" for i, sample_id in enumerate(human_ids)},
            mouse_h5: {sample_id: f"GSEM{i}" for i, sample_id in enumerate(mouse_ids)},
        }
        with mock.patch.object(
            compute_gene_mean_module,
            "load_archs4_series",
            side_effect=lambda path: h5_maps[Path(path)],
        ):
            genes, means, counts, split = compute_gene_mean(
                parquet_path,
                "tpm",
                train_subset=4,
                val_subset=2,
                balanced_sampling=True,
                human_h5=human_h5,
                mouse_h5=mouse_h5,
                seed=42,
            )

        train_rows = np.asarray([sample_ids.index(sample_id) for sample_id in train_ids])
        transformed = np.log1p(values)
        assert genes == ["g1", "g2"]
        np.testing.assert_allclose(means["global"], transformed[train_rows].mean(axis=0))
        assert counts["global"] == 4
        for species_name in ("human", "mouse"):
            species_rows = np.asarray([
                row for row in train_rows if species[sample_ids[row]] == species_name
            ])
            np.testing.assert_allclose(
                means[species_name], transformed[species_rows].mean(axis=0)
            )
            assert counts[species_name] == len(species_rows)
        assert split["n_val_rows_excluded"] == len(val_ids) == 2
        assert split["row_policy"] == "exact_train_rows_only"


def test_overlap_audit_uses_one_global_cross_species_series_union():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        human_h5, mouse_h5 = root / "human.h5", root / "mouse.h5"
        h5_maps = {
            human_h5: {
                "H_REF": "HUMAN_TRAIN",
                "H_DROP": "MOUSE_TRAIN",
                "H_KEEP": "HOLDOUT_H",
            },
            mouse_h5: {
                "M_REF": "MOUSE_TRAIN",
                "M_DROP": "HUMAN_TRAIN",
                "M_KEEP": "HOLDOUT_M",
            },
        }
        human_reference, mouse_reference = root / "human.parquet", root / "mouse.parquet"
        pq.write_table(pa.table({"geo_accession": ["H_REF"], "g": [1.0]}), human_reference)
        pq.write_table(pa.table({"geo_accession": ["M_REF"], "g": [1.0]}), mouse_reference)

        holdout_path = root / "holdout.parquet"
        pd.DataFrame({
            "sample_id": ["H_DROP", "H_KEEP", "M_DROP", "M_KEEP"],
            "species": ["human", "human", "mouse", "mouse"],
            "series_id": ["MOUSE_TRAIN", "HOLDOUT_H", "HUMAN_TRAIN", "HOLDOUT_M"],
            "series_group_id": ["MOUSE_TRAIN", "HOLDOUT_H", "HUMAN_TRAIN", "HOLDOUT_M"],
            "g": [1.0, 2.0, 3.0, 4.0],
        }).to_parquet(holdout_path, index=False)

        annotated = root / "nested" / "annotated.parquet"
        strict = root / "strict" / "strict.parquet"
        strict_ids = root / "ids" / "strict.txt"
        report = root / "reports" / "report.json"
        argv = [
            "audit_holdout_overlap.py",
            "--holdout", str(holdout_path),
            "--human-h5", str(human_h5),
            "--mouse-h5", str(mouse_h5),
            "--reference-split", f"human={human_reference},1,0,0",
            "--reference-split", f"mouse={mouse_reference},1,0,0",
            "--annotated-output", str(annotated),
            "--strict-output", str(strict),
            "--strict-ids-output", str(strict_ids),
            "--report", str(report),
        ]
        with (
            mock.patch.object(sys, "argv", argv),
            mock.patch.object(
                audit_holdout_overlap,
                "load_archs4_series",
                side_effect=lambda path: h5_maps[Path(path)],
            ),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            audit_main()

        strict_frame = pd.read_parquet(strict)
        assert strict_frame["sample_id"].tolist() == ["H_KEEP", "M_KEEP"]
        assert strict_ids.read_text().splitlines() == ["H_KEEP", "M_KEEP"]
        report_data = json.loads(report.read_text())
        assert report_data["reference_series_union"]["global"] == 2
        assert report_data["overlapping_samples_by_species"] == {"human": 1, "mouse": 1}


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            suite.addTest(unittest.FunctionTestCase(value))
    return suite
