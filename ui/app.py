"""
SafeFoam v4.0 — PrusaSlicer tarzı tek ekran arayuz
Sol: ayarlar | Sag ust: 3D model + kesim duzlemi | Sag alt: 2D profil sim
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D          # noqa: F401
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from core.mesh_import import (load_mesh, extract_profile, foam_bounds,
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
        self.minsize(1150, 680)
        self.resizable(True, True)

        self._mesh    = None
        self._profile = (None, None)
        self._bounds  = None

        self._build()

    # ── Layout ───────────────────────────────────────────────────────────────

    def _build(self):
        # Baslik
        bar = tk.Frame(self, bg="#12122a", height=34)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Label(bar, text="  SafeFoam",
                 bg="#12122a", fg="#4fc3f7",
                 font=("Segoe UI", 11, "bold")).pack(side="left", padx=8)
        tk.Label(bar, text="v4.0  CNC Kopuk Kesici",
                 bg="#12122a", fg="#FF6B35",
                 font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Label(bar,
                 text="  3D model ac | kesim eksenini sec | profil + G-code",
                 bg="#12122a", fg="#444",
                 font=("Segoe UI", 8)).pack(side="left", padx=10)

        # Icerik alani
        content = ttk.Frame(self)
        content.pack(fill="both", expand=True)

        # Sol panel (sabit genislik, kaydirma destekli)
        self._build_left(content)

        ttk.Separator(content, orient="vertical").pack(side="left", fill="y")

        # Sag alan: dikey bolmeli (3D ust, 2D profil alt)
        right = ttk.PanedWindow(content, orient="vertical")
        right.pack(side="left", fill="both", expand=True, padx=3, pady=3)

        view3d_frm = ttk.Frame(right)
        right.add(view3d_frm, weight=3)
        self._build_3d_view(view3d_frm)

        sim_frm = ttk.Frame(right)
        right.add(sim_frm, weight=2)
        self._sim = SimPlayer(sim_frm, title="Kesim Profili Simulasyonu")
        self._sim.pack(fill="both", expand=True)

    # ── Sol panel ────────────────────────────────────────────────────────────

    def _build_left(self, parent):
        outer = ttk.Frame(parent, width=245)
        outer.pack(side="left", fill="y")
        outer.pack_propagate(False)

        # Canvas + scrollbar icin kap
        cv = tk.Canvas(outer, width=243, highlightthickness=0,
                       bg=self.cget("bg"))
        sb = ttk.Scrollbar(outer, orient="vertical", command=cv.yview)
        cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        cv.pack(side="left", fill="both", expand=True)

        inner = ttk.Frame(cv)
        win_id = cv.create_window((0, 0), window=inner, anchor="nw", width=237)
        inner.bind("<Configure>",
                   lambda e: cv.configure(scrollregion=cv.bbox("all")))
        # Fare tekerlegini sol panele sinirla
        inner.bind("<Enter>", lambda e: cv.bind_all(
            "<MouseWheel>",
            lambda ev: cv.yview_scroll(-1*(ev.delta//120), "units")))
        inner.bind("<Leave>", lambda e: cv.unbind_all("<MouseWheel>"))

        self._build_file_section(inner)
        self._build_axis_section(inner)
        self._build_holes_section(inner)
        self._build_machine_section(inner)

        ttk.Separator(inner).pack(fill="x", padx=5, pady=4)
        ttk.Button(inner, text="G-Code Uret & Kaydet",
                   command=self._save_gcode).pack(fill="x", padx=5, pady=2)

    def _build_file_section(self, parent):
        ff = _section(parent, "3D Model")
        ttk.Button(ff, text="Dosya Ac...  (STL / OBJ)",
                   command=self._open_file).pack(fill="x", pady=2)
        self._file_lbl = ttk.Label(ff, text="Dosya secilmedi",
                                   foreground="#888", wraplength=210)
        self._file_lbl.pack(fill="x")

        sf = ttk.Frame(ff)
        sf.pack(fill="x", pady=(4, 0))
        _lbl(sf, "Olcek:").grid(row=0, column=0, sticky="w")
        self._v_scale = tk.StringVar(value="1.0")
        _entry(sf, self._v_scale, 5).grid(row=0, column=1, padx=3)
        ttk.Button(sf, text="x Uygula", width=8,
                   command=self._apply_scale).grid(row=0, column=2)

        self._info_lbl = ttk.Label(ff, text="", foreground="#aaa",
                                   justify="left", font=("Segoe UI", 8))
        self._info_lbl.pack(anchor="w", pady=(4, 0))

    def _build_axis_section(self, parent):
        af = _section(parent, "Kesim Ekseni  (tel hangi yonde gidecek?)")

        self._v_axis = tk.StringVar(value="X")
        self._axis_rbs = {}

        for axis in ("X", "Y", "Z"):
            rb = ttk.Radiobutton(af, text=f"  {axis}  ekseni boyunca",
                                 value=axis, variable=self._v_axis,
                                 command=self._on_axis_change)
            rb.pack(anchor="w", pady=1)
            self._axis_rbs[axis] = rb

        self._axis_hint = ttk.Label(af, text="Model bekleniyor...",
                                    foreground="#555",
                                    font=("Segoe UI", 7, "italic"),
                                    wraplength=215)
        self._axis_hint.pack(anchor="w", pady=(3, 0))

    def _build_holes_section(self, parent):
        hf = _section(parent, "Karbon Tup Delikleri")

        self._v_holes_en = tk.BooleanVar(value=False)
        ttk.Checkbutton(hf, text="Delik gecisi aktif",
                        variable=self._v_holes_en).grid(
                            row=0, column=0, columnspan=6, sticky="w")

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

        ttk.Button(hf, text="Uygula",
                   command=self._refresh_profile).grid(
                       row=len(defaults)+2, column=0, columnspan=5,
                       sticky="ew", pady=(4, 0))

    def _build_machine_section(self, parent):
        mf = _section(parent, "Makine Ayarlari")

        # 2 sutun: sol hiz ayarlari, sag eksen eslestirme
        left  = ttk.Frame(mf)
        right = ttk.Frame(mf)
        left.grid(row=0, column=0, sticky="nw", padx=(0, 8))
        right.grid(row=0, column=1, sticky="nw")

        self._v_feed   = _row(left,  "Kesim hizi:",  300, 0, unit="mm/m", w=6)
        self._v_plunge = _row(left,  "Yaklasma:",    100, 1, unit="mm/m", w=6)
        self._v_leadin = _row(left,  "Lead-in:",      15, 2, unit="mm",   w=6)

        self._v_ax1h = _row(right, "K1 yatay:", "X", 0, unit="", w=3)
        self._v_ax1v = _row(right, "K1 dikey:", "Y", 1, unit="", w=3)
        self._v_ax2h = _row(right, "K2 yatay:", "A", 2, unit="", w=3)
        self._v_ax2v = _row(right, "K2 dikey:", "B", 3, unit="", w=3)

    # ── 3D Goruntu ───────────────────────────────────────────────────────────

    def _build_3d_view(self, parent):
        fig = Figure(figsize=(7, 4.5), dpi=96, facecolor="#0f0f1e")
        self._fig3d    = fig
        self._ax3d     = fig.add_subplot(111, projection="3d")
        self._canvas3d = FigureCanvasTkAgg(fig, master=parent)
        self._canvas3d.get_tk_widget().pack(fill="both", expand=True)
        self._draw_3d_empty()

    def _draw_3d_empty(self):
        self._fig3d.clear()
        ax = self._fig3d.add_subplot(111, projection="3d")
        self._ax3d = ax
        ax.set_facecolor("#0f0f1e")
        ax.set_title("3D model yüklemek için sol panelden 'Dosya Ac' butonunu kullanin",
                     color="#444", fontsize=9)
        for p in [ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane]:
            p.set_facecolor("#0a0a1a"); p.set_alpha(0.5)
        self._canvas3d.draw()

    def _draw_3d_mesh(self):
        if self._mesh is None:
            return

        self._fig3d.clear()
        ax = self._fig3d.add_subplot(111, projection="3d")
        self._ax3d = ax
        ax.set_facecolor("#0f0f1e")

        m     = self._mesh
        verts = m.vertices
        edges = m.edges_unique

        # Edge wireframe (hizli, temiz)
        step = max(1, len(edges) // 4000)
        ex, ey, ez = [], [], []
        for e in edges[::step]:
            ex += [verts[e[0], 0], verts[e[1], 0], None]
            ey += [verts[e[0], 1], verts[e[1], 1], None]
            ez += [verts[e[0], 2], verts[e[1], 2], None]
        ax.plot(ex, ey, ez, color="#4fc3f7", lw=0.4, alpha=0.55)

        # Kesim duzlemi — orta turuncu panel
        self._draw_cutting_plane(ax, m.bounds, self._v_axis.get())

        b   = m.bounds
        pad = (b[1] - b[0]) * 0.06
        ax.set_xlim(b[0][0]-pad[0], b[1][0]+pad[0])
        ax.set_ylim(b[0][1]-pad[1], b[1][1]+pad[1])
        ax.set_zlim(b[0][2]-pad[2], b[1][2]+pad[2])
        ax.set_xlabel("X", color="#666", fontsize=7)
        ax.set_ylabel("Y", color="#666", fontsize=7)
        ax.set_zlabel("Z", color="#666", fontsize=7)
        ax.tick_params(colors="#555", labelsize=6)

        plane_name = {
            'X': "YZ duzlemi (kanat profili)",
            'Y': "XZ duzlemi",
            'Z': "XY duzlemi (planform)",
        }
        ax.set_title(
            f"Tel ekseni: {self._v_axis.get()}  |  "
            f"Kesim duzlemi: {plane_name.get(self._v_axis.get(), '')}",
            color="#FF6B35", fontsize=9)

        for p in [ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane]:
            p.set_facecolor("#0a0a1a"); p.set_alpha(0.6)
        ax.view_init(elev=20, azim=-50)
        self._canvas3d.draw()

    def _draw_cutting_plane(self, ax, bounds, view_axis):
        """Tel duzlemini 3D goruntuye yari saydam turuncu panel olarak ekle."""
        lo, hi = bounds[0], bounds[1]
        # Kesitin orta noktasinda duzlem goster
        if view_axis == 'X':
            verts = [[(0, lo[1], lo[2]), (0, hi[1], lo[2]),
                      (0, hi[1], hi[2]), (0, lo[1], hi[2])]]
        elif view_axis == 'Y':
            verts = [[(lo[0], 0, lo[2]), (hi[0], 0, lo[2]),
                      (hi[0], 0, hi[2]), (lo[0], 0, hi[2])]]
        else:
            verts = [[(lo[0], lo[1], 0), (hi[0], lo[1], 0),
                      (hi[0], hi[1], 0), (lo[0], hi[1], 0)]]
        plane = Poly3DCollection(verts, alpha=0.18,
                                 facecolor="#FF6B35",
                                 edgecolor="#FF6B35", lw=1.5)
        ax.add_collection3d(plane)

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
        fname = path.replace("\\", "/").split("/")[-1]
        self._file_lbl.config(text=fname, foreground="#4fc3f7")
        self._update_info()
        self._draw_3d_mesh()
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
        self._update_info()
        self._draw_3d_mesh()
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
            airfoil_ax:  f"  {airfoil_ax}  — aciklik {ax_size[airfoil_ax]:.0f}mm  [Profil]",
            planform_ax: f"  {planform_ax}  — kalinlik {ax_size[planform_ax]:.0f}mm  [Planform]",
            chord_ax:    f"  {chord_ax}  — veter {ax_size[chord_ax]:.0f}mm",
        }
        for axis, rb in self._axis_rbs.items():
            rb.config(text=labels[axis])

        # Otomatik profil eksenini sec
        self._v_axis.set(airfoil_ax)
        self._axis_hint.config(
            text=f"Otomatik algilandi: aciklik = {airfoil_ax} ekseni",
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
            px, py = extract_profile(self._mesh, view_axis=axis)
            if px is None:
                return
            bd = foam_bounds(self._mesh, view_axis=axis)
            self._profile = (px, py)
            self._bounds  = bd
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
