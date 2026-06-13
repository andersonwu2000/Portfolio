"""Head-to-head: revenue_new_high vs revenue_acceleration (FinLab rule #6 claim).

FinLab's strategy notes claim "revenue at a new high is a very strong
signal". We test it against our incumbent ranking factor (acceleration) in the
same framework that we used to establish "signal real, implementation bad":

  accel    = mean(rev[-3:]) / mean(rev[-12:])
  new_high = rev[-1] / max(rev[-12:-1])        # canonical new-high definition

Both with the 40-day publication lag. For each factor:
  A) Quantile Q5-Q1 spread (GROSS, monthly EW) — pure signal quality
     -> annRet / Sharpe / MDD / beta + Q1..Q5 monotonicity
  B) Long-only top-50 (NET buy17/sell47, monthly EW) — deployable form
Across 2015-2025, 2018-2025, 2022-2025.

Usage:  python analyze_newhigh_vs_accel.py
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


def met(rets: pd.Series):
    nav = (1 + rets.fillna(0)).cumprod()
    yrs = (nav.index[-1] - nav.index[0]).days / 365.25
    cagr = (nav.iloc[-1] / nav.iloc[0]) ** (1 / yrs) - 1
    r = nav.pct_change().dropna()
    sh = r.mean() / r.std() * np.sqrt(12) if r.std() > 0 else 0.0
    mdd = ((nav - nav.cummax()) / nav.cummax()).min()
    return cagr, sh, mdd


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
        past_max = np.max(rev[-12:-1])
        if r12 <= 0 or past_max <= 0:
            return None
        return r3 / r12, rev[-1] / past_max  # accel, new_high

    # per-month observations
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
            if not (np.isfinite(p0) and np.isfinite(p1) and p0 > 0 and p1 > 0):
                continue
            obs.append((sym, f[0], f[1], p1 / p0 - 1))
        if len(obs) >= 120:
            months.append((d1, pd.DataFrame(obs, columns=["sym", "accel", "new_high", "ret"])))

    dates = [d for d, _ in months]
    mkt = pd.Series({d: df["ret"].mean() for d, df in months})

    def quantile_ls(fcol):
        q1, q5, monos = {}, {}, []
        qmeans = np.zeros(NQ)
        for d, df in months:
            df = df.copy()
            df["q"] = pd.qcut(df[fcol].rank(method="first"), NQ, labels=False)
            g = df.groupby("q")["ret"].mean()
            q1[d], q5[d] = g.get(0, np.nan), g.get(NQ - 1, np.nan)
            qmeans += np.array([g.get(i, np.nan) for i in range(NQ)])
        q1, q5 = pd.Series(q1), pd.Series(q5)
        ls = q5 - q1
        return ls, q5, qmeans / len(months)

    def topN_net(fcol):
        prev, navs, dts = set(), [], []
        nav = 1.0
        for d, df in months:
            top = set(df.sort_values(fcol, ascending=False)["sym"].head(TOPN))
            w = 1.0 / TOPN
            cost = len(top - prev) * w * BUY + len(prev - top) * w * SELL
            g = df[df["sym"].isin(top)]["ret"].mean()
            nav *= (1 + g) * (1 - cost)
            navs.append(nav); dts.append(d); prev = top
        return pd.Series(navs, index=pd.to_datetime(dts))

    def beta(s):
        al = s.dropna().index.intersection(mkt.index)
        x, y = mkt.loc[al].values, s.loc[al].values
        return np.cov(y, x)[0, 1] / np.var(x)

    periods = [("2015-2025", pd.Timestamp("2015-01-01")),
               ("2018-2025", pd.Timestamp("2018-01-01")),
               ("2022-2025", pd.Timestamp("2022-01-01"))]

    for fcol in ["accel", "new_high"]:
        ls, q5, qmeans = quantile_ls(fcol)
        lo = topN_net(fcol)
        print("\n" + "=" * 84)
        print(f"FACTOR = {fcol}")
        print("=" * 84)
        print(f"  Q1..Q5 monthly mean ret (full): " + "  ".join(f"{v*100:+.3f}%" for v in qmeans))
        print(f"  {'period':>10} | {'Q5-Q1 LS (gross)':^34} | {'top-50 long-only (net)':^28}")
        print(f"  {'':>10} | {'annRet':>8}{'Sharpe':>8}{'MDD':>8}{'beta':>8} | {'CAGR':>8}{'Sharpe':>8}{'MDD':>8}")
        for name, t0 in periods:
            lss = ls[ls.index >= t0]
            c1, s1, d1 = met(lss)
            b = beta(lss)
            los = lo[lo.index >= t0]
            c2, s2, d2 = met(los.pct_change().dropna()) if len(los) > 2 else (np.nan,)*3
            # for long-only use NAV-based metrics
            yrs = (los.index[-1] - los.index[0]).days / 365.25
            c2 = (los.iloc[-1] / los.iloc[0]) ** (1 / yrs) - 1
            r2 = los.pct_change().dropna(); s2 = r2.mean()/r2.std()*np.sqrt(12)
            d2 = ((los - los.cummax())/los.cummax()).min()
            print(f"  {name:>10} | {c1*100:>7.2f}%{s1:>8.2f}{d1*100:>7.1f}%{b:>8.2f} | "
                  f"{c2*100:>7.2f}%{s2:>8.2f}{d2*100:>7.1f}%")


if __name__ == "__main__":
    main()
