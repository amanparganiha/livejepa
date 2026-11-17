"""Generate the two figures the 2026-08 results added, in the house style of
livejepa/run_eval.py:plot_pareto (Agg backend, same palette, dpi 130+).

  results_egoexo_rigor.png    paired (adaptive - uniform) per budget with 95%
                              bootstrap CIs -- the significance figure. Bars
                              clear of zero == significant; the reader sees the
                              margin grow as the budget shrinks.
  results_egoexo_ceiling.png  where every method sits between "decode nothing
                              useful" and the best-window upper bound -- the
                              headroom figure.

With a rigor run that includes the pooling-matched baseline (2026-11-17), both
figures add it: the paired figure plots adaptive - uniform+pool beside
adaptive - uniform, and the headroom figure adds uniform+pool and the
one-decode-per-take reference.

    python scripts/make_thesis_figures.py --rigor results_egoexo_rigor_pooled.json
"""
import argparse
import json
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

C_ADAPT, C_UNIF, C_ORACLE, C_CEIL = "#2c7fb8", "#888888", "#7fbc41", "#8c6bb1"
C_UPOOL, C_TAKE = "#e6550d", "#333333"


def fig_paired(rigor_path, out_png):
    """Paired adaptive-minus-baseline differences with 95% CIs, both metrics.

    Plots adaptive - uniform, and also adaptive - uniform_pool (the
    pooling-matched baseline) when the rigor run included it."""
    d = json.load(open(rigor_path))
    series = [("paired_adaptive_minus_uniform", "adaptive - uniform", C_ADAPT, "o-")]
    if "paired_adaptive_minus_uniform_pool" in d:
        series.append(("paired_adaptive_minus_uniform_pool",
                       "adaptive - uniform+pool", C_UPOOL, "^-"))

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), sharex=True)
    for ax, key, label in ((axes[0], "semantic", "semantic (SONAR cosine)"),
                           (axes[1], "cider", "per-take CIDEr-D")):
        ax.axhline(0, color="k", lw=1)
        any_ns = False
        for skey, slabel, color, fmt in series:
            rows = d[skey]
            hz = np.array([r["target_hz"] for r in rows], dtype=float)
            order = np.argsort(hz)
            m = np.array([rows[i][key]["mean_diff"] for i in order])
            lo = np.array([rows[i][key]["ci95"][0] for i in order])
            hi = np.array([rows[i][key]["ci95"][1] for i in order])
            sig = np.array([rows[i][key]["significant"] for i in order])
            x = hz[order]
            ax.errorbar(x, m, yerr=[m - lo, hi - m], fmt=fmt, color=color,
                        capsize=4, lw=1.8, ms=6, label=slabel)
            # hollow marker = not significant, so ns cells are visible at a glance
            if (~sig).any():
                ax.plot(x[~sig], m[~sig], "o", ms=9, mfc="white", mec="#c0392b",
                        mew=2, ls="none",
                        label=None if any_ns else "not significant")
                any_ns = True
        ax.set_xscale("log")
        ax.set_xlabel("target decoding frequency (Hz, log)")
        ax.set_ylabel(f"$\\Delta$ {label}")
        ax.set_title(label)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8, loc="upper right")
    fig.suptitle("Paired difference over 40 held-out EgoExo4D takes "
                 "(5,000 bootstrap resamples)", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(out_png, dpi=150)
    print("wrote", out_png)


def fig_ceiling(ceiling_path, oracle_path, out_png, hz=0.05, extra_path=None):
    """Horizontal bars: every reference against the best-window upper bound.

    `extra_path` (a rigor run that included uniform_pool / take_mean) adds the
    pooling-matched baseline and the one-decode-per-take reference, which show
    how much of this metric averaging alone earns."""
    ceil = json.load(open(ceiling_path))
    sources = [json.load(open(oracle_path))]
    if extra_path:
        sources.insert(0, json.load(open(extra_path)))

    def at(method):
        for src in sources:
            for row in src["results"].get(method, []):
                if abs(row["target_hz"] - hz) < 1e-9:
                    return row["semantic_mean"], row["semantic_ci95"]
        return None

    s = ceil["summary"]
    bars = [
        (f"uniform @{hz} Hz", at("uniform"), C_UNIF),
        ("dense (decode EVERY step, 2 Hz)", (s["dense"]["mean"], s["dense"]["ci95"]), C_UNIF),
        ("GT-boundary reference", at("oracle"), C_ORACLE),
        (f"adaptive @{hz} Hz", at("adaptive"), C_ADAPT),
        (f"uniform+pool @{hz} Hz", at("uniform_pool"), C_UPOOL),
        ("one decode per take (whole-take mean)", at("take_mean"), C_TAKE),
        ("best-frame ceiling", (s["frame"]["mean"], s["frame"]["ci95"]), C_CEIL),
        ("best-window ceiling (bound)", (s["window"]["mean"], s["window"]["ci95"]), C_CEIL),
    ]
    bars = [(lab, *v, col) for lab, v, col in bars if v is not None]
    top = s["window"]["mean"]

    fig, ax = plt.subplots(figsize=(8.6, 4.4))
    y = np.arange(len(bars))
    for i, (lab, m, ci, col) in enumerate(bars):
        ax.barh(i, m, color=col, alpha=0.85,
                xerr=[[m - ci[0]], [ci[1] - m]], capsize=4,
                error_kw=dict(ecolor="#333", lw=1.2))
        ax.text(ci[1] + 0.006, i, f"{m:.3f}  ({100 * m / top:.1f}%)",
                va="center", fontsize=9)          # clear of the CI whisker
    ax.axvline(top, color=C_CEIL, ls="--", lw=1.4, alpha=0.8)
    ax.set_yticks(y); ax.set_yticklabels([b[0] for b in bars], fontsize=9)
    ax.invert_yaxis()
    ax.set_xlim(0.5, max(b[2][1] for b in bars) + 0.075)
    ax.set_xlabel("semantic score  (cosine to GT caption, time-aligned)")
    ax.set_title("Semantic metric against its best-window bound\n"
                 "40 held-out EgoExo4D takes; dashed line = best-window ceiling",
                 fontsize=11)
    ax.grid(True, axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    print("wrote", out_png)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rigor", default="results_egoexo_rigor.json")
    ap.add_argument("--ceiling", default="results_egoexo_ceiling.json")
    ap.add_argument("--oracle", default="results_egoexo_rigor_oracle_fixed.json")
    ap.add_argument("--hz", type=float, default=0.05)
    args = ap.parse_args()
    for p in (args.rigor, args.ceiling, args.oracle):
        if not os.path.exists(p):
            print(f"ERROR: missing {p}"); sys.exit(1)
    fig_paired(args.rigor, "results_egoexo_rigor.png")
    fig_ceiling(args.ceiling, args.oracle, "results_egoexo_ceiling.png", args.hz,
                extra_path=args.rigor)


if __name__ == "__main__":
    main()
