#!/usr/bin/env python3
"""Append a decision-oriented corrected interspecies report to report.md."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

from validate_corrected_eval_outputs import validate


CONDITIONS = (
    "human",
    "mouse",
    "mixed",
    "fixed_blend_mse_crossfit",
    "metadata_species_soft_mse_crossfit",
    "soft_oracle_mse",
    "training_gene_mean_species",
)

LABELS = {
    "human": "Human expert",
    "mouse": "Mouse expert",
    "mixed": "Pooled mixed expert",
    "fixed_blend_mse_crossfit": "OOF fixed blend",
    "metadata_species_soft_mse_crossfit": "Metadata-species soft router",
    "soft_oracle_mse": "Per-sample soft MSE oracle",
    "training_gene_mean_species": "Species train-mean baseline",
}


def _read(path: Path) -> dict:
    return json.loads(path.read_text())


def _fmt(value, digits=4) -> str:
    return f"{float(value):.{digits}f}"


def _signed(value, digits=4) -> str:
    return f"{float(value):+.{digits}f}"


def _ci(values, digits=4) -> str:
    return f"[{_signed(values[0], digits)}, {_signed(values[1], digits)}]"


def _comparison(report: dict, name: str) -> dict:
    for row in report["comparisons"]:
        if row["name"] == name:
            return row
    raise KeyError(f"comparison {name!r} is missing")


def _scale_condition(scale: dict, condition: str) -> dict:
    for row in scale["direct_scale_change"]:
        if row["condition"] == condition:
            return row
    raise KeyError(f"scale condition {condition!r} is missing")


def _condition_table(report: dict) -> list[str]:
    lines = [
        "| Condition | Pearson* | Residual Pearson* | MSE* |",
        "|---|---:|---:|---:|",
    ]
    for condition in CONDITIONS:
        row = report["conditions"][condition]
        lines.append(
            f"| {LABELS[condition]} | "
            f"{_fmt(row['primary_pearson_study_macro'])} | "
            f"{_fmt(row.get('primary_residual_pearson_study_macro', 0.0))} | "
            f"{_fmt(row['primary_mse_study_macro'], 5)} |"
        )
    return lines


def _gain_line(label: str, row: dict) -> str:
    residual = ""
    if "residual_pearson_gain_mean" in row:
        residual = (
            f", residual Pearson {_signed(row['residual_pearson_gain_mean'])} "
            f"CI {_ci(row['residual_pearson_gain_ci95'])}"
        )
    return (
        f"- **{label}:** Pearson {_signed(row['pearson_gain_mean'])} "
        f"CI {_ci(row['pearson_gain_ci95'])}; MSE improvement "
        f"{_signed(row['mse_improvement_mean'], 5)} "
        f"CI {_ci(row['mse_improvement_ci95'], 5)}; relative MSE reduction "
        f"{float(row['relative_mse_reduction']):.1%}{residual}."
    )


def _positive_ci(row: dict, metric: str) -> bool:
    return float(row[metric][0]) > 0.0


def _diagnose_usefulness(strict_report: dict) -> str:
    metadata_vs_mixed = _comparison(strict_report, "species_soft_vs_pooled_mixed")
    metadata_vs_fixed = _comparison(strict_report, "species_soft_vs_fixed_blend")
    oracle_vs_fixed = _comparison(strict_report, "soft_mse_oracle_vs_fixed_blend")

    router_absolute_positive = _positive_ci(metadata_vs_fixed, "mse_improvement_ci95")
    router_relative = float(metadata_vs_fixed["relative_mse_reduction"])
    router_residual_positive = (
        "residual_pearson_gain_ci95" in metadata_vs_fixed
        and _positive_ci(metadata_vs_fixed, "residual_pearson_gain_ci95")
    )
    oracle_meaningful = (
        _positive_ci(oracle_vs_fixed, "mse_improvement_ci95")
        and float(oracle_vs_fixed["relative_mse_reduction"]) >= 0.03
    )
    pooled_positive = _positive_ci(metadata_vs_mixed, "mse_improvement_ci95")

    if router_absolute_positive and router_relative >= 0.05 and router_residual_positive:
        router_conclusion = (
            "**Practically convincing adaptive MoE ceiling:** on the strict 20k cohort, the "
            "metadata soft router beats the out-of-fold fixed blend by at least 5% relative MSE "
            "and has a positive residual-Pearson confidence-interval lower bound."
        )
    elif router_absolute_positive and router_relative >= 0.03:
        router_conclusion = (
            "**Promising adaptive MoE ceiling:** on the strict 20k cohort, the metadata soft "
            "router beats the out-of-fold fixed blend with a positive absolute-MSE confidence-"
            "interval lower bound and at least 3% relative MSE reduction."
        )
    elif router_absolute_positive:
        router_conclusion = (
            "The metadata soft router is statistically positive against the out-of-fold fixed "
            "blend, but its relative MSE reduction is below 3% and therefore practically small."
        )
    else:
        router_conclusion = (
            "The metadata soft router does not beat the out-of-fold fixed blend with a positive "
            "MSE confidence-interval lower bound, so the strict result does not establish usable "
            "adaptive MoE benefit."
        )

    if pooled_positive and not (router_absolute_positive and router_relative >= 0.03):
        pooled_conclusion = (
            " Its improvement over the one pooled `mixed` expert is an ensemble benefit, not "
            "evidence that adaptive routing adds value beyond a fixed ensemble."
        )
    else:
        pooled_conclusion = (
            " The metadata-soft versus pooled-`mixed` comparison remains a pooled-model control; "
            "it is not sufficient by itself to justify MoE."
        )

    if oracle_meaningful:
        oracle_conclusion = (
            " The per-sample soft oracle also exceeds the fixed blend by at least 3% relative "
            "MSE with a positive absolute-MSE interval, indicating a meaningful routing ceiling."
        )
    else:
        oracle_conclusion = (
            " The per-sample soft oracle does not clear both the positive-interval and 3% relative-"
            "MSE criteria, so meaningful routing ceiling is not established."
        )
    return router_conclusion + pooled_conclusion + oracle_conclusion


def render(results_root: Path) -> tuple[str, str]:
    validation = validate(results_root)
    paths = {
        "5k full": results_root / "interspecies_headroom_5k_v2_corrected" / "report.json",
        "20k full": results_root / "interspecies_headroom_20k_v3_corrected" / "report.json",
        "5k strict": results_root / "interspecies_headroom_5k_v2_strict_study_disjoint" / "report.json",
        "20k strict": results_root / "interspecies_headroom_20k_v3_strict_study_disjoint" / "report.json",
    }
    reports = {name: _read(path) for name, path in paths.items()}
    scales = {
        "full": _read(results_root / "interspecies_scale_change_full.json"),
        "strict": _read(results_root / "interspecies_scale_change_strict_study_disjoint.json"),
    }
    fingerprint = hashlib.sha256(
        "|".join(
            [validation["full_mask_sha256"], validation["strict_mask_sha256"]]
            + [reports[name]["checkpoint_info"][expert]["sha256"]
               for name in ("5k full", "20k full")
               for expert in ("human", "mouse", "mixed")]
        ).encode("ascii")
    ).hexdigest()
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")

    strict_20 = reports["20k strict"]
    metadata_vs_mixed = _comparison(strict_20, "species_soft_vs_pooled_mixed")
    metadata_vs_fixed = _comparison(strict_20, "species_soft_vs_fixed_blend")
    oracle_vs_fixed = _comparison(strict_20, "soft_mse_oracle_vs_fixed_blend")
    diagnosis = _diagnose_usefulness(strict_20)

    lines = [
        "",
        "---",
        "",
        f"<!-- corrected-interspecies-report:{fingerprint} -->",
        f"## Corrected Interspecies MoE Evaluation - {timestamp}",
        "",
        "> This append-only addendum supersedes the earlier balanced-ARCHS4 and gene-mean conclusions above. "
        "The historical text is retained for provenance, but its old headroom numbers used raw TPM in a "
        "log1p-TPM model, test-fitted blends, and a test-derived mean baseline.",
        "",
        "### Executive conclusion",
        "",
        diagnosis,
        "",
        "The result must still be interpreted with two design constraints: the metadata router receives "
        "the true species label and is an upper bound rather than a learned blind gate; and the pooled "
        "mixed model is not compute/data/parameter matched to a three-model ensemble. The mixed V3 run "
        "also used species-contiguous row-group ordering, so a weak pooled checkpoint cannot by itself "
        "establish method failure.",
        "",
        "### Frozen protocol",
        "",
        f"- Full held-out-sample diagnostic: 667 samples; strict study-disjoint sensitivity: 103 samples.",
        f"- Shared common space: {validation['n_common_genes']:,} genes; masked positions per sample: "
        f"{validation['n_masked_genes']:,} (training-matched 30%).",
        "- Primary estimand: species-balanced study-macro mean; uncertainty: paired study bootstrap.",
        "- Fixed blend and metadata routing weights are fitted out of fold with connected GEO-series groups.",
        "- Baselines use exact mixed-model training rows only, with separate human/mouse means.",
        "- The full cohort has study overlap with training and is diagnostic; the 103-sample strict cohort "
        "is the cleaner sensitivity analysis and has wider intervals.",
        "",
    ]

    for name in ("5k full", "20k full", "5k strict", "20k strict"):
        lines.extend([f"### {name.title()} results", "", *_condition_table(reports[name]), ""])
        for label, comparison_name in (
            ("OOF fixed blend vs pooled mixed", "fixed_blend_vs_pooled_mixed"),
            ("Metadata-species soft router vs pooled mixed", "species_soft_vs_pooled_mixed"),
            ("Metadata-species soft router vs OOF fixed blend", "species_soft_vs_fixed_blend"),
            ("Per-sample soft oracle vs OOF fixed blend", "soft_mse_oracle_vs_fixed_blend"),
        ):
            lines.append(_gain_line(label, _comparison(reports[name], comparison_name)))
        lines.append("")

    lines.extend(["### Paired scale effect: 20k minus 5k", ""])
    for cohort in ("full", "strict"):
        lines.append(f"**{cohort.title()} cohort**")
        for condition in ("human", "mouse", "mixed", "fixed_blend_mse_crossfit", "metadata_species_soft_mse_crossfit"):
            row = _scale_condition(scales[cohort], condition)
            pearson = row["pearson_20k_minus_5k"]
            mse = row["mse_5k_minus_20k"]
            lines.append(
                f"- {LABELS[condition]}: Pearson {_signed(pearson['mean'])} CI {_ci(pearson['ci95'])}; "
                f"MSE improvement {_signed(mse['mean'], 5)} CI {_ci(mse['ci95'], 5)}."
            )
        lines.append("")

    lines.extend([
        "### Diagnosis",
        "",
        _gain_line("20k strict metadata router vs pooled mixed", metadata_vs_mixed),
        _gain_line("20k strict metadata router vs fixed blend", metadata_vs_fixed),
        _gain_line("20k strict soft oracle vs fixed blend", oracle_vs_fixed),
        "",
        "These are frozen-expert ceiling measurements. No corrected blind learned gate is implemented "
        "in this overnight path; `train_moe.py` remains an older softmax proof of concept. A positive "
        "metadata comparison against pooled `mixed` alone is an ensemble result, while adaptive-routing "
        "evidence requires improvement over the out-of-fold fixed blend.",
        "",
        "### Recommended next work",
        "",
        "1. **Correct the mixed sampler and rerun the pooled control.** Shuffle batches globally across "
        "species, preserve the frozen holdouts, and reproduce this report before rejecting the method.",
        "2. **Add fair controls.** Compare against a pooled model trained on the union of specialist data "
        "and against parameter/inference-budget-matched single models; report ensemble cost explicitly.",
        "3. **Test a blind learned router only when the ceiling warrants it.** Train routing on calibration "
        "studies, never the final cohort, and evaluate on the strict grouped split. Compare with the true-"
        "species metadata ceiling to measure how much routable signal is learnable from expression alone.",
        "4. **Use profile-controlled endpoints.** Require paired improvement in MSE and residual Pearson, "
        "not raw across-gene Pearson alone, because static gene profiles can dominate that metric.",
        "5. **Then evaluate the human-organ hypothesis.** Build organ-disjoint specialists and a frozen "
        "organ-balanced holdout. First measure hard/soft oracle and true-organ metadata ceilings; proceed "
        "to an unknown-organ gate only if those ceilings clearly exceed the corrected species result.",
        "6. **Treat the strict cohort as uncertainty-limited.** Its 103 studies are clean but small; repeat "
        "the grouped sampling or build a larger prospective study-disjoint holdout before a definitive claim.",
        "",
        "### Reproducibility artifacts",
        "",
        f"- Result fingerprint: `{fingerprint}`",
        f"- Full mask SHA256: `{validation['full_mask_sha256']}`",
        f"- Strict mask SHA256: `{validation['strict_mask_sha256']}`",
        "- Validation artifact: `results/corrected_interspecies_eval.validation.json`",
        "- Scale reports: `results/interspecies_scale_change_full.json` and "
        "`results/interspecies_scale_change_strict_study_disjoint.json`",
        "",
    ])
    return "\n".join(lines), fingerprint


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-root", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    report_path = Path(args.report)
    rendered, fingerprint = render(Path(args.results_root))
    marker = f"<!-- corrected-interspecies-report:{fingerprint} -->"
    existing = report_path.read_text() if report_path.exists() else ""
    if marker in existing:
        print(f"[report] existing validated addendum found: {fingerprint}")
        return
    with report_path.open("a") as handle:
        handle.write(rendered)
        if not rendered.endswith("\n"):
            handle.write("\n")
    print(f"[report] appended validated addendum: {fingerprint}")


if __name__ == "__main__":
    main()
