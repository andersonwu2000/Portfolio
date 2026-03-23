"""
回測效能基準測試 — 測量不同配置下的執行時間與記憶體使用量。

用法：
    python scripts/benchmark.py
    python scripts/benchmark.py --quick     # 僅測試小型配置
"""

from __future__ import annotations

import argparse
import gc
import logging
import sys
import time
import tracemalloc
from dataclasses import dataclass
from pathlib import Path

# 確保專案根目錄在路徑中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest.engine import BacktestConfig, BacktestEngine


@dataclass
class BenchmarkCase:
    """單一測試案例。"""
    name: str
    universe: list[str]
    years: int
    start: str
    end: str


@dataclass
class BenchmarkResult:
    """測試結果。"""
    name: str
    symbols: int
    years: int
    elapsed_sec: float
    peak_memory_mb: float
    trading_days: int
    total_trades: int
    status: str  # "ok" 或 error message


# ── 測試配置 ──────────────────────────────────────────────────

US_5 = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]

US_20 = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META",
    "TSLA", "NVDA", "JPM", "V", "JNJ",
    "WMT", "PG", "MA", "UNH", "HD",
    "DIS", "PYPL", "ADBE", "NFLX", "CRM",
]

US_50 = US_20 + [
    "INTC", "CSCO", "PEP", "ABT", "KO",
    "NKE", "MRK", "T", "VZ", "ABBV",
    "ORCL", "ACN", "AVGO", "TXN", "QCOM",
    "COST", "NEE", "DHR", "BMY", "LIN",
    "MDT", "AMGN", "PM", "RTX", "HON",
    "UPS", "IBM", "GE", "LOW", "SBUX",
]

FULL_CASES: list[BenchmarkCase] = [
    BenchmarkCase("5sym_1y", US_5, 1, "2024-01-01", "2024-12-31"),
    BenchmarkCase("5sym_3y", US_5, 3, "2022-01-01", "2024-12-31"),
    BenchmarkCase("5sym_5y", US_5, 5, "2020-01-01", "2024-12-31"),
    BenchmarkCase("20sym_1y", US_20, 1, "2024-01-01", "2024-12-31"),
    BenchmarkCase("20sym_3y", US_20, 3, "2022-01-01", "2024-12-31"),
    BenchmarkCase("20sym_5y", US_20, 5, "2020-01-01", "2024-12-31"),
    BenchmarkCase("50sym_1y", US_50, 1, "2024-01-01", "2024-12-31"),
    BenchmarkCase("50sym_3y", US_50, 3, "2022-01-01", "2024-12-31"),
    BenchmarkCase("50sym_5y", US_50, 5, "2020-01-01", "2024-12-31"),
]

QUICK_CASES: list[BenchmarkCase] = [
    BenchmarkCase("5sym_1y", US_5, 1, "2024-01-01", "2024-12-31"),
    BenchmarkCase("5sym_3y", US_5, 3, "2022-01-01", "2024-12-31"),
    BenchmarkCase("20sym_1y", US_20, 1, "2024-01-01", "2024-12-31"),
]


def run_benchmark(case: BenchmarkCase) -> BenchmarkResult:
    """執行單一基準測試。"""
    gc.collect()
    tracemalloc.start()

    config = BacktestConfig(
        universe=case.universe,
        start=case.start,
        end=case.end,
        initial_cash=10_000_000.0,
        rebalance_freq="weekly",
    )

    engine = BacktestEngine()

    try:
        from strategies.momentum import MomentumStrategy
        strategy = MomentumStrategy()

        t0 = time.perf_counter()
        result = engine.run(strategy, config)
        elapsed = time.perf_counter() - t0

        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        trading_days = len(result.nav_series)
        total_trades = result.total_trades

        return BenchmarkResult(
            name=case.name,
            symbols=len(case.universe),
            years=case.years,
            elapsed_sec=round(elapsed, 2),
            peak_memory_mb=round(peak / 1024 / 1024, 1),
            trading_days=trading_days,
            total_trades=total_trades,
            status="ok",
        )
    except Exception as e:
        tracemalloc.stop()
        return BenchmarkResult(
            name=case.name,
            symbols=len(case.universe),
            years=case.years,
            elapsed_sec=0,
            peak_memory_mb=0,
            trading_days=0,
            total_trades=0,
            status=str(e)[:60],
        )


def print_results(results: list[BenchmarkResult]) -> None:
    """輸出結果表格。"""
    header = f"{'Case':<15} {'Syms':>5} {'Years':>5} {'Time(s)':>8} {'Mem(MB)':>8} {'Days':>6} {'Trades':>7} {'Status':<20}"
    sep = "-" * len(header)

    print("\n" + "=" * len(header))
    print("BACKTEST PERFORMANCE BENCHMARK")
    print("=" * len(header))
    print(header)
    print(sep)

    for r in results:
        status = r.status if r.status != "ok" else "ok"
        print(
            f"{r.name:<15} {r.symbols:>5} {r.years:>5} "
            f"{r.elapsed_sec:>8.2f} {r.peak_memory_mb:>8.1f} "
            f"{r.trading_days:>6} {r.total_trades:>7} {status:<20}"
        )

    print(sep)

    # 摘要
    ok_results = [r for r in results if r.status == "ok"]
    if ok_results:
        total_time = sum(r.elapsed_sec for r in ok_results)
        max_mem = max(r.peak_memory_mb for r in ok_results)
        print(f"\nTotal time: {total_time:.1f}s | Peak memory: {max_mem:.1f} MB | Cases: {len(ok_results)}/{len(results)} passed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest performance benchmark")
    parser.add_argument("--quick", action="store_true", help="Run only quick cases")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)

    cases = QUICK_CASES if args.quick else FULL_CASES
    print(f"Running {len(cases)} benchmark cases {'(quick mode)' if args.quick else ''}...")

    results: list[BenchmarkResult] = []
    for i, case in enumerate(cases):
        print(f"  [{i+1}/{len(cases)}] {case.name} ({len(case.universe)} symbols × {case.years}y)...", end="", flush=True)
        result = run_benchmark(case)
        results.append(result)
        if result.status == "ok":
            print(f" {result.elapsed_sec:.1f}s")
        else:
            print(f" FAILED: {result.status}")

    print_results(results)


if __name__ == "__main__":
    main()
