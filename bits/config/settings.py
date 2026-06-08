"""Configuration loading and validation for BITS 3.2."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

_BOOL_TRUE = {"1", "true", "yes", "on"}


def _env_override(config: dict[str, Any]) -> dict[str, Any]:
    """
    Apply environment variable overrides to the loaded config dict.

    Conventions:
    - DATABASE_URL              → config["data"]["database_url"]
    - ALPACA_API_KEY            → config["execution"]["alpaca"]["api_key"]
    - ALPACA_API_SECRET         → config["execution"]["alpaca"]["api_secret"]
    - MLFLOW_TRACKING_URI       → config["models"]["registry"]["mlflow_tracking_uri"]
    - SLACK_WEBHOOK_URL         → config["analytics"]["alerts"]["slack_webhook_url"]
    - LOG_LEVEL                 → config["logging"]["level"]
    """
    overrides: list[tuple[list[str], str]] = [
        (["data", "database_url"], "DATABASE_URL"),
        (["execution", "alpaca", "api_key"], "ALPACA_API_KEY"),
        (["execution", "alpaca", "api_secret"], "ALPACA_API_SECRET"),
        (["models", "registry", "mlflow_tracking_uri"], "MLFLOW_TRACKING_URI"),
        (["analytics", "alerts", "slack_webhook_url"], "SLACK_WEBHOOK_URL"),
        (["logging", "level"], "LOG_LEVEL"),
    ]
    for keys, env_var in overrides:
        value = os.environ.get(env_var)
        if value is not None:
            node = config
            for key in keys[:-1]:
                node = node.setdefault(key, {})
            node[keys[-1]] = value
    return config


def load_config(path: str | Path = "config.yaml") -> dict[str, Any]:
    """
    Load YAML configuration from *path* and apply .env + env-var overrides.

    Returns the merged config dict.
    """
    import yaml  # noqa: PLC0415

    config_path = Path(path)
    if not config_path.exists():
        # Return a minimal default config if the file isn't present (useful in tests)
        config: dict[str, Any] = {}
    else:
        with config_path.open("r", encoding="utf-8") as fh:
            config = yaml.safe_load(fh) or {}

    # Load .env if it exists (next to config.yaml or in cwd)
    env_path = config_path.parent / ".env"
    if env_path.exists():
        try:
            from dotenv import load_dotenv  # noqa: PLC0415
            load_dotenv(env_path)
        except ImportError:
            pass

    config = _env_override(config)
    return config


def get_tickers(config: dict[str, Any]) -> list[str]:
    """Extract ticker list from config."""
    return config.get("universe", {}).get("tickers", [])


def get_database_url(config: dict[str, Any]) -> str:
    """Extract database URL from config."""
    return config.get("data", {}).get("database_url", "sqlite:///bits.db")


def get_broker(config: dict[str, Any]) -> str:
    """Return the configured broker name."""
    return config.get("execution", {}).get("broker", "paper")


def configure_logging(config: dict[str, Any]) -> None:
    """Configure loguru based on config settings."""
    try:
        from loguru import logger  # noqa: PLC0415
        import sys  # noqa: PLC0415

        log_cfg = config.get("logging", {})
        level = log_cfg.get("level", "INFO")
        log_file = log_cfg.get("log_file", "logs/bits.log")
        rotation = log_cfg.get("rotation", "10 MB")
        retention = log_cfg.get("retention", "1 month")

        # Remove default handler and reconfigure
        logger.remove()
        logger.add(sys.stderr, level=level, colorize=True, backtrace=True, diagnose=True)
        logger.add(
            log_file,
            level=level,
            rotation=rotation,
            retention=retention,
            backtrace=True,
            diagnose=True,
        )
    except ImportError:
        import logging  # noqa: PLC0415
        level_str = config.get("logging", {}).get("level", "INFO")
        logging.basicConfig(level=getattr(logging, level_str, logging.INFO))
