import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

from core.airfoil import get_profile, get_surfaces
from core.gcode import MachineConfig, generate_wing_gcode


# ── Yardimci: baslikli cerceve ──────────────────────────────────────────────
def _section(parent, title):
    frm = ttk.LabelFrame(parent, text=title, padding=6)
    frm.pack(fill="x", padx=6, pady=4)
    return frm


def _row(parent, label, default, row, unit="", width=8):
    ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=2)
    var = tk.StringVar(value=str(default))
    ttk.Entry(parent, textvariable=var, width=width).grid(row=row, column=1,
                                                           padx=4, pady=2)
    if unit:
        ttk.Label(parent, text=unit, foreground="#666").grid(row=row, column=2,
                                                              sticky="w")
    return var


# ── Ana uygulama ─────────────────────────────────────────────────────────────
class FoamCutterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SafeFoam — CNC Köpük Kesici")
        self.resizable(True, True)
        self.minsize(950, 600)

        self._build_ui()
        self.after(100, self._update_preview)

    # ── UI insa ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Ana iki sutun
        left = ttk.Frame(self, padding=4)
        left.pack(side="left", fill="y")

        right = ttk.Frame(self, padding=4)
        right.pack(side="left", fill="both", expand=True)

        self._build_params(left)
        self._build_preview(right)
        self._build_buttons(left)

    def _build_params(self, parent):
        # ── Kanat parametreleri ──
        wf = _section(parent, "Kanat Geometrisi")

        self.v_root_naca  = _row(wf, "Kök NACA",       "2412",  0)
        self.v_tip_naca   = _row(wf, "Uç NACA",        "2412",  1)
        self.v_root_chord = _row(wf, "Kök veter",       200,    2, "mm")
        self.v_tip_chord  = _row(wf, "Uç veter",        150,    3, "mm")
        self.v_wingspan   = _row(wf, "Açıklık (blok)",  600,    4, "mm")
        self.v_root_twist = _row(wf, "Kök twist",         0.0,  5, "°")
        self.v_tip_twist  = _row(wf, "Uç twist",         -2.0,  6, "°")
        self.v_npoints    = _row(wf, "Profil nokta",     100,   7)

        # ── Makine parametreleri ──
        mf = _section(parent, "Makine")

        self.v_feed    = _row(mf, "Kesim hızı",   300, 0, "mm/min")
        self.v_plunge  = _row(mf, "Yaklaşma",     100, 1, "mm/min")
        self.v_leadin  = _row(mf, "Lead-in",       15, 2, "mm")
        self.v_leadout = _row(mf, "Lead-out",      15, 3, "mm")

        mf2 = _section(parent, "Eksen Eşleştirme")
        self.v_ax1h = _row(mf2, "Kule 1 yatay", "X", 0, width=4)
        self.v_ax1v = _row(mf2, "Kule 1 dikey", "Y", 1, width=4)
        self.v_ax2h = _row(mf2, "Kule 2 yatay", "A", 2, width=4)
        self.v_ax2v = _row(mf2, "Kule 2 dikey", "B", 3, width=4)

    def _build_preview(self, parent):
        fig = Figure(figsize=(7, 5), dpi=96, facecolor="#1e1e1e")
        self._fig = fig

        self._ax_prof = fig.add_subplot(121)         # profil karsilastirma
        self._ax_wing = fig.add_subplot(122, projection="3d")  # 3d kanat

        self._canvas = FigureCanvasTkAgg(fig, master=parent)
        self._canvas.get_tk_widget().pack(fill="both", expand=True)

    def _build_buttons(self, parent):
        bf = ttk.Frame(parent, padding=6)
        bf.pack(fill="x", padx=6, pady=8)

        ttk.Button(bf, text="Önizle",
                   command=self._update_preview).pack(fill="x", pady=2)
        ttk.Button(bf, text="G-Code Üret & Kaydet",
                   command=self._generate_gcode).pack(fill="x", pady=2)

    # ── Parametrelerden degerleri oku ────────────────────────────────────────
    def _get_params(self):
        def f(v): return float(v.get())
        def i(v): return int(v.get())
        def s(v): return v.get().strip()
        return dict(
            root_naca  = s(self.v_root_naca),
            tip_naca   = s(self.v_tip_naca),
            root_chord = f(self.v_root_chord),
            tip_chord  = f(self.v_tip_chord),
            wingspan   = f(self.v_wingspan),
            root_twist = f(self.v_root_twist),
            tip_twist  = f(self.v_tip_twist),
            n_points   = i(self.v_npoints),
            feed       = f(self.v_feed),
            plunge     = f(self.v_plunge),
            lead_in    = f(self.v_leadin),
            lead_out   = f(self.v_leadout),
            ax1h = s(self.v_ax1h), ax1v = s(self.v_ax1v),
            ax2h = s(self.v_ax2h), ax2v = s(self.v_ax2v),
        )

    def _build_profiles(self, p):
        rx, ry = get_profile(p["root_naca"], p["root_chord"],
                             p["root_twist"], p["n_points"])
        tx, ty = get_profile(p["tip_naca"],  p["tip_chord"],
                             p["tip_twist"],  p["n_points"])
        return (rx, ry), (tx, ty)

    # ── Onizleme ─────────────────────────────────────────────────────────────
    def _update_preview(self):
        try:
            p = self._get_params()
            root_xy, tip_xy = self._build_profiles(p)
        except Exception as e:
            messagebox.showerror("Parametre hatasi", str(e))
            return

        rx, ry = root_xy
        tx, ty = tip_xy
        span   = p["wingspan"]
        n_pts  = p["n_points"]

        # ── Sol panel: profil karsilastirma (normalize) ──
        ax = self._ax_prof
        ax.cla()
        ax.set_facecolor("#2d2d2d")
        rc = p["root_chord"]
        tc = p["tip_chord"]
        ax.plot(rx / rc, ry / rc, color="#4fc3f7", lw=1.8,
                label=f"Kök  NACA {p['root_naca']}  ({rc:.0f} mm)")
        ax.plot(tx / tc, ty / tc, color="#ef5350", lw=1.8, linestyle="--",
                label=f"Uç   NACA {p['tip_naca']}  ({tc:.0f} mm)")
        ax.axhline(0, color="#555", lw=0.5)
        ax.set_aspect("equal")
        ax.set_xlabel("x/c", color="gray", fontsize=8)
        ax.set_ylabel("y/c", color="gray", fontsize=8)
        ax.set_title("Profil Kesitleri (normalize)", color="white", fontsize=9)
        ax.tick_params(colors="gray", labelsize=7)
        ax.legend(fontsize=7, facecolor="#2a2a2a", labelcolor="white",
                  loc="upper right")
        for sp in ax.spines.values():
            sp.set_color("#444")

        # ── Sag panel: 3D kanat yüzeyi ──
        ax3 = self._ax_wing
        ax3.cla()
        ax3.set_facecolor("#1a1a2e")

        # Ust ve alt yüzeyleri ayri al
        rxu, ryu, rxl, ryl = get_surfaces(
            p["root_naca"], p["root_chord"], p["root_twist"], n_pts)
        txu, tyu, txl, tyl = get_surfaces(
            p["tip_naca"],  p["tip_chord"],  p["tip_twist"],  n_pts)

        n_span  = 40
        n_chord = len(rxu)
        t_vals  = np.linspace(0, 1, n_span)

        # Her iki yüzey icin mesh grid olustur
        # Koordinat sistemi: X=veter, Y=kalınlık, Z=acıklık (dogal kanat bakisi)
        Xu = np.zeros((n_span, n_chord))
        Yu = np.zeros((n_span, n_chord))
        Zu = np.zeros((n_span, n_chord))
        Xl = np.zeros((n_span, n_chord))
        Yl = np.zeros((n_span, n_chord))
        Zl = np.zeros((n_span, n_chord))

        for i, t in enumerate(t_vals):
            Xu[i] = (1 - t) * rxu + t * txu
            Yu[i] = (1 - t) * ryu + t * tyu
            Zu[i] = t * span
            Xl[i] = (1 - t) * rxl + t * txl
            Yl[i] = (1 - t) * ryl + t * tyl
            Zl[i] = t * span

        # Yüzey çiz — X=veter, Z=açıklık, Y=kalınlık
        ax3.plot_surface(Xu, Zu, Yu, alpha=0.75, color="#4fc3f7",
                         linewidth=0, antialiased=True)
        ax3.plot_surface(Xl, Zl, Yl, alpha=0.75, color="#29b6f6",
                         linewidth=0, antialiased=True)

        # Kök ve uç profil konturları
        ax3.plot(rxu, np.zeros(n_chord), ryu, color="white", lw=1.2, zorder=5)
        ax3.plot(rxl, np.zeros(n_chord), ryl, color="white", lw=1.2, zorder=5)
        ax3.plot(txu, np.full(n_chord, span), tyu,
                 color="#ef5350", lw=1.5, zorder=5)
        ax3.plot(txl, np.full(n_chord, span), tyl,
                 color="#ef5350", lw=1.5, zorder=5)

        # LE ve TE kenar cizgileri
        ax3.plot([rxu[0],  txu[0]],  [0, span], [ryu[0],  tyu[0]],
                 color="#ffcc02", lw=1.2)   # ön kenar
        ax3.plot([rxu[-1], txu[-1]], [0, span], [ryu[-1], tyu[-1]],
                 color="#aaaaaa", lw=1.0)   # arka kenar

        ax3.set_xlabel("Veter (mm)", color="#aaa", fontsize=7, labelpad=2)
        ax3.set_ylabel("Açıklık (mm)", color="#aaa", fontsize=7, labelpad=2)
        ax3.set_zlabel("Kalınlık (mm)", color="#aaa", fontsize=7, labelpad=2)
        ax3.set_title("3D Kanat Yüzeyi", color="white", fontsize=9)
        ax3.tick_params(colors="#777", labelsize=6)
        ax3.xaxis.pane.set_facecolor("#12122a")
        ax3.yaxis.pane.set_facecolor("#12122a")
        ax3.zaxis.pane.set_facecolor("#12122a")
        ax3.xaxis.pane.set_alpha(0.5)
        ax3.yaxis.pane.set_alpha(0.5)
        ax3.zaxis.pane.set_alpha(0.5)
        # Dogal kanat bakis acisi: biraz yukari ve ondan bak
        ax3.view_init(elev=25, azim=-60)

        self._fig.tight_layout()
        self._canvas.draw()

    # ── G-Code uret ──────────────────────────────────────────────────────────
    def _generate_gcode(self):
        try:
            p = self._get_params()
            root_xy, tip_xy = self._build_profiles(p)
        except Exception as e:
            messagebox.showerror("Hata", str(e))
            return

        mc = MachineConfig(
            ax1_h=p["ax1h"], ax1_v=p["ax1v"],
            ax2_h=p["ax2h"], ax2_v=p["ax2v"],
            feed_rate=p["feed"], plunge_rate=p["plunge"],
            lead_in=p["lead_in"], lead_out=p["lead_out"],
        )

        gcode = generate_wing_gcode(root_xy, tip_xy, mc)

        path = filedialog.asksaveasfilename(
            defaultextension=".nc",
            filetypes=[("G-Code", "*.nc *.gcode *.txt"), ("Tümü", "*.*")],
            initialfile="kanat.nc",
            title="G-Code Kaydet",
        )
        if not path:
            return

        with open(path, "w", encoding="utf-8") as f:
            f.write(gcode)

        messagebox.showinfo("Kaydedildi",
                            f"G-Code kaydedildi:\n{path}\n\n"
                            f"{gcode.count(chr(10))+1} satir")
