"""Télécharge l'historique EUR/USD M5 (Yahoo Finance, sans clé) au format du programme.

Résultat : data/raw/EURUSD_M5.csv (time,open,high,low,close, heure UTC).
Yahoo ne fournit que ~60 derniers jours en M5 ; les données ne viennent pas de votre courtier.

Usage : python3 tools/download_eurusd.py      (dépendance : pip install yfinance)
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "raw" / "EURUSD_M5.csv"


class DownloadError(RuntimeError):
    pass


def normalize(raw: pd.DataFrame) -> pd.DataFrame:
    """Format attendu : index UTC, colonnes open/high/low/close, sans lignes vides ni doublons."""
    df = raw.copy()
    if isinstance(df.columns, pd.MultiIndex):  # yfinance récent : (Prix, Ticker)
        df.columns = df.columns.get_level_values(0)
    wanted = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    df = df[wanted].rename(columns=str.lower).dropna(subset=["open", "high", "low", "close"])
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")
    df.index.name = "time"
    return df[~df.index.duplicated(keep="last")].sort_index()


def download(out: Path = OUT) -> int:
    """Télécharge et écrit le CSV. Retourne le nombre de bougies. Lève DownloadError si échec."""
    try:
        import yfinance as yf
    except ImportError as e:
        raise DownloadError("module yfinance absent : pip install yfinance") from e
    try:
        raw = yf.download("EURUSD=X", interval="5m", period="60d", progress=False, auto_adjust=False)
    except Exception as e:
        raise DownloadError(f"téléchargement Yahoo impossible : {e}") from e
    if raw is None or raw.empty:
        raise DownloadError("aucune donnée reçue de Yahoo Finance (connexion ou limite)")
    df = normalize(raw)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.reset_index().to_csv(out, index=False, date_format="%Y-%m-%d %H:%M:%S")
    return len(df)


def main() -> int:
    try:
        n = download()
    except DownloadError as e:
        print(f"ECHEC : {e}")
        return 1
    print(f"OK : {n} bougies M5 écrites dans {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
