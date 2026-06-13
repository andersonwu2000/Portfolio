"""Yearly breakdown — is new_high's RECENT performance poor? (long-only top-50 net + LS)

Answers "is new_high bad in the last ~3 years" with year-by-year granularity,
for both new_high and accel, in both forms (long-only top-50 net, and Q5-Q1 LS gross).

Usage:  python analyze_newhigh_yearly.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "Backtest"))

START, END = "2015-01-01", "2025-12-31"
BUY, SELL = 17.0 / 1e4, 47.0 / 1e4
NQ, TOPN = 5, 50


def main() -> None:
    from verify_strategy import ParquetDataSource, build_universe, eligible_at, get_rebalance_dates
    from strategies.revenue_momentum import _preload_revenue

    data = ParquetDataSource(ROOT.parent / "Data")
    universe, panel, volume_panel, _, first_listed = build_universe(data, START, END)
    rev_cache = _preload_revenue(str(ROOT.parent / "Data"))
    sim_idx = panel.index[(panel.index >= pd.Timestamp(START)) & (panel.index <= pd.Timestamp(END))]
    rb = list(get_rebalance_dates(sim_idx))
    pool_cache = {d: list(eligible_at(d, panel, volume_panel, first_listed)) for d in rb}

    def factors(sym, d):
        df = rev_cache.get(sym)
        if df is None:
            return None
        u = df[df["date"] <= d - pd.DateOffset(days=40)]
        if len(u) < 12:
            return None
        rev = u["revenue"].astype(float).values
        r3, r12 = np.mean(rev[-3:]), np.mean(rev[-12:])
        pmax = np.max(rev[-12:-1])
        if r12 <= 0 or pmax <= 0:
            return None
        return r3 / r12, rev[-1] / pmax

    months = []
    for d0, d1 in zip(rb[:-1], rb[1:]):
        obs = []
        for sym in pool_cache[d0]:
            f = factors(sym, d0)
            if f is None:
                continue
            try:
                p0, p1 = panel.at[d0, sym], panel.at[d1, sym]
            except KeyError:
                continue
            if np.isfinite(p0) and np.isfinite(p1) and p0 > 0 and p1 > 0:
                obs.append((sym, f[0], f[1], p1 / p0 - 1))
        if len(obs) >= 120:
            months.append((d1, pd.DataFrame(obs, columns=["sym", "accel", "new_high", "ret"])))

    def topN_monthly_ret(fcol):
        prev, out = set(), {}
        for d, df in months:
            top = set(df.sort_values(fcol, ascending=False)["sym"].head(TOPN))
            w = 1.0 / TOPN
            cost = len(top - prev) * w * BUY + len(prev - top) * w * SELL
            g = df[df["sym"].isin(top)]["ret"].mean()
            out[d] = (1 + g) * (1 - cost) - 1
            prev = top
        return pd.Series(out)

    def ls_monthly_ret(fcol):
        out = {}
        for d, df in months:
            df = df.copy()
            df["q"] = pd.qcut(df[fcol].rank(method="first"), NQ, labels=False)
            g = df.groupby("q")["ret"].mean()
            out[d] = g.get(NQ - 1, np.nan) - g.get(0, np.nan)
        return pd.Series(out)

    def yearly(s):
        nav = (1 + s.fillna(0)).cumprod()
        y = nav.resample("YE").last().pct_change()
        first = nav[nav.index.year == nav.index.year.min()]
        y.iloc[0] = first.iloc[-1] / 1.0 - 1
        return {k.year: round(v * 100, 1) for k, v in y.items()}

    print("\n" + "=" * 78)
    print("YEARLY RETURNS (%) — long-only top-50 NET")
    print("=" * 78)
    for f in ["accel", "new_high"]:
        print(f"  {f:9s}: {yearly(topN_monthly_ret(f))}")
    print("\nYEARLY RETURNS (%) — Q5-Q1 long-short GROSS")
    for f in ["accel", "new_high"]:
        print(f"  {f:9s}: {yearly(ls_monthly_ret(f))}")


if __name__ == "__main__":
    main()
