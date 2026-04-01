# Deep RL 自動交易策略

## 研究目的

用強化學習（PPO）訓練神經網路 Agent，自動學習台股投組的權重配置。與傳統因子策略比較：因子策略靠人定義規則，RL Agent 從數據中自己學。

## 架構

```
市場特徵 (OHLCV + 營收 + 法人)
  → Actor-Critic Network (Flax linen)
    → 目標權重 dict[str, float]
      → Portfolio 回測引擎（成本、滑價、風控）
        → 獎勵 (Sharpe ratio)
```

RL Agent 的輸出格式與 Quant System 的 `Strategy.on_bar()` 完全一致，可直接用同一套回測引擎和 Validator 評估。

## 實驗設計

| 項目 | 內容 |
|------|------|
| 演算法 | PPO (Proximal Policy Optimization) |
| 模型 | Actor-Critic，Flax linen API |
| 訓練環境 | BacktestEngine + SimBroker（含交易成本） |
| 獎勵函數 | 風險調整後報酬（Sharpe ratio） |
| Baseline | revenue_acceleration 因子策略 |
| 評估 | StrategyValidator 16 項統計檢定 |

## 附件

- `System/` — 共用的回測引擎（RL 環境 + 評估）
