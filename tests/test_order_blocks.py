import pandas as pd

from src.analysis.order_blocks import find_order_blocks


def test_bullish_order_block_detected_and_active():
    rows = [
        [1.0980, 1.0995, 1.0975, 1.0990],  # 0 haussière
        [1.1000, 1.1005, 1.0985, 1.0990],  # 1 baissière : origine de l'OB
        [1.0990, 1.1000, 1.0980, 1.0995],  # 2
        [1.0995, 1.1002, 1.0992, 1.1000],  # 3
        [1.0990, 1.1032, 1.0988, 1.1030],  # 4 impulsion qui casse le plus haut récent
        [1.1020, 1.1040, 1.1018, 1.1035],  # 5 reste au-dessus de la zone
    ]
    idx = pd.date_range("2026-10-01", periods=len(rows), freq="30min", tz="UTC")
    df = pd.DataFrame(rows, index=idx, columns=["open", "high", "low", "close"])
    atr = pd.Series(0.001, index=idx)

    blocks = find_order_blocks(df, atr, lookback=3, impulse_atr=1.0)
    assert len(blocks) == 1
    ob = blocks[0]
    assert ob.direction == "BUY"
    assert ob.status == "actif"
    assert abs(ob.low - 1.0985) < 1e-9 and abs(ob.high - 1.1005) < 1e-9
