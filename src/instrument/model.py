"""
金融工具模型 — 統一描述股票、ETF、期貨等所有可交易標的。

與 src/domain/models.py 中的舊 Instrument 共存：
- 舊 Instrument 繼續被 Position/Order 使用（向後相容）
- 新 Instrument 提供更豐富的 metadata，用於 InstrumentRegistry
- 可透過 to_legacy() 轉換為舊格式
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum


class AssetClass(Enum):
    """資產類別。"""

    EQUITY = "equity"  # 個股
    ETF = "etf"  # ETF（含債券/商品 ETF 代理）
    FUTURES = "futures"  # 期貨


class Market(Enum):
    """交易市場。"""

    TW = "tw"
    US = "us"


class Currency(Enum):
    """幣別。"""

    TWD = "TWD"
    USD = "USD"


class SubClass(Enum):
    """資產子類別 — 細分 ETF 暴露的底層資產。"""

    STOCK = "stock"
    ETF_EQUITY = "etf_equity"  # 股票型 ETF (SPY, 0050)
    ETF_BOND = "etf_bond"  # 債券 ETF (TLT, AGG)
    ETF_COMMODITY = "etf_commodity"  # 商品 ETF (GLD, USO)
    ETF_MIXED = "etf_mixed"  # 混合型 ETF
    FUTURE = "future"


@dataclass(frozen=True)
class Instrument:
    """
    金融工具的完整描述。

    所有可交易標的的統一模型，包含合約規格和交易成本資訊。
    """

    symbol: str  # 唯一識別碼: "2330.TW", "AAPL", "ES=F", "TLT"
    name: str = ""
    asset_class: AssetClass = AssetClass.EQUITY
    sub_class: SubClass = SubClass.STOCK
    market: Market = Market.US
    currency: Currency = Currency.USD

    # 合約規格
    contract_size: Decimal = Decimal("1")  # 期貨合約乘數
    tick_size: Decimal = Decimal("0.01")  # 最小跳動
    lot_size: int = 1  # 最小交易單位
    margin_rate: Decimal | None = None  # 保證金比率（期貨）
    expiry: date | None = None  # 到期日（期貨）

    # 交易成本
    commission_rate: Decimal = Decimal("0.001425")
    tax_rate: Decimal = Decimal("0")  # 賣出稅
    slippage_bps: Decimal = Decimal("5")

    # 分類標籤
    sector: str = ""
    tags: tuple[str, ...] = ()

    def to_legacy(self) -> object:
        """轉換為 src/domain/models.py 中的舊 Instrument 格式。"""
        from src.domain.models import AssetClass as LegacyAC
        from src.domain.models import Instrument as LegacyInst

        ac_map = {
            AssetClass.EQUITY: LegacyAC.EQUITY,
            AssetClass.ETF: LegacyAC.EQUITY,
            AssetClass.FUTURES: LegacyAC.FUTURE,
        }
        return LegacyInst(
            symbol=self.symbol,
            name=self.name,
            asset_class=ac_map.get(self.asset_class, LegacyAC.EQUITY),
            currency=self.currency.value,
            lot_size=self.lot_size,
            tick_size=self.tick_size,
            multiplier=self.contract_size,
        )


# ── 預設交易成本模板 ─────────────────────────────────────

TW_STOCK_DEFAULTS = dict(
    market=Market.TW,
    currency=Currency.TWD,
    lot_size=1000,
    commission_rate=Decimal("0.001425"),
    tax_rate=Decimal("0.003"),
    slippage_bps=Decimal("5"),
)

US_STOCK_DEFAULTS = dict(
    market=Market.US,
    currency=Currency.USD,
    lot_size=1,
    commission_rate=Decimal("0"),  # 多數美國券商免佣
    tax_rate=Decimal("0"),
    slippage_bps=Decimal("3"),
)

TW_FUTURES_DEFAULTS = dict(
    asset_class=AssetClass.FUTURES,
    sub_class=SubClass.FUTURE,
    market=Market.TW,
    currency=Currency.TWD,
    lot_size=1,
    margin_rate=Decimal("0.10"),  # ~10% 保證金
    commission_rate=Decimal("0.00002"),
    tax_rate=Decimal("0.00002"),
    slippage_bps=Decimal("3"),
)

US_FUTURES_DEFAULTS = dict(
    asset_class=AssetClass.FUTURES,
    sub_class=SubClass.FUTURE,
    market=Market.US,
    currency=Currency.USD,
    lot_size=1,
    commission_rate=Decimal("0"),
    tax_rate=Decimal("0"),
    slippage_bps=Decimal("3"),
)
