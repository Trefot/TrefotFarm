"""Clics y arrastres. Usan el raton real, asi que mientras el bot corre no muevas el raton.

Seguridad: llevar el raton a una esquina de la pantalla detiene pyautogui (FailSafe).
"""

import random
import time

import pyautogui
import win32api
import win32con

from lumen.control import control

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0

# Pequena variacion aleatoria para no clicar siempre en el mismo pixel exacto.
JITTER_PX = 2
DURACION_CLIC = 0.12  # segundos con el boton pulsado


def _punto(objetivo, origen) -> tuple[int, int]:
    """Acepta un rectangulo (x, y, w, h) o un punto (x, y) relativo a la ventana."""
    if len(objetivo) == 4:
        x, y, w, h = objetivo
        x, y = x + w // 2, y + h // 2
    else:
        x, y = objetivo
    return int(x + origen[0]), int(y + origen[1])


def apuntar(objetivo, origen) -> None:
    """Deja el raton encima del objetivo sin pulsar (para pulsar luego en el instante justo)."""
    control.revisar()
    pyautogui.moveTo(*_punto(objetivo, origen))


def pulsar() -> None:
    """Pulsa donde este el raton, sin moverlo ni esperar antes (ver ``apuntar``)."""
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
    time.sleep(DURACION_CLIC)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
    control.actividad()


def clic_rapido(objetivo, origen) -> None:
    """Clic como el de AutoFarming: mover, la pausa de pyautogui (0.1 s) y pulsacion de 0.01 s.
    Para aceptar invitaciones de tiempo real: con este clic su bot siempre entraba (ver modos/indura)."""
    control.revisar()
    pyautogui.moveTo(*_punto(objetivo, origen))
    time.sleep(0.1)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
    time.sleep(0.01)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
    control.actividad()


def clic(objetivo, origen, espera: float = 0.05, jitter: int = JITTER_PX):
    control.revisar()
    x, y = _punto(objetivo, origen)
    if jitter:
        x += random.randint(-jitter, jitter)
        y += random.randint(-jitter, jitter)
    pyautogui.moveTo(x, y)
    time.sleep(0.05)  # que el juego "vea" el raton encima antes de pulsar
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
    # En la primera pelea real, pulsaciones de 30-70 ms se perdian a menudo: ~120 ms entran siempre.
    time.sleep(DURACION_CLIC + random.random() * 0.04)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
    control.actividad()
    if espera:
        control.esperar(espera)


def tecla(nombre: str, espera: float = 0.5):
    """Pulsa una tecla en el juego (p. ej. "esc" para volver atras, como AutoFarming)."""
    control.revisar()
    pyautogui.press(nombre)
    control.actividad()
    control.esperar(espera)


def arrastrar(desde, hasta, origen, duracion: float = 0.4):
    control.revisar()
    x1, y1 = _punto(desde, origen)
    x2, y2 = _punto(hasta, origen)
    pyautogui.moveTo(x1, y1)
    time.sleep(0.05)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
    time.sleep(DURACION_CLIC)  # que el juego "agarre" la carta antes de moverla
    pasos = max(10, int(duracion * 60))
    for i in range(1, pasos + 1):
        t = i / pasos
        pyautogui.moveTo(int(x1 + (x2 - x1) * t), int(y1 + (y2 - y1) * t))
        time.sleep(duracion / pasos)
    time.sleep(0.1)  # soltar quieto sobre el destino
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
    control.actividad()
    control.esperar(0.15)
