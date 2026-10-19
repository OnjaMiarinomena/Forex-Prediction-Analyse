"""Swings, structure de marché (HH/HL, LH/LL) et BOS.

Un swing n'est confirmé que lorsque k bougies suivantes sont clôturées :
les k dernières bougies ne sont donc jamais utilisées pour confirmer un swing.
"""
import pandas as pd


def swing_points(df: pd.DataFrame, k: int = 2) -> tuple[list[int], list[int]]:
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    swing_highs, swing_lows = [], []
    for i in range(k, len(df) - k):
        if highs[i] == highs[i - k : i + k + 1].max():
            swing_highs.append(i)
        if lows[i] == lows[i - k : i + k + 1].min():
            swing_lows.append(i)
    return swing_highs, swing_lows


def structure_bias(df: pd.DataFrame, k: int = 2) -> str:
    """Retourne 'BUY' (HH+HL), 'SELL' (LH+LL) ou 'NEUTRE'."""
    sh, sl = swing_points(df, k)
    if len(sh) < 2 or len(sl) < 2:
        return "NEUTRE"
    h_prev, h_last = df["high"].iloc[sh[-2]], df["high"].iloc[sh[-1]]
    l_prev, l_last = df["low"].iloc[sl[-2]], df["low"].iloc[sl[-1]]
    if h_last > h_prev and l_last > l_prev:
        return "BUY"
    if h_last < h_prev and l_last < l_prev:
        return "SELL"
    return "NEUTRE"


def bos(df: pd.DataFrame, direction: str, k: int = 2) -> bool:
    """Cassure haussière (BUY) ou baissière (SELL) du dernier swing confirmé, sur la dernière clôture."""
    sh, sl = swing_points(df, k)
    last_close = df["close"].iloc[-1]
    if direction == "BUY":
        return bool(sh) and bool(last_close > df["high"].iloc[sh[-1]])
    if direction == "SELL":
        return bool(sl) and bool(last_close < df["low"].iloc[sl[-1]])
    return False
