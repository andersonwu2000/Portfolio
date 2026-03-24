# 多資產架構設計

> **目標**: 涵蓋台股、美股、ETF、期貨的投資組合研究與優化系統
> **不納入**: 直接債券交易（OTC）、實體商品、零售外匯
> **狀態**: Phase A~D 已實作，Phase E 待開始

---

## 1. 架構總覽

```
┌─────────────────────────────────────────────────────────────┐
│                     投資組合研究平台                           │
│                                                             │
│  ┌────────────────────────────────────────────────────────┐ │
│  │         第三層：組合最佳化 (src/portfolio/) ✅            │ │
│  │  PortfolioOptimizer (EW/IV/RP/MVO/BL/HRP)             │ │
│  │  RiskModel (Ledoit-Wolf + 風險貢獻)                     │ │
│  │  CurrencyHedger (分級對沖)                              │ │
│  └───────────────────────┬────────────────────────────────┘ │
│                          │                                   │
│  ┌───────────────────────┼────────────────────────────────┐ │
│  │         第二層：Alpha 信號                                │ │
│  │  資產內 Alpha (src/alpha/) ✅   資產間 Alpha (src/allocation/) ✅│
│  │  11 因子 + Pipeline            宏觀因子 + 跨資產信號        │ │
│  │  中性化/正交化/建構             戰術配置引擎                 │ │
│  └───────────────────────┬────────────────────────────────┘ │
│                          │                                   │
│  ┌───────────────────────┼────────────────────────────────┐ │
│  │         第一層：數據 + 標的                                │ │
│  │  InstrumentRegistry (src/instrument/) ✅                 │ │
│  │  DataFeed: Yahoo + FinMind + FRED (src/data/) ✅         │ │
│  │  台股 │ 美股 │ ETF (債券/商品代理) │ 期貨                  │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  ╔════════════════════════════════════════════════════════╗ │
│  ║  基礎設施                                                ║ │
│  ║  BacktestEngine │ RiskEngine(10規則) │ SimBroker │ API │ 前端 ║ │
│  ╚════════════════════════════════════════════════════════╝ │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 模組設計

### 2.1 Instrument Registry (`src/instrument/`)

統一標的模型：

```python
@dataclass(frozen=True)
class Instrument:
    symbol: str                      # "2330.TW", "ES=F", "TLT"
    asset_class: AssetClass          # EQUITY / ETF / FUTURE / OPTION
    sub_class: SubClass              # STOCK / ETF_BOND / ETF_COMMODITY / FUTURE / ...
    market: Market                   # TW / US
    currency: str                    # "TWD" / "USD"
    multiplier: Decimal              # 期貨合約乘數（股票=1）
    commission_rate: Decimal         # per-instrument 手續費
    tax_rate: Decimal                # per-instrument 稅率
```

`InstrumentRegistry.get_or_create()` 自動從 symbol pattern 推斷屬性（`.TW` → TW stock, `=F` → futures, 已知 ETF 列表）。

### 2.2 戰術配置層 (`src/allocation/`)

```
macro_factors.py  → MacroSignals (growth/inflation/rates/credit z-score)
cross_asset.py    → dict[AssetClass, float] (momentum/vol/value per class)
tactical.py       → dict[AssetClass, float] (戰術權重)
```

宏觀資料頻率處理：FRED 月度/季度資料以 `.ffill(limit=66)` 前向填補。

### 2.3 組合最佳化層 (`src/portfolio/`)

```
optimizer.py   → OptimizationResult (weights + return/risk/Sharpe/RC)
risk_model.py  → 共變異數矩陣 (歷史/EWM/Ledoit-Wolf) + 風險貢獻
currency.py    → HedgeRecommendation (暴露/比例/成本)
```

### 2.4 兩層配置整合 (`src/strategy/multi_asset.py`)

MultiAssetStrategy 串接完整流程：

```
1. 分類 universe → dict[AssetClass, list[str]]
2. 跨資產信號 → dict[AssetClass, float]
3. 市場狀態 → MarketRegime
4. 戰術配置 → dict[AssetClass, float]
5. 各類別內等權/Alpha → dict[str, float]
6. 組合最佳化 (Risk Parity 等) → final weights
```

已註冊至策略 registry，可透過回測和 API 使用。

---

## 3. 資料流程

```
DataFeed (Yahoo/FinMind/FRED)
     ↓
Strategy.on_bar(ctx) → target weights: dict[str, float]
     ↓
weights_to_orders() — 含乘數、lot_size、總權重驗證
     ↓
RiskEngine — 10 規則（含 asset_class/currency/leverage）
     ↓
SimBroker — per-instrument 費率、sqrt 滑點
     ↓
Portfolio — 多幣別 NAV (per-bar FX rate)
```

### 層間資料契約

| 步驟 | 輸出型別 |
|------|---------|
| 戰術配置 | `dict[AssetClass, float]`（sum ≈ 1.0） |
| 資產內選標 | `dict[str, float]`（各 symbol 權重） |
| 組合最佳化 | `OptimizationResult.weights: dict[str, float]` |
| 最終 | `weights_to_orders() → list[Order]` |

---

## 4. 風控架構

| 規則 | 層級 | 說明 |
|------|------|------|
| max_position_weight | 個股 | 單一標的權重上限 |
| max_order_notional | 個股 | 單筆金額上限 |
| fat_finger | 個股 | 價格偏離檢查 |
| daily_drawdown | 組合 | 日回撤上限 |
| max_daily_trades | 組合 | 交易次數上限 |
| max_order_vs_adv | 個股 | 流動性限制 |
| price_circuit_breaker | 個股 | 價格熔斷 |
| **max_asset_class_weight** | **跨資產** | 資產類別權重上限 |
| **max_currency_exposure** | **跨資產** | 幣別暴露上限 |
| **max_gross_leverage** | **跨資產** | 總槓桿上限 |

---

## 5. 前端架構

| 頁面 | 路由 | 功能 |
|------|------|------|
| Dashboard | `/` | NAV/持倉/即時 |
| Portfolio | `/portfolio` | CRUD + 再平衡預覽 |
| Strategies | `/strategies` | 9 策略列表 + 啟停 |
| Orders | `/orders` | 下單 + 歷史 |
| Backtest | `/backtest` | 回測 + 比較 + 月報 |
| Alpha | `/alpha` | 因子研究 (11 因子) |
| **Allocation** | `/allocation` | 戰術配置計算 + 視覺化 |
| Risk | `/risk` | 10 規則 + 告警 + kill switch |
| Settings | `/settings` | API key + 語言 + 主題 |
| Admin | `/admin` | 用戶管理 + 審計 |

---

## 6. 目錄結構

```
src/
├── alpha/           ✅ 11 files — 資產內 Alpha (Pipeline + 中性化 + 建構)
├── allocation/      ✅  4 files — 戰術配置 (宏觀 + 跨資產 + 戰術)
├── portfolio/       ✅  4 files — 組合最佳化 (6法 + LW + 對沖)
├── strategy/        ✅  8 files — 9 策略 + 因子庫 + MultiAssetStrategy
├── backtest/        ✅  6 files — 回測引擎 (多幣別 + FX 時序)
├── risk/            ✅  4 files — 10 規則 + kill switch
├── execution/       ✅  4 files — SimBroker (乘數 + per-instrument)
├── data/            ✅  6 files — Yahoo + FinMind + FRED
├── instrument/      ✅  3 files — Registry + 自動推斷
├── domain/          ✅  3 files — 統一模型
├── api/             ✅ 19 files — REST + WS + 11 路由
├── cli/             ✅  2 files — backtest/server/status/factors
├── notifications/   ✅  6 files — Discord/LINE/Telegram
└── scheduler/       ✅  2 files — APScheduler
```
