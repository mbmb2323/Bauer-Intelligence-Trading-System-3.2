from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from bits.data.storage import FundamentalSnapshot, NewsItem, OHLCVBar, init_db, get_session
from bits.screener import run_screener



def test_run_screener_returns_ranked_results(tmp_path) -> None:
    db_path = tmp_path / "bits.db"
    init_db(f"sqlite:///{db_path}")
    session = get_session()
    now = datetime.utcnow()
    tickers = ["AAA", "BBB", "CCC"]
    try:
        for idx, ticker in enumerate(tickers):
            for day in range(120):
                price = 100 + idx * 5 + day * (idx + 1) * 0.2
                timestamp = now - timedelta(days=120 - day)
                session.add(
                    OHLCVBar(
                        ticker=ticker,
                        timestamp=timestamp,
                        interval="1d",
                        open=price - 0.5,
                        high=price + 1.0,
                        low=price - 1.0,
                        close=price,
                        volume=100_000 + idx * 10_000,
                        adj_close=price,
                    )
                )
            session.add(
                FundamentalSnapshot(
                    ticker=ticker,
                    fetched_at=now,
                    pe_ratio=25 - idx * 5,
                    pb_ratio=6 - idx,
                    ev_ebitda=12 + idx,
                    revenue_growth=0.05 + idx * 0.03,
                    earnings_surprise=0.01 + idx * 0.02,
                    dividend_yield=0.01 * idx,
                    beta=1.0 + idx * 0.1,
                )
            )
            session.add(
                NewsItem(
                    ticker=ticker,
                    published_at=now,
                    title=f"News for {ticker}",
                    source="Test",
                    url="https://example.com",
                    vader_compound=0.1 * idx,
                    vader_positive=0.2,
                    vader_negative=0.1,
                    vader_neutral=0.7,
                )
            )
        session.commit()
    finally:
        session.close()

    config = {
        "data": {"database_url": f"sqlite:///{db_path}", "news_max_age_hours": 48},
        "universe": {"tickers": tickers},
        "screener": {"top_n": 2, "weights": {"momentum": 0.3, "quality": 0.2, "value": 0.2, "ml_alpha": 0.3}},
        "features": {"technical": {"bb_period": 20, "atr_period": 14}, "statistical": {"zscore_window": 20}},
    }

    result = run_screener(config)

    assert list(result.columns) == ["ticker", "composite_score", "momentum_score", "quality_score", "value_score", "ml_alpha", "rank"]
    assert len(result) == 2
    assert result["composite_score"].between(0, 1).all()
    assert result["rank"].tolist() == [1, 2]
