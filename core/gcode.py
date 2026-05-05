from dataclasses import dataclass, field
import numpy as np


@dataclass
class MachineConfig:
    # Sol kule eksenleri
    ax1_h: str = "X"   # yatay
    ax1_v: str = "Y"   # dikey
    # Sag kule eksenleri
    ax2_h: str = "A"
    ax2_v: str = "B"

    feed_rate: float = 300.0    # mm/min — kesim hizi
    plunge_rate: float = 100.0  # mm/min — yaklasma hizi
    lead_in: float = 15.0       # mm — profilden once gelen mesafe
    lead_out: float = 15.0      # mm — profilden sonra cikis mesafesi


@dataclass
class WingParams:
    root_naca: str = "2412"
    tip_naca: str = "2412"
    root_chord: float = 200.0   # mm
    tip_chord: float = 150.0    # mm
    wingspan: float = 600.0     # mm (kopuk blogunun uzunlugu)
    root_twist: float = 0.0     # derece
    tip_twist: float = -2.0     # derece (washout)
    n_points: int = 100


def _resample(x, y, n):
    """Profili n noktaya yeniden ornekle (arc-length parametrik)."""
    dx = np.diff(x)
    dy = np.diff(y)
    seg = np.sqrt(dx**2 + dy**2)
    arc = np.concatenate([[0], np.cumsum(seg)])
    arc /= arc[-1]
    t_new = np.linspace(0, 1, n)
    return np.interp(t_new, arc, x), np.interp(t_new, arc, y)


def generate_wing_gcode(
    root_xy: tuple,
    tip_xy: tuple,
    machine: MachineConfig,
) -> str:
    """
    4 eksen kanat G-code uret.
    root_xy = (x_arr, y_arr) — sol kule (kok profili, mm)
    tip_xy  = (x_arr, y_arr) — sag kule (uc profili, mm)
    """
    rx, ry = _resample(*root_xy, machine.__class__.__dict__.get("n_points", len(root_xy[0])))
    tx, ty = _resample(*tip_xy, len(root_xy[0]))

    # Nokta sayilarini esitle
    n = min(len(rx), len(tx))
    rx, ry = _resample(*root_xy, n)
    tx, ty = _resample(*tip_xy, n)

    h1, v1 = machine.ax1_h, machine.ax1_v
    h2, v2 = machine.ax2_h, machine.ax2_v
    F  = machine.feed_rate
    Fp = machine.plunge_rate
    li = machine.lead_in
    lo = machine.lead_out

    def pt(x1, y1, x2, y2, feed, comment=""):
        s = f"G1 {h1}{x1:.3f} {v1}{y1:.3f} {h2}{x2:.3f} {v2}{y2:.3f} F{feed:.0f}"
        if comment:
            s += f"  ; {comment}"
        return s

    lines = [
        "; ================================================",
        "; SafeFoam — 4-Eksen Kanat G-Code",
        f"; Kok NACA, Uc NACA profilleri",
        f"; Besleme: {F} mm/min",
        "; ================================================",
        "",
        "G21        ; milimetre",
        "G90        ; mutlak koordinat",
        f"G0 {h1}0 {v1}0 {h2}0 {v2}0  ; eve don",
        "",
        "; --- Yaklasma (lead-in) ---",
    ]

    # Lead-in: profilin ilk noktasindan lead_in kadar geri
    # Profil TE'den baslar — yatay olarak geri cekil
    lx1, ly1 = rx[0] + li, ry[0]
    lx2, ly2 = tx[0] + li, ty[0]
    lines.append(f"G0 {h1}{lx1:.3f} {v1}{ly1:.3f} {h2}{lx2:.3f} {v2}{ly2:.3f}")
    lines.append(pt(rx[0], ry[0], tx[0], ty[0], Fp, "TE giris"))
    lines.append("")
    lines.append("; --- Profil kesimi ---")

    for i in range(n):
        lines.append(pt(rx[i], ry[i], tx[i], ty[i], F))

    lines += [
        "",
        "; --- Cikis (lead-out) ---",
        pt(rx[-1] + lo, ry[-1], tx[-1] + lo, ty[-1], Fp),
        "",
        f"G0 {h1}0 {v1}0 {h2}0 {v2}0  ; eve don",
        "; ================================================",
        "; Bitti",
        "; ================================================",
    ]

    return "\n".join(lines)


def generate_planform_gcode(
    planform_xy: tuple,
    machine: MachineConfig,
) -> str:
    """
    2 gecis teknik — 1. gecis: planform kesimi (ust gorunus).
    Her iki kule ayni yolu izler (senkron, tapered yok).
    """
    px, py = planform_xy
    h1, v1 = machine.ax1_h, machine.ax1_v
    h2, v2 = machine.ax2_h, machine.ax2_v
    F = machine.feed_rate
    li = machine.lead_in

    lines = [
        "; SafeFoam — Planform Kesim G-Code (her iki kule ayni yol)",
        "G21 G90",
        f"G0 {h1}0 {v1}0 {h2}0 {v2}0",
        f"G0 {h1}{px[0]+li:.3f} {v1}{py[0]:.3f} {h2}{px[0]+li:.3f} {v2}{py[0]:.3f}",
    ]
    for x, y in zip(px, py):
        lines.append(
            f"G1 {h1}{x:.3f} {v1}{y:.3f} {h2}{x:.3f} {v2}{y:.3f} F{F:.0f}"
        )
    lines += [
        f"G0 {h1}0 {v1}0 {h2}0 {v2}0",
        "; Bitti",
    ]
    return "\n".join(lines)
