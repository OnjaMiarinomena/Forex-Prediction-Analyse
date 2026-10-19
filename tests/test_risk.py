from src.strategy.risk_management import build_plan

CFG = {
    "pip_size": 0.0001,
    "pip_value_usd_per_lot": 10.0,
    "equity": 1000.0,
    "risk_pct": 1.0,
    "target_rr": 2.0,
    "min_rr": 1.5,
    "max_sl_pips": 30.0,
    "sl_buffer_atr": 0.5,
}


def _close(a, b, tol=1e-9):
    return abs(a - b) < tol


def test_buy_plan_values():
    plan, msg = build_plan("BUY", 1.1000, 1.0985, 1.1005, 0.0004, CFG)
    assert msg == "ok"
    assert _close(plan["sl"], 1.0983)
    assert _close(plan["tp"], 1.1034)
    assert _close(plan["risk_pips"], 17.0, 1e-6)
    assert _close(plan["rr_net"], 2.0, 1e-9)
    assert plan["lots"] == 0.05  # 10 USD / (17 pips * 10 USD) = 0.0588 -> 0.05


def test_spread_can_reject_trade():
    plan, msg = build_plan("BUY", 1.1000, 1.0985, 1.1005, 0.0004, CFG, spread_pips=5)
    assert plan is None
    assert "RR net insuffisant" in msg


def test_sell_plan_is_mirrored():
    plan, _ = build_plan("SELL", 1.1000, 1.0985, 1.1015, 0.0004, CFG)
    assert plan["sl"] > 1.1015
    assert plan["tp"] < 1.1000
