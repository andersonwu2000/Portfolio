"""
配置體系 — Pydantic Settings，一目了然，型別安全。

優先級：環境變數 > .env 檔案 > 預設值
"""

from __future__ import annotations

import threading
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TradingConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="QUANT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── 環境 ──
    env: Literal["dev", "staging", "prod"] = "dev"

    # ── 運行模式 ──
    mode: Literal["backtest", "paper", "live"] = "backtest"

    # ── 數據庫 ──
    database_url: str = "postgresql://postgres:postgres@localhost:5432/quant"

    # ── 數據源 ──
    data_source: Literal["yahoo", "fubon", "twse"] = "yahoo"
    data_cache_dir: str = ".cache/market_data"

    # ── 風控 ──
    max_position_pct: float = 0.05
    max_sector_pct: float = 0.20
    max_daily_drawdown_pct: float = 0.03
    kill_switch_weekly_drawdown_pct: float = 0.10
    max_daily_trades: int = 100
    fat_finger_pct: float = 0.05
    max_order_vs_adv_pct: float = 0.10

    # ── 執行 ──
    default_slippage_bps: float = 5.0
    commission_rate: float = 0.001425       # 台灣券商手續費
    tax_rate: float = 0.003                 # 台灣證交稅 (賣出)

    # ── API ──
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 1
    api_key: str = "dev-key"
    jwt_secret: str = "change-me-in-production"
    jwt_expire_minutes: int = 1440          # 24 小時
    allowed_origins: list[str] = ["http://localhost:3000"]

    # ── 日誌 ──
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "text"

    # ── 回測 ──
    backtest_initial_cash: float = 10_000_000.0
    backtest_start: str = "2020-01-01"
    backtest_end: str = "2025-12-31"
    backtest_timeout: int = 1800            # 秒

    @model_validator(mode="after")
    def _check_prod_secrets(self) -> "TradingConfig":
        """Non-dev environments must not use default secrets."""
        if self.env != "dev":
            if self.api_key == "dev-key":
                raise ValueError("QUANT_API_KEY must be set in non-dev environments (cannot use 'dev-key')")
            if self.jwt_secret == "change-me-in-production":
                raise ValueError("QUANT_JWT_SECRET must be set in non-dev environments")
        return self


# 全局單例（thread-safe）
_config: TradingConfig | None = None
_config_lock = threading.Lock()


def get_config() -> TradingConfig:
    global _config
    if _config is None:
        with _config_lock:
            if _config is None:
                _config = TradingConfig()
    return _config


def override_config(config: TradingConfig) -> None:
    """測試用：注入自訂配置。"""
    global _config
    _config = config
