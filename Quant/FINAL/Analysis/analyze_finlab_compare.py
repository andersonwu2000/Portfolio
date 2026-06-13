"""Cross-engine check vs FinLab — same period (2007-2018), our engine.

FinLab (online, free data, equal-weight, no hedge, fee 0.1425/tax 0.3) gave:
    net   2007-18  annR +0.32%   MDD -53.5%
    gross 2007-18  annR +5.10%   MDD -48.9%
    net   2010-18  annR -4.59%
    gross 2010-18  annR  0.00%
    YEARLY net: 2008 -22.6  2009 +191.1  2010 -0.4  2011 -42.8  2012 -2.9
                2013 +21.6  2014 +6.9  2015 -9.4  2016 +4.5  2017 +18.0  2018 -26.0

This runs our verifier on the same window in two configs:
  A) match-FinLab : RevenueMomentumStrategy, equal-weight, NO hedge
  B) our-native   : RevenueMomentumHedgedStrategy, signal-weight, hedge ON
for NET (buy17/sell47) and GROSS (0/0), plus yearly returns and a 2010-18 cut.

Usage:  python analyze_finlab_compare.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "Backtest"))

START, END = "2007-07-01", "2018-12-31"


def main() -> None:
    from verify_strategy import (
        ParquetDataSource, build_universe, eligible_at, get_rebalance_dates,
        simulate_nav, VerifyFeed, VerifyContext, VerifyPortfolio, VerifyPosition,
        compute_metrics,
    )
    from strategies.revenue_momentum import RevenueMomentumStrategy
    from strategies.revenue_momentum_hedged import RevenueMomentumHedgedStrategy

    data = ParquetDataSource(ROOT.parent / "Data")
    universe, panel, volume_panel, _, first_listed = build_universe(data, START, END)
    feed = VerifyFeed(universe, panel, volume_panel)
    start_ts, end_ts = pd.Timestamp(START), pd.Timestamp(END)
    sim_idx = panel.index[(panel.index >= start_ts) & (panel.index <= end_ts)]
    rebalance_dates = get_rebalance_dates(sim_idx)
    pool_cache = {d: eligible_at(d, panel, volume_panel, first_listed) for d in rebalance_dates}

    # universe thickness over time
    sizes = [len(pool_cache[d]) for d in rebalance_dates]
    logger.info("Pool size: start=%d mid=%d end=%d", sizes[0], sizes[len(sizes)//2], sizes[-1])

    def make_fn(strategy):
        def weight_fn(date, current_weights, nav, _s=strategy):
            ts = pd.Timestamp(date)
            feed.set_dynamic_universe(pool_cache.get(ts, []))
            pf = VerifyPortfolio(nav)
            for sym, w in current_weights.items():
                pf.positions[sym] = VerifyPosition(value=w * nav)
            return _s.on_bar(VerifyContext(feed, pf, ts))
        return weight_fn

    def yearly(nav):
        y = nav.resample("YE").last().pct_change().dropna()
        # first partial year
        first = nav[nav.index.year == nav.index.year.min()]
        y0 = first.iloc[-1] / first.iloc[0] - 1
        out = {str(nav.index.year.min()): round(y0 * 100, 1)}
        out.update({str(k.year): round(v * 100, 1) for k, v in y.items()})
        return out

    def run(label, strat_factory, buy, sell, want_yearly=False):
        nav, stats = simulate_nav(panel, rebalance_dates, make_fn(strat_factory()),
                                  buy_cost_bps=buy, sell_cost_bps=sell, sim_idx=sim_idx)
        m = compute_metrics(nav)
        logger.info("%-26s annR=%+6.2f%%  Sharpe=%5.2f  MDD=%6.1f%%  turn=%5.2f",
                    label, m["cagr"]*100, m["sharpe"], m["max_drawdown"]*100,
                    stats.get("annual_turnover", float("nan")))
        row = {"config": label, "cagr": m["cagr"], "sharpe": m["sharpe"],
               "mdd": m["max_drawdown"], "turnover": stats.get("annual_turnover")}
        if want_yearly:
            row["yearly"] = yearly(nav)
        # 2010-2018 sub-cut
        sub = nav[nav.index >= pd.Timestamp("2010-01-01")]
        if len(sub) > 2:
            sm = compute_metrics(sub)
            row["cagr_2010_18"] = sm["cagr"]
        return row, nav

    A = lambda: RevenueMomentumStrategy(revenue_dir=str(ROOT.parent / "Data"), weight_method="equal")
    B = lambda: RevenueMomentumHedgedStrategy(revenue_dir=str(ROOT.parent / "Data"))

    rows = []
    r, navA_net = run("A match-FinLab NET", A, 17.0, 47.0, want_yearly=True); rows.append(r)
    r, _ = run("A match-FinLab GROSS", A, 0.0, 0.0); rows.append(r)
    r, _ = run("B our-native NET", B, 17.0, 47.0, want_yearly=True); rows.append(r)
    r, _ = run("B our-native GROSS", B, 0.0, 0.0); rows.append(r)

    print("\n" + "=" * 84)
    print("OUR ENGINE, 2007-2018  (compare to FinLab numbers in header docstring)")
    print("=" * 84)
    for r in rows:
        print("%-24s annR=%+6.2f%%  Sharpe=%5.2f  MDD=%6.1f%%  annR(2010-18)=%+6.2f%%" % (
            r["config"], r["cagr"]*100, r["sharpe"], r["mdd"]*100,
            r.get("cagr_2010_18", float("nan"))*100))
    print("\nYEARLY (A match-FinLab NET):")
    print(" ", rows[0].get("yearly"))
    print("YEARLY (B our-native NET):")
    print(" ", rows[2].get("yearly"))

    out = ROOT / "results" / "_finlab_compare"
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{k: v for k, v in r.items() if k != "yearly"} for r in rows]).to_csv(
        out / "compare.csv", index=False)
    print(f"\nOutput: {(out / 'compare.csv').resolve()}")


if __name__ == "__main__":
    main()
