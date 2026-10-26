"""TrefotFarm v2 - arranque de la interfaz. Doble clic en 'TrefotFarm.bat' o en este archivo."""

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)

import trefot.entrada  # noqa: E402,F401  (pyautogui activa el modo DPI-aware antes que Qt)
from PyQt5.QtCore import Qt  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from trefot.gui import tema  # noqa: E402
from trefot.gui.principal import VentanaPrincipal  # noqa: E402


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setApplicationName("TrefotFarm")
    app.setStyleSheet(tema.HOJA)
    principal = VentanaPrincipal()
    principal.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
