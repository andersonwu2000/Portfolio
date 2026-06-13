"""Full-framework validation — does the ensemble ranking win INSIDE the real strategy?

The factor tests (analyze_ensemble.py) used a pure top-N by factor, no screens,
equal-weight. Here we run the FULL RevenueMomentumHedgedStrategy (5 screens +
signal-weight + no-trade zone + regime hedge) and only swap the `ranking` factor,
to check the improvement survives the real machinery.

Config 1 reproduces the committed reference (accel / top-15) as a regression check
(should be ~ CAGR 11.9% / Sharpe 0.48 / +145%).

NET buy17/sell47, 2018-2025. Baselines: Top-50 EW passive, 0050 buy-hold.

Usage:  python analyze_validate_ensemble.py
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


def main() -> None:
    from verify_strategy import (
        ParquetDataSource, build_universe, eligible_at, get_rebalance_dates,
        simulate_nav, VerifyFeed, VerifyContext, VerifyPortfolio, VerifyPosition,
        compute_metrics, top_n_equal_weight_nav, buy_hold_etf,
    )
    from strategies.revenue_momentum_hedged import RevenueMomentumHedgedStrategy

    data = ParquetDataSource(ROOT.parent / "Data")
    universe, panel, volume_panel, _, first_listed = build_universe(data, "2018-01-01", "2025-12-31")
    feed = VerifyFeed(universe, panel, volume_panel)
    sim_idx = panel.index[(panel.index >= pd.Timestamp("2018-01-01")) & (panel.index <= pd.Timestamp("2025-12-31"))]
    rb = get_rebalance_dates(sim_idx)
    pool_cache = {d: eligible_at(d, panel, volume_panel, first_listed) for d in rb}

    def make_fn(strategy):
        def weight_fn(date, current_weights, nav, _s=strategy):
            ts = pd.Timestamp(date)
            feed.set_dynamic_universe(pool_cache.get(ts, []))
            pf = VerifyPortfolio(nav)
            for sym, w in current_weights.items():
                pf.positions[sym] = VerifyPosition(value=w * nav)
            return _s.on_bar(VerifyContext(feed, pf, ts))
        return weight_fn

    def run(label, ranking, maxh, buy=17.0, sell=47.0):
        strat = RevenueMomentumHedgedStrategy(revenue_dir=str(ROOT.parent / "Data"),
                                              ranking=ranking, max_holdings=maxh)
        nav, stats = simulate_nav(panel, rb, make_fn(strat), buy_cost_bps=buy, sell_cost_bps=sell, sim_idx=sim_idx)
        m = compute_metrics(nav)
        logger.info("%-34s total=%+7.1f%% CAGR=%+6.2f%% Sharpe=%.2f MDD=%.1f%% turn=%.1f",
                    label, m["total_return"]*100, m["cagr"]*100, m["sharpe"],
                    m["max_drawdown"]*100, stats["annual_turnover"])
        return (label, m, stats)

    rows = [
        run("accel  top-15 (=reference) NET", "accel", 15),
        run("accel  top-50           NET", "accel", 50),
        run("new_high top-50         NET", "new_high", 50),
        run("ensemble top-50         NET", "ensemble", 50),
        run("ensemble top-50         GROSS", "ensemble", 50, buy=0.0, sell=0.0),
    ]

    # baselines
    top50 = top_n_equal_weight_nav(panel, volume_panel, first_listed, rb, sim_idx,
                                   n_holdings=50, buy_bps=17.0, sell_bps=47.0)
    m50 = compute_metrics(top50)
    etf = buy_hold_etf(data, "0050.TW", sim_idx)
    me = compute_metrics(etf)

    print("\n" + "=" * 92)
    print("FULL-FRAMEWORK VALIDATION (hedged: 5 screens + signal-wt + NTZ + regime), 2018-2025")
    print("=" * 92)
    print(f"{'config':>34}{'total':>9}{'CAGR':>8}{'Sharpe':>8}{'MDD':>8}{'turn/yr':>9}")
    for label, m, stats in rows:
        print(f"{label:>34}{m['total_return']*100:>8.1f}%{m['cagr']*100:>7.2f}%"
              f"{m['sharpe']:>8.2f}{m['max_drawdown']*100:>7.1f}%{stats['annual_turnover']:>9.1f}")
    print(f"{'-- Top-50 EW passive':>34}{m50['total_return']*100:>8.1f}%{m50['cagr']*100:>7.2f}%"
          f"{m50['sharpe']:>8.2f}{m50['max_drawdown']*100:>7.1f}%{'~1':>9}")
    print(f"{'-- 0050 buy-hold':>34}{me['total_return']*100:>8.1f}%{me['cagr']*100:>7.2f}%"
          f"{me['sharpe']:>8.2f}{me['max_drawdown']*100:>7.1f}%{'-':>9}")
    print("\nReference check: 'accel top-15 NET' should be ~ +145% / CAGR 11.9% / Sharpe 0.48.")


if __name__ == "__main__":
    main()
