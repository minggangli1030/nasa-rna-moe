#!/usr/bin/env python3
"""Validate the frozen corrected 5k/20k result bundle before interpretation."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


FULL_ID_SHA256 = "84c607dd83f93964430877f572291836fddd7315dd4f7eae3bcbf12f70fc0d65"
STRICT_ID_SHA256 = "e52a695f5e518be24803dcb1fba266c7a67b7d4696520dba35466f5f38da2b18"


def _read(path: Path) -> dict:
    return json.loads(path.read_text())


def _require_finite(value, path="root"):
    if isinstance(value, dict):
        for key, child in value.items():
            _require_finite(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _require_finite(child, f"{path}[{index}]")
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"nonfinite result at {path}: {value}")


def validate(root: Path) -> dict:
    directories = {
        "full_5k": root / "interspecies_headroom_5k_v2_corrected",
        "full_20k": root / "interspecies_headroom_20k_v3_corrected",
        "strict_5k": root / "interspecies_headroom_5k_v2_strict_study_disjoint",
        "strict_20k": root / "interspecies_headroom_20k_v3_strict_study_disjoint",
    }
    reports = {name: _read(path / "report.json") for name, path in directories.items()}
    scales = {
        "full": _read(root / "interspecies_scale_change_full.json"),
        "strict": _read(root / "interspecies_scale_change_strict_study_disjoint.json"),
    }
    for name, payload in {**reports, **{f"scale_{k}": v for k, v in scales.items()}}.items():
        _require_finite(payload, name)

    expected_samples = {"full_5k": 667, "full_20k": 667, "strict_5k": 103, "strict_20k": 103}
    expected_labels = {
        "full_5k": "5k_v2_corrected",
        "full_20k": "20k_v3_corrected",
        "strict_5k": "5k_v2_strict_study_disjoint",
        "strict_20k": "20k_v3_strict_study_disjoint",
    }
    required_conditions = {
        "human", "mouse", "mixed", "fixed_blend_mse_crossfit",
        "metadata_species_soft_mse_crossfit", "hard_oracle_mse", "soft_oracle_mse",
        "training_gene_mean_global", "training_gene_mean_species",
    }
    for name, report in reports.items():
        if report["n_samples"] != expected_samples[name]:
            raise ValueError(f"{name} has {report['n_samples']} samples")
        if report["run_label"] != expected_labels[name]:
            raise ValueError(f"{name} has unexpected run label {report['run_label']!r}")
        if abs(report["mask_ratio"] - 0.30) > 1e-12:
            raise ValueError(f"{name} did not use the training-matched 30% mask")
        if report.get("group_column") != "series_group_id":
            raise ValueError(f"{name} did not use connected GEO-series groups")
        missing = required_conditions - set(report["conditions"])
        if missing:
            raise ValueError(f"{name} lacks required conditions: {sorted(missing)}")
        for comparison in report["comparisons"]:
            required_relative = {
                "candidate_mse_mean", "reference_mse_mean", "relative_mse_reduction"
            }
            absent = required_relative - set(comparison)
            if absent:
                raise ValueError(
                    f"{name} comparison {comparison['name']} lacks relative MSE fields: "
                    f"{sorted(absent)}"
                )
            reference_mse = float(comparison["reference_mse_mean"])
            if reference_mse <= 0:
                raise ValueError(f"{name} comparison {comparison['name']} has nonpositive MSE")
            expected_relative = (
                reference_mse - float(comparison["candidate_mse_mean"])
            ) / reference_mse
            if abs(expected_relative - float(comparison["relative_mse_reduction"])) > 1e-10:
                raise ValueError(
                    f"{name} comparison {comparison['name']} has inconsistent relative MSE"
                )

    for cohort in ("full", "strict"):
        five = reports[f"{cohort}_5k"]
        twenty = reports[f"{cohort}_20k"]
        for field in ("mask_sha256", "source_cache_mask_sha256", "n_masked_genes", "n_common_genes"):
            if five[field] != twenty[field]:
                raise ValueError(f"{cohort} 5k/20k differ in {field}")
    if reports["strict_5k"]["source_cache_mask_sha256"] != reports["full_5k"]["mask_sha256"]:
        raise ValueError("strict 5k report is not derived from the frozen full mask cache")
    if reports["strict_20k"]["source_cache_mask_sha256"] != reports["full_20k"]["mask_sha256"]:
        raise ValueError("strict 20k report is not derived from the frozen full mask cache")

    if scales["full"]["sample_id_sha256"] != FULL_ID_SHA256:
        raise ValueError("full paired comparison uses the wrong ordered cohort")
    if scales["strict"]["sample_id_sha256"] != STRICT_ID_SHA256:
        raise ValueError("strict paired comparison uses the wrong ordered cohort")
    if scales["full"]["mask_sha256"] != reports["full_5k"]["mask_sha256"]:
        raise ValueError("full scale report mask does not match model reports")
    if scales["strict"]["mask_sha256"] != reports["strict_5k"]["mask_sha256"]:
        raise ValueError("strict scale report mask does not match model reports")

    return {
        "status": "validated",
        "full_samples": 667,
        "strict_samples": 103,
        "n_common_genes": reports["full_5k"]["n_common_genes"],
        "n_masked_genes": reports["full_5k"]["n_masked_genes"],
        "full_mask_sha256": reports["full_5k"]["mask_sha256"],
        "strict_mask_sha256": reports["strict_5k"]["mask_sha256"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-root", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    summary = validate(Path(args.results_root))
    rendered = json.dumps(summary, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
