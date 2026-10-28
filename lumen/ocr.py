"""Leer texto de la pantalla con el OCR que trae Windows (paquetes winrt).

Se usa en la captura de heroes (nombres, atributos, descripciones de cartas) y para encontrar
los botones de los pisos de las bestias.
Si los paquetes no estan instalados, ``disponible()`` devuelve False y nada mas falla.
"""

import asyncio

import cv2
import numpy as np

try:
    from winrt.windows.globalization import Language
    from winrt.windows.graphics.imaging import BitmapAlphaMode, BitmapPixelFormat, SoftwareBitmap
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.storage.streams import DataWriter
except ImportError:  # pragma: no cover - solo si faltan las dependencias
    OcrEngine = None

_motor = None


def disponible() -> bool:
    return _obtener_motor() is not None


def _obtener_motor():
    """Motor en ingles (el idioma del juego); si Windows no lo tiene, el del usuario."""
    global _motor
    if _motor is None and OcrEngine is not None:
        ingles = Language("en-US")
        _motor = OcrEngine.try_create_from_language(ingles) if OcrEngine.is_language_supported(ingles) else None
        _motor = _motor or OcrEngine.try_create_from_user_profile_languages()
    return _motor


def preparar(imagen: np.ndarray, escala: float = 2.0, invertir: bool = False) -> np.ndarray:
    """Gris, ampliado y (si el texto es claro sobre fondo oscuro) invertido: el OCR lee mejor asi."""
    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY) if imagen.ndim == 3 else imagen
    if invertir:
        gris = 255 - gris
    return cv2.resize(gris, None, fx=escala, fy=escala, interpolation=cv2.INTER_CUBIC)


def leer(imagen: np.ndarray, escala: float = 2.0, invertir: bool = False) -> list[str]:
    """Lineas de texto de la imagen (BGR o gris)."""
    return [linea.text.strip() for linea in _reconocer(imagen, escala, invertir).lines if linea.text.strip()]


def _reconocer(imagen: np.ndarray, escala: float, invertir: bool):
    motor = _obtener_motor()
    if motor is None:
        raise RuntimeError("El OCR de Windows no esta disponible (faltan los paquetes winrt).")
    gris = preparar(imagen, escala, invertir)
    bgra = cv2.cvtColor(gris, cv2.COLOR_GRAY2BGRA)
    alto, ancho = bgra.shape[:2]
    escritor = DataWriter()
    escritor.write_bytes(bgra.tobytes())
    mapa = SoftwareBitmap.create_copy_from_buffer(escritor.detach_buffer(), BitmapPixelFormat.BGRA8, ancho, alto,
                                                 BitmapAlphaMode.PREMULTIPLIED)

    async def reconocer():
        return await motor.recognize_async(mapa)

    return asyncio.run(reconocer())


def lineas_con_posicion(imagen: np.ndarray, escala: float = 2.0, invertir: bool = False) -> list[tuple[str, tuple[int, int, int, int]]]:
    """Cada linea de texto con su rectangulo (x, y, w, h) en la imagen original."""
    salida = []
    for linea in _reconocer(imagen, escala, invertir).lines:
        cajas = [p.bounding_rect for p in linea.words]
        if not cajas or not linea.text.strip():
            continue
        x1 = min(c.x for c in cajas)
        y1 = min(c.y for c in cajas)
        x2 = max(c.x + c.width for c in cajas)
        y2 = max(c.y + c.height for c in cajas)
        salida.append((linea.text.strip(), tuple(int(v / escala) for v in (x1, y1, x2 - x1, y2 - y1))))
    return salida


def leer_region(pantalla: np.ndarray, region: tuple[int, int, int, int], **opciones) -> list[str]:
    x1, y1, x2, y2 = region
    return leer(pantalla[y1:y2, x1:x2], **opciones)
