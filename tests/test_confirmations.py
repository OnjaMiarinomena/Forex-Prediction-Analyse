import numpy as np
import pandas as pd

from src.analysis.confirmations import evaluate, h1_trend
from src.strategy.decision_engine import NO_TRADE, Decision
from src.strategy.final_decision import combine

CCFG = {"h1_trend": True, "rsi": True, "volatility": True, "rsi_period": 14, "rsi_overbought": 70,
        "rsi_oversold": 30, "vol_lookback": 100, "vol_min_ratio": 0.6, "vol_max_ratio": 2.0}


def _frame(close, freq="5min"):
    close = np.asarray(close, dtype=float)
    idx = pd.date_range("2026-10-05", periods=len(close), freq=freq, tz="UTC")
    return pd.DataFrame({"open": np.r_[close[0], close[:-1]], "high": close + 0.0002,
                         "low": close - 0.0002, "close": close}, index=idx)


def _by_label(checks):
    return {c["label"]: c for c in checks}


def test_rising_market_is_overbought_so_buy_fails_rsi_but_sell_passes():
    m5 = _frame(1.10 + 0.0002 * np.arange(300))
    h1 = _frame(1.10 + 0.0010 * np.arange(300), freq="1h")
    buy = _by_label(evaluate("BUY", h1, m5, CCFG))
    sell = _by_label(evaluate("SELL", h1, m5, CCFG))
    assert buy["RSI M5"]["ok"] is False
    assert sell["RSI M5"]["ok"] is True
    assert buy["Tendance H1"]["ok"] is True


def test_constant_volatility_is_normal():
    m5 = _frame(1.10 + np.zeros(300))
    h1 = _frame(1.10 + np.zeros(300), freq="1h")
    vol = _by_label(evaluate("BUY", h1, m5, CCFG))["Volatilité M5"]
    assert vol["ok"] is True


def test_short_h1_history_is_not_guessed():
    h1 = _frame(1.10 + np.zeros(50), freq="1h")
    assert h1_trend(h1) == "NEUTRE"
    m5 = _frame(1.10 + np.zeros(300))
    assert _by_label(evaluate("BUY", h1, m5, CCFG))["Tendance H1"]["ok"] is None


def test_failed_confirmation_blocks_signal():
    CFG = {"decision": {"min_edge": 0.10, "heatmap_min_pips": 1.0}}
    plan = {"entry": 1.1, "sl": 1.098, "tp": 1.104, "risk_pips": 20, "rr_gross": 2, "rr_net": 2,
            "lots": 0.05, "risk_money": 10, "invalidation": "x"}
    setup = Decision("BUY", 1.1, ["setup"], [], plan)
    probs = {"conditional": {"n": 200, "probs": {"HAUSSIER": 0.5, "NEUTRE": 0.2, "BAISSIER": 0.3}},
             "low_sample": False, "condition_label": "test"}
    mean = pd.DataFrame(np.nan, index=range(24), columns=range(5))
    count = pd.DataFrame(0, index=range(24), columns=range(5))
    mean.loc[10, 1] = 2.0
    count.loc[10, 1] = 50
    when = pd.Timestamp("2026-10-06 10:00", tz="UTC")
    ok_conf = [{"label": "RSI M5", "ok": True, "detail": "50"}]
    bad_conf = [{"label": "RSI M5", "ok": False, "detail": "75"}]
    assert combine(setup, probs, mean, count, when, CFG, confirmations=ok_conf).action == "BUY"
    blocked = combine(setup, probs, mean, count, when, CFG, confirmations=bad_conf)
    assert blocked.action == NO_TRADE
    assert any("rsi m5" in w for w in blocked.waiting_for)
