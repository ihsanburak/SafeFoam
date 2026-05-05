import sys
import os

# core ve ui import yollarini ekle
sys.path.insert(0, os.path.dirname(__file__))

from ui.app import FoamCutterApp

if __name__ == "__main__":
    app = FoamCutterApp()
    app.mainloop()
