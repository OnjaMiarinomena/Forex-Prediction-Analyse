"""Calendrier économique EUR/USD : événements des 7 prochains jours et dernières annonces.

Source principale : flux XML (semaine en cours et semaine suivante), adresses dans settings.yaml.
Repli : data/events.csv saisi à la main, si le flux est indisponible.
Étoiles : ★★★ impact fort, ★★ moyen, ★ faible, d'après l'impact annoncé par la source.
Les heures sont converties en UTC. Les événements sans heure précise sont ignorés.
"""
import time
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

from src.data_sources.economic_events import load_events
from src.data_sources.news import _fetch, describe_error

IMPACT_STARS = {"high": 3, "medium": 2, "low": 1}
_CACHE = {"at": 0.0, "result": None}


def parse_xml(xml_bytes: bytes, tz: str) -> list[dict]:
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml_bytes)
    events = []
    for ev in root.iter("event"):
        title = (ev.findtext("title") or "").strip()
        date = (ev.findtext("date") or "").strip()
        clock = (ev.findtext("time") or "").strip().lower()
        if not title or not date or ":" not in clock:
            continue
        try:
            local = pd.to_datetime(f"{date} {clock}", format="%m-%d-%Y %I:%M%p")
            when = local.tz_localize(tz).tz_convert("UTC")
        except (ValueError, TypeError):
            continue
        impact = (ev.findtext("impact") or "").strip().lower()
        events.append({
            "title": title,
            "currency": (ev.findtext("country") or "").strip().upper(),
            "when": when,
            "stars": IMPACT_STARS.get(impact, 0),
            "source": "calendrier",
        })
    return events


def _manual(events_path) -> list[dict]:
    df = load_events(events_path)
    if df is None or df.empty:
        return []
    return [{"title": r["title"], "currency": "SAISIE", "when": r["time_utc"],
             "stars": IMPACT_STARS.get(r["impact"], 0), "source": "saisie manuelle"}
            for _, r in df.iterrows()]


def get_calendar(cfg: dict, events_path, now=None, fetch=None, clock=time.time, timeout=8) -> dict:
    """Retourne {'upcoming': [...], 'past': [...], 'errors': [...]}."""
    ccfg = cfg["calendar"]
    now = now if now is not None else pd.Timestamp.now(tz="UTC")
    if _CACHE["result"] is not None and clock() - _CACHE["at"] < ccfg["cache_minutes"] * 60:
        cached = _CACHE["result"]
        return _select(cached["events"], cached["errors"], now)

    fetch = fetch or _fetch
    events, errors = [], []
    for url in ccfg["feeds"]:
        try:
            events += parse_xml(fetch(url, timeout), ccfg["timezone"])
        except Exception as e:
            host = urlparse(url).netloc or url
            errors.append(f"{host} {describe_error(e)}")
    events = [e for e in events if e["currency"] in ccfg["currencies"]]
    if not events:
        manual = _manual(events_path)
        if manual:
            errors.append("repli sur la saisie manuelle")
        events = manual
    _CACHE.update(at=clock(), result={"events": events, "errors": errors})
    return _select(events, errors, now)


def _select(events, errors, now):
    events = sorted(events, key=lambda e: e["when"])
    week_ago = now - pd.Timedelta(days=7)
    week_ahead = now + pd.Timedelta(days=7)
    past = [e for e in events if week_ago <= e["when"] < now]
    upcoming = [e for e in events if now <= e["when"] <= week_ahead]
    return {
        "past": list(reversed(past))[:10],
        "upcoming": upcoming[:10],
        "all": [e for e in events if week_ago <= e["when"] <= week_ahead],
        "errors": errors,
    }
