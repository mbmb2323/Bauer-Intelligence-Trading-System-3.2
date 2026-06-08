from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from bits.config.settings import get_database_url
from bits.data.storage import FeatureSnapshot, get_session, init_db

logger = logging.getLogger(__name__)


FEATURE_COLUMNS = [
    "rsi",
    "macd_line",
    "macd_signal",
    "macd_histogram",
    "bb_position",
    "bb_bandwidth",
    "atr",
    "vwap",
    "obv",
    "zscore_close",
    "momentum_5d",
    "momentum_10d",
    "momentum_20d",
    "momentum_60d",
    "corr_spy",
    "pe_ratio",
    "pb_ratio",
    "ev_ebitda",
    "revenue_growth",
    "earnings_surprise",
    "dividend_yield",
    "beta",
    "vader_compound_mean",
]



def _ensure_db(config: dict[str, Any]) -> None:
    init_db(get_database_url(config))



def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default



def _latest(series: pd.Series | None, default: float = 0.0) -> float:
    if series is None or series.empty:
        return default
    return _safe_float(series.iloc[-1], default=default)



def _benchmark_returns(config: dict[str, Any]) -> pd.Series | None:
    runtime = config.get("runtime", {})
    benchmark = runtime.get("spy_returns")
    if benchmark is None:
        benchmark = runtime.get("benchmark_returns")
    if benchmark is None:
        return None
    if isinstance(benchmark, pd.DataFrame):
        if "close" in benchmark.columns:
            return benchmark["close"].pct_change().dropna()
        if benchmark.shape[1] > 0:
            return benchmark.iloc[:, 0].pct_change().dropna()
    if isinstance(benchmark, pd.Series):
        return benchmark.dropna()
    return None



def build_features(
    ticker: str,
    df_ohlcv: pd.DataFrame,
    fundamentals: dict[str, Any] | None,
    sentiment_score: float,
    config: dict[str, Any],
) -> dict[str, float]:
    technical_cfg = config.get("features", {}).get("technical", {})
    stats_cfg = config.get("features", {}).get("statistical", {})
    bb_period = int(technical_cfg.get("bb_period", 20))
    df = df_ohlcv.copy()
    features = {column: 0.0 for column in FEATURE_COLUMNS}
    if df.empty or "close" not in df.columns:
        features.update(
            {
                "pe_ratio": _safe_float((fundamentals or {}).get("pe_ratio")),
                "pb_ratio": _safe_float((fundamentals or {}).get("pb_ratio")),
                "ev_ebitda": _safe_float((fundamentals or {}).get("ev_ebitda")),
                "revenue_growth": _safe_float((fundamentals or {}).get("revenue_growth")),
                "earnings_surprise": _safe_float((fundamentals or {}).get("earnings_surprise")),
                "dividend_yield": _safe_float((fundamentals or {}).get("dividend_yield")),
                "beta": _safe_float((fundamentals or {}).get("beta")),
                "vader_compound_mean": _safe_float(sentiment_score),
            }
        )
        return features

    df.columns = [str(column).lower() for column in df.columns]
    df = df.sort_index()
    for column in ["open", "high", "low", "close", "volume"]:
        if column not in df.columns:
            df[column] = 0.0
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    volume = df["volume"].fillna(0).astype(float)

    try:
        from ta.momentum import RSIIndicator
        from ta.trend import MACD
        from ta.volatility import AverageTrueRange, BollingerBands
        from ta.volume import OnBalanceVolumeIndicator, VolumeWeightedAveragePrice

        rsi = RSIIndicator(close=close, window=int(technical_cfg.get("rsi_period", 14))).rsi()
        macd_indicator = MACD(
            close=close,
            window_fast=int(technical_cfg.get("macd_fast", 12)),
            window_slow=int(technical_cfg.get("macd_slow", 26)),
            window_sign=int(technical_cfg.get("macd_signal", 9)),
        )
        bb = BollingerBands(close=close, window=bb_period, window_dev=float(technical_cfg.get("bb_std", 2.0)))
        atr = AverageTrueRange(high=high, low=low, close=close, window=int(technical_cfg.get("atr_period", 14))).average_true_range()
        bb_high = bb.bollinger_hband()
        bb_low = bb.bollinger_lband()
        bb_mid = bb.bollinger_mavg()
        bb_range = (bb_high - bb_low).replace(0, np.nan)
        bb_position = ((close - bb_low) / bb_range).clip(lower=0.0, upper=1.0)
        bb_bandwidth = ((bb_high - bb_low) / bb_mid.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)

        if bool(technical_cfg.get("vwap_enabled", True)) and volume.abs().sum() > 0:
            vwap_indicator = VolumeWeightedAveragePrice(
                high=high,
                low=low,
                close=close,
                volume=volume,
                window=max(1, min(bb_period, len(df))),
            )
            vwap = vwap_indicator.volume_weighted_average_price()
        else:
            vwap = pd.Series(0.0, index=df.index, dtype=float)

        if bool(technical_cfg.get("obv_enabled", True)) and volume.abs().sum() > 0:
            obv = OnBalanceVolumeIndicator(close=close, volume=volume).on_balance_volume()
        else:
            obv = pd.Series(0.0, index=df.index, dtype=float)

        features.update(
            {
                "rsi": _latest(rsi),
                "macd_line": _latest(macd_indicator.macd()),
                "macd_signal": _latest(macd_indicator.macd_signal()),
                "macd_histogram": _latest(macd_indicator.macd_diff()),
                "bb_position": _latest(bb_position),
                "bb_bandwidth": _latest(bb_bandwidth),
                "atr": _latest(atr),
                "vwap": _latest(vwap),
                "obv": _latest(obv),
            }
        )
    except ImportError:
        logger.warning("ta library not available; technical indicators defaulting to zero for %s", ticker)

    z_window = int(stats_cfg.get("zscore_window", 20))
    rolling_mean = close.rolling(z_window).mean()
    rolling_std = close.rolling(z_window).std(ddof=0).replace(0, np.nan)
    zscore = ((close - rolling_mean) / rolling_std).replace([np.inf, -np.inf], np.nan)
    features["zscore_close"] = _latest(zscore)

    for window in [5, 10, 20, 60]:
        features[f"momentum_{window}d"] = _safe_float(close.pct_change(window).iloc[-1] if len(close) > window else 0.0)

    benchmark_returns = _benchmark_returns(config)
    own_returns = close.pct_change().dropna()
    if benchmark_returns is not None and not own_returns.empty:
        aligned = pd.concat([own_returns, benchmark_returns.rename("benchmark")], axis=1).dropna()
        corr_window = int(stats_cfg.get("correlation_window", 60))
        if len(aligned) >= 2:
            aligned = aligned.tail(corr_window)
            features["corr_spy"] = _safe_float(aligned.iloc[:, 0].corr(aligned.iloc[:, 1]))

    fundamentals = fundamentals or {}
    for column in [
        "pe_ratio",
        "pb_ratio",
        "ev_ebitda",
        "revenue_growth",
        "earnings_surprise",
        "dividend_yield",
        "beta",
    ]:
        features[column] = _safe_float(fundamentals.get(column))
    features["vader_compound_mean"] = _safe_float(sentiment_score)

    return {key: _safe_float(value) for key, value in features.items()}



def store_features(
    ticker: str,
    snapshot_date: datetime,
    version: str,
    features: dict[str, float],
    config: dict[str, Any],
) -> None:
    _ensure_db(config)
    session = get_session()
    try:
        existing = (
            session.query(FeatureSnapshot)
            .filter_by(ticker=ticker, snapshot_date=snapshot_date, version=version)
            .order_by(FeatureSnapshot.id.desc())
            .first()
        )
        payload = json.dumps({key: _safe_float(value) for key, value in features.items()}, sort_keys=True)
        if existing:
            existing.features_json = payload
        else:
            session.add(
                FeatureSnapshot(
                    ticker=ticker,
                    snapshot_date=snapshot_date,
                    version=version,
                    features_json=payload,
                )
            )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()



def load_features(
    ticker: str,
    snapshot_date: datetime,
    version: str,
    config: dict[str, Any],
) -> dict[str, float]:
    _ensure_db(config)
    session = get_session()
    try:
        row = (
            session.query(FeatureSnapshot)
            .filter_by(ticker=ticker, snapshot_date=snapshot_date, version=version)
            .order_by(FeatureSnapshot.id.desc())
            .first()
        )
        if row is None:
            return {}
        data = json.loads(row.features_json)
        return {str(key): _safe_float(value) for key, value in data.items()}
    finally:
        session.close()


__all__ = ["FEATURE_COLUMNS", "build_features", "load_features", "store_features"]
