"""Ordenes desde el movil por ntfy: escribes 'estado', 'pausar', 'captura'... en el canal y el bot
responde en el mismo canal. Se activa en Ajustes ("Aceptar ordenes desde el movil").

Los mensajes que manda el propio bot llevan la etiqueta ``avisos.ETIQUETA`` y aqui se ignoran,
asi el bot no se lee a si mismo.
"""

import json
import threading
import time
from collections.abc import Callable

import requests

from lumen import avisos, config

ORDENES = {
    "estado": "que esta haciendo el bot y como va",
    "iniciar": "empieza a farmear con el modo elegido en Farmear",
    "plan": "empieza el plan del dia (Farmear -> Plan)",
    "plan ver": "las tareas del plan y por cual va",
    "saltar": "deja la tarea del plan en curso y pasa a la siguiente",
    "prueba": "prueba rapida: 1 victoria de cada modo listo y un informe",
    "diario": "resumen del diario de peleas del modo elegido (para el analista)",
    "pausar": "pausa el bot",
    "reanudar": "sigue despues de una pausa",
    "detener": "detiene el bot",
    "captura": "foto de la pantalla del juego",
    "ayuda": "esta lista",
}
SINONIMOS = {"start": "iniciar", "empezar": "iniciar", "pausa": "pausar", "seguir": "reanudar",
             "parar": "detener", "stop": "detener", "foto": "captura", "status": "estado", "?": "ayuda",
             "tareas": "plan ver", "skip": "saltar", "siguiente": "saltar", "test": "prueba"}


def texto_ayuda() -> str:
    return "Ordenes de LumenFarm:\n" + "\n".join(f"• {o}: {d}" for o, d in ORDENES.items())


def interpretar(texto: str) -> str | None:
    palabras = (texto or "").strip().lower().split()
    if not palabras:
        return None
    if palabras[0] == "plan" and len(palabras) > 1 and palabras[1] in ("ver", "lista", "?"):
        return "plan ver"
    orden = SINONIMOS.get(palabras[0], palabras[0])
    return orden if orden in ORDENES else None


class Escucha:
    """Hilo que lee el canal de ntfy y llama a ``al_recibir(orden)`` con cada orden valida."""

    def __init__(self, al_recibir: Callable[[str], None]):
        self.al_recibir = al_recibir
        self._hilo: threading.Thread | None = None
        self._parar = threading.Event()

    def aplicar_ajustes(self):
        """Arranca o para la escucha segun config (llamar al abrir y al guardar Ajustes)."""
        activa = bool(config.obtener("ntfy_ordenes")) and bool((config.obtener("ntfy_canal") or "").strip())
        if activa:
            self._parar.clear()  # si el hilo anterior aun no habia salido, sigue con el
        if activa and not (self._hilo and self._hilo.is_alive()):
            self._hilo = threading.Thread(target=self._bucle, daemon=True, name="ordenes")
            self._hilo.start()
        elif not activa:
            self._parar.set()

    def _bucle(self):
        desde = str(int(time.time()))  # solo ordenes nuevas, no las de antes de abrir el programa
        canal = ""
        while not self._parar.is_set():
            nuevo = (config.obtener("ntfy_canal") or "").strip()
            if nuevo != canal:
                canal, desde = nuevo, str(int(time.time()))
            try:
                with requests.get(f"https://ntfy.sh/{canal}/json", params={"since": desde},
                                  stream=True, timeout=(10, 90)) as r:
                    r.raise_for_status()
                    for linea in r.iter_lines():
                        if self._parar.is_set():
                            return
                        if (config.obtener("ntfy_canal") or "").strip() != canal:
                            break  # cambiaron el canal en Ajustes: reconectar
                        if not linea:
                            continue
                        msg = json.loads(linea)
                        if msg.get("event") != "message":
                            continue
                        desde = msg.get("id") or desde
                        if avisos.ETIQUETA in (msg.get("tags") or []):
                            continue  # lo mando el propio bot
                        orden = interpretar(msg.get("message", ""))
                        if orden:
                            self.al_recibir(orden)
                        else:
                            avisos.enviar("No entiendo esa orden. Escribe 'ayuda' para ver la lista.")
            except (requests.RequestException, ValueError):
                pass  # sin internet o corte de la conexion: se reintenta
            self._parar.wait(5)
