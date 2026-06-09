from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)



def _extract_score_and_volatility(value: Any) -> tuple[float, float]:
    if isinstance(value, dict):
        score = float(value.get("score", 0.0))
        volatility = float(value.get("volatility", 0.15) or 0.15)
        return score, max(volatility, 1e-6)
    return float(value), 0.15



def compute_position_sizes(
    scores: dict[str, Any],
    config: dict[str, Any],
    portfolio_value: float,
) -> dict[str, float]:
    if portfolio_value <= 0 or not scores:
        return {}

    threshold = float(config.get("strategy", {}).get("signal_confidence_threshold", 0.55))
    risk_cfg = config.get("strategy", {}).get("risk", {})
    max_position_pct = float(risk_cfg.get("max_position_pct", 0.10))
    volatility_target = float(risk_cfg.get("volatility_target", 0.15))
    sizing_method = risk_cfg.get("position_sizing", "volatility_target")

    filtered: dict[str, tuple[float, float]] = {}
    for ticker, raw in scores.items():
        score, volatility = _extract_score_and_volatility(raw)
        if score > threshold:
            filtered[ticker] = (score, volatility)
    if not filtered:
        return {}

    raw_weights: dict[str, float] = {}
    for ticker, (score, volatility) in filtered.items():
        if sizing_method == "volatility_target":
            raw_weight = max(score - threshold, 0.0) * (volatility_target / max(volatility, 1e-6))
        else:
            raw_weight = max(score - threshold, 0.0)
        raw_weights[ticker] = max(raw_weight, 0.0)

    total_weight = sum(raw_weights.values())
    if total_weight <= 0:
        return {}

    capped_amount = portfolio_value * max_position_pct
    positions = {
        ticker: min((weight / total_weight) * portfolio_value, capped_amount)
        for ticker, weight in raw_weights.items()
    }
    return {ticker: amount for ticker, amount in positions.items() if amount > 0}


__all__ = ["compute_position_sizes"]
