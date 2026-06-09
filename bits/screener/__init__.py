from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from bits.config.settings import get_database_url, get_tickers
from bits.data.ingestion import load_ohlcv
from bits.data.news import load_recent_sentiment
from bits.data.storage import FundamentalSnapshot, get_session, init_db
from bits.features import build_features, store_features
from bits.models import load_model, predict_screener

logger = logging.getLogger(__name__)

RESULT_COLUMNS = [
    "ticker",
    "composite_score",
    "momentum_score",
    "quality_score",
    "value_score",
    "ml_alpha",
    "rank",
]



def _series_percentile(values: pd.Series, ascending: bool = True) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan)
    if numeric.dropna().empty:
        return pd.Series(0.5, index=values.index, dtype=float)
    return numeric.rank(pct=True, ascending=ascending).fillna(0.5)



def _latest_fundamentals(ticker: str) -> dict[str, float]:
    session = get_session()
    try:
        row = (
            session.query(FundamentalSnapshot)
            .filter(FundamentalSnapshot.ticker == ticker)
            .order_by(FundamentalSnapshot.fetched_at.desc(), FundamentalSnapshot.id.desc())
            .first()
        )
        if row is None:
            return {}
        return {
            "pe_ratio": row.pe_ratio,
            "pb_ratio": row.pb_ratio,
            "ev_ebitda": row.ev_ebitda,
            "revenue_growth": row.revenue_growth,
            "earnings_surprise": row.earnings_surprise,
            "dividend_yield": row.dividend_yield,
            "beta": row.beta,
        }
    finally:
        session.close()



def _build_feature_frame(config: dict[str, Any]) -> pd.DataFrame:
    init_db(get_database_url(config))
    tickers = get_tickers(config)
    if not tickers:
        return pd.DataFrame()

    interval = str(config.get("data", {}).get("bar_size", "1d"))
    benchmark_df = load_ohlcv("SPY", interval=interval)
    runtime_config = dict(config)
    runtime_config["runtime"] = {**config.get("runtime", {}), "spy_returns": benchmark_df.get("close", pd.Series(dtype=float)).pct_change().dropna()}

    rows: list[dict[str, Any]] = []
    for ticker in tickers:
        df = load_ohlcv(ticker, interval=interval)
        if df.empty:
            continue
        fundamentals = _latest_fundamentals(ticker)
        sentiment = load_recent_sentiment(ticker, hours=int(config.get("data", {}).get("news_max_age_hours", 24)))
        features = build_features(ticker, df, fundamentals, sentiment, runtime_config)
        store_features(
            ticker=ticker,
            snapshot_date=pd.Timestamp(df.index.max()).to_pydatetime() if not df.empty else datetime.utcnow(),
            version="latest",
            features=features,
            config=config,
        )
        rows.append({"ticker": ticker, **features})
    return pd.DataFrame(rows)



def run_screener(config: dict[str, Any]) -> pd.DataFrame:
    try:
        feature_df = _build_feature_frame(config)
    except Exception as exc:
        logger.warning("Screener data load failed: %s", exc)
        return pd.DataFrame(columns=RESULT_COLUMNS)

    if feature_df.empty:
        return pd.DataFrame(columns=RESULT_COLUMNS)

    feature_df = feature_df.set_index("ticker")
    momentum_score = _series_percentile(feature_df["momentum_20d"], ascending=True)
    quality_base = feature_df[["revenue_growth", "earnings_surprise"]].fillna(0.0).mean(axis=1)
    quality_score = _series_percentile(quality_base, ascending=True)
    pe_rank = _series_percentile(feature_df["pe_ratio"].replace(0.0, np.nan), ascending=False)
    pb_rank = _series_percentile(feature_df["pb_ratio"].replace(0.0, np.nan), ascending=False)
    value_score = ((pe_rank + pb_rank) / 2.0).fillna(0.5)

    try:
        model = load_model("screener", config)
        ml_alpha = _series_percentile(predict_screener(model, feature_df), ascending=True)
    except Exception:
        ml_alpha = ((momentum_score + quality_score + value_score) / 3.0).fillna(0.5)

    weights = config.get("screener", {}).get("weights", {})
    composite = (
        momentum_score * float(weights.get("momentum", 0.30))
        + quality_score * float(weights.get("quality", 0.20))
        + value_score * float(weights.get("value", 0.20))
        + ml_alpha * float(weights.get("ml_alpha", 0.30))
    )

    result = pd.DataFrame(
        {
            "ticker": feature_df.index.to_list(),
            "composite_score": composite.astype(float).to_numpy(),
            "momentum_score": momentum_score.astype(float).to_numpy(),
            "quality_score": quality_score.astype(float).to_numpy(),
            "value_score": value_score.astype(float).to_numpy(),
            "ml_alpha": ml_alpha.astype(float).to_numpy(),
        }
    ).sort_values(["composite_score", "ticker"], ascending=[False, True])
    result = result[result["composite_score"] >= float(config.get("screener", {}).get("min_composite_score", 0.0))]
    result = result.head(int(config.get("screener", {}).get("top_n", 20))).reset_index(drop=True)
    result["rank"] = np.arange(1, len(result) + 1)
    return result[RESULT_COLUMNS]


__all__ = ["RESULT_COLUMNS", "run_screener"]
