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

    def add_hole_loop(xs, ys, hx, hy, hr, n=48):
        # Merkezden cembere cik, deligi tam tur kes, merkeze geri don.
        angles = np.linspace(0, 2 * np.pi, n, endpoint=True)
        xs.append(hx + hr)
        ys.append(hy)
        xs.extend((hx + hr * np.cos(angles)).tolist())
        ys.extend((hy + hr * np.sin(angles)).tolist())
        xs.append(hx)
        ys.append(hy)

    # Kanal + delik kesim yolu:
    # profile giris -> ilk delik merkezi -> delik cemberleri -> ayni kanaldan cikis.
    sub_x = [ex, ex, first_hx]
    sub_y = [ey, first_hy, first_hy]

    for hx, hy, hr in holes:
        if sub_x[-1] != hx or sub_y[-1] != hy:
            sub_x.append(hx)
            sub_y.append(hy)
        add_hole_loop(sub_x, sub_y, hx, hy, hr)

    # Delikler arasi kesilen kanaldan geri don.
    for hx, hy, _ in reversed(holes[:-1]):
        sub_x.append(hx)
        sub_y.append(hy)

    # Ilk delik merkezinden ayni giris kanalina ve profile cik.
    sub_x += [ex, ex]
    sub_y += [first_hy, ey]

    new_px = np.concatenate([px[:entry_idx + 1], sub_x, px[entry_idx:]])
    new_py = np.concatenate([py[:entry_idx + 1], sub_y, py[entry_idx:]])

    return new_px, new_py
