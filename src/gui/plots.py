"""Graphiques matplotlib au thème sombre. Sans Tkinter, donc testables."""
import numpy as np
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

DAYS = ["Lun", "Mar", "Mer", "Jeu", "Ven"]
DARK = {
    "bg": "#0b0e14", "ax": "#11151d", "grid": "#1f2635", "text": "#cbd5e1", "muted": "#64748b",
    "up": "#22c55e", "down": "#ef4444", "price": "#60a5fa", "nan": "#374151",
    "BUY": "#22c55e", "SELL": "#ef4444", "NEUTRE": "#94a3b8",
}


def _style(fig: Figure, ax) -> None:
    fig.set_facecolor(DARK["bg"])
    ax.set_facecolor(DARK["ax"])
    ax.tick_params(colors=DARK["text"], labelsize=8)
    for spine in ax.spines.values():
        spine.set_color(DARK["grid"])
    ax.grid(color=DARK["grid"], alpha=0.6, linewidth=0.6)


def draw_heatmap(fig: Figure, mean, title: str = "", highlight=None) -> None:
    fig.clf()
    ax = fig.add_subplot(111)
    _style(fig, ax)
    data = mean.to_numpy(dtype=float)
    finite = np.abs(data[np.isfinite(data)])
    lim = float(finite.max()) if finite.size else 1.0
    lim = lim or 1.0

    ax.set_facecolor(DARK["nan"])
    image = ax.imshow(np.ma.masked_invalid(data), aspect="auto", cmap="RdYlGn",
                      vmin=-lim, vmax=lim, origin="upper")
    if highlight is not None:
        h, d = highlight
        ax.add_patch(Rectangle((d - 0.5, h - 0.5), 1, 1, fill=False, edgecolor="white", linewidth=2.5))
    ax.grid(False)
    ax.set_xticks(range(5))
    ax.set_xticklabels(DAYS)
    ax.set_yticks(range(0, 24, 2))
    ax.set_yticklabels([f"{h:02d}h" for h in range(0, 24, 2)])
    ax.set_ylabel("Heure UTC", color=DARK["text"])
    ax.set_title(title or "mouvement moyen (pips) — gris = échantillon insuffisant",
                 fontsize=10, loc="left", color=DARK["text"])
    cbar = fig.colorbar(image, ax=ax, label="pips moyens")
    cbar.ax.tick_params(colors=DARK["text"], labelsize=8)
    cbar.set_label("pips moyens", color=DARK["text"])
    cbar.outline.set_edgecolor(DARK["grid"])


def draw_price_chart(fig: Figure, tf_df, zones, focus, price, title="", n_bars=120,
                     events=None, pip_size=0.0001) -> None:
    """Prix (zones, événements), volume et RSI 14 sur un même axe temporel."""
    from src.analysis.event_impact import reaction_pips
    from src.analysis.indicators import rsi

    fig.clf()
    gs = fig.add_gridspec(3, 1, height_ratios=[6, 1.2, 1.2], hspace=0.06)
    ax = fig.add_subplot(gs[0])
    axv = fig.add_subplot(gs[1], sharex=ax)
    axr = fig.add_subplot(gs[2], sharex=ax)
    for a in (ax, axv, axr):
        _style(fig, a)

    d = tf_df.iloc[-n_bars:]
    x = np.arange(len(d))
    span = float(d["high"].max() - d["low"].min()) or 0.001
    for i, (o, h, l, c) in enumerate(zip(d["open"], d["high"], d["low"], d["close"])):
        col = DARK["up"] if c >= o else DARK["down"]
        ax.vlines(i, l, h, color=col, linewidth=1)
        ax.add_patch(Rectangle((i - 0.3, min(o, c)), 0.6, max(abs(c - o), span * 0.004), color=col))

    lo, hi = float(d["low"].min()), float(d["high"].max())
    pad = (hi - lo) * 0.1 or 0.001
    ylo, yhi = lo - pad, hi + pad
    ax.set_xlim(-1, len(d))
    ax.set_ylim(ylo, yhi)

    colors = {"BUY": DARK["BUY"], "SELL": DARK["SELL"], "NEUTRE": DARK["NEUTRE"]}
    x_label = len(d) - 0.5
    for z in zones:
        if z.high < ylo or z.low > yhi:
            continue
        is_focus = z in focus
        col = colors.get(z.side, DARK["NEUTRE"])
        if z.kind == "zone":
            ax.axhspan(z.low, z.high, facecolor=col, edgecolor=col,
                       alpha=0.32 if is_focus else 0.14,
                       linestyle="--" if is_focus else "-", linewidth=1.6 if is_focus else 0.8)
            y = (z.low + z.high) / 2
        else:
            ax.axhline(z.low, color=col, linestyle=":", linewidth=1)
            y = z.low
        ax.text(x_label, y, ("▶ " if is_focus else "") + z.label, ha="right", va="center", fontsize=8,
                color=DARK["text"] if is_focus else DARK["muted"],
                bbox=dict(facecolor=DARK["bg"], alpha=0.85, edgecolor="none", pad=2))

    # annonces : ligne verticale, étoiles, réaction mesurée (passé) ou « à venir » (futur)
    for k, e in enumerate(sorted(events or [], key=lambda ev: ev["when"])):
        when = e["when"]
        if when < d.index[0]:
            continue
        future = when > d.index[-1]
        xpos = x_label if future else float(d.index.searchsorted(when, side="right") - 1)
        col = "#38bdf8" if e["currency"] == "EUR" else ("#fb923c" if e["currency"] == "USD" else DARK["muted"])
        ax.axvline(xpos, color=col, linestyle="--", linewidth=0.8, alpha=0.6)
        label = "★" * e["stars"] + f" {e['currency']} {e['title'][:24]}"
        if future:
            label += "  → à venir"
        else:
            pips = reaction_pips(tf_df, when, 60, pip_size)
            if pips is not None:
                label += f"  {pips:+.0f} p / 1 h"
        y = yhi - (yhi - ylo) * (0.03 + 0.07 * (k % 4))
        if future:
            ax.text(xpos - 0.3, y, label, fontsize=7, color=col, va="top", ha="right",
                    bbox=dict(facecolor=DARK["bg"], alpha=0.8, edgecolor="none", pad=1.5))
        else:
            ax.text(xpos + 0.3, y, label, fontsize=7, color=col, va="top", ha="left",
                    bbox=dict(facecolor=DARK["bg"], alpha=0.8, edgecolor="none", pad=1.5))

    ax.axhline(price, color=DARK["price"], linewidth=1.2)
    ax.text(0, price, f" {price:.5f}", va="bottom", fontsize=8, color=DARK["price"])
    ax.set_title(title, fontsize=11, loc="left", color=DARK["text"])

    up_down = [DARK["up"] if c >= o else DARK["down"] for o, c in zip(d["open"], d["close"])]
    if "volume" in d.columns and (d["volume"] > 0).any():
        axv.bar(x, d["volume"].values, color=up_down, width=0.6)
        axv.set_ylabel("Volume", color=DARK["muted"], fontsize=8)
    else:
        axv.text(0.5, 0.5, "volume non fourni par la source", transform=axv.transAxes,
                 ha="center", va="center", color=DARK["muted"], fontsize=8)
        axv.set_yticks([])

    values = rsi(tf_df["close"], 14).iloc[-n_bars:]
    axr.plot(x, values.values, color="#a78bfa", linewidth=1.2)
    axr.axhline(70, color=DARK["down"], linestyle=":", linewidth=0.8)
    axr.axhline(30, color=DARK["up"], linestyle=":", linewidth=0.8)
    axr.set_ylim(0, 100)
    axr.set_ylabel("RSI 14", color=DARK["muted"], fontsize=8)

    ax.tick_params(labelbottom=False)
    axv.tick_params(labelbottom=False)
    step = max(1, len(d) // 8)
    axr.set_xticks(range(0, len(d), step))
    axr.set_xticklabels([t.strftime("%d %H:%M") for t in d.index[::step]], fontsize=8)
