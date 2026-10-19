"""Figures de chandeliers : engulfing et pin bar, avec filtre de taille via l'ATR."""
import pandas as pd


def pattern_at(df: pd.DataFrame, atr_series: pd.Series, i: int, min_range_atr: float = 0.5):
    """Retourne (nom, direction) pour la bougie i, ou None. direction vaut BUY ou SELL."""
    if i < 1 or pd.isna(atr_series.iloc[i]):
        return None
    a = float(atr_series.iloc[i])
    o, h, l, c = (float(df[col].iloc[i]) for col in ["open", "high", "low", "close"])
    po, pc = float(df["open"].iloc[i - 1]), float(df["close"].iloc[i - 1])

    body, rng = abs(c - o), h - l
    upper, lower = h - max(o, c), min(o, c) - l
    prev_body = abs(pc - po)

    if pc < po and c > o and o <= pc and c >= po and body > prev_body:
        return ("engulfing haussier", "BUY")
    if pc > po and c < o and o >= pc and c <= po and body > prev_body:
        return ("engulfing baissier", "SELL")

    if rng >= min_range_atr * a:
        if lower >= 2 * body and lower >= 0.6 * rng:
            return ("pin bar haussier", "BUY")
        if upper >= 2 * body and upper >= 0.6 * rng:
            return ("pin bar baissier", "SELL")
    return None
