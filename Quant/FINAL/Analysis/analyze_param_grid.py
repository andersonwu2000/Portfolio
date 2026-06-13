"""參數敏感度網格 — 證明策略不靠特定參數組合。

對 RevenueMomentumHedgedStrategy 的兩個關鍵參數做 3×3 掃描：
- max_holdings ∈ {10, 15, 20}
- min_yoy_growth ∈ {5, 10, 15}

每組跑完整 8 年回測，輸出 Sharpe / CAGR / MDD。
真有 alpha 的策略：鄰近組合表現應該相近，分布平滑。
過擬合的策略：只有特定組合好，附近就崩。

Usage:
    python analyze_param_grid.py
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "Backtest"))


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--ranking", default="accel", choices=["accel", "new_high", "ensemble"])
    p.add_argument("--holdings", default="10,15,20", help="comma list of max_holdings")
    p.add_argument("--yoy", default="5,10,15", help="comma list of min_yoy_growth")
    p.add_argument("--out", default=str(ROOT / "results" / "_param_grid"))
    args = p.parse_args()

    # ── 跟主驗證器共用 build_universe / simulate_nav / Verify* adapters ──
    from verify_strategy import (
        ParquetDataSource, build_universe, eligible_at, get_rebalance_dates,
        simulate_nav, VerifyFeed, VerifyContext, VerifyPortfolio, VerifyPosition,
        compute_metrics,
    )
    from strategies.revenue_momentum_hedged import RevenueMomentumHedgedStrategy

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    data = ParquetDataSource(ROOT.parent / "Data")
    universe, panel, volume_panel, _, first_listed = build_universe(
        data, "2018-01-01", "2025-12-31",
    )
    feed = VerifyFeed(universe, panel, volume_panel)

    start_ts = pd.Timestamp("2018-01-01")
    end_ts = pd.Timestamp("2025-12-31")
    sim_idx = panel.index[(panel.index >= start_ts) & (panel.index <= end_ts)]
    rebalance_dates = get_rebalance_dates(sim_idx)
    pool_cache = {d: eligible_at(d, panel, volume_panel, first_listed) for d in rebalance_dates}

    grid_top = [int(x) for x in args.holdings.split(",")]
    grid_yoy = [float(x) for x in args.yoy.split(",")]
    logger.info("Ranking=%s  holdings=%s  yoy=%s", args.ranking, grid_top, grid_yoy)

    rows = []
    for top in grid_top:
        for yoy in grid_yoy:
            logger.info("Running max_holdings=%d, min_yoy_growth=%.0f", top, yoy)
            strategy = RevenueMomentumHedgedStrategy(
                revenue_dir=str(ROOT.parent / "Data"),
                ranking=args.ranking,
                max_holdings=top,
                min_yoy_growth=yoy,
            )

            def weight_fn(date, current_weights, nav, _s=strategy):
                ts = pd.Timestamp(date)
                feed.set_dynamic_universe(pool_cache.get(ts, []))
                portfolio = VerifyPortfolio(nav)
                for sym, w in current_weights.items():
                    portfolio.positions[sym] = VerifyPosition(value=w * nav)
                ctx = VerifyContext(feed, portfolio, ts)
                return _s.on_bar(ctx)

            nav, stats = simulate_nav(panel, rebalance_dates, weight_fn,
                                      buy_cost_bps=17.0, sell_cost_bps=47.0, sim_idx=sim_idx)
            m = compute_metrics(nav)
            rows.append({
                "max_holdings": top,
                "min_yoy_growth": yoy,
                "total_return": m["total_return"],
                "cagr": m["cagr"],
                "sharpe": m["sharpe"],
                "max_drawdown": m["max_drawdown"],
                "annual_turnover": stats["annual_turnover"],
            })
            logger.info("  -> total=%+.2f%% CAGR=%+.2f%% Sharpe=%.2f MDD=%.2f%%",
                        m["total_return"]*100, m["cagr"]*100, m["sharpe"], m["max_drawdown"]*100)

    df = pd.DataFrame(rows)
    df.to_csv(out_dir / "grid.csv", index=False)

    # 透視表：以 Sharpe 為主指標
    pivot_sharpe = df.pivot(index="max_holdings", columns="min_yoy_growth", values="sharpe")
    pivot_cagr = df.pivot(index="max_holdings", columns="min_yoy_growth", values="cagr")
    pivot_mdd = df.pivot(index="max_holdings", columns="min_yoy_growth", values="max_drawdown")

    summary = {
        "grid": {
            "max_holdings": grid_top,
            "min_yoy_growth": grid_yoy,
        },
        "n_combos": len(rows),
        "sharpe_min": float(df["sharpe"].min()),
        "sharpe_max": float(df["sharpe"].max()),
        "sharpe_mean": float(df["sharpe"].mean()),
        "sharpe_std": float(df["sharpe"].std()),
        "cagr_min": float(df["cagr"].min()),
        "cagr_max": float(df["cagr"].max()),
        "cagr_mean": float(df["cagr"].mean()),
        "all_sharpe_positive": bool((df["sharpe"] > 0).all()),
        "robustness_verdict": (
            "robust" if (df["sharpe"] > 0).all() and df["sharpe"].std() < 0.3
            else "moderate" if (df["sharpe"] > 0).all()
            else "fragile"
        ),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=float), encoding="utf-8")

    print("\n" + "=" * 60)
    print("PARAMETER SENSITIVITY GRID (Sharpe)")
    print("=" * 60)
    print(pivot_sharpe.round(2).to_string())
    print()
    print("CAGR (%):")
    print((pivot_cagr * 100).round(2).to_string())
    print()
    print("Max Drawdown (%):")
    print((pivot_mdd * 100).round(2).to_string())
    print()
    print(f"Sharpe range: [{summary['sharpe_min']:.2f}, {summary['sharpe_max']:.2f}]  "
          f"std={summary['sharpe_std']:.2f}")
    print(f"All Sharpe > 0: {summary['all_sharpe_positive']}")
    print(f"Robustness verdict: {summary['robustness_verdict']}")
    print(f"\nOutputs: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
