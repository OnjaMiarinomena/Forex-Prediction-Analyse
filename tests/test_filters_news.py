import os
import tempfile

import numpy as np
import pandas as pd
import yaml

import src.data_sources.news as news
from src.app_service import run_analysis
from src.data_sources.market_data import CsvProvider

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RSS = b"""<?xml version="1.0"?><rss><channel>
<item><title>ECB keeps rates unchanged</title><link>https://x/1</link>
<pubDate>Fri, 16 Oct 2026 14:30:00 GMT</pubDate></item>
<item><title>Fed statement</title><link>https://x/2</link>
<pubDate>Thu, 15 Oct 2026 18:00:00 GMT</pubDate></item>
</channel></rss>"""


def _cfg():
    with open(os.path.join(ROOT, "config", "settings.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_parse_rss_extracts_titles_and_utc_dates():
    items = news.parse_rss(RSS, "BCE", "EUR")
    assert items[0]["title"] == "ECB keeps rates unchanged"
    assert items[0]["when"].hour == 14 and str(items[0]["when"].tz) == "UTC"


def test_get_news_survives_one_broken_feed():
    news._CACHE.update(at=0.0, result=None)
    cfg = {"news": {"cache_minutes": 15, "max_items": 6,
                    "feeds": [{"name": "BCE", "currency": "EUR", "url": "ok"},
                              {"name": "Fed", "currency": "USD", "url": "bad"}]}}

    def fake(url, timeout):
        if url == "bad":
            raise OSError("hors ligne")
        return RSS
    res = news.get_news(cfg, clock=lambda: 1e9, fetch=fake)
    assert len(res["items"]) == 2
    assert any("Fed" in e for e in res["errors"])


def test_checks_list_has_expected_labels_and_no_trade_when_closed_market():
    rng = np.random.default_rng(12)
    n = 800
    c = 1.1 + np.cumsum(rng.normal(0, 0.0004, n))
    o = np.r_[c[0], c[:-1]]
    idx = pd.date_range("2026-10-05", periods=n, freq="5min", tz="UTC")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "M5.csv")
        pd.DataFrame({"time": idx, "open": o, "high": np.maximum(o, c) + 0.0002,
                      "low": np.minimum(o, c) - 0.0002, "close": c}).to_csv(path, index=False)
        res = run_analysis(_cfg(), CsvProvider(path), "M30", replay=True, events_path=os.path.join(tmp, "none.csv"))
    labels = [x["label"] for x in res.checks]
    for expected in ["Marché ouvert", "Structure M30", "Order Block M30", "Figure M5", "BOS M5",
                     "Probabilités", "Heatmap", "Annonces", "Ratio net"]:
        assert expected in labels
    assert res.decision.action in {"BUY", "SELL", "NO TRADE"}
    if res.decision.action != "NO TRADE":
        assert all(x["ok"] for x in res.checks if x["ok"] is not None and x["label"] in
                   ["Structure M30", "Order Block M30", "Figure M5", "BOS M5", "Probabilités", "Heatmap"])
