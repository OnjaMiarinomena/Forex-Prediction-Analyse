import numpy as np
import pandas as pd

from src.analysis.indicators import atr, rsi


def test_rsi_rising_series_is_high():
    s = pd.Series(np.arange(1.0, 60.0))
    assert rsi(s).iloc[-1] > 95


def test_atr_constant_range():
    idx = pd.date_range("2026-10-01", periods=30, freq="5min", tz="UTC")
    df = pd.DataFrame({"open": 1.1, "high": 1.101, "low": 1.099, "close": 1.1}, index=idx)
    assert abs(atr(df, 14).iloc[-1] - 0.002) < 1e-9
