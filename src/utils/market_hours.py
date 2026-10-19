"""Heures d'ouverture du marché des changes (approximation en UTC).

Fermeture : vendredi 21h UTC. Réouverture : dimanche 21h UTC.
Les changements d'heure peuvent décaler cette limite d'une heure ; à ajuster si besoin.
"""
import pandas as pd

CLOSE_HOUR_UTC = 21


def is_market_open(ts) -> bool:
    t = pd.Timestamp(ts)
    t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
    if t.dayofweek == 5:                                   # samedi
        return False
    if t.dayofweek == 4 and t.hour >= CLOSE_HOUR_UTC:      # vendredi soir
        return False
    if t.dayofweek == 6 and t.hour < CLOSE_HOUR_UTC:       # dimanche avant réouverture
        return False
    return True
