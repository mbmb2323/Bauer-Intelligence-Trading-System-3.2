from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

from bits.config.settings import load_config
from bits.screener import run_screener

logger = logging.getLogger(__name__)



def export_csv(df: pd.DataFrame, path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)



def export_html(df: pd.DataFrame, path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(df.to_html(index=False, float_format=lambda value: f"{value:.4f}"), encoding="utf-8")



def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the BITS stock screener")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--csv", help="CSV export path")
    parser.add_argument("--html", help="HTML export path")
    args = parser.parse_args(sys.argv[2:] if argv is None else argv)

    config = load_config(args.config)
    result = run_screener(config)
    csv_path = args.csv or config.get("screener", {}).get("export", {}).get("csv_path", "screener_output.csv")
    html_path = args.html or config.get("screener", {}).get("export", {}).get("html_path", "screener_output.html")
    export_csv(result, csv_path)
    export_html(result, html_path)
    print(result.to_string(index=False) if not result.empty else "No screener results available")
    return 0


__all__ = ["cli", "export_csv", "export_html"]
