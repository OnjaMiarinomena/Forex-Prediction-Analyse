import os
import tempfile

import pandas as pd

import src.data_sources.calendar as cal
import src.data_sources.news as news

XML = b"""<?xml version="1.0"?><weekevents>
<event><title>Non-Farm Employment Change</title><country>USD</country><date>10-16-2026</date>
<time>8:30am</time><impact>High</impact></event>
<event><title>German ZEW</title><country>EUR</country><date>10-16-2026</date>
<time>All Day</time><impact>Medium</impact></event>
<event><title>Some Japan thing</title><country>JPY</country><date>10-16-2026</date>
<time>1:00pm</time><impact>Low</impact></event>
</weekevents>"""


def test_parse_converts_new_york_time_to_utc_and_skips_all_day():
    events = cal.parse_xml(XML, "America/New_York")
    assert len(events) == 2  # "All Day" ignoré
    nfp = [e for e in events if "Non-Farm" in e["title"]][0]
    assert nfp["when"].hour == 12 and nfp["when"].minute == 30  # 8h30 EDT = 12h30 UTC
    assert nfp["stars"] == 3


def test_headline_stars_heuristic():
    assert news.headline_stars("ECB rate decision and press conference") == 3
    assert news.headline_stars("Fed chair speech on outlook") == 2
    assert news.headline_stars("Bank holiday notice") == 1


def test_calendar_falls_back_to_manual_file_when_feed_fails():
    news._CACHE.update(at=0.0, result=None)
    cal._CACHE.update(at=0.0, result=None)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "events.csv")
        pd.DataFrame({"time_utc": ["2026-10-16 12:30:00"], "title": ["NFP"], "impact": ["high"]}).to_csv(path, index=False)
        cfg = {"calendar": {"cache_minutes": 60, "timezone": "America/New_York", "currencies": ["EUR", "USD"],
                            "feeds": ["bad"]}}

        def broken(url, timeout):
            raise OSError("hors ligne")
        now = pd.Timestamp("2026-10-15 12:00", tz="UTC")
        res = cal.get_calendar(cfg, path, now=now, fetch=broken, clock=lambda: 1e9)
    assert res["upcoming"][0]["title"] == "NFP"
    assert res["upcoming"][0]["stars"] == 3
    assert any("saisie manuelle" in e for e in res["errors"])
