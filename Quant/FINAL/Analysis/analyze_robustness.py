"""Robustness 分析 — 對主驗證的策略 NAV 做後處理檢定。

需要先跑過 `python verify_strategy.py` 產生 `results/_verify/strategy_nav_net.csv`。

三個檢定：

1. **逐年 walk-forward**：把 8 年 NAV 切 8 個年度區間，分別算 Sharpe / 報酬
   真有 alpha 的策略，多數年度 Sharpe 應 > 0
   過擬合策略，可能某 1-2 年很強，其他年份零或負

2. **Deflated Sharpe Ratio (DSR)**：Bailey & Lopez de Prado 2014
   修正多重檢定偏差。研究紀錄做過 ~25 個實驗，加上參數網格 9 組 → N=34
   DSR > 0.95 = 95% 信心 alpha 不是運氣
   DSR < 0.5 = 顯著性極低

3. **同池殘差 alpha**：策略月報酬對「隨機投組中位數」(random p50) 月報酬迴歸
   - 為什麼不用 0050？0050 ~55% 是 TSMC 一檔，集中度跟策略（10% 上限 × 15 檔）
     根本不在同一檔次。對 0050 迴歸測到的 beta 主要反映 TSMC 集中度差異，
     不是「策略加了什麼價值」
   - random p50 = 同池、同分散約束、無技能；對它迴歸的 alpha 才是「策略
     比同條件下的無技能投組多賺多少」
   - intercept (alpha) > 0 且 t > 2 → 有真正的 stock-picking alpha
   - 同時也跑 vs 0050 作為「相對市場」的參考

Usage:
    python analyze_robustness.py
"""

from __future__ import annotations

import json
import logging
import sys
from math import sqrt, erf
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent


def yearly_walkforward(nav: pd.Series) -> pd.DataFrame:
    """每個日曆年的 Sharpe / total return / MDD。"""
    rows = []
    for year, year_nav in nav.groupby(nav.index.year):
        if len(year_nav) < 30:
            continue
        rets = year_nav.pct_change().dropna()
        if len(rets) < 2:
            continue
        total = year_nav.iloc[-1] / year_nav.iloc[0] - 1
        vol = rets.std() * sqrt(252)
        sharpe = (rets.mean() * 252) / vol if vol > 0 else 0
        rolling_max = year_nav.cummax()
        dd = (year_nav - rolling_max) / rolling_max
        mdd = -float(dd.min())
        rows.append({
            "year": int(year),
            "total_return": float(total),
            "sharpe": float(sharpe),
            "max_drawdown": mdd,
            "n_days": int(len(year_nav)),
        })
    return pd.DataFrame(rows)


def deflated_sharpe(observed_sharpe: float, daily_returns: pd.Series, n_trials: int) -> dict:
    """DSR per Bailey & Lopez de Prado (2014).

    estimated_sharpe_via_trials_max ~ E[max(SR_1, ..., SR_N)]
    DSR = Phi(SR_observed - SR_max_estimate) / sqrt(var) where var includes
    skew and kurtosis corrections of the observed return series.
    """
    if len(daily_returns) < 30:
        return {"dsr": None, "note": "insufficient data"}

    T = len(daily_returns)
    skew = float(daily_returns.skew())
    kurt = float(daily_returns.kurtosis())  # excess kurtosis (Pandas convention)

    # Observed annualised Sharpe in per-period terms (daily)
    sr_per_period = observed_sharpe / sqrt(252)

    # Variance of the Sharpe estimator (Mertens 2002)
    sr_var = (1 - sr_per_period * skew + (kurt / 4.0) * sr_per_period**2) / max(T - 1, 1)
    sr_std = sqrt(max(sr_var, 1e-12))

    # Expected max Sharpe under N independent null trials (Bailey & Lopez de Prado)
    # E[max] ≈ sqrt(2 * ln(N)) * sigma_SR (per trial)
    # Using Euler-Mascheroni constant correction:
    gamma = 0.5772156649
    if n_trials <= 1:
        sr_max_expected = 0.0
    else:
        sr_max_expected = sr_std * (
            (1 - gamma) * _norm_inv(1 - 1.0 / n_trials)
            + gamma * _norm_inv(1 - 1.0 / (n_trials * np.e))
        )

    # DSR
    z = (sr_per_period - sr_max_expected) / sr_std
    dsr = float(_norm_cdf(z))

    return {
        "observed_sharpe_annual": float(observed_sharpe),
        "n_trials_assumed": n_trials,
        "sr_max_expected": float(sr_max_expected) * sqrt(252),
        "skew": skew,
        "excess_kurtosis": kurt,
        "z_score": float(z),
        "dsr": dsr,
        "interpretation": (
            "highly significant (>95%)" if dsr > 0.95
            else "significant (>80%)" if dsr > 0.80
            else "marginal (>50%)" if dsr > 0.50
            else "not significant"
        ),
    }


def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + erf(x / sqrt(2)))


def _norm_inv(p: float) -> float:
    """Quantile of standard normal — Beasley-Springer-Moro approximation."""
    if p <= 0 or p >= 1:
        return 0.0
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow = 0.02425
    phigh = 1 - plow
    if p < plow:
        q = sqrt(-2 * np.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / (
                ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1))
    if p > phigh:
        q = sqrt(-2 * np.log(1-p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / (
                ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1))
    q = p - 0.5
    r = q*q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (
            (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1))


def market_residual_alpha(strategy_nav: pd.Series, market_nav: pd.Series) -> dict:
    """OLS of strategy monthly returns on market monthly returns.
    Returns alpha + beta + t-stat + R²."""
    # Resample to monthly returns
    s_m = strategy_nav.resample("M").last().pct_change().dropna()
    m_m = market_nav.resample("M").last().pct_change().dropna()
    common = s_m.index.intersection(m_m.index)
    s_m = s_m.loc[common]
    m_m = m_m.loc[common]
    if len(s_m) < 12:
        return {"note": "insufficient monthly observations"}

    # Manual OLS (avoid scipy dependency)
    x = m_m.values
    y = s_m.values
    n = len(x)
    x_mean = x.mean()
    y_mean = y.mean()
    sx2 = ((x - x_mean) ** 2).sum()
    sxy = ((x - x_mean) * (y - y_mean)).sum()
    beta = sxy / sx2 if sx2 > 0 else 0.0
    alpha = y_mean - beta * x_mean
    y_pred = alpha + beta * x
    residuals = y - y_pred
    rss = (residuals ** 2).sum()
    tss = ((y - y_mean) ** 2).sum()
    r_squared = 1 - rss / tss if tss > 0 else 0.0
    sigma2 = rss / max(n - 2, 1)
    se_alpha = sqrt(sigma2 * (1.0 / n + x_mean ** 2 / sx2)) if sx2 > 0 else 0.0
    t_alpha = alpha / se_alpha if se_alpha > 0 else 0.0
    # Annualise alpha
    annual_alpha = (1 + alpha) ** 12 - 1

    return {
        "n_months": int(n),
        "alpha_monthly": float(alpha),
        "alpha_annualised": float(annual_alpha),
        "alpha_t_stat": float(t_alpha),
        "alpha_significant_t2": bool(abs(t_alpha) > 2),
        "beta": float(beta),
        "r_squared": float(r_squared),
        "interpretation": (
            "significant alpha after market exposure" if abs(t_alpha) > 2
            else "weak alpha — likely just market beta" if abs(t_alpha) < 1
            else "marginal"
        ),
    }


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--verify-dir", default=str(ROOT / "results" / "_verify"),
                   help="Directory holding strategy_nav_net.csv + benchmarks/ from verify_strategy.py")
    p.add_argument("--out", default=str(ROOT / "results" / "_robustness"))
    args = p.parse_args()

    verify_dir = Path(args.verify_dir)
    if not (verify_dir / "strategy_nav_net.csv").exists():
        raise SystemExit(
            f"Missing {verify_dir/'strategy_nav_net.csv'}. "
            "Run `python verify_strategy.py` first."
        )

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    strategy_nav = pd.read_csv(verify_dir / "strategy_nav_net.csv",
                              parse_dates=["date"]).set_index("date")["nav"]
    bench_0050 = pd.read_csv(verify_dir / "benchmarks" / "0050.csv",
                            parse_dates=["date"]).set_index("date")["nav"]

    # Random p50 — "same-pool, same-constraint, no-skill" benchmark.
    # This is the proper baseline for residual-alpha purposes (0050 has 55% TSMC,
    # not comparable to a 10%-capped 15-stock portfolio).
    rp = pd.read_csv(verify_dir / "benchmarks" / "random_portfolios_net.csv",
                    parse_dates=["date"]).set_index("date")
    bench_rp50 = rp["p50"]

    rets = strategy_nav.pct_change().dropna()
    n_years = (strategy_nav.index[-1] - strategy_nav.index[0]).days / 365.25
    total = strategy_nav.iloc[-1] / strategy_nav.iloc[0] - 1
    cagr = (1 + total) ** (1 / n_years) - 1
    vol = rets.std() * sqrt(252)
    sharpe = cagr / vol if vol > 0 else 0

    logger.info("Loaded strategy NAV: %d days, CAGR=%.2f%%, Sharpe=%.2f",
                len(strategy_nav), cagr * 100, sharpe)

    # 1. Walk-forward yearly
    logger.info("Computing yearly walk-forward...")
    yearly = yearly_walkforward(strategy_nav)
    yearly.to_csv(out_dir / "yearly.csv", index=False)
    pos_years = int((yearly["sharpe"] > 0).sum())

    # 2. DSR — assume N = 25 historical experiments + 9 grid points = 34
    logger.info("Computing DSR (N=34 trials)...")
    dsr = deflated_sharpe(sharpe, rets, n_trials=34)

    # 3a. Same-pool residual alpha (PROPER test) — vs random p50
    logger.info("Computing same-pool residual alpha vs random p50...")
    alpha_rp50 = market_residual_alpha(strategy_nav, bench_rp50)

    # 3b. Market-relative alpha (auxiliary) — vs 0050 (note: not strictly
    # comparable due to concentration mismatch, but informative for context)
    logger.info("Computing market-relative alpha vs 0050 (auxiliary)...")
    alpha_0050 = market_residual_alpha(strategy_nav, bench_0050)

    summary = {
        "strategy_overall": {
            "n_years": float(n_years),
            "total_return": float(total),
            "cagr": float(cagr),
            "sharpe": float(sharpe),
            "volatility_annual": float(vol),
        },
        "yearly_walkforward": {
            "years": yearly.to_dict(orient="records"),
            "n_years_positive_sharpe": pos_years,
            "n_years_total": int(len(yearly)),
            "win_rate": float(pos_years / max(len(yearly), 1)),
        },
        "deflated_sharpe": dsr,
        "alpha_vs_random_p50_same_pool": alpha_rp50,
        "alpha_vs_0050_market_index_aux": alpha_0050,
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, default=float), encoding="utf-8"
    )

    print("\n" + "=" * 60)
    print("ROBUSTNESS ANALYSIS")
    print("=" * 60)

    print("\n1. Yearly Walk-Forward Sharpe:")
    for r in yearly.itertuples():
        print(f"  {r.year}:  total={r.total_return*100:+7.2f}%  Sharpe={r.sharpe:+5.2f}  MDD={r.max_drawdown*100:5.2f}%")
    print(f"  Years with Sharpe > 0: {pos_years} / {len(yearly)}")

    print("\n2. Deflated Sharpe Ratio (N=34 assumed trials):")
    print(f"  Observed Sharpe (annual): {dsr['observed_sharpe_annual']:.2f}")
    print(f"  Expected max under nulls: {dsr['sr_max_expected']:.2f}")
    print(f"  Z-score:                  {dsr['z_score']:.2f}")
    print(f"  DSR:                      {dsr['dsr']:.3f}  ({dsr['interpretation']})")

    print("\n3a. Same-Pool Residual Alpha (vs Random p50, monthly OLS) [PROPER TEST]:")
    if "alpha_t_stat" in alpha_rp50:
        print(f"  Alpha (annualised): {alpha_rp50['alpha_annualised']*100:+.2f}%")
        print(f"  Alpha t-stat:       {alpha_rp50['alpha_t_stat']:+.2f}")
        print(f"  Beta vs Random p50: {alpha_rp50['beta']:.2f}")
        print(f"  R-squared:          {alpha_rp50['r_squared']:.2f}")
        print(f"  Verdict:            {alpha_rp50['interpretation']}")

    print("\n3b. Market-Relative Alpha (vs 0050, auxiliary):")
    if "alpha_t_stat" in alpha_0050:
        print(f"  Alpha (annualised): {alpha_0050['alpha_annualised']*100:+.2f}%")
        print(f"  Alpha t-stat:       {alpha_0050['alpha_t_stat']:+.2f}")
        print(f"  Beta vs 0050:       {alpha_0050['beta']:.2f}  (TSMC-driven, not strictly comparable)")
        print(f"  R-squared:          {alpha_0050['r_squared']:.2f}")

    print(f"\nOutputs: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
