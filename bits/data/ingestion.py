"""Market data ingestion using yfinance."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from bits.data.storage import OHLCVBar, FundamentalSnapshot, get_session

logger = logging.getLogger(__name__)

# Lazy import so yfinance is optional during unit tests
def _yf():
    import yfinance as yf  # noqa: PLC0415
    return yf


def fetch_ohlcv(
    tickers: list[str],
    lookback_days: int = 365,
    interval: str = "1d",
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict[str, pd.DataFrame]:
    """
    Download OHLCV bars for *tickers* using yfinance.

    Returns a mapping of ticker -> DataFrame with columns
    [open, high, low, close, volume, adj_close].
    """
    yf = _yf()
    end_dt = end or datetime.utcnow()
    start_dt = start or (end_dt - timedelta(days=lookback_days))

    logger.info(
        "Fetching OHLCV for %d tickers (%s → %s, interval=%s)",
        len(tickers),
        start_dt.date(),
        end_dt.date(),
        interval,
    )
    raw = yf.download(
        tickers,
        start=start_dt.strftime("%Y-%m-%d"),
        end=end_dt.strftime("%Y-%m-%d"),
        interval=interval,
        group_by="ticker",
        auto_adjust=False,
        progress=False,
        threads=True,
    )

    result: dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        try:
            if len(tickers) == 1:
                df = raw.copy()
            else:
                df = raw[ticker].copy()
            df.columns = [c.lower() for c in df.columns]
            df = df.rename(columns={"adj close": "adj_close"})
            df = df.dropna(subset=["close"])
            df.index = pd.to_datetime(df.index)
            result[ticker] = df
        except (KeyError, Exception) as exc:
            logger.warning("Could not parse data for %s: %s", ticker, exc)
    return result


def upsert_ohlcv(
    ticker: str,
    df: pd.DataFrame,
    interval: str = "1d",
) -> int:
    """
    Upsert OHLCV rows from *df* into the database.

    Returns the number of rows inserted/updated.
    """
    session = get_session()
    inserted = 0
    try:
        for ts, row in df.iterrows():
            ts_dt = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
            # Check for existing row
            existing = (
                session.query(OHLCVBar)
                .filter_by(ticker=ticker, timestamp=ts_dt, interval=interval)
                .first()
            )
            if existing:
                existing.open = float(row.get("open", existing.open))
                existing.high = float(row.get("high", existing.high))
                existing.low = float(row.get("low", existing.low))
                existing.close = float(row.get("close", existing.close))
                existing.volume = int(row.get("volume", existing.volume))
                existing.adj_close = float(row.get("adj_close", existing.adj_close or existing.close))
            else:
                bar = OHLCVBar(
                    ticker=ticker,
                    timestamp=ts_dt,
                    interval=interval,
                    open=float(row.get("open", 0)),
                    high=float(row.get("high", 0)),
                    low=float(row.get("low", 0)),
                    close=float(row.get("close", 0)),
                    volume=int(row.get("volume", 0)),
                    adj_close=float(row.get("adj_close", row.get("close", 0))),
                )
                session.add(bar)
                inserted += 1
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    return inserted


def fetch_fundamentals(tickers: list[str]) -> dict[str, dict[str, Any]]:
    """Fetch fundamental data via yfinance Ticker.info."""
    yf = _yf()
    result: dict[str, dict[str, Any]] = {}
    for ticker in tickers:
        try:
            info = yf.Ticker(ticker).info
            result[ticker] = {
                "market_cap": info.get("marketCap"),
                "pe_ratio": info.get("trailingPE"),
                "pb_ratio": info.get("priceToBook"),
                "ev_ebitda": info.get("enterpriseToEbitda"),
                "revenue_growth": info.get("revenueGrowth"),
                "earnings_surprise": info.get("earningsQuarterlyGrowth"),
                "dividend_yield": info.get("dividendYield"),
                "beta": info.get("beta"),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
            }
        except Exception as exc:
            logger.warning("Failed to fetch fundamentals for %s: %s", ticker, exc)
            result[ticker] = {}
    return result


def upsert_fundamentals(ticker: str, data: dict[str, Any]) -> None:
    """Upsert a FundamentalSnapshot row."""
    session = get_session()
    try:
        snap = FundamentalSnapshot(
            ticker=ticker,
            fetched_at=datetime.utcnow(),
            **{k: v for k, v in data.items() if v is not None},
        )
        session.add(snap)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def load_ohlcv(
    ticker: str,
    start: datetime | None = None,
    end: datetime | None = None,
    interval: str = "1d",
) -> pd.DataFrame:
    """Load OHLCV bars from the database into a DataFrame."""
    session = get_session()
    try:
        q = session.query(OHLCVBar).filter_by(ticker=ticker, interval=interval)
        if start:
            q = q.filter(OHLCVBar.timestamp >= start)
        if end:
            q = q.filter(OHLCVBar.timestamp <= end)
        rows = q.order_by(OHLCVBar.timestamp).all()
        if not rows:
            return pd.DataFrame()
        data = [
            {
                "timestamp": r.timestamp,
                "open": r.open,
                "high": r.high,
                "low": r.low,
                "close": r.close,
                "volume": r.volume,
                "adj_close": r.adj_close,
            }
            for r in rows
        ]
        df = pd.DataFrame(data).set_index("timestamp")
        return df
    finally:
        session.close()
