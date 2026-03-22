# Quant 系統完整說明書

> 本文件說明 **Portfolio（後端）** 與 **Quant Mobile（前端）** 的架構、模組職責、API 介面與整合關係。

---

## 一、系統架構總覽

```
┌─────────────────────────────────────────────────────────┐
│              Quant Mobile（前端 - React Native）          │
│  Dashboard | Positions | Strategies | Alerts | Settings  │
└─────────┬───────────────────────────┬───────────────────┘
          │  REST API (HTTP/JSON)      │  WebSocket (ws://)
          │  /api/v1/*                │  /ws/{channel}
          ▼                           ▼
┌─────────────────────────────────────────────────────────┐
│             Portfolio（後端 - FastAPI Python）             │
│  Strategy Engine | Risk Engine | Backtest | OMS | DB     │
└─────────────────────────────────────────────────────────┘
```

兩個專案構成一套**完整的量化交易系統**：
- **Portfolio（後端）**：台灣/全球股市量化策略引擎，負責策略執行、風險管理、回測、資料處理
- **Quant Mobile（前端）**：行動端監控與控制介面，讓交易員隨時隨地管理策略與倉位

---

## 二、後端：Portfolio

### 2.1 專案定位

以台灣股市為預設目標（手續費 0.1425%、賣方稅 0.3%），支援三種運作模式：
- `backtest`：歷史回測
- `paper`：模擬交易（不真實下單）
- `live`：實盤交易

### 2.2 技術棧

| 類別 | 技術 |
|------|------|
| 語言/執行 | Python 3.12+ |
| API 框架 | FastAPI 0.110+、Uvicorn 0.27+、WebSockets |
| 資料處理 | Pandas 2.0+、NumPy 1.26+、yfinance |
| 資料庫 | PostgreSQL、SQLAlchemy 2.0+、Alembic |
| 最佳化 | cvxpy 1.4+、scipy 1.12+ |
| 認證 | JWT（python-jose）、API Key |
| CLI | Typer + Rich |
| 測試 | pytest 8.0+、pytest-asyncio、httpx |

> **關鍵設計**：所有金額使用 `Decimal` 而非 `float`，確保財務計算無浮點誤差。

### 2.3 核心模組

```
src/
├── domain/models.py      ← 核心領域物件（Instrument、Bar、Position、Portfolio、Order、Trade）
├── config.py             ← 設定管理（QUANT_ 前綴環境變數）
├── data/
│   ├── feed.py           ← 抽象資料源介面
│   └── sources/yahoo.py  ← Yahoo Finance 資料源（含快取）
├── strategy/
│   ├── base.py           ← 策略抽象基類（on_bar → target weights dict）
│   ├── engine.py         ← 權重→訂單轉換引擎
│   └── factors.py        ← 純函式因子庫（動量、均值回歸、RSI、MA）
├── risk/
│   ├── rules.py          ← 宣告式風險規則工廠
│   └── engine.py         ← 風險引擎（依序執行，首個 REJECT 即停止）
├── execution/
│   ├── sim.py            ← 模擬撮合（含滑點、手續費、稅費）
│   └── oms.py            ← 訂單管理系統
├── backtest/
│   ├── engine.py         ← 事件驅動回測主迴圈
│   └── analytics.py      ← 績效指標（Sharpe、Sortino、最大回撤等）
├── api/
│   ├── app.py            ← FastAPI 應用入口
│   ├── schemas.py        ← Pydantic 請求/回應模型
│   ├── auth.py           ← JWT + API Key 認證
│   ├── state.py          ← AppState 單例
│   └── ws.py             ← WebSocket 頻道管理
└── cli/main.py           ← CLI 指令（backtest、server、status、factors）
```

### 2.4 策略清單

| 策略 | 邏輯 | 部位控制 |
|------|------|---------|
| **MomentumStrategy** | 買入過去 12 個月動量最強（跳過最近 1 個月）的前 10 檔 | 訊號加權配置 |
| **MeanReversionStrategy** | 買入 Z-score ≥ 1.5 標準差偏低的股票 | 風險平價（逆波動率）|

### 2.5 風險規則

| 規則 | 說明 |
|------|------|
| `max_position_weight` | 單一部位不得超過 NAV 5% |
| `max_order_notional` | 單筆訂單不得超過 NAV 的設定比例 |
| `daily_drawdown_limit` | 當日虧損超過 3% 停止下單 |
| `fat_finger_check` | 訂單價格偏離市場 5% 以上自動拒絕 |
| `max_daily_trades` | 單日最多 100 筆交易 |
| `max_order_vs_adv_pct` | 訂單不得超過日均量 10% |
| Kill Switch（週線）| 週虧損 10% 觸發全部停止 |

### 2.6 REST API 端點

| 端點 | 方法 | 說明 |
|------|------|------|
| `/api/v1/portfolio` | GET | 當前 NAV、現金、部位、P&L |
| `/api/v1/portfolio/positions` | GET | 詳細部位列表 |
| `/api/v1/orders` | GET | 訂單與成交記錄 |
| `/api/v1/orders` | POST | 手動下單（含風控） |
| `/api/v1/strategies` | GET | 策略列表與狀態 |
| `/api/v1/strategies/{name}/start` | POST | 啟動策略 |
| `/api/v1/strategies/{name}/stop` | POST | 停止策略 |
| `/api/v1/backtest` | POST | 觸發非同步回測 |
| `/api/v1/risk/status` | GET | 當前風險指標 |
| `/api/v1/risk/rules` | GET | 取得所有風控規則 |
| `/api/v1/risk/rules/{name}` | PUT | 切換風控規則（enabled） |
| `/api/v1/risk/alerts` | GET | 取得風險警報 |
| `/api/v1/risk/kill-switch` | POST | 緊急全部停止 |
| `/api/v1/system/health` | GET | 系統健康狀態 |
| `/api/v1/system/status` | GET | 系統詳細狀態 |

### 2.7 WebSocket 頻道

| 頻道 | 推播內容 |
|------|---------|
| `portfolio` | 部位與 NAV 即時更新 |
| `alerts` | 風險警報 |
| `orders` | 訂單成交與狀態變更 |
| `market` | 行情資料更新 |

連線格式：`ws://{host}:{port}/ws/{channel}`

### 2.8 重要環境變數

```bash
QUANT_MODE=backtest|paper|live
QUANT_DATABASE_URL=postgresql://user:pass@localhost:5432/quant
QUANT_DATA_SOURCE=yahoo
QUANT_API_HOST=0.0.0.0
QUANT_API_PORT=8000
QUANT_API_KEY=your-api-key          # 前端登入用
QUANT_JWT_SECRET=your-secret
QUANT_JWT_EXPIRE_MINUTES=1440       # 24 小時

QUANT_COMMISSION_RATE=0.001425      # 手續費 0.1425%
QUANT_TAX_RATE=0.003                # 賣方交易稅 0.3%
QUANT_DEFAULT_SLIPPAGE_BPS=5.0      # 滑點（bps）

QUANT_MAX_POSITION_PCT=0.05         # 單一部位上限 5%
QUANT_MAX_SECTOR_PCT=0.20           # 單一板塊上限 20%
QUANT_MAX_DAILY_DRAWDOWN_PCT=0.03   # 每日最大虧損 3%
QUANT_KILL_SWITCH_WEEKLY_DRAWDOWN_PCT=0.10  # 週熔斷 10%
QUANT_MAX_DAILY_TRADES=100
QUANT_FAT_FINGER_PCT=0.05

QUANT_BACKTEST_INITIAL_CASH=10000000
QUANT_BACKTEST_START=2020-01-01
QUANT_BACKTEST_END=2025-12-31
```

### 2.9 啟動方式

```bash
# 安裝
pip install -e ".[dev]"
cp .env.example .env

# 啟動資料庫
docker compose up -d db
make migrate

# 開發模式（熱重載）
make dev          # uvicorn --reload --port 8000

# 執行回測
make backtest ARGS="--strategy momentum -u AAPL -u MSFT --start 2023-01-01 --end 2024-12-31"

# 執行測試 / Lint
make test
make lint
```

---

## 三、前端：Quant Mobile

### 3.1 專案定位

React Native 行動應用程式，作為後端的**即時控制面板**，讓交易員在手機上完整操控量化交易系統。

**專案路徑**：`Ursa-Major/projects/quant-mobile`

### 3.2 技術棧

| 類別 | 技術 |
|------|------|
| 框架 | React Native 0.76.7 + Expo 52.0 |
| 路由 | Expo Router 4.0（檔案式路由） |
| 語言 | TypeScript 5.3（strict mode） |
| 狀態管理 | React Hooks（useState/useEffect/useCallback） |
| 安全儲存 | expo-secure-store（JWT、API Key 加密存儲） |
| 動畫 | react-native-reanimated 3.16 |
| 圖示 | @expo/vector-icons（Ionicons） |

### 3.3 畫面結構

```
app/
├── _layout.tsx          ← 根佈局（登入守衛）
├── login.tsx            ← 登入畫面（輸入 Server URL + API Key）
└── (tabs)/
    ├── _layout.tsx      ← Tab 導航佈局
    ├── index.tsx        ← Dashboard（投組總覽）
    ├── positions.tsx    ← 部位列表（未實現損益）
    ├── strategies.tsx   ← 策略控制（啟動/停止）
    ├── alerts.tsx       ← 風險警報 + 緊急停止
    └── settings.tsx     ← 系統狀態 + 風控規則管理
```

### 3.4 原始碼結構

```
src/
├── api/
│   ├── client.ts        ← HTTP 客戶端（自動帶入認證 Header）
│   ├── endpoints.ts     ← 所有 API 函式（型別安全）
│   └── ws.ts            ← WebSocket 管理（含心跳 30 秒 Ping、斷線重連 3 秒）
├── hooks/
│   ├── useAuth.ts       ← 認證狀態（登入/登出/自動還原 Session）
│   ├── usePortfolio.ts  ← 投組資料（10 秒輪詢 + WebSocket 即時更新）
│   └── useAlerts.ts     ← 風險警報（WebSocket 即時接收）
├── components/
│   ├── MetricCard.tsx   ← KPI 指標卡
│   ├── AlertItem.tsx    ← 警報列
│   ├── PositionRow.tsx  ← 部位列
│   └── StrategyRow.tsx  ← 策略列（含開關切換）
├── types/index.ts       ← 所有 TypeScript 型別定義
└── utils/format.ts      ← 貨幣、百分比格式化
```

### 3.5 資料流設計

```
┌──────────────────────────────────────┐
│          usePortfolio Hook           │
│  ┌──────────┐    ┌────────────────┐  │
│  │ REST API │    │  WebSocket     │  │
│  │ 10秒輪詢 │    │  即時推播      │  │
│  └────┬─────┘    └──────┬─────────┘  │
│       └────────┬─────────┘            │
│           Portfolio State             │
└───────────────┬──────────────────────┘
                ▼
         Dashboard UI Components
```

### 3.6 認證流程

```
App 啟動
    ↓
expo-secure-store 讀取已存 credentials
    ↓（有）                    ↓（無）
自動還原 Session          導向 login.tsx
    ↓                          ↓
GET /api/v1/system/health  輸入 Server URL + API Key
    ↓（200）                   ↓
進入 Dashboard        驗證後存入 secure-store → Dashboard
```

### 3.7 核心 TypeScript 型別

```typescript
// 投組快照
Portfolio {
  nav: number               // 淨資產值
  cash: number
  daily_pnl: number         // 當日損益
  daily_pnl_pct: number
  gross_exposure: number
  net_exposure: number
  positions_count: number
  positions: Position[]
  as_of: string             // ISO 時間戳
}

// 單一部位
Position {
  symbol: string
  quantity: number
  avg_cost: number
  market_price: number
  market_value: number
  unrealized_pnl: number
  weight: number            // 佔 NAV 比例
}

// 策略狀態
StrategyInfo {
  name: string
  status: "running" | "stopped" | "error"
  pnl: number
}

// 訂單
OrderInfo {
  id: string
  symbol: string
  side: "BUY" | "SELL"
  quantity: number
  price: number | null
  status: string
  filled_qty: number
  filled_avg_price: number
  commission: number
  created_at: string
  strategy_id: string
}

// 風險警報（由 WebSocket 即時接收）
RiskAlert {
  timestamp: string
  rule_name: string
  severity: "INFO" | "WARNING" | "CRITICAL"
  metric_value: number
  threshold: number
  action_taken: string
  message: string
}

// 系統狀態
SystemStatus {
  mode: string
  uptime_seconds: number
  strategies_running: number
  data_source: string
  database: string
}
```

### 3.8 啟動方式

```bash
# 安裝
npm install

# 開發模式
npm start            # Expo 互動選單
npm run ios          # iOS 模擬器
npm run android      # Android 模擬器

# 型別檢查 / Lint
npm run typecheck
npm run lint

# 第一次啟動設定
# Server URL: http://localhost:8000
#             （Android 模擬器請用 http://10.0.2.2:8000）
# API Key:    對應後端 .env 的 QUANT_API_KEY
```

---

## 四、前後端整合關係

### 4.1 連線對照表

| 前端畫面 | 後端端點 | 協議 |
|---------|---------|------|
| Dashboard 即時 NAV | `GET /api/v1/portfolio` | REST（10秒）+ WebSocket `portfolio` |
| Positions 部位列表 | `GET /api/v1/portfolio/positions` | REST |
| Strategies 啟動/停止 | `POST /api/v1/strategies/{id}/start\|stop` | REST |
| Alerts 警報 Feed | `GET /api/v1/risk/alerts` | REST + WebSocket `alerts` |
| Alerts Kill Switch | `POST /api/v1/risk/kill-switch` | REST |
| Settings 系統狀態 | `GET /api/v1/system/status` | REST |
| Settings 風控規則 | `GET /api/v1/risk/rules` + `PUT /api/v1/risk/rules/{name}` | REST |
| 登入驗證 | `GET /api/v1/system/health` | REST |

### 4.2 認證機制對應

```
前端 login.tsx 輸入 API Key
        ↓
src/api/client.ts 自動帶入 Header：
    "Authorization: Bearer {jwt_token}"
    "X-API-Key: {apiKey}"
        ↓
後端 src/api/auth.py → verify_api_key()
        ↓
JWT 角色分級：viewer < researcher < trader < risk_manager < admin
```

### 4.3 即時資料流

```
後端 WebSocket (/ws/portfolio)
        ↓
前端 src/api/ws.ts（心跳 30s Ping、斷線 3s 重連）
        ↓
src/hooks/usePortfolio.ts（接收推播，更新 React state）
        ↓
app/(tabs)/index.tsx → Dashboard 即時顯示
```

### 4.4 部署架構

```
[行動裝置]                    [伺服器/本機]
Quant Mobile App   ←HTTP→   FastAPI (Port 8000)
                   ←WS→     WebSocket (/ws/*)
                                    ↕
                             PostgreSQL (DB)
                                    ↕
                             Yahoo Finance API
```

### 4.5 版本相容性注意事項

| 項目 | 後端定義 | 前端使用 |
|------|---------|---------|
| API 前綴 | `/api/v1/` | `/api/v1/` ✓ |
| 策略回傳格式 | `{strategies: [...]}` | 取 `.strategies` 屬性 ✓ |
| 風險警報嚴重度 | INFO / WARNING / CRITICAL / EMERGENCY | INFO / WARNING / CRITICAL |
| 訂單 Side | `BUY` / `SELL`（Python Enum） | `"BUY" \| "SELL"`（TypeScript） |
| 金額型別 | 後端 `Decimal` → JSON 序列化 | 前端 `number` 接收 |

> ⚠️ **潛在問題**：後端使用 Python `Decimal` 進行金融計算，序列化至 JSON 時需確認 FastAPI 的 `jsonable_encoder` 將 `Decimal` 正確轉為數字，前端需統一處理。

---

## 五、本地開發完整啟動流程

```bash
# === Step 1：啟動後端 ===
cd Portfolio
cp .env.example .env          # 設定 QUANT_API_KEY=dev-key
docker compose up -d db       # 啟動 PostgreSQL
make migrate                  # 套用資料庫遷移
make dev                      # 啟動 FastAPI（http://0.0.0.0:8000）

# === Step 2：啟動前端 ===
cd Ursa-Major/projects/quant-mobile
npm install
npm start                     # 選擇 iOS/Android 模擬器

# === Step 3：前端連線設定 ===
# Server URL: http://localhost:8000
#             （Android 模擬器請改為 http://10.0.2.2:8000）
# API Key:    dev-key（對應後端 .env 的 QUANT_API_KEY）
```

---

## 六、關鍵設計決策摘要

| 決策 | 後端 | 前端 |
|------|------|------|
| 貨幣精度 | `Decimal`，無浮點誤差 | `number` 顯示用 |
| 策略介面 | 回傳目標權重 dict，引擎負責轉換訂單 | 只需顯示狀態/啟停 |
| 時間因果性 | `HistoricalFeed.set_current_date()` 確保回測不看未來資料 | 不適用 |
| 風險規則 | 純函式工廠（非繼承），首個 REJECT 即停止 | 僅顯示/切換規則開關 |
| 狀態管理 | AppState 單例 | React Hooks（無 Redux） |
| 認證 | JWT + API Key 雙重驗證 | expo-secure-store 加密儲存 |
| 即時資料 | WebSocket + 4 頻道訂閱 | WebSocket + 30s Ping 心跳 |
