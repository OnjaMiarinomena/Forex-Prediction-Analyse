"""Zones clés affichées sur le graphique, calculées uniquement à partir des données réelles.

- zone : Order Block M30 actif ou mitigé (haussier ou baissier).
- niveau : derniers swings M30 et plus haut / plus bas de la veille.
"""
from dataclasses import dataclass

from src.analysis.indicators import atr
from src.analysis.market_structure import swing_points
from src.analysis.order_blocks import find_order_blocks


@dataclass(frozen=True)
class Zone:
    label: str
    low: float
    high: float
    kind: str    # "zone" ou "niveau"
    side: str    # BUY, SELL ou NEUTRE
    status: str


def key_zones(m30, m5, cfg, max_levels=2):
    a_cfg = cfg["analysis"]
    zones = []

    for b in find_order_blocks(m30, atr(m30, a_cfg["atr_period"]), a_cfg["ob_lookback"], a_cfg["impulse_atr"]):
        if b.status in ("actif", "mitigé"):
            name = "OB haussier" if b.direction == "BUY" else "OB baissier"
            zones.append(Zone(f"{name} M30 ({b.status})", b.low, b.high, "zone", b.direction, b.status))

    sh, sl = swing_points(m30, a_cfg["swing_k"])
    for pos in sh[-max_levels:]:
        level = float(m30["high"].iloc[pos])
        zones.append(Zone("swing haut M30", level, level, "niveau", "SELL", "confirmé"))
    for pos in sl[-max_levels:]:
        level = float(m30["low"].iloc[pos])
        zones.append(Zone("swing bas M30", level, level, "niveau", "BUY", "confirmé"))

    days = m5.index.normalize().unique()
    if len(days) >= 2:
        prev = m5[m5.index.normalize() == days[-2]]
        zones.append(Zone("plus haut de la veille", float(prev["high"].max()), float(prev["high"].max()),
                          "niveau", "SELL", "veille"))
        zones.append(Zone("plus bas de la veille", float(prev["low"].min()), float(prev["low"].min()),
                          "niveau", "BUY", "veille"))
    return zones


def waiting_state(zones, price, event_message):
    """Retourne (état, explication, zones_en_attente) : ce que le système attend avant d'agir."""
    if event_message:
        return "événement économique", event_message, []
    obs = [z for z in zones if z.kind == "zone"]
    if not obs:
        return "aucune zone", "aucun OB M30 valide : attendre une nouvelle impulsion", []
    inside = [z for z in obs if z.low <= price <= z.high]
    if inside:
        return ("confirmation M5", f"prix dans {inside[0].label} : attendre figure M5 et BOS M5", inside)
    nearest = min(obs, key=lambda z: min(abs(price - z.low), abs(price - z.high)))
    return ("zone clé", f"attendre le retour du prix dans {nearest.label} "
                        f"[{nearest.low:.5f} – {nearest.high:.5f}]", [nearest])
