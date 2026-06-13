"""
Portfolio optimizer — turn raw signals into target weights subject to constraints.

Self-contained, with no external dependencies.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class OptConstraints:
    """Portfolio constraints."""
    max_weight: float = 0.05            # per-symbol cap
    max_total_weight: float = 0.95      # total invested cap (5% cash buffer)
    min_weight: float = 0.001           # below this -> drop to 0
    long_only: bool = True


def equal_weight(
    signals: dict[str, float],
    constraints: OptConstraints | None = None,
) -> dict[str, float]:
    """Equal weight across all symbols with positive signal."""
    c = constraints or OptConstraints()

    if c.long_only:
        selected = {k: v for k, v in signals.items() if v > 0}
    else:
        selected = {k: v for k, v in signals.items() if abs(v) > 0}

    if not selected:
        return {}

    n = len(selected)
    w = min(c.max_weight, c.max_total_weight / n)

    return {symbol: w for symbol in selected}


def signal_weight(
    signals: dict[str, float],
    constraints: OptConstraints | None = None,
) -> dict[str, float]:
    """Weight by signal strength."""
    c = constraints or OptConstraints()

    if c.long_only:
        filtered = {k: v for k, v in signals.items() if v > 0}
    else:
        filtered = {k: v for k, v in signals.items() if abs(v) > 0}

    if not filtered:
        return {}

    total_signal = sum(abs(v) for v in filtered.values())
    if total_signal == 0:
        return {}

    weights = {}
    for symbol, sig in filtered.items():
        raw_w = (sig / total_signal) * c.max_total_weight
        w = max(-c.max_weight, min(c.max_weight, raw_w))
        if abs(w) >= c.min_weight:
            weights[symbol] = w

    if not c.long_only:
        total_short = sum(w for w in weights.values() if w < 0)
        if total_short < -c.max_total_weight:
            scale = -c.max_total_weight / total_short
            weights = {k: (v * scale if v < 0 else v) for k, v in weights.items()}

    return weights


def risk_parity(
    signals: dict[str, float],
    volatilities: dict[str, float],
    constraints: OptConstraints | None = None,
) -> dict[str, float]:
    """Inverse-volatility weighting; equal risk contribution."""
    c = constraints or OptConstraints()

    zero_vol_assets = [
        k for k in signals
        if signals[k] > 0 and k in volatilities and volatilities[k] == 0
    ]
    if zero_vol_assets:
        logger.warning(
            "risk_parity: assets with zero volatility excluded: %s", zero_vol_assets
        )

    selected = {
        k: volatilities[k]
        for k in signals
        if signals[k] > 0 and k in volatilities and volatilities[k] > 0
    }

    if not selected:
        return {}

    inv_vols = {k: 1.0 / v for k, v in selected.items()}
    total_inv = sum(inv_vols.values())

    weights = {}
    for symbol, inv_v in inv_vols.items():
        raw_w = (inv_v / total_inv) * c.max_total_weight
        w = min(c.max_weight, raw_w)
        if w >= c.min_weight:
            weights[symbol] = w

    return weights
