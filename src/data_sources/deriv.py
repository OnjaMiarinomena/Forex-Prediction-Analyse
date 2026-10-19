"""Bougies M5 EUR/USD via l'API WebSocket publique de Deriv (lecture seule, aucune clé).

Non vérifié en direct depuis l'environnement de développement : lancez
`python main.py --check-deriv` pour contrôler la connexion chez vous.
"""
from __future__ import annotations

import json
import time

import pandas as pd

from src.data_sources.market_data import MarketDataError, MarketDataProvider
from src.utils.validation import validate_ohlc

GRANULARITY_M5 = 300
MAX_PER_REQUEST = 5000


class DerivProvider(MarketDataProvider):
    def __init__(self, symbol="frxEURUSD", app_id="1089", url="wss://ws.derivws.com/websockets/v3",
                 timeout=20, connector=None, clock=time.time):
        self.symbol = symbol
        self.url = f"{url}?app_id={app_id}"
        self.timeout = timeout
        self._send = connector or self._websocket_send
        self._clock = clock
        self.name = f"Deriv ({symbol})"

    def _websocket_send(self, payload: dict) -> dict:
        try:
            import websocket  # paquet websocket-client
        except ImportError as e:
            raise MarketDataError("module websocket-client absent : pip install websocket-client") from e
        try:
            ws = websocket.create_connection(self.url, timeout=self.timeout)
        except Exception as e:
            hint = (" (erreur 520/5xx : serveur Deriv indisponible ou adresse obsolète ; "
                    "essayez plus tard ou changez deriv.url dans config/settings.yaml)")
            raise MarketDataError(f"connexion Deriv impossible : {e}{hint}") from e
        try:
            ws.send(json.dumps(payload))
            return json.loads(ws.recv())
        except Exception as e:
            raise MarketDataError(f"échange avec Deriv interrompu : {e}") from e
        finally:
            ws.close()

    def _candles(self, end):
        req = {
            "ticks_history": self.symbol,
            "adjust_start_time": 1,
            "count": MAX_PER_REQUEST,
            "end": end,
            "style": "candles",
            "granularity": GRANULARITY_M5,
        }
        resp = self._send(req)
        if "error" in resp:
            raise MarketDataError(f"Deriv a renvoyé une erreur : {resp['error'].get('message', resp['error'])}")
        return resp.get("candles", [])

    def get_m5(self, bars: int) -> pd.DataFrame:
        if not 50 <= bars <= 50000:
            raise MarketDataError("nombre de bougies demandé hors limites (50 à 50000)")
        by_epoch: dict[int, dict] = {}
        end = "latest"
        while len(by_epoch) < bars:
            page = self._candles(end)
            if not page:
                break
            for c in page:
                by_epoch[int(c["epoch"])] = c
            earliest = min(int(c["epoch"]) for c in page)
            if end != "latest" and earliest >= int(end):
                break  # pas de progression
            end = earliest
        if not by_epoch:
            raise MarketDataError("Deriv n'a renvoyé aucune bougie")

        # La dernière bougie retournée avec end=latest peut être en cours : on la retire.
        now = self._clock()
        complete = {e: c for e, c in by_epoch.items() if e + GRANULARITY_M5 <= now}
        if not complete:
            raise MarketDataError("aucune bougie M5 complète reçue de Deriv")

        epochs = sorted(complete)
        df = pd.DataFrame({
            "open": [float(complete[e]["open"]) for e in epochs],
            "high": [float(complete[e]["high"]) for e in epochs],
            "low": [float(complete[e]["low"]) for e in epochs],
            "close": [float(complete[e]["close"]) for e in epochs],
        }, index=pd.to_datetime(epochs, unit="s", utc=True))
        errors = validate_ohlc(df)
        if errors:
            raise MarketDataError("données Deriv incohérentes : " + "; ".join(errors))
        return df.tail(bars)
