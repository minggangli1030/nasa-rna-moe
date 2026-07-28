#!/usr/bin/env python3
"""Render the compact Stage 2 additive-transfer result for the July 30 deck."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
INPUT = (
    ROOT
    / "artifacts"
    / "stage2_organ_expert_mechanism"
    / "additive_evaluation_be1a6f9"
    / "additive_edges.csv"
)
OUTPUT = ROOT / "presentation" / "2026-07-30-stage2-additive-effects.png"


def main() -> None:
    frame = pd.read_csv(INPUT)
    labels = [
        f"{recipient.replace('_', ' ')} \u2190 {donor.replace('_', ' ')}"
        for recipient, donor in zip(frame["recipient"], frame["donor"], strict=True)
    ]
    effects = frame["mean_effect_vs_a1500_percent"].to_numpy()
    lows = frame["donor_ci_low_vs_a1500_percent"].to_numpy()
    highs = frame["donor_ci_high_vs_a1500_percent"].to_numpy()
    positive_seeds = frame["positive_seed_count"].astype(int).to_numpy()
    robust = (positive_seeds == 3) & (lows > 0)

    colors = [
        "#176f5b" if is_robust else "#6da99b" if effect > 0 else "#b66058"
        for effect, is_robust in zip(effects, robust, strict=True)
    ]

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.titleweight": "bold",
            "axes.edgecolor": "#d2d9d4",
            "xtick.color": "#58655f",
            "ytick.color": "#26332e",
        }
    )
    fig, ax = plt.subplots(figsize=(13, 7.3), dpi=180)
    fig.patch.set_facecolor("#f7f8f5")
    ax.set_facecolor("#ffffff")

    y = range(len(frame))
    ax.barh(y, effects, color=colors, height=0.56, zorder=2)
    ax.errorbar(
        effects,
        y,
        xerr=[effects - lows, highs - effects],
        fmt="none",
        ecolor="#26332e",
        elinewidth=1.3,
        capsize=3,
        zorder=3,
    )
    ax.axvline(0, color="#26332e", linewidth=1.0, zorder=1)
    ax.set_yticks(list(y), labels)
    ax.invert_yaxis()
    ax.set_xlim(-1.1, 3.35)
    ax.set_xlabel(
        "MSE reduction from adding B750 to A1500 (%) \u00b7 positive is better",
        fontsize=11,
    )
    ax.set_title(
        "Adding another organ helps selectively\u2014but never beats more recipient data",
        loc="left",
        fontsize=19,
        pad=22,
        color="#15201d",
    )
    ax.text(
        0,
        1.015,
        "Held-out recipient donors \u00b7 mean of seeds 17, 42, 101 \u00b7 bars show paired donor-bootstrap 95% intervals",
        transform=ax.transAxes,
        fontsize=10.5,
        color="#5e6c67",
        va="bottom",
    )

    for row, (effect, seeds, low, high) in enumerate(
        zip(effects, positive_seeds, lows, highs, strict=True)
    ):
        ci_mark = "CI > 0" if low > 0 else "CI < 0" if high < 0 else "CI crosses 0"
        ax.text(
            2.18,
            row,
            f"{effect:+.2f}%  \u00b7  {seeds}/3 +  \u00b7  {ci_mark}",
            va="center",
            ha="left",
            fontsize=9.5,
            color="#17352d" if robust[row] else "#4b5853",
            fontweight="bold" if robust[row] else "normal",
        )

    ax.text(
        0.0,
        -0.14,
        "Robust positive edge: liver \u2190 skin only (3/3 seeds; CI above zero).   "
        "0/8 named donors beat A2250 in all seeds.",
        transform=ax.transAxes,
        fontsize=10.5,
        color="#174f49",
        fontweight="bold",
    )
    ax.text(
        0.0,
        -0.205,
        "Development-only GTEx evidence: seed/donor robustness is not study universality.",
        transform=ax.transAxes,
        fontsize=9.5,
        color="#6a756f",
    )
    ax.grid(axis="x", color="#e5eae6", linewidth=0.8, zorder=0)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0, labelsize=10.5)
    ax.tick_params(axis="x", labelsize=9.5)
    plt.subplots_adjust(left=0.20, right=0.97, top=0.84, bottom=0.22)
    fig.savefig(OUTPUT, bbox_inches="tight", facecolor=fig.get_facecolor())


if __name__ == "__main__":
    main()
