from __future__ import annotations

import numpy as np
import pandas as pd

from bits.features import FEATURE_COLUMNS, build_features



def test_build_features_returns_expected_keys() -> None:
    rng = np.random.default_rng(42)
    periods = 100
    dates = pd.date_range("2024-01-01", periods=periods, freq="D")
    close = pd.Series(100 + rng.normal(0, 1, periods).cumsum(), index=dates)
    df = pd.DataFrame(
        {
            "open": close + rng.normal(0, 0.5, periods),
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": rng.integers(100_000, 500_000, periods),
        },
        index=dates,
    )
    fundamentals = {
        "pe_ratio": 20.0,
        "pb_ratio": 5.0,
        "ev_ebitda": 14.0,
        "revenue_growth": 0.12,
        "earnings_surprise": 0.08,
        "dividend_yield": 0.01,
        "beta": 1.1,
    }
    config = {
        "features": {
            "technical": {"rsi_period": 14, "bb_period": 20, "atr_period": 14, "vwap_enabled": True, "obv_enabled": True},
            "statistical": {"zscore_window": 20, "correlation_window": 60},
        }
    }

    features = build_features("AAPL", df, fundamentals, 0.25, config)

    assert set(FEATURE_COLUMNS).issubset(features)
    for key in FEATURE_COLUMNS:
        assert isinstance(features[key], float)
    for key in ["rsi", "bb_position", "atr", "zscore_close", "momentum_20d", "pe_ratio", "vader_compound_mean"]:
        assert np.isfinite(features[key])
