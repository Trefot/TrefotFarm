"""Control de ejecucion compartido entre el bot (hilo de trabajo) y la interfaz.

El bot nunca usa time.sleep directamente: usa ``control.esperar()``, que respeta la pausa y
lanza ``Detenido`` en cuanto se pide parar. Asi el boton Detener responde al instante.
"""

import threading
import time
from collections.abc import Callable


class Detenido(Exception):
    """Se pidio detener el bot."""


class Control:
    def __init__(self):
        self._detener = threading.Event()
        self._pausa = threading.Event()
        self.al_log: Callable[[str, str], None] = lambda msg, nivel: print(f"[{nivel}] {msg}")
        self.al_estado: Callable[[str], None] = lambda estado: None
        self.al_stats: Callable[[dict], None] = lambda stats: None
        self.ultima_actividad = time.time()  # lo usa el vigilante de atascos
        self.estado_actual = ""
        self.parar_en_zona_segura = False  # p. ej. hay una actualizacion: terminar la pelea y parar

    # ------------------------------------------------------------- ordenes de la interfaz
    def detener(self):
        self._detener.set()
        self._pausa.clear()

    def pausar(self):
        self._pausa.set()

    def reanudar(self):
        self._pausa.clear()
        self.ultima_actividad = time.time()

    @property
    def en_pausa(self) -> bool:
        return self._pausa.is_set()

    @property
    def detenido(self) -> bool:
        return self._detener.is_set()

    def reiniciar(self):
        self._detener.clear()
        self._pausa.clear()
        self.parar_en_zona_segura = False
        self.ultima_actividad = time.time()

    # --------------------------------------------------------------------- uso del bot
    def revisar(self):
        """Punto de control: espera si hay pausa y corta si se pidio detener."""
        if self._detener.is_set():
            raise Detenido()
        if self._pausa.is_set():
            self.log("En pausa...", "aviso")
            while self._pausa.is_set():
                if self._detener.wait(0.2):
                    raise Detenido()
            self.log("Reanudado.", "ok")
            self.ultima_actividad = time.time()

    def esperar(self, segundos: float):
        self.revisar()
        if self._detener.wait(max(0.0, segundos)):
            raise Detenido()
        self.revisar()

    def log(self, mensaje: str, nivel: str = "info"):
        self.al_log(mensaje, nivel)

    def estado(self, nombre: str):
        if nombre != self.estado_actual:
            self.estado_actual = nombre
            self.ultima_actividad = time.time()
            self.al_estado(nombre)

    def actividad(self):
        self.ultima_actividad = time.time()


# Instancia unica: la usan la entrada (clics) y los modos.
control = Control()
