"""Turnover-reduction experiment — does cutting churn close the net-alpha gap?

Diagnosis (see README): the strategy has real GROSS alpha but loses NET to
Top-50 EW because annual turnover ~13/yr meets asymmetric TW cost (buy 17 /
sell 47 bps). The churn is dominated by names oscillating around the
rank-`max_holdings` boundary, which the no-trade zone cannot suppress (a new
entrant goes 0% -> target, far above the 1.5% buy threshold).

This script tests two principled, pre-registered structural fixes — NOT a
parameter search. Every variant is reported; nothing is cherry-picked.

  A. Selection hysteresis (buffering): enter at rank <= 15, hold until rank > B
     for B in {20, 25, 30}.  (strategy-level, one parameter with physical meaning)
  B. Slower rebalance: monthly -> quarterly.  (engine-level)

Baseline (monthly, no buffer) reproduces the reference run for comparison.

Usage:
    python analyze_turnover_opt.py
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

BUY_BPS, SELL_BPS = 17.0, 47.0


def main() -> None:
    from verify_strategy import (
        ParquetDataSource, build_universe, eligible_at, get_rebalance_dates,
        simulate_nav, VerifyFeed, VerifyContext, VerifyPortfolio, VerifyPosition,
        compute_metrics,
    )
    from strategies.revenue_momentum_hedged import RevenueMomentumHedgedStrategy

    data = ParquetDataSource(ROOT.parent / "Data")
    universe, panel, volume_panel, _, first_listed = build_universe(
        data, "2018-01-01", "2025-12-31",
    )
    feed = VerifyFeed(universe, panel, volume_panel)

    start_ts, end_ts = pd.Timestamp("2018-01-01"), pd.Timestamp("2025-12-31")
    sim_idx = panel.index[(panel.index >= start_ts) & (panel.index <= end_ts)]
    monthly_dates = get_rebalance_dates(sim_idx)
    quarterly_dates = monthly_dates[::3]
    pool_cache = {d: eligible_at(d, panel, volume_panel, first_listed) for d in monthly_dates}

    def run(label: str, *, exit_rank=None, rebalance_dates=None):
        rb = rebalance_dates if rebalance_dates is not None else monthly_dates
        strategy = RevenueMomentumHedgedStrategy(
            revenue_dir=str(ROOT.parent / "Data"),
            exit_rank=exit_rank,
        )

        def weight_fn(date, current_weights, nav, _s=strategy):
            ts = pd.Timestamp(date)
            feed.set_dynamic_universe(pool_cache.get(ts, []))
            portfolio = VerifyPortfolio(nav)
            for sym, w in current_weights.items():
                portfolio.positions[sym] = VerifyPosition(value=w * nav)
            ctx = VerifyContext(feed, portfolio, ts)
            return _s.on_bar(ctx)

        nav, stats = simulate_nav(panel, rb, weight_fn,
                                  buy_cost_bps=BUY_BPS, sell_cost_bps=SELL_BPS, sim_idx=sim_idx)
        m = compute_metrics(nav)
        row = {
            "variant": label,
            "annual_turnover": stats["annual_turnover"],
            "total_return": m["total_return"],
            "cagr": m["cagr"],
            "sharpe": m["sharpe"],
            "max_drawdown": m["max_drawdown"],
        }
        logger.info("%-26s turnover=%5.2f/yr  total=%+7.1f%%  CAGR=%+6.2f%%  Sharpe=%.2f  MDD=%.1f%%",
                    label, row["annual_turnover"], m["total_return"]*100, m["cagr"]*100,
                    m["sharpe"], m["max_drawdown"]*100)
        return row

    rows = [
        run("baseline (monthly)"),
        run("hysteresis exit_rank=20", exit_rank=20),
        run("hysteresis exit_rank=25", exit_rank=25),
        run("hysteresis exit_rank=30", exit_rank=30),
        run("quarterly rebalance", rebalance_dates=quarterly_dates),
        run("quarterly + exit_rank=25", exit_rank=25, rebalance_dates=quarterly_dates),
    ]

    df = pd.DataFrame(rows)
    out_dir = ROOT / "results" / "_turnover_opt"
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / "comparison.csv", index=False)

    print("\n" + "=" * 78)
    print("TURNOVER-REDUCTION EXPERIMENT  (net: buy 17 / sell 47 bps, 2018-2025)")
    print("Reference: Top-50 EW net  total=+183%  CAGR +13.9%  Sharpe 0.55")
    print("=" * 78)
    disp = df.copy()
    disp["total_return"] = (disp["total_return"] * 100).round(1)
    disp["cagr"] = (disp["cagr"] * 100).round(2)
    disp["max_drawdown"] = (disp["max_drawdown"] * 100).round(1)
    disp["sharpe"] = disp["sharpe"].round(3)
    disp["annual_turnover"] = disp["annual_turnover"].round(2)
    print(disp.to_string(index=False))
    print(f"\nOutput: {(out_dir / 'comparison.csv').resolve()}")


if __name__ == "__main__":
    main()
