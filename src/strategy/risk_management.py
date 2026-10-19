"""Calcul du plan de trade : stop-loss, take-profit, RR net et taille indicative.

Aucun ordre n'est envoyé. La taille est une estimation à vérifier chez le courtier.
"""
import math


def build_plan(direction, price, ob_low, ob_high, atr5, cfg, spread_pips=None):
    """Retourne (plan, message). plan vaut None si le trade est rejeté, avec le motif dans message."""
    pip = cfg["pip_size"]
    buffer = cfg["sl_buffer_atr"] * float(atr5)

    if direction == "BUY":
        sl = ob_low - buffer
        risk = price - sl
    elif direction == "SELL":
        sl = ob_high + buffer
        risk = sl - price
    else:
        return None, "direction inconnue"

    if risk <= 0:
        return None, "stop-loss mal placé"
    risk_pips = risk / pip
    if risk_pips > cfg["max_sl_pips"]:
        return None, f"stop-loss trop large ({risk_pips:.1f} pips)"

    spread_price = (spread_pips or 0.0) * pip
    rr_net = (risk * cfg["target_rr"] - spread_price) / (risk + spread_price)
    if rr_net < cfg["min_rr"]:
        return None, f"RR net insuffisant ({rr_net:.2f} < {cfg['min_rr']})"

    sign = 1 if direction == "BUY" else -1
    tp = price + sign * risk * cfg["target_rr"]

    risk_money = cfg["equity"] * cfg["risk_pct"] / 100
    lots = math.floor(round(risk_money / (risk_pips * cfg["pip_value_usd_per_lot"]) * 100, 6)) / 100
    if lots < 0.01:
        return None, "taille calculée inférieure au lot minimum (0.01)"

    plan = {
        "entry": price,
        "sl": sl,
        "tp": tp,
        "risk_pips": risk_pips,
        "rr_gross": cfg["target_rr"],
        "rr_net": rr_net,
        "lots": lots,
        "risk_money": risk_money,
    }
    return plan, "ok"
