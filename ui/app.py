"""
SafeFoam — 3-sekme wizard:
  1. Model Import  (STL / OBJ / 3D model)
  2. Pass 1        (Yan kesim simülasyonu + G-code)
  3. Pass 2        (Ön kesim simülasyonu + G-code)
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from core.mesh_import import load_mesh, extract_profile, foam_bounds, mesh_info
from core.gcode import MachineConfig, generate_wing_gcode, generate_planform_gcode
from core.airfoil import get_profile, get_surfaces
from ui.sim_player import SimPlayer


# ── Kucuk yardimcilar ────────────────────────────────────────────────────────

def _lbl(parent, text, **kw):
    return ttk.Label(parent, text=text, **kw)

def _entry(parent, var, w=9):
    return ttk.Entry(parent, textvariable=var, width=w)

def _row(parent, label, default, row, unit="", w=9):
    _lbl(parent, label).grid(row=row, column=0, sticky="w", pady=2, padx=(0, 4))
    var = tk.StringVar(value=str(default))
    _entry(parent, var, w).grid(row=row, column=1, pady=2)
    if unit:
        _lbl(parent, unit, foreground="#777").grid(row=row, column=2, sticky="w")
    return var

def _section(parent, title):
    f = ttk.LabelFrame(parent, text=title, padding=6)
    f.pack(fill="x", padx=6, pady=4)
    return f


# ════════════════════════════════════════════════════════════════════════════
#  TAB 1 — Model Import
# ════════════════════════════════════════════════════════════════════════════

class ImportTab(ttk.Frame):

    def __init__(self, parent, app):
        super().__init__(parent, padding=4)
        self._app = app
        self._mesh = None
        self._build()

    def _build(self):
        # Sol panel
        left = ttk.Frame(self, width=210)
        left.pack(side="left", fill="y", padx=(0, 6))
        left.pack_propagate(False)

        # Dosya sec
        ff = _section(left, "3D Model")
        ttk.Button(ff, text="📂  STL / OBJ Aç...",
                   command=self._open_file).pack(fill="x", pady=2)
        self._file_lbl = ttk.Label(ff, text="Dosya seçilmedi",
                                   foreground="#888", wraplength=180)
        self._file_lbl.pack(fill="x", pady=2)

        # Boyut bilgisi
        self._info_frm = _section(left, "Model Bilgisi")
        self._info_lbl = ttk.Label(self._info_frm,
                                   text="—", foreground="#aaa",
                                   justify="left")
        self._info_lbl.pack(anchor="w")

        # Olcek
        sf = _section(left, "Ölçek & Konum")
        self._v_scale = _row(sf, "Ölçek", "1.0", 0, "×")
        ttk.Button(sf, text="Uygula",
                   command=self._apply_scale).grid(
                       row=1, column=0, columnspan=3, sticky="ew", pady=4)

        # Pass butonlari
        ttk.Separator(left).pack(fill="x", pady=6)
        ttk.Button(left, text="▶  Pass 1: Yan Kesim →",
                   command=lambda: self._app.goto_pass(1)).pack(fill="x", pady=2)
        ttk.Button(left, text="▶  Pass 2: Ön Kesim →",
                   command=lambda: self._app.goto_pass(2)).pack(fill="x", pady=2)

        # Sag panel — 3D onizleme
        right = ttk.Frame(self)
        right.pack(side="left", fill="both", expand=True)

        fig = Figure(figsize=(6, 5), dpi=96, facecolor="#0f0f1e")
        self._fig3d = fig
        self._ax3d  = fig.add_subplot(111, projection="3d")
        self._canvas3d = FigureCanvasTkAgg(fig, master=right)
        self._canvas3d.get_tk_widget().pack(fill="both", expand=True)
        self._draw_empty()

    def _draw_empty(self):
        ax = self._ax3d
        ax.cla()
        ax.set_facecolor("#0f0f1e")
        ax.set_title("3D Model Önizleme", color="white", fontsize=9)
        for p in [ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane]:
            p.set_facecolor("#12122a"); p.set_alpha(0.5)
        self._canvas3d.draw_idle()

    def _open_file(self):
        path = filedialog.askopenfilename(
            title="3D Model Aç",
            filetypes=[("3D Dosyalar", "*.stl *.obj *.ply *.3mf"),
                       ("Tüm dosyalar", "*.*")])
        if not path:
            return
        try:
            mesh = load_mesh(path)
        except Exception as e:
            messagebox.showerror("Yükleme Hatası", str(e))
            return

        self._mesh = mesh
        self._app.set_mesh(mesh)
        self._file_lbl.config(text=path.split("/")[-1], foreground="#4fc3f7")
        self._update_info()
        self._draw_mesh()

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
        self._app.set_mesh(m)
        self._update_info()
        self._draw_mesh()

    def _update_info(self):
        if self._mesh is None:
            return
        i = mesh_info(self._mesh)
        self._info_lbl.config(
            text=(f"X: {i['x']:.1f} mm\n"
                  f"Y: {i['y']:.1f} mm\n"
                  f"Z: {i['z']:.1f} mm\n"
                  f"Vertices: {i['vertices']:,}\n"
                  f"Faces: {i['faces']:,}"))

    def _draw_mesh(self):
        if self._mesh is None:
            return
        ax = self._ax3d
        ax.cla()
        ax.set_facecolor("#0f0f1e")

        m = self._mesh
        verts = m.vertices
        faces = m.faces

        # Sadece her 4. yuz ciz (hiz icin)
        step = max(1, len(faces) // 2000)
        sub  = faces[::step]
        tris = verts[sub]

        poly = Poly3DCollection(tris, alpha=0.55,
                                facecolor="#4fc3f7", edgecolor="none")
        ax.add_collection3d(poly)

        b = m.bounds
        ax.set_xlim(b[0][0], b[1][0])
        ax.set_ylim(b[0][1], b[1][1])
        ax.set_zlim(b[0][2], b[1][2])

        ax.set_xlabel("X", color="#777", fontsize=7)
        ax.set_ylabel("Y", color="#777", fontsize=7)
        ax.set_zlabel("Z", color="#777", fontsize=7)
        ax.tick_params(colors="#555", labelsize=6)
        ax.set_title("3D Model Önizleme", color="white", fontsize=9)
        for p in [ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane]:
            p.set_facecolor("#12122a"); p.set_alpha(0.5)
        ax.view_init(elev=20, azim=-50)

        self._canvas3d.draw_idle()


# ════════════════════════════════════════════════════════════════════════════
#  TAB 2 & 3 — Pass (Yan / On Kesim)
# ════════════════════════════════════════════════════════════════════════════

class PassTab(ttk.Frame):

    VIEW_LABELS = {
        'Y': "Yan (XZ düzlemi — Y boyunca tel)",
        'X': "Ön  (YZ düzlemi — X boyunca tel)",
        'Z': "Üst (XY düzlemi — Z boyunca tel)",
    }

    def __init__(self, parent, app, pass_num: int):
        super().__init__(parent, padding=4)
        self._app      = app
        self._pass_num = pass_num
        self._profile  = (None, None)
        self._bounds   = None
        self._build()

    def _build(self):
        # Sol ayarlar paneli
        left = ttk.Frame(self, width=220)
        left.pack(side="left", fill="y", padx=(0, 6))
        left.pack_propagate(False)

        # Kesim yonu
        df = _section(left, "Kesim Yönü")
        self._v_axis = tk.StringVar(
            value='Y' if self._pass_num == 1 else 'X')
        for axis, lbl in self.VIEW_LABELS.items():
            ttk.Radiobutton(df, text=lbl, value=axis,
                            variable=self._v_axis,
                            command=self._refresh).pack(anchor="w", pady=1)

        # Makine ayarlari
        mf = _section(left, "Makine")
        self._v_feed   = _row(mf, "Kesim hızı", 300, 0, "mm/min")
        self._v_plunge = _row(mf, "Yaklaşma",   100, 1, "mm/min")
        self._v_leadin = _row(mf, "Lead-in",     15, 2, "mm")

        # Eksen eslestirme
        af = _section(left, "Eksen (Pass " + str(self._pass_num) + ")")
        self._v_ax1h = _row(af, "Kule 1 yatay", "X", 0, w=4)
        self._v_ax1v = _row(af, "Kule 1 dikey", "Y", 1, w=4)
        self._v_ax2h = _row(af, "Kule 2 yatay", "A", 2, w=4)
        self._v_ax2v = _row(af, "Kule 2 dikey", "B", 3, w=4)

        ttk.Separator(left).pack(fill="x", pady=6)
        ttk.Button(left, text="🔄  Profili Yenile",
                   command=self._refresh).pack(fill="x", pady=2)
        ttk.Button(left, text="💾  G-Code Üret & Kaydet",
                   command=self._save_gcode).pack(fill="x", pady=2)

        if self._pass_num == 1:
            ttk.Button(left, text="▶  Pass 2 →",
                       command=lambda: self._app.goto_pass(2)).pack(
                           fill="x", pady=(8, 2))

        # Sag — SimPlayer
        self._sim = SimPlayer(
            self,
            title=f"Pass {self._pass_num} — "
                  + ("Yan Kesim" if self._pass_num == 1 else "Ön Kesim"))
        self._sim.pack(side="left", fill="both", expand=True)

    # ── Profili guncelle ─────────────────────────────────────────────────────

    def refresh_from_mesh(self, mesh):
        """Dis cagriya acik — mesh degisince cagrilir."""
        if mesh is None:
            self._sim.clear()
            return
        axis = self._v_axis.get()
        try:
            px, py = extract_profile(mesh, view_axis=axis)
            if px is None:
                messagebox.showwarning("Profil", "Bu eksende profil çıkarılamadı.")
                return
            bd = foam_bounds(mesh, view_axis=axis)
            self._profile = (px, py)
            self._bounds  = bd
            self._sim.set_data(px, py, bd)
        except Exception as e:
            messagebox.showerror("Profil Hatası", str(e))

    def _refresh(self):
        self.refresh_from_mesh(self._app.mesh)

    # ── G-Code kaydet ────────────────────────────────────────────────────────

    def _save_gcode(self):
        px, py = self._profile
        if px is None:
            messagebox.showwarning("G-Code", "Önce bir model yükleyin.")
            return

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
            filetypes=[("G-Code", "*.nc *.gcode *.txt"), ("Tümü", "*.*")],
            initialfile=f"pass{self._pass_num}.nc",
            title="G-Code Kaydet",
        )
        if not path:
            return

        with open(path, "w", encoding="utf-8") as f:
            f.write(gcode)

        messagebox.showinfo("Kaydedildi",
                            f"Pass {self._pass_num} G-Code kaydedildi:\n{path}")


# ════════════════════════════════════════════════════════════════════════════
#  Ana Uygulama
# ════════════════════════════════════════════════════════════════════════════

class FoamCutterApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("SafeFoam — CNC Köpük Kesici")
        self.minsize(1050, 640)
        self.resizable(True, True)

        self.mesh = None  # paylasilan durum

        self._build()

    def _build(self):
        # Baslik bar
        bar = tk.Frame(self, bg="#12122a", height=36)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Label(bar, text="  SafeFoam  CNC Köpük Kesici",
                 bg="#12122a", fg="#4fc3f7",
                 font=("Segoe UI", 11, "bold")).pack(side="left", padx=8)
        tk.Label(bar, text="v2.0",
                 bg="#12122a", fg="#555",
                 font=("Segoe UI", 9)).pack(side="left")

        # Notebook (sekmeler)
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=6, pady=6)
        self._nb = nb

        self.tab_import = ImportTab(nb, self)
        self.tab_pass1  = PassTab(nb, self, pass_num=1)
        self.tab_pass2  = PassTab(nb, self, pass_num=2)

        nb.add(self.tab_import, text="  1 ·  Model Import  ")
        nb.add(self.tab_pass1,  text="  2 ·  Pass 1 — Yan Kesim  ")
        nb.add(self.tab_pass2,  text="  3 ·  Pass 2 — Ön Kesim  ")

        # Sekme degisince profilleri yenile
        nb.bind("<<NotebookTabChanged>>", self._on_tab_change)

    # ── Paylasilan durum ─────────────────────────────────────────────────────

    def set_mesh(self, mesh):
        """ImportTab'dan cagrılır."""
        self.mesh = mesh
        # Her iki pass tab'ini bilgilendir
        self.tab_pass1.refresh_from_mesh(mesh)
        self.tab_pass2.refresh_from_mesh(mesh)

    def goto_pass(self, num: int):
        self._nb.select(num)  # 0=import, 1=pass1, 2=pass2

    def _on_tab_change(self, event):
        idx = self._nb.index("current")
        if idx == 1:
            self.tab_pass1.refresh_from_mesh(self.mesh)
        elif idx == 2:
            self.tab_pass2.refresh_from_mesh(self.mesh)
