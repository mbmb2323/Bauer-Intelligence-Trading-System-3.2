"""BITS 3.2 CLI entry point."""
from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="bits",
        description="Bauer Intelligence Trading System 3.2",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("screen", help="Run the stock screener")
    subparsers.add_parser("backtest", help="Run the strategy backtester")
    subparsers.add_parser("trade", help="Start live/paper trading")
    subparsers.add_parser("dashboard", help="Launch the analytics dashboard")
    subparsers.add_parser("ingest", help="Run a manual data ingestion pass")
    subparsers.add_parser("train", help="Train / retrain ML models")

    args = parser.parse_args()

    if args.command == "screen":
        from bits.screener.export import cli as screener_cli

        return screener_cli()
    elif args.command == "backtest":
        from bits.strategy.backtester import cli as backtest_cli

        return backtest_cli()
    elif args.command == "trade":
        from bits.execution.portfolio import cli as trade_cli

        return trade_cli()
    elif args.command == "dashboard":
        from bits.analytics.terminal import cli as dashboard_cli

        return dashboard_cli()
    elif args.command == "ingest":
        from bits.data.pipeline import cli as ingest_cli

        return ingest_cli()
    elif args.command == "train":
        from bits.models.registry import cli as train_cli

        return train_cli()
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
