"""Scheduled data ingestion pipeline for BITS 3.2."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def run_ingestion(config: dict[str, Any]) -> dict[str, int]:
    """
    Run a full ingestion pass:
    1. Fetch OHLCV bars for all tickers in the universe.
    2. Fetch fundamentals.
    3. Fetch news and score sentiment.

    Returns a summary dict with row counts.
    """
    from bits.data.ingestion import (  # noqa: PLC0415
        fetch_fundamentals,
        fetch_ohlcv,
        upsert_fundamentals,
        upsert_ohlcv,
    )
    from bits.data.news import fetch_news, score_sentiment, upsert_news  # noqa: PLC0415
    from bits.data.storage import init_db  # noqa: PLC0415

    db_url = config.get("data", {}).get("database_url", "sqlite:///bits.db")
    init_db(db_url)

    tickers: list[str] = config.get("universe", {}).get("tickers", [])
    lookback: int = config.get("data", {}).get("lookback_days", 365)
    interval: str = config.get("data", {}).get("bar_size", "1d")
    news_hours: int = config.get("data", {}).get("news_max_age_hours", 24)

    total_bars = 0
    total_news = 0

    logger.info("Starting ingestion for %d tickers", len(tickers))

    # ── OHLCV ────────────────────────────────────────────────────────────────
    ohlcv_data = fetch_ohlcv(tickers, lookback_days=lookback, interval=interval)
    for ticker, df in ohlcv_data.items():
        if df.empty:
            logger.warning("No OHLCV data returned for %s", ticker)
            continue
        n = upsert_ohlcv(ticker, df, interval=interval)
        total_bars += n
        logger.debug("Upserted %d OHLCV bars for %s", n, ticker)

    # ── Fundamentals ─────────────────────────────────────────────────────────
    fundamentals = fetch_fundamentals(tickers)
    for ticker, data in fundamentals.items():
        if data:
            upsert_fundamentals(ticker, data)

    # ── News & sentiment ─────────────────────────────────────────────────────
    for ticker in tickers:
        items = fetch_news(ticker)
        items = score_sentiment(items)
        n = upsert_news(items)
        total_news += n

    summary = {
        "tickers": len(tickers),
        "ohlcv_rows": total_bars,
        "news_rows": total_news,
    }
    logger.info("Ingestion complete: %s", summary)
    return summary


def start_scheduler(config: dict[str, Any]) -> None:
    """Start APScheduler to run ingestion on a cron schedule."""
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler  # noqa: PLC0415
        from apscheduler.triggers.cron import CronTrigger  # noqa: PLC0415
    except ImportError:
        logger.error("APScheduler not installed. Run: pip install apscheduler")
        return

    cron_expr = config.get("data", {}).get("schedule_cron", "0 7 * * 1-5")
    parts = cron_expr.split()

    scheduler = BlockingScheduler(timezone="America/New_York")
    scheduler.add_job(
        run_ingestion,
        CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
        ),
        args=[config],
        id="data_ingestion",
        replace_existing=True,
    )
    logger.info("Scheduler started with cron: %s", cron_expr)
    scheduler.start()


def cli() -> int:
    """CLI entry point for manual ingestion."""
    import argparse  # noqa: PLC0415
    import sys  # noqa: PLC0415

    from bits.config.settings import load_config  # noqa: PLC0415

    parser = argparse.ArgumentParser(description="Run BITS data ingestion")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--schedule", action="store_true", help="Start scheduled ingestion")
    args = parser.parse_args()

    cfg = load_config(args.config)

    if args.schedule:
        start_scheduler(cfg)
    else:
        summary = run_ingestion(cfg)
        print(f"Ingestion complete: {summary}")
    return 0
