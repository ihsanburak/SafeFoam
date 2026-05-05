"""
3D mesh import ve silhouette profil cikarimi.
Desteklenen formatlar: STL, OBJ, PLY, 3MF
"""
import numpy as np
from scipy.ndimage import uniform_filter1d


def load_mesh(filepath: str):
    """
    STL / OBJ / PLY dosyasini yukle, tek bir mesh olarak domdur.
    Merkezi otomatik olarak origina tasir.
    """
    import trimesh
    loaded = trimesh.load(filepath, force='mesh')
    if isinstance(loaded, trimesh.Scene):
        loaded = trimesh.util.concatenate(list(loaded.dump()))
    # Koordinat orijinine tasi
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


def extract_profile(mesh, view_axis: str = 'Y', n_bins: int = 300,
                    smooth: int = 9) -> tuple:
    """
    Mesh'i belirtilen eksenden projekte ederek kesim profili cikar.

    view_axis = 'Y'  : Yandan bak  → profil XZ duzleminde (kanat, govde yan)
    view_axis = 'X'  : Ondon bak   → profil YZ duzleminde
    view_axis = 'Z'  : Ustden bak  → profil XY duzleminde (planform)

    Donus: (px, py) — kapali kontur, mm cinsinden.
    Kesici tel bu konturun uzerinde hareket eder.
    """
    v = mesh.vertices

    # Hangi iki eksen kesim duzlemini olusturuyor?
    axis_map = {
        'Y': (v[:, 0], v[:, 2]),   # X yatay, Z dikey
        'X': (v[:, 1], v[:, 2]),   # Y yatay, Z dikey
        'Z': (v[:, 0], v[:, 1]),   # X yatay, Y dikey
    }
    h, vv = axis_map[view_axis]

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

    # Kapali kontur: ust sol→sag + alt sag→sol
    px = np.concatenate([upper[:, 0], lower[::-1, 0], [upper[0, 0]]])
    py = np.concatenate([upper[:, 1], lower[::-1, 1], [upper[0, 1]]])

    return px, py


def foam_bounds(mesh, view_axis: str, margin_pct: float = 0.08):
    """
    Kesim icin kopuk blok sinirlarini dondur.
    view_axis: hangi eksenden bakildigi
    Donus: (h_min, h_max, v_min, v_max)
    """
    v = mesh.vertices
    axis_map = {
        'Y': (v[:, 0], v[:, 2]),
        'X': (v[:, 1], v[:, 2]),
        'Z': (v[:, 0], v[:, 1]),
    }
    h, vv = axis_map[view_axis]
    m_h = (h.max() - h.min()) * margin_pct
    m_v = (vv.max() - vv.min()) * margin_pct
    return (h.min() - m_h,  h.max() + m_h,
            vv.min() - m_v, vv.max() + m_v)
