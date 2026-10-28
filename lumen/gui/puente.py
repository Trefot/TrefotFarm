"""Conecta el bot (hilo de trabajo) con la interfaz mediante senales de Qt, y las teclas globales."""

import threading
import time
import traceback

from PyQt5.QtCore import QObject, pyqtSignal

from lumen import avisos, config, informe, ordenes, ventana
from lumen.control import control
from lumen.rutas import LOGS


class Puente(QObject):
    log = pyqtSignal(str, str)
    estado = pyqtSignal(str)
    stats = pyqtSignal(dict)
    terminado = pyqtSignal()
    tecla = pyqtSignal(str)  # "pausa" | "detener"
    orden = pyqtSignal(str)  # una orden del movil (ver lumen/ordenes.py)

    def __init__(self):
        super().__init__()
        control.al_log = self._registrar
        control.al_estado = lambda e: self.estado.emit(e)
        control.al_stats = lambda s: self.stats.emit(s)
        self.hilo: threading.Thread | None = None
        self._teclado = None
        self._archivo = None  # logs/sesion_<fecha>.log de la sesion en curso (incluye el detalle)
        self._lock_archivo = threading.Lock()
        self.escucha = ordenes.Escucha(lambda o: self.orden.emit(o))
        self.ultimo_error: str | None = None  # el error que paro la ultima sesion (None = acabo bien)

    def _registrar(self, mensaje: str, nivel: str):
        informe.anotar(mensaje, nivel)
        with self._lock_archivo:
            if self._archivo:
                self._archivo.write(f"{time.strftime('%H:%M:%S')} [{nivel}] {mensaje}\n")
                self._archivo.flush()
        self.log.emit(mensaje, nivel)

    @property
    def corriendo(self) -> bool:
        return self.hilo is not None and self.hilo.is_alive()

    def iniciar(self, modo):
        control.reiniciar()
        self.ultimo_error = None
        with self._lock_archivo:
            self._archivo = (LOGS / f"sesion_{time.strftime('%Y%m%d_%H%M%S')}.log").open("a", encoding="utf-8")

        def correr():
            try:
                modo.ejecutar()
            except Exception as error:  # que un fallo no tumbe la interfaz
                control.log(f"Error inesperado: {error}", "error")
                with (LOGS / "errores.log").open("a", encoding="utf-8") as f:
                    f.write(traceback.format_exc() + "\n")
                control.log("Detalle guardado en logs/errores.log", "error")
                self.ultimo_error = informe.resumen_error(error)
                try:
                    pantalla, _ = ventana.capturar()
                except Exception:
                    pantalla = None
                avisos.enviar(informe.texto_error(modo, error), pantalla)  # para copiarlo desde el movil
            finally:
                with self._lock_archivo:
                    if self._archivo:
                        self._archivo.close()
                        self._archivo = None
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
