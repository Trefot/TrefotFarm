"""Avisos al movil con ntfy.sh (opcional). Instala la app ntfy y suscribete a tu canal."""

import threading

import cv2
import requests

from trefot import config

ETIQUETA = "trefotfarm"  # marca los mensajes del bot para que la escucha de ordenes los ignore


def enviar(mensaje: str, captura=None) -> None:
    canal = (config.obtener("ntfy_canal") or "").strip()
    if not canal:
        return

    def _enviar():
        url = f"https://ntfy.sh/{canal}"
        try:
            if captura is not None:
                ok, png = cv2.imencode(".png", captura)
                if ok:
                    # El texto va en la URL: en las cabeceras no caben acentos ni saltos de linea.
                    requests.put(url, data=png.tobytes(), params={"message": mensaje},
                                 headers={"Filename": "captura.png", "Tags": ETIQUETA}, timeout=15)
                    return
            requests.post(url, data=mensaje.encode("utf-8"), headers={"Tags": ETIQUETA}, timeout=15)
        except requests.RequestException:
            pass

    threading.Thread(target=_enviar, daemon=True).start()
