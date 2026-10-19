"""Réaction mesurée du prix après une annonce passée (données réelles uniquement)."""
import pandas as pd


def reaction_pips(tf_df: pd.DataFrame, when: pd.Timestamp, horizon_min: int, pip_size: float):
    """Variation en pips du dernier close avant l'annonce au dernier close après horizon_min.

    Retourne None si l'annonce est future ou si les données ne couvrent pas l'horizon.
    """
    if tf_df.empty:
        return None
    end = when + pd.Timedelta(minutes=horizon_min)
    if end > tf_df.index[-1]:
        return None
    i0 = tf_df.index.searchsorted(when, side="right") - 1
    i1 = tf_df.index.searchsorted(end, side="right") - 1
    if i0 < 0 or i1 <= i0:
        return None
    return float((tf_df["close"].iloc[i1] - tf_df["close"].iloc[i0]) / pip_size)
