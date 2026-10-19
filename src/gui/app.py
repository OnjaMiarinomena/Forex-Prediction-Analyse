"""Interface Tkinter, thème sombre : informations en haut, colonne d'analyse à gauche,
graphique en grand à droite. Aucun ordre n'est envoyé.
"""
import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from src.app_service import run_analysis
from src.data_sources.deriv import DerivProvider
from src.data_sources.economic_events import load_events
from src.data_sources.calendar import get_calendar
from src.data_sources.news import get_news
from src.data_sources.market_data import TF_MINUTES, CsvProvider, MarketDataError, OandaProvider
from src.analysis.event_glossary import describe
from src.gui.plots import DARK, draw_heatmap, draw_price_chart

ROOT = Path(__file__).resolve().parent.parent
BG = "#0b0e14"
PANEL = "#11151d"
CARD = "#171c27"
TEXT = "#e5e7eb"
MUTED = "#8b93a7"
ACCENT = "#3b82f6"
DECISION = {"BUY": "#16a34a", "SELL": "#dc2626", "NO TRADE": "#475569", "ERREUR": "#52525b"}
DELAY = {"ok": "#22c55e", "warn": "#f59e0b", "late": "#ef4444", "closed": "#94a3b8"}
CLASSES = [("HAUSSIER", "Hausse"), ("NEUTRE", "Neutre"), ("BAISSIER", "Baisse")]
FONT = "Helvetica"


def _stars(n: int) -> str:
    return ("★" * n) if n else "·"


def _fmt_event(e: dict, upcoming: bool = False) -> str:
    when = e["when"].strftime("%a %d %b %H:%M")
    meaning, effect = describe(e["title"])
    lines = [f"{_stars(e['stars'])}  {e['currency']} · {when} UTC", f"    {e['title']}", f"    ↳ {meaning}"]
    if upcoming:
        lines.append(f"    ~ effet habituel : {effect}")
    return "\n".join(lines)


def _fmt_news(item: dict) -> str:
    when = item["when"].strftime("%d %b %H:%M") if item["when"] is not None else "—"
    return f"{_stars(item['stars'])}  {item['currency']} · {when}\n    {item['title']}"


def _format_delay(minutes: float, market_open: bool):
    if not market_open:
        return "marché fermé", "closed"
    if minutes < 10:
        return f"{int(minutes)} min", "ok"
    h, m = divmod(int(minutes), 60)
    text = f"{h} h {m:02d}" if h else f"{m} min"
    return text, ("warn" if minutes <= 30 else "late")


class EurusdApp(tk.Tk):
    def __init__(self, cfg, csv_path=None):
        super().__init__()
        self.title("EURUSD · Analyse")
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{min(1400, sw - 40)}x{min(900, sh - 80)}")
        self.configure(bg=BG)
        self.cfg = cfg
        self.csv_path = csv_path
        self.source_var = tk.StringVar(value="csv" if csv_path else "yahoo")
        self.tf_var = tk.StringVar(value=cfg["analysis"]["default_tf"])
        self.spread_var = tk.StringVar()
        self.replay_var = tk.BooleanVar(value=bool(csv_path))
        self.auto_var = tk.BooleanVar(value=False)
        self._job = None
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TCombobox", fieldbackground=CARD, background=CARD, foreground=TEXT, arrowcolor=TEXT)
        style.configure("TCheckbutton", background=BG, foreground=TEXT, font=(FONT, 10))
        style.map("TCheckbutton", background=[("active", BG)])
        style.configure("Horizontal.TProgressbar", troughcolor="#1f2635", background=ACCENT, thickness=10)
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=CARD, foreground=MUTED, padding=(14, 6))
        style.map("TNotebook.Tab", background=[("selected", PANEL)], foreground=[("selected", TEXT)])
        self.news_queue = queue.Queue()
        self.calendar_events = []
        self._build()
        self._load_news()

    # ------------------------------------------------------------------ construction
    def _label(self, parent, text="", size=10, bold=False, fg=TEXT, bg=CARD, **kw):
        font = (FONT, size, "bold") if bold else (FONT, size)
        return tk.Label(parent, text=text, font=font, fg=fg, bg=bg, **kw)

    def _build(self):
        # En-tête : décision + indicateurs clés
        header = tk.Frame(self, bg=PANEL, padx=18, pady=12)
        header.pack(fill="x")
        self.decision_box = tk.Label(header, text="—", font=(FONT, 22, "bold"), fg="white",
                                     bg=DECISION["NO TRADE"], width=12, pady=10)
        self.decision_box.pack(side="left")
        metrics = tk.Frame(header, bg=PANEL)
        metrics.pack(side="left", padx=24)
        self.price_val = self._metric(metrics, "PRIX", 0)
        self.candle_val = self._metric(metrics, "DERNIÈRE BOUGIE", 1)
        self.delay_val = self._metric(metrics, "RETARD", 2)
        self.source_val = self._metric(metrics, "SOURCE", 3)

        # Barre de commandes
        bar = tk.Frame(self, bg=BG, padx=18, pady=10)
        bar.pack(fill="x")
        for text, value in [("Yahoo récent", "yahoo"), ("Deriv", "deriv"), ("OANDA", "oanda"), ("CSV", "csv")]:
            tk.Radiobutton(bar, text=text, value=value, variable=self.source_var, bg=BG, fg=TEXT,
                           selectcolor=CARD, activebackground=BG, activeforeground=TEXT,
                           font=(FONT, 10)).pack(side="left", padx=(0, 12))
        tk.Button(bar, text="Choisir CSV…", command=self._pick_csv, relief="flat", bg=CARD, fg=TEXT,
                  activebackground="#1f2635", activeforeground=TEXT, font=(FONT, 9),
                  padx=10, pady=3).pack(side="left", padx=(4, 6))
        self.csv_name = self._label(bar, os.path.basename(self.csv_path) if self.csv_path else "",
                                    size=9, fg=MUTED, bg=BG)
        self.csv_name.pack(side="left", padx=(0, 18))
        self._label(bar, "Timeframe", size=10, fg=MUTED, bg=BG).pack(side="left")
        ttk.Combobox(bar, textvariable=self.tf_var, values=list(TF_MINUTES), state="readonly",
                     width=6).pack(side="left", padx=(6, 16))
        self._label(bar, "Spread", size=10, fg=MUTED, bg=BG).pack(side="left")
        tk.Entry(bar, textvariable=self.spread_var, width=6, bg=CARD, fg=TEXT, insertbackground=TEXT,
                 relief="flat", font=(FONT, 10)).pack(side="left", padx=(6, 16), ipady=3)
        ttk.Checkbutton(bar, text="Rejeu historique", variable=self.replay_var).pack(side="left", padx=4)
        ttk.Checkbutton(bar, text="Actualiser / minute", variable=self.auto_var,
                        command=self._toggle_auto).pack(side="left", padx=4)
        tk.Button(bar, text="Analyser", command=self.analyse, bg=ACCENT, fg="white", relief="flat",
                  activebackground="#2563eb", activeforeground="white", font=(FONT, 11, "bold"),
                  padx=22, pady=5).pack(side="right")

        # Corps : colonne gauche + graphique en grand
        body = tk.Frame(self, bg=BG, padx=12, pady=(0), )
        body.pack(fill="both", expand=True)
        outer = tk.Frame(body, bg=BG, width=360)
        outer.pack(side="left", fill="y", pady=(0, 12))
        outer.pack_propagate(False)
        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0, width=346)
        scroll = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        left = tk.Frame(canvas, bg=BG)
        canvas.create_window((0, 0), window=left, anchor="nw")
        left.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        self.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))
        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=(0, 12))

        filters = self._card(left)
        self._label(filters, "FILTRES", size=8, bold=True, fg=MUTED).pack(anchor="w")
        self.filter_summary = self._label(filters, "", size=9, bold=True, fg=MUTED)
        self.filter_summary.pack(anchor="w", pady=(4, 6))
        self.checks_frame = tk.Frame(filters, bg=CARD)
        self.checks_frame.pack(fill="x")

        probs = self._card(left)
        self._label(probs, "PROBABILITÉS HISTORIQUES", size=8, bold=True, fg=MUTED).pack(anchor="w")
        self.prob_bars, self.prob_pct = {}, {}
        for key, name in CLASSES:
            row = tk.Frame(probs, bg=CARD)
            row.pack(fill="x", pady=4)
            self._label(row, name, size=10, width=7, anchor="w").pack(side="left")
            bar_w = ttk.Progressbar(row, maximum=100, length=150)
            bar_w.pack(side="left", padx=8)
            pct = self._label(row, "—", size=10, bold=True, width=6, anchor="e")
            pct.pack(side="left")
            self.prob_bars[key], self.prob_pct[key] = bar_w, pct
        self.prob_note = self._label(probs, "", size=8, fg=MUTED, wraplength=300, justify="left")
        self.prob_note.pack(anchor="w", pady=(6, 0))

        detail = self._card(left)
        self.detail_title = self._label(detail, "", size=10, bold=True)
        self.detail_title.pack(anchor="w")
        self.detail = self._label(detail, "", size=9, wraplength=300, justify="left", fg=MUTED)
        self.detail.pack(anchor="w", pady=(6, 0))

        reasons = self._card(left)
        self._label(reasons, "RAISONS", size=8, bold=True, fg=MUTED).pack(anchor="w")
        self.reasons = self._label(reasons, "", size=9, fg=TEXT, wraplength=300, justify="left")
        self.reasons.pack(anchor="w", pady=(6, 0))

        news = self._card(left)
        self._label(news, "CALENDRIER ET ACTUALITÉS EUR / USD", size=8, bold=True, fg=MUTED).pack(anchor="w")
        self.news_text = self._label(news, "Chargement des actualités…", size=9, fg=MUTED,
                                     wraplength=300, justify="left")
        self.news_text.pack(anchor="w", pady=(6, 0))


        notebook = ttk.Notebook(right)
        notebook.pack(fill="both", expand=True)
        price_tab = tk.Frame(notebook, bg=BG)
        heat_tab = tk.Frame(notebook, bg=BG)
        notebook.add(price_tab, text="Graphique")
        notebook.add(heat_tab, text="Heatmap")
        self.price_fig = Figure(figsize=(9, 6), dpi=100)
        self.price_canvas = FigureCanvasTkAgg(self.price_fig, master=price_tab)
        self.price_canvas.get_tk_widget().pack(fill="both", expand=True)
        self.heat_fig = Figure(figsize=(8, 6), dpi=100)
        self.heat_canvas = FigureCanvasTkAgg(self.heat_fig, master=heat_tab)
        self.heat_canvas.get_tk_widget().pack(fill="both", expand=True)

        self.status = self._label(self, "Choisissez une source et un timeframe, puis Analyser.",
                                  size=9, fg=MUTED, bg=PANEL, anchor="w")
        self.status.pack(side="bottom", fill="x", ipady=4, padx=0)

    def _metric(self, parent, title, column):
        cell = tk.Frame(parent, bg=PANEL, padx=14)
        cell.grid(row=0, column=column, sticky="w")
        self._label(cell, title, size=8, bold=True, fg=MUTED, bg=PANEL).pack(anchor="w")
        value = self._label(cell, "—", size=14, bold=True, bg=PANEL)
        value.pack(anchor="w")
        return value

    def _card(self, parent):
        card = tk.Frame(parent, bg=CARD, padx=14, pady=10)
        card.pack(fill="x", pady=(0, 8))
        return card

    # ------------------------------------------------------------------ filtres et actualités
    def _render_checks(self, checks):
        for w in self.checks_frame.winfo_children():
            w.destroy()
        for c in checks:
            ok = c["ok"]
            sym, col = (("✓", "#22c55e") if ok is True else ("✗", "#ef4444") if ok is False else ("–", MUTED))
            row = tk.Frame(self.checks_frame, bg=CARD)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=sym, font=(FONT, 10, "bold"), fg=col, bg=CARD, width=2).pack(side="left")
            tk.Label(row, text=c["label"], font=(FONT, 9, "bold"), fg=TEXT, bg=CARD).pack(side="left")
            tk.Label(row, text=c["detail"], font=(FONT, 9), fg=MUTED, bg=CARD).pack(side="right")
        failing = [c for c in checks if c["ok"] is False]
        if not failing:
            self.filter_summary.config(text="Tous les filtres vérifiés sont verts", fg="#22c55e")
        else:
            self.filter_summary.config(text=f"{len(failing)} filtre(s) rouge(s) bloquent le signal",
                                       fg="#f59e0b")

    def _load_news(self):
        """Charge calendrier et actualités en arrière-plan, sans figer la fenêtre, puis tous les 15 min."""
        def worker():
            try:
                calendar = get_calendar(self.cfg, ROOT / self.cfg["events"]["file"])
                news = get_news(self.cfg)
                self.news_queue.put(("ok", calendar, news))
            except Exception as e:
                self.news_queue.put(("erreur", str(e), None))
        threading.Thread(target=worker, daemon=True).start()
        self.after(200, self._poll_news)
        self.after(15 * 60 * 1000, self._load_news)

    def _poll_news(self):
        try:
            kind, first, second = self.news_queue.get_nowait()
        except queue.Empty:
            self.after(200, self._poll_news)
            return
        if kind == "erreur":
            self.news_text.config(text=f"Actualités indisponibles : {first}", fg="#f87171")
            return
        self._show_news(first, second)

    def _show_news(self, calendar, news):
        blocks = []
        last_week = "\n\n".join(_fmt_event(e) for e in calendar["past"]) or "Aucune annonce EUR / USD."
        next_week = "\n\n".join(_fmt_event(e, upcoming=True) for e in calendar["upcoming"]) or "Aucune annonce EUR / USD."
        blocks.append("SEMAINE DERNIÈRE\n" + last_week)
        blocks.append("SEMAINE PROCHAINE\n" + next_week)
        self.calendar_events = calendar["all"]
        if news["items"]:
            blocks.append("DERNIÈRES NOUVELLES\n" + "\n".join(_fmt_news(i) for i in news["items"][:5]))
        problems = calendar["errors"] + [f"actualités : {e}" for e in news["errors"]]
        if problems:
            blocks.append("⚠ " + " · ".join(problems))
        self.news_text.config(text="\n\n".join(blocks), fg=TEXT)

    # ------------------------------------------------------------------ actions
    def _pick_csv(self):
        path = filedialog.askopenfilename(title="CSV M5", filetypes=[("CSV", "*.csv")])
        if path:
            self.csv_path = path
            self.csv_name.config(text=os.path.basename(path))
            self.source_var.set("csv")

    def _make_provider(self):
        source = self.source_var.get()
        if source == "yahoo":
            from tools.download_eurusd import OUT, DownloadError, download
            try:
                download(OUT)
            except DownloadError as e:
                raise MarketDataError(str(e)) from e
            return CsvProvider(OUT, name="Yahoo Finance")
        if source == "deriv":
            d = self.cfg["deriv"]
            return DerivProvider(symbol=d["symbol"], app_id=str(d["app_id"]), url=d["url"])
        if source == "oanda":
            o = self.cfg["oanda"]
            return OandaProvider(instrument=o["instrument"], environment=o["environment"])
        if not self.csv_path:
            raise MarketDataError("Choisissez un fichier CSV M5.")
        return CsvProvider(self.csv_path)

    def _toggle_auto(self):
        if self.auto_var.get():
            self._tick()
        elif self._job is not None:
            self.after_cancel(self._job)
            self._job = None

    def _tick(self):
        self.analyse(silent=True)
        self._job = self.after(60_000, self._tick) if self.auto_var.get() else None

    def analyse(self, silent=False):
        spread_txt = self.spread_var.get().strip().replace(",", ".")
        try:
            spread = float(spread_txt) if spread_txt else None
        except ValueError:
            if not silent:
                messagebox.showerror("Spread", "Entrez un nombre (ex. 0.8) ou laissez vide.")
            return
        self.config(cursor="watch")
        self.status.config(text="  Récupération des données…")
        self.update_idletasks()
        try:
            provider = self._make_provider()
            result = run_analysis(self.cfg, provider, self.tf_var.get(), spread, self.replay_var.get())
        except MarketDataError as e:
            self._show_error(str(e), silent)
            return
        except Exception as e:  # erreur inattendue : affichée, jamais silencieuse
            self._show_error(f"Erreur inattendue : {e}", silent)
            return
        finally:
            self.config(cursor="")
        self._show(result)

    # ------------------------------------------------------------------ affichage
    def _show_error(self, message, silent=False):
        self.decision_box.config(text="ERREUR", bg=DECISION["ERREUR"])
        self.detail_title.config(text="Données indisponibles", fg="#f87171")
        self.detail.config(text=message, fg="#fca5a5")
        self.reasons.config(text="")
        self._render_checks([])
        self.status.config(text="  Aucune décision affichée.")
        if not silent:
            messagebox.showerror("Analyse impossible", message)

    def _show(self, res):
        d = res.decision
        self.decision_box.config(text=d.action, bg=DECISION.get(d.action, DECISION["NO TRADE"]))

        self.price_val.config(text=f"{res.price:.5f}")
        self.candle_val.config(text=res.last_time)
        delay_text, key = _format_delay(res.delay_min, res.market_open)
        self.delay_val.config(text=delay_text, fg=DELAY[key])
        self.source_val.config(text=f"{res.source} · {res.timeframe}")

        p = res.probabilities
        cond = p["conditional"]
        for key, _ in CLASSES:
            pct = cond["probs"][key] * 100 if cond["probs"] else 0.0
            self.prob_bars[key]["value"] = pct
            self.prob_pct[key].config(text=f"{pct:.0f} %" if cond["probs"] else "—")
        note = f"{p['condition_label']} · n = {cond['n']}"
        if p["low_sample"]:
            note += " · échantillon faible"
        self.prob_note.config(text=note)

        color = DECISION.get(d.action, DECISION["NO TRADE"])
        if d.plan:
            pl = d.plan
            self.detail_title.config(text=f"Signal {d.action}", fg=color)
            self.detail.config(fg=TEXT, text=(
                f"Entrée        {pl['entry']:.5f}\n"
                f"Stop loss     {pl['sl']:.5f}  ({pl['risk_pips']:.1f} pips)\n"
                f"Take profit   {pl['tp']:.5f}\n"
                f"Ratio net     {pl['rr_net']:.2f}\n"
                f"Taille        {pl['lots']:.2f} lot(s)\n"
                f"Invalidation  {pl['invalidation']}"))
        else:
            self.detail_title.config(text=f"En attente · {res.wait_state}", fg=TEXT)
            lines = [res.wait_text] + [f"• {w}" for w in d.waiting_for]
            self.detail.config(fg=MUTED, text="\n".join(lines))

        self.reasons.config(text="\n".join(f"• {r}" for r in d.reasons[:6]))
        self._render_checks(res.checks)

        title = f"{res.timeframe} · {d.action}"
        if d.action == "NO TRADE":
            title += f"  ·  en attente : {res.wait_state}"
        draw_price_chart(self.price_fig, res.tf_df, res.zones, res.focus_zones, res.price,
                         title=title, n_bars=self.cfg["chart"]["bars"],
                         events=self.calendar_events, pip_size=self.cfg["risk"]["pip_size"])
        self.price_canvas.draw()

        highlight = (res.when.hour, res.when.dayofweek) if res.when.dayofweek < 5 else None
        draw_heatmap(self.heat_fig, res.heatmap_mean,
                     title=f"Heatmap {res.timeframe} · horizon {p['horizon_minutes']} min",
                     highlight=highlight)
        self.heat_canvas.draw()
        stamp = pd.Timestamp.now(tz="UTC").strftime("%H:%M:%S")
        self.status.config(text=f"  Mis à jour à {stamp} UTC · aucun ordre envoyé · résultats passés ≠ garantie")


def run_gui(cfg, csv_path=None):
    EurusdApp(cfg, csv_path).mainloop()
