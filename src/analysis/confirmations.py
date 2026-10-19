"""Trois confirmations supplémentaires, en plus de la heatmap :

1. Tendance H1 : le prix est au-dessus (BUY) ou en dessous (SELL) de l'EMA 50 et de l'EMA 200 en H1.
2. RSI M5 : pas en zone de surachat pour un achat, pas en zone de survente pour une vente.
3. Volatilité M5 : l'ATR actuel est dans une plage normale par rapport à sa médiane récente.

Chaque confirmation vaut True, False, ou None si elle ne peut pas être calculée.
Un réglage à false dans config/settings.yaml (section confirmations) la désactive.
"""
import pandas as pd

from src.analysis.indicators import atr, ema, rsi

MIN_H1_BARS = 200
LABEL_TREND = {"BUY": "haussière", "SELL": "baissière", "NEUTRE": "neutre"}


def h1_trend(h1: pd.DataFrame) -> str:
    if len(h1) < MIN_H1_BARS:
        return "NEUTRE"
    close = h1["close"]
    last = float(close.iloc[-1])
    e50 = float(ema(close, 50).iloc[-1])
    e200 = float(ema(close, 200).iloc[-1])
    if last > e50 > e200:
        return "BUY"
    if last < e50 < e200:
        return "SELL"
    return "NEUTRE"


def evaluate(direction, h1: pd.DataFrame, m5: pd.DataFrame, ccfg: dict, atr_period: int = 14) -> list[dict]:
    checks = []

    if ccfg.get("h1_trend", True):
        if len(h1) < MIN_H1_BARS:
            checks.append({"label": "Tendance H1", "ok": None, "detail": "historique insuffisant"})
        else:
            trend = h1_trend(h1)
            ok = direction is not None and trend == direction
            checks.append({"label": "Tendance H1", "ok": bool(ok), "detail": LABEL_TREND[trend]})

    if ccfg.get("rsi", True):
        value = float(rsi(m5["close"], ccfg["rsi_period"]).iloc[-1])
        if pd.isna(value):
            ok = None
        elif direction == "BUY":
            ok = value < ccfg["rsi_overbought"]
        elif direction == "SELL":
            ok = value > ccfg["rsi_oversold"]
        else:
            ok = False
        checks.append({"label": "RSI M5", "ok": None if ok is None else bool(ok),
                       "detail": "non calculé" if pd.isna(value) else f"{value:.0f}"})

    if ccfg.get("volatility", True):
        a = atr(m5, atr_period)
        base = float(a.iloc[-ccfg["vol_lookback"]:].median())
        ratio = float(a.iloc[-1]) / base if base else float("nan")
        if pd.isna(ratio):
            checks.append({"label": "Volatilité M5", "ok": None, "detail": "non calculée"})
        else:
            ok = ccfg["vol_min_ratio"] <= ratio <= ccfg["vol_max_ratio"]
            checks.append({"label": "Volatilité M5", "ok": bool(ok), "detail": f"x{ratio:.2f} la médiane"})
    return checks
