"""
SimPlayer — Adim adim kesim simülasyonu widget'i.
Kopuk blok dikdortgeni uzerinde tel yolu animasyonu.
"""
import tkinter as tk
from tkinter import ttk
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.patches import FancyArrowPatch, Polygon as MplPolygon, Rectangle


FOAM_COLOR   = "#8B7355"
FOAM_EDGE    = "#C8A97E"
CUT_COLOR    = "#1a3a5c"
TRACE_COLOR  = "#FF6B35"
WIRE_COLOR   = "#00FF99"
REMAIN_COLOR = "#6B9E5E"
BG           = "#0f0f1e"
GRID_COLOR   = "#1e1e3a"


class SimPlayer(ttk.Frame):
    """
    Embedded simulation widget.
    set_data() ile profil ve kopuk siniri verilir,
    play/step/scrub ile animasyon kontrol edilir.
    """

    def __init__(self, parent, title="Kesim Simülasyonu"):
        super().__init__(parent)
        self._title   = title
        self._px      = None
        self._py      = None
        self._bounds  = None   # (h0, h1, v0, v1)
        self._step    = 0
        self._n       = 0
        self._playing = False
        self._after_id = None

        self._build()

    # ── Public API ───────────────────────────────────────────────────────────

    def set_data(self, profile_x, profile_y, bounds):
        """
        profile_x, profile_y : kesim yolu koordinatlari (mm)
        bounds               : (h_min, h_max, v_min, v_max) kopuk blok
        """
        # Profili 400 adima yeniden ornekle — duzgun animasyon icin
        n_raw = len(profile_x)
        t_old = np.linspace(0, 1, n_raw)
        t_new = np.linspace(0, 1, 400)
        self._px = np.interp(t_new, t_old, profile_x)
        self._py = np.interp(t_new, t_old, profile_y)
        self._bounds = bounds
        self._n = len(self._px)
        self._step = 0
        self._playing = False
        self._play_btn.config(text="▶  Oynat")
        self._slider.config(to=self._n - 1)
        self._slider.set(0)
        self._draw(0)

    def clear(self):
        self._px = None
        ax = self._ax
        ax.cla()
        ax.set_facecolor(BG)
        ax.set_title(self._title, color="white", fontsize=9)
        self._canvas.draw()

    # ── UI insa ──────────────────────────────────────────────────────────────

    def _build(self):
        # Matplotlib canvas
        fig = Figure(figsize=(5.5, 4), dpi=96, facecolor=BG)
        self._fig = fig
        self._ax  = fig.add_subplot(111)
        self._ax.set_facecolor(BG)

        self._canvas = FigureCanvasTkAgg(fig, master=self)
        self._canvas.get_tk_widget().pack(fill="both", expand=True)

        # Kontroller
        ctrl = ttk.Frame(self, padding=(4, 2))
        ctrl.pack(fill="x")

        btn_cfg = dict(width=4)
        ttk.Button(ctrl, text="⏮",  command=self._goto_start, **btn_cfg).pack(side="left", padx=1)
        ttk.Button(ctrl, text="◀",  command=self._step_back,  **btn_cfg).pack(side="left", padx=1)
        self._play_btn = ttk.Button(ctrl, text="▶  Oynat",
                                    command=self._toggle_play, width=10)
        self._play_btn.pack(side="left", padx=2)
        ttk.Button(ctrl, text="▶",  command=self._step_fwd,   **btn_cfg).pack(side="left", padx=1)
        ttk.Button(ctrl, text="⏭",  command=self._goto_end,   **btn_cfg).pack(side="left", padx=1)

        self._lbl = ttk.Label(ctrl, text="Adım: 0 / 0", width=14)
        self._lbl.pack(side="left", padx=8)

        # Hiz
        ttk.Label(ctrl, text="Hız:").pack(side="right", padx=2)
        self._speed_var = tk.StringVar(value="Hızlı")
        ttk.Combobox(ctrl, textvariable=self._speed_var,
                     values=["Yavaş", "Normal", "Hızlı", "Çok Hızlı"],
                     width=10, state="readonly").pack(side="right", padx=4)

        # Slider
        self._slider = ttk.Scale(self, from_=0, to=100,
                                 orient="horizontal",
                                 command=self._on_slider)
        self._slider.pack(fill="x", padx=8, pady=(2, 4))

    # ── Cizim ────────────────────────────────────────────────────────────────

    def _draw(self, step: int):
        if self._px is None:
            return

        px   = self._px
        py   = self._py
        n    = self._n
        step = max(0, min(step, n - 1))
        bx0, bx1, by0, by1 = self._bounds

        # Axes'i yeniden olustur (cla() bazi matplotlib surumlerinde hatali)
        self._fig.clear()
        ax = self._fig.add_subplot(111)
        self._ax = ax
        ax.set_facecolor(BG)
        ax.set_aspect("equal")

        # ── Kesimlenmemis kopuk blok ──
        foam = Rectangle((bx0, by0), bx1 - bx0, by1 - by0,
                          facecolor=FOAM_COLOR, alpha=0.45,
                          edgecolor=FOAM_EDGE, lw=1.5, zorder=1)
        ax.add_patch(foam)

        # ── Tam profil yolu (soluk) ──
        ax.plot(px, py, color="#2a4060", lw=1.2, zorder=2)

        if step >= n - 1:
            # ── Kesim tamamlandi: kalan kopuk formu goster ──
            verts = np.column_stack([px, py])
            remain = MplPolygon(verts, closed=True,
                                facecolor=REMAIN_COLOR, alpha=0.65,
                                edgecolor="#90D080", lw=2.0, zorder=3)
            ax.add_patch(remain)
            ax.set_title(f"{self._title}  ✓  Tamamlandı",
                         color="#90D080", fontsize=9, pad=4)
        else:
            # ── Gecilen iz ──
            if step > 0:
                ax.plot(px[:step + 1], py[:step + 1],
                        color=TRACE_COLOR, lw=2.0, alpha=0.85, zorder=4)

            # ── Tel konumu (nokta + dikey kesim cizgisi) ──
            wx, wy = px[step], py[step]
            ax.plot(wx, wy, "o", color=WIRE_COLOR,
                    markersize=9, zorder=6)
            ax.plot([wx, wx], [by0, by1],
                    color=WIRE_COLOR, lw=1.0, alpha=0.35,
                    linestyle="--", zorder=5)

            # ── Ilerlemis kesim alani (kopuk disinda kalan) ──
            # Basit gosterim: gecilen pathi cok hafif doldur
            if step > 1:
                ax.fill(px[:step + 1], py[:step + 1],
                        color=CUT_COLOR, alpha=0.25, zorder=3)

            ax.set_title(self._title, color="white", fontsize=9, pad=4)

        # ── Eksen stilleri ──
        margin = max(bx1 - bx0, by1 - by0) * 0.12
        ax.set_xlim(bx0 - margin, bx1 + margin)
        ax.set_ylim(by0 - margin, by1 + margin)
        ax.set_xlabel("mm", color="#555", fontsize=7)
        ax.tick_params(colors="#444", labelsize=6)
        for sp in ax.spines.values():
            sp.set_color("#2a2a4a")

        self._lbl.config(text=f"Adım: {step} / {n - 1}")
        self._slider.set(step)
        self._canvas.draw()

    # ── Kontrol aksiyonlari ──────────────────────────────────────────────────

    _SPEEDS = {"Yavaş": 80, "Normal": 25, "Hızlı": 8, "Çok Hızlı": 1}

    def _toggle_play(self):
        if self._px is None:
            return
        if self._playing:
            self._playing = False
            self._play_btn.config(text="▶  Oynat")
            if self._after_id:
                self.after_cancel(self._after_id)
        else:
            if self._step >= self._n - 1:
                self._step = 0
            self._playing = True
            self._play_btn.config(text="⏸  Durdur")
            self._play_loop()

    def _play_loop(self):
        if not self._playing:
            return
        self._step += 1
        self._draw(self._step)
        if self._step >= self._n - 1:
            self._playing = False
            self._play_btn.config(text="▶  Oynat")
            return
        delay = self._SPEEDS.get(self._speed_var.get(), 8)
        self._after_id = self.after(delay, self._play_loop)

    def _step_fwd(self):
        if self._px is not None and self._step < self._n - 1:
            self._step += 1
            self._draw(self._step)

    def _step_back(self):
        if self._px is not None and self._step > 0:
            self._step -= 1
            self._draw(self._step)

    def _goto_start(self):
        if self._px is not None:
            self._playing = False
            self._play_btn.config(text="▶  Oynat")
            self._step = 0
            self._draw(0)

    def _goto_end(self):
        if self._px is not None:
            self._playing = False
            self._play_btn.config(text="▶  Oynat")
            self._step = self._n - 1
            self._draw(self._n - 1)

    def _on_slider(self, val):
        if self._px is None:
            return
        new_step = int(float(val))
        if new_step != self._step:
            self._step = new_step
            self._draw(self._step)
