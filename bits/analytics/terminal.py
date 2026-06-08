from __future__ import annotations

import argparse
import logging
import sys
import time
from typing import Any

import pandas as pd

from bits.config.settings import load_config
from bits.screener import run_screener

logger = logging.getLogger(__name__)



def render_screener_table(df: pd.DataFrame, config: dict[str, Any]) -> None:
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        print(df.to_string(index=False) if not df.empty else "No screener results available")
        return

    console = Console()
    table = Table(title="BITS Screener")
    for column in df.columns:
        table.add_column(str(column))
    max_rows = int(config.get("analytics", {}).get("terminal", {}).get("max_rows", len(df) or 20))
    display_df = df.head(max_rows)
    for _, row in display_df.iterrows():
        table.add_row(*[f"{value:.4f}" if isinstance(value, float) else str(value) for value in row.tolist()])
    console.print(table)



def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render the BITS screener dashboard")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--refresh", type=int, help="Refresh interval in seconds")
    args = parser.parse_args(sys.argv[2:] if argv is None else argv)

    config = load_config(args.config)
    refresh = args.refresh
    if refresh is None:
        refresh = int(config.get("analytics", {}).get("terminal", {}).get("refresh_seconds", 5))

    while True:
        render_screener_table(run_screener(config), config)
        if refresh <= 0:
            break
        time.sleep(refresh)
    return 0


__all__ = ["cli", "render_screener_table"]
