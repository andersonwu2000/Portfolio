"""
Strategy registry — trimmed to revenue_momentum + revenue_momentum_hedged only.

The original production registry held many strategies; this copy keeps only
the few relevant to this course package.
"""

from __future__ import annotations

import functools
import inspect
import logging
from typing import Any, Callable, TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .base import Strategy

_REGISTRY: dict[str, type["Strategy"]] = {}


def register_strategy(name: str) -> Callable[[type["Strategy"]], type["Strategy"]]:
    """Decorator: register a strategy class by name."""
    def decorator(cls: type["Strategy"]) -> type["Strategy"]:
        _REGISTRY[name] = cls
        return cls
    return decorator


@functools.lru_cache(maxsize=1)
def _load_strategy_map() -> dict[str, type["Strategy"]]:
    from .revenue_momentum import RevenueMomentumStrategy
    from .revenue_momentum_hedged import RevenueMomentumHedgedStrategy
    from .momentum import MomentumStrategy

    legacy: dict[str, type["Strategy"]] = {
        "revenue_momentum": RevenueMomentumStrategy,
        "revenue_momentum_hedged": RevenueMomentumHedgedStrategy,
        "momentum_12_1": MomentumStrategy,
    }
    return {**legacy, **_REGISTRY}


def list_strategies() -> list[str]:
    return list(_load_strategy_map().keys())


def resolve_strategy(name: str, params: dict[str, Any] | None = None) -> "Strategy":
    """Instantiate a strategy by registered name."""
    strategy_map = _load_strategy_map()
    cls = strategy_map.get(name)
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
            return cls(**params)
        valid_params = set(sig.parameters.keys()) - {"self"}
        dropped = {k: v for k, v in params.items() if k not in valid_params}
        if dropped:
            logger.warning(
                "resolve_strategy(%s): unknown parameters ignored: %s",
                name, list(dropped.keys()),
            )
        filtered = {k: v for k, v in params.items() if k in valid_params}
        return cls(**filtered)
    return cls()
