"""Leer texto de la pantalla con el OCR que trae Windows (paquetes winrt).

Se usa para la captura de heroes (nombres, atributos, descripciones de cartas), no al farmear.
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

    resultado = asyncio.run(reconocer())
    return [linea.text.strip() for linea in resultado.lines if linea.text.strip()]


def leer_region(pantalla: np.ndarray, region: tuple[int, int, int, int], **opciones) -> list[str]:
    x1, y1, x2, y2 = region
    return leer(pantalla[y1:y2, x1:x2], **opciones)
