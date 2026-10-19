import os

import numpy as np
import pandas as pd

from src.data_sources.market_data import MarketDataError, OandaProvider, resample_ohlc

BASE = pd.Timestamp("2026-01-05T00:00:00Z")  # lundi


def _fake_oanda(total, incomplete_last=True):
    """Simule l'API : renvoie `count` bougies strictement avant `to`, en ordre chronologique."""
    def fmt(i):
        return (BASE + pd.Timedelta(minutes=5 * i)).strftime("%Y-%m-%dT%H:%M:%S.000000000Z")

    def request(params):
        hi = total
        if "to" in params:
            hi = int((pd.Timestamp(params["to"]) - BASE) / pd.Timedelta(minutes=5))
        lo = max(0, hi - params["count"])
        candles = []
        for i in range(lo, hi):
            candles.append({
                "time": fmt(i),
                "complete": not (incomplete_last and i == total - 1),
                "mid": {"o": "1.10000", "h": "1.10100", "l": "1.09900", "c": "1.10050"},
            })
        return {"candles": candles}
    return request


def test_oanda_pagination_returns_requested_unique_bars_without_incomplete_candle():
    p = OandaProvider(api_key="test-key")
    p._request = _fake_oanda(total=15000)
    df = p.get_m5(12000)
    assert len(df) == 12000
    assert df.index.is_unique and df.index.is_monotonic_increasing
    assert (df.index[1:] - df.index[:-1] == pd.Timedelta("5min")).all()
    assert df.index[-1] < BASE + pd.Timedelta(minutes=5 * 14999)  # bougie incomplète exclue


def test_oanda_without_key_is_explicit_error():
    saved = os.environ.pop("OANDA_API_KEY", None)
    try:
        OandaProvider()
        assert False, "une erreur était attendue"
    except MarketDataError as e:
        assert "OANDA_API_KEY" in str(e)
    finally:
        if saved is not None:
            os.environ["OANDA_API_KEY"] = saved


def test_resample_drops_incomplete_buckets():
    idx = pd.date_range("2026-01-05T10:00:00Z", periods=11, freq="5min")  # 11 bougies M5
    m5 = pd.DataFrame({"open": 1.1, "high": 1.101, "low": 1.099, "close": 1.1}, index=idx)
    m30 = resample_ohlc(m5, "M30")
    assert len(m30) == 1  # la seconde tranche n'a que 5 bougies sur 6 : supprimée
    assert resample_ohlc(m5, "M5") is m5
