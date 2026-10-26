"""Conecta el bot (hilo de trabajo) con la interfaz mediante senales de Qt, y las teclas globales."""

import threading
import traceback

from PyQt5.QtCore import QObject, pyqtSignal

from trefot import config
from trefot.control import control
from trefot.rutas import LOGS


class Puente(QObject):
    log = pyqtSignal(str, str)
    estado = pyqtSignal(str)
    stats = pyqtSignal(dict)
    terminado = pyqtSignal()
    tecla = pyqtSignal(str)  # "pausa" | "detener"

    def __init__(self):
        super().__init__()
        control.al_log = lambda m, n: self.log.emit(m, n)
        control.al_estado = lambda e: self.estado.emit(e)
        control.al_stats = lambda s: self.stats.emit(s)
        self.hilo: threading.Thread | None = None
        self._teclado = None

    @property
    def corriendo(self) -> bool:
        return self.hilo is not None and self.hilo.is_alive()

    def iniciar(self, modo):
        control.reiniciar()

        def correr():
            try:
                modo.ejecutar()
            except Exception as error:  # que un fallo no tumbe la interfaz
                control.log(f"Error inesperado: {error}", "error")
                with (LOGS / "errores.log").open("a", encoding="utf-8") as f:
                    f.write(traceback.format_exc() + "\n")
                control.log("Detalle guardado en logs/errores.log", "error")
            finally:
                self.terminado.emit()

        self.hilo = threading.Thread(target=correr, daemon=True, name="bot")
        self.hilo.start()

    # ------------------------------------------------------------ teclas globales
    def escuchar_teclas(self):
        try:
            from pynput import keyboard
        except ImportError:
            control.log("pynput no esta instalado: sin teclas rapidas.", "aviso")
            return
        if self._teclado:
            self._teclado.stop()

        def nombre(tecla) -> str:
            return getattr(tecla, "name", None) or getattr(tecla, "char", "") or ""

        def al_pulsar(tecla):
            n = (nombre(tecla) or "").lower()
            if n == str(config.obtener("tecla_pausa")).lower():
                self.tecla.emit("pausa")
            elif n == str(config.obtener("tecla_detener")).lower():
                self.tecla.emit("detener")

        self._teclado = keyboard.Listener(on_press=al_pulsar)
        self._teclado.daemon = True
        self._teclado.start()
