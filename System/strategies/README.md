# 策略開發指南

本文件說明如何在此系統中開發自訂交易策略。完整的架構原理與進階主題（自訂因子、風控規則、資料層擴充等）請參考 [開發者指南](../doc/developer-guide-zh.md)。

## 快速上手

建立一支新策略只需三步：

### 第一步：建立策略檔案

在 `strategies/` 目錄下新增 Python 檔案，繼承 `Strategy` 並實作兩個方法：

```python
# strategies/my_strategy.py

from src.strategy.base import Strategy, Context
from src.strategy.factors import momentum
from src.strategy.optimizer import signal_weight, OptConstraints

class MyStrategy(Strategy):
    def __init__(self, lookback: int = 60):
        self.lookback = lookback

    def name(self) -> str:
        return "my_strategy"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        signals = {}
        for symbol in ctx.universe():
            bars = ctx.bars(symbol, lookback=self.lookback)
            if len(bars) < self.lookback:
                continue

            factor = momentum(bars, lookback=self.lookback, skip=5)
            if not factor.empty and factor["momentum"] > 0:
                signals[symbol] = factor["momentum"]

        return signal_weight(
            signals,
            OptConstraints(max_weight=0.10, max_total_weight=0.95),
        )
```

**重點**：`on_bar()` 回傳 `dict[str, float]` — key 是標的代碼，value 是目標權重（佔 NAV 的比例）。你只需決定「持有什麼、佔多少」，系統自動處理差異計算、風控檢查、訂單生成與執行。

### 第二步：註冊策略

在以下兩個檔案的 `_resolve_strategy()` 中加入你的策略：

**`src/cli/main.py`**（CLI 回測用）：
```python
from strategies.my_strategy import MyStrategy

mapping = {
    # ... 現有策略 ...
    "my_strategy": MyStrategy,
}
```

**`src/api/routes/backtest.py`**（API 回測用）：
```python
from strategies.my_strategy import MyStrategy

strategy_map = {
    # ... 現有策略 ...
    "my_strategy": MyStrategy,
}
```

### 第三步：執行回測

```bash
python -m src.cli.main backtest \
  --strategy my_strategy \
  -u AAPL -u MSFT -u GOOGL \
  --start 2023-01-01 --end 2024-12-31
```

---

## 現有策略參考

| 策略 | 檔案 | 因子 | 最佳化器 | 核心邏輯 |
|------|------|------|----------|----------|
| 動量 12-1 | `momentum.py` | `momentum` | `signal_weight` | 買入過去 12 月漲幅最大、跳過近 1 月的標的 |
| 營收動量 | `revenue_momentum.py` | `revenue_acceleration` | `signal_weight` | 營收 3M/12M 加速度 + 多條件篩選，月頻再平衡 |

建議先讀 `momentum.py`（結構最簡單），再讀 `revenue_momentum.py`（完整的真實策略）。

---

## 常見模式

### 模式一：單因子 + 信號加權

最常見的策略結構，適合大多數因子策略。參考 `momentum.py`。

```python
def on_bar(self, ctx: Context) -> dict[str, float]:
    signals = {}
    for symbol in ctx.universe():
        bars = ctx.bars(symbol, lookback=self.lookback)
        if len(bars) < self.lookback:
            continue
        factor = some_factor(bars)
        if not factor.empty and factor["value"] > self.threshold:
            signals[symbol] = factor["value"]

    return signal_weight(signals, OptConstraints(max_weight=0.10))
```

### 模式二：多因子複合評分

結合多個因子，適合更穩健的策略。

```python
def on_bar(self, ctx: Context) -> dict[str, float]:
    signals = {}
    for symbol in ctx.universe():
        bars = ctx.bars(symbol, lookback=300)
        mom = momentum(bars)
        rev = mean_reversion(bars)
        score = 0.6 * mom["momentum"] + 0.4 * rev["z_score"]
        if score > 0:
            signals[symbol] = score

    return signal_weight(signals, OptConstraints(max_weight=0.08))
```

### 模式三：風險平價配置

按波動率倒數分配，使每個標的貢獻相等的風險。

```python
def on_bar(self, ctx: Context) -> dict[str, float]:
    signals, vols = {}, {}
    for symbol in ctx.universe():
        bars = ctx.bars(symbol, lookback=100)
        signals[symbol] = some_score
        vol = volatility(bars)
        if not vol.empty:
            vols[symbol] = vol["volatility"]

    return risk_parity(signals, vols, OptConstraints(max_weight=0.20))
```

---

## 注意事項

1. **不要直接產生訂單** — `on_bar()` 只回傳目標權重，系統自動處理後續流程
2. **不要存取未來資料** — `ctx.bars()` 已保證時間因果律，但自行載入外部資料需自行確保
3. **lookback 要留餘量** — 請求的 `lookback` 應大於因子所需的最少 bar 數
4. **處理空值** — 因子函式在資料不足時回傳空 `Series`，務必檢查 `factor.empty`
5. **權重語義** — 正值 = 做多，負值 = 做空（需 `long_only=False`），不在 dict 中 = 平倉

---

## 深入了解

- **系統架構與完整流程** → [README.md](../README.md)
- **術語與公式解說** → [GLOSSARY.md](../GLOSSARY.md)
