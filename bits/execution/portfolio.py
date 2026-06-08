from __future__ import annotations

import argparse
import logging
import sys
from typing import Any

from bits.config.settings import load_config

logger = logging.getLogger(__name__)



def get_current_positions(config: dict[str, Any]) -> dict[str, float]:
    execution_cfg = config.get("execution", {})
    alpaca_cfg = execution_cfg.get("alpaca", {})
    api_key = alpaca_cfg.get("api_key")
    api_secret = alpaca_cfg.get("api_secret")
    if not api_key or not api_secret:
        return {}

    try:
        from alpaca.trading.client import TradingClient
    except ImportError:
        logger.warning("alpaca-py not installed; returning empty positions")
        return {}

    try:
        client = TradingClient(api_key, api_secret, paper=bool(execution_cfg.get("paper_trading", True)))
        positions = client.get_all_positions()
        return {position.symbol: float(position.market_value or 0.0) for position in positions}
    except Exception as exc:
        logger.warning("Failed to fetch current positions: %s", exc)
        return {}



def submit_orders(target_positions: dict[str, float], config: dict[str, Any]) -> list[str]:
    execution_cfg = config.get("execution", {})
    paper_trading = bool(execution_cfg.get("paper_trading", True)) or execution_cfg.get("broker") == "paper"
    if paper_trading:
        receipts = []
        for ticker, value in target_positions.items():
            receipt = f"paper-{ticker}-{value:.2f}"
            logger.info("Paper order: %s -> %.2f", ticker, value)
            receipts.append(receipt)
        return receipts

    alpaca_cfg = execution_cfg.get("alpaca", {})
    api_key = alpaca_cfg.get("api_key")
    api_secret = alpaca_cfg.get("api_secret")
    if not api_key or not api_secret:
        logger.warning("Missing Alpaca credentials; no orders submitted")
        return []

    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.requests import MarketOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce
    except ImportError:
        logger.warning("alpaca-py not installed; no orders submitted")
        return []

    client = TradingClient(api_key, api_secret, paper=False)
    order_ids: list[str] = []
    tif_value = str(execution_cfg.get("order_defaults", {}).get("time_in_force", "day")).lower()
    for ticker, target_value in target_positions.items():
        side = OrderSide.BUY if target_value >= 0 else OrderSide.SELL
        notional = abs(float(target_value))
        if notional <= 0:
            continue
        try:
            order = client.submit_order(
                order_data=MarketOrderRequest(
                    symbol=ticker,
                    notional=notional,
                    side=side,
                    time_in_force=TimeInForce.DAY if tif_value == "day" else TimeInForce.GTC,
                )
            )
            order_ids.append(str(order.id))
        except Exception as exc:
            logger.warning("Order submission failed for %s: %s", ticker, exc)
    return order_ids



def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Submit BITS portfolio trades")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    args = parser.parse_args(sys.argv[2:] if argv is None else argv)

    config = load_config(args.config)
    current_positions = get_current_positions(config)
    print(current_positions)
    return 0


__all__ = ["cli", "get_current_positions", "submit_orders"]
