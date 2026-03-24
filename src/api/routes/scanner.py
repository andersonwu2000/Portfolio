"""Scanner & Market Data API routes — 市場掃描、快照、歷史 tick。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.api.auth import verify_api_key

router = APIRouter(prefix="/scanner", tags=["scanner"])


# ── Schemas ───────────────────────────────────────────────


class ScannerItem(BaseModel):
    code: str
    name: str = ""
    close: float = 0
    volume: int = 0
    total_volume: int = 0
    change_price: float = 0
    change_rate: float = 0


class ScannerResponse(BaseModel):
    items: list[ScannerItem]
    count: int
    scanner_type: str


class RegulatoryResponse(BaseModel):
    disposition: list[str]
    attention: list[str]


class ActiveUniverseResponse(BaseModel):
    symbols: list[str]
    count: int
    excluded_disposition: int
    excluded_attention: int


# ── Endpoints ─────────────────────────────────────────────


@router.get("/top-volume", response_model=ScannerResponse)
async def top_volume(
    count: int = Query(default=50, ge=1, le=200),
    api_key: str = Depends(verify_api_key),
) -> ScannerResponse:
    """成交量排行。"""
    scanner = _get_scanner()
    items = scanner.top_volume(count=count)
    return ScannerResponse(
        items=[ScannerItem(**i) for i in items],
        count=len(items),
        scanner_type="volume",
    )


@router.get("/top-gainers", response_model=ScannerResponse)
async def top_gainers(
    count: int = Query(default=50, ge=1, le=200),
    api_key: str = Depends(verify_api_key),
) -> ScannerResponse:
    """漲幅排行。"""
    scanner = _get_scanner()
    items = scanner.top_gainers(count=count)
    return ScannerResponse(
        items=[ScannerItem(**i) for i in items],
        count=len(items),
        scanner_type="gainers",
    )


@router.get("/top-losers", response_model=ScannerResponse)
async def top_losers(
    count: int = Query(default=50, ge=1, le=200),
    api_key: str = Depends(verify_api_key),
) -> ScannerResponse:
    """跌幅排行。"""
    scanner = _get_scanner()
    items = scanner.top_losers(count=count)
    return ScannerResponse(
        items=[ScannerItem(**i) for i in items],
        count=len(items),
        scanner_type="losers",
    )


@router.get("/top-amount", response_model=ScannerResponse)
async def top_amount(
    count: int = Query(default=50, ge=1, le=200),
    api_key: str = Depends(verify_api_key),
) -> ScannerResponse:
    """成交金額排行。"""
    scanner = _get_scanner()
    items = scanner.top_amount(count=count)
    return ScannerResponse(
        items=[ScannerItem(**i) for i in items],
        count=len(items),
        scanner_type="amount",
    )


@router.get("/regulatory", response_model=RegulatoryResponse)
async def regulatory_stocks(
    api_key: str = Depends(verify_api_key),
) -> RegulatoryResponse:
    """查詢處置股與注意股清單。"""
    scanner = _get_scanner()
    return RegulatoryResponse(
        disposition=sorted(scanner.get_disposition_stocks()),
        attention=sorted(scanner.get_attention_stocks()),
    )


@router.get("/active-universe", response_model=ActiveUniverseResponse)
async def active_universe(
    count: int = Query(default=100, ge=10, le=500),
    exclude_disposition: bool = Query(default=True),
    api_key: str = Depends(verify_api_key),
) -> ActiveUniverseResponse:
    """動態活躍 universe（成交量排行 - 處置/注意股）。"""
    scanner = _get_scanner()
    symbols = scanner.get_active_universe(
        count=count, exclude_disposition=exclude_disposition,
    )
    disp_count = len(scanner.get_disposition_stocks()) if exclude_disposition else 0
    attn_count = len(scanner.get_attention_stocks()) if exclude_disposition else 0
    return ActiveUniverseResponse(
        symbols=symbols,
        count=len(symbols),
        excluded_disposition=disp_count,
        excluded_attention=attn_count,
    )


@router.get("/snapshot")
async def get_snapshot(
    symbols: str = Query(description="Comma-separated stock codes, e.g. 2330,2317,2454"),
    api_key: str = Depends(verify_api_key),
) -> dict[str, Any]:
    """批量即時快照（最多 500 檔）。"""
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        raise HTTPException(status_code=400, detail="No symbols provided")
    if len(symbol_list) > 500:
        raise HTTPException(status_code=400, detail="Max 500 symbols per request")

    from src.api.state import get_app_state

    state = get_app_state()
    broker = getattr(state.execution_service, "broker", None)
    if broker is None or not broker.is_connected():
        raise HTTPException(status_code=503, detail="Broker not connected")

    from src.data.sources.shioaji_feed import ShioajiFeed

    feed = ShioajiFeed(api=broker.api, universe=symbol_list)
    df = feed.get_snapshot(symbol_list)

    if df.empty:
        return {"items": [], "count": 0}

    items = df.to_dict(orient="records")
    return {"items": items, "count": len(items)}


# ── Helpers ───────────────────────────────────────────────


def _get_scanner() -> Any:
    """取得 ShioajiScanner 實例。"""
    from src.api.state import get_app_state
    from src.data.scanner import ShioajiScanner

    state = get_app_state()
    broker = getattr(state.execution_service, "broker", None)
    api = getattr(broker, "api", None) if broker else None
    return ShioajiScanner(api=api)
