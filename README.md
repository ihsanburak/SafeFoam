# SafeFoam — CNC Hot Wire Foam Cutter CAM

**SafeFoam** is a desktop CAM application for 4-axis CNC hot wire foam cutters.  
It generates GRBL-compatible G-code to cut RC airplane wings and fuselage sections from foam (EPS/EPP/XPS).

![SafeFoam Screenshot](screenshots/preview.png)

---

## Features

- **NACA 4-digit airfoil generator** — built-in, no external files needed
- **4-axis wing G-code** — root and tip profiles move independently for tapered/twisted wings
- **Supports tapered wings** (different chord at root and tip)
- **Washout / twist** — per-section twist angle
- **3D wing surface preview** — real-time visualization before cutting
- **Lead-in / lead-out** — smooth wire entry and exit
- **Configurable axis mapping** — works with any GRBL axis layout (X/Y/A/B etc.)

---

## Screenshots

| Profile comparison | 3D wing surface |
|---|---|
| ![profiles](screenshots/profiles.png) | ![wing3d](screenshots/wing3d.png) |

---

## Download

**[⬇ Download SafeFoam.exe (Windows)](../../releases/latest)** — no Python required

---

## Usage

### Option A — Run the EXE (Windows, no install)
1. Download `SafeFoam.exe` from [Releases](../../releases/latest)
2. Double-click — no installation needed

### Option B — Run from source
```bash
git clone https://github.com/ihsanburak/SafeFoam
cd SafeFoam
pip install -r requirements.txt
python main.py
```

### Workflow
1. Enter wing parameters (NACA code, chord lengths, span, twist)
2. Click **Önizle** to see the 3D wing shape
3. Click **G-Code Üret & Kaydet** → save `.nc` file
4. Open the `.nc` file in **Universal Gcode Sender (UGS)**
5. Connect to your machine (GRBL firmware) and cut

---

## Wing Parameters

| Parameter | Description |
|---|---|
| Kök NACA | Root airfoil NACA code (e.g. `2412`, `0012`, `6409`) |
| Uç NACA | Tip airfoil — can differ from root for washout profiles |
| Kök veter | Root chord length in mm |
| Uç veter | Tip chord length in mm |
| Açıklık | Wing span / foam block length in mm |
| Kök / Uç twist | Twist angle in degrees (negative = washout, typical: 0° root, -2° tip) |

---

## Hardware & Firmware

Designed for machines based on:
- **Arduino Mega 2560** + **RAMPS 1.4**
- **4× NEMA17 stepper motors** (2 per tower)
- **Firmware:** [GRBL 0.8c MEGA RAMPS](https://github.com/eugenober/GRBL0.8cMEGARAMPS) — 4-axis hot wire edition
- **PC sender:** [Universal Gcode Sender (UGS)](https://universalgcodesender.com/)

Reference build: [4-Axis CNC Hotwire by Dodo3441 on Thingiverse](https://www.thingiverse.com/thing:3676825)

### Default axis mapping
| Axis | Function |
|---|---|
| X | Left tower — horizontal (chord direction) |
| Y | Left tower — vertical (thickness direction) |
| A | Right tower — horizontal |
| B | Right tower — vertical |

---

## How 4-Axis Cutting Works

```
Left tower (X, Y)        Hot wire        Right tower (A, B)
   Root profile ←——————————/———————————→ Tip profile
   (larger chord)       synchronized     (smaller chord)
```

The wire interpolates between root and tip as it cuts — allowing tapered, twisted wings in a single pass.

---

## Roadmap

- [ ] DXF profile import (from Fusion 360)
- [ ] 2-pass cutting mode (planform + profile)
- [ ] Delta wing sweep parameter
- [ ] Serial port / direct GRBL control
- [ ] Fuselage half-section mode

---

## Requirements

- Python 3.10+
- numpy
- matplotlib
- ezdxf (for future DXF import)

---

## License

MIT © ihsanburak
