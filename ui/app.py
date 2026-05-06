"""
SafeFoam v4.0 — PrusaSlicer tarzı tek ekran arayuz
Sol: ayarlar | Sag ust: 3D model + kesim duzlemi | Sag alt: 2D profil sim
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D          # noqa: F401
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from core.mesh_import import (load_mesh, extract_profile, extract_section_profile, foam_bounds,
                               mesh_info, auto_axes)
from core.gcode import MachineConfig, generate_planform_gcode
from core.cut_path import insert_hole_traversal
from ui.sim_player import SimPlayer


# ── Yardimcilar ──────────────────────────────────────────────────────────────

def _lbl(parent, text, **kw):
    return ttk.Label(parent, text=text, **kw)

def _entry(parent, var, w=7):
    return ttk.Entry(parent, textvariable=var, width=w)

def _row(parent, label, default, row, col=0, unit="", w=7):
    _lbl(parent, label).grid(row=row, column=col,   sticky="w", pady=1, padx=(0, 3))
    var = tk.StringVar(value=str(default))
    _entry(parent, var, w).grid(row=row, column=col+1, pady=1)
    if unit:
        _lbl(parent, unit, foreground="#777").grid(row=row, column=col+2, sticky="w")
    return var

def _section(parent, title):
    f = ttk.LabelFrame(parent, text=title, padding=(6, 4))
    f.pack(fill="x", padx=5, pady=2)
    return f


# ════════════════════════════════════════════════════════════════════════════
#  Ana Uygulama — tek ekran, tab yok
# ════════════════════════════════════════════════════════════════════════════

class FoamCutterApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("SafeFoam v4 — CNC Kopuk Kesici")
        self.minsize(1280, 720)
        self.resizable(True, True)

        self._mesh    = None
        self._profile = (None, None)
        self._bounds  = None
        self._holes_autofit_done = False
        self._view_elev = 24
        self._view_azim = -58
        self._cube_ax = None
        self._cube_drag = None
        self._pan_drag = None
        self._view_radius = None
        self._view_center = None
        self._model_color = "#2374B8"
        self._edge_color = "#111820"
        self._lang = "tr"
        self._ui = {}

        self._set_app_icon()
        self._build()

    def _set_app_icon(self):
        ico = Path(__file__).resolve().parents[1] / "app.ico"
        if ico.exists():
            try:
                self.iconbitmap(str(ico))
            except tk.TclError:
                pass

    # ── Layout ───────────────────────────────────────────────────────────────

    def _build(self):
        self._build_menu()

        # Baslik
        bar = tk.Frame(self, bg="#1a3a6a", height=34)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        self._ui["brand"] = tk.Label(bar, text="  SafeFoam",
                                      bg="#1a3a6a", fg="white",
                                      font=("Segoe UI", 11, "bold"))
        self._ui["brand"].pack(side="left", padx=8)
        self._ui["version"] = tk.Label(bar, text="v4.0  CNC Kopuk Kesici",
                                       bg="#1a3a6a", fg="#ffa040",
                                       font=("Segoe UI", 9, "bold"))
        self._ui["version"].pack(side="left")
        self._ui["flow"] = tk.Label(bar,
                                    text="  Dosya ac -> eksen sec -> profil -> G-code",
                                    bg="#1a3a6a", fg="#aabbcc",
                                    font=("Segoe UI", 8))
        self._ui["flow"].pack(side="left", padx=10)

        # Icerik alani
        content = ttk.Frame(self)
        content.pack(fill="both", expand=True)

        # Sol panel (sabit genislik, kaydirma destekli)
        self._build_left(content)

        ttk.Separator(content, orient="vertical").pack(side="left", fill="y")

        # Sag alan: 3D ust (esnek) + SimPlayer alt (sabit yukseklik)
        right = ttk.Frame(content)
        right.pack(side="left", fill="both", expand=True, padx=3, pady=3)

        sim_frm = ttk.Frame(right, height=390)
        sim_frm.pack(side="bottom", fill="x")
        sim_frm.pack_propagate(False)
        self._sim = SimPlayer(sim_frm, title="Kesim Profili Simulasyonu")
        self._sim.pack(fill="both", expand=True)

        ttk.Separator(right, orient="horizontal").pack(side="bottom", fill="x")

        # 3D view — kalan alani doldur
        view3d_frm = ttk.Frame(right)
        view3d_frm.pack(side="top", fill="both", expand=True)
        self._build_3d_view(view3d_frm)
        self._apply_language()

    def _build_menu(self):
        menu = tk.Menu(self)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="Open...", command=self._open_file)
        file_menu.add_command(label="Save G-Code...", command=self._save_gcode)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.destroy)

        view_menu = tk.Menu(menu, tearoff=False)
        view_menu.add_command(label="Fit Model", command=self._fit_view_and_redraw)
        view_menu.add_separator()
        view_menu.add_command(label="Front", command=lambda: self._set_view("FRONT"))
        view_menu.add_command(label="Back", command=lambda: self._set_view("BACK"))
        view_menu.add_command(label="Left", command=lambda: self._set_view("LEFT"))
        view_menu.add_command(label="Right", command=lambda: self._set_view("RIGHT"))
        view_menu.add_command(label="Top", command=lambda: self._set_view("TOP"))
        view_menu.add_command(label="Bottom", command=lambda: self._set_view("BOTTOM"))
        view_menu.add_separator()
        view_menu.add_command(label="Isometric", command=lambda: self._set_view("ISO"))

        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label="About SafeFoam", command=self._show_about)

        menu.add_cascade(label="File", menu=file_menu)
        menu.add_cascade(label="View", menu=view_menu)
        menu.add_cascade(label="About", menu=help_menu)
        self.config(menu=menu)

    # ── Sol panel ────────────────────────────────────────────────────────────

    def _build_left(self, parent):
        outer = ttk.Frame(parent, width=340)
        outer.pack(side="left", fill="y")
        outer.pack_propagate(False)

        # Canvas + scrollbar icin kap
        cv = tk.Canvas(outer, width=338, highlightthickness=0,
                       bg=self.cget("bg"))
        sb = ttk.Scrollbar(outer, orient="vertical", command=cv.yview)
        cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        cv.pack(side="left", fill="both", expand=True)

        inner = ttk.Frame(cv)
        win_id = cv.create_window((0, 0), window=inner, anchor="nw", width=326)
        inner.bind("<Configure>",
                   lambda e: cv.configure(scrollregion=cv.bbox("all")))
        # Fare tekerlegini sol panele sinirla
        inner.bind("<Enter>", lambda e: cv.bind_all(
            "<MouseWheel>",
            lambda ev: cv.yview_scroll(-1*(ev.delta//120), "units")))
        inner.bind("<Leave>", lambda e: cv.unbind_all("<MouseWheel>"))

        self._build_file_section(inner)
        self._build_settings_section(inner)
        self._build_axis_section(inner)
        self._build_holes_section(inner)
        self._build_machine_section(inner)

        ttk.Separator(inner).pack(fill="x", padx=5, pady=4)
        self._ui["preview_btn"] = ttk.Button(inner, text="Önizle / Slice",
                                             command=self._refresh_profile)
        self._ui["preview_btn"].pack(fill="x", padx=5, pady=2)
        self._ui["save_btn"] = ttk.Button(inner, text="G-Code Uret & Kaydet",
                                          command=self._save_gcode)
        self._ui["save_btn"].pack(fill="x", padx=5, pady=2)

    def _build_file_section(self, parent):
        ff = _section(parent, "3D Model")
        self._ui["file_section"] = ff
        self._ui["open_btn"] = ttk.Button(ff, text="Dosya Ac...  (STL / OBJ)",
                                          command=self._open_file)
        self._ui["open_btn"].pack(fill="x", pady=2)
        self._file_lbl = ttk.Label(ff, text="Dosya secilmedi",
                                   foreground="#888", wraplength=300)
        self._file_lbl.pack(fill="x")

        sf = ttk.Frame(ff)
        sf.pack(fill="x", pady=(4, 0))
        self._ui["scale_lbl"] = _lbl(sf, "Olcek:")
        self._ui["scale_lbl"].grid(row=0, column=0, sticky="w")
        self._v_scale = tk.StringVar(value="1.0")
        _entry(sf, self._v_scale, 5).grid(row=0, column=1, padx=3)
        self._ui["scale_btn"] = ttk.Button(sf, text="x Uygula", width=8,
                                           command=self._apply_scale)
        self._ui["scale_btn"].grid(row=0, column=2)

        self._info_lbl = ttk.Label(ff, text="", foreground="#aaa",
                                   justify="left", font=("Segoe UI", 8))
        self._info_lbl.pack(anchor="w", pady=(4, 0))

        self._v_fast3d = tk.BooleanVar(value=True)
        self._ui["fast3d_chk"] = ttk.Checkbutton(ff, text="Hizli 3D gorunum",
                                                 variable=self._v_fast3d,
                                                 command=self._draw_3d_mesh)
        self._ui["fast3d_chk"].pack(anchor="w", pady=(4, 0))

    def _build_settings_section(self, parent):
        sf = _section(parent, "Ayarlar / Settings")
        self._ui["settings_section"] = sf
        self._ui["lang_lbl"] = _lbl(sf, "Dil / Language:")
        self._ui["lang_lbl"].grid(row=0, column=0, sticky="w")
        self._v_lang = tk.StringVar(value="Türkçe")
        cb = ttk.Combobox(sf, textvariable=self._v_lang,
                          values=["Türkçe", "English"],
                          width=12, state="readonly")
        cb.grid(row=0, column=1, sticky="w", padx=4)
        cb.bind("<<ComboboxSelected>>", self._on_language_change)

    def _build_axis_section(self, parent):
        af = _section(parent, "Kesilecek Eksen / 2D Profil")
        self._ui["axis_section"] = af

        self._v_axis = tk.StringVar(value="X")
        self._axis_rbs = {}

        for axis in ("X", "Y", "Z"):
            rb = ttk.Radiobutton(af, text=f"  {axis}  ekseni boyunca",
                                 value=axis, variable=self._v_axis,
                                 command=self._on_axis_change)
            rb.pack(anchor="w", pady=1)
            self._axis_rbs[axis] = rb

        self._ui["axis_preview_btn"] = ttk.Button(
            af, text="Secili Ekseni Kes / Onizle", command=self._refresh_profile)
        self._ui["axis_preview_btn"].pack(fill="x", pady=(4, 0))

        self._axis_hint = ttk.Label(af, text="Model bekleniyor...",
                                    foreground="#555",
                                    font=("Segoe UI", 7, "italic"),
                                    wraplength=300)
        self._axis_hint.pack(anchor="w", pady=(3, 0))

    def _build_holes_section(self, parent):
        hf = _section(parent, "Karbon Tup Delikleri")
        self._ui["holes_section"] = hf

        self._v_holes_en = tk.BooleanVar(value=False)
        self._ui["holes_chk"] = ttk.Checkbutton(hf, text="Delik gecisi aktif",
                                                variable=self._v_holes_en)
        self._ui["holes_chk"].grid(row=0, column=0, columnspan=6, sticky="w")

        for col, txt in enumerate(["", "  HX", " HY", " R", ""]):
            ttk.Label(hf, text=txt, foreground="#666",
                      font=("Segoe UI", 7)).grid(row=1, column=col)

        defaults = [
            (True,  -50., -8., 6.),
            (True,    0., -8., 6.),
            (False,  45., -6., 5.),
        ]
        self._hole_rows = []
        for i, (en, hx, hy, hr) in enumerate(defaults):
            r = i + 2
            v_en = tk.BooleanVar(value=en)
            v_hx = tk.StringVar(value=str(hx))
            v_hy = tk.StringVar(value=str(hy))
            v_hr = tk.StringVar(value=str(hr))
            ttk.Checkbutton(hf, variable=v_en).grid(row=r, column=0)
            ttk.Entry(hf, textvariable=v_hx, width=5).grid(row=r, column=1, padx=1)
            ttk.Entry(hf, textvariable=v_hy, width=5).grid(row=r, column=2, padx=1)
            ttk.Entry(hf, textvariable=v_hr, width=4).grid(row=r, column=3, padx=1)
            ttk.Label(hf, text=f"D{i+1}", foreground="#aaa",
                      font=("Segoe UI", 7)).grid(row=r, column=4, padx=2)
            self._hole_rows.append((v_en, v_hx, v_hy, v_hr))

        self._ui["holes_apply_btn"] = ttk.Button(hf, text="Uygula",
                                                 command=self._refresh_profile)
        self._ui["holes_apply_btn"].grid(
            row=len(defaults)+2, column=0, columnspan=5,
            sticky="ew", pady=(4, 0))

    def _build_machine_section(self, parent):
        mf = _section(parent, "Makine Ayarlari")
        self._ui["machine_section"] = mf

        self._v_feed   = _row(mf, "Kesim hizi:", 300, 0, unit="mm/m", w=7)
        self._v_plunge = _row(mf, "Yaklasma:",   100, 1, unit="mm/m", w=7)
        self._v_leadin = _row(mf, "Lead-in:",     15, 2, unit="mm",   w=7)

        ttk.Separator(mf, orient="horizontal").grid(
            row=3, column=0, columnspan=6, sticky="ew", pady=4)

        self._v_ax1h = _row(mf, "K1 yatay:", "X", 4, col=0, unit="", w=4)
        self._v_ax1v = _row(mf, "K1 dikey:", "Y", 4, col=3, unit="", w=4)
        self._v_ax2h = _row(mf, "K2 yatay:", "A", 5, col=0, unit="", w=4)
        self._v_ax2v = _row(mf, "K2 dikey:", "B", 5, col=3, unit="", w=4)

    # ── 3D Goruntu ───────────────────────────────────────────────────────────

    def _build_3d_view(self, parent):
        fig = Figure(figsize=(7, 4.5), dpi=96, facecolor="#e8e8e8")
        self._fig3d    = fig
        self._ax3d     = fig.add_subplot(111, projection="3d")
        self._canvas3d = FigureCanvasTkAgg(fig, master=parent)
        self._canvas3d.get_tk_widget().pack(fill="both", expand=True)
        self._canvas3d.mpl_connect("scroll_event", self._on_3d_scroll)
        self._canvas3d.mpl_connect("button_press_event", self._on_3d_press)
        self._canvas3d.mpl_connect("motion_notify_event", self._on_3d_motion)
        self._canvas3d.mpl_connect("button_release_event", self._remember_3d_view)
        self._canvas3d.mpl_connect("pick_event", self._on_cube_pick)
        self._draw_3d_empty()

    def _draw_3d_empty(self):
        self._fig3d.clear()
        ax = self._fig3d.add_subplot(111, projection="3d")
        self._ax3d = ax
        ax.set_position([0.02, 0.02, 0.96, 0.92])
        ax.set_facecolor("#e8e8e8")
        ax.set_title("STL / OBJ dosyasi acmak icin 'Dosya Ac' butonunu kullanin",
                     color="#555", fontsize=9)
        for p in [ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane]:
            p.set_facecolor("#d8d8d8"); p.set_alpha(1.0)
        self._canvas3d.draw()

    def _draw_3d_mesh(self):
        if self._mesh is None:
            return

        self._fig3d.clear()
        ax = self._fig3d.add_subplot(111, projection="3d")
        self._ax3d = ax
        ax.set_position([0.02, 0.02, 0.96, 0.92])
        ax.set_facecolor("#e8e8e8")

        m = self._mesh
        verts = np.asarray(m.vertices)
        faces = np.asarray(m.faces)

        fast = self._v_fast3d.get()

        # Yuzey cizimi: wireframe bazi STL'lerde bos gorunebiliyor.
        if len(faces):
            target_faces = 12000 if fast else 40000
            step_faces = 1 if len(faces) <= target_faces else max(1, len(faces) // target_faces)
            tris = verts[faces[::step_faces]]
            mesh_poly = Poly3DCollection(
                tris,
                facecolor=self._model_color,
                edgecolor="none",
                linewidths=0.0,
                alpha=0.98,
            )
            ax.add_collection3d(mesh_poly)

        edges = getattr(m, "edges_unique", [])
        if len(edges):
            target_edges = 1200 if fast else 5000
            step_edges = max(1, len(edges) // target_edges)
            ex, ey, ez = [], [], []
            for e in edges[::step_edges]:
                ex += [verts[e[0], 0], verts[e[1], 0], np.nan]
                ey += [verts[e[0], 1], verts[e[1], 1], np.nan]
                ez += [verts[e[0], 2], verts[e[1], 2], np.nan]
            ax.plot(
                ex, ey, ez,
                color=self._edge_color,
                lw=0.28 if fast else 0.42,
                alpha=0.22 if fast else 0.52,
            )

        b = m.bounds

        # Kesim duzlemi — limitler ayarlandiktan SONRA ciz
        self._draw_cutting_plane(ax, m.bounds, self._v_axis.get())
        self._draw_model_brackets(ax, b)
        self._fit_3d_model(ax, b, reset=self._view_center is None)

        ax.set_xlabel("X (mm)", color="#333", fontsize=7)
        ax.set_ylabel("Y (mm)", color="#333", fontsize=7)
        ax.set_zlabel("Z (mm)", color="#333", fontsize=7)
        ax.tick_params(colors="#444", labelsize=6)

        plane_name = self._axis_plane_names()
        ax.set_title(
            f"Tel ekseni: {self._v_axis.get()}  —  "
            f"{plane_name.get(self._v_axis.get(), '')}",
            color="#1a3a6a", fontsize=9, fontweight="bold")

        for p in [ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane]:
            p.set_facecolor("#d8d8d8"); p.set_alpha(1.0)
        ax.grid(False if fast else True, color="#c7c7c7")
        ax.view_init(elev=self._view_elev, azim=self._view_azim)
        try:
            ax.set_proj_type("persp", focal_length=0.8)
        except TypeError:
            ax.set_proj_type("persp")
        self._draw_axis_cube()
        self._canvas3d.draw()

    def _fit_3d_model(self, ax, bounds, margin=0.28, reset=False):
        if reset or self._view_center is None or self._view_radius is None:
            center = bounds.mean(axis=0)
            extents = bounds[1] - bounds[0]
            self._view_center = center
            self._view_radius = max(float(np.max(extents)) * (0.5 + margin), 1.0)
        center = self._view_center
        radius = self._view_radius
        ax.set_xlim(center[0] - radius, center[0] + radius)
        ax.set_ylim(center[1] - radius, center[1] + radius)
        ax.set_zlim(center[2] - radius, center[2] + radius)
        try:
            ax.set_box_aspect([1, 1, 1], zoom=1.18)
        except TypeError:
            ax.set_box_aspect([1, 1, 1])

    def _draw_model_brackets(self, ax, bounds):
        lo, hi = bounds
        size = hi - lo
        seg = max(float(np.max(size)) * 0.08, 2.0)
        corners = [
            (lo[0], lo[1], lo[2]), (lo[0], lo[1], hi[2]),
            (lo[0], hi[1], lo[2]), (lo[0], hi[1], hi[2]),
            (hi[0], lo[1], lo[2]), (hi[0], lo[1], hi[2]),
            (hi[0], hi[1], lo[2]), (hi[0], hi[1], hi[2]),
        ]
        for x, y, z in corners:
            sx = 1 if x == lo[0] else -1
            sy = 1 if y == lo[1] else -1
            sz = 1 if z == lo[2] else -1
            ax.plot([x, x + sx * seg], [y, y], [z, z],
                    color="white", lw=1.7, alpha=0.95, zorder=10)
            ax.plot([x, x], [y, y + sy * seg], [z, z],
                    color="white", lw=1.7, alpha=0.95, zorder=10)
            ax.plot([x, x], [y, y], [z, z + sz * seg],
                    color="white", lw=1.7, alpha=0.95, zorder=10)

    def _fit_view_and_redraw(self):
        if self._mesh is None:
            return
        self._view_center = None
        self._view_radius = None
        self._draw_3d_mesh()

    def _set_view(self, view_name):
        presets = {
            "X": (0, -90),
            "Y": (0, 0),
            "Z": (90, -90),
            "RIGHT": (0, -90),
            "LEFT": (0, 90),
            "FRONT": (0, -180),
            "BACK": (0, 0),
            "TOP": (90, -90),
            "BOTTOM": (-90, -90),
            "ISO": (24, -58),
        }
        if view_name not in presets:
            return
        self._view_elev, self._view_azim = presets[view_name]
        self._fit_view_and_redraw()

    def _show_about(self):
        win = tk.Toplevel(self)
        win.title("About SafeFoam")
        win.resizable(False, False)
        win.transient(self)
        try:
            ico = Path(__file__).resolve().parents[1] / "app.ico"
            if ico.exists():
                win.iconbitmap(str(ico))
        except tk.TclError:
            pass

        root = ttk.Frame(win, padding=18)
        root.pack(fill="both", expand=True)

        logo = tk.Canvas(root, width=132, height=132, bg="#f3f5f7",
                         highlightthickness=1, highlightbackground="#c7d0d8")
        logo.grid(row=0, column=0, rowspan=2, sticky="n", padx=(0, 18))
        self._draw_about_logo(logo)

        ttk.Label(root, text="SafeFoam v4",
                  font=("Segoe UI", 16, "bold")).grid(row=0, column=1, sticky="w")
        text = (
            "CNC hot wire foam cutter CAM\n"
            "for wing profiles and foam parts.\n\n"
            "Developer: Captain21\n"
            "Email: ihsanburakgoksin@gmail.com\n\n"
            "Workflow\n"
            "- Load STL / OBJ\n"
            "- Choose cut axis\n"
            "- Preview hot-wire path\n"
            "- Generate GRBL-compatible G-code\n\n"
            "Reference: 4 Axis CNC Hotwire Foam Cutter,\n"
            "RAMPS 1.4 and GRBL hot-wire setups."
        )
        ttk.Label(root, text=text, justify="left",
                  font=("Segoe UI", 9)).grid(row=1, column=1, sticky="w")
        ttk.Button(root, text="OK", command=win.destroy).grid(
            row=2, column=1, sticky="e", pady=(12, 0))

    def _draw_about_logo(self, canvas):
        # Foam block
        canvas.create_polygon(
            26, 82, 92, 92, 108, 52, 42, 42,
            fill="#e7d5b7", outline="#8b7658", width=2)
        canvas.create_polygon(
            42, 42, 108, 52, 96, 34, 32, 25,
            fill="#f0dfc0", outline="#8b7658", width=2)
        canvas.create_polygon(
            92, 92, 108, 52, 96, 34, 80, 73,
            fill="#cbb38c", outline="#8b7658", width=2)

        # Wing/profile cut
        canvas.create_polygon(
            38, 65, 55, 54, 92, 60, 104, 69,
            91, 73, 55, 72,
            fill="#2374B8", outline="#0d2740", width=2)
        canvas.create_oval(63, 62, 74, 70, fill="#f3f5f7",
                           outline="#0d2740", width=1)
        canvas.create_oval(83, 63, 91, 70, fill="#f3f5f7",
                           outline="#0d2740", width=1)

        # Hot wire and towers
        canvas.create_line(20, 22, 20, 103, fill="#1e2a32", width=4)
        canvas.create_line(114, 18, 114, 104, fill="#1e2a32", width=4)
        canvas.create_line(20, 63, 114, 63, fill="#ff6b35", width=3)
        canvas.create_oval(16, 58, 24, 66, fill="#ff9b63", outline="#b3471e")
        canvas.create_oval(110, 58, 118, 66, fill="#ff9b63", outline="#b3471e")

        canvas.create_text(66, 113, text="SafeFoam", fill="#1a3a6a",
                           font=("Segoe UI", 11, "bold"))

    def _draw_axis_cube(self):
        """Bambu/Prusa tarzi kucuk yon kupu."""
        if self._cube_ax is not None and self._cube_ax in self._fig3d.axes:
            self._cube_ax.remove()

        cube_ax = self._fig3d.add_axes([0.035, 0.08, 0.13, 0.20],
                                       projection="3d")
        self._cube_ax = cube_ax
        cube_ax.set_navigate(False)
        cube_ax.set_facecolor((0.0, 0.0, 0.0, 0.0))
        cube_ax.view_init(elev=self._view_elev, azim=self._view_azim)
        cube_ax.set_axis_off()

        r = np.array([-0.5, 0.5])
        faces = [
            [(-.5, -.5, .5), (.5, -.5, .5), (.5, .5, .5), (-.5, .5, .5)],
            [(-.5, -.5, -.5), (-.5, .5, -.5), (.5, .5, -.5), (.5, -.5, -.5)],
            [(-.5, .5, -.5), (-.5, .5, .5), (.5, .5, .5), (.5, .5, -.5)],
            [(-.5, -.5, -.5), (.5, -.5, -.5), (.5, -.5, .5), (-.5, -.5, .5)],
            [(.5, -.5, -.5), (.5, .5, -.5), (.5, .5, .5), (.5, -.5, .5)],
            [(-.5, -.5, -.5), (-.5, -.5, .5), (-.5, .5, .5), (-.5, .5, -.5)],
        ]
        cube = Poly3DCollection(
            faces,
            facecolors=["#f5f5f0", "#d8dde2", "#eef1f4", "#e5e9ee", "#f9fafb", "#cfd6dd"],
            edgecolors="#6d7882",
            linewidths=0.8,
            alpha=0.9,
        )
        cube_ax.add_collection3d(cube)

        cube_ax.quiver(0, 0, 0, 0.9, 0, 0, color="#d9534f", lw=1.5)
        cube_ax.quiver(0, 0, 0, 0, 0.9, 0, color="#2aa84a", lw=1.5)
        cube_ax.quiver(0, 0, 0, 0, 0, 0.9, color="#4058d8", lw=1.5)
        for axis, label, x, y, z, color in (
            ("X", "X", 1.05, 0, 0, "#d9534f"),
            ("Y", "Y", 0, 1.05, 0, "#2aa84a"),
            ("Z", "Z", 0, 0, 1.05, "#4058d8"),
            ("RIGHT", "RIGHT", 0.52, 0, 0, "#29323a"),
            ("LEFT", "LEFT", -0.76, 0, 0, "#29323a"),
            ("FRONT", "FRONT", 0, 0.62, 0, "#29323a"),
            ("BACK", "BACK", 0, -0.74, 0, "#29323a"),
            ("TOP", "TOP", 0, 0, 0.62, "#29323a"),
            ("BOTTOM", "BTM", 0, 0, -0.74, "#29323a"),
        ):
            txt = cube_ax.text(x, y, z, label, color=color, fontsize=7 if len(label) > 1 else 10,
                               fontweight="bold", picker=12)
            txt.set_gid(axis)
            pick_dot = cube_ax.scatter([x], [y], [z], s=420, alpha=0.01,
                                       color=color, picker=12)
            pick_dot.set_gid(axis)
        cube_ax.set_xlim(-0.6, 1.1)
        cube_ax.set_ylim(-0.6, 1.1)
        cube_ax.set_zlim(-0.6, 1.1)

    def _axis_plane_names(self):
        if self._mesh is None:
            return {
                "X": "YZ",
                "Y": "XZ",
                "Z": "XY",
            }
        airfoil_ax, planform_ax = auto_axes(self._mesh)
        chord_ax = [a for a in "XYZ" if a not in (airfoil_ax, planform_ax)][0]
        return {
            airfoil_ax: "profil kesiti",
            planform_ax: "planform / ust gorunum",
            chord_ax: "veter kesiti / kontrol",
        }

    def _on_language_change(self, _event=None):
        self._lang = "en" if self._v_lang.get() == "English" else "tr"
        self._apply_language()

    def _txt(self, key):
        texts = {
            "tr": {
                "title": "SafeFoam v4 — CNC Kopuk Kesici",
                "version": "v4.0  CNC Kopuk Kesici",
                "flow": "  Dosya ac -> eksen sec -> profil -> G-code",
                "file_section": "3D Model",
                "open": "Dosya Ac...  (STL / OBJ)",
                "scale": "Olcek:",
                "apply_scale": "x Uygula",
                "fast3d": "Hizli 3D gorunum",
                "settings": "Ayarlar / Settings",
                "language": "Dil / Language:",
                "axis_section": "Kesilecek Eksen / 2D Profil",
                "axis_preview": "Secili Ekseni Kes / Onizle",
                "holes_section": "Karbon Tup Delikleri",
                "holes_enable": "Delik gecisi aktif",
                "apply": "Uygula",
                "machine": "Makine Ayarlari",
                "preview": "Önizle / Slice",
                "save": "G-Code Uret & Kaydet",
                "waiting": "Model bekleniyor...",
                "auto_axis": "Otomatik algilandi: aciklik = {axis} ekseni",
                "profile": "Profil",
                "planform": "Planform",
                "span": "aciklik",
                "thickness": "kalinlik",
                "chord": "veter",
            },
            "en": {
                "title": "SafeFoam v4 — CNC Foam Cutter",
                "version": "v4.0  CNC Foam Cutter",
                "flow": "  Open file -> choose axis -> preview -> G-code",
                "file_section": "3D Model",
                "open": "Open File...  (STL / OBJ)",
                "scale": "Scale:",
                "apply_scale": "Apply x",
                "fast3d": "Fast 3D view",
                "settings": "Settings",
                "language": "Language:",
                "axis_section": "Cut Axis / 2D Profile",
                "axis_preview": "Preview Selected Axis",
                "holes_section": "Carbon Tube Holes",
                "holes_enable": "Enable hole pass",
                "apply": "Apply",
                "machine": "Machine Settings",
                "preview": "Preview / Slice",
                "save": "Generate & Save G-Code",
                "waiting": "Waiting for model...",
                "auto_axis": "Auto detected: span = {axis} axis",
                "profile": "Profile",
                "planform": "Planform",
                "span": "span",
                "thickness": "thickness",
                "chord": "chord",
            },
        }
        return texts[self._lang][key]

    def _apply_language(self):
        self.title(self._txt("title"))
        self._ui["version"].config(text=self._txt("version"))
        self._ui["flow"].config(text=self._txt("flow"))
        self._ui["file_section"].config(text=self._txt("file_section"))
        self._ui["open_btn"].config(text=self._txt("open"))
        self._ui["scale_lbl"].config(text=self._txt("scale"))
        self._ui["scale_btn"].config(text=self._txt("apply_scale"))
        self._ui["fast3d_chk"].config(text=self._txt("fast3d"))
        self._ui["settings_section"].config(text=self._txt("settings"))
        self._ui["lang_lbl"].config(text=self._txt("language"))
        self._ui["axis_section"].config(text=self._txt("axis_section"))
        self._ui["axis_preview_btn"].config(text=self._txt("axis_preview"))
        self._ui["holes_section"].config(text=self._txt("holes_section"))
        self._ui["holes_chk"].config(text=self._txt("holes_enable"))
        self._ui["holes_apply_btn"].config(text=self._txt("apply"))
        self._ui["machine_section"].config(text=self._txt("machine"))
        self._ui["preview_btn"].config(text=self._txt("preview"))
        self._ui["save_btn"].config(text=self._txt("save"))
        if self._mesh is None:
            self._axis_hint.config(text=self._txt("waiting"), foreground="#555")
        else:
            self._update_info()

    def _on_cube_pick(self, event):
        axis = getattr(event.artist, "get_gid", lambda: None)()
        presets = {
            "X": (0, -90),
            "Y": (0, 0),
            "Z": (90, -90),
            "RIGHT": (0, -90),
            "LEFT": (0, 90),
            "FRONT": (0, -180),
            "BACK": (0, 0),
            "TOP": (90, -90),
            "BOTTOM": (-90, -90),
        }
        if axis not in presets:
            return
        self._view_elev, self._view_azim = presets[axis]
        self._draw_3d_mesh()

    def _on_3d_press(self, event):
        if event.inaxes is self._cube_ax:
            self._cube_drag = (event.x, event.y, self._view_elev, self._view_azim)
        elif event.inaxes is self._ax3d and event.button in (2, 3):
            self._pan_drag = (event.x, event.y, np.array(self._view_center, dtype=float))

    def _on_3d_motion(self, event):
        if event.x is None or event.y is None:
            return
        if self._cube_drag is not None:
            x0, y0, elev0, azim0 = self._cube_drag
            self._view_azim = azim0 + (event.x - x0) * 0.45
            self._view_elev = max(-89, min(89, elev0 - (event.y - y0) * 0.45))
            if self._ax3d is not None:
                self._ax3d.view_init(elev=self._view_elev, azim=self._view_azim)
            if self._cube_ax is not None:
                self._cube_ax.view_init(elev=self._view_elev, azim=self._view_azim)
            self._canvas3d.draw_idle()
            return
        if self._pan_drag is not None and self._view_center is not None:
            x0, y0, center0 = self._pan_drag
            widget = self._canvas3d.get_tk_widget()
            scale = (self._view_radius or 1.0) * 2.0 / max(widget.winfo_width(), widget.winfo_height(), 1)
            dx = (event.x - x0) * scale
            dy = (event.y - y0) * scale
            self._view_center = center0 + np.array([-dx, dy, 0.0])
            self._apply_current_limits()
            self._canvas3d.draw_idle()

    def _remember_3d_view(self, event=None):
        if self._cube_drag is not None:
            self._cube_drag = None
            return
        if self._pan_drag is not None:
            self._pan_drag = None
            return
        if event is not None and event.inaxes is not self._ax3d:
            return
        if hasattr(self, "_ax3d") and self._ax3d is not None:
            self._view_elev = self._ax3d.elev
            self._view_azim = self._ax3d.azim
            self._draw_axis_cube()
            self._canvas3d.draw_idle()

    def _on_3d_scroll(self, event):
        if self._mesh is None:
            return
        if event.inaxes not in (self._ax3d, self._cube_ax):
            return
        scale = 0.82 if event.button == "up" else 1.22
        self._view_radius = max((self._view_radius or 1.0) * scale, 1.0)
        self._apply_current_limits()
        self._canvas3d.draw_idle()

    def _apply_current_limits(self):
        if self._ax3d is None or self._view_center is None or self._view_radius is None:
            return
        center = self._view_center
        radius = self._view_radius
        self._ax3d.set_xlim(center[0] - radius, center[0] + radius)
        self._ax3d.set_ylim(center[1] - radius, center[1] + radius)
        self._ax3d.set_zlim(center[2] - radius, center[2] + radius)

    def _draw_cutting_plane(self, ax, bounds, view_axis):
        """Tel duzlemini belirgin turuncu cerceve olarak ciz (Poly3D yok, sadece plot)."""
        lo, hi = bounds[0], bounds[1]
        center = (lo + hi) * 0.5
        if view_axis == 'X':
            ox = [center[0], center[0], center[0], center[0], center[0]]
            oy = [lo[1], hi[1], hi[1], lo[1], lo[1]]
            oz = [lo[2], lo[2], hi[2], hi[2], lo[2]]
        elif view_axis == 'Y':
            ox = [lo[0], hi[0], hi[0], lo[0], lo[0]]
            oy = [center[1], center[1], center[1], center[1], center[1]]
            oz = [lo[2], lo[2], hi[2], hi[2], lo[2]]
        else:
            ox = [lo[0], hi[0], hi[0], lo[0], lo[0]]
            oy = [lo[1], lo[1], hi[1], hi[1], lo[1]]
            oz = [center[2], center[2], center[2], center[2], center[2]]

        # Kalin turuncu cerceve + iki diagonal = kesim duzlemi belli olsun
        ax.plot(ox, oy, oz, color="#FF6B35", lw=3.0, alpha=0.95)
        # Kose kose diagonal (X seklinde ic cizgi)
        ax.plot([ox[0], ox[2]], [oy[0], oy[2]], [oz[0], oz[2]],
                color="#FF6B35", lw=1.0, alpha=0.5, linestyle="--")
        ax.plot([ox[1], ox[3]], [oy[1], oy[3]], [oz[1], oz[3]],
                color="#FF6B35", lw=1.0, alpha=0.5, linestyle="--")

    # ── Dosya / Mesh ─────────────────────────────────────────────────────────

    def _open_file(self):
        path = filedialog.askopenfilename(
            title="3D Model Ac",
            filetypes=[("3D Dosyalar", "*.stl *.obj *.ply *.3mf"),
                       ("Tum dosyalar", "*.*")])
        if not path:
            return
        try:
            mesh = load_mesh(path)
        except Exception as e:
            messagebox.showerror("Yukleme Hatasi", str(e))
            return

        self._mesh = mesh
        self._holes_autofit_done = False
        fname = path.replace("\\", "/").split("/")[-1]
        self._file_lbl.config(text=fname, foreground="#1a5a1a")
        self._update_info()
        self._draw_3d_mesh()
        # Layout yerlesin, sonra profil ciz
        self.update()
        self.update_idletasks()
        self._refresh_profile()

    def _apply_scale(self):
        if self._mesh is None:
            return
        try:
            s = float(self._v_scale.get())
        except ValueError:
            return
        import trimesh
        m = self._mesh.copy()
        m.apply_scale(s)
        m.apply_translation(-m.centroid)
        self._mesh = m
        self._holes_autofit_done = False
        self._update_info()
        self._draw_3d_mesh()
        self.update()
        self.update_idletasks()
        self._refresh_profile()

    def _update_info(self):
        if self._mesh is None:
            return
        i = mesh_info(self._mesh)
        airfoil_ax, planform_ax = auto_axes(self._mesh)
        extents = self._mesh.bounds[1] - self._mesh.bounds[0]
        ax_size = {a: extents[j] for a, j in zip("XYZ", range(3))}

        # Model bilgisi
        self._info_lbl.config(
            text=(f"X: {i['x']:.1f}mm   Y: {i['y']:.1f}mm   Z: {i['z']:.1f}mm\n"
                  f"Vertices: {i['vertices']:,}   Faces: {i['faces']:,}"))

        # Eksen radio button etiketlerini guncelle
        chord_ax = [a for a in "XYZ" if a not in (airfoil_ax, planform_ax)][0]
        labels = {
            airfoil_ax:  f"  {airfoil_ax}  — {self._txt('span')} {ax_size[airfoil_ax]:.0f}mm  [{self._txt('profile')}]",
            planform_ax: f"  {planform_ax}  — {self._txt('thickness')} {ax_size[planform_ax]:.0f}mm  [{self._txt('planform')}]",
            chord_ax:    f"  {chord_ax}  — {self._txt('chord')} {ax_size[chord_ax]:.0f}mm  [Kontrol]",
        }
        for axis, rb in self._axis_rbs.items():
            rb.config(text=labels[axis])

        # Otomatik profil eksenini sec
        self._v_axis.set(airfoil_ax)
        self._axis_hint.config(
            text=self._txt("auto_axis").format(axis=airfoil_ax),
            foreground="#90D080")

    # ── Eksen degisimi ───────────────────────────────────────────────────────

    def _on_axis_change(self):
        self._draw_3d_mesh()       # 3D'yi guncelle (yeni duzlem)
        self._refresh_profile()    # 2D profili yeniden cikar

    # ── Profil cikarma ───────────────────────────────────────────────────────

    def _get_holes(self):
        if not self._v_holes_en.get():
            return []
        holes = []
        for v_en, v_hx, v_hy, v_hr in self._hole_rows:
            if not v_en.get():
                continue
            try:
                holes.append((float(v_hx.get()),
                               float(v_hy.get()),
                               float(v_hr.get())))
            except ValueError:
                pass
        return holes

    def _refresh_profile(self):
        if self._mesh is None:
            return
        axis = self._v_axis.get()
        try:
            airfoil_ax, planform_ax = auto_axes(self._mesh)
            if axis == planform_ax:
                px, py = extract_profile(self._mesh, view_axis=axis)
            else:
                px, py = extract_section_profile(self._mesh, view_axis=axis)
                if px is None:
                    px, py = extract_profile(self._mesh, view_axis=axis)
            if px is None:
                return
            bd = foam_bounds(self._mesh, view_axis=axis)
            self._profile = (px, py)
            self._bounds  = bd
            self._autofit_holes_to_profile(px, py)
        except Exception as e:
            messagebox.showerror("Profil Hatasi", str(e))
            return

        holes = self._get_holes()
        if holes:
            try:
                px, py = insert_hole_traversal(px, py, holes)
            except Exception:
                pass

        self._sim.set_data(px, py, bd, holes=holes)

    def _autofit_holes_to_profile(self, px, py):
        if self._holes_autofit_done or len(px) < 8:
            return
        x_min = float(np.min(px))
        x_max = float(np.max(px))
        y_min = float(np.min(py))
        y_max = float(np.max(py))
        chord = max(x_max - x_min, 1.0)
        thick = max(y_max - y_min, 1.0)
        positions = [0.38, 0.55, 0.70]
        radius = max(min(thick * 0.12, chord * 0.035), 1.0)
        for i, (v_en, v_hx, v_hy, v_hr) in enumerate(self._hole_rows):
            hx = x_min + chord * positions[i]
            near = np.abs(px - hx) < chord * 0.03
            if near.any():
                local_y = py[near]
                hy = (float(np.max(local_y)) + float(np.min(local_y))) * 0.5
            else:
                hy = (y_min + y_max) * 0.5
            v_hx.set(f"{hx:.1f}")
            v_hy.set(f"{hy:.1f}")
            v_hr.set(f"{radius:.1f}")
        self._holes_autofit_done = True

    # ── G-Code ───────────────────────────────────────────────────────────────

    def _save_gcode(self):
        px, py = self._profile
        if px is None:
            messagebox.showwarning("G-Code", "Once bir model yukleyin.")
            return

        holes = self._get_holes()
        if holes:
            try:
                px, py = insert_hole_traversal(px, py, holes)
            except Exception:
                pass

        mc = MachineConfig(
            ax1_h=self._v_ax1h.get(), ax1_v=self._v_ax1v.get(),
            ax2_h=self._v_ax2h.get(), ax2_v=self._v_ax2v.get(),
            feed_rate=float(self._v_feed.get()),
            plunge_rate=float(self._v_plunge.get()),
            lead_in=float(self._v_leadin.get()),
        )
        gcode = generate_planform_gcode((px, py), mc)

        path = filedialog.asksaveasfilename(
            defaultextension=".nc",
            filetypes=[("G-Code", "*.nc *.gcode *.txt"), ("Tumu", "*.*")],
            initialfile="safefoam_cut.nc",
            title="G-Code Kaydet",
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(gcode)
        messagebox.showinfo("Kaydedildi", f"G-Code kaydedildi:\n{path}")
