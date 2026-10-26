"""Encontrar, ajustar y capturar la ventana del juego (Windows)."""

import ctypes
import threading
import time
from ctypes import wintypes

import numpy as np
import win32con
import win32gui
import win32ui

from trefot import config

_lock = threading.RLock()

# Los recortes del borde los hereda el proyecto original: 2 px a los lados y 20 abajo.
BORDE_LATERAL = 2
BORDE_INFERIOR = 20


class VentanaNoEncontrada(RuntimeError):
    pass


def buscar_ventana() -> int:
    return win32gui.FindWindow(None, config.obtener("titulo_ventana"))


def ventana_abierta() -> bool:
    return buscar_ventana() != 0


def _region() -> tuple[tuple[int, int], int, int]:
    hwnd = buscar_ventana()
    if not hwnd:
        raise VentanaNoEncontrada(f"No encuentro la ventana '{config.obtener('titulo_ventana')}'. ¿Esta abierto el juego?")
    izq, arr, der, aba = win32gui.GetWindowRect(hwnd)
    ancho = der - izq - BORDE_LATERAL * 2
    alto = aba - arr - BORDE_INFERIOR
    if ancho <= 0 or alto <= 0:
        raise VentanaNoEncontrada("La ventana del juego esta minimizada.")
    return (izq, arr), ancho, alto


def _capturar_region(origen: tuple[int, int], ancho: int, alto: int) -> np.ndarray:
    escritorio = win32gui.GetDesktopWindow()
    hdc = win32gui.GetWindowDC(escritorio)
    dc = win32ui.CreateDCFromHandle(hdc)
    mem = dc.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap()
    try:
        bmp.CreateCompatibleBitmap(dc, ancho, alto)
        mem.SelectObject(bmp)
        mem.BitBlt((0, 0), (ancho, alto), dc, origen, win32con.SRCCOPY)
        datos = bmp.GetBitmapBits(True)
        img = np.frombuffer(datos, dtype=np.uint8).reshape(alto, ancho, 4)
        return np.ascontiguousarray(img[..., :3])
    finally:
        win32gui.DeleteObject(bmp.GetHandle())
        mem.DeleteDC()
        dc.DeleteDC()
        win32gui.ReleaseDC(escritorio, hdc)


def capturar() -> tuple[np.ndarray, tuple[int, int]]:
    """Captura de la ventana del juego (BGR) y la esquina superior izquierda en pantalla.

    Se copia desde el escritorio, asi que la ventana tiene que estar visible (no tapada).
    """
    with _lock:
        ultimo_error = None
        for _ in range(3):
            try:
                origen, ancho, alto = _region()
                return _capturar_region(origen, ancho, alto), origen
            except VentanaNoEncontrada:
                raise
            except Exception as error:  # fallos puntuales de GDI
                ultimo_error = error
                time.sleep(0.05)
        raise RuntimeError(f"No pude capturar la ventana: {ultimo_error}")


def tamano_actual() -> tuple[int, int] | None:
    hwnd = buscar_ventana()
    if not hwnd:
        return None
    izq, arr, der, aba = win32gui.GetClientRect(hwnd)
    return der - izq, aba - arr


def _tamano_exterior(hwnd: int, ancho: int, alto: int) -> tuple[int, int]:
    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    rect = RECT(0, 0, ancho, alto)
    estilo = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
    estilo_ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    user32 = ctypes.windll.user32
    hecho = False
    if hasattr(user32, "GetDpiForWindow") and hasattr(user32, "AdjustWindowRectExForDpi"):
        dpi = user32.GetDpiForWindow(wintypes.HWND(hwnd))
        hecho = bool(user32.AdjustWindowRectExForDpi(ctypes.byref(rect), estilo, False, estilo_ex, dpi))
    if not hecho:
        user32.AdjustWindowRectEx(ctypes.byref(rect), estilo, False, estilo_ex)
    return rect.right - rect.left, rect.bottom - rect.top


def es_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


AVISO_ADMIN = (
    "Windows no deja tocar la ventana del juego porque el juego corre como administrador. "
    "Cierra TrefotFarm y vuelve a abrirlo aceptando el aviso de administrador."
)

ultimo_error = ""  # motivo del ultimo ajuste fallido, para mostrarlo en la interfaz


def ajustar_tamano() -> bool:
    """Deja el area del juego en el tamano para el que estan hechas las coordenadas (540x960).

    Nunca lanza excepciones: si falla devuelve False y deja el motivo en ``ultimo_error``.
    """
    global ultimo_error
    ancho, alto = config.obtener("ancho_ventana"), config.obtener("alto_ventana")
    with _lock:
        hwnd = buscar_ventana()
        if not hwnd:
            ultimo_error = f"No encuentro la ventana '{config.obtener('titulo_ventana')}'."
            return False
        try:
            izq, arr, _, _ = win32gui.GetWindowRect(hwnd)
            ext_ancho, ext_alto = _tamano_exterior(hwnd, ancho, alto)
            # Que quede dentro de la pantalla
            pantalla_alto = ctypes.windll.user32.GetSystemMetrics(1)
            arr = max(0, min(arr, pantalla_alto - ext_alto))
            izq = max(0, izq)
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, izq, arr, ext_ancho, ext_alto, win32con.SWP_SHOWWINDOW)
        except win32gui.error as error:
            ultimo_error = AVISO_ADMIN if error.winerror == 5 and not es_admin() else f"No pude ajustar la ventana: {error.strerror}"
            return False
        time.sleep(0.3)
        actual = tamano_actual()
        if actual is not None and abs(actual[0] - ancho) <= 4 and abs(actual[1] - alto) <= 4:
            ultimo_error = ""
            return True
        ultimo_error = f"La ventana quedo en {actual[0]}x{actual[1]} en vez de {ancho}x{alto}." if actual else "La ventana se cerro."
        return False


def traer_al_frente() -> None:
    hwnd = buscar_ventana()
    if hwnd:
        try:
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
        except win32gui.error:
            pass
