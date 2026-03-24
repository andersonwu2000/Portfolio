# 開發計畫書

> **版本**: v3.0
> **日期**: 2026-03-24
> **目標**: 建立涵蓋多個可自動交易市場的投資組合研究與優化系統
> **可交易市場**: 台股、美股、ETF（含債券/商品 ETF 代理）、台灣期貨、美國期貨
> **不納入**: 直接債券交易（OTC）、實體商品、零售外匯（台灣法規限制）
> **架構設計**: `docs/dev/MULTI_ASSET_ARCHITECTURE.md`
> **已完成**: Phase A（基礎設施）+ Phase B（跨資產 Alpha）+ Phase C（組合最佳化）

---

## 目錄

1. [階段概覽](#1-階段概覽)
2. [Phase A~C：已完成](#2-phase-ac已完成)
3. [Phase D：系統整合 + 風控升級（當前）](#3-phase-d系統整合--風控升級當前)
4. [Phase E：實盤交易](#4-phase-e實盤交易)
5. [已完成的里程碑](#5-已完成的里程碑)
6. [設計缺陷追蹤](#6-設計缺陷追蹤)

---

## 1. 階段概覽

```
Phase A ✅               Phase B ✅          Phase C ✅           Phase D (當前)       Phase E
基礎設施+管線整合         跨資產 Alpha         組合最佳化            系統整合+風控         實盤
─────────────────       ────────────        ─────────           ─────────           ──────
✅ Instrument Registry  ✅ 宏觀因子模型       ✅ 6 種最佳化器       兩層配置整合          券商對接
✅ 多幣別 Portfolio      ✅ 跨資產信號        ✅ 風險模型(LW)       跨資產風控規則         Paper/Live
✅ DataFeed 擴展        ✅ 戰術配置引擎       ✅ 幣別對沖           期貨展期模擬          多資產前端
✅ FRED + 管線整合      ✅ API + 前端型別                          績效歸因
✅ FX 時序修復                                                    Allocation 整合
```

### 核心原則

Phase A~C 的教訓：**模組存在 ≠ 系統整合**。目前 `src/allocation/` 和 `src/portfolio/` 都是獨立模組，尚未接入回測引擎的主迴圈。Phase D 的首要任務是打通兩層配置流程，使系統能做到「輸入 universe → 自動配置 → 回測」。

---

## 2. Phase A~C：已完成

### Phase A：多資產基礎設施 + 管線整合 ✅

- Instrument Registry (自動推斷 symbol → asset_class/market/currency/multiplier)
- 多幣別 Portfolio (`nav_in_base()`, `currency_exposure()`, `cash_by_currency`)
- DataFeed 擴展 (FX time series, futures chain)
- FRED 宏觀數據源 (7+ series, parquet cache)
- 管線整合 (weights_to_orders 乘數, SimBroker per-instrument 費率, 回測 FX per-bar)
- 模型統一 + 死碼清理 + mypy strict 0 errors

### Phase B：跨資產 Alpha ✅

- `src/allocation/macro_factors.py`：成長/通膨/利率/信用 四因子 z-score
- `src/allocation/cross_asset.py`：動量/波動率/均值回歸 per AssetClass
- `src/allocation/tactical.py`：TacticalEngine (戰略 + 宏觀 + 跨資產 + regime → 資產類別權重)
- `POST /api/v1/allocation` API + 前端 TacticalRequest/Response 型別

### Phase C：多資產組合最佳化 ✅

- `src/portfolio/optimizer.py`：6 種方法 (EW/IV/RP/MVO/BL/HRP) + OptimizationResult
- `src/portfolio/risk_model.py`：Ledoit-Wolf 收縮共變異數 + 風險貢獻分解
- `src/portfolio/currency.py`：CurrencyHedger 分級對沖策略

---

## 3. Phase D：系統整合 + 風控升級（當前）

**目標**: 打通兩層配置流程，讓 allocation + optimizer 能參與回測和執行。

### Task D1: 兩層配置整合

**核心問題**: `src/allocation/` 和 `src/portfolio/` 目前與 BacktestEngine 完全斷開。

**方案**: 建立 `MultiAssetStrategy` — 一個新的 Strategy 子類，內部串接兩層：

```python
class MultiAssetStrategy(Strategy):
    """兩層配置策略：資產類別配置 → 資產內選股 → 組合最佳化。"""

    def on_bar(self, ctx: Context) -> dict[str, float]:
        # 1. 戰術配置 → dict[AssetClass, float]
        tactical_weights = self.tactical_engine.compute(macro, cross_asset, regime)

        # 2. 各資產類別內選標的 → dict[str, float]
        symbol_weights = {}
        for asset_class, class_weight in tactical_weights.items():
            class_universe = [s for s in universe if instruments[s].asset_class == asset_class]
            alpha_weights = self.alpha_pipeline.generate_weights(data, current_date)
            for sym, w in alpha_weights.items():
                symbol_weights[sym] = w * class_weight

        # 3. 組合最佳化
        returns_df = self._build_returns(data, symbol_weights.keys())
        result = self.optimizer.optimize(returns_df)
        return result.weights
```

**位置**: `src/strategy/multi_asset.py`
**整合**: 註冊至 strategy registry，可在回測和 API 中使用

### Task D2: 跨資產風控規則

擴展 `src/risk/rules.py`：

```
max_asset_class_weight(threshold)   — 單一資產類別上限（如期貨 ≤ 20%）
max_currency_exposure(threshold)    — 單一幣別暴露上限
max_gross_leverage(threshold)       — 總槓桿上限（期貨保證金計算）
```

### Task D3: 期貨展期模擬

**新增**: `src/execution/roll.py`

自動偵測近月到期，模擬 roll 到下月合約，展期成本 (roll cost) 納入績效。

### Task D4: 三層績效歸因

**新增**: 擴展 `src/alpha/attribution.py`

資產配置歸因 + 選股歸因 + 匯率歸因。區分配置層 vs Alpha 層 vs FX 對報酬的貢獻。

### Phase D 完成標誌

能執行一次完整的多資產回測：
1. 輸入混合 universe (TW 股 + US 股 + ETF + 期貨)
2. 系統自動分配至各資產類別（戰術配置）
3. 各類別內部選標的（Alpha pipeline）
4. 組合最佳化（Risk Parity / BL）
5. 風控規則通過後執行
6. 績效報告含資產配置歸因 + 匯率影響

---

## 4. Phase E：實盤交易

| 任務 | 說明 |
|------|------|
| E1 券商對接 | 台股 (永豐 Shioaji) + 美股 (Interactive Brokers) |
| E2 即時行情 | 填補 WebSocket `market` 頻道 |
| E3 Paper Trading | 完整紙上交易循環 |
| E4 多資產前端 | 配置儀表板、跨市場持倉、幣別暴露圖、資產配置視覺化 |

> 券商評估細節見 `docs/dev/BROKER_API_EVALUATION.md`。

---

## 5. 已完成的里程碑

### 股票交易系統 (2026-03-22 ~ 2026-03-23)

回測引擎、7 策略、風控、SimBroker、REST API + WebSocket、Web + Mobile 前端。

### Alpha 研究層 (2026-03-24)

11 模組 + API 端點 + 前端頁面。效能優化：`compute_factor_values()` 向量化（~7 min → ~30s）。

### Phase A 基礎設施 (2026-03-24)

Instrument Registry + 多幣別 Portfolio + DataFeed + FRED + 管線整合 (D-01~D-07) + 模型統一 + 死碼清理。

### Phase B 跨資產 Alpha (2026-03-24)

宏觀因子模型 + 跨資產信號 + 戰術配置引擎 + API + 前端型別。23 tests。

### Phase C 組合最佳化 (2026-03-24)

6 種最佳化方法 + Ledoit-Wolf 風險模型 + 幣別對沖。28 tests。

### 測試覆蓋補齊 (2026-03-24)

+29 tests 補齊期貨成本、golden value、多資產 E2E、Alpha 整合、NaN 邊界、FX 整合。

### 架構審計 + Bug 修復 (2026-03-24)

- **FX per-bar 更新**: 載入 USDTWD=X 時序，_snap_nav 每 bar 查找對應匯率
- **總權重驗證**: weights_to_orders 檢查 sum > 1.5 時警告+正規化
- **FRED ffill 上限**: `.ffill()` → `.ffill(limit=66)`

---

## 6. 設計缺陷追蹤

| 編號 | 嚴重度 | 狀態 | 問題 |
|------|--------|------|------|
| ~~D-01~~ | ~~致命~~ | ✅ | weights_to_orders 合約乘數 |
| ~~D-02~~ | ~~致命~~ | ✅ | Portfolio.nav_in_base() 多幣別 |
| ~~D-03~~ | ~~致命~~ | ✅ | BacktestEngine 多幣別 + Registry |
| ~~D-04~~ | ~~高~~ | ✅ | SimBroker per-instrument 費率 |
| ~~D-05~~ | ~~高~~ | ✅ Phase B | 戰術配置層已實作 |
| ~~D-06~~ | ~~高~~ | ✅ | Registry 整合 BacktestEngine |
| ~~D-07~~ | ~~中~~ | ✅ | YahooFeed 重試/限流 |
| D-08 | 中 | 延後 | Alpha Pipeline GIL 限制 |
| ~~D-09~~ | ~~低~~ | ✅ | 前端標的列表 230 支 |
| ~~D-10~~ | ~~高~~ | ✅ | Instrument 模型統一 |
| ~~D-11~~ | ~~致命~~ | ✅ | registry.py expiry kwarg |
| ~~D-12~~ | ~~高~~ | ✅ | _snap_nav 用 nav_in_base |
| ~~D-13~~ | ~~中~~ | ✅ | mypy 14 errors |
| ~~D-14~~ | ~~致命~~ | ✅ | FX 匯率逐 bar 更新（原本只載入一次） |
| ~~D-15~~ | ~~高~~ | ✅ | 總權重無驗證（策略可回傳 >100%） |
| ~~D-16~~ | ~~中~~ | ✅ | FRED ffill 無上限（應 66 天） |
| D-17 | **高** | Phase D | allocation/optimizer 未整合進 BacktestEngine |
| D-18 | **中** | Phase D | 無跨資產風控規則（幣別/槓桿上限） |
| D-19 | **低** | Phase D | 期貨展期未模擬 |

---

> **文件維護說明**: 每完成一個 Task 標注日期。每完成一個 Phase 更新 `SYSTEM_STATUS_REPORT.md`。
