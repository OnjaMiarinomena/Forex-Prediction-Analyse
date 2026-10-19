"""Décision finale.

BUY n'est affiché que si TOUT est d'accord :
  - le setup technique (structure M30, OB, figure M5, BOS M5) donne BUY avec un plan ;
  - les probabilités historiques penchent nettement vers la hausse ;
  - la heatmap de l'heure courante est positive.
SELL est symétrique. Sinon : NO TRADE, avec la liste exacte des conditions manquantes.
"""
import pandas as pd

from src.strategy.decision_engine import NO_TRADE, Decision

DAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi"]


def stats_side(probs, min_edge, blocked, reasons):
    cond = probs["conditional"]
    n = cond["n"]
    if cond["probs"] is None or probs["low_sample"]:
        blocked.append(f"probabilités : échantillon insuffisant (n = {n})")
        return None
    up, down = cond["probs"]["HAUSSIER"], cond["probs"]["BAISSIER"]
    edge = up - down
    reasons.append(f"Probabilités ({probs['condition_label']}, n = {n}) : hausse {up:.0%}, baisse {down:.0%}")
    if edge >= min_edge:
        return "BUY"
    if -edge >= min_edge:
        return "SELL"
    blocked.append(f"probabilités : écart hausse/baisse insuffisant ({edge:+.0%}, seuil ±{min_edge:.0%})")
    return None


def heat_side(mean, count, when, min_pips, blocked, reasons):
    if when.dayofweek >= 5:
        blocked.append("heatmap : week-end, aucune cellule disponible")
        return None
    h, d = when.hour, when.dayofweek
    value = mean.loc[h, d]
    n = int(count.loc[h, d])
    if pd.isna(value):
        blocked.append(f"heatmap : cellule {h:02d}h UTC {DAYS[d]} insuffisante (n = {n})")
        return None
    reasons.append(f"Heatmap {h:02d}h UTC {DAYS[d]} : {value:+.2f} pips en moyenne (n = {n})")
    if value >= min_pips:
        return "BUY"
    if value <= -min_pips:
        return "SELL"
    blocked.append(f"heatmap : mouvement moyen trop faible ({value:+.2f} pips, seuil ±{min_pips})")
    return None


def combine(setup: Decision, probs: dict, heat_mean, heat_count, when, cfg: dict,
            confirmations=None) -> Decision:
    dcfg = cfg["decision"]
    reasons, blocked = [], []

    stats = stats_side(probs, dcfg["min_edge"], blocked, reasons)
    heat = heat_side(heat_mean, heat_count, when, dcfg["heatmap_min_pips"], blocked, reasons)

    if setup.action in ("BUY", "SELL"):
        setup_side = setup.action
    else:
        setup_side = None
        blocked.extend(setup.waiting_for or ["setup technique non confirmé"])

    if stats and heat and stats != heat:
        blocked.append("probabilités et heatmap contradictoires")
    if setup_side and stats and setup_side != stats:
        blocked.append("setup technique contraire aux probabilités")
    if setup_side and heat and setup_side != heat:
        blocked.append("setup technique contraire à la heatmap")

    for c in confirmations or []:
        if c["ok"] is not True:
            blocked.append(f"{c['label'].lower()} : {c['detail']}")

    final = None
    if not blocked and setup_side and stats and heat and setup_side == stats == heat and setup.plan:
        final = setup_side

    return Decision(
        action=final or NO_TRADE,
        price=setup.price,
        reasons=list(setup.reasons) + reasons,
        waiting_for=[] if final else blocked,
        plan=setup.plan if final else None,
        ob=setup.ob,
        pattern=setup.pattern,
    )
