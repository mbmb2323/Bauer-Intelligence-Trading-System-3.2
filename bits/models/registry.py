from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)



def _models_dir(config: dict[str, Any]) -> Path:
    return Path(config.get("models", {}).get("registry", {}).get("path", "models"))



def _feature_frame(feature_df: pd.DataFrame, label_col: str | None = None) -> pd.DataFrame:
    frame = feature_df.copy()
    if label_col and label_col in frame.columns:
        frame = frame.drop(columns=[label_col])
    return frame.select_dtypes(include=[np.number]).fillna(0.0)



def _target_series(feature_df: pd.DataFrame, label_col: str) -> pd.Series:
    if label_col not in feature_df.columns:
        raise ValueError(f"Missing label column: {label_col}")
    return pd.Series(feature_df[label_col]).fillna(0.0)



def train_screener(feature_df: pd.DataFrame, label_col: str, config: dict[str, Any]) -> Any:
    X = _feature_frame(feature_df, label_col)
    y = _target_series(feature_df, label_col)
    screener_cfg = config.get("models", {}).get("screener", {})
    try:
        from lightgbm import LGBMRegressor

        model = LGBMRegressor(
            n_estimators=int(screener_cfg.get("n_estimators", 200)),
            learning_rate=float(screener_cfg.get("learning_rate", 0.05)),
            num_leaves=int(screener_cfg.get("num_leaves", 63)),
            subsample=float(screener_cfg.get("subsample", 0.8)),
            colsample_bytree=float(screener_cfg.get("colsample_bytree", 0.8)),
            random_state=int(screener_cfg.get("random_state", 42)),
        )
    except ImportError:
        from sklearn.ensemble import RandomForestRegressor

        model = RandomForestRegressor(
            n_estimators=max(50, int(screener_cfg.get("n_estimators", 100) / 2)),
            random_state=int(screener_cfg.get("random_state", 42)),
        )
    model.fit(X, y)
    return model



def _regime_features(ohlcv_df: pd.DataFrame) -> pd.DataFrame:
    if ohlcv_df.empty or "close" not in ohlcv_df.columns:
        return pd.DataFrame(columns=["return", "volatility", "range"])
    frame = ohlcv_df.copy().sort_index()
    close = frame["close"].astype(float)
    returns = close.pct_change().fillna(0.0)
    volatility = returns.rolling(10).std(ddof=0).fillna(0.0)
    intraday_range = ((frame.get("high", close) - frame.get("low", close)) / close.replace(0, np.nan)).replace([np.inf, -np.inf], 0.0).fillna(0.0)
    return pd.DataFrame({"return": returns, "volatility": volatility, "range": intraday_range}).dropna()



def train_regime(ohlcv_df: pd.DataFrame, config: dict[str, Any]) -> Any:
    features = _regime_features(ohlcv_df)
    if features.empty:
        raise ValueError("Not enough OHLCV data to train regime model")
    from sklearn.cluster import KMeans

    regime_cfg = config.get("models", {}).get("regime", {})
    model = KMeans(
        n_clusters=int(regime_cfg.get("n_regimes", 4)),
        random_state=int(regime_cfg.get("random_state", 42)),
        n_init=10,
    )
    model.fit(features)
    return model



def save_model(model: Any, name: str, config: dict[str, Any]) -> Path:
    model_dir = _models_dir(config)
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / f"{name}.joblib"
    joblib.dump(model, model_path)

    registry_cfg = config.get("models", {}).get("registry", {})
    tracking_uri = registry_cfg.get("mlflow_tracking_uri")
    if tracking_uri:
        try:
            import mlflow

            mlflow.set_tracking_uri(tracking_uri)
            mlflow.set_experiment(registry_cfg.get("experiment_name", "BITS-3.2"))
            with mlflow.start_run(run_name=name):
                mlflow.log_artifact(str(model_path))
        except Exception as exc:
            logger.warning("MLflow logging failed for %s: %s", name, exc)
    return model_path



def load_model(name: str, config: dict[str, Any]) -> Any:
    model_path = _models_dir(config) / f"{name}.joblib"
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")
    return joblib.load(model_path)



def predict_screener(model: Any, feature_df: pd.DataFrame) -> pd.Series:
    X = _feature_frame(feature_df)
    predictions = np.asarray(model.predict(X), dtype=float)
    return pd.Series(predictions, index=feature_df.index, name="ml_alpha")



def predict_regime(model: Any, ohlcv_df: pd.DataFrame) -> int:
    features = _regime_features(ohlcv_df)
    if features.empty:
        return 0
    prediction = model.predict(features.tail(1))[0]
    return int(prediction)



def cli(argv: list[str] | None = None) -> int:
    from bits.config.settings import load_config
    from bits.data.ingestion import load_ohlcv

    parser = argparse.ArgumentParser(description="Train BITS models")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--model", choices=["screener", "regime"], default="screener")
    parser.add_argument("--label-col", default="label")
    parser.add_argument("--ticker", default="SPY")
    parser.add_argument("--input", help="CSV path for screener training data")
    args = parser.parse_args(sys.argv[2:] if argv is None else argv)

    config = load_config(args.config)
    if args.model == "screener":
        if not args.input:
            logger.error("--input is required for screener training")
            return 1
        feature_df = pd.read_csv(args.input)
        model = train_screener(feature_df, args.label_col, config)
        save_model(model, "screener", config)
        return 0

    ohlcv_df = load_ohlcv(args.ticker)
    if ohlcv_df.empty:
        logger.error("No OHLCV data available for regime training")
        return 1
    model = train_regime(ohlcv_df, config)
    save_model(model, "regime", config)
    return 0


__all__ = [
    "cli",
    "load_model",
    "predict_regime",
    "predict_screener",
    "save_model",
    "train_regime",
    "train_screener",
]
