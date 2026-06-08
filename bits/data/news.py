"""News ingestion and VADER sentiment scoring."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

from bits.data.storage import NewsItem, get_session

logger = logging.getLogger(__name__)

# RSS feed templates – add more as desired
_YAHOO_RSS = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
_SEEKING_ALPHA_RSS = "https://seekingalpha.com/api/sa/combined/{ticker}.xml"


def _import_feedparser():
    import feedparser  # noqa: PLC0415
    return feedparser


def _import_vader():
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer  # noqa: PLC0415
    return SentimentIntensityAnalyzer()


def _parse_published(entry: Any) -> datetime:
    """Parse an RSS entry's published date into a UTC datetime."""
    if hasattr(entry, "published"):
        try:
            return parsedate_to_datetime(entry.published).astimezone(timezone.utc).replace(tzinfo=None)
        except Exception:
            pass
    return datetime.utcnow()


def fetch_news(ticker: str, max_items: int = 50) -> list[dict[str, Any]]:
    """Fetch news headlines for *ticker* from Yahoo Finance RSS."""
    feedparser = _import_feedparser()
    url = _YAHOO_RSS.format(ticker=ticker)
    feed = feedparser.parse(url)
    items: list[dict[str, Any]] = []
    for entry in feed.entries[:max_items]:
        items.append(
            {
                "ticker": ticker,
                "published_at": _parse_published(entry),
                "title": getattr(entry, "title", ""),
                "source": getattr(entry, "source", {}).get("title", "Yahoo Finance") if hasattr(entry, "source") else "Yahoo Finance",
                "url": getattr(entry, "link", ""),
            }
        )
    logger.info("Fetched %d news items for %s", len(items), ticker)
    return items


def score_sentiment(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach VADER sentiment scores to each news item dict (in-place)."""
    analyzer = _import_vader()
    for item in items:
        scores = analyzer.polarity_scores(item.get("title", ""))
        item["vader_compound"] = scores["compound"]
        item["vader_positive"] = scores["pos"]
        item["vader_negative"] = scores["neg"]
        item["vader_neutral"] = scores["neu"]
    return items


def upsert_news(items: list[dict[str, Any]]) -> int:
    """Persist news items to the database. Returns count inserted."""
    session = get_session()
    inserted = 0
    try:
        for item in items:
            existing = (
                session.query(NewsItem)
                .filter_by(ticker=item["ticker"], published_at=item["published_at"], title=item["title"])
                .first()
            )
            if existing:
                continue
            news = NewsItem(
                ticker=item["ticker"],
                published_at=item["published_at"],
                title=item["title"],
                source=item.get("source"),
                url=item.get("url"),
                vader_compound=item.get("vader_compound"),
                vader_positive=item.get("vader_positive"),
                vader_negative=item.get("vader_negative"),
                vader_neutral=item.get("vader_neutral"),
            )
            session.add(news)
            inserted += 1
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    return inserted


def load_recent_sentiment(ticker: str, hours: int = 24) -> float:
    """Return mean VADER compound score for *ticker* over last *hours* hours."""
    from datetime import timedelta  # noqa: PLC0415

    session = get_session()
    try:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        rows = (
            session.query(NewsItem.vader_compound)
            .filter(
                NewsItem.ticker == ticker,
                NewsItem.published_at >= cutoff,
                NewsItem.vader_compound.isnot(None),
            )
            .all()
        )
        if not rows:
            return 0.0
        return sum(r[0] for r in rows) / len(rows)
    finally:
        session.close()
