from __future__ import annotations

import numpy as np
import pandas as pd

from bits.models import load_model, predict_screener, save_model, train_screener



def test_train_save_load_predict_roundtrip(tmp_path) -> None:
    rng = np.random.default_rng(7)
    feature_df = pd.DataFrame(
        {
            "feature_a": rng.normal(size=120),
            "feature_b": rng.normal(size=120),
            "feature_c": rng.normal(size=120),
        }
    )
    feature_df["label"] = 0.4 * feature_df["feature_a"] + 0.2 * feature_df["feature_b"] + rng.normal(scale=0.1, size=120)
    config = {"models": {"registry": {"path": str(tmp_path)}}}

    model = train_screener(feature_df, "label", config)
    path = save_model(model, "screener", config)
    loaded_model = load_model("screener", config)
    predictions = predict_screener(loaded_model, feature_df.drop(columns=["label"]))

    assert path.exists()
    assert len(predictions) == len(feature_df)
    assert predictions.dtype.kind == "f"
