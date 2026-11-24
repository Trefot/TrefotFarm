"""Prueba del modo en segundo plano: ¿se puede farmear sin mover el raton ni tener el juego delante?

Hoy el bot copia de la pantalla la zona donde esta el juego (si algo lo tapa, ve eso) y mueve el raton de
verdad (no se puede usar el PC a la vez). Windows tiene otra forma de hacer cada cosa, que unos juegos
aceptan y otros no; esto lo prueba en el PC del jugador con 7DS abierto:

1. Ver: PrintWindow pide la imagen a la propia ventana del juego (aunque este tapada).
2. Tocar: PostMessage le manda el clic a la ventana sin mover el raton.

Se lanza con ProbarSegundoPlano.bat (como administrador, igual que el juego). Guarda las imagenes y un
informe en logs/segundo_plano/ y lo escribe en la consola para pegarlo en el chat. No cambia nada del bot.
"""

import ctypes
import time
from pathlib import Path

import cv2
import numpy as np

from lumen.rutas import LOGS

CARPETA = LOGS / "segundo_plano"
PW_RENDERFULLCONTENT = 2  # pide tambien lo que dibuja la tarjeta grafica (DirectX), si no sale negro
PARECIDA = 25.0  # diferencia media (0-255) por debajo: es la misma imagen (con animaciones del juego)
CAMBIO = 12.0  # diferencia media por encima tras el clic: la pantalla del juego cambio
WM_MOUSEMOVE, WM_LBUTTONDOWN, WM_LBUTTONUP, MK_LBUTTON = 0x0200, 0x0201, 0x0202, 0x0001
WM_ACTIVATE, WM_SETFOCUS, WM_NCACTIVATE, WM_ACTIVATEAPP, WM_SETCURSOR = 0x0006, 0x0007, 0x0086, 0x001C, 0x0020
WA_ACTIVE, HTCLIENT = 1, 1
# Toque con el dedo (InjectTouchInput): Windows lo pone en ese punto de la pantalla sin mover el raton
PT_TOUCH, TOUCH_FEEDBACK_NONE = 2, 3
POINTER_FLAG_INRANGE, POINTER_FLAG_INCONTACT, POINTER_FLAG_DOWN, POINTER_FLAG_UP = 0x2, 0x4, 0x10000, 0x40000


def diferencia(a: np.ndarray | None, b: np.ndarray | None) -> float:
    """Diferencia media entre dos capturas (255 si falta una). En pantallas bajas el bot agranda su captura:
    la otra se lleva a su tamano antes de comparar."""
    if a is None or b is None or a.ndim != b.ndim:
        return 255.0
    if a.shape != b.shape:
        b = cv2.resize(b, (a.shape[1], a.shape[0]))
    return float(cv2.absdiff(a, b).mean())


def es_negra(img: np.ndarray | None) -> bool:
    return img is None or float(img.mean()) < 8


def lparam(x: int, y: int) -> int:
    """Coordenadas de un mensaje del raton: y en la palabra alta, x en la baja."""
    return ((int(y) & 0xFFFF) << 16) | (int(x) & 0xFFFF)


def capturar_ventana(hwnd: int) -> np.ndarray | None:
    """La imagen de la ventana con PrintWindow, recortada como la captura de siempre (sin los bordes que quita
    el bot). None si Windows no la da."""
    import win32gui
    import win32ui

    from lumen.ventana import BORDE_INFERIOR, BORDE_LATERAL

    izq, arr, der, aba = win32gui.GetWindowRect(hwnd)
    ancho, alto = der - izq, aba - arr
    if ancho <= 0 or alto <= 0:
        return None
    hdc = win32gui.GetWindowDC(hwnd)
    dc = win32ui.CreateDCFromHandle(hdc)
    mem = dc.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap()
    try:
        bmp.CreateCompatibleBitmap(dc, ancho, alto)
        mem.SelectObject(bmp)
        if not ctypes.windll.user32.PrintWindow(hwnd, mem.GetSafeHdc(), PW_RENDERFULLCONTENT):
            return None
        datos = np.frombuffer(bmp.GetBitmapBits(True), dtype=np.uint8).reshape(alto, ancho, 4)
        img = cv2.cvtColor(datos, cv2.COLOR_BGRA2BGR)
        return img[:alto - BORDE_INFERIOR, BORDE_LATERAL:ancho - BORDE_LATERAL].copy()
    finally:
        win32gui.DeleteObject(bmp.GetHandle())
        mem.DeleteDC()
        dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hdc)


def clic_mensaje(hwnd: int, x_pantalla: int, y_pantalla: int, enviar: bool = False) -> int:
    """Un clic mandado a la ventana (a la hija que este en ese punto, si la hay) sin mover el raton.
    ``enviar``: SendMessage (espera a que el juego lo procese) en vez de PostMessage. Devuelve la ventana usada."""
    import win32api
    import win32gui

    cx, cy = win32gui.ScreenToClient(hwnd, (x_pantalla, y_pantalla))
    destino = hwnd
    hija = win32gui.ChildWindowFromPoint(hwnd, (cx, cy))
    if hija and hija != hwnd:
        destino = hija
        cx, cy = win32gui.ScreenToClient(hija, (x_pantalla, y_pantalla))
    mandar = win32api.SendMessage if enviar else win32api.PostMessage
    mandar(destino, WM_MOUSEMOVE, 0, lparam(cx, cy))
    mandar(destino, WM_LBUTTONDOWN, MK_LBUTTON, lparam(cx, cy))
    time.sleep(0.08)
    mandar(destino, WM_LBUTTONUP, 0, lparam(cx, cy))
    return destino


def clic_activando(hwnd: int, x_pantalla: int, y_pantalla: int) -> int:
    """Como clic_mensaje, pero antes le dice a la ventana que esta activa y tiene el foco (Unity a veces ignora el
    raton de una ventana que cree inactiva) y deja el boton pulsado mas tiempo (lo lee una vez por fotograma)."""
    import win32api
    import win32gui

    cx, cy = win32gui.ScreenToClient(hwnd, (x_pantalla, y_pantalla))
    enviar = win32api.SendMessage
    enviar(hwnd, WM_ACTIVATEAPP, 1, 0)
    enviar(hwnd, WM_NCACTIVATE, 1, 0)
    enviar(hwnd, WM_ACTIVATE, WA_ACTIVE, 0)
    enviar(hwnd, WM_SETFOCUS, 0, 0)
    for _ in range(3):
        enviar(hwnd, WM_SETCURSOR, hwnd, (WM_MOUSEMOVE << 16) | HTCLIENT)
        enviar(hwnd, WM_MOUSEMOVE, 0, lparam(cx, cy))
        time.sleep(0.03)
    enviar(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam(cx, cy))
    time.sleep(0.2)
    enviar(hwnd, WM_LBUTTONUP, 0, lparam(cx, cy))
    return hwnd


def _estructuras_toque():
    from ctypes import wintypes

    class POINTER_INFO(ctypes.Structure):
        _fields_ = [("pointerType", ctypes.c_uint32), ("pointerId", ctypes.c_uint32), ("frameId", ctypes.c_uint32),
                    ("pointerFlags", ctypes.c_uint32), ("sourceDevice", wintypes.HANDLE), ("hwndTarget", wintypes.HWND),
                    ("ptPixelLocation", wintypes.POINT), ("ptHimetricLocation", wintypes.POINT),
                    ("ptPixelLocationRaw", wintypes.POINT), ("ptHimetricLocationRaw", wintypes.POINT),
                    ("dwTime", wintypes.DWORD), ("historyCount", ctypes.c_uint32), ("InputData", ctypes.c_int32),
                    ("dwKeyStates", wintypes.DWORD), ("PerformanceCount", ctypes.c_uint64),
                    ("ButtonChangeType", ctypes.c_int)]

    class POINTER_TOUCH_INFO(ctypes.Structure):
        _fields_ = [("pointerInfo", POINTER_INFO), ("touchFlags", ctypes.c_uint32), ("touchMask", ctypes.c_uint32),
                    ("rcContact", wintypes.RECT), ("rcContactRaw", wintypes.RECT), ("orientation", ctypes.c_uint32),
                    ("pressure", ctypes.c_uint32)]

    return POINTER_TOUCH_INFO


def toque(x_pantalla: int, y_pantalla: int) -> bool:
    """Un toque con el dedo en ese punto de la pantalla (InjectTouchInput). No mueve el raton, pero va a la ventana
    que este en ese punto: el juego tiene que verse. True si Windows lo acepto."""
    user32 = ctypes.windll.user32
    if not user32.InitializeTouchInjection(1, TOUCH_FEEDBACK_NONE):
        return False
    info = _estructuras_toque()()
    info.pointerInfo.pointerType = PT_TOUCH
    info.pointerInfo.pointerId = 0
    info.pointerInfo.ptPixelLocation.x, info.pointerInfo.ptPixelLocation.y = int(x_pantalla), int(y_pantalla)
    info.pointerInfo.pointerFlags = POINTER_FLAG_DOWN | POINTER_FLAG_INRANGE | POINTER_FLAG_INCONTACT
    if not user32.InjectTouchInput(1, ctypes.byref(info)):
        return False
    time.sleep(0.12)
    info.pointerInfo.pointerFlags = POINTER_FLAG_UP
    return bool(user32.InjectTouchInput(1, ctypes.byref(info)))


# ------------------------------------------------------------------ la prueba guiada
def _esperar(texto: str):
    input(f"\n{texto}\n  (pulsa Enter cuando este listo) ")


def _guardar(nombre: str, img):
    if img is not None:
        CARPETA.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(CARPETA / f"{nombre}.png"), img)


def _cursor() -> tuple[int, int]:
    import win32api

    return win32api.GetCursorPos()


def probar_ver(hwnd, normal) -> list[str]:
    lineas = []
    propia = capturar_ventana(hwnd)
    _guardar("1_printwindow", propia)
    d = diferencia(normal, propia)
    if es_negra(propia):
        lineas.append("VER (juego delante): FALLA, PrintWindow da una imagen negra.")
    else:
        lineas.append(f"VER (juego delante): {'OK' if d < PARECIDA else 'DISTINTA'} (diferencia {d:.1f}).")
    _esperar("2/3 VER TAPADO: pon otra ventana ENCIMA del juego (por ejemplo el Bloc de notas o el navegador),\n"
             "    que lo tape del todo, sin minimizar el juego.")
    tapada = capturar_ventana(hwnd)
    _guardar("2_tapada", tapada)
    d = diferencia(normal, tapada)
    if es_negra(tapada):
        lineas.append("VER (juego tapado): FALLA, imagen negra.")
    else:
        lineas.append(f"VER (juego tapado): {'OK' if d < PARECIDA else 'DISTINTA (mira 2_tapada.png)'} "
                      f"(diferencia {d:.1f}).")
    return lineas


def probar_tocar(hwnd) -> list[str]:
    from lumen import juego, ventana

    _esperar("3/3 TOCAR: deja el juego en la TAVERN (que se vea el boton de Battle), quita la ventana de encima y\n"
             "    NO toques el raton durante 10 segundos.")
    img, origen = ventana.capturar()
    rect = juego.menu_batalla.buscar(img, 0.6)
    if rect is None:
        return ["TOCAR: no se hizo (no veo el boton Battle de la Tavern)."]
    x, y, w, h = rect
    xp, yp = origen.a_pantalla(x + w // 2, y + h // 2)
    import win32gui

    lineas = []
    # 2026-11-24: PostMessage y SendMessage no hicieron nada en 7DS (Unity). Se prueban otras dos formas.
    formas = (("PostMessage", lambda: clic_mensaje(hwnd, xp, yp)),
              ("SendMessage", lambda: clic_mensaje(hwnd, xp, yp, enviar=True)),
              ("SendMessage con la ventana activa", lambda: clic_activando(hwnd, xp, yp)),
              ("toque con el dedo", lambda: hwnd if toque(xp, yp) else None))
    for nombre, tocar in formas:
        antes = capturar_ventana(hwnd)
        cursor = _cursor()
        delante = win32gui.GetForegroundWindow()
        destino = tocar()
        time.sleep(2.5)
        despues = capturar_ventana(hwnd)
        _guardar(f"3_tocar_{nombre.split()[0]}_{len(lineas)}", despues)
        if destino is None:
            lineas.append(f"TOCAR con {nombre}: Windows no lo acepto.")
            continue
        movio = _cursor() != cursor
        robo = win32gui.GetForegroundWindow() != delante
        d = diferencia(antes, despues)
        cambio = d > CAMBIO
        hija = " (a una ventana hija)" if destino != hwnd else ""
        lineas.append(f"TOCAR con {nombre}{hija}: {'OK, el juego reacciono' if cambio else 'el juego NO reacciono'} "
                      f"(cambio {d:.1f}){'; OJO: el raton se movio' if movio else ''}"
                      f"{'; la ventana del juego paso delante' if robo else ''}.")
        if cambio:
            lineas.append("  (vuelve tu a la Tavern si se abrio el menu Battle)")
            break
        time.sleep(0.5)
    return lineas


def main():
    import win32gui

    from lumen import config, ventana

    print("PRUEBA DEL MODO EN SEGUNDO PLANO (no cambia nada del bot)")
    hwnd = ventana.buscar_ventana()
    if not hwnd:
        print(f"No encuentro la ventana del juego ('{config.obtener('titulo_ventana')}'). Abre 7DS y vuelve a probar.")
        return
    _esperar("1/3 VER: deja el juego abierto y DELANTE de todo (en cualquier pantalla del juego).")
    normal, _ = ventana.capturar()
    _guardar("0_normal", normal)
    lineas = [f"Ventana: '{win32gui.GetWindowText(hwnd)}' clase '{win32gui.GetClassName(hwnd)}'"]
    try:
        lineas += probar_ver(hwnd, normal)
    except Exception as error:
        lineas.append(f"VER: error {type(error).__name__}: {error}")
    try:
        lineas += probar_tocar(hwnd)
    except Exception as error:
        lineas.append(f"TOCAR: error {type(error).__name__}: {error}")
    informe = "Lumen Farm · prueba de segundo plano\n" + "\n".join(lineas)
    CARPETA.mkdir(parents=True, exist_ok=True)
    (CARPETA / "informe.txt").write_text(informe, encoding="utf-8")
    print("\n" + "=" * 60 + "\n" + informe + "\n" + "=" * 60)
    print(f"\nCopia el informe de arriba y pegaselo a Claude. Imagenes en: {Path(CARPETA)}")


if __name__ == "__main__":
    main()
