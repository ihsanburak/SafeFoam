"""
3D mesh import ve silhouette profil cikarimi.
Desteklenen formatlar: STL, OBJ, PLY, 3MF
"""
import numpy as np
from scipy.ndimage import uniform_filter1d


def load_mesh(filepath: str):
    """STL / OBJ / PLY dosyasini yukle, merkezi origina tasi."""
    import trimesh
    loaded = trimesh.load(filepath, force='mesh')
    if isinstance(loaded, trimesh.Scene):
        loaded = trimesh.util.concatenate(list(loaded.dump()))
    loaded.apply_translation(-loaded.centroid)
    return loaded


def mesh_info(mesh) -> dict:
    b = mesh.bounds
    s = b[1] - b[0]
    return dict(
        x=s[0], y=s[1], z=s[2],
        x_min=b[0][0], y_min=b[0][1], z_min=b[0][2],
        x_max=b[1][0], y_max=b[1][1], z_max=b[1][2],
        vertices=len(mesh.vertices),
        faces=len(mesh.faces),
    )


def detect_span_axis(mesh) -> str:
    """Mesh'in en uzun ekseni — kanat aciklik yonu ('X', 'Y', veya 'Z')."""
    extents = mesh.bounds[1] - mesh.bounds[0]
    return ['X', 'Y', 'Z'][int(np.argmax(extents))]


def auto_axes(mesh) -> tuple:
    """
    (airfoil_axis, planform_axis) dondurur.
    airfoil_axis  : aciklik boyunca projeksiyon -> profil (veter x kalinlik)
    planform_axis : kalinlik boyunca projeksiyon -> planform (aciklik x veter)
    """
    extents = mesh.bounds[1] - mesh.bounds[0]
    order = np.argsort(extents)          # [ince, orta, uzun]
    names = ['X', 'Y', 'Z']
    span_axis  = names[int(order[2])]    # en uzun = aciklik
    thick_axis = names[int(order[0])]    # en kisa = kalinlik
    return span_axis, thick_axis


def _proj_axes(mesh, view_axis: str):
    """
    view_axis boyunca projeksiyon icin (h_idx, v_idx) dondurur.
    Uzun kalan eksen yatay (h), kisa olan dikey (v) olur.
    Bu sayede profil her zaman dogru yonelimde gosterilir.
    """
    extents = mesh.bounds[1] - mesh.bounds[0]
    skip = {'X': 0, 'Y': 1, 'Z': 2}[view_axis]
    rem  = [i for i in range(3) if i != skip]
    if extents[rem[0]] >= extents[rem[1]]:
        return rem[0], rem[1]
    return rem[1], rem[0]


def extract_profile(mesh, view_axis: str = 'Y', n_bins: int = 300,
                    smooth: int = 9) -> tuple:
    """
    Mesh'i belirtilen eksenden projekte ederek kesim profili cikar.
    Uzun eksen yatay, kisa eksen dikey (otomatik yonlendirme).

    view_axis = 'X'  : X boyunca bak -> YZ duzlemi (kanat profili)
    view_axis = 'Y'  : Y boyunca bak -> XZ duzlemi
    view_axis = 'Z'  : Z boyunca bak -> XY duzlemi (planform)

    Donus: (px, py) — kapali kontur, mm cinsinden.
    """
    v = mesh.vertices
    h_idx, v_idx = _proj_axes(mesh, view_axis)
    h  = v[:, h_idx]
    vv = v[:, v_idx]

    edges = np.linspace(h.min(), h.max(), n_bins + 1)
    cx    = 0.5 * (edges[:-1] + edges[1:])

    upper_pts, lower_pts = [], []
    for i in range(n_bins):
        mask = (h >= edges[i]) & (h <= edges[i + 1])
        if mask.sum() > 0:
            upper_pts.append([cx[i], vv[mask].max()])
            lower_pts.append([cx[i], vv[mask].min()])

    if not upper_pts:
        return None, None

    upper = np.array(upper_pts)
    lower = np.array(lower_pts)

    if smooth > 1 and len(upper) > smooth:
        upper[:, 1] = uniform_filter1d(upper[:, 1], size=smooth)
        lower[:, 1] = uniform_filter1d(lower[:, 1], size=smooth)

    # Kapali kontur: ust sol->sag + alt sag->sol
    px = np.concatenate([upper[:, 0], lower[::-1, 0], [upper[0, 0]]])
    py = np.concatenate([upper[:, 1], lower[::-1, 1], [upper[0, 1]]])

    return px, py


def foam_bounds(mesh, view_axis: str, margin_pct: float = 0.08):
    """
    Kesim icin kopuk blok sinirlarini dondur: (h_min, h_max, v_min, v_max)
    Eksen yonelimi extract_profile ile tutarli.
    """
    v = mesh.vertices
    h_idx, v_idx = _proj_axes(mesh, view_axis)
    h  = v[:, h_idx]
    vv = v[:, v_idx]
    m_h = (h.max() - h.min()) * margin_pct
    m_v = (vv.max() - vv.min()) * margin_pct
    return (h.min() - m_h, h.max() + m_h,
            vv.min() - m_v, vv.max() + m_v)
