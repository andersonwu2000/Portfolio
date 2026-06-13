"""Ensemble test — does combining factors (rank-average) beat the best single factor?

FinLab 4/1 thesis: "weak + weak + weak = strong" via ensemble of uncorrelated
factors. We have revenue (accel, new_high) + technical (60d momentum); no value
data. Test long-only top-50 NET (monthly EW), the deployable form:

  accel only | new_high only | accel+new_high | accel+new_high+mom60

Combine by averaging cross-sectional ranks each month, then take top-50.
Report yearly returns + aggregate Sharpe over 2015-25 / 2018-25 / 2022-25.
Question: higher Sharpe AND/OR fewer bad years than the best single factor?

Usage:  python analyze_ensemble.py
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
TOPN = 50


def main() -> None:
    from verify_strategy import ParquetDataSource, build_universe, eligible_at, get_rebalance_dates
    from strategies.revenue_momentum import _preload_revenue

    data = ParquetDataSource(ROOT.parent / "Data")
    universe, panel, volume_panel, _, first_listed = build_universe(data, START, END)
    rev_cache = _preload_revenue(str(ROOT.parent / "Data"))
    sim_idx = panel.index[(panel.index >= pd.Timestamp(START)) & (panel.index <= pd.Timestamp(END))]
    rb = list(get_rebalance_dates(sim_idx))
    pool_cache = {d: list(eligible_at(d, panel, volume_panel, first_listed)) for d in rb}
    ipos = {d: i for i, d in enumerate(panel.index)}

    def rev_factors(sym, d):
        df = rev_cache.get(sym)
        if df is None:
            return None
        u = df[df["date"] <= d - pd.DateOffset(days=40)]
        if len(u) < 12:
            return None
        rev = u["revenue"].astype(float).values
        r3, r12, pmax = np.mean(rev[-3:]), np.mean(rev[-12:]), np.max(rev[-12:-1])
        if r12 <= 0 or pmax <= 0:
            return None
        return r3 / r12, rev[-1] / pmax

    months = []
    for d0, d1 in zip(rb[:-1], rb[1:]):
        i0 = ipos[d0]
        obs = []
        for sym in pool_cache[d0]:
            rf = rev_factors(sym, d0)
            if rf is None:
                continue
            try:
                p0, p1 = panel.at[d0, sym], panel.at[d1, sym]
            except KeyError:
                continue
            if not (np.isfinite(p0) and np.isfinite(p1) and p0 > 0 and p1 > 0):
                continue
            mom = np.nan
            if i0 >= 60:
                pm = panel[sym].iloc[i0 - 60]
                if np.isfinite(pm) and pm > 0:
                    mom = p0 / pm - 1
            obs.append((sym, rf[0], rf[1], mom, p1 / p0 - 1))
        if len(obs) >= 120:
            months.append((d1, pd.DataFrame(obs, columns=["sym", "accel", "new_high", "mom", "ret"])))

    def topN_net(score_cols):
        prev, out = set(), {}
        for d, df in months:
            df = df.copy()
            sub = df.dropna(subset=score_cols)
            if len(sub) < TOPN:
                sub = df.copy()
                for c in score_cols:
                    sub[c] = sub[c].fillna(sub[c].median())
            score = sum(sub[c].rank(pct=True) for c in score_cols) / len(score_cols)
            top = set(sub.assign(s=score).sort_values("s", ascending=False)["sym"].head(TOPN))
            w = 1.0 / TOPN
            cost = len(top - prev) * w * BUY + len(prev - top) * w * SELL
            g = df[df["sym"].isin(top)]["ret"].mean()
            out[d] = (1 + g) * (1 - cost) - 1
            prev = top
        return pd.Series(out)

    def agg(s, t0):
        s = s[s.index >= t0]
        nav = (1 + s.fillna(0)).cumprod()
        yrs = (nav.index[-1] - nav.index[0]).days / 365.25
        c = (nav.iloc[-1]) ** (1 / yrs) - 1
        r = nav.pct_change().dropna()
        sh = r.mean() / r.std() * np.sqrt(12)
        mdd = ((nav - nav.cummax()) / nav.cummax()).min()
        return c, sh, mdd

    def yearly(s):
        nav = (1 + s.fillna(0)).cumprod()
        y = nav.resample("YE").last().pct_change()
        y.iloc[0] = nav[nav.index.year == nav.index.year.min()].iloc[-1] - 1
        return {k.year: round(v * 100, 1) for k, v in y.items()}

    variants = {
        "accel": ["accel"],
        "new_high": ["new_high"],
        "accel+nh": ["accel", "new_high"],
        "accel+nh+mom": ["accel", "new_high", "mom"],
    }
    series = {name: topN_net(cols) for name, cols in variants.items()}

    print("\n" + "=" * 80)
    print("ENSEMBLE — long-only top-50 NET (monthly EW). CAGR / Sharpe / MDD")
    print("=" * 80)
    print(f"{'variant':>14}{'2015-25':>22}{'2018-25':>22}{'2022-25':>22}")
    for name, s in series.items():
        cells = []
        for t0 in [pd.Timestamp("2015-01-01"), pd.Timestamp("2018-01-01"), pd.Timestamp("2022-01-01")]:
            c, sh, mdd = agg(s, t0)
            cells.append(f"{c*100:5.1f}% Sh{sh:.2f} {mdd*100:5.0f}%")
        print(f"{name:>14}" + "".join(f"{x:>22}" for x in cells))

    print("\nYEARLY RETURNS (%):")
    for name, s in series.items():
        print(f"  {name:>14}: {yearly(s)}")


if __name__ == "__main__":
    main()
