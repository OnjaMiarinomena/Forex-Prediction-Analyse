"""Sources de données de marché : OANDA (API v20) et CSV local.

Règles : une source en erreur lève MarketDataError ; aucune donnée n'est inventée ;
les bougies incomplètes ne sont jamais utilisées.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd

from src.utils.validation import validate_ohlc

TF_MINUTES = {"M5": 5, "M15": 15, "M30": 30, "H1": 60}
OANDA_HOSTS = {
    "practice": "https://api-fxpractice.oanda.com",
    "live": "https://api-fxtrade.oanda.com",
}


class MarketDataError(RuntimeError):
    """Erreur de configuration, de connexion, de lecture ou de validation."""


class MarketDataProvider(ABC):
    name: str = "inconnu"

    @abstractmethod
    def get_m5(self, bars: int) -> pd.DataFrame:
        """Retourne les dernières bougies M5 clôturées (index UTC, open/high/low/close)."""


def resample_ohlc(m5: pd.DataFrame, tf: str) -> pd.DataFrame:
    """Agrège des bougies M5 vers M15, M30 ou H1. Les tranches incomplètes sont supprimées."""
    if tf not in TF_MINUTES:
        raise MarketDataError(f"timeframe inconnu : {tf}")
    if tf == "M5":
        return m5
    minutes = TF_MINUTES[tf]
    rule = f"{minutes}min"
    kwargs = {"label": "left", "closed": "left"}
    agg_map = {"open": "first", "high": "max", "low": "min", "close": "last"}
    if "volume" in m5.columns:
        agg_map["volume"] = "sum"
    agg = m5.resample(rule, **kwargs).agg(agg_map)
    counts = m5["close"].resample(rule, **kwargs).count()
    return agg[counts == minutes // 5].dropna()


class CsvProvider(MarketDataProvider):
    """Lit des bougies M5 depuis un CSV : colonnes time,open,high,low,close (UTC)."""

    name = "CSV local"

    def __init__(self, path: str | Path, name: str = "CSV local"):
        self.path = Path(path)
        self.name = name

    def get_m5(self, bars: int) -> pd.DataFrame:
        if not self.path.exists():
            raise MarketDataError(f"Fichier introuvable : {self.path}")
        df = pd.read_csv(self.path)
        missing = {"time", "open", "high", "low", "close"} - set(df.columns)
        if missing:
            raise MarketDataError(f"{self.path.name} : colonnes manquantes {sorted(missing)}")
        df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
        if df["time"].isna().any():
            raise MarketDataError(f"{self.path.name} : horodatages illisibles")
        df = df.set_index("time").sort_index()
        for col in ["open", "high", "low", "close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        keep = ["open", "high", "low", "close"] + (["volume"] if "volume" in df.columns else [])
        df = df[keep]
        errors = validate_ohlc(df)
        if errors:
            raise MarketDataError(f"{self.path.name} : " + "; ".join(errors))
        return df.tail(bars)


class OandaProvider(MarketDataProvider):
    """Bougies EUR/USD via l'API REST OANDA v20 (lecture seule, aucun ordre)."""

    def __init__(self, instrument="EUR_USD", environment="practice", api_key=None, timeout=20):
        key = api_key or os.getenv("OANDA_API_KEY")
        if not key:
            raise MarketDataError("OANDA_API_KEY absente : créez un fichier .env (voir .env.example)")
        if environment not in OANDA_HOSTS:
            raise MarketDataError(f"environnement OANDA inconnu : {environment}")
        self.key = key
        self.host = OANDA_HOSTS[environment]
        self.instrument = instrument
        self.timeout = timeout
        self.name = f"OANDA {environment} ({instrument})"

    def _request(self, params: dict) -> dict:
        url = f"{self.host}/v3/instruments/{self.instrument}/candles?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {self.key}",
            "Accept-Datetime-Format": "RFC3339",
        })
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            raise MarketDataError(f"OANDA a répondu HTTP {e.code} : vérifiez la clé et l'environnement") from e
        except urllib.error.URLError as e:
            raise MarketDataError(f"connexion à OANDA impossible : {e.reason}") from e

    def get_m5(self, bars: int) -> pd.DataFrame:
        if not 50 <= bars <= 50000:
            raise MarketDataError("nombre de bougies demandé hors limites (50 à 50000)")
        candles: list[dict] = []
        to = None
        while len(candles) < bars:
            params = {"granularity": "M5", "price": "M", "count": min(5000, bars - len(candles))}
            if to:
                params["to"] = to
            page = [c for c in self._request(params).get("candles", []) if c.get("complete")]
            if not page:
                break
            new_to = page[0]["time"]
            if new_to == to:  # pas de progression : on arrête pour éviter une boucle infinie
                break
            candles = page + candles
            to = new_to
        if not candles:
            raise MarketDataError("OANDA n'a renvoyé aucune bougie complète")
        return self._to_frame(candles).tail(bars)

    @staticmethod
    def _to_frame(candles: list[dict]) -> pd.DataFrame:
        idx = pd.to_datetime([c["time"] for c in candles], utc=True)
        df = pd.DataFrame({
            "open": [float(c["mid"]["o"]) for c in candles],
            "high": [float(c["mid"]["h"]) for c in candles],
            "low": [float(c["mid"]["l"]) for c in candles],
            "close": [float(c["mid"]["c"]) for c in candles],
        }, index=idx)
        df = df[~df.index.duplicated(keep="last")].sort_index()
        errors = validate_ohlc(df)
        if errors:
            raise MarketDataError("données OANDA incohérentes : " + "; ".join(errors))
        return df
