"""A fairer benchmark: the equal-weight investable universe.

0050 is a poor benchmark (cap-weight, ~half TSMC). Top-50 EW is large-cap only.
The fairest no-skill benchmark for a long-only diversified factor strategy is the
EQUAL-WEIGHT INVESTABLE UNIVERSE: hold every eligible stock each month at equal
weight (same point-in-time pool the strategy and random portfolios draw from),
monthly rebalance, net cost. The strategy is then "EW-universe + revenue tilt",
so strategy − EW-universe isolates the factor's value-add, and a CAPM regression
on it gives a clean beta (~1) and alpha.

Compares new_high top-50 (net) vs: EW-universe, Top-50 EW, 0050. 2018-2025.

Usage:  python analyze_fair_benchmark.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "Backtest"))
V = ROOT / "results" / "_verify_newhigh50"
BUY, SELL = 17.0 / 1e4, 47.0 / 1e4


def nav(p):
    return pd.read_csv(p, parse_dates=["date"]).set_index("date")["nav"]


def metrics(s):
    s = s.dropna()
    yrs = (s.index[-1] - s.index[0]).days / 365.25
    cagr = (s.iloc[-1] / s.iloc[0]) ** (1 / yrs) - 1
    r = s.pct_change().dropna()
    sharpe = r.mean() / r.std() * np.sqrt(252) if r.std() > 0 else 0.0
    mdd = ((s - s.cummax()) / s.cummax()).min()
    return cagr, sharpe, mdd


def capm(strat_nav, bench_nav):
    al = strat_nav.index.intersection(bench_nav.index)
    rs = strat_nav.loc[al].pct_change().dropna()
    rb = bench_nav.loc[al].pct_change().dropna()
    j = rs.index.intersection(rb.index)
    x, y = rb.loc[j].values, rs.loc[j].values
    beta, alpha_d = np.polyfit(x, y, 1)
    resid = y - (beta * x + alpha_d)
    t_alpha = alpha_d / (resid.std() / np.sqrt(len(y)))
    return beta, (1 + alpha_d) ** 252 - 1, t_alpha


def main():
    from verify_strategy import (
        ParquetDataSource, build_universe, get_rebalance_dates, top_n_equal_weight_nav,
    )

    data = ParquetDataSource(ROOT.parent / "Data")
    universe, panel, volume_panel, _, first_listed = build_universe(data, "2018-01-01", "2025-12-31")
    sim_idx = panel.index[(panel.index >= pd.Timestamp("2018-01-01")) & (panel.index <= pd.Timestamp("2025-12-31"))]
    rb = get_rebalance_dates(sim_idx)

    # Equal-weight investable universe = top_n_equal_weight with n = entire pool.
    # Produces a DAILY NAV via the same engine as the strategy, so metrics (sqrt252)
    # and the CAPM regression are frequency-consistent.
    ewu = top_n_equal_weight_nav(
        panel, volume_panel, first_listed, rb, sim_idx,
        n_holdings=100000, buy_bps=17.0, sell_bps=47.0,
    )

    strat = nav(V / "strategy_nav_net.csv")
    etf0050 = nav(V / "benchmarks" / "0050.csv")
    top50 = nav(V / "benchmarks" / "top50_eq_weight_net.csv")

    print("=" * 76)
    print("FAIR-BENCHMARK COMPARISON (net, 2018-2025) — new_high top-50")
    print("=" * 76)
    print(f"{'series':<26}{'CAGR':>8}{'Sharpe':>8}{'MDD':>8}")
    for name, s in [("Strategy (new_high 50)", strat),
                    ("EW investable universe", ewu),
                    ("Top-50 EW (large-cap)", top50),
                    ("0050 (cap-weight)", etf0050)]:
        c, sh, mdd = metrics(s / s.iloc[0])
        print(f"{name:<26}{c*100:>7.1f}%{sh:>8.2f}{mdd*100:>7.1f}%")

    print("\nCAPM of strategy vs each benchmark (alpha annualised, t):")
    capm_rows = []
    for name, b in [("EW investable universe", ewu),
                    ("Top-50 EW", top50),
                    ("0050", etf0050)]:
        beta, alpha, t = capm(strat, b)
        flag = "  <- fair benchmark" if "EW investable" in name else ""
        print(f"  vs {name:<24} beta={beta:.2f}  alpha={alpha*100:+5.1f}%  t={t:.2f}{flag}")
        capm_rows.append({"benchmark": name, "beta": beta,
                          "alpha_ann": alpha, "t_alpha": t})

    out = ROOT / "results" / "_fair_benchmark"
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(capm_rows).to_csv(out / "capm.csv", index=False)
    print(f"\nOutput: {(out / 'capm.csv').resolve()}")


if __name__ == "__main__":
    main()
