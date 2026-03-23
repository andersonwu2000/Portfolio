# 開發計畫書 v2.1

**日期**: 2026-03-24（最後更新）
**目標**: 從「回測研究平台」進化為「個人可用的投資輔助工具」
**資料源決策**: FinMind（免費，未來可擴充 EODHD/TEJ）
**參考文件**: `PERSONAL_USE_GAP_REPORT.md`, `PLAN_VS_REALITY.md`, `DATA_SOURCE_EVALUATION.md`

---

## 總覽與進度

```
Phase 0  回測可信度修復        ─── ✅ 已完成
Phase 1  FinMind 整合          ─── ✅ 已完成
Phase 2  回測引擎強化          ─── ✅ 大致完成（漲跌幅/價格升降單位待做）
Phase 3  實用化基礎設施        ─── ✅ 已完成
Phase 4  進階功能              ─── 🔲 未開始
```

✅ Phase 0-3 已完成：回測可信、支援基本面策略、系統可產生交易建議、推播通知、持倉持久化。

---

## Phase 0 — 回測可信度修復 ✅ 已完成

### 0-1. 次日開盤價成交 ✅
- `BacktestConfig.execution_delay: int = 1`
- 主迴圈: Day N 產生訊號 → `pending_orders` → Day N+1 開盤價執行
- `SimBroker.execute()` 支援 open 價成交
- `_open_matrix` 已建立

### 0-2. 滑價模型升級 ✅
- `SimConfig.impact_model: Literal["fixed", "sqrt"] = "sqrt"`
- `_calc_slippage()` 實作 square-root impact model
- `slippage_bps = base_bps + impact_coeff × sqrt(order_qty / adv)`

### 0-3. Kill Switch 串接回測 ✅
- 回測主迴圈每日呼叫 `risk_engine.kill_switch(portfolio)`
- Kill switch 觸發 → 清空持倉 → 停止交易直到月底
- `BacktestConfig.enable_kill_switch: bool = True`

### 0-4. 拒單記錄與報告 ✅
- `SimBroker.rejected_log: list[Order]`
- `BacktestResult.rejected_orders` / `rejected_notional`

### 0-5. 成交量為零不可交易 ✅
- `execute()` 中 volume == 0 → REJECT

---

## Phase 1 — FinMind 整合 ✅ 已完成

### 1-1. FinMind 資料源（OHLCV）✅
- `src/data/sources/finmind.py` — `FinMindFeed` 實作 `DataFeed` ABC
- 雙層快取：LRU 記憶體 + Parquet 磁碟（`ParquetDiskCache`）
- .TW/.TWO 後綴自動轉換（`finmind_common.py`）

### 1-2. 基本面資料介面 ✅
- `src/data/fundamentals.py` — `FundamentalsProvider` ABC
- 方法: `get_financials()`, `get_sector()`, `get_revenue()`, `get_dividends()`

### 1-3. FinMind 基本面實作 ✅
- `src/data/sources/finmind_fundamentals.py` — `FinMindFundamentals`
- PE/PB (TaiwanStockPER), EPS/ROE (TaiwanStockFinancialStatement)
- 月營收 + YoY (TaiwanStockMonthRevenue)
- 股利歷史 (TaiwanStockDividend)
- 產業分類: 一次下載全表快取 (`_populate_sector_cache()`)
- 快取 TTL: 7 天

### 1-4. 策略升級：真實基本面因子 ✅
- `Context` 新增 `fundamentals()`, `sector()` 方法
- `strategies/multi_factor.py`: 真實 PE/PB/ROE 因子
- `strategies/sector_rotation.py`: 真實產業分類
- `src/strategy/factors.py`: `value_pe()`, `value_pb()`, `quality_roe()`

### 1-5. 資料源切換機制 ✅
- `src/data/sources/__init__.py` — `create_feed()` 工廠函式
- `config.data_source` 支援 `"yahoo"` / `"finmind"`

---

## Phase 2 — 回測引擎強化 ✅ 大致完成

### 2-1. 回測引擎單元測試 ✅
- `tests/unit/test_backtest_engine.py` — 完整引擎核心測試

### 2-2. 回測品質驗證模組 ✅
- `src/backtest/validation.py` — `check_causality()`, `check_determinism()`, `check_sensitivity()`
- `tests/unit/test_validation.py`

### 2-3. 台股整股交易單位 ✅
- `weights_to_orders()` 根據 `.TW`/`.TWO` 後綴自動設 `lot_size=1000`
- `config.tw_lot_size` 可配置（零股模式設 1）
- `tests/unit/test_weights_to_orders.py`

### 2-4. 台股漲跌幅限制模擬 🔲 待做
- `SimConfig.price_limit_pct` 規劃中

### 2-5. T+2 交割模擬 ✅
- `Portfolio.settled_cash`, `Portfolio.pending_settlements`
- `BacktestConfig.settlement_days: int = 0`
- 主迴圈每日結算到期的 pending settlements

### 2-6. 前向填充上限 ✅
- `BacktestConfig.max_ffill_days: int = 5`
- `_build_matrices()` 使用 `ffill(limit=...)`

### 2-7. 股利模擬 ✅
- `BacktestConfig.enable_dividends: bool = False`
- 回測日迴圈中依 ex-date + 持倉量注入現金
- `tests/unit/test_backtest_dividends.py`

---

## Phase 3 — 實用化基礎設施 ✅ 已完成

### 3-1. Portfolio 持久化 ✅
- `migrations/versions/004_portfolio_persistence.py` — portfolios + position_snapshots 表
- `src/domain/repository.py` — `PortfolioRepository` CRUD（single JOIN queries）

### 3-2. 「建議交易」API ✅
- `POST /api/v1/portfolio/saved/{id}/rebalance-preview`
- 使用真正的 `weights_to_orders()` 而非重新實作
- 含預估手續費、交易稅

### 3-3. 交易通知 ✅
- `src/notifications/` — Discord, LINE, Telegram
- `src/notifications/formatter.py` — 交易/再平衡/警報格式化
- `src/notifications/factory.py` — 根據 config 自動建立通知管道

### 3-4. 策略排程 ✅
- `src/scheduler/` — APScheduler
- `src/scheduler/jobs.py` — 每日 portfolio snapshot + 每週 rebalance check
- `config.scheduler_enabled`, `config.rebalance_cron`

### 3-5. Walk-Forward Analysis ✅
- `src/backtest/walk_forward.py` — `WalkForwardAnalyzer`
- `POST /api/v1/backtest/walk-forward`
- Rolling train/test windows

### 3-6. Prometheus 指標 ✅
- `prometheus-fastapi-instrumentator` 整合
- 自訂 metrics: backtest_duration, active_ws

### 3-7. WebSocket 廣播優化 ✅
- `broadcast()` 改用 `asyncio.gather` + 5 秒 timeout + 死連線清理

---

## Phase 4 — 進階功能 🔲 未開始

> **目的**: 提升使用體驗，接近半自動化投資。

### 4-1. 實際績效追蹤
- 新增 `actual_trades` 表：記錄在券商實際執行的交易
- 手動輸入 API: `POST /api/v1/portfolio/{id}/actual-trades`
- 績效比較: 回測建議 vs 實際執行的差異分析

### 4-2. 手動交易記錄
- Web UI: 在 OrdersPage 新增「記錄已執行交易」功能
- Mobile: OrderForm 增加「記錄模式」

### 4-3. 券商 API 介接（Shioaji 首選）
- 新增 `src/execution/shioaji.py` 實作 `BrokerAdapter`
- 支援查詢持倉、下單、撤單、模擬交易
- 詳見 `BROKER_API_EVALUATION.md`

### 4-4. 台股漲跌幅限制
- `SimConfig.price_limit_pct: float = 0.10`
- 成交價超出限制 → REJECT

### 4-5. PaperBroker 實作
- 使用即時行情模擬成交（對接 Shioaji simulation mode）

---

## 依賴關係

```
Phase 0-1~0-5 ─── ✅ 全部完成
Phase 1-1~1-5 ─── ✅ 全部完成
Phase 2-1~2-3, 2-5~2-7 ─── ✅ 完成
Phase 2-4 (漲跌幅) ─── 🔲 獨立可做
Phase 3-1~3-7 ─── ✅ 全部完成

Phase 4 依賴:
  Phase 3-1 (持久化) → Phase 4-1 (績效追蹤)
  Phase 3-3 (通知) → Phase 4-3 (券商介接)
```

---

## 測試覆蓋

| 類別 | 測試檔數 | 測試數 |
|:----:|:--------:|:------:|
| 後端 unit | 25 | ~300 |
| 後端 integration | 2 | ~40 |
| Web frontend | 多個 | ~40 |
| Mobile | 多個 | ~70 |
| E2E (Playwright) | 4 | ~20 |
| **合計** | | **~349+ backend, ~110+ frontend** |

---

## 里程碑

| 里程碑 | 狀態 | 說明 |
|--------|:----:|------|
| **M1: 可信回測** | ✅ | 次日成交、sqrt 滑價、kill switch、拒單記錄、零量檢查 |
| **M2: 基本面策略** | ✅ | FinMind PE/PB/ROE/產業分類，multi_factor + sector_rotation 升級 |
| **M3: 台股精確模擬** | ⚠️ | 整股交易、T+2、ffill limit 完成；漲跌停待做 |
| **M4: 投資輔助工具** | ✅ | 持久化、建議交易、通知（Discord/LINE/Telegram）、排程 |
| **M5: 半自動化** | 🔲 | 績效追蹤、券商介接待做 |
