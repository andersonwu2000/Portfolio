"""
Market scanner — wraps Shioaji scanner API for TW market universe discovery.

Provides ranked lists (volume, gainers, losers, amount) and regulatory
stock lists (disposition / attention) for universe filtering.
"""

from __future__ import annotations

from typing import Any


class ShioajiScanner:
    """Wraps shioaji scanner / punish / notice APIs."""

    def __init__(self, api: Any | None = None) -> None:
        self._api = api

    def _require_api(self) -> Any:
        if self._api is None:
            raise RuntimeError("Shioaji API not connected")
        return self._api

    # ── ranked scanners ────────────────────────────────────

    @staticmethod
    def _item_to_dict(item: Any) -> dict[str, Any]:
        return {
            "code": item.code,
            "name": item.name,
            "close": item.close,
            "volume": item.volume,
            "total_volume": item.total_volume,
            "change_price": item.change_price,
            "change_rate": item.change_rate,
        }

    def top_volume(self, count: int = 50) -> list[dict[str, Any]]:
        """Top stocks by volume rank (descending)."""
        api = self._require_api()
        import shioaji as sj

        items = api.scanners(
            scanner_type=sj.constant.ScannerType.VolumeRank,
            ascending=False,
            count=count,
        )
        return [self._item_to_dict(it) for it in items]

    def top_gainers(self, count: int = 50) -> list[dict[str, Any]]:
        """Top stocks by change percent (descending)."""
        api = self._require_api()
        import shioaji as sj

        items = api.scanners(
            scanner_type=sj.constant.ScannerType.ChangePercentRank,
            ascending=False,
            count=count,
        )
        return [self._item_to_dict(it) for it in items]

    def top_losers(self, count: int = 50) -> list[dict[str, Any]]:
        """Top stocks by change percent (ascending = biggest losers)."""
        api = self._require_api()
        import shioaji as sj

        items = api.scanners(
            scanner_type=sj.constant.ScannerType.ChangePercentRank,
            ascending=True,
            count=count,
        )
        return [self._item_to_dict(it) for it in items]

    def top_amount(self, count: int = 50) -> list[dict[str, Any]]:
        """Top stocks by turnover amount rank."""
        api = self._require_api()
        import shioaji as sj

        items = api.scanners(
            scanner_type=sj.constant.ScannerType.AmountRank,
            ascending=False,
            count=count,
        )
        return [self._item_to_dict(it) for it in items]

    # ── regulatory lists ───────────────────────────────────

    def get_disposition_stocks(self) -> set[str]:
        """Return stock codes under disposition (處置股)."""
        api = self._require_api()
        punish = api.punish()
        return set(punish.code)

    def get_attention_stocks(self) -> set[str]:
        """Return stock codes under attention (注意股)."""
        api = self._require_api()
        notice = api.notice()
        return set(notice.code)

    # ── composite universe ─────────────────────────────────

    def get_active_universe(
        self,
        count: int = 100,
        exclude_disposition: bool = True,
    ) -> list[str]:
        """
        Active universe = top volume stocks minus disposition/attention stocks.

        Parameters
        ----------
        count : int
            Number of volume-ranked stocks to start from.
        exclude_disposition : bool
            If True, remove disposition and attention stocks.
        """
        volume_list = self.top_volume(count=count)
        codes = [d["code"] for d in volume_list]

        if exclude_disposition:
            blocked = self.get_disposition_stocks() | self.get_attention_stocks()
            codes = [c for c in codes if c not in blocked]

        return codes
