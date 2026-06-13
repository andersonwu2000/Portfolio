"""
Revenue momentum strategy package for this course project.

Main strategy:  RevenueMomentumHedgedStrategy  (revenue_momentum_hedged)
Inner engine:   RevenueMomentumStrategy        (revenue_momentum)

Quick start:
    from strategies import RevenueMomentumHedgedStrategy
    strategy = RevenueMomentumHedgedStrategy(revenue_dir="data")
    weights = strategy.on_bar(ctx)   # ctx must implement Context API (see base.py)
"""

from .base import Context, Strategy
from .optimizer import OptConstraints, equal_weight, risk_parity, signal_weight
from .registry import list_strategies, register_strategy, resolve_strategy
from .momentum import MomentumStrategy
from .revenue_momentum import RevenueMomentumStrategy
from .revenue_momentum_hedged import RevenueMomentumHedgedStrategy

__all__ = [
    "Context",
    "Strategy",
    "OptConstraints",
    "equal_weight",
    "signal_weight",
    "risk_parity",
    "list_strategies",
    "register_strategy",
    "resolve_strategy",
    "MomentumStrategy",
    "RevenueMomentumStrategy",
    "RevenueMomentumHedgedStrategy",
]
