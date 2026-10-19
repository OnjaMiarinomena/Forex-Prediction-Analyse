import numpy as np
import pandas as pd

from src.strategy.decision_engine import NO_TRADE, analyse

CFG = {
    "analysis": {"atr_period": 14, "swing_k": 2, "ob_lookback": 10, "impulse_atr": 1.0},
    "data": {"max_data_age_minutes": 30},
    "risk": {
        "equity": 1000.0, "risk_pct": 1.0, "pip_size": 0.0001, "pip_value_usd_per_lot": 10.0,
        "target_rr": 2.0, "min_rr": 1.5, "max_sl_pips": 30.0, "max_spread_pips": 1.5,
        "sl_buffer_atr": 0.5,
    },
}


def _walk(n, freq, seed=0):
    """Données synthétiques de test uniquement, jamais utilisées en production."""
    rng = np.random.default_rng(seed)
    closes = 1.1 + np.cumsum(rng.normal(0, 0.0004, n))
    opens = np.r_[closes[0], closes[:-1]]
    noise = np.abs(rng.normal(0, 0.0003, n))
    idx = pd.date_range("2026-10-01", periods=n, freq=freq, tz="UTC")
    return pd.DataFrame(
        {
            "open": opens,
            "high": np.maximum(opens, closes) + noise,
            "low": np.minimum(opens, closes) - noise,
            "close": closes,
        },
        index=idx,
    )


def test_invalid_data_gives_no_trade():
    m30, m5 = _walk(200, "30min"), _walk(200, "5min")
    m5.iloc[-1, m5.columns.get_loc("high")] = m5.iloc[-1]["close"] - 0.001
    d = analyse(m30, m5, CFG, replay=True)
    assert d.action == NO_TRADE
    assert any("invalides" in r for r in d.reasons)


def test_stale_data_gives_no_trade():
    m30, m5 = _walk(200, "30min"), _walk(200, "5min")
    later = m5.index[-1] + pd.Timedelta(hours=3)
    d = analyse(m30, m5, CFG, now=later, replay=False)
    assert d.action == NO_TRADE
    assert any("périmées" in r for r in d.reasons)


def test_signal_only_with_full_conditions():
    m30, m5 = _walk(300, "30min", seed=1), _walk(300, "5min", seed=2)
    d = analyse(m30, m5, CFG, replay=True)
    assert d.action in {"BUY", "SELL", NO_TRADE}
    if d.action != NO_TRADE:
        assert d.plan is not None and d.ob is not None and d.pattern is not None
        assert d.plan["rr_net"] >= CFG["risk"]["min_rr"]
