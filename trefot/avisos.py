"""Avisos al movil con ntfy.sh (opcional). Instala la app ntfy y suscribete a tu canal."""

import threading

import cv2
import requests

from trefot import config


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
                    requests.put(url, data=png.tobytes(), headers={"Filename": "captura.png", "Message": mensaje}, timeout=15)
                    return
            requests.post(url, data=mensaje.encode("utf-8"), timeout=15)
        except requests.RequestException:
            pass

    threading.Thread(target=_enviar, daemon=True).start()
