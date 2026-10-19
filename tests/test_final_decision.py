import numpy as np
import pandas as pd

from src.strategy.decision_engine import NO_TRADE, Decision
from src.strategy.final_decision import combine

CFG = {"decision": {"min_edge": 0.10, "heatmap_min_pips": 1.0}}
TUESDAY_10H = pd.Timestamp("2026-10-06 10:00", tz="UTC")  # mardi, dayofweek = 1
PLAN = {"entry": 1.1, "sl": 1.098, "tp": 1.104, "risk_pips": 20, "rr_gross": 2, "rr_net": 2,
        "lots": 0.05, "risk_money": 10, "invalidation": "x"}


def _heat(value=2.0, n=50):
    mean = pd.DataFrame(np.nan, index=range(24), columns=range(5))
    count = pd.DataFrame(0, index=range(24), columns=range(5))
    mean.loc[10, 1] = value
    count.loc[10, 1] = n
    return mean, count


def _probs(up=0.5, down=0.3, n=200, low=False):
    return {"conditional": {"n": n, "probs": {"HAUSSIER": up, "NEUTRE": 1 - up - down, "BAISSIER": down}},
            "low_sample": low, "condition_label": "test"}


def _setup(action="BUY"):
    if action == "NO TRADE":
        return Decision("NO TRADE", 1.1, ["setup"], ["figure M5 manquante"])
    return Decision(action, 1.1, ["setup ok"], [], PLAN)


def test_all_agree_gives_buy():
    mean, count = _heat(2.0)
    d = combine(_setup("BUY"), _probs(0.5, 0.3), mean, count, TUESDAY_10H, CFG)
    assert d.action == "BUY" and d.plan is not None


def test_probabilities_contradicting_setup_gives_no_trade():
    mean, count = _heat(2.0)
    d = combine(_setup("BUY"), _probs(0.2, 0.6), mean, count, TUESDAY_10H, CFG)
    assert d.action == NO_TRADE
    assert any("contraire aux probabilités" in w or "contradictoires" in w for w in d.waiting_for)


def test_heatmap_contradiction_blocks_sell():
    # Setup SELL, probabilités baissières, mais heatmap positive : contradiction -> NO TRADE
    mean, count = _heat(2.0)
    d = combine(_setup("SELL"), _probs(0.2, 0.6), mean, count, TUESDAY_10H, CFG)
    assert d.action == NO_TRADE
    assert any("contraire à la heatmap" in w for w in d.waiting_for)


def test_small_heatmap_sample_gives_no_trade():
    mean, count = _heat(2.0, n=5)
    mean.loc[10, 1] = np.nan  # masquée car n < min_samples
    d = combine(_setup("BUY"), _probs(0.5, 0.3), mean, count, TUESDAY_10H, CFG)
    assert d.action == NO_TRADE
    assert any("heatmap" in w for w in d.waiting_for)


def test_no_setup_gives_no_trade_with_setup_reasons():
    mean, count = _heat(2.0)
    d = combine(_setup("NO TRADE"), _probs(0.5, 0.3), mean, count, TUESDAY_10H, CFG)
    assert d.action == NO_TRADE and d.plan is None
    assert "figure M5 manquante" in d.waiting_for


def test_weekend_gives_no_trade():
    mean, count = _heat(2.0)
    saturday = pd.Timestamp("2026-10-10 10:00", tz="UTC")
    d = combine(_setup("BUY"), _probs(0.5, 0.3), mean, count, saturday, CFG)
    assert d.action == NO_TRADE
