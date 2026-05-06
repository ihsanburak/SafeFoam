# SafeFoam v4

Desktop CAM software for 4-axis CNC hot-wire foam cutters.

SafeFoam loads STL/OBJ wing or foam-part models, previews the selected cut axis,
simulates the hot-wire path, and exports GRBL-compatible G-code.

Developer: Captain21  
Contact: ihsanburakgoksin@gmail.com

## Highlights

- STL / OBJ / PLY / 3MF model import
- PrusaSlicer-style single-screen workflow
- 3D model viewport with fit, pan, zoom, orbit, and view presets
- Axis-based profile extraction for hot-wire cutting
- 2D cut path simulation with play/step controls
- Carbon tube hole pass support
- Turkish / English UI switch
- GRBL-style G-code export for synchronized tower movement
- Windows EXE build via PyInstaller

## Basic Workflow

1. Open a 3D model with `Dosya Ac... / Open File...`.
2. Select the cut axis.
   - `X` is normally the wing profile cut.
   - `Y` is useful for planform / top view.
   - `Z` is mostly a chord/control section for this wing orientation.
3. Click `Onizle / Slice` to preview the 2D wire path.
4. Use the simulation controls to inspect the cut.
5. Click `G-Code Uret & Kaydet` to export a `.nc` file.

## Running From Source

```bash
git clone https://github.com/ihsanburak/SafeFoam
cd SafeFoam
pip install -r requirements.txt
python main.py
```

## Building the Windows EXE

```bash
pip install -r requirements.txt pyinstaller
python -m PyInstaller SafeFoam.spec --clean --noconfirm
```

The standalone executable will be created at:

```text
dist/SafeFoam.exe
```

Users who do not have Python installed can download `SafeFoam.exe` from the
GitHub Releases page and run it directly on Windows.

## Hardware Target

SafeFoam is designed around typical 4-axis hot-wire foam cutter builds such as:

- Arduino Mega 2560 + RAMPS 1.4
- 4 stepper motors, two synchronized towers
- GRBL hot-wire firmware variants
- Universal Gcode Sender or similar G-code sender

Default axis mapping:

| Axis | Function |
|---|---|
| X | Left tower horizontal |
| Y | Left tower vertical |
| A | Right tower horizontal |
| B | Right tower vertical |

## Notes

The current v4 viewport is built with Tkinter and Matplotlib. It is practical and
portable, but a future OpenGL viewport would make orbit/pan/zoom feel closer to
professional slicers and CAD tools.

## License

MIT
