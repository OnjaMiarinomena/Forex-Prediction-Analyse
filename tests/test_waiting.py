import os
import tempfile

import numpy as np
import pandas as pd
import yaml
from matplotlib.figure import Figure

from src.analysis.key_levels import Zone, key_zones, waiting_state
from src.app_service import run_analysis
from src.data_sources.economic_events import event_block
from src.data_sources.market_data import CsvProvider, resample_ohlc
from src.gui.plots import draw_price_chart

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _cfg():
    with open(os.path.join(ROOT, "config", "settings.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_previous_day_levels_are_real_values():
    day1 = pd.date_range("2026-10-05 00:00", periods=288, freq="5min", tz="UTC")
    day2 = pd.date_range("2026-10-06 00:00", periods=12, freq="5min", tz="UTC")
    idx = day1.append(day2)
    m5 = pd.DataFrame({"open": 1.115, "high": 1.120, "low": 1.110, "close": 1.115}, index=idx)
    m5.loc[day2, ["open", "high", "low", "close"]] = [1.115, 1.116, 1.114, 1.115]
    zones = key_zones(resample_ohlc(m5, "M30"), m5, _cfg())
    labels = {z.label: z for z in zones}
    assert labels["plus haut de la veille"].low == 1.120
    assert labels["plus bas de la veille"].low == 1.110


def test_waiting_state_variants():
    ob = Zone("OB haussier M30 (actif)", 1.0990, 1.1010, "zone", "BUY", "actif")
    s, t, f = waiting_state([ob], 1.1100, None)
    assert s == "zone clé" and ob in f
    s, t, f = waiting_state([ob], 1.1000, None)
    assert s == "confirmation M5"
    s, t, f = waiting_state([ob], 1.1100, "annonce « NFP »")
    assert s == "événement économique"
    s, t, f = waiting_state([], 1.1100, None)
    assert s == "aucune zone"


def test_event_block_window():
    events = pd.DataFrame({"time_utc": [pd.Timestamp("2026-10-16 12:30", tz="UTC")],
                           "title": ["NFP"], "impact": ["high"]})
    now_close = pd.Timestamp("2026-10-16 12:10", tz="UTC")
    now_far = pd.Timestamp("2026-10-16 08:00", tz="UTC")
    block, _ = event_block(events, now_close, 30, 30)
    assert block is not None and "NFP" in block
    block, info = event_block(events, now_far, 30, 30)
    assert block is None and "aucune annonce" in info


def test_event_block_without_file_is_honest():
    block, info = event_block(None, pd.Timestamp.now(tz="UTC"), 30, 30)
    assert block is None and "non saisies" in info


def test_run_analysis_blocks_signal_during_event():
    cfg = _cfg()
    rng = np.random.default_rng(4)
    n = 3000
    c = 1.1 + np.cumsum(rng.normal(0, 0.0004, n))
    o = np.r_[c[0], c[:-1]]
    idx = pd.date_range("2026-10-05", periods=n, freq="5min", tz="UTC")
    with tempfile.TemporaryDirectory() as tmp:
        csv = os.path.join(tmp, "M5.csv")
        pd.DataFrame({"time": idx, "open": o, "high": np.maximum(o, c) + 0.0002,
                      "low": np.minimum(o, c) - 0.0002, "close": c}).to_csv(csv, index=False)
        ev = os.path.join(tmp, "events.csv")
        event_time = idx[-1] + pd.Timedelta(minutes=10)
        pd.DataFrame({"time_utc": [event_time.strftime("%Y-%m-%d %H:%M:%S")], "title": ["NFP"],
                      "impact": ["high"]}).to_csv(ev, index=False)
        res = run_analysis(cfg, CsvProvider(csv), "M30", replay=True, events_path=ev)
        assert res.decision.action == "NO TRADE"
        assert any("NFP" in w for w in res.decision.waiting_for)
        assert res.wait_state == "événement économique"


def test_price_chart_renders_with_waiting_zone():
    rng = np.random.default_rng(5)
    c = 1.1 + np.cumsum(rng.normal(0, 0.0004, 200))
    idx = pd.date_range("2026-10-05", periods=200, freq="30min", tz="UTC")
    df = pd.DataFrame({"open": np.r_[c[0], c[:-1]], "high": c + 0.0003, "low": c - 0.0003, "close": c}, index=idx)
    zone = Zone("OB haussier M30 (actif)", float(c[-1]) - 0.0005, float(c[-1]) + 0.0005, "zone", "BUY", "actif")
    fig = Figure(figsize=(6, 4))
    draw_price_chart(fig, df, [zone], [zone], float(c[-1]), title="test", n_bars=120)
    import io
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    assert buf.getbuffer().nbytes > 1000


def test_market_hours_weekend_and_sessions():
    from src.utils.market_hours import is_market_open
    assert not is_market_open(pd.Timestamp("2026-10-17 12:00", tz="UTC"))  # samedi
    assert is_market_open(pd.Timestamp("2026-10-16 20:00", tz="UTC"))      # vendredi avant 21h
    assert not is_market_open(pd.Timestamp("2026-10-16 22:00", tz="UTC"))  # vendredi soir
    assert not is_market_open(pd.Timestamp("2026-10-18 20:00", tz="UTC"))  # dimanche avant 21h
    assert is_market_open(pd.Timestamp("2026-10-18 22:00", tz="UTC"))      # dimanche soir
    assert is_market_open(pd.Timestamp("2026-10-14 10:00", tz="UTC"))      # mercredi


def test_weekend_gives_no_trade_message_not_stale_error():
    import numpy as np
    from src.strategy.decision_engine import analyse
    cfg = {"analysis": {"atr_period": 14, "swing_k": 2, "ob_lookback": 10, "impulse_atr": 1.0},
           "data": {"max_data_age_minutes": 30},
           "risk": {"equity": 1000.0, "risk_pct": 1.0, "pip_size": 0.0001, "pip_value_usd_per_lot": 10.0,
                    "target_rr": 2.0, "min_rr": 1.5, "max_sl_pips": 30.0, "max_spread_pips": 1.5,
                    "sl_buffer_atr": 0.5}}
    rng = np.random.default_rng(8)
    c = 1.1 + np.cumsum(rng.normal(0, 0.0004, 300))
    o = np.r_[c[0], c[:-1]]
    idx = pd.date_range("2026-10-16 10:00", periods=300, freq="5min", tz="UTC")
    m5 = pd.DataFrame({"open": o, "high": np.maximum(o, c) + 0.0002, "low": np.minimum(o, c) - 0.0002,
                       "close": c}, index=idx)
    m30 = m5.resample("30min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    saturday = pd.Timestamp("2026-10-17 12:00", tz="UTC")
    d = analyse(m30, m5, cfg, now=saturday, replay=False)
    assert d.action == "NO TRADE"
    assert any("week-end" in r for r in d.reasons)
