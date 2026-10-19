"""Logique partagée (GUI et CLI). Aucune dépendance à Tkinter."""
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from src.analysis.candlesticks import pattern_at
from src.analysis.confirmations import evaluate as evaluate_confirmations
from src.analysis.historical_stats import current_probabilities, hour_weekday_heatmap
from src.analysis.indicators import atr
from src.analysis.key_levels import Zone, key_zones, waiting_state
from src.analysis.market_structure import bos, structure_bias
from src.data_sources.economic_events import event_block, load_events
from src.data_sources.market_data import TF_MINUTES, MarketDataError, resample_ohlc
from src.strategy.decision_engine import NO_TRADE, Decision, analyse
from src.strategy.final_decision import combine, heat_side, stats_side
from src.utils.market_hours import is_market_open

ROOT = Path(__file__).resolve().parent.parent
MIN_BARS_FOR_STATS = 50


@dataclass
class AnalysisResult:
    decision: Decision
    setup: Decision
    probabilities: dict
    heatmap_mean: pd.DataFrame
    heatmap_count: pd.DataFrame
    tf_df: pd.DataFrame
    zones: list = field(default_factory=list)
    focus_zones: list = field(default_factory=list)
    checks: list = field(default_factory=list)
    wait_state: str = ""
    wait_text: str = ""
    event_info: str = ""
    timeframe: str = ""
    source: str = ""
    last_time: str = ""
    when: pd.Timestamp = None
    bars_used: int = 0
    price: float = 0.0
    delay_min: float = 0.0
    market_open: bool = True


def _check(label, ok, detail=""):
    return {"label": label, "ok": ok, "detail": detail}


def _build_checks(cfg, m30, m5, zones, price, probs, mean, count, when, setup, market_open, replay,
                  delay_min, spread_pips, block, events_known):
    """Liste ordonnée des filtres. ok : True (vert), False (rouge), None (non vérifié)."""
    a_cfg, d_cfg, r_cfg, p_cfg = cfg["analysis"], cfg["data"], cfg["risk"], cfg["decision"]
    bias = structure_bias(m30, a_cfg["swing_k"])
    direction = None if bias == "NEUTRE" else bias
    names = {"BUY": "haussière", "SELL": "baissière"}
    checks = []

    checks.append(_check("Marché ouvert", None if replay else market_open,
                         "rejeu historique" if replay else ("ouvert" if market_open else "week-end")))
    fresh = None if (replay or not market_open) else delay_min <= d_cfg["max_data_age_minutes"]
    checks.append(_check("Données fraîches", fresh, f"retard {delay_min:.0f} min"))
    if spread_pips is None:
        checks.append(_check("Spread", None, "non fourni"))
    else:
        checks.append(_check("Spread", spread_pips <= r_cfg["max_spread_pips"], f"{spread_pips} pips"))
    checks.append(_check("Structure M30", direction is not None, names.get(direction, "sans direction")))

    in_zone = [z for z in zones if z.kind == "zone" and (direction is None or z.side == direction)
               and z.low <= price <= z.high]
    checks.append(_check("Order Block M30", bool(in_zone) and direction is not None,
                         in_zone[0].label if in_zone else "prix hors zone"))

    pat = pattern_at(m5, atr(m5, a_cfg["atr_period"]), len(m5) - 1)
    pat_ok = bool(pat and direction and pat[1] == direction)
    checks.append(_check("Figure M5", pat_ok, pat[0] if pat else "aucune"))

    bos_ok = bool(direction) and bool(bos(m5, direction, a_cfg["swing_k"]))
    checks.append(_check("BOS M5", bos_ok, "cassure confirmée" if bos_ok else "pas de cassure"))

    cond = probs["conditional"]["probs"]
    s = stats_side(probs, p_cfg["min_edge"], [], [])
    detail = (f"hausse {cond['HAUSSIER']:.0%} · baisse {cond['BAISSIER']:.0%}" if cond
              else "échantillon insuffisant")
    checks.append(_check("Probabilités", direction is not None and s == direction, detail))

    h = heat_side(mean, count, when, p_cfg["heatmap_min_pips"], [], [])
    cell = mean.loc[when.hour, when.dayofweek] if when.dayofweek < 5 else None
    detail = f"{cell:+.2f} pips" if cell is not None and cell == cell else "cellule insuffisante"
    checks.append(_check("Heatmap", direction is not None and h == direction, detail))

    if block:
        checks.append(_check("Annonces", False, "annonce proche"))
    elif events_known:
        checks.append(_check("Annonces", True, "aucune annonce proche"))
    else:
        checks.append(_check("Annonces", None, "non saisies"))

    if setup.plan:
        checks.append(_check("Ratio net", setup.plan["rr_net"] >= r_cfg["min_rr"],
                             f"{setup.plan['rr_net']:.2f}"))
    else:
        checks.append(_check("Ratio net", None, "aucun plan"))
    return checks


def run_analysis(cfg, provider, tf, spread_pips=None, replay=False, now=None, events_path=None):
    if tf not in TF_MINUTES:
        raise MarketDataError(f"timeframe non supporté : {tf}")

    m5 = provider.get_m5(cfg["oanda"]["bars"])
    m30 = resample_ohlc(m5, "M30")
    tf_df = resample_ohlc(m5, tf)
    if len(tf_df) < MIN_BARS_FOR_STATS:
        raise MarketDataError(f"historique insuffisant en {tf} ({len(tf_df)} bougies)")

    price = float(m5["close"].iloc[-1])
    now_ts = now if now is not None else (m5.index[-1] if replay else pd.Timestamp.now(tz="UTC"))
    if now_ts.tzinfo is None:
        now_ts = now_ts.tz_localize("UTC")
    setup = analyse(m30, m5, cfg, now=now_ts, spread_pips=spread_pips, replay=replay)

    pip = cfg["risk"]["pip_size"]
    atr_period = cfg["analysis"]["atr_period"]
    pcfg = cfg["probabilities"]
    horizon_bars = max(1, round(pcfg["horizon_minutes"] / TF_MINUTES[tf]))
    probs = current_probabilities(
        tf_df,
        {"horizon_bars": horizon_bars, "threshold_pips": pcfg["threshold_pips"], "min_samples": pcfg["min_samples"]},
        pip, atr_period,
    )
    probs["horizon_minutes"] = pcfg["horizon_minutes"]
    mean, count = hour_weekday_heatmap(tf_df, horizon_bars, pip, pcfg["min_samples"])

    when = tf_df.index[-1]
    ecfg = cfg["events"]
    path = events_path if events_path is not None else ROOT / ecfg["file"]
    events = load_events(path)
    block, event_info = event_block(events, now_ts, ecfg["block_before_min"], ecfg["block_after_min"], ecfg["impact"])

    zones = key_zones(m30, m5, cfg)
    state, text, focus = waiting_state(zones, price, block)

    market_open = is_market_open(now_ts)
    delay_min = max(0.0, (now_ts - (m5.index[-1] + pd.Timedelta(minutes=5))).total_seconds() / 60)
    checks = _build_checks(cfg, m30, m5, zones, price, probs, mean, count, when, setup, market_open,
                           replay, delay_min, spread_pips, block, events is not None and not events.empty)
    bias = structure_bias(m30, cfg["analysis"]["swing_k"])
    direction = None if bias == "NEUTRE" else bias
    extra = evaluate_confirmations(direction, resample_ohlc(m5, "H1"), m5, cfg["confirmations"],
                                   cfg["analysis"]["atr_period"])
    checks = checks + extra

    final = combine(setup, probs, mean, count, when, cfg, confirmations=extra)
    if block and final.action != NO_TRADE:
        final = Decision(NO_TRADE, final.price, final.reasons, [block], None, final.ob, final.pattern)
    elif block:
        final.waiting_for = [block] + [w for w in final.waiting_for if w != block]

    return AnalysisResult(
        decision=final,
        setup=setup,
        probabilities=probs,
        heatmap_mean=mean,
        heatmap_count=count,
        tf_df=tf_df,
        zones=zones,
        focus_zones=focus,
        checks=checks,
        wait_state=state,
        wait_text=text,
        event_info=event_info,
        timeframe=tf,
        source=provider.name + (" [REJEU HISTORIQUE]" if replay else ""),
        last_time=m5.index[-1].strftime("%d %b %H:%M UTC"),
        when=when,
        bars_used=len(m5),
        price=price,
        delay_min=delay_min,
        market_open=market_open,
    )
