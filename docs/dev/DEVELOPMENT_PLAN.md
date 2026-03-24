# 開發計畫書

> **版本**: v2.1
> **日期**: 2026-03-24
> **目標**: 建立涵蓋多個可自動交易市場的投資組合研究與優化系統
> **可交易市場**: 台股、美股、ETF（含債券/商品 ETF 代理）、台灣期貨、美國期貨
> **不納入**: 直接債券交易（OTC）、實體商品、零售外匯（台灣法規限制）
> **架構設計**: `docs/dev/MULTI_ASSET_ARCHITECTURE.md`
> **已完成**: 股票交易系統 + Alpha 研究層 + Phase A 基礎設施（部分）

---

## 目錄

1. [開發策略](#1-開發策略)
2. [Phase A：多資產基礎設施 + 管線整合](#2-phase-a多資產基礎設施--管線整合)
3. [Phase B：跨資產 Alpha](#3-phase-b跨資產-alpha)
4. [Phase C：多資產組合最佳化](#4-phase-c多資產組合最佳化)
5. [Phase D：回測與風控升級](#5-phase-d回測與風控升級)
6. [Phase E：實盤與商業化](#6-phase-e實盤與商業化)
7. [已完成的里程碑](#7-已完成的里程碑)
8. [設計缺陷追蹤](#8-設計缺陷追蹤)

---

## 1. 開發策略

### 1.1 核心原則

**基礎設施 → 管線整合 → Alpha → 最佳化 → 回測 → 實盤**

Phase A 的教訓：建立新模組（Instrument、多幣別欄位）不等於完成。必須將新模組**整合進現有的執行管線**（回測引擎、SimBroker、weights_to_orders），否則新舊系統斷裂。

### 1.2 階段概覽

```
Phase A (進行中)            Phase B              Phase C              Phase D            Phase E
基礎設施 + 管線整合         跨資產 Alpha          組合最佳化            回測+風控           實盤
───────────────────       ────────────         ─────────            ──────────         ──────
✅ A1 Instrument Registry   宏觀因子模型          Risk Parity          多幣別回測          券商對接
✅ A2 多幣別 Portfolio 欄位  跨資產信號           Black-Litterman       期貨展期           Paper/Live
✅ A3 擴展 DataFeed         市場狀態識別          幣別對沖              跨資產風控          多資產前端
✅ A4 FRED 數據源           戰術配置引擎          再平衡邏輯            績效歸因           合規
⬜ A5 管線整合 (致命缺陷修復)
⬜ A6 YahooFeed 韌性強化
```

### 1.3 現有基礎

| 能力 | 狀態 | 位置 |
|------|------|------|
| 股票回測引擎 | ✅ | `src/backtest/` |
| Alpha 研究層 (11 模組) | ✅ | `src/alpha/` |
| Instrument Registry | ✅ 已建立，未整合 | `src/instrument/` |
| 多幣別 Portfolio 欄位 | ✅ 已建立，未整合 | `src/domain/models.py` |
| FRED 數據源 | ✅ | `src/data/sources/fred.py` |
| DataFeed 擴展 (FX/期貨) | ✅ | `src/data/feed.py` |

---

## 2. Phase A：多資產基礎設施 + 管線整合

### 已完成

- ✅ **A1**: Instrument Registry (`src/instrument/`)
- ✅ **A2**: 多幣別 Portfolio 欄位 (`cash_by_currency`, `total_cash()`, `currency_exposure()`)
- ✅ **A3**: DataFeed 擴展 (`get_fx_rate()`, `get_futures_chain()`)
- ✅ **A4**: FRED 宏觀數據源 (`src/data/sources/fred.py`)

### 待完成：管線整合（修復致命缺陷）

#### Task A5: 執行管線多資產整合

**目的**: 讓新的 Instrument/多幣別基礎設施真正被回測引擎和執行層使用。目前 D-01~D-06 缺陷的根因都是「基礎設施建了但沒接上」。

##### A5a: weights_to_orders() 支援合約乘數 (D-01)

**修改**: `src/strategy/engine.py`

**問題**: `qty = target_value / price` 忽略 `multiplier`，期貨數量錯誤 200~500 倍。

**修復**:
```python
# 目前 (錯誤)
qty = abs(target_value / price)

# 修復後
notional_per_contract = price * inst.multiplier
qty = abs(target_value / notional_per_contract)
```

同時讓 BacktestEngine 建構 instruments dict 並傳入 weights_to_orders()。

##### A5b: SimBroker 使用 per-instrument 費率 (D-04)

**修改**: `src/execution/sim.py`

**問題**: 手續費/稅為全域 SimConfig，不使用 Instrument 的 per-instrument 費率。

**修復**: `execute()` 方法檢查 Order.instrument 的 `commission_rate` 和 `tax_rate`，若有值則覆蓋 SimConfig 預設值。

##### A5c: Portfolio.nav 支援多幣別 (D-02)

**修改**: `src/domain/models.py`

**問題**: `nav` property 直接加總不同幣別市值。

**修復**: `nav` property 改為接受可選 `fx_rates` 參數（或新增 `nav_in_base()` 方法），按持倉幣別轉換後加總。向後相容：無 `fx_rates` 時維持現有行為。

##### A5d: BacktestEngine 多幣別支援 (D-03)

**修改**: `src/backtest/engine.py`

**問題**: 回測迴圈不載入匯率、不呼叫多幣別 NAV。

**修復**:
- 在 `_refresh_bar_cache()` 中偵測混幣別 universe（根據 InstrumentRegistry）
- 若有混幣別，自動載入 `USDTWD=X` 匯率時序
- `_snap_nav()` 改用 `portfolio.nav_in_base(fx_rates)` 計算 NAV
- 單幣別場景不受影響（無 FX 開銷）

##### A5e: InstrumentRegistry 接入回測引擎 (D-06)

**修改**: `src/backtest/engine.py`

在 BacktestEngine 初始化時，為 universe 中的每個 symbol 呼叫 `registry.get_or_create()`，建構 instruments dict 供 weights_to_orders() 和 SimBroker 使用。

#### Task A6: YahooFeed 韌性強化 (D-07)

**修改**: `src/data/sources/yahoo.py`

- 加入指數退避重試（最多 3 次，間隔 1s/2s/4s）
- 加入全域速率限制（每秒最多 2 請求）
- 失敗時記錄 warning 而非靜默返回空 DataFrame

### Phase A 完成標誌

能正確回測一個混合 universe（如 `["2330.TW", "AAPL", "TLT", "GC=F"]`），其中：
- 期貨數量正確反映合約乘數
- NAV 以 base_currency (TWD) 計價，含匯率轉換
- 各標的使用各自的手續費/稅率
- InstrumentRegistry 自動推斷標的屬性

---

## 3. Phase B：跨資產 Alpha

**目標**: 回答「現在應該把多少比例放在股票、債券ETF、商品、現金？」

### Task B1: 宏觀因子模型

**新增**: `src/allocation/macro_factors.py`

| 因子 | 指標 | 信號 |
|------|------|------|
| 成長 | GDP, PMI, 就業 | 加速 → 股票+、債券ETF− |
| 通膨 | CPI, PPI, 油價 | 上升 → 商品ETF+、長債ETF− |
| 利率 | 央行利率, 殖利率斜率 | 下降 → 長債ETF+、成長股+ |
| 信用 | 信用利差, 違約率 | 收窄 → HYG+、股票+ |

### Task B2: 跨資產信號

**新增**: `src/allocation/cross_asset.py`

| 因子 | 定義 | 適用 |
|------|------|------|
| 時間序列動量 | 12M 報酬 (12-1) | 所有資產 |
| Carry | 股息率 / 展期收益 | 股票 / 期貨 |
| Value | 長期均值回歸 (CAPE) | 股票 / 債券ETF |
| Volatility | 已實現 vs 隱含波動率 | 所有 |

### Task B3: 戰術配置引擎

**新增**: `src/allocation/tactical.py`

結合戰略配置 + 宏觀觀點 + 跨資產信號 → 資產類別戰術權重。

### Phase B 完成標誌

能自動產出「股票 55% / 債券ETF 30% / 商品ETF 10% / 現金 5%」的戰術配置，回測驗證超額報酬。

---

## 4. Phase C：多資產組合最佳化

### Task C1: 多資產最佳化器 (`src/portfolio/optimizer.py`)

方法：Mean-Variance, Risk Parity, Black-Litterman, HRP

### Task C2: 幣別對沖 (`src/portfolio/currency.py`)

根據 TWD/USD 暴露和對沖成本，自動決定對沖比例。

### Task C3: 兩層配置整合

```
戰略配置 → 戰術偏離 → 資產內選擇 (Alpha) → 組合最佳化 → 最終持倉
```

### Phase C 完成標誌

輸入「戰略配置 + 宏觀觀點 + Alpha 信號」，產出跨市場最終持倉（含幣別對沖建議）。

---

## 5. Phase D：回測與風控升級

### Task D1: 期貨展期模擬

自動偵測近月到期，模擬 roll 到下期，展期成本納入績效。

### Task D2: 跨資產風控規則

```
max_asset_class_weight()   — 資產類別上限
max_currency_exposure()    — 單一幣別上限
max_leverage()             — 總槓桿上限（期貨保證金）
stress_test_limit()        — 壓力測試虧損上限
```

### Task D3: 三層績效歸因

資產配置歸因 + 選股歸因 + 匯率歸因。

---

## 6. Phase E：實盤與商業化

| 任務 | 說明 |
|------|------|
| 券商對接 | 台股 (永豐 Shioaji) + 美股 (Interactive Brokers) |
| 即時行情 | 填補 WebSocket market 頻道 |
| Paper Trading | 完整紙上交易循環 |
| 多資產前端 | 配置儀表板、跨市場持倉、幣別暴露圖 |

---

## 7. 已完成的里程碑

### 股票交易系統 (2026-03-22 ~ 2026-03-23)

回測引擎、7 策略、風控、SimBroker、REST API + WebSocket、Web + Mobile 前端。

### Alpha 研究層 (2026-03-24)

11 模組 + API 端點 + 前端頁面。效能優化：`compute_factor_values()` 向量化。

### Phase A 基礎設施（部分）(2026-03-24)

InstrumentRegistry (model + registry)、多幣別 Portfolio 欄位、DataFeed 擴展、FRED 數據源。

**尚未完成**: 管線整合（A5a~A5e）、YahooFeed 韌性（A6）。

---

## 8. 設計缺陷追蹤

Phase A 檢討中發現的致命缺陷，已納入 Task A5 修復計畫：

| 編號 | 嚴重度 | 位置 | 問題 | 修復 Task |
|------|--------|------|------|----------|
| D-01 | 致命 | `strategy/engine.py` | `weights_to_orders()` 忽略合約乘數 | A5a |
| D-02 | 致命 | `domain/models.py` | `Portfolio.nav` 混加不同幣別 | A5c |
| D-03 | 致命 | `backtest/engine.py` | 回測引擎單幣別假設 | A5d |
| D-04 | 高 | `execution/sim.py` | SimBroker 全域費率 | A5b |
| D-05 | 高 | `alpha/strategy.py` | AlphaStrategy 無資產配置層 | Phase B |
| D-06 | 高 | `instrument/` | Registry 未被消費 | A5e |
| D-07 | 中 | `data/sources/yahoo.py` | 無重試/限流 | A6 |
| D-08 | 中 | `api/routes/alpha.py` | GIL 限制（ThreadPool） | 延後 |
| D-09 | 低 | 前端 | 標的列表硬編碼 | 延後 |

---

> **文件維護說明**: 每完成一個 Task 標注日期。每完成一個 Phase 更新 `SYSTEM_STATUS_REPORT.md`。
