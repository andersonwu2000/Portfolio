# 專案建議書：量化交易系統平台

> **版本：** 1.0
> **日期：** 2026-03-23
> **專案代號：** Quant Trading Platform

---

## 一、摘要

本專案為一套全端量化交易系統，採用 Monorepo 架構整合 Python 後端、React 網頁前端與 React Native 行動應用程式。系統預設對接台灣股市（手續費 0.1425%、賣出證交稅 0.3%），同時透過 Yahoo Finance 支援全球市場。涵蓋策略開發、回測引擎、風險控管、即時監控與交易執行等核心功能，目標為提供專業交易者與量化研究員一站式投資決策工具。

---

## 二、專案背景與動機

### 2.1 市場需求

- 散戶及中小型機構缺乏整合回測、風控與執行的一站式量化交易平台
- 市面商用系統授權費用高昂，且難以客製化策略邏輯
- 行動端監控需求日益增長，交易者需要隨時掌握投資組合狀態

### 2.2 技術趨勢

- Python 生態系在量化金融領域持續主導
- TypeScript 全端化降低前後端溝通成本
- Monorepo 架構有利於共用型別定義與工具程式碼

---

## 三、系統架構

### 3.1 整體架構

```
┌──────────────────────────────────────────────────────────────┐
│                        使用者端                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  React Web   │  │ React Native │  │  CLI（Typer）     │   │
│  │  (Vite)      │  │ (Expo 52)    │  │                  │   │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘   │
│         │                 │                    │             │
│         └────────┬────────┘                    │             │
│                  ▼                             │             │
│       ┌─────────────────┐                      │             │
│       │ @quant/shared    │                      │             │
│       │ (Types/API/WS)  │                      │             │
│       └────────┬────────┘                      │             │
└────────────────┼───────────────────────────────┼─────────────┘
                 │          REST / WebSocket      │
                 ▼                               ▼
┌──────────────────────────────────────────────────────────────┐
│                    FastAPI 後端 (Port 8000)                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │ Auth     │ │ Portfolio│ │ Backtest │ │ Risk / WS    │   │
│  │ (JWT)    │ │ & Orders │ │ Engine   │ │ Manager      │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Core Engine                                          │   │
│  │  Strategy → RiskEngine → SimBroker → Portfolio       │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────┬───────────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │  PostgreSQL 16      │
                    │  + Yahoo Finance    │
                    └─────────────────────┘
```

### 3.2 技術棧

| 層級 | 技術 | 說明 |
|------|------|------|
| **後端** | Python 3.12、FastAPI、SQLAlchemy | 非同步 API、ORM |
| **資料庫** | PostgreSQL 16、Alembic | 關聯式儲存、版本遷移 |
| **Web 前端** | React 18、Vite、Tailwind CSS | SPA 儀表板 |
| **行動端** | React Native 0.76、Expo 52 | 跨平台行動應用 |
| **共用層** | @quant/shared（TypeScript） | 型別、API Client、工具函式 |
| **套件管理** | uv（Python）、bun（前端 Workspace） | 快速安裝與解析 |
| **容器化** | Docker、Docker Compose | 標準化部署 |
| **CI/CD** | GitHub Actions | 自動化測試與建置 |

### 3.3 Monorepo 結構

```
D:\Finance/
├── src/                # Python 後端核心
│   ├── api/            # FastAPI 路由、中介層、認證
│   ├── backtest/       # 回測引擎與分析
│   ├── strategy/       # 策略基底、因子庫、最佳化器
│   ├── risk/           # 風險引擎與規則
│   ├── execution/      # 模擬券商、訂單管理
│   ├── data/           # 資料來源（Yahoo Finance）與儲存
│   ├── domain/         # 領域模型（Instrument, Position, Portfolio...）
│   ├── cli/            # 命令列介面
│   └── config.py       # 環境變數設定
├── strategies/         # 使用者自訂策略
├── tests/              # 單元測試與整合測試
├── migrations/         # 資料庫遷移
├── apps/
│   ├── shared/         # @quant/shared 共用套件
│   ├── web/            # React Web 前端
│   └── mobile/         # React Native 行動端
├── .github/workflows/  # CI/CD Pipeline
├── Dockerfile          # 容器映像
└── docker-compose.yml  # 容器編排
```

---

## 四、核心功能模組

### 4.1 策略引擎

- **策略抽象**：透過 `Strategy` ABC 定義介面，`on_bar(ctx)` 回傳目標權重 `dict[str, float]`
- **因子庫**：內建 Momentum、Mean Reversion、RSI、Volatility 等純函式因子
- **最佳化器**：支援 Equal Weight、Signal Weight、Risk Parity 三種權重配置
- **擴充性**：於 `strategies/` 目錄新增檔案即可註冊新策略

**現有策略：**

| 策略名稱 | 說明 | 關鍵參數 |
|----------|------|----------|
| Momentum | 12-1 月動量策略，買入過去報酬最高的標的 | lookback=252, skip=21, max_holdings=10 |
| Mean Reversion | 均值回歸策略，Z-score 低於閾值時買入 | lookback=20, z_threshold=1.5 |

### 4.2 回測引擎

- **資料流程**：下載歷史資料 → 遍歷交易日 → 策略產生權重 → 風控審查 → 模擬執行 → 更新組合
- **時間因果律**：`Context` 封裝 `DataFeed`，確保策略僅能存取當前時間點之前的資料，杜絕未來資訊洩漏
- **效能指標**：Sharpe Ratio、Sortino Ratio、Calmar Ratio、最大回撤、勝率等
- **再平衡頻率**：支援每日、每週、每月調倉
- **交易成本模擬**：滑點、手續費、證交稅

### 4.3 風險管理引擎

採用**宣告式規則**設計，每條規則為純函式工廠，回傳 `RiskRule` dataclass。

| 規則 | 說明 | 預設閾值 |
|------|------|----------|
| max_position_weight | 單一標的權重上限 | 5% |
| max_order_notional | 單筆訂單占 NAV 比例 | 2% |
| daily_drawdown_limit | 日內回撤警戒線 | 3% |
| fat_finger_check | 價格異常偏離偵測 | 5% |
| max_daily_trades | 每日交易次數上限 | 100 筆 |
| max_order_vs_adv | 訂單量占日均量比例 | 10% |

- **緊急停損開關（Kill Switch）**：週回撤達 10% 時觸發，暫停所有交易
- **即時監控**：透過 WebSocket 推送風險警報至前端

### 4.4 交易執行

- **SimBroker**：模擬市場成交，含滑點、手續費、稅金計算、部分成交支援
- **訂單管理系統（OMS）**：追蹤訂單生命週期 PENDING → SUBMITTED → FILLED/CANCELLED/REJECTED
- **組合更新**：`apply_trades()` 依成交紀錄更新持倉與現金

### 4.5 資料層

- **Yahoo Finance**：透過 `yfinance` 下載全球市場歷史資料
- **本地快取**：24 小時 TTL 檔案快取，避免重複下載
- **時區正規化**：所有時間序列統一為無時區 UTC
- **資料庫儲存**：K 線資料、交易紀錄、回測結果、風險事件

### 4.6 API 服務

| 模組 | 端點 | 說明 |
|------|------|------|
| 認證 | `POST /auth/login`, `/logout` | JWT Token 發放與撤銷 |
| 系統 | `GET /system/health`, `/status`, `/metrics` | 健康檢查、系統監控 |
| 投資組合 | `GET /portfolio`, `/portfolio/positions` | 投組概覽與持倉 |
| 策略 | `GET /strategies`, `POST /.../start`, `/.../stop` | 策略管理與控制 |
| 訂單 | `GET /orders` | 訂單查詢（分頁、篩選） |
| 回測 | `POST /backtest`, `GET /backtest/{task_id}` | 非同步回測提交與結果查詢 |
| 風控 | `GET /risk/rules`, `PUT /.../toggle`, `POST /kill-switch` | 風控規則管理 |
| WebSocket | `/ws/{channel}` | 即時推送（portfolio, alerts, orders, market） |

**安全機制：**
- JWT 認證 + API Key 驗證
- 角色權限層級：viewer < researcher < trader < risk_manager < admin
- 回測速率限制：10 次/分鐘
- 稽核日誌中介層

### 4.7 Web 前端

| 頁面 | 功能 |
|------|------|
| Dashboard | 投組總覽、NAV 走勢圖、持倉表 |
| Portfolio | 持倉細節與曝險指標 |
| Strategies | 策略列表、啟動/停止控制 |
| Orders | 分頁訂單紀錄、狀態篩選 |
| Backtest | 策略選擇、參數設定、回測執行與結果圖表 |
| Risk | 風控規則管理、警報歷史、緊急停損 |
| Settings | API Key 設定、語言切換 |

**國際化：** 支援英文（en）與繁體中文（zh）

### 4.8 行動應用

- **Tab 導覽**：Dashboard、Positions、Alerts、Strategies、Settings
- **安全儲存**：使用 Expo SecureStore 管理登入憑證
- **即時資料**：透過 WebSocket 接收即時投組與警報更新
- **動畫效果**：React Native Reanimated 提升互動體驗

---

## 五、資料模型

### 5.1 核心領域物件

```
Instrument (frozen)     — 金融工具描述（symbol, name, exchange, lot_size）
Bar (frozen)            — K 線資料（open, high, low, close, volume, timestamp）
Position (mutable)      — 持倉（symbol, quantity, avg_cost, current_price, pnl）
Order (mutable)         — 訂單（side, quantity, price, status, timestamps）
Trade (frozen)          — 成交紀錄（order_id, price, quantity, commission, slippage）
Portfolio (mutable)     — 投資組合（positions, cash, nav, daily_pnl）
RiskAlert               — 風險警報（rule_name, severity, metric_value, threshold）
RiskDecision            — 風控裁決（APPROVE / REJECT + reason）
```

### 5.2 資料庫 Schema

| 資料表 | 說明 | 主鍵 |
|--------|------|------|
| bars | K 線歷史資料 | (symbol, timestamp, freq) |
| trades | 成交紀錄 | id (UUID) |
| backtest_results | 回測結果與設定 | id (UUID) |
| risk_events | 風險事件日誌 | id + timestamp |

---

## 六、設定與部署

### 6.1 環境變數

所有設定透過 `QUANT_` 前綴環境變數或 `.env` 檔案管理，由 Pydantic Settings 驗證。

| 類別 | 關鍵設定 |
|------|----------|
| 環境 | `QUANT_ENV` (dev/staging/prod)、`QUANT_MODE` (backtest/paper/live) |
| 資料庫 | `QUANT_DATABASE_URL` |
| 資料 | `QUANT_DATA_SOURCE` (yahoo/fubon/twse)、快取目錄 |
| 風控 | 各項風控閾值（position_pct, drawdown, trade limits...） |
| 執行 | 滑點、手續費率、稅率 |
| API | 主機、埠、Workers、JWT Secret、允許來源 |

### 6.2 Docker 部署

```yaml
# docker-compose.yml
services:
  api:    # FastAPI 後端（port 8000）
  db:     # PostgreSQL 16-alpine
```

- 多階段建置（Multi-stage build），最終映像精簡
- 非 root 使用者執行
- Health check 與 Volume 持久化

### 6.3 CI/CD Pipeline

GitHub Actions 自動化流程：

```
backend-lint  ──→  ruff check + mypy strict
backend-test  ──→  pytest
web-typecheck ──→  tsc --noEmit
web-build     ──→  vite build（依賴 typecheck）
mobile-typecheck → tsc --noEmit
```

---

## 七、安全設計

| 層面 | 措施 |
|------|------|
| 認證 | JWT Token + API Key 雙重驗證 |
| 授權 | 五層角色權限（viewer → admin） |
| 傳輸 | HTTPS（部署環境）、WebSocket Token 驗證 |
| 儲存 | 行動端使用 Expo SecureStore 加密儲存 |
| 輸入 | Pydantic Schema 驗證、速率限制 |
| 稽核 | 中介層記錄所有 API 請求與操作 |
| 金融安全 | 全程使用 `Decimal` 型別，避免浮點誤差 |

---

## 八、開發規範

### 8.1 設計原則

- **策略回傳權重**：策略只產出目標權重字典，不直接操作訂單
- **風控規則為純函式**：無繼承，每條規則為獨立的函式工廠
- **時間因果律**：回測中嚴格防止未來資訊洩漏
- **金額使用 Decimal**：禁止 float 處理金融數據
- **平台適配器模式**：共用邏輯在 `@quant/shared`，平台特定程式碼留在各自專案

### 8.2 擴充新策略流程

1. 在 `strategies/` 目錄建立新 Python 檔案
2. 繼承 `Strategy` 基底類別
3. 實作 `name()` 屬性與 `on_bar(ctx) -> dict[str, float]` 方法
4. 在 `src/api/routes/backtest.py` 與 `src/cli/main.py` 的 `_resolve_strategy()` 中註冊

### 8.3 測試策略

```bash
make test              # 全部測試
make lint              # 程式碼品質檢查
make web-typecheck     # 前端型別檢查
make mobile-typecheck  # 行動端型別檢查
```

---

## 九、未來規劃與建議

### 9.1 短期改善（1-3 個月）

| 項目 | 說明 | 優先級 |
|------|------|--------|
| 整合測試補強 | 目前 `tests/integration/` 為空，需補上 API 端到端測試 | 高 |
| 更多策略模板 | 新增 Pairs Trading、Statistical Arbitrage、Factor Investing 等策略 | 高 |
| 即時行情對接 | 整合台灣券商 API（如富邦、元大），支援即時報價 | 高 |
| Web 前端測試 | 建立 Vitest 單元測試與 Playwright E2E 測試 | 中 |
| 效能最佳化 | 大型回測的記憶體與速度優化，考慮 Polars 取代 Pandas | 中 |

### 9.2 中期發展（3-6 個月）

| 項目 | 說明 | 優先級 |
|------|------|--------|
| 實盤交易對接 | 完成 `live` 模式，串接券商下單 API | 高 |
| 多因子模型 | 實作完整的 Alpha 因子研究框架與因子合成 | 高 |
| 組合最佳化 | 整合 Mean-Variance、Black-Litterman 等組合最佳化方法 | 中 |
| 監控告警 | Grafana 儀表板 + Prometheus 指標 + 告警通知（LINE/Telegram） | 中 |
| 使用者管理 | 多用戶支援、策略隔離、績效歸因 | 中 |

### 9.3 長期願景（6-12 個月）

| 項目 | 說明 |
|------|------|
| 機器學習整合 | 整合 ML 因子挖掘與預測模型 |
| 多市場支援 | 美股、港股、加密貨幣等跨市場交易 |
| 社群功能 | 策略分享、績效排行、策略市場 |
| 進階回測 | 支援事件驅動回測、Tick 級別回測、多策略組合回測 |
| 高頻交易 | 低延遲執行引擎，支援微秒級別操作 |

---

## 十、風險評估

| 風險項目 | 影響程度 | 緩解措施 |
|----------|----------|----------|
| Yahoo Finance API 不穩定或限制 | 中 | 本地快取機制 + 備用資料源（TWSE、Fubon） |
| 即時交易的資金安全 | 高 | 多層風控規則 + Kill Switch + 每日/每週回撤上限 |
| 策略未來資訊洩漏 | 高 | 時間因果律強制執行 + 資料截斷驗證 |
| 浮點精度問題 | 中 | 全程使用 Decimal 型別 |
| 系統可用性 | 中 | Docker 容器化 + 健康檢查 + CI/CD 自動化 |

---

## 十一、結論

本量化交易系統平台已具備完整的策略開發、回測驗證、風險控管與多端監控能力。Monorepo 架構確保前後端型別一致性，宣告式風控規則提供靈活且安全的交易保障。透過持續擴充策略庫、對接即時行情與券商 API，系統將逐步從回測研究工具演進為完整的自動化交易平台。

---

*本文件由 Claude Code 協助產生，基於專案現有程式碼與架構分析撰寫。*
