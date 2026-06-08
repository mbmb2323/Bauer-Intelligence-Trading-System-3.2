"""SQLAlchemy ORM models and database initialisation for BITS 3.2."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


class OHLCVBar(Base):
    """One OHLCV bar per ticker per interval."""

    __tablename__ = "ohlcv_bars"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(16), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    interval = Column(String(8), nullable=False, default="1d")
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(BigInteger, nullable=False)
    adj_close = Column(Float)

    __table_args__ = (
        Index("ix_ohlcv_ticker_ts", "ticker", "timestamp", "interval", unique=True),
    )


class FundamentalSnapshot(Base):
    """Latest fundamental data snapshot per ticker."""

    __tablename__ = "fundamental_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(16), nullable=False)
    fetched_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    market_cap = Column(Float)
    pe_ratio = Column(Float)
    pb_ratio = Column(Float)
    ev_ebitda = Column(Float)
    revenue_growth = Column(Float)
    earnings_surprise = Column(Float)
    dividend_yield = Column(Float)
    beta = Column(Float)
    sector = Column(String(64))
    industry = Column(String(128))

    __table_args__ = (Index("ix_fund_ticker", "ticker"),)


class NewsItem(Base):
    """A single news headline with sentiment scores."""

    __tablename__ = "news_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(16), nullable=False)
    published_at = Column(DateTime, nullable=False)
    title = Column(Text, nullable=False)
    source = Column(String(128))
    url = Column(Text)
    vader_compound = Column(Float)
    vader_positive = Column(Float)
    vader_negative = Column(Float)
    vader_neutral = Column(Float)

    __table_args__ = (Index("ix_news_ticker_pub", "ticker", "published_at"),)


class FeatureSnapshot(Base):
    """Versioned feature vector snapshots for model training."""

    __tablename__ = "feature_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(16), nullable=False)
    snapshot_date = Column(DateTime, nullable=False)
    version = Column(String(32), nullable=False)
    features_json = Column(Text, nullable=False)  # JSON-serialised dict

    __table_args__ = (
        Index("ix_feat_ticker_date_ver", "ticker", "snapshot_date", "version"),
    )


_engine = None
_SessionFactory = None


def init_db(database_url: str = "sqlite:///bits.db") -> None:
    """Create tables and initialise the session factory."""
    global _engine, _SessionFactory
    _engine = create_engine(database_url, echo=False, future=True)
    Base.metadata.create_all(_engine)
    _SessionFactory = sessionmaker(bind=_engine, expire_on_commit=False)


def get_session() -> Session:
    """Return a new SQLAlchemy session. Call init_db() first."""
    if _SessionFactory is None:
        raise RuntimeError("Database not initialised. Call init_db() first.")
    return _SessionFactory()


def get_engine() -> "Engine":
    """Return the SQLAlchemy engine."""
    if _engine is None:
        raise RuntimeError("Database not initialised. Call init_db() first.")
    return _engine
