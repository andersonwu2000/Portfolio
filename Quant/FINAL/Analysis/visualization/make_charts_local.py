"""Per-factor charts from LOCAL results (no GitHub fetch).

Reads each factor config's `results/_verify_<x>/` + `results/_robustness_<x>/` and
writes charts under `visualization/<factor>/` (01_nav, 02_drawdown, 03_yearly),
plus a cross-factor comparison under `visualization/_compare/`.

Run after: verify_strategy.py (per config) + analyze_robustness.py (per config).

Usage:  python visualization/make_charts_local.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent   # = Analysis/
VIZ = ROOT.parent / "Report" / "figures"         # rendered figures live with the report

plt.rcParams.update({
    "figure.facecolor": "#F8F9FA", "axes.facecolor": "#FFFFFF",
    "axes.grid": True, "grid.alpha": 0.35, "grid.linestyle": "--", "grid.color": "#CCCCCC",
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 10,
})
C = {
    "strategy": "#2ECC71", "top50": "#E67E22", "c0050": "#3498DB", "c0056": "#9B59B6",
    "momentum": "#E74C3C", "random_dark": "#7F8C8D", "random_fill": "#BDC3C7",
    "red_bar": "#E74C3C", "green_bar": "#27AE60",
}
FACTOR_COLORS = {"accel_top15": "#95A5A6", "accel_top50": "#E67E22",
                 "new_high_top50": "#2ECC71", "ensemble_top50": "#8E44AD"}

# factor key -> (verify dir, robustness dir, label)
CONFIGS = {
    "accel_top15":    ("_verify_accel15",    "_robustness_accel15",    "Accel top-15 (reference)"),
    "accel_top50":    ("_verify_accel50",    "_robustness_accel50",    "Accel top-50"),
    "new_high_top50": ("_verify_newhigh50",  "_robustness_newhigh50",  "New-high top-50 (best)"),
    "ensemble_top50": ("_verify_ensemble50", "_robustness_ensemble50", "Ensemble top-50"),
}


def _nav(path):
    return pd.read_csv(path, parse_dates=["date"]).set_index("date")["nav"]


def _navdf(path):
    return pd.read_csv(path, parse_dates=["date"]).set_index("date")


def drawdown(nav):
    return (nav - nav.cummax()) / nav.cummax()


def load(verify_dir: Path, robust_dir: Path) -> dict:
    b = verify_dir / "benchmarks"
    d = {
        "strat_net":   _nav(verify_dir / "strategy_nav_net.csv"),
        "strat_gross": _nav(verify_dir / "strategy_nav_gross.csv"),
        "mom_net":     _nav(verify_dir / "momentum_12_1_nav_net.csv"),
        "mom_gross":   _nav(verify_dir / "momentum_12_1_nav_gross.csv"),
        "etf_0050":    _nav(b / "0050.csv"),
        "top50_net":   _nav(b / "top50_eq_weight_net.csv"),
        "top50_gross": _nav(b / "top50_eq_weight_gross.csv"),
        "rand_net":    _navdf(b / "random_portfolios_net.csv"),
        "rand_gross":  _navdf(b / "random_portfolios_gross.csv"),
        "yearly":      pd.read_csv(robust_dir / "yearly.csv"),
        "robust":      json.loads((robust_dir / "summary.json").read_text(encoding="utf-8")),
    }
    return d


def chart_nav(d, label, out):
    fig, axes = plt.subplots(1, 2, figsize=(17, 7))
    fig.suptitle(f"NAV Curve 2018-2025 — {label}", fontsize=16, fontweight="bold")
    for ax, rand, strat, mom, t50, title in [
        (axes[0], d["rand_net"], d["strat_net"], d["mom_net"], d["top50_net"], "After Costs (NET)"),
        (axes[1], d["rand_gross"], d["strat_gross"], d["mom_gross"], d["top50_gross"], "No-Cost Signal (GROSS)"),
    ]:
        ax.fill_between(rand.index, rand["p5"], rand["p95"], alpha=0.12, color=C["random_fill"], label="Random p5-p95")
        ax.fill_between(rand.index, rand["p25"], rand["p75"], alpha=0.22, color=C["random_dark"], label="Random p25-p75")
        ax.plot(rand.index, rand["p50"], color=C["random_dark"], lw=1.2, ls="--", alpha=0.8, label="Random p50")
        ax.plot(d["etf_0050"].index, d["etf_0050"], color=C["c0050"], lw=1.6, label="0050 buy-hold")
        ax.plot(t50.index, t50, color=C["top50"], lw=1.6, ls="-.", label="Top 50 EW")
        ax.plot(mom.index, mom, color=C["momentum"], lw=1.2, ls=":", label="Momentum 12-1")
        ax.plot(strat.index, strat, color=C["strategy"], lw=2.5, label=label)
        ax.set_title(title, fontsize=12)
        ax.set_xlabel("Date"); ax.set_ylabel("NAV (start = 1.0)")
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.1f}x"))
        ax.legend(fontsize=8, loc="upper left")
    plt.tight_layout(); plt.savefig(out / "01_nav_curve.png", dpi=150, bbox_inches="tight"); plt.close()


def chart_drawdown(d, label, out):
    fig, ax = plt.subplots(figsize=(14, 6))
    fig.suptitle(f"Drawdown — Underwater Equity (NET) — {label}", fontsize=15, fontweight="bold")
    dd_s, dd_t = drawdown(d["strat_net"]) * 100, drawdown(d["top50_net"]) * 100
    dd_0, dd_m = drawdown(d["etf_0050"]) * 100, drawdown(d["mom_net"]) * 100
    ax.fill_between(dd_s.index, dd_s, 0, alpha=0.35, color=C["strategy"])
    ax.plot(dd_s.index, dd_s, color=C["strategy"], lw=1.8, label=f"{label} NET")
    ax.plot(dd_t.index, dd_t, color=C["top50"], lw=1.5, ls="-.", label="Top 50 EW NET")
    ax.plot(dd_0.index, dd_0, color=C["c0050"], lw=1.5, ls="--", label="0050 buy-hold")
    ax.plot(dd_m.index, dd_m, color=C["momentum"], lw=1.2, ls=":", alpha=0.7, label="Momentum 12-1 NET")
    mdd = d["robust"]["strategy_overall"].get("cagr")  # placeholder; use MDD from yearly min
    mdd_val = drawdown(d["strat_net"]).min() * 100
    ax.set_xlabel("Date"); ax.set_ylabel("Drawdown (%)")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.set_title(f"{label} max drawdown: {mdd_val:.1f}%", fontsize=10, color="#555")
    ax.legend(fontsize=9)
    plt.tight_layout(); plt.savefig(out / "02_drawdown.png", dpi=150, bbox_inches="tight"); plt.close()


def chart_yearly(d, label, out):
    yearly = d["yearly"]
    fig, axes = plt.subplots(3, 1, figsize=(12, 12), sharex=True)
    fig.suptitle(f"Yearly Walk-Forward — {label} (NET)", fontsize=15, fontweight="bold")
    years = yearly["year"].astype(int).tolist()
    x = np.arange(len(years)); w = 0.6
    rets = yearly["total_return"].values * 100
    ax = axes[0]
    bars = ax.bar(x, rets, width=w, color=[C["green_bar"] if r >= 0 else C["red_bar"] for r in rets],
                  edgecolor="white", linewidth=0.8)
    ax.axhline(0, color="black", lw=0.8)
    for b, v in zip(bars, rets):
        ax.text(b.get_x() + b.get_width()/2, b.get_height() + (1.2 if v >= 0 else -3.5),
                f"{v:+.1f}%", ha="center", va="bottom" if v >= 0 else "top", fontsize=9, fontweight="bold")
    ax.set_ylabel("Annual Return (%)"); ax.set_title("Annual Return")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    sharpes = yearly["sharpe"].values
    ax = axes[1]
    bars = ax.bar(x, sharpes, width=w, color=[C["green_bar"] if s >= 0 else C["red_bar"] for s in sharpes],
                  edgecolor="white", linewidth=0.8)
    ax.axhline(0, color="black", lw=0.8); ax.axhline(1.0, color="#AAA", lw=1, ls="--")
    for b, v in zip(bars, sharpes):
        ax.text(b.get_x() + b.get_width()/2, b.get_height() + (0.06 if v >= 0 else -0.18),
                f"{v:+.2f}", ha="center", va="bottom" if v >= 0 else "top", fontsize=9, fontweight="bold")
    ax.set_ylabel("Sharpe Ratio"); ax.set_title("Annual Sharpe Ratio")
    mdds = yearly["max_drawdown"].values * 100
    ax = axes[2]
    bars = ax.bar(x, mdds, width=w, color=C["red_bar"], alpha=0.75, edgecolor="white", linewidth=0.8)
    for b, v in zip(bars, mdds):
        ax.text(b.get_x() + b.get_width()/2, b.get_height() + 0.5, f"{v:.1f}%",
                ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.set_ylabel("Max Drawdown (%)"); ax.set_title("Annual Max Drawdown")
    ax.set_xticks(x); ax.set_xticklabels(years)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    plt.tight_layout(); plt.savefig(out / "03_yearly_performance.png", dpi=150, bbox_inches="tight"); plt.close()


def chart_compare(loaded, out):
    """Cross-factor: NET NAV overlay + Sharpe/CAGR bars."""
    fig, axes = plt.subplots(1, 2, figsize=(18, 7), gridspec_kw={"width_ratios": [2, 1]})
    fig.suptitle("Factor Comparison (NET, 2018-2025)", fontsize=16, fontweight="bold")
    ax = axes[0]
    # shared baselines from any config (use reference)
    ref = loaded["accel_top15"]
    ax.plot(ref["etf_0050"].index, ref["etf_0050"], color=C["c0050"], lw=1.4, ls="--", label="0050 buy-hold")
    ax.plot(ref["top50_net"].index, ref["top50_net"], color="#999", lw=1.2, ls="-.", label="Top 50 EW")
    for key, d in loaded.items():
        _, _, label = CONFIGS[key]
        ax.plot(d["strat_net"].index, d["strat_net"], color=FACTOR_COLORS[key], lw=2.2, label=label)
    ax.set_title("NET NAV"); ax.set_xlabel("Date"); ax.set_ylabel("NAV (start = 1.0)")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.1f}x"))
    ax.legend(fontsize=8, loc="upper left")
    # bars
    ax = axes[1]
    keys = list(loaded.keys())
    cagrs = [loaded[k]["robust"]["strategy_overall"]["cagr"] * 100 for k in keys]
    sharpes = [loaded[k]["robust"]["strategy_overall"]["sharpe"] for k in keys]
    xpos = np.arange(len(keys)); bw = 0.38
    ax.bar(xpos - bw/2, cagrs, bw, color="#3498DB", label="CAGR %")
    ax2 = ax.twinx()
    ax2.bar(xpos + bw/2, sharpes, bw, color="#2ECC71", label="Sharpe")
    ax.set_xticks(xpos); ax.set_xticklabels([CONFIGS[k][2].replace(" (", "\n(") for k in keys], fontsize=7)
    ax.set_ylabel("CAGR (%)", color="#3498DB"); ax2.set_ylabel("Sharpe", color="#2ECC71")
    ax.set_title("CAGR & Sharpe (NET)")
    for i, (c, s) in enumerate(zip(cagrs, sharpes)):
        ax.text(i - bw/2, c + 0.3, f"{c:.1f}", ha="center", fontsize=8, color="#2471A3")
        ax2.text(i + bw/2, s + 0.01, f"{s:.2f}", ha="center", fontsize=8, color="#1E8449")
    plt.tight_layout(); plt.savefig(out / "factor_comparison.png", dpi=150, bbox_inches="tight"); plt.close()


def main():
    loaded = {}
    for key, (vd, rd, label) in CONFIGS.items():
        verify_dir, robust_dir = ROOT / "results" / vd, ROOT / "results" / rd
        if not (verify_dir / "strategy_nav_net.csv").exists():
            print(f"SKIP {key}: missing {verify_dir}")
            continue
        d = load(verify_dir, robust_dir)
        loaded[key] = d
        out = VIZ / key
        out.mkdir(parents=True, exist_ok=True)
        chart_nav(d, label, out)
        chart_drawdown(d, label, out)
        chart_yearly(d, label, out)
        print(f"OK {key}: 3 charts -> {out}")
    if len(loaded) >= 2:
        cmp_out = VIZ / "_compare"
        cmp_out.mkdir(parents=True, exist_ok=True)
        chart_compare(loaded, cmp_out)
        print(f"OK comparison -> {cmp_out}")


if __name__ == "__main__":
    main()
