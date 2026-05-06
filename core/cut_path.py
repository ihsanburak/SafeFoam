"""
Kesim yolu degisiklikleri — karbon tup delik gecisi.
"""
import numpy as np


def insert_hole_traversal(px: np.ndarray, py: np.ndarray,
                          holes: list) -> tuple:
    """
    Kapali airfoil konturuna karbon tup delik gecisi ekle.

    px, py  : airfoil profil koordinatlari (kapali kontur, mm)
    holes   : [(hx, hy, hr), ...]  delik merkez + yariçap listesi
              hx = yatay (veter yonu), hy = dikey (kalinlik yonu), hr = yariçap

    Algoritma:
    1. Delikleri hx'e gore siralar
    2. Ilk deligin hx konumunda alt yuzeye en yakin profil noktasini bulur
    3. Alt yuzeyden delik 1 merkezine iner (giris kanali)
    4. Delik 1 -> 2 -> 3 arasi gecis (ileri)
    5. Delik 3 -> 2 -> 1 geri donus
    6. Kanaldan alt yuzeye cikar
    7. Profile devam eder

    Donus: (new_px, new_py)
    """
    if not holes:
        return px.copy(), py.copy()

    holes = sorted(holes, key=lambda h: h[0])
    first_hx, first_hy, first_hr = holes[0]

    # Alt yuzey: profildeki en dusuk py degerleri
    # Giris noktasini bul: first_hx'e yakin, en dusuk py
    tol = max(float(np.ptp(px)), 1.0) * 0.06
    near = np.abs(px - first_hx) < tol

    if not near.any():
        near_arr = np.array([int(np.argmin(np.abs(px - first_hx)))])
    else:
        near_arr = np.where(near)[0]

    entry_idx = int(near_arr[np.argmin(py[near_arr])])
    ex = float(px[entry_idx])
    ey = float(py[entry_idx])   # alt yuzey Y degeri giris noktasinda

    # Kanal + delik gecis yolu
    sub_x = [ex, ex]               # alt yuzey giris noktasi (iki kez — yumusak giris)
    sub_y = [ey, first_hy]         # alt yuzeyden delik 1 merkezine in

    # Ileri gecis: delik 1 zaten var, 2. delikten baslayarak ilerle
    for hx, hy, _ in holes[1:]:
        sub_x.append(hx)
        sub_y.append(hy)

    # Geri donus: son delikten delik 1'e
    for hx, hy, _ in reversed(holes[1:]):
        sub_x.append(hx)
        sub_y.append(hy)

    # Delik 1 merkezinden alt yuzeye cik
    sub_x += [ex, ex]
    sub_y += [first_hy, ey]

    new_px = np.concatenate([px[:entry_idx + 1], sub_x, px[entry_idx:]])
    new_py = np.concatenate([py[:entry_idx + 1], sub_y, py[entry_idx:]])

    return new_px, new_py
