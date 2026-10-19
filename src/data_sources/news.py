"""Derniers titres des publications officielles BCE (EUR) et Fed (USD), via flux RSS.

Ce sont des TITRES seulement : aucune interprétation, aucun biais déduit automatiquement.
Les adresses des flux sont dans config/settings.yaml (section news) et doivent être vérifiées.
"""
import time
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import pandas as pd

_CACHE = {"at": 0.0, "result": None}


def describe_error(e: Exception) -> str:
    code = getattr(e, "code", None)
    return f"HTTP {code}" if code else type(e).__name__
STRONG_WORDS = ["rate decision", "interest rate", "rate hike", "rate cut", "inflation", "cpi", "pce",
                "nfp", "payroll", "employment", "gdp", "pmi", "monetary policy", "press conference",
                "taux directeur", "emploi", "pib"]
MEDIUM_WORDS = ["speech", "minutes", "remarks", "testimony", "outlook", "forecast", "statement", "discours"]


def headline_stars(title: str) -> int:
    """Estimation par mots-clés (pas un impact officiel) : 3 fort, 2 moyen, 1 faible."""
    lower = title.lower()
    if any(w in lower for w in STRONG_WORDS):
        return 3
    if any(w in lower for w in MEDIUM_WORDS):
        return 2
    return 1


def _fetch(url: str, timeout: float) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "eurusd-analyse/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _to_utc(text):
    if not text:
        return None
    try:
        ts = pd.Timestamp(parsedate_to_datetime(text))
    except (TypeError, ValueError):
        return None
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def parse_rss(xml_bytes: bytes, source: str, currency: str) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    items = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        items.append({
            "title": title,
            "link": (item.findtext("link") or "").strip(),
            "when": _to_utc(item.findtext("pubDate")),
            "source": source,
            "currency": currency,
            "stars": headline_stars(title),
        })
    return items


def get_news(cfg: dict, timeout: float = 8, clock=time.time, fetch=None) -> dict:
    """Retourne {'items': [...], 'errors': [...]}. Résultat mis en cache pendant cache_minutes."""
    ncfg = cfg["news"]
    now = clock()
    if _CACHE["result"] is not None and now - _CACHE["at"] < ncfg["cache_minutes"] * 60:
        return _CACHE["result"]
    fetch = fetch or _fetch
    items, errors = [], []
    for feed in ncfg["feeds"]:
        try:
            items += parse_rss(fetch(feed["url"], timeout), feed["name"], feed["currency"])
        except Exception as e:  # un flux en panne ne bloque pas les autres
            errors.append(f"{feed['name']} {describe_error(e)}")
    epoch = pd.Timestamp(0, tz="UTC")
    items.sort(key=lambda i: i["when"] or epoch, reverse=True)
    result = {"items": items[:ncfg["max_items"]], "errors": errors}
    _CACHE.update(at=now, result=result)
    return result
