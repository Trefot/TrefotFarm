"""TrefotFarm v2 - arranque de la interfaz. Doble clic en 'TrefotFarm.bat' o en este archivo.

El juego corre como administrador, y Windows no deja que un programa normal mueva su ventana
ni le haga clic. Por eso TrefotFarm se reabre como administrador (sale el aviso de Windows).
"""

import ctypes
import os
import sys
import time
import traceback
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)

SIN_ADMIN = "--sin-admin"  # para arrancar sin pedir permisos (pruebas)
YA_ELEVADO = "--elevado"


def reabrir_como_admin() -> bool:
    """Relanza este script con permisos de administrador. True si Windows lo acepto."""
    if SIN_ADMIN in sys.argv or YA_ELEVADO in sys.argv:
        return False
    try:
        if ctypes.windll.shell32.IsUserAnAdmin():
            return False
        resultado = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, f'"{Path(__file__).resolve()}" {YA_ELEVADO}', str(RAIZ), 1
        )
        return resultado > 32  # <= 32: el usuario dijo que no, o fallo
    except Exception:
        return False


if reabrir_como_admin():
    sys.exit(0)

import trefot.entrada  # noqa: E402,F401  (pyautogui activa el modo DPI-aware antes que Qt)
from PyQt5.QtCore import Qt  # noqa: E402
from PyQt5.QtWidgets import QApplication, QMessageBox  # noqa: E402

from trefot.gui import tema  # noqa: E402
from trefot.gui.principal import VentanaPrincipal  # noqa: E402
from trefot.rutas import LOGS  # noqa: E402


def error_inesperado(tipo, valor, tb):
    """Un fallo en la interfaz no debe cerrar el programa: se guarda y se avisa."""
    detalle = "".join(traceback.format_exception(tipo, valor, tb))
    try:
        with (LOGS / "errores.log").open("a", encoding="utf-8") as f:
            f.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')}\n{detalle}\n")
    except OSError:
        pass
    if QApplication.instance() is not None:
        QMessageBox.critical(None, "TrefotFarm - error", f"{valor}\n\nDetalle guardado en logs\\errores.log")


def main():
    sys.excepthook = error_inesperado
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setApplicationName("TrefotFarm")
    tema.cargar_fuentes()
    app.setStyleSheet(tema.HOJA)
    principal = VentanaPrincipal()
    principal.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
