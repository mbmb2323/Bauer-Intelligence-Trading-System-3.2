from __future__ import annotations

from bits.strategy import compute_position_sizes



def test_compute_position_sizes_caps_and_filters() -> None:
    config = {
        "strategy": {
            "signal_confidence_threshold": 0.55,
            "risk": {
                "max_position_pct": 0.10,
                "position_sizing": "volatility_target",
                "volatility_target": 0.15,
            },
        }
    }
    scores = {
        "AAA": {"score": 0.90, "volatility": 0.10},
        "BBB": {"score": 0.70, "volatility": 0.20},
        "CCC": {"score": 0.40, "volatility": 0.10},
    }

    positions = compute_position_sizes(scores, config, portfolio_value=100_000)

    assert "CCC" not in positions
    assert positions["AAA"] <= 10_000
    assert positions["BBB"] <= 10_000
