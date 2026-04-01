# 從因子到策略驗證：量化回測系統實戰

本專案展示一個完整的量化交易開發流程 — 從**一個已經發現的因子**開始，到**建構可回測的策略**，再到**用統計方法嚴格驗證**。

以台股營收加速度因子（`revenue_acceleration`）為主軸，帶你走過量化策略開發的三個核心階段。

---

## 目錄

- [三個階段總覽](#三個階段總覽)
- [安裝與環境](#安裝與環境)
- [Stage 1：因子 — 我們已經找到的訊號](#stage-1因子--我們已經找到的訊號)
- [Stage 2：策略 — 從因子到投組權重](#stage-2策略--從因子到投組權重)
- [Stage 3：驗證 — 回測與統計檢定](#stage-3驗證--回測與統計檢定)
- [專案結構](#專案結構)
- [系統架構](#系統架構)

---

## 三個階段總覽

```
Stage 1                Stage 2              Stage 3
因子（已產出）           策略                  驗證
────────────────── → ────────────────── → ──────────────────
revenue_acceleration  Alpha Pipeline        BacktestEngine
= avg_3m / avg_12m    ↓                    ↓
                     中性化 + 標準化       模擬撮合 + 成本
已知：                 ↓                    ↓
ICIR = 0.44~0.58     投組建構 → 權重       15+ 項統計檢定
67% 勝率                                    ↓
10 年穩定                                 Sharpe, MDD,
                                          PBO, DSR ...
                                            ↓
                                          通過 → 可部署
                                          不通過 → 回頭修改
```

---

## 安裝與環境

**環境需求：** Python 3.11+

```bash
pip install pandas numpy scipy yfinance pydantic structlog
# 選用：投組最佳化功能
pip install cvxpy
```

---

## Stage 1：因子 — 我們已經找到的訊號

### 什麼是因子？

因子是一個**可量化的數值訊號**，用來預測股票未來報酬。好的因子能在統計上區分「未來會漲」和「未來會跌」的股票。

### revenue_acceleration 因子

**定義位置：** `src/strategy/factors/fundamental.py`

```python
def revenue_acceleration_factor(acceleration: float) -> float:
    """營收加速度因子：近 3 個月平均營收 / 近 12 個月平均營收。

    比率 > 1 → 近期營收高於長期平均，成長動能加速中
    比率 < 1 → 近期營收低於長期平均，成長動能減速
    """
    return max(0.0, min(acceleration, 5.0))  # 截斷至 [0, 5]
```

**計算方式：**

```python
# 取得某支股票的月營收資料（自動套用 40 天延遲，避免前視偏差）
revenue_data = ctx.get_revenue(symbol, lookback_months=24)

# 計算因子
rev_3m = revenue_data["revenue"].iloc[-3:].mean()   # 近 3 個月平均
rev_12m = revenue_data["revenue"].iloc[-12:].mean()  # 近 12 個月平均
acceleration = rev_3m / rev_12m                       # 加速度比率
```

### 這個因子的實證結果

| 指標 | 數值 | 意義 |
|------|------|------|
| ICIR (20 日) | +0.438 | 預測未來 20 天報酬的穩定度，> 0.15 算有效 |
| ICIR (60 日) | +0.582 | 預測未來 60 天更強，適合月頻再平衡 |
| 勝率 | 67.3% | 有 2/3 的月份 IC 為正 |
| 穩定性 | 10/10 年為正 | 2016-2025 每年都有效，沒有衰退 |

### 為什麼是營收？

| 結論 | 證據 |
|------|------|
| 台股 Alpha 在營收，不在價格 | 4 個營收因子 ICIR > 0.15；66 個價格因子全 < 0.3 |
| revenue_acceleration 最強 | 在所有測試過的因子中 ICIR 最高 |
| 成本是台股瓶頸 | 換手率 > 10% 的因子全部虧損 |

> **40 天延遲**：台灣上市公司月營收最遲於次月 10 號公布。系統強制加 40 天延遲，確保回測不會使用到「當時還不知道」的資訊。這是量化研究中最隱蔽的錯誤 — Look-Ahead Bias（前視偏差）。

---

## Stage 2：策略 — 從因子到投組權重

有了因子之後，下一步是將它轉化為**可執行的交易指令**。核心問題是：因子值告訴你「哪些股票好」，但你還需要決定「買多少」。

### 路徑 A：直接寫策略（適合理解原理）

繼承 `Strategy` 基類，在 `on_bar()` 中用因子決定買什麼、買多少：

```python
from src.strategy.base import Strategy, Context

class RevenueAccelerationStrategy(Strategy):
    def name(self) -> str:
        return "revenue_acceleration"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        """每個交易日呼叫一次，回傳目標權重。"""
        candidates = []

        for symbol in ctx.universe():
            rev = ctx.get_revenue(symbol, lookback_months=24)
            if rev is None or len(rev) < 12:
                continue

            rev_3m = rev["revenue"].iloc[-3:].mean()
            rev_12m = rev["revenue"].iloc[-12:].mean()
            acceleration = rev_3m / rev_12m

            if acceleration > 1.0:  # 動能加速中
                candidates.append((symbol, acceleration))

        # 依加速度排序，取前 15 名，等權配置
        candidates.sort(key=lambda x: x[1], reverse=True)
        top = candidates[:15]

        if not top:
            return {}  # 沒有符合條件的標的，空倉

        weight = 1.0 / len(top)
        return {symbol: weight for symbol, _ in top}
```

**關鍵設計：**
- `on_bar()` 回傳 `dict[str, float]` — 標的代碼 → 目標權重
- 權重為佔 NAV 的比例（0.10 = 10%）
- 沒出現在 dict 中的持股會被自動平倉
- `Context` 保證所有資料截斷至當前日期（不可能偷看未來）

### 路徑 B：Alpha Pipeline（適合系統化研究）

Alpha Pipeline 自動處理因子從「原始數值」到「投組權重」的全部步驟：

```python
from src.alpha.pipeline import AlphaConfig, FactorSpec
from src.alpha.strategy import AlphaStrategy

config = AlphaConfig(
    factors=[
        FactorSpec("revenue_acceleration", direction=1),  # 值越高越好
    ],
    standardize_method="zscore",     # 跨股票標準化
    neutralize_method="market",      # 移除市場 Beta
    combine_method="equal",          # 多因子等權合成
    holding_period=20,               # 每 20 個交易日再平衡
)

# AlphaStrategy 將 pipeline 結果包裝成 Strategy 介面
strategy = AlphaStrategy(config=config)
```

**Pipeline 內部流程：**

```
因子原始值（每支股票一個數字）
  → 縮尾處理（去除極端值，避免少數異常值主導）
    → Z-score 標準化（讓不同因子的量綱可以比較）
      → 市場中性化（移除大盤漲跌的影響，只留個股差異）
        → 因子合成（如果用多個因子，在這裡加權合成）
          → 投組建構（決定每支股票的權重）
            → 目標權重 dict → 給回測引擎或實盤執行
```

**為什麼需要這些步驟？**
- **縮尾**：一支營收暴漲 10 倍的股票不應主導整個投組
- **標準化**：讓「營收加速度 1.5」和「ROE 15%」可以放在同一個框架比較
- **中性化**：大盤漲 5% 的那個月，所有股票營收都好看 — 中性化移除這個共同因素

### 實際範例：`strategies/revenue_momentum.py`

本專案附帶一個完整的營收動量策略實作，展示了：
- 營收資料的預載入與快取機制
- 40 天延遲的實作方式
- 多條件篩選（加速度 > 1、YoY 成長、均線確認、成交量門檻）
- 三種權重計算方式（訊號加權 / 等權 / 風險平價）

---

## Stage 3：驗證 — 回測與統計檢定

有了策略，必須回答兩個問題：
1. **歷史上能賺錢嗎？** → 回測引擎
2. **統計上可靠嗎？不是過擬合嗎？** → Validator

### 3.1 回測引擎

回測引擎模擬策略在歷史市場中的真實表現，包含所有交易成本：

```python
from src.backtest.engine import BacktestEngine, BacktestConfig

config = BacktestConfig(
    universe=["2330.TW", "2317.TW", "2454.TW", ...],  # 交易標的
    start="2018-01-01",
    end="2025-06-30",
    initial_cash=10_000_000,       # 初始資金 1,000 萬
    rebalance_freq="monthly",      # 月頻再平衡
    commission_rate=0.001425,      # 台股手續費 0.1425%
    tax_rate=0.003,                # 台股證交稅 0.3%（賣出收取）
    impact_model="sqrt",           # 根號衝擊滑價模型
    fractional_shares=False,       # 整張交易（1,000 股一張）
)

engine = BacktestEngine()
result = engine.run(strategy, config)

print(f"年化報酬 (CAGR):  {result.annual_return:+.2%}")
print(f"Sharpe Ratio:     {result.sharpe:.3f}")
print(f"最大回撤 (MDD):   {result.max_drawdown:.2%}")
print(f"總交易筆數:       {result.total_trades}")
print(f"勝率:             {result.win_rate:.1%}")
```

**引擎模擬的真實市場行為：**

| 項目 | 說明 |
|------|------|
| 手續費 | 買賣雙向各收 0.1425% |
| 證交稅 | 賣出時收 0.3% |
| 滑價 | 根號衝擊模型：買量越大，成交價越差 |
| 漲跌停 | 觸及 ±10% 限制時拒絕下單 |
| 先賣後買 | 避免「要買的錢卡在還沒賣的股票裡」 |
| 整張 vs 零股 | 整張 1,000 股，零股有額外滑價 |
| Kill Switch | 單日虧損超過閾值時強制全部平倉 |

### 3.2 回測結果怎麼看

`BacktestResult` 包含 20+ 種績效指標：

| 指標 | 白話意義 | 怎麼判斷好壞 |
|------|---------|-------------|
| **CAGR** | 每年平均賺多少（複利） | > 8% 是基本門檻，考慮台股大盤約 8-10% |
| **Sharpe Ratio** | 每承受 1 單位風險，換到多少報酬 | > 0.7 算不錯，> 1.0 很好，> 2.0 要懷疑過擬合 |
| **Sortino Ratio** | 同 Sharpe 但只計虧損波動 | 比 Sharpe 更保守，對下檔風險敏感 |
| **Calmar Ratio** | 年化報酬 / 最大回撤 | 賺 20% 但曾虧 40% → Calmar = 0.5 |
| **Max Drawdown** | 從高點到低谷最多虧多少 | < 30% 舒適，< 40% 可接受，> 50% 危險 |
| **VaR(95%)** | 正常狀況下一天最多虧多少 | 例如 -2% 表示 95% 的天數虧損不超過 2% |
| **CVaR(95%)** | 最慘那 5% 的天數平均虧多少 | 衡量尾部風險，比 VaR 更嚴格 |
| **Win Rate** | 獲利交易的比例 | 50-60% 已不錯；低勝率但單筆獲利大也行 |
| **Turnover** | 每年交易量佔 NAV 多少 | 越高手續費越重，台股 > 10x 幾乎不可能獲利 |

### 3.3 Validator — 15+ 項統計檢定

回測績效好看 ≠ 策略有效。Validator 用統計方法回答「**這個績效是真的嗎？**」

```python
from src.backtest.validator import StrategyValidator, ValidationConfig

validator = StrategyValidator(ValidationConfig(
    min_sharpe=0.7,
    max_drawdown=0.40,
    min_cagr=0.08,
    n_trials=5,
))

report = validator.validate(strategy, universe, "2017-01-01", "2025-06-30")
print(report.summary())
```

**15+ 項檢查完整解說：**

#### 基本績效門檻（第 1-6 項）

| # | 檢查項目 | 門檻 | 在問什麼 |
|---|---------|------|---------|
| 1 | 投資域大小 | ≥ 50 支 | 只挑 3 支股票回測當然好看，但沒有統計意義 |
| 2 | CAGR | ≥ 8% | 扣除所有成本後，年化報酬夠嗎？ |
| 3 | Sharpe | ≥ 0.7 | 風險調整後報酬是否足夠？ |
| 4 | 最大回撤 | ≤ 40% | 你真的受得了帳面虧 40% 嗎？ |
| 5 | 成本比率 | < Alpha 的 50% | 交易成本不能吃掉超過一半的利潤 |
| 6 | 2× 成本安全邊際 | 加倍成本後仍獲利 | 實際成本往往比模擬高，留安全邊際 |

#### 防過擬合檢定（第 7-12 項）— 最重要

> **過擬合**：策略在歷史數據上表現很好，但在未來會失效。原因是策略「記住了歷史」，而不是「學到了規律」。

| # | 檢查項目 | 門檻 | 在問什麼 |
|---|---------|------|---------|
| 7 | **前推一致性** | ≥ 60% 窗口為正 | 把歷史切成多段，每段都用前面的資料訓練、後面的資料測試。60% 以上的「後面」都賺錢嗎？ |
| 8 | **Deflated Sharpe** | ≥ 0.70 | 你試了 100 個策略選最好的那個，Sharpe 1.5 可能只是運氣。DSR 校正這個「多重檢定」偏差 |
| 9 | **Bootstrap 信心** | P(Sharpe>0) ≥ 80% | 從歷史報酬中隨機重抽 1,000 次，看 Sharpe 的分佈。80% 以上都 > 0 才算可靠 |
| 10 | **樣本外 Sharpe** | ≥ 0.3 | 保留最近 1.5 年資料不讓策略看到，在這段「策略沒見過的資料」上表現如何？ |
| 11 | **vs 等權基準** | ≥ 50% 窗口勝出 | 你的策略比「買所有股票各買一點」好嗎？如果連這個都贏不了，因子沒有用 |
| 12 | **構建敏感度 (PBO)** | ≤ 50% | 換一種投組建構方法（等權→風險平價），結果還是好的嗎？還是剛好挑到最有利的方法？ |

#### 穩健性檢查（第 13-17 項）

| # | 檢查項目 | 門檻 | 在問什麼 |
|---|---------|------|---------|
| 13 | 最差年度報酬 | ≥ -30% | 最慘的一年也不至於虧光 |
| 14 | 近期 Sharpe | ≥ 0% | 策略最近一年還有效嗎？有些因子會隨時間衰退 |
| 15 | 市場相關性 | \|corr\| ≤ 0.80 | 你是有獨立的 Alpha，還是只是在跟大盤？ |
| 16 | CVaR(95%) | ≥ -5%（日） | 尾部風險（最慘的日子）可接受嗎？ |
| 17 | 排列檢定 | p < 0.10 | 把報酬序列打亂重排，如果隨機數據也能得到一樣好的結果，那你的訊號就不是真的 |

### 3.4 防過擬合工具箱

| 方法 | 解決什麼問題 | 原理 |
|------|-------------|------|
| **PBO (CSCV)** | 直接計算過擬合機率 | 把歷史切成多段，用組合數學窮舉所有 IS/OOS 分割 (Bailey 2017) |
| **前推分析** | 測試樣本外穩定性 | 滾動窗口：用過去 2 年訓練，預測下 1 年，不斷前推 |
| **Deflated Sharpe** | 修正多重檢定偏差 | 試 N 個策略取最好的，需要修正 Sharpe 的顯著性 (Bailey 2014) |
| **Bootstrap** | 估計績效信心區間 | 不假設報酬分佈，直接從歷史重抽 1,000 次看結果有多穩定 |
| **排列檢定** | 證明訊號不是隨機的 | 打亂因子和報酬的對應關係，看策略是否仍有效 |

---

## 專案結構

```
System/
├── README.md                       ← 你正在讀的這份文件
│
├── strategies/
│   └── revenue_momentum.py         # 營收動量策略（完整範例）
│
├── src/
│   ├── strategy/                   # ❶ 因子與策略框架
│   │   ├── base.py                 #    Strategy 基類 + Context 介面
│   │   ├── factors/                #    因子實作
│   │   │   ├── fundamental.py      #    ← revenue_acceleration 在這裡
│   │   │   ├── technical.py        #    技術面因子（動量、波動率等）
│   │   │   └── research/           #    研究中的實驗因子
│   │   ├── research.py             #    IC / ICIR 計算工具
│   │   ├── engine.py               #    權重 → 訂單轉換
│   │   └── optimizer.py            #    投組最佳化（14 種方法）
│   │
│   ├── alpha/                      # ❷ Alpha 管線（因子 → 策略）
│   │   ├── pipeline.py             #    端到端因子研究
│   │   ├── strategy.py             #    AlphaStrategy 轉接器
│   │   ├── construction.py         #    投組建構（等權/訊號/風險平價）
│   │   ├── filter_strategy.py      #    條件篩選策略
│   │   ├── neutralize.py           #    市場/產業中性化
│   │   ├── cross_section.py        #    分位回測
│   │   └── regime.py               #    市況條件分析
│   │
│   ├── backtest/                   # ❸ 回測引擎與驗證
│   │   ├── engine.py               #    核心模擬迴圈
│   │   ├── validator.py            #    15+ 項驗證閘門
│   │   ├── analytics.py            #    績效指標計算
│   │   ├── overfitting.py          #    PBO 過擬合偵測
│   │   ├── walk_forward.py         #    前推分析
│   │   └── vectorized.py           #    向量化 PBO 回測
│   │
│   ├── core/models.py              # 核心資料模型（Order, Trade, Portfolio）
│   ├── data/                       # 資料層（Yahoo, FinMind）
│   ├── execution/broker/simulated.py  # SimBroker（擬真撮合）
│   ├── risk/                       # 風控（持倉上限、回撤熔斷等）
│   └── portfolio/                  # 投組分析（VaR, CVaR, 最佳化）
│
└── _extras/                        # 已移出的非核心檔案
```

---

## 系統架構

```
┌──────────────────────────────────────────────────────────────┐
│  Stage 1: 因子（已產出）                                      │
│                                                               │
│  revenue_acceleration = avg_3m / avg_12m                      │
│  ICIR = 0.44~0.58 | 勝率 67% | 10 年穩定                     │
│  (src/strategy/factors/fundamental.py)                        │
└────────────────────────┬─────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────┐
│  Stage 2: 策略                                               │
│                                                               │
│  路徑 A: 直接寫策略                路徑 B: Alpha Pipeline      │
│  Strategy.on_bar(ctx)             AlphaConfig + FactorSpec    │
│    → 計算因子                       → 縮尾 → 標準化           │
│    → 篩選 + 排序                    → 中性化 → 合成           │
│    → 回傳權重 dict                  → 投組建構 → 權重         │
│                                                               │
│  共同輸出：{"2330.TW": 0.08, "2317.TW": 0.07, ...}           │
└────────────────────────┬─────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────┐
│  Stage 3: 驗證                                               │
│                                                               │
│  BacktestEngine                    StrategyValidator           │
│  ┌────────────────────┐            ┌────────────────────┐    │
│  │ 每日模擬：          │            │ 15+ 項檢查：       │    │
│  │  策略產出權重       │            │                    │    │
│  │  → 風控審核         │            │ 基本門檻：         │    │
│  │  → SimBroker 撮合   │  ──結果──→ │  CAGR, Sharpe, MDD │    │
│  │    (手續費+稅+滑價) │            │                    │    │
│  │  → 記錄 NAV         │            │ 防過擬合：         │    │
│  │                    │            │  前推, PBO, DSR,   │    │
│  │ 輸出：20+ 績效指標  │            │  Bootstrap, 排列   │    │
│  └────────────────────┘            └───────┬────────────┘    │
│                                            │                  │
│                                     通過 ✅ → 可部署          │
│                                     不通過 ❌ → 回 Stage 2    │
└──────────────────────────────────────────────────────────────┘
```

---

## 授權

本專案僅供教育與研究用途。
