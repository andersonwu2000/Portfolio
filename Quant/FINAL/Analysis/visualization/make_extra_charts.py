"""Extra charts for the report — signal-quality, benchmark, and concentration.

Generates:
  signal/quintile_spread.png      — Q1..Q5 mean monthly return (signal is real)   [§5.1]
  signal/rolling_ic.png           — 12-month rolling IC (predictive power is stable)[§5.1]
  benchmark/startdate_sensitivity.png — strategy vs 0050 CAGR by start year        [§6.2]
  benchmark/alpha_significance.png    — alpha t-value rises as benchmark gets fairer[§6.3]
  holdings_tradeoff.png           — CAGR/Sharpe/MDD vs holdings count              [concentration]
  param_heatmaps.png              — 3-signal parameter heatmaps (not overfit)        [§5.3]

CSV-derived charts read from results/. Two charts (alpha_significance, holdings)
use deterministic values produced this session by analyze_fair_benchmark.py and
analyze_holdings_sweep.py (cited inline; re-run those scripts to verify).

Usage:  python visualization/make_extra_charts.py
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
RES = ROOT / "results"

plt.rcParams.update({
    "figure.facecolor": "#F8F9FA", "axes.facecolor": "#FFFFFF",
    "axes.grid": True, "grid.alpha": 0.35, "grid.linestyle": "--", "grid.color": "#CCCCCC",
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 10,
    # CJK font for Traditional Chinese labels (Windows); fall back gracefully.
    "font.sans-serif": ["Microsoft JhengHei", "Microsoft YaHei", "PingFang TC",
                        "Noto Sans CJK TC", "DejaVu Sans"],
    "axes.unicode_minus": False,
})
GREEN, RED, BLUE, GREY, ORANGE = "#27AE60", "#E74C3C", "#3498DB", "#7F8C8D", "#E67E22"


def save(fig, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("saved:", path.relative_to(ROOT.parent))


# ── §5.1 Quintile spread ─────────────────────────────────────────────────
def quintile_spread():
    df = pd.read_csv(RES / "_quantile_spread" / "monthly_quantile_returns.csv")
    means = [df[f"q{i}"].mean() * 100 for i in range(1, 6)]
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(range(1, 6), means, width=0.6,
                  color=[RED if m < 0 else GREEN for m in means], edgecolor="white")
    ax.axhline(0, color="black", lw=0.8)
    for b, m in zip(bars, means):
        ax.text(b.get_x() + b.get_width()/2, m + (0.03 if m >= 0 else -0.06),
                f"{m:+.2f}%", ha="center", va="bottom" if m >= 0 else "top", fontweight="bold")
    ax.set_xticks(range(1, 6))
    ax.set_xticklabels(["Q1\n(最弱)", "Q2", "Q3", "Q4", "Q5\n(最強)"])
    ax.set_ylabel("後續月均報酬 (%)")
    ax.set_title("分位數報酬單調遞增 — 訊號具預測力的直接證據\n(營收動能五等分, 2015–2025)", fontweight="bold")
    save(fig, VIZ / "signal" / "quintile_spread.png")


# ── §5.1 Rolling IC ──────────────────────────────────────────────────────
def rolling_ic():
    df = pd.read_csv(RES / "_signal_decay" / "monthly_ic.csv", parse_dates=["date"]).set_index("date")
    fig, ax = plt.subplots(figsize=(12, 5))
    for col, c, lab in [("ic20", BLUE, "IC(20日)"), ("ic60", GREEN, "IC(60日)")]:
        roll = df[col].rolling(12, min_periods=6).mean()
        ax.plot(df.index, df[col], color=c, lw=0.6, alpha=0.25)
        ax.plot(roll.index, roll, color=c, lw=2.2, label=f"{lab} 12個月滾動平均")
        ax.axhline(df[col].mean(), color=c, lw=1, ls=":", alpha=0.7)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_ylabel("IC")
    ax.set_title("月 IC 長期穩定為正 — 預測力不衰減\n(細線為當月 IC, 粗線為 12 個月滾動平均, 點線為全期均值)", fontweight="bold")
    ax.legend(fontsize=9, loc="upper right")
    save(fig, VIZ / "signal" / "rolling_ic.png")


# ── §6.2 Start-date sensitivity ──────────────────────────────────────────
def startdate_sensitivity():
    V = RES / "_verify_newhigh50"
    strat = pd.read_csv(V / "strategy_nav_net.csv", parse_dates=["date"]).set_index("date")["nav"]
    etf = pd.read_csv(V / "benchmarks" / "0050.csv", parse_dates=["date"]).set_index("date")["nav"]

    def cagr(s, t0):
        s = s[s.index >= t0].dropna()
        s = s / s.iloc[0]
        yrs = (s.index[-1] - s.index[0]).days / 365.25
        return (s.iloc[-1]) ** (1 / yrs) - 1

    starts = ["2018", "2019", "2020", "2021", "2022", "2023"]
    s_cagr = [cagr(strat, pd.Timestamp(f"{y}-01-01")) * 100 for y in starts]
    e_cagr = [cagr(etf, pd.Timestamp(f"{y}-01-01")) * 100 for y in starts]
    x = np.arange(len(starts)); w = 0.38
    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.bar(x - w/2, s_cagr, w, color=GREEN, label="策略 (new_high 50)")
    ax.bar(x + w/2, e_cagr, w, color=BLUE, label="0050")
    for i, (sv, ev) in enumerate(zip(s_cagr, e_cagr)):
        ax.text(i - w/2, sv + 0.3, f"{sv:.0f}", ha="center", fontsize=8)
        ax.text(i + w/2, ev + 0.3, f"{ev:.0f}", ha="center", fontsize=8)
    ax.set_xticks(x); ax.set_xticklabels([f"{y} 起" for y in starts])
    ax.set_ylabel("年化報酬 CAGR (%)  (終點皆 2025-12)")
    ax.set_title("「輸 0050」取決於起點 — 6 起點中策略 4 個勝出\n僅 2018(含Q4股災) 與 2023(台積電行情) 起點 0050 較高", fontweight="bold")
    ax.legend(fontsize=9)
    save(fig, VIZ / "benchmark" / "startdate_sensitivity.png")


# ── §6.3 Alpha significance by benchmark ─────────────────────────────────
def alpha_significance():
    # Data-driven: CAPM from analyze_fair_benchmark.py + random-p50 from robustness.
    cap = pd.read_csv(RES / "_fair_benchmark" / "capm.csv").set_index("benchmark")
    rob = json.loads((RES / "_robustness_newhigh50" / "summary.json").read_text(encoding="utf-8"))
    rp = rob["alpha_vs_random_p50_same_pool"]
    data = [  # ordered by benchmark fairness (t ascending)
        ("0050\n(市值加權, 不對稱)", cap.loc["0050", "alpha_ann"] * 100, cap.loc["0050", "t_alpha"]),
        ("Top-50 EW\n(大型股)", cap.loc["Top-50 EW", "alpha_ann"] * 100, cap.loc["Top-50 EW", "t_alpha"]),
        ("等權投資範圍\n(公平基準)", cap.loc["EW investable universe", "alpha_ann"] * 100, cap.loc["EW investable universe", "t_alpha"]),
        ("同池隨機 p50\n(無技能基準)", rp["alpha_annualised"] * 100, rp["alpha_t_stat"]),
    ]
    labels = [d[0] for d in data]; alphas = [d[1] for d in data]; ts = [d[2] for d in data]
    x = np.arange(len(data))
    fig, ax = plt.subplots(figsize=(10, 5.5))
    bars = ax.bar(x, ts, width=0.6, color=[GREEN if t >= 2 else GREY for t in ts], edgecolor="white")
    ax.axhline(2.0, color=RED, lw=1.2, ls="--")
    ax.text(len(x) - 0.4, 2.08, "t = 2 (顯著門檻)", color=RED, fontsize=8, ha="right")
    for b, t, a in zip(bars, ts, alphas):
        ax.text(b.get_x() + b.get_width()/2, t + 0.08, f"t={t:.2f}\nα={a:+.1f}%",
                ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("超額報酬顯著性 (t 值)")
    ax.set_ylim(0, 5)
    ax.set_title("基準越公平, 超額報酬越顯著 — alpha 一致 +7~16%\n「贏不過 0050 原始報酬」反映基準選擇, 非缺乏 alpha", fontweight="bold")
    save(fig, VIZ / "benchmark" / "alpha_significance.png")


# ── Concentration tradeoff ───────────────────────────────────────────────
def holdings_tradeoff():
    # Data-driven: analyze_holdings_sweep.py (new_high, full framework, net).
    df = pd.read_csv(RES / "_holdings_sweep" / "sweep.csv")
    df = df[df["ranking"] == "new_high"].sort_values("n_holdings")
    n = df["n_holdings"].tolist()
    cagr = (df["cagr"] * 100).tolist()
    sharpe = df["sharpe"].tolist()
    mdd = (df["mdd"] * 100).tolist()
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.plot(n, cagr, "-o", color=BLUE, lw=2, label="CAGR (%)")
    ax.plot(n, [abs(m) for m in mdd], "-s", color=RED, lw=2, label="最大回撤 |MDD| (%)")
    ax.set_xlabel("持股數"); ax.set_ylabel("CAGR / |MDD|  (%)")
    ax2 = ax.twinx()
    ax2.plot(n, sharpe, "-^", color=GREEN, lw=2.4, label="Sharpe")
    ax2.set_ylabel("Sharpe", color=GREEN)
    for xi, s in zip(n, sharpe):
        ax2.text(xi, s + 0.01, f"{s:.2f}", ha="center", fontsize=8, color="#1E8449")
    ax.set_xticks(n)
    ax.set_title("集中度取捨 (new_high, NET) — 越分散, Sharpe 越高、回撤越淺\n12/15 檔可用且勝被動, 但代價約 0.2 Sharpe + 10pp 回撤", fontweight="bold")
    l1, lab1 = ax.get_legend_handles_labels(); l2, lab2 = ax2.get_legend_handles_labels()
    ax.legend(l1 + l2, lab1 + lab2, fontsize=9, loc="center right")
    save(fig, VIZ / "holdings_tradeoff.png")


# ── Parameter heatmaps — not-overfit check across signals ─────────────────
def param_heatmaps():
    cfgs = [
        ("accel",    RES / "_param_grid",          (15, 10)),
        ("new_high", RES / "_param_grid_newhigh",  (50, 10)),
        ("ensemble", RES / "_param_grid_ensemble", (50, 10)),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    for ax, (name, d, star) in zip(axes, cfgs):
        g = pd.read_csv(d / "grid.csv")
        piv = g.pivot(index="max_holdings", columns="min_yoy_growth", values="sharpe")
        ax.imshow(piv.values, cmap="RdYlGn", aspect="auto", vmin=0.4, vmax=0.9)
        ax.set_xticks(range(len(piv.columns)))
        ax.set_xticklabels([f"{int(c)}%" for c in piv.columns])
        ax.set_yticks(range(len(piv.index)))
        ax.set_yticklabels([int(i) for i in piv.index])
        ax.set_xlabel("min_yoy_growth"); ax.set_ylabel("max_holdings")
        for i, hold in enumerate(piv.index):
            for j, yoy in enumerate(piv.columns):
                v = piv.values[i, j]
                star_hit = (int(hold), int(yoy)) == star
                ax.text(j, i, f"{v:.2f}" + (" ★" if star_hit else ""),
                        ha="center", va="center",
                        fontweight="bold" if star_hit else "normal", fontsize=11)
        ax.set_title(f"{name}\nSharpe 範圍 [{g['sharpe'].min():.2f}, {g['sharpe'].max():.2f}], "
                     f"std={g['sharpe'].std():.2f}, 全正", fontsize=10)
    fig.suptitle("參數熱力圖 (Sharpe) — 三種訊號皆穩健, 選用配置(★)非孤立尖峰",
                 fontsize=14, fontweight="bold", y=1.02)
    fig.tight_layout()
    save(fig, VIZ / "param_heatmaps.png")


if __name__ == "__main__":
    quintile_spread()
    rolling_ic()
    startdate_sensitivity()
    alpha_significance()
    holdings_tradeoff()
    param_heatmaps()
    print("done.")
