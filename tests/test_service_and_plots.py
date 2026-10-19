import io
import os
import tempfile

import numpy as np
import pandas as pd
import yaml
from matplotlib.figure import Figure

from src.app_service import run_analysis
from src.data_sources.market_data import CsvProvider
from src.gui.plots import draw_heatmap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _write_m5_csv(path, n, seed):
    rng = np.random.default_rng(seed)
    close = 1.1 + np.cumsum(rng.normal(0, 0.0004, n))
    opens = np.r_[close[0], close[:-1]]
    idx = pd.date_range("2026-10-05", periods=n, freq="5min", tz="UTC")
    pd.DataFrame({"time": idx, "open": opens, "high": np.maximum(opens, close) + 0.0002,
                  "low": np.minimum(opens, close) - 0.0002, "close": close}).to_csv(path, index=False)


def _cfg():
    with open(os.path.join(ROOT, "config", "settings.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_run_analysis_end_to_end_on_synthetic_csv():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "M5.csv")
        _write_m5_csv(path, 3000, 2)
        res = run_analysis(_cfg(), CsvProvider(path), "M30", replay=True)
        assert res.decision.action in {"BUY", "SELL", "NO TRADE"}
        assert res.setup.action in {"BUY", "SELL", "NO TRADE"}
        assert res.heatmap_mean.shape == (24, 5)
        assert "REJEU HISTORIQUE" in res.source
        if res.decision.action != "NO TRADE":
            assert res.decision.plan is not None


def test_heatmap_renders_to_image_without_tk():
    fig = Figure(figsize=(4, 3))
    mean = pd.DataFrame(np.random.default_rng(0).normal(0, 2, (24, 5)))
    mean.iloc[0:3, 0:2] = np.nan
    draw_heatmap(fig, mean, title="test", highlight=(10, 1))
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    assert buf.getbuffer().nbytes > 1000


def test_gui_module_compiles():
    import py_compile
    py_compile.compile(os.path.join(ROOT, "src", "gui", "app.py"), doraise=True)
