"""Moteur de décision BUY / SELL / NO TRADE.

Règle de base : NO TRADE par défaut. Un signal exige, dans l'ordre :
données valides et fraîches -> structure M30 claire -> OB M30 valide contenant le prix
-> figure de chandelier M5 dans la direction -> BOS M5 -> plan de risque acceptable.
"""
from dataclasses import dataclass, field

import pandas as pd

from src.analysis.candlesticks import pattern_at
from src.analysis.indicators import atr
from src.analysis.market_structure import bos, structure_bias
from src.analysis.order_blocks import find_order_blocks
from src.strategy.risk_management import build_plan
from src.utils.market_hours import is_market_open
from src.utils.validation import check_freshness, validate_ohlc

NO_TRADE = "NO TRADE"
LABEL = {"BUY": "haussier", "SELL": "baissier"}


@dataclass
class Decision:
    action: str
    price: float | None = None
    reasons: list = field(default_factory=list)
    waiting_for: list = field(default_factory=list)
    plan: dict | None = None
    ob: object | None = None
    pattern: str | None = None


def _no_trade(reasons, waiting, price=None):
    return Decision(NO_TRADE, price, reasons, waiting)


def analyse(m30, m5, cfg, now=None, spread_pips=None, replay=False) -> Decision:
    now = now if now is not None else pd.Timestamp.now(tz="UTC")
    a_cfg, d_cfg, r_cfg = cfg["analysis"], cfg["data"], cfg["risk"]

    errors = validate_ohlc(m30) + validate_ohlc(m5)
    if errors:
        return _no_trade([f"Données invalides : {e}" for e in errors], ["Corriger les données"])

    price = float(m5["close"].iloc[-1])

    if not replay:
        if not is_market_open(now):
            return _no_trade(["Marché fermé (week-end)"],
                             ["Réouverture du marché, dimanche vers 21h UTC"], price)
        stale = check_freshness(m5.index[-1], now, d_cfg["max_data_age_minutes"])
        if stale:
            return _no_trade([stale], ["Données fraîches provenant de la source"], price)

    atr30 = atr(m30, a_cfg["atr_period"])
    atr5 = atr(m5, a_cfg["atr_period"])
    a5 = atr5.iloc[-1]
    if pd.isna(a5) or pd.isna(atr30.iloc[-1]):
        return _no_trade(["Historique insuffisant pour l'ATR"], ["Davantage de bougies"], price)

    direction = structure_bias(m30, a_cfg["swing_k"])
    if direction == "NEUTRE":
        return _no_trade(
            ["Structure M30 sans direction claire"],
            ["Un HH+HL (haussier) ou LH+LL (baissier) confirmé en M30"],
            price,
        )
    reasons = [f"Biais M30 : {LABEL[direction]}"]

    if spread_pips is not None and spread_pips > r_cfg["max_spread_pips"]:
        return _no_trade(
            reasons + [f"Spread trop élevé ({spread_pips} pips)"],
            [f"Spread sous {r_cfg['max_spread_pips']} pips"],
            price,
        )

    blocks = find_order_blocks(m30, atr30, a_cfg["ob_lookback"], a_cfg["impulse_atr"])
    usable = [b for b in blocks if b.direction == direction and b.status in ("actif", "mitigé")]
    in_zone = [b for b in usable if b.low <= price <= b.high]

    if not in_zone:
        waiting = [f"Retour du prix dans un OB {LABEL[direction]} M30 valide"]
        for b in usable:
            waiting.append(f"Zone surveillée : {b.low:.5f} – {b.high:.5f} (statut : {b.status})")
        if not usable:
            waiting.append("Aucun OB M30 valide : attendre une nouvelle impulsion")
        return _no_trade(reasons, waiting, price)

    ob = in_zone[-1]
    reasons.append(f"Prix dans l'OB {LABEL[direction]} M30 [{ob.low:.5f} – {ob.high:.5f}]")

    pat = pattern_at(m5, atr5, len(m5) - 1)
    pattern_ok = pat is not None and pat[1] == direction
    bos_ok = bos(m5, direction, a_cfg["swing_k"])

    waiting = []
    if not pattern_ok:
        waiting.append("Figure de chandelier M5 dans la direction (engulfing ou pin bar)")
    if not bos_ok:
        waiting.append(f"BOS M5 {LABEL[direction]} (cassure du dernier swing)")
    if waiting:
        return _no_trade(reasons, waiting, price)

    reasons += [f"Figure M5 : {pat[0]}", f"BOS M5 {LABEL[direction]} confirmé"]

    plan, message = build_plan(direction, price, ob.low, ob.high, a5, r_cfg, spread_pips)
    if plan is None:
        return _no_trade(reasons + [f"Plan de trade rejeté : {message}"], ["Configuration plus favorable"], price)

    if spread_pips is None:
        reasons.append("Spread non fourni : filtre spread non appliqué")
    plan["invalidation"] = (
        f"clôture M30 sous {ob.low:.5f}" if direction == "BUY" else f"clôture M30 au-dessus de {ob.high:.5f}"
    )
    return Decision(direction, price, reasons, [], plan, ob, pat[0])
