"""Calendrier économique saisi à la main (data/events.csv). Aucune annonce n'est inventée.

Format : time_utc (ex. 2026-10-16 12:30:00), title, impact (high / medium / low).
"""
from pathlib import Path

import pandas as pd

from src.data_sources.market_data import MarketDataError

REQUIRED = ["time_utc", "title", "impact"]


def load_events(path):
    p = Path(path)
    if not p.exists():
        return None
    df = pd.read_csv(p)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise MarketDataError(f"{p.name} : colonnes manquantes {missing} (attendu : time_utc,title,impact)")
    df["time_utc"] = pd.to_datetime(df["time_utc"], utc=True, errors="coerce")
    df = df.dropna(subset=["time_utc"]).copy()
    df["impact"] = df["impact"].astype(str).str.lower().str.strip()
    return df


def event_block(events, now, before_min, after_min, impact="high"):
    """Retourne (message_de_blocage ou None, information_de_calendrier)."""
    if events is None:
        return None, "annonces : non saisies"
    relevant = events[events["impact"] == impact]
    if relevant.empty:
        return None, "annonces : non saisies"
    for _, row in relevant.iterrows():
        delta = (row["time_utc"] - now).total_seconds() / 60
        if -after_min <= delta <= before_min:
            return (f"annonce « {row['title']} » à {row['time_utc']:%H:%M} UTC "
                    f"({delta:+.0f} min) : attendre la publication"), None
    return None, f"aucune annonce « {impact} » proche"
