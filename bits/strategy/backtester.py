from __future__ import annotations

import argparse
import logging
import math
from typing import Any

import pandas as pd

from bits.config.settings import get_database_url, get_tickers, load_config
from bits.data.ingestion import load_ohlcv
from bits.data.storage import init_db

logger = logging.getLogger(__name__)



def _portfolio_metrics(equity_curve: pd.Series, daily_returns: pd.Series, n_trades: int) -> dict[str, float]:
    if equity_curve.empty:
        return {"total_return": 0.0, "sharpe_ratio": 0.0, "max_drawdown": 0.0, "n_trades": 0}
    cumulative_max = equity_curve.cummax()
    drawdown = equity_curve / cumulative_max - 1.0
    sharpe = 0.0
    if daily_returns.std(ddof=0) > 0:
        sharpe = float((daily_returns.mean() / daily_returns.std(ddof=0)) * math.sqrt(252))
    return {
        "total_return": float(equity_curve.iloc[-1] / equity_curve.iloc[0] - 1.0),
        "sharpe_ratio": sharpe,
        "max_drawdown": float(drawdown.min()),
        "n_trades": int(n_trades),
    }



def backtest(tickers: list[str], config: dict[str, Any]) -> dict[str, float]:
    init_db(get_database_url(config))
    interval = str(config.get("data", {}).get("bar_size", "1d"))
    frames: dict[str, pd.Series] = {}
    for ticker in tickers:
        df = load_ohlcv(ticker, interval=interval)
        if not df.empty and "close" in df.columns:
            frames[ticker] = df["close"].astype(float)
    if not frames:
        return {"total_return": 0.0, "sharpe_ratio": 0.0, "max_drawdown": 0.0, "n_trades": 0}

    close_df = pd.DataFrame(frames).sort_index().ffill().dropna(how="all")
    returns = close_df.pct_change().fillna(0.0)
    momentum = close_df.pct_change(20)
    top_n = max(1, int(config.get("screener", {}).get("top_n", min(5, len(close_df.columns)))))
    commission_bps = float(config.get("strategy", {}).get("backtester", {}).get("commission_bps", 5))
    slippage_bps = float(config.get("strategy", {}).get("backtester", {}).get("slippage_bps", 2))

    daily_strategy_returns: list[float] = []
    positions_history: list[tuple[str, ...]] = []
    dates = returns.index
    for idx in range(len(dates)):
        if idx == 0:
            daily_strategy_returns.append(0.0)
            positions_history.append(tuple())
            continue
        signal_date = dates[idx - 1]
        signal = momentum.loc[signal_date].dropna().sort_values(ascending=False)
        picks = tuple(signal.head(top_n).index.tolist()) if not signal.empty else tuple()
        positions_history.append(picks)
        if not picks:
            daily_strategy_returns.append(0.0)
            continue
        gross_return = float(returns.loc[dates[idx], list(picks)].mean())
        previous_picks = positions_history[-2] if len(positions_history) > 1 else tuple()
        turnover = len(set(picks).symmetric_difference(previous_picks)) / max(len(picks), 1)
        costs = turnover * (commission_bps + slippage_bps) / 10000.0
        daily_strategy_returns.append(gross_return - costs)

    strategy_returns = pd.Series(daily_strategy_returns, index=dates, dtype=float)
    initial_capital = float(config.get("strategy", {}).get("backtester", {}).get("initial_capital", 100000.0))
    equity_curve = initial_capital * (1.0 + strategy_returns).cumprod()
    n_trades = sum(1 for i in range(1, len(positions_history)) if positions_history[i] != positions_history[i - 1])
    return _portfolio_metrics(equity_curve, strategy_returns, n_trades)



def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the BITS backtester")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    args = parser.parse_args(argv or None)

    config = load_config(args.config)
    results = backtest(get_tickers(config), config)
    print(results)
    return 0


__all__ = ["backtest", "cli"]
