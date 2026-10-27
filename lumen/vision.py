"""Busqueda de plantillas (template matching) sobre capturas del juego."""

from pathlib import Path

import cv2
import numpy as np

from lumen.rutas import IMAGENES

RECT_VACIO = np.zeros((0, 4), dtype=np.int32)


def leer_imagen(ruta: Path) -> np.ndarray | None:
    """cv2.imread no soporta rutas con tildes en Windows; se lee como bytes."""
    try:
        datos = np.frombuffer(Path(ruta).read_bytes(), dtype=np.uint8)
        return cv2.imdecode(datos, cv2.IMREAD_COLOR) if datos.size else None
    except OSError:
        return None


def guardar_imagen(ruta: Path, imagen: np.ndarray) -> None:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ok, datos = cv2.imencode(ruta.suffix if ruta.suffix in (".png", ".jpg") else ".png", imagen)
    if not ok:
        raise RuntimeError(f"No se pudo guardar {ruta}")
    ruta.write_bytes(datos.tobytes())


class Plantilla:
    """Una o varias imagenes que representan lo mismo (p. ej. todos los botones OK).

    Las rutas relativas se buscan en assets/imagenes. Se cargan la primera vez que se usan.
    """

    def __init__(self, *rutas: str | Path, nombre: str | None = None):
        self.rutas = [Path(r) if Path(r).is_absolute() else IMAGENES / r for r in rutas]
        self.nombre = nombre or self.rutas[0].stem
        self._imagenes: list[np.ndarray] | None = None

    @property
    def imagenes(self) -> list[np.ndarray]:
        if self._imagenes is None:
            self._imagenes = [img for img in (leer_imagen(r) for r in self.rutas) if img is not None]
        return self._imagenes

    @property
    def disponible(self) -> bool:
        return bool(self.imagenes)

    def recargar(self):
        self._imagenes = None

    def confianza(self, pantalla: np.ndarray | None) -> tuple[float, np.ndarray]:
        """Mejor coincidencia entre todas las imagenes: (confianza 0..1, rectangulo x,y,w,h)."""
        mejor, rect = -1.0, RECT_VACIO
        if pantalla is None:
            return mejor, rect
        for plantilla in self.imagenes:
            ph, pw = plantilla.shape[:2]
            if ph > pantalla.shape[0] or pw > pantalla.shape[1]:
                continue
            resultado = cv2.matchTemplate(pantalla, plantilla, cv2.TM_CCOEFF_NORMED)
            _, valor, _, (x, y) = cv2.minMaxLoc(resultado)
            if valor > mejor:
                mejor, rect = float(valor), np.array([x, y, pw, ph], dtype=np.int32)
        return mejor, rect

    def buscar(self, pantalla: np.ndarray | None, umbral: float = 0.7) -> np.ndarray | None:
        """Rectangulo de la mejor coincidencia, o None si no supera el umbral."""
        valor, rect = self.confianza(pantalla)
        return rect if valor >= umbral else None

    def esta(self, pantalla: np.ndarray | None, umbral: float = 0.7) -> bool:
        return self.buscar(pantalla, umbral) is not None

    def buscar_todas(self, pantalla: np.ndarray, umbral: float = 0.7) -> list[np.ndarray]:
        """Todas las apariciones (agrupando las que se solapan)."""
        rects = []
        for plantilla in self.imagenes:
            ph, pw = plantilla.shape[:2]
            if ph > pantalla.shape[0] or pw > pantalla.shape[1]:
                continue
            resultado = cv2.matchTemplate(pantalla, plantilla, cv2.TM_CCOEFF_NORMED)
            ys, xs = np.where(resultado >= umbral)
            rects.extend([int(x), int(y), pw, ph] for x, y in zip(xs, ys))
        return agrupar(rects)


def agrupar(rects: list) -> list[np.ndarray]:
    """Une rectangulos solapados en uno solo."""
    if not rects:
        return []
    dobles = [list(r) for r in rects] * 2  # groupRectangles descarta grupos de 1 elemento
    agrupados, _ = cv2.groupRectangles(dobles, groupThreshold=1, eps=0.5)
    return [np.asarray(r) for r in agrupados]


def recortar(imagen: np.ndarray, region: tuple[int, int, int, int]) -> np.ndarray:
    """region = (x1, y1, x2, y2)."""
    x1, y1, x2, y2 = region
    return imagen[y1:y2, x1:x2]
