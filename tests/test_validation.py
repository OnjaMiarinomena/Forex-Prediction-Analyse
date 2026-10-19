import pandas as pd

from src.utils.validation import check_freshness, validate_ohlc


def _df(rows, start="2026-10-01 00:00"):
    idx = pd.date_range(start, periods=len(rows), freq="5min", tz="UTC")
    return pd.DataFrame(rows, index=idx, columns=["open", "high", "low", "close"])


def test_valid_candles():
    assert validate_ohlc(_df([[1.1, 1.102, 1.099, 1.101]])) == []


def test_high_below_close_is_detected():
    errors = validate_ohlc(_df([[1.1, 1.1005, 1.099, 1.101]]))
    assert any("high" in e for e in errors)


def test_naive_index_is_rejected():
    idx = pd.date_range("2026-10-01", periods=1, freq="5min")
    df = pd.DataFrame([[1.1, 1.102, 1.099, 1.101]], index=idx, columns=["open", "high", "low", "close"])
    assert any("UTC" in e for e in validate_ohlc(df))


def test_stale_data_detected():
    last = pd.Timestamp("2026-10-01 10:00", tz="UTC")
    now = pd.Timestamp("2026-10-01 12:00", tz="UTC")
    assert check_freshness(last, now, 30) is not None
    assert check_freshness(last, last + pd.Timedelta("5min"), 30) is None
