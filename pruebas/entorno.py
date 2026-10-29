"""Entorno comun de las pruebas: se importa antes que nada de lumen.

- Simula los modulos de Windows (raton, teclado, ventanas, OCR): las pruebas nunca mueven el raton
  ni tocan el juego, y funcionan tambien fuera de Windows.
- La interfaz se abre sin pantalla (Qt "offscreen").
- config.yaml no se toca: los ajustes viven en memoria mientras corren las pruebas.
"""

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

for nombre in ("pyautogui", "pynput", "pynput.keyboard", "pynput.mouse", "win32gui", "win32ui", "win32con",
               "win32api", "win32process", "win32com", "win32com.client", "pywintypes"):
    sys.modules[nombre] = mock.MagicMock()

from lumen import config  # noqa: E402
from lumen.control import control  # noqa: E402

control.al_log = lambda mensaje, nivel: None  # el registro del bot no ensucia la salida de las pruebas

_ajustes = dict(config.POR_DEFECTO)
config.obtener = lambda clave, defecto=None: _ajustes.get(clave, defecto)
config.guardar = lambda cambios: _ajustes.update(cambios)
config.todo = lambda: dict(_ajustes)


from lumen import metas  # noqa: E402

metas._vincular = lambda: None  # las pruebas no tocan el catalogo del botin


TEMPORAL = Path(tempfile.mkdtemp(prefix="lumen_pruebas_"))  # archivos que escriben las pruebas (se borra al acabar)
atexit.register(shutil.rmtree, TEMPORAL, True)


def ajustes() -> dict:
    """Los ajustes en memoria (para prepararlos o mirarlos en una prueba)."""
    return _ajustes


class PlantillaFalsa:
    """Sustituye a una imagen del juego: "esta" si su nombre aparece en la pantalla simulada (un set)."""

    def __init__(self, nombre: str):
        self.nombre = nombre

    def esta(self, pantalla, *_):
        return bool(pantalla) and self.nombre in pantalla

    def buscar(self, pantalla, *_):
        return (1, 1, 2, 2) if self.esta(pantalla) else None


_app = None


def app_qt():
    """La QApplication de las pruebas de interfaz (una sola para todas)."""
    global _app
    from PyQt5.QtWidgets import QApplication

    _app = QApplication.instance() or QApplication([])
    from lumen.gui import tema

    _app.setStyleSheet(tema.HOJA)
    return _app
