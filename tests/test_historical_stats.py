import numpy as np
import pandas as pd

from src.analysis.historical_stats import (
    class_stats, current_probabilities, forward_labels, hour_weekday_heatmap,
)


def _rising(n, step=0.0005, freq="5min"):
    close = 1.1 + step * np.arange(n)
    idx = pd.date_range("2026-10-05", periods=n, freq=freq, tz="UTC")  # lundi
    return pd.DataFrame({"open": close, "high": close + 0.0002, "low": close - 0.0002, "close": close}, index=idx)


def test_forward_labels_rising_market():
    m5 = _rising(20)  # +5 pips par bougie
    _, labels = forward_labels(m5, horizon=1, pip_size=0.0001, threshold_pips=3)
    assert labels.iloc[0] == "HAUSSIER"
    assert pd.isna(labels.iloc[-1])  # pas de bougie future


def test_class_probabilities_sum_to_one():
    labels = pd.Series(["HAUSSIER", "BAISSIER", "NEUTRE", "HAUSSIER"], dtype=object)
    s = class_stats(labels)
    assert s["n"] == 4
    assert abs(sum(s["probs"].values()) - 1.0) < 1e-12
    assert s["probs"]["HAUSSIER"] == 0.5


def test_empty_stats_return_none_probs():
    s = class_stats(pd.Series([None, None], dtype=object))
    assert s == {"n": 0, "probs": None}


def test_heatmap_shape_and_sample_masking():
    m5 = _rising(400)
    mean, count = hour_weekday_heatmap(m5, horizon=12, pip_size=0.0001, min_samples=30)
    assert mean.shape == (24, 5) and count.shape == (24, 5)
    # Très peu de données : toutes les cellules doivent être masquées
    assert mean.isna().all().all()


def test_current_probabilities_structure():
    rng = np.random.default_rng(3)
    close = 1.1 + np.cumsum(rng.normal(0, 0.0004, 600))
    idx = pd.date_range("2026-10-05", periods=600, freq="5min", tz="UTC")
    m5 = pd.DataFrame({"open": np.r_[close[0], close[:-1]], "high": close + 0.0003,
                       "low": close - 0.0003, "close": close}, index=idx)
    pcfg = {"horizon_bars": 12, "threshold_pips": 3.0, "min_samples": 30}
    res = current_probabilities(m5, pcfg, 0.0001)
    assert res["base"]["n"] > 0
    assert res["pattern"] in (None, "BUY", "SELL")
    assert isinstance(res["low_sample"], bool)
