import numpy as np


def naca4(code: str, n_points: int = 100):
    """
    NACA 4-digit airfoil koordinatlarini uret.
    Donus: (x, y) normalized [0..1] — TE ust'ten LE'ye, LE'den TE alt'a.
    """
    code = code.strip().upper().replace("NACA", "").strip()
    if len(code) != 4 or not code.isdigit():
        raise ValueError(f"Gecersiz NACA kodu: '{code}' — ornek: 2412, 0012")

    m = int(code[0]) / 100.0   # max camber
    p = int(code[1]) / 10.0    # camber konumu
    t = int(code[2:]) / 100.0  # max kalinlik

    # Kosinüs araliklamasi — LE etrafinda daha fazla nokta
    beta = np.linspace(0, np.pi, n_points)
    x = 0.5 * (1 - np.cos(beta))

    # Kalinlik dagitimi (NACA formulu)
    yt = 5 * t * (0.2969 * np.sqrt(x)
                  - 0.1260 * x
                  - 0.3516 * x**2
                  + 0.2843 * x**3
                  - 0.1015 * x**4)

    if m == 0 or p == 0:
        # Simetrik profil
        xu, yu = x, yt
        xl, yl = x, -yt
    else:
        # Kamburlu profil
        yc = np.where(
            x < p,
            m / p**2 * (2 * p * x - x**2),
            m / (1 - p)**2 * ((1 - 2 * p) + 2 * p * x - x**2)
        )
        dyc = np.where(
            x < p,
            2 * m / p**2 * (p - x),
            2 * m / (1 - p)**2 * (p - x)
        )
        theta = np.arctan(dyc)
        xu = x - yt * np.sin(theta)
        yu = yc + yt * np.cos(theta)
        xl = x + yt * np.sin(theta)
        yl = yc - yt * np.cos(theta)

    # Birlesik profil: ust TE→LE, alt LE→TE (kesici yolu)
    x_out = np.concatenate([xu[::-1], xl[1:]])
    y_out = np.concatenate([yu[::-1], yl[1:]])
    return x_out, y_out


def scale_and_twist(x: np.ndarray, y: np.ndarray,
                    chord: float, twist_deg: float = 0.0):
    """
    Normalize profili gercek olcege (mm) cevir ve twist uygula.
    Twist ekseni: veter/4 noktasi.
    """
    xs = x * chord
    ys = y * chord

    if twist_deg != 0.0:
        angle = np.radians(twist_deg)
        c, s = np.cos(angle), np.sin(angle)
        cx = 0.25 * chord
        xs, ys = cx + (xs - cx) * c - ys * s, (xs - cx) * s + ys * c

    return xs, ys


def get_profile(naca_code: str, chord: float,
                twist_deg: float = 0.0, n_points: int = 100):
    """Ana yardimci: NACA kodu + olcek + twist → (x, y) mm."""
    x, y = naca4(naca_code, n_points)
    return scale_and_twist(x, y, chord, twist_deg)


def get_surfaces(naca_code: str, chord: float,
                 twist_deg: float = 0.0, n_points: int = 100):
    """
    Ust ve alt yüzeyleri ayri dondur.
    Donus: (x_upper, y_upper, x_lower, y_lower) — LE→TE yonunde.
    """
    x, y = naca4(naca_code, n_points)
    # naca4 cikarisi: [ust TE→LE (n nokta)] + [alt LE→TE (n-1 nokta)]
    n = n_points
    x_upper = x[:n][::-1]   # LE→TE
    y_upper = y[:n][::-1]
    x_lower = x[n - 1:]     # LE→TE
    y_lower = y[n - 1:]
    x_u, y_u = scale_and_twist(x_upper, y_upper, chord, twist_deg)
    x_l, y_l = scale_and_twist(x_lower, y_lower, chord, twist_deg)
    return x_u, y_u, x_l, y_l
