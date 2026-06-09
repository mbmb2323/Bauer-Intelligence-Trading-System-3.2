from __future__ import annotations

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)



def send_slack_alert(message: str, config: dict[str, Any]) -> bool:
    webhook_url = config.get("analytics", {}).get("alerts", {}).get("slack_webhook_url")
    if not webhook_url:
        return False
    try:
        import requests

        response = requests.post(webhook_url, json={"text": message}, timeout=10)
        return response.ok
    except Exception as exc:
        logger.warning("Slack alert failed: %s", exc)
        return False



def send_screener_alert(df: pd.DataFrame, config: dict[str, Any]) -> bool:
    if df.empty:
        return False
    top_rows = df.head(int(config.get("analytics", {}).get("terminal", {}).get("max_rows", 5)))
    message = "BITS top picks:\n" + "\n".join(
        f"{row.ticker}: score={row.composite_score:.3f}, ml={row.ml_alpha:.3f}"
        for row in top_rows.itertuples(index=False)
    )
    return send_slack_alert(message, config)


__all__ = ["send_screener_alert", "send_slack_alert"]
