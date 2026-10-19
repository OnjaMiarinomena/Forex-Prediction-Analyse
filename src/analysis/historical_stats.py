"""Statistiques historiques descriptives.

Ce ne sont PAS des prédictions garanties : ce sont des fréquences observées dans le passé.
Les étiquettes futures ne servent qu'à mesurer l'historique. Le contexte courant n'utilise
que des bougies déjà clôturées, sans regarder vers le futur.
"""
import numpy as np
import pandas as pd

from src.analysis.candlesticks import pattern_at
from src.analysis.indicators import atr

CLASSES = ["HAUSSIER", "NEUTRE", "BAISSIER"]


def forward_labels(m5: pd.DataFrame, horizon: int, pip_size: float, threshold_pips: float = 0.0):
    """Mouvement en pips à l'horizon et étiquette correspondante (None sans bougie future)."""
    close = m5["close"].astype(float)
    fwd = (close.shift(-horizon) - close) / pip_size
    labels = pd.Series(
        np.select([fwd >= threshold_pips, fwd <= -threshold_pips], ["HAUSSIER", "BAISSIER"], default="NEUTRE"),
        index=m5.index,
        dtype=object,
    )
    labels = labels.where(fwd.notna(), None)
    return fwd, labels


def pattern_directions(m5: pd.DataFrame, atr_period: int = 14) -> pd.Series:
    """Direction (BUY/SELL) de la figure M5 de chaque bougie, ou None."""
    atr_series = atr(m5, atr_period)
    out = [None] * len(m5)
    for i in range(1, len(m5)):
        pattern = pattern_at(m5, atr_series, i)
        out[i] = pattern[1] if pattern else None
    return pd.Series(out, index=m5.index, dtype=object)


def class_stats(labels: pd.Series, mask: pd.Series | None = None) -> dict:
    s = labels.dropna()
    if mask is not None:
        s = s[mask.loc[s.index].to_numpy(dtype=bool)]
    n = len(s)
    if n == 0:
        return {"n": 0, "probs": None}
    counts = s.value_counts()
    return {"n": n, "probs": {c: float(counts.get(c, 0)) / n for c in CLASSES}}


def current_probabilities(m5: pd.DataFrame, pcfg: dict, pip_size: float, atr_period: int = 14) -> dict:
    """Fréquences historiques : base générale et conditionnée à la figure du dernier bougie clôturée."""
    horizon, threshold, min_n = pcfg["horizon_bars"], pcfg["threshold_pips"], pcfg["min_samples"]
    _, labels = forward_labels(m5, horizon, pip_size, threshold)
    directions = pattern_directions(m5, atr_period)
    last = directions.iloc[-1]

    base = class_stats(labels)
    if last:
        conditional = class_stats(labels, directions == last)
        condition_label = f"après une figure M5 {last}"
    else:
        conditional = class_stats(labels, directions.isna())
        condition_label = "sur les bougies sans figure M5"

    return {
        "horizon_bars": horizon,
        "threshold_pips": threshold,
        "base": base,
        "conditional": conditional,
        "condition_label": condition_label,
        "pattern": last,
        "low_sample": conditional["n"] < min_n,
        "min_samples": min_n,
    }


def hour_weekday_heatmap(m5: pd.DataFrame, horizon: int, pip_size: float, min_samples: int):
    """Mouvement moyen (pips) par heure UTC (0-23) et jour (0=lundi à 4=vendredi).

    Les cellules avec moins de min_samples observations valent NaN.
    Limite connue : l'horizon peut traverser un week-end ou un jour férié.
    """
    fwd, _ = forward_labels(m5, horizon, pip_size)
    df = pd.DataFrame({"fwd": fwd, "hour": m5.index.hour, "dow": m5.index.dayofweek}).dropna()
    df = df[df["dow"] < 5]
    grouped = df.groupby(["hour", "dow"])["fwd"]
    rows, cols = range(24), range(5)
    mean = grouped.mean().unstack("dow").reindex(index=rows, columns=cols)
    count = grouped.count().unstack("dow").reindex(index=rows, columns=cols).fillna(0).astype(int)
    return mean.where(count >= min_samples), count
