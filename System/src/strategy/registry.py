"""
策略註冊表 — 集中管理策略名稱到類別的對應，供 API 和 CLI 共用。
"""

from __future__ import annotations

import functools
import inspect
import logging
from typing import Any, TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from src.strategy.base import Strategy


@functools.lru_cache(maxsize=1)
def _load_strategy_map() -> dict[str, type[Strategy]]:
    """Lazy import 所有策略類別（結果快取，只執行一次）。"""
    strategy_map: dict[str, type[Strategy]] = {}

    _optional_imports: list[tuple[str, str, str]] = [
        ("strategies.revenue_momentum", "RevenueMomentumStrategy", "revenue_momentum"),
        ("src.alpha.strategy", "AlphaStrategy", "alpha"),
    ]

    import importlib
    for mod_path, cls_name, key in _optional_imports:
        try:
            mod = importlib.import_module(mod_path)
            strategy_map[key] = getattr(mod, cls_name)
        except (ImportError, AttributeError):
            logger.debug("Strategy %s not available (module %s)", key, mod_path)

    return strategy_map


_ALIASES: dict[str, str] = {}


def list_strategies() -> list[str]:
    """回傳所有可用的策略名稱（不含別名）。"""
    return list(_load_strategy_map().keys())


def resolve_strategy(name: str, params: dict[str, Any] | None = None) -> Strategy:
    """
    根據名稱解析並實例化策略。

    Args:
        name: 策略名稱（需在註冊表中）
        params: 傳給策略建構子的參數（選用）

    Raises:
        ValueError: 未知的策略名稱
    """
    canonical = _ALIASES.get(name, name)
    strategy_map = _load_strategy_map()
    cls = strategy_map.get(canonical)
    if cls is None:
        raise ValueError(
            f"Unknown strategy: {name}. Available: {list(strategy_map.keys())}"
        )

    if params:
        sig = inspect.signature(cls.__init__)
        has_var_keyword = any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        )
        if has_var_keyword:
            # Class accepts **kwargs — pass all params through
            return cls(**params)
        valid_params = set(sig.parameters.keys()) - {"self"}
        dropped = {k: v for k, v in params.items() if k not in valid_params}
        if dropped:
            logger.warning(
                "resolve_strategy(%s): unknown parameters ignored: %s", name, list(dropped.keys())
            )
        filtered = {k: v for k, v in params.items() if k in valid_params}
        return cls(**filtered)
    return cls()
