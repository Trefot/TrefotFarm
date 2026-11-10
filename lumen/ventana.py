"""Encontrar, ajustar y capturar la ventana del juego (Windows)."""

import ctypes
import ctypes.wintypes
import threading
import time

import cv2
import numpy as np
import win32con
import win32gui
import win32ui

from lumen import config

_lock = threading.RLock()

# Los recortes del borde los hereda el proyecto original: 2 px a los lados y 20 abajo.
BORDE_LATERAL = 2
BORDE_INFERIOR = 20


class VentanaNoEncontrada(RuntimeError):
    pass


# Pantallas bajas (p. ej. 1366x768): la ventana de 554x960 no cabe. Entonces se pone mas pequena, con la misma
# forma, y cada captura se agranda a la de referencia (las plantillas y coordenadas no cambian); los clics
# se convierten de vuelta. Medido en la ventana de referencia: la zona del juego (sin bordes ni barra de
# titulo) mide 538x921 y empieza en (8, 31) de la captura.
REF_CLIENTE = (538, 921)
REF_ORIGEN_CLIENTE = (8, 31)


class Origen(tuple):
    """Esquina de la captura en pantalla, (x, y). Con la ventana reducida tambien sabe convertir un punto de
    la captura (de referencia) al punto real de la pantalla y al reves."""

    def __new__(cls, xy, cliente=None, escala=(1.0, 1.0)):
        if cliente is not None:  # aproximado, para quien use origen[0] y origen[1] directamente
            xy = (round(cliente[0] - REF_ORIGEN_CLIENTE[0] * escala[0]),
                  round(cliente[1] - REF_ORIGEN_CLIENTE[1] * escala[1]))
        o = super().__new__(cls, (int(xy[0]), int(xy[1])))
        o.cliente, o.escala = cliente, escala
        return o

    @property
    def reducida(self) -> bool:
        return self.cliente is not None

    def a_pantalla(self, x: float, y: float) -> tuple[int, int]:
        if not self.reducida:
            return int(x + self[0]), int(y + self[1])
        return (int(round(self.cliente[0] + (x - REF_ORIGEN_CLIENTE[0]) * self.escala[0])),
                int(round(self.cliente[1] + (y - REF_ORIGEN_CLIENTE[1]) * self.escala[1])))

    def a_ventana(self, x: float, y: float) -> tuple[int, int]:
        if not self.reducida:
            return int(x - self[0]), int(y - self[1])
        return (int(round((x - self.cliente[0]) / self.escala[0] + REF_ORIGEN_CLIENTE[0])),
                int(round((y - self.cliente[1]) / self.escala[1] + REF_ORIGEN_CLIENTE[1])))


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


def capturar_pantalla() -> tuple[np.ndarray, tuple[int, int]]:
    """Captura de todas las pantallas juntas y su esquina superior izquierda (para buscar el lanzador)."""
    metricas = ctypes.windll.user32.GetSystemMetrics
    origen = (metricas(76), metricas(77))  # SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN
    with _lock:
        return _capturar_region(origen, metricas(78), metricas(79)), origen


def _cliente(hwnd: int) -> tuple[tuple[int, int], int, int]:
    """Zona del juego sin bordes ni barra de titulo: esquina en pantalla, ancho y alto."""
    _, _, ancho, alto = win32gui.GetClientRect(hwnd)
    return win32gui.ClientToScreen(hwnd, (0, 0)), ancho, alto


def _capturar_reducida(hwnd: int, ancho_ref: int, alto_ref: int):
    """Con la ventana mas pequena que la de referencia: la zona del juego agrandada a 538x921 y puesta donde
    estaria en una captura normal, con su Origen. None si la ventana es de tamano normal."""
    izq, arr, der, aba = win32gui.GetWindowRect(hwnd)
    if aba - arr >= TAMANO_OBJETIVO[1] - TOLERANCIA_PX:  # ventana de tamano normal: captura de siempre
        return None
    cliente, ancho, alto = _cliente(hwnd)
    if ancho <= 0 or alto <= 0:
        return None
    juego = cv2.resize(_capturar_region(cliente, ancho, alto), REF_CLIENTE, interpolation=cv2.INTER_CUBIC)
    lienzo = np.zeros((alto_ref, ancho_ref, 3), dtype=np.uint8)
    x0, y0 = REF_ORIGEN_CLIENTE
    trozo = juego[:alto_ref - y0, :ancho_ref - x0]
    lienzo[y0:y0 + trozo.shape[0], x0:x0 + trozo.shape[1]] = trozo
    return lienzo, Origen((0, 0), cliente, (ancho / REF_CLIENTE[0], alto / REF_CLIENTE[1]))


def capturar() -> tuple[np.ndarray, tuple[int, int]]:
    """Captura de la ventana del juego (BGR) y la esquina superior izquierda en pantalla.

    Se copia desde el escritorio, asi que la ventana tiene que estar visible (no tapada). En pantallas
    bajas la ventana es mas pequena: la captura se agranda al tamano de siempre (ver Origen).
    """
    with _lock:
        ultimo_error = None
        for _ in range(3):
            try:
                origen, ancho, alto = _region()
                ancho_ref, alto_ref = TAMANO_OBJETIVO[0] - BORDE_LATERAL * 2, TAMANO_OBJETIVO[1] - BORDE_INFERIOR
                reducida = _capturar_reducida(buscar_ventana(), ancho_ref, alto_ref)
                if reducida is not None:
                    return reducida
                return _capturar_region(origen, ancho, alto), Origen(origen)
            except VentanaNoEncontrada:
                raise
            except Exception as error:  # fallos puntuales de GDI
                ultimo_error = error
                time.sleep(0.05)
        raise RuntimeError(f"No pude capturar la ventana: {ultimo_error}")


# Tamano de la ventana COMPLETA (con barra de titulo y bordes) para el que estan hechas las
# plantillas y coordenadas de AutoFarming: da capturas de 550x940. Comprobado con capturas reales.
TAMANO_OBJETIVO = (554, 960)
TOLERANCIA_PX = 3


def tamano_actual() -> tuple[int, int] | None:
    """Tamano exterior de la ventana del juego, o None si no esta abierta."""
    hwnd = buscar_ventana()
    if not hwnd:
        return None
    izq, arr, der, aba = win32gui.GetWindowRect(hwnd)
    return der - izq, aba - arr


def _alto_util() -> int:
    """Alto de la pantalla principal sin la barra de tareas."""
    rect = ctypes.wintypes.RECT()
    if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):  # SPI_GETWORKAREA
        return rect.bottom - rect.top
    return ctypes.windll.user32.GetSystemMetrics(1)


def tamano_objetivo() -> tuple[int, int]:
    """El tamano en que hay que dejar la ventana: TAMANO_OBJETIVO si cabe; si no, mas pequena con la misma
    forma de la zona del juego, tan alta como la pantalla sin la barra de tareas."""
    alto_util = _alto_util()
    if alto_util >= TAMANO_OBJETIVO[1]:
        return TAMANO_OBJETIVO
    marco = (TAMANO_OBJETIVO[0] - REF_CLIENTE[0], TAMANO_OBJETIVO[1] - REF_CLIENTE[1])  # bordes y barra de titulo
    hwnd = buscar_ventana()
    if hwnd:
        izq, arr, der, aba = win32gui.GetWindowRect(hwnd)
        _, ancho, alto = _cliente(hwnd)
        if ancho > 0 and alto > 0:
            marco = (der - izq - ancho, aba - arr - alto)
    escala = (alto_util - marco[1]) / REF_CLIENTE[1]
    return round(REF_CLIENTE[0] * escala) + marco[0], alto_util


def tamano_correcto(tam: tuple[int, int] | None = None) -> bool:
    tam = tamano_actual() if tam is None else tam
    return tam is not None and all(abs(a - b) <= TOLERANCIA_PX for a, b in zip(tam, tamano_objetivo()))


def es_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


AVISO_ADMIN = (
    "Windows no deja tocar la ventana del juego porque el juego corre como administrador. "
    "Cierra LumenFarm y vuelve a abrirlo aceptando el aviso de administrador."
)

ultimo_error = ""  # motivo del ultimo ajuste fallido, para mostrarlo en la interfaz


def ajustar_tamano() -> bool:
    """Deja la ventana del juego en tamano_objetivo() (TAMANO_OBJETIVO si cabe en la pantalla).

    Nunca lanza excepciones: si falla devuelve False y deja el motivo en ``ultimo_error``.
    """
    global ultimo_error
    with _lock:
        ancho, alto = tamano_objetivo()
        hwnd = buscar_ventana()
        if not hwnd:
            ultimo_error = f"No encuentro la ventana '{config.obtener('titulo_ventana')}'."
            return False
        try:
            # Ya esta bien: no moverla (el plan del dia la recolocaba en cada tarea y "saltaba", 2026-11-10)
            if not win32gui.IsIconic(hwnd) and tamano_correcto():
                ultimo_error = ""
                return True
        except win32gui.error:
            pass
        try:
            izq, arr, _, _ = win32gui.GetWindowRect(hwnd)
            # Que quede entera dentro de la pantalla
            pantalla_ancho = ctypes.windll.user32.GetSystemMetrics(0)
            pantalla_alto = ctypes.windll.user32.GetSystemMetrics(1)
            izq = max(0, min(izq, pantalla_ancho - ancho))
            arr = max(0, min(arr, pantalla_alto - alto))
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, izq, arr, ancho, alto, win32con.SWP_SHOWWINDOW)
        except win32gui.error as error:
            ultimo_error = AVISO_ADMIN if error.winerror == 5 and not es_admin() else f"No pude ajustar la ventana: {error.strerror}"
            return False
        time.sleep(0.3)
        actual = tamano_actual()
        if tamano_correcto(actual):
            ultimo_error = ""
            return True
        ultimo_error = f"La ventana quedo en {actual[0]}x{actual[1]} en vez de {ancho}x{alto}." if actual else "La ventana se cerro."
        return False


def traer_al_frente() -> None:
    hwnd = buscar_ventana()
    if hwnd:
        try:
            if win32gui.GetForegroundWindow() == hwnd and not win32gui.IsIconic(hwnd):
                return  # ya esta delante: no tocarla
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
        except win32gui.error:
            pass
