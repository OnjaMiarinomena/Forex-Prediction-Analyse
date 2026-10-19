import io
import os

import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from src.analysis.event_glossary import describe
from src.analysis.event_impact import reaction_pips
from src.analysis.key_levels import Zone
from src.data_sources.market_data import resample_ohlc
from src.gui.plots import draw_price_chart


def _frame(n=300, volume=True, seed=4):
    rng = np.random.default_rng(seed)
    c = 1.12 + np.cumsum(rng.normal(0, 0.0004, n))
    o = np.r_[c[0], c[:-1]]
    idx = pd.date_range("2026-10-12", periods=n, freq="5min", tz="UTC")
    df = pd.DataFrame({"open": o, "high": np.maximum(o, c) + 0.0002, "low": np.minimum(o, c) - 0.0002,
                       "close": c}, index=idx)
    if volume:
        df["volume"] = rng.integers(10, 100, n)
    return df


def test_reaction_measured_on_past_event_only():
    df = _frame()
    past = df.index[50]
    assert reaction_pips(df, past, 60, 0.0001) is not None
    assert reaction_pips(df, df.index[-1], 60, 0.0001) is None


def test_glossary_describes_common_releases():
    assert describe("Non-Farm Employment Change")[0].startswith("Emploi")
    assert "taux" in describe("ECB Interest Rate Decision")[0].lower()
    assert describe("Unknown thing")[0] == "Publication économique"


def test_chart_renders_with_events_volume_and_rsi():
    df = _frame()
    ev = [{"title": "NFP", "currency": "USD", "stars": 3, "when": df.index[80]},
          {"title": "CPI", "currency": "USD", "stars": 3, "when": df.index[-1] + pd.Timedelta(hours=2)}]
    z = Zone("OB haussier M30 (actif)", float(df.close.iloc[-1]) - 0.0005,
             float(df.close.iloc[-1]) - 0.0002, "zone", "BUY", "actif")
    fig = Figure(figsize=(9, 6))
    draw_price_chart(fig, df, [z], [z], float(df.close.iloc[-1]), title="test", n_bars=120, events=ev)
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    assert buf.getbuffer().nbytes > 1000


def test_chart_without_volume_still_renders():
    df = _frame(volume=False)
    fig = Figure(figsize=(9, 6))
    draw_price_chart(fig, df, [], [], float(df.close.iloc[-1]), title="sans volume", n_bars=120)
    assert len(fig.axes) == 3


def test_resample_keeps_volume_sum():
    df = _frame(n=12)
    m30 = resample_ohlc(df, "M30")
    assert "volume" in m30.columns
    assert m30["volume"].iloc[0] == df["volume"].iloc[:6].sum()
