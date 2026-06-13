"""Quantile long-short spread — the decisive test of "signal real, implementation bad".

If the revenue_acceleration signal is genuine (positive IC), then a market-neutral
Q5-Q1 long-short spread should be POSITIVE, LOW-beta, and have a SMALL drawdown —
while the long-only top quintile carries market beta and a large drawdown.

That separates the signal (real) from the long-only construction (the problem).

Each month, rank the *investable* pool (eligible_at: listed >=90d + liquidity, but
NO trend/momentum screens — those are implementation) by accel = rev3m/rev12m
(40-day lag) into quintiles. Hold each quintile equal-weight for the month. Build
NAV per quintile + Q5-Q1 spread. Report annual return / Sharpe / MDD / beta vs the
equal-weight market, plus quintile monotonicity. GROSS (signal test).

NOTE: TW shorting is costly/constrained — Q5-Q1 is a SIGNAL diagnostic, not a
directly tradeable product.

Usage:  python analyze_quantile_spread.py
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
NQ = 5


def metrics(nav: pd.Series) -> dict:
    nav = nav.dropna()
    if len(nav) < 3:
        return {}
    yrs = (nav.index[-1] - nav.index[0]).days / 365.25
    total = nav.iloc[-1] / nav.iloc[0] - 1
    cagr = (nav.iloc[-1] / nav.iloc[0]) ** (1 / yrs) - 1
    rets = nav.pct_change().dropna()
    sharpe = rets.mean() / rets.std() * np.sqrt(12) if rets.std() > 0 else 0.0
    mdd = ((nav - nav.cummax()) / nav.cummax()).min()
    return {"total": total, "cagr": cagr, "sharpe": sharpe, "mdd": mdd}


def main() -> None:
    from verify_strategy import ParquetDataSource, build_universe, eligible_at, get_rebalance_dates
    from strategies.revenue_momentum import _preload_revenue, _get_revenue_at

    data = ParquetDataSource(ROOT.parent / "Data")
    universe, panel, volume_panel, _, first_listed = build_universe(data, START, END)
    rev_cache = _preload_revenue(str(ROOT.parent / "Data"))

    start_ts, end_ts = pd.Timestamp(START), pd.Timestamp(END)
    sim_idx = panel.index[(panel.index >= start_ts) & (panel.index <= end_ts)]
    rb = list(get_rebalance_dates(sim_idx))
    pool_cache = {d: set(eligible_at(d, panel, volume_panel, first_listed)) for d in rb}

    # monthly returns per quintile + market
    recs = []
    for d0, d1 in zip(rb[:-1], rb[1:]):
        pool = pool_cache[d0]
        obs = []
        for sym in pool:
            rv = _get_revenue_at(rev_cache, sym, d0)
            if rv is None or rv[1] <= 0:
                continue
            a = rv[0] / rv[1]
            try:
                p0 = panel.at[d0, sym]
                p1 = panel.at[d1, sym]
            except KeyError:
                continue
            if not (np.isfinite(p0) and np.isfinite(p1) and p0 > 0 and p1 > 0):
                continue
            obs.append((a, p1 / p0 - 1))
        if len(obs) < NQ * 10:
            continue
        df = pd.DataFrame(obs, columns=["accel", "ret"]).sort_values("accel")
        df["q"] = pd.qcut(df["accel"].rank(method="first"), NQ, labels=False)
        qret = df.groupby("q")["ret"].mean()
        rec = {"date": d1, "mkt": df["ret"].mean()}
        for q in range(NQ):
            rec[f"q{q+1}"] = qret.get(q, np.nan)
        recs.append(rec)

    m = pd.DataFrame(recs).set_index("date")
    m["ls"] = m[f"q{NQ}"] - m["q1"]  # long top, short bottom
    out = ROOT / "results" / "_quantile_spread"
    out.mkdir(parents=True, exist_ok=True)
    m.to_csv(out / "monthly_quantile_returns.csv")

    def beta(series):
        x = m["mkt"].values
        y = series.values
        ok = np.isfinite(x) & np.isfinite(y)
        if ok.sum() < 5:
            return np.nan
        return np.cov(y[ok], x[ok])[0, 1] / np.var(x[ok])

    def report(title, sub):
        print("\n" + "=" * 86)
        print(f"QUANTILE SPREAD — revenue_acceleration, {title}  (GROSS, monthly EW)")
        print("=" * 86)
        print(f"{'leg':10s}{'annRet':>9s}{'Sharpe':>9s}{'MDD':>9s}{'beta(mkt)':>11s}")
        legs = [f"q{q+1}" for q in range(NQ)] + ["ls", "mkt"]
        names = {**{f"q{q+1}": f"Q{q+1}" for q in range(NQ)},
                 "ls": "Q5-Q1 LS", "mkt": "Market EW"}
        monos = []
        for leg in legs:
            nav = (1 + sub[leg].fillna(0)).cumprod()
            mt = metrics(nav)
            if not mt:
                continue
            b = beta(sub[leg]) if leg != "mkt" else 1.0
            print(f"{names[leg]:10s}{mt['cagr']*100:>8.2f}%{mt['sharpe']:>9.2f}"
                  f"{mt['mdd']*100:>8.1f}%{b:>11.2f}")
            if leg.startswith("q"):
                monos.append(sub[leg].mean())
        # monotonicity Q1..Q5 mean monthly return
        print("  Q1..Q5 mean monthly ret: " + "  ".join(f"{v*100:+.3f}%" for v in monos))

    report("2015-2025", m)
    report("2018-2025", m[m.index >= pd.Timestamp("2018-01-01")])
    print(f"\nOutput: {(out / 'monthly_quantile_returns.csv').resolve()}")


if __name__ == "__main__":
    main()
