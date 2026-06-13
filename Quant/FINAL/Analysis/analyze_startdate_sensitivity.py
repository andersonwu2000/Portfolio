"""Start-date sensitivity + proper risk-adjusted comparison vs 0050.

Q: our backtest is 2018-2025 — does that window flatter 0050 (TSMC/AI supercycle)?
   And is raw-CAGR-vs-0050 even the right yardstick?

Reads the new_high top-50 net NAV + 0050 NAV (results/_verify_newhigh50) and:
  1. recomputes strategy vs 0050 CAGR/Sharpe for several start dates -> 2025-12
  2. runs CAPM (strategy daily ret ~ 0050 daily ret): alpha (annualised) + beta + t
     to show the risk-adjusted picture, not just raw return.

Usage:  python analyze_startdate_sensitivity.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
V = ROOT / "results" / "_verify_newhigh50"


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


def main():
    strat = nav(V / "strategy_nav_net.csv")
    etf = nav(V / "benchmarks" / "0050.csv")

    print("=" * 78)
    print("START-DATE SENSITIVITY — new_high top-50 (net) vs 0050, end = 2025-12")
    print("=" * 78)
    print(f"{'start':>10} | {'strategy CAGR/Sharpe':>24} | {'0050 CAGR/Sharpe':>22} | winner")
    for start in ["2018-01-01", "2019-01-01", "2020-01-01", "2021-01-01", "2022-01-01", "2023-01-01"]:
        t0 = pd.Timestamp(start)
        s1 = strat[strat.index >= t0]
        e1 = etf[etf.index >= t0]
        # rebase to 1.0 at window start
        s1 = s1 / s1.iloc[0]; e1 = e1 / e1.iloc[0]
        cs, ss, _ = metrics(s1)
        ce, se, _ = metrics(e1)
        win = "strategy" if cs > ce else "0050"
        print(f"{start:>10} | {cs*100:8.1f}% / {ss:5.2f}        | {ce*100:7.1f}% / {se:5.2f}      | {win} (raw CAGR)")

    # CAPM: strategy vs 0050 (risk-adjusted, full window)
    print("\n" + "=" * 78)
    print("RISK-ADJUSTED (CAPM): strategy daily return regressed on 0050 daily return")
    print("=" * 78)
    al = strat.index.intersection(etf.index)
    rs = strat.loc[al].pct_change().dropna()
    re = etf.loc[al].pct_change().dropna()
    j = rs.index.intersection(re.index)
    x = re.loc[j].values; y = rs.loc[j].values
    beta, alpha_d = np.polyfit(x, y, 1)
    resid = y - (beta * x + alpha_d)
    se_alpha = resid.std() / np.sqrt(len(y))
    t_alpha = alpha_d / se_alpha
    alpha_ann = (1 + alpha_d) ** 252 - 1
    print(f"  beta  vs 0050        = {beta:.2f}   (sensitivity to 0050 moves)")
    print(f"  alpha (annualised)   = {alpha_ann*100:+.1f}%   t = {t_alpha:.2f}")
    print(f"  -> beta {beta:.2f} < 1 means the strategy takes LESS market risk than 0050;")
    print(f"     a positive alpha means it adds return beyond that risk exposure.")


if __name__ == "__main__":
    main()
