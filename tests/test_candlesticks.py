import pandas as pd

from src.analysis.candlesticks import pattern_at


def _df(rows):
    idx = pd.date_range("2026-10-01", periods=len(rows), freq="5min", tz="UTC")
    return pd.DataFrame(rows, index=idx, columns=["open", "high", "low", "close"])


def test_bullish_engulfing():
    df = _df([[1.1000, 1.1002, 1.0988, 1.0990], [1.0988, 1.1025, 1.0985, 1.1020]])
    atr = pd.Series(0.001, index=df.index)
    assert pattern_at(df, atr, 1) == ("engulfing haussier", "BUY")


def test_bullish_pin_bar():
    df = _df([[1.0990, 1.1010, 1.0985, 1.1005], [1.1000, 1.1003, 1.0970, 1.1002]])
    atr = pd.Series(0.001, index=df.index)
    assert pattern_at(df, atr, 1) == ("pin bar haussier", "BUY")


def test_no_pattern_on_small_candle():
    df = _df([[1.1000, 1.1001, 1.0999, 1.1000], [1.1000, 1.1001, 1.0999, 1.1000]])
    atr = pd.Series(0.001, index=df.index)
    assert pattern_at(df, atr, 1) is None
