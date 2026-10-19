"""Détection des Order Blocks.

Un OB haussier (BUY) est la dernière bougie baissière précédant une impulsion haussière
qui cassait le plus haut récent. Symétrique pour SELL. Une bougie opposée n'est jamais
retenue seule : une cassure avec impulsion est exigée.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class OrderBlock:
    direction: str        # BUY ou SELL
    time: pd.Timestamp    # heure de la bougie d'origine
    low: float
    high: float
    confirmed_at: pd.Timestamp
    status: str           # actif, mitigé ou invalidé


def find_order_blocks(
    df: pd.DataFrame, atr_series: pd.Series, lookback: int = 10, impulse_atr: float = 1.0
) -> list[OrderBlock]:
    o, h = df["open"].to_numpy(), df["high"].to_numpy()
    l, c = df["low"].to_numpy(), df["close"].to_numpy()
    a = atr_series.to_numpy()
    blocks, seen = [], set()

    for i in range(lookback, len(df)):
        if np.isnan(a[i]):
            continue
        prev_high, prev_low = h[i - lookback : i].max(), l[i - lookback : i].min()
        body = c[i] - o[i]
        if c[i] > prev_high and body >= impulse_atr * a[i]:
            direction = "BUY"
            candidates = [b for b in range(i - lookback, i) if c[b] < o[b]]
        elif c[i] < prev_low and -body >= impulse_atr * a[i]:
            direction = "SELL"
            candidates = [b for b in range(i - lookback, i) if c[b] > o[b]]
        else:
            continue
        if not candidates:
            continue
        b = candidates[-1]
        if b in seen:
            continue
        seen.add(b)

        low, high = l[b], h[b]
        after_c, after_h, after_l = c[i + 1 :], h[i + 1 :], l[i + 1 :]
        if direction == "BUY":
            invalidated = (after_c < low).any()
            touched = (after_l <= high).any()
        else:
            invalidated = (after_c > high).any()
            touched = (after_h >= low).any()
        status = "invalidé" if invalidated else ("mitigé" if touched else "actif")

        blocks.append(
            OrderBlock(direction, df.index[b], float(low), float(high), df.index[i], status)
        )
    return blocks
