import pandas as pd

from src.data_sources.deriv import DerivProvider
from src.data_sources.market_data import MarketDataError

START = 1_767_225_600  # 1er janvier 2026 00:00 UTC
STEP = 300


def _fake_deriv(total):
    """Imite ticks_history : `count` bougies avant `end` (ou les plus récentes si end='latest')."""
    def send(req):
        assert req["granularity"] == 300 and req["style"] == "candles"
        hi = total if req["end"] == "latest" else int((int(req["end"]) - START) // STEP)
        lo = max(0, hi - req["count"])
        candles = [{"epoch": START + i * STEP, "open": 1.10, "high": 1.11, "low": 1.09, "close": 1.105}
                   for i in range(lo, hi)]
        return {"candles": candles}
    return send


def test_pagination_gives_unique_ordered_bars():
    now = START + 20000 * STEP + 1000  # toutes les bougies sont clôturées
    p = DerivProvider(connector=_fake_deriv(12000), clock=lambda: now)
    df = p.get_m5(10000)
    assert len(df) == 10000
    assert df.index.is_unique and df.index.is_monotonic_increasing
    assert (df.index[1:] - df.index[:-1] == pd.Timedelta("5min")).all()


def test_forming_candle_is_dropped():
    total = 100
    last_epoch = START + (total - 1) * STEP
    now = last_epoch + 60  # la dernière bougie est encore en cours
    p = DerivProvider(connector=_fake_deriv(total), clock=lambda: now)
    df = p.get_m5(50)
    assert df.index[-1] < pd.to_datetime(last_epoch, unit="s", utc=True)


def test_error_message_from_deriv_is_reported():
    p = DerivProvider(connector=lambda req: {"error": {"code": "InvalidSymbol", "message": "symbole inconnu"}})
    try:
        p.get_m5(100)
        assert False, "erreur attendue"
    except MarketDataError as e:
        assert "symbole inconnu" in str(e)


def test_missing_websocket_library_is_explicit():
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "websocket":
            raise ImportError("absent")
        return real_import(name, *args, **kwargs)

    builtins.__import__ = fake_import
    try:
        DerivProvider()._websocket_send({"ping": 1})
        assert False, "erreur attendue"
    except MarketDataError as e:
        assert "websocket-client" in str(e)
    finally:
        builtins.__import__ = real_import


def test_yahoo_normalization_handles_multiindex_and_timezone():
    from tools.download_eurusd import normalize
    idx = pd.date_range("2026-10-05 10:00", periods=3, freq="5min", tz="America/New_York")
    cols = pd.MultiIndex.from_tuples([("Open", "EURUSD=X"), ("High", "EURUSD=X"),
                                      ("Low", "EURUSD=X"), ("Close", "EURUSD=X")])
    raw = pd.DataFrame([[1.1, 1.102, 1.099, 1.101]] * 3, index=idx, columns=cols)
    df = normalize(raw)
    assert list(df.columns) == ["open", "high", "low", "close"]
    assert str(df.index.tz) == "UTC"
    assert df.index[0].hour == 14  # 10:00 New York = 14:00 UTC en octobre
