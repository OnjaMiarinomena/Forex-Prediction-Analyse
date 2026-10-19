"""Point d'entrée. Par défaut : interface graphique. Avec --cli : sortie texte."""
import argparse
import sys
from pathlib import Path

import yaml

from src.app_service import run_analysis
from src.data_sources.deriv import DerivProvider
from src.data_sources.market_data import TF_MINUTES, CsvProvider, MarketDataError, OandaProvider
from src.utils.env import load_env

ROOT = Path(__file__).resolve().parent


def render_text(res) -> str:
    d, p = res.decision, res.probabilities
    w = 60
    lines = ["=" * w, "EURUSD AI SCALPING INTELLIGENCE".center(w), "=" * w, ""]
    lines.append(f"DÉCISION FINALE : {d.action}")
    lines.append(f"Timeframe : {res.timeframe}   Prix : {res.price:.5f}   Dernière bougie : {res.last_time}")
    lines.append(f"Source : {res.source}")
    lines.append("")
    if d.plan:
        pl = d.plan
        lines += [
            "PLAN (estimation, aucun ordre envoyé) :",
            f"  Entrée : {pl['entry']:.5f}",
            f"  Stop Loss : {pl['sl']:.5f} ({pl['risk_pips']:.1f} pips)",
            f"  Take Profit : {pl['tp']:.5f}",
            f"  RR brut {pl['rr_gross']:.2f} / RR net {pl['rr_net']:.2f}",
            f"  Taille indicative : {pl['lots']:.2f} lot(s), risque {pl['risk_money']:.2f}",
            f"  Invalidation : {pl['invalidation']}",
        ]
    else:
        lines.append("CONDITIONS MANQUANTES :")
        lines += [f"  - {x}" for x in d.waiting_for] or ["  - aucune"]
    cond = p["conditional"]
    lines += ["", "PROBABILITÉS HISTORIQUES (non garanties) :"]
    if cond["probs"]:
        for cls, v in cond["probs"].items():
            lines.append(f"  {cls:<9} {v * 100:5.1f} %")
    lines.append(f"  Contexte : {p['condition_label']} (n = {cond['n']})")
    if p["low_sample"]:
        lines.append("  ⚠ échantillon faible : estimation peu fiable")
    lines += ["", f"ÉTAT D'ATTENTE : {res.wait_state} — {res.wait_text}"] if not d.plan else []
    lines.append(f"Calendrier : {res.event_info}")
    zs = [z for z in res.zones if z.kind == "zone"]
    lines += ["", "ZONES CLÉS :"] + ([f"  - {z.label} [{z.low:.5f} – {z.high:.5f}]" for z in zs] or ["  - aucune"])
    lines += ["", "FILTRES :"]
    for c in res.checks:
        sym = "✓" if c["ok"] is True else ("✗" if c["ok"] is False else "–")
        lines.append(f"  {sym} {c['label']} · {c['detail']}")
    lines += ["", "RAISONS :"] + [f"  - {r}" for r in d.reasons]
    lines += ["", "=" * w]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="EURUSD AI Scalping Intelligence")
    parser.add_argument("--source", choices=["deriv", "oanda", "csv"], default="deriv")
    parser.add_argument("--check-deriv", action="store_true", help="teste la connexion Deriv et affiche les dernières bougies")
    parser.add_argument("--csv", help="CSV M5 (time,open,high,low,close), si --source csv")
    parser.add_argument("--tf", choices=list(TF_MINUTES), help="timeframe d'analyse")
    parser.add_argument("--spread-pips", type=float, default=None)
    parser.add_argument("--replay", action="store_true", help="ignorer la fraîcheur (historique)")
    parser.add_argument("--cli", action="store_true", help="sortie texte, sans fenêtre")
    parser.add_argument("--config", default=str(ROOT / "config" / "settings.yaml"))
    parser.add_argument("--env", default=str(ROOT / ".env"))
    args = parser.parse_args()

    load_env(args.env)
    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    tf = args.tf or cfg["analysis"]["default_tf"]

    if args.check_deriv:
        d = cfg["deriv"]
        try:
            df = DerivProvider(symbol=d["symbol"], app_id=str(d["app_id"]), url=d["url"]).get_m5(60)
        except MarketDataError as e:
            print(f"ECHEC : {e}")
            return 1
        print(f"OK : {len(df)} bougies M5 reçues. Dernières bougies :")
        print(df.tail(3).to_string())
        return 0

    if args.cli:
        try:
            if args.source == "deriv":
                d = cfg["deriv"]
                provider = DerivProvider(symbol=d["symbol"], app_id=str(d["app_id"]), url=d["url"])
            elif args.source == "csv":
                if not args.csv:
                    print("En mode csv, indiquez --csv.")
                    return 2
                provider = CsvProvider(args.csv)
            else:
                o = cfg["oanda"]
                provider = OandaProvider(instrument=o["instrument"], environment=o["environment"])
            res = run_analysis(cfg, provider, tf, args.spread_pips, args.replay)
        except MarketDataError as e:
            print(f"ERREUR DE DONNÉES : {e}")
            return 1
        print(render_text(res))
        return 0

    try:
        from src.gui.app import run_gui
    except ImportError as e:
        print(f"Interface graphique indisponible ({e}).")
        print("Sous Kali/Debian : sudo apt install python3-tk  puis  pip install matplotlib")
        print("Ou utilisez le mode texte : python main.py --cli --tf M30")
        return 1
    run_gui(cfg, args.csv if args.source == "csv" else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
