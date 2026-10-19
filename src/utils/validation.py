"""Contrôles de qualité des données OHLC. Aucune donnée n'est corrigée ou inventée."""
import pandas as pd

PRICE_COLS = ["open", "high", "low", "close"]


def validate_ohlc(df: pd.DataFrame) -> list[str]:
    """Retourne la liste des anomalies détectées (liste vide = données correctes)."""
    missing = [c for c in PRICE_COLS if c not in df.columns]
    if missing:
        return [f"colonnes manquantes : {missing}"]
    if len(df) == 0:
        return ["aucune bougie"]

    errors = []
    if not isinstance(df.index, pd.DatetimeIndex) or df.index.tz is None:
        errors.append("index temporel UTC (timezone-aware) requis")
    if df[PRICE_COLS].isna().any().any():
        errors.append("valeurs manquantes ou non numériques")
    if df.index.duplicated().any():
        errors.append("horodatages dupliqués")
    if not df.index.is_monotonic_increasing:
        errors.append("horodatages non triés")
    if errors:
        return errors  # inutile de contrôler la cohérence des prix si la structure est fausse

    if (df["high"] < df[["open", "close"]].max(axis=1)).any():
        errors.append("high inférieur à open ou close")
    if (df["low"] > df[["open", "close"]].min(axis=1)).any():
        errors.append("low supérieur à open ou close")
    if (df[PRICE_COLS] <= 0).any().any():
        errors.append("prix non positifs")
    return errors


def check_freshness(last_time: pd.Timestamp, now: pd.Timestamp, max_age_minutes: float) -> str | None:
    """Retourne un message si la dernière bougie est trop ancienne, sinon None."""
    age_min = (now - last_time).total_seconds() / 60
    if age_min > max_age_minutes:
        return f"données périmées (dernière bougie il y a {age_min:.0f} min)"
    return None
